import streamlit as st
import requests
import pandas as pd
import time
import random
from datetime import datetime
from bs4 import BeautifulSoup
import urllib3 # 👈 [추가] 보안 경고 무시용

# 1. 보안 경고 메시지 끄기 (SSL 검사 무시할 때 뜨는 빨간 경고 제거)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 페이지 설정
st.set_page_config(page_title="스팀 리뷰 & 토론 수집기", layout="wide")

# --- 🔐 비밀번호 잠금 ---
password = st.text_input("🔒 접속 암호", type="password")
if password != "smilegate":
    st.warning("권한이 없습니다.")
    st.stop()

st.title("Steam 리뷰 & 토론 수집기 (Local & SSL Bypass)")

# --- 사이드바 ---
with st.sidebar:
    st.header("설정")
    menu = st.selectbox("분석 채널", ["Steam (스팀)", "Reddit (준비중)", "YouTube (준비중)"])
    st.divider()

if menu == "Steam (스팀)":
    tab1, tab2 = st.tabs(["⭐ 리뷰 수집", "🗣️ 토론장 수집"])
    
    # [TAB 1] 리뷰 수집
    with tab1:
        st.subheader("⭐ 스팀 리뷰 수집 (API 방식)")
        col1, col2 = st.columns(2)
        with col1:
            app_id_review = st.text_input("App ID (리뷰용)", value="1562700")
        with col2:
            language = st.selectbox("언어", ["all", "koreana", "english", "japanese", "schinese"], index=0)
        
        start_date = st.date_input("언제부터 수집할까요?", datetime(2025, 2, 1))
        
        if st.button("리뷰 수집 시작 🚀", key="btn_review"):
            st.toast("리뷰 탐색 시작...")
            all_reviews = []
            cursor = '*'
            progress_bar = st.progress(0)
            status_box = st.info(f"탐색 중... (목표: {start_date})")
            
            try:
                for i in range(5000):
                    params = {
                        'json': 1, 'cursor': cursor, 'language': language,
                        'num_per_page': 100, 'purchase_type': 'all', 'filter': 'recent'
                    }
                    # 👇 [수정] verify=False 추가 (SSL 검사 무시)
                    res = requests.get(f"https://store.steampowered.com/appreviews/{app_id_review}", params=params, verify=False)
                    data = res.json()
                    
                    if 'reviews' in data and len(data['reviews']) > 0:
                        last_ts = data['reviews'][-1]['timestamp_created']
                        curr_date = pd.to_datetime(last_ts, unit='s').date()
                        for r in data['reviews']:
                            r_date = pd.to_datetime(r['timestamp_created'], unit='s').date()
                            if r_date >= start_date:
                                all_reviews.append({
                                    '작성일': r_date, 
                                    '내용': r['review'].replace('\n', ' '), 
                                    '추천수': r['votes_up']
                                })
                        cursor = data['cursor']
                        status_box.info(f"{len(all_reviews)}개 수집 중... (현재: {curr_date})")
                        if curr_date < start_date: break
                    else: break
                
                if all_reviews:
                    df = pd.DataFrame(all_reviews)
                    filtered_df = df[df['작성일'] >= start_date]
                    st.success(f"✅ 완료! {len(filtered_df)}개 수집됨.")
                    st.dataframe(filtered_df)
                    st.download_button("엑셀 다운로드", filtered_df.to_csv(index=False).encode('utf-8-sig'), "steam_reviews.csv")
                else:
                    st.warning("수집된 리뷰가 없습니다.")
            except Exception as e:
                st.error(f"오류: {e}")

    # [TAB 2] 토론장 수집 (SSL 인증서 에러 해결됨 🛡️)
    with tab2:
        st.subheader("🗣️ 토론장 상세 수집 (로컬 전용)")
        st.info("💡 이제 회사 네트워크나 보안 프로그램이 있어도 뚫립니다!")
        
        target_url = st.text_input(
            "수집할 토론장 URL", 
            value="https://steamcommunity.com/app/1562700/discussions/"
        )
        
        pages_to_crawl = st.number_input("탐색 페이지 수", min_value=1, max_value=50, value=3)
        
        if st.button("토론글 수집 시작 (SSL 무시)", key="btn_discuss"):
            st.toast("서버에 접속을 시도합니다...")
            discussion_data = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
            }
            cookies = {'wants_mature_content': '1', 'birthtime': '660000001', 'lastagecheckage': '1-January-1990'}
            
            try:
                if not target_url.endswith('/') and '?' not in target_url:
                    target_url += '/'

                for p in range(pages_to_crawl):
                    full_url = f"{target_url}?fp={p+1}"
                    
                    sleep_time = random.uniform(1.0, 2.0)
                    time.sleep(sleep_time)
                    
                    # 👇 [핵심 수정] verify=False 추가 (인증서 검사 생략)
                    res = requests.get(full_url, headers=headers, cookies=cookies, timeout=15, verify=False)
                    
                    if res.status_code != 200:
                        st.error(f"❌ 접속 실패! 코드: {res.status_code}")
                        break

                    soup = BeautifulSoup(res.text, 'html.parser')
                    topics = soup.find_all('a', class_='forum_topic_link')
                    
                    if len(topics) == 0:
                        st.warning(f"⚠️ {p+1}페이지에서 글을 못 찾았습니다.")
                        break 
                    
                    status_text.text(f"✅ {p+1}페이지 접속 성공! ({len(topics)}개 글 발견)")
                    
                    for idx, topic in enumerate(topics):
                        title = topic.text.strip()
                        link = topic['href']
                        
                        time.sleep(random.uniform(0.3, 0.8))
                        # 👇 [핵심 수정] 상세 페이지도 verify=False
                        sub_res = requests.get(link, headers=headers, cookies=cookies, verify=False)
                        sub_soup = BeautifulSoup(sub_res.text, 'html.parser')
                        
                        content_div = sub_soup.find('div', class_='forum_op')
                        if content_div:
                            author = content_div.find('div', class_='author').text.strip()
                            main_text = content_div.find('div', class_='content').text.strip()
                            date_posted = content_div.find('div', class_='date').text.strip()
                            
                            discussion_data.append({'Type': '본문', 'Title': title, 'Author': author, 'Content': main_text, 'Date': date_posted, 'Link': link})
                            
                            comments = sub_soup.find_all('div', class_='commentthread_comment')
                            for comm in comments:
                                try:
                                    c_author = comm.find('bdi').text.strip()
                                    c_text = comm.find('div', class_='commentthread_comment_text').text.strip()
                                    discussion_data.append({'Type': '댓글', 'Title': f"(Re) {title}", 'Author': c_author, 'Content': c_text, 'Date': '-', 'Link': link})
                                except: continue
                        
                        current_progress = (p / pages_to_crawl) + ((idx + 1) / len(topics) / pages_to_crawl)
                        progress_bar.progress(min(current_progress, 0.99))

                progress_bar.progress(1.0)
                
                if discussion_data:
                    df = pd.DataFrame(discussion_data)
                    st.success(f"🎉 수집 완료! 총 {len(df)}개 데이터")
                    st.dataframe(df)
                    st.download_button("엑셀 다운로드", df.to_csv(index=False).encode('utf-8-sig'), "steam_discuss_full.csv")
                else:
                    st.error("수집된 데이터가 없습니다.")
                    
            except Exception as e:
                st.error(f"오류: {e}")