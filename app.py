import streamlit as st
import requests
import pandas as pd
import time
from datetime import datetime
from bs4 import BeautifulSoup

# 페이지 설정
st.set_page_config(page_title="스팀 리뷰 수집기", layout="wide")

# --- 🔐 비밀번호 잠금 ---
password = st.text_input("🔒 접속 암호", type="password")
if password != "smilegate":
    st.warning("권한이 없습니다.")
    st.stop()

st.title("Steam 리뷰 & 토론 수집기")

# --- 사이드바 ---
with st.sidebar:
    st.header("설정")
    menu = st.selectbox("분석 채널", ["Steam (스팀)", "Reddit (준비중)", "YouTube (준비중)"])
    st.divider()

# =========================================================
# 🎮 Steam 로직
# =========================================================
if menu == "Steam (스팀)":
    tab1, tab2 = st.tabs(["⭐ 리뷰 수집", "🗣️ 토론장 수집"])
    
    # [TAB 1] 리뷰 수집 (API)
    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            app_id_review = st.text_input("App ID (리뷰용)", value="1562700")
        with col2:
            language = st.selectbox("언어", ["all", "koreana", "english", "japanese", "schinese"], index=0)
        
        start_date = st.date_input("시작일", datetime(2025, 2, 1))
        
        if st.button("리뷰 수집 시작", key="btn_review"):
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
                    res = requests.get(f"https://store.steampowered.com/appreviews/{app_id_review}", params=params)
                    data = res.json()
                    
                    if 'reviews' in data and len(data['reviews']) > 0:
                        last_ts = data['reviews'][-1]['timestamp_created']
                        curr_date = pd.to_datetime(last_ts, unit='s').date()
                        for r in data['reviews']:
                            r_date = pd.to_datetime(r['timestamp_created'], unit='s').date()
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
                    mask = (df['작성일'] >= start_date)
                    filtered_df = df.loc[mask]
                    st.success(f"{len(filtered_df)}개 완료!")
                    st.dataframe(filtered_df)
                    st.download_button("엑셀 다운로드", filtered_df.to_csv(index=False).encode('utf-8-sig'), "steam_reviews.csv")
            except Exception as e:
                st.error(f"에러: {e}")

    # [TAB 2] 토론장 수집 (헤더 추가 & 문법 오류 수정됨)
    with tab2:
        st.info("토론장은 직접 페이지를 방문하여 수집합니다.")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            app_id_discuss = st.text_input("App ID (토론장용)", value="1562700")
        with col_t2:
            pages_to_crawl = st.number_input("탐색 페이지 수", min_value=1, max_value=50, value=3)
        
        if st.button("토론글 수집 시작", key="btn_discuss"):
            st.toast("토론장 방문 중...")
            discussion_data = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # 봇 차단 방지용 헤더
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
            }
            
            try:
                for p in range(pages_to_crawl):
                    url = f"https://steamcommunity.com/app/{app_id_discuss}/discussions/0/?fp={p+1}"
                    res = requests.get(url, headers=headers) 
                    soup = BeautifulSoup(res.text, 'html.parser')
                    
                    topics = soup.find_all('a', class_='forum_topic_link')
                    
                    if len(topics) == 0:
                        page_title = soup.title.string if soup.title else "제목 없음"
                        st.warning(f"{p+1}페이지에서 글을 못 찾았습니다. (스팀 응답: {page_title})")
                        break 
                    
                    status_text.text(f"{p+1}페이지 수집 중... ({len(topics)}개 글 발견)")
                    
                    for topic in topics:
                        title = topic.text.strip()
                        link = topic['href']
                        
                        # 상세 페이지 접속
                        sub_res = requests.get(link, headers=headers)
                        sub_soup = BeautifulSoup(sub_res.text, 'html.parser')
                        
                        content_div = sub_soup.find('div', class_='forum_op')
                        if content_div:
                            author = content_div.find('div', class_='author').text.strip()
                            main_text = content_div.find('div', class_='content').text.strip()
                            date_posted = content_div.find('div', class_='date').text.strip()
                            
                            # 게시글 저장 (여기서 괄호를 확실히 닫았습니다!)
                            discussion_data.append({
                                '구분': '게시글', 
                                '제목': title, 
                                '작성자': author, 
                                '내용': main_text, 
                                '작성일': date_posted
                            })
                            
                            # 댓글 수집 (들여쓰기 주의)
                            comments = sub_soup.find_all('div', class_='commentthread_comment')
                            for comm in comments:
                                try:
                                    c_author = comm.find('bdi').text.strip()
                                    c_text = comm.find('div', class_='commentthread_comment_text').text.strip()
                                    discussion_data.append({
                                        '구분': 'ㄴ댓글', 
                                        '제목': '-', 
                                        '작성자': c_author, 
                                        '내용': c_text, 
                                        '작성일': '-'
                                    })
                                except: 
                                    continue
                        
                        time.sleep(0.5)
                    
                    progress_bar.progress((p + 1) / pages_to_crawl)
                
                if discussion_data:
                    df = pd.DataFrame(discussion_data)
                    st.success(f"{len(df)}개 수집 완료!")
                    st.dataframe(df)
                    st.download_button("토론장 엑셀 다운로드", df.to_csv(index=False).encode('utf-8-sig'), "steam_discuss.csv")
                else:
                    st.error("수집된 데이터가 없습니다.")
                    
            except Exception as e:
                st.error(f"오류: {e}")