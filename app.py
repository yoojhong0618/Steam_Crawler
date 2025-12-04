import streamlit as st
import requests
import pandas as pd
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# 페이지 설정
st.set_page_config(page_title="통합 게임 여론 분석기", layout="wide")

# --- 🔐 비밀번호 잠금 ---
password = st.text_input("🔒 접속 암호", type="password")
if password != "smilegate":
    st.warning("권한이 없습니다.")
    st.stop()

# --- 사이드바 ---
with st.sidebar:
    st.title("🕹️ Smilegate Research")
    
    menu = st.selectbox(
        "분석 채널 선택", 
        ["Steam (스팀)", "Reddit (레딧 - 준비중)", "YouTube (유튜브 - 준비중)"]
    )
    st.divider()

# =========================================================
# 🎮 1. Steam 로직
# =========================================================
if menu == "Steam (스팀)":
    st.header("🎮 Steam 데이터 수집")
    
    tab1, tab2 = st.tabs(["⭐ 리뷰(Review) 수집", "🗣️ 토론장(Discussion) 수집"])
    
    # -----------------------------------------------------
    # [TAB 1] 리뷰 수집기 (기존 완벽 코드)
    # -----------------------------------------------------
    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            app_id_review = st.text_input("App ID (리뷰용)", value="1562700")
        with col2:
            language = st.selectbox("언어", ["all", "koreana", "english", "japanese", "schinese"], index=0)
            
        start_date = st.date_input("시작일", datetime(2025, 2, 1))
        
        if st.button("리뷰 수집 시작 🚀", key="btn_review"):
            st.toast("리뷰 탐색 시작...")
            all_reviews = []
            cursor = '*'
            progress_bar = st.progress(0)
            status_box = st.info(f"탐색 중... (목표: {start_date})")
            
            try:
                for i in range(5000): # 50만개 제한
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
                                '추천수': r['votes_up'],
                                '플레이시간(분)': r['author']['playtime_forever']
                            })
                        cursor = data['cursor']
                        status_box.info(f"{len(all_reviews)}개 수집 중... (현재: {curr_date})")
                        if curr_date < start_date: break
                    else: break
                
                if all_reviews:
                    df = pd.DataFrame(all_reviews)
                    mask = (df['작성일'] >= start_date)
                    filtered_df = df.loc[mask]
                    st.success(f"{len(filtered_df)}개 리뷰 수집 완료!")
                    st.dataframe(filtered_df)
                    st.download_button("엑셀 다운로드", filtered_df.to_csv(index=False).encode('utf-8-sig'), "steam_reviews.csv")
            except Exception as e:
                st.error(f"에러: {e}")

    # -----------------------------------------------------
    # [TAB 2] 토론장 수집기 (안전장치 추가됨 ✨)
    # -----------------------------------------------------
    with tab2:
        st.info("💡 토론장은 직접 페이지를 방문하여 수집합니다. (1페이지 = 게시글 15개 + 댓글들)")
        
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            app_id_discuss = st.text_input("App ID (토론장용)", value="1562700")
        with col_t2:
            # 넉넉하게 10페이지 입력해도, 없으면 알아서 멈춥니다.
            pages_to_crawl = st.number_input("최대 탐색할 페이지 수", min_value=1, max_value=50, value=3)
        
        if st.button("토론글 수집 시작 🕵️‍♀️", key="btn_discuss"):
            st.toast("토론장 방문 중...")
            
            discussion_data = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                for p in range(pages_to_crawl):
                    url = f"https://steamcommunity.com/app/{app_id_discuss}/discussions/0/?fp={p+1}"
                    res = requests.get(url)
                    soup = BeautifulSoup(res.text, 'html.parser')
                    
                    # 게시글 찾기
                    topics = soup.find_all('a', class_='forum_topic_link')
                    
                    # 👇 [핵심] 여기가 바로 안전장치입니다! 
                    # 만약 게시글이 하나도 없다면? (페이지가 끝났다는 뜻)
                    if len(topics) == 0:
                        st.success(f"✅ {p+1}페이지에는 글이 없어서 수집을 종료합니다. (실제 페이지 끝 도달)")
                        progress_bar.progress(100)
                        break 
                    
                    status_text.text(f"📄 {p+1}페이지 수집 중... ({len(topics)}개 글 발견)")
                    
                    for idx, topic in enumerate(topics):
                        title = topic.text.strip()
                        link = topic['href']
                        
                        # 상세 내용 수집
                        sub_res = requests.get(link)
                        sub_soup = BeautifulSoup(sub_res.text, 'html.parser')
                        
                        content_div = sub_soup.find('div', class_='forum_op')
                        if content_div:
                            author = content_div.find('div', class_='author').text.strip()
                            main_text = content_div.find('div', class_='content').text.strip()
                            date_posted = content_div.find('div', class_='date').text.strip()
                            
                            discussion_data.append({
                                '구분': '게시글(본문)',
                                '제목': title,
                                '작성자': author,
                                '내용': main_text,
                                '작성일': date_posted,
                                '링크': link
                            })
                            
                            # 댓글 수집
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
                                        '작성일': '-',
                                        '링크': link
                                    })
                                except: continue
                        
                        time.sleep(0.5) 
                    
                    progress_bar.progress((p + 1) / pages_to_crawl)
                
                if discussion_data:
                    df_discuss = pd.DataFrame(discussion_data)
                    st.divider()
                    st.success(f"수집 완료! 총 {len(df_discuss)}개의 데이터를 찾았습니다.")
                    st.dataframe(df_discuss)
                    st.download_button("토론장 엑셀 다운로드", df_discuss.to_csv(index=False).encode('utf-8-sig'), "steam_discussions.csv")
                else:
                    st.warning("수집된 글이 없습니다.")

            except Exception as e:
                st.error(f"오류: {e}")

# =========================================================
# 👽 2. Reddit (UI만 유지)
# =========================================================
elif menu == "Reddit (레딧 - 준비중)":
    st.header("👽 Reddit 데이터 수집")
    st.info("API Key가 준비되면 코드를 추가할 예정입니다.")

# =========================================================
# 📺 3. YouTube (UI만 유지)
# =========================================================
elif menu == "YouTube (유튜브 - 준비중)":
    st.header("📺 YouTube 데이터 수집")
    st.info("API Key가 준비되면 코드를 추가할 예정입니다.")