import streamlit as st
import requests
import pandas as pd
import time
from datetime import datetime
from bs4 import BeautifulSoup

# 페이지 설정
st.set_page_config(page_title="스팀 리뷰 & 토론 수집기", layout="wide")

# --- 🔐 비밀번호 잠금 ---
password = st.text_input("🔒 접속 암호", type="password")
if password != "smilegate":
    st.warning("권한이 없습니다.")
    st.stop()

st.title("Steam 리뷰 & 토론 수집기 (통합판)")

# --- 사이드바 ---
with st.sidebar:
    st.header("설정")
    menu = st.selectbox("분석 채널", ["Steam (스팀)", "Reddit (준비중)", "YouTube (준비중)"])
    st.divider()

if menu == "Steam (스팀)":
    tab1, tab2 = st.tabs(["⭐ 리뷰 수집", "🗣️ 토론장 수집"])
    
    # =========================================================
    # [TAB 1] 리뷰 수집 (기존 기능 복구 완료!)
    # =========================================================
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
                # 최대 5000번 반복 (안전장치)
                for i in range(5000):
                    params = {
                        'json': 1, 
                        'cursor': cursor, 
                        'language': language,
                        'num_per_page': 100, 
                        'purchase_type': 'all', 
                        'filter': 'recent'
                    }
                    res = requests.get(f"https://store.steampowered.com/appreviews/{app_id_review}", params=params)
                    data = res.json()
                    
                    if 'reviews' in data and len(data['reviews']) > 0:
                        last_ts = data['reviews'][-1]['timestamp_created']
                        curr_date = pd.to_datetime(last_ts, unit='s').date()
                        
                        # 데이터 저장
                        for r in data['reviews']:
                            r_date = pd.to_datetime(r['timestamp_created'], unit='s').date()
                            if r_date >= start_date:
                                all_reviews.append({
                                    '작성일': r_date, 
                                    '내용': r['review'].replace('\n', ' '), 
                                    '추천수': r['votes_up'],
                                    '플레이시간(분)': r['author'].get('playtime_forever', 0)
                                })
                        
                        cursor = data['cursor']
                        status_box.info(f"{len(all_reviews)}개 수집 중... (현재 탐색 위치: {curr_date})")
                        
                        # 목표 날짜보다 과거로 가면 중단
                        if curr_date < start_date: 
                            break
                    else: 
                        break # 더 이상 리뷰가 없음
                
                if all_reviews:
                    df = pd.DataFrame(all_reviews)
                    # 날짜로 한 번 더 정확히 자르기
                    filtered_df = df[df['작성일'] >= start_date]
                    
                    st.success(f"✅ 수집 완료! 총 {len(filtered_df)}개의 리뷰를 찾았습니다.")
                    st.dataframe(filtered_df)
                    st.download_button("엑셀 다운로드", filtered_df.to_csv(index=False).encode('utf-8-sig'), "steam_reviews.csv")
                else:
                    st.warning("해당 기간에 작성된 리뷰가 없습니다.")
                    
            except Exception as e:
                st.error(f"오류 발생: {e}")

    # =========================================================
    # [TAB 2] 토론장 수집 (상세 수집 기능 유지)
    # =========================================================
    with tab2:
        st.subheader("🗣️ 토론장 상세 수집 (크롤링 방식)")
        st.info("💡 목록을 읽고 → 각 글 안으로 들어가서 내용과 댓글을 가져옵니다.")
        
        target_url = st.text_input(
            "수집할 토론장 URL (브라우저 주소 복사)", 
            value="https://steamcommunity.com/app/1562700/discussions/"
        )
        
        pages_to_crawl = st.number_input("탐색할 목록 페이지 수", min_value=1, max_value=50, value=3)
        
        if st.button("토론글 상세 수집 시작 🕵️‍♀️", key="btn_discuss"):
            st.toast("수집을 시작합니다...")
            discussion_data = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
            }
            cookies = {'wants_mature_content': '1', 'birthtime': '660000001', 'lastagecheckage': '1-January-1990'}
            
            try:
                # URL 정리
                if not target_url.endswith('/') and '?' not in target_url:
                    target_url += '/'

                for p in range(pages_to_crawl):
                    # 1. 목록 페이지 접속
                    full_url = f"{target_url}?fp={p+1}"
                    res = requests.get(full_url, headers=headers, cookies=cookies) 
                    soup = BeautifulSoup(res.text, 'html.parser')
                    
                    # 글 목록 찾기
                    topics = soup.find_all('a', class_='forum_topic_link')
                    
                    if len(topics) == 0:
                        st.warning(f"⚠️ {p+1}페이지에서 글 목록을 못 찾았습니다.")
                        break 
                    
                    status_text.text(f"📄 {p+1}페이지 목록 확보! ({len(topics)}개 글). 상세 내용을 긁어옵니다...")
                    
                    # 2. 상세 내용 수집
                    for idx, topic in enumerate(topics):
                        title = topic.text.strip()
                        link = topic['href']
                        
                        # 상세 페이지 접속
                        sub_res = requests.get(link, headers=headers, cookies=cookies)
                        sub_soup = BeautifulSoup(sub_res.text, 'html.parser')
                        
                        # 본문 가져오기
                        content_div = sub_soup.find('div', class_='forum_op')
                        if content_div:
                            author = content_div.find('div', class_='author').text.strip()
                            main_text = content_div.find('div', class_='content').text.strip()
                            date_posted = content_div.find('div', class_='date').text.strip()
                            
                            discussion_data.append({
                                'Type': '게시글(본문)', 
                                'Title': title, 
                                'Author': author, 
                                'Content': main_text, 
                                'Date': date_posted, 
                                'Link': link
                            })
                            
                            # 댓글 가져오기
                            comments = sub_soup.find_all('div', class_='commentthread_comment')
                            for comm in comments:
                                try:
                                    c_author = comm.find('bdi').text.strip()
                                    c_text = comm.find('div', class_='commentthread_comment_text').text.strip()
                                    
                                    discussion_data.append({
                                        'Type': 'ㄴ댓글', 
                                        'Title': f"(Re) {title}", 
                                        'Author': c_author, 
                                        'Content': c_text, 
                                        'Date': '-', 
                                        'Link': link
                                    })
                                except: continue
                        
                        time.sleep(0.3) # 차단 방지 딜레이
                        
                        # 진행률 업데이트
                        current_progress = (p / pages_to_crawl) + ((idx + 1) / len(topics) / pages_to_crawl)
                        progress_bar.progress(min(current_progress, 0.99))

                progress_bar.progress(1.0)
                
                if discussion_data:
                    df = pd.DataFrame(discussion_data)
                    st.success(f"🎉 수집 완료! 총 {len(df)}개의 데이터(글+댓글)를 가져왔습니다.")
                    st.dataframe(df)
                    st.download_button("토론장 엑셀 다운로드", df.to_csv(index=False).encode('utf-8-sig'), "steam_discuss_full.csv")
                else:
                    st.error("데이터를 찾지 못했습니다.")
                    
            except Exception as e:
                st.error(f"오류 발생: {e}")