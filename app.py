import streamlit as st
import requests
import pandas as pd
import time
import random
import urllib3
from datetime import datetime
from bs4 import BeautifulSoup

# SSL 경고 메시지 숨기기 (깔끔한 로그를 위해)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 페이지 기본 설정
st.set_page_config(page_title="Steam 데이터 수집기", layout="wide")

# --- 🔐 비밀번호 잠금 ---
password = st.text_input("접속 암호", type="password")
if password != "smilegate":
    st.warning("암호를 입력하세요.")
    st.stop()

st.title("Steam 데이터 수집기")

# --- 사이드바 ---
with st.sidebar:
    st.header("설정")
    menu = st.selectbox("분석 채널", ["Steam (스팀)", "Reddit (준비중)", "YouTube (준비중)"])
    st.divider()

if menu == "Steam (스팀)":
    tab1, tab2 = st.tabs(["리뷰 수집 (API)", "토론장 수집 (크롤링)"])
    
    # =========================================================
    # [TAB 1] 리뷰 수집 (공식 API 사용)
    # =========================================================
    with tab1:
        st.subheader("리뷰 데이터 수집")
        
        col1, col2 = st.columns(2)
        with col1:
            app_id_review = st.text_input("App ID (리뷰용)", value="1562700")
        with col2:
            language = st.selectbox("언어", ["all", "koreana", "english", "japanese", "schinese"], index=0)
        
        start_date = st.date_input("수집 시작 날짜", datetime(2025, 2, 1))
        
        if st.button("리뷰 수집 시작", key="btn_review"):
            all_reviews = []
            cursor = '*'
            status_box = st.info(f"데이터 수집 중... (목표: {start_date} 이후)")
            
            try:
                # 최대 100페이지 (약 1만개) 안전 장치
                for i in range(100): 
                    params = {
                        'json': 1, 
                        'cursor': cursor, 
                        'language': language,
                        'num_per_page': 100, 
                        'purchase_type': 'all', 
                        'filter': 'recent'
                    }
                    # verify=False로 보안 이슈 방지
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
                                    '추천수': r['votes_up'],
                                    '플레이시간(분)': r['author'].get('playtime_forever', 0)
                                })
                        
                        cursor = data['cursor']
                        status_box.info(f"현재 {len(all_reviews)}개 수집됨... (탐색 날짜: {curr_date})")
                        
                        if curr_date < start_date: break
                    else: break
                
                if all_reviews:
                    df = pd.DataFrame(all_reviews)
                    filtered_df = df[df['작성일'] >= start_date]
                    st.success(f"완료! 총 {len(filtered_df)}개의 리뷰를 수집했습니다.")
                    st.dataframe(filtered_df)
                    st.download_button("엑셀 다운로드", filtered_df.to_csv(index=False).encode('utf-8-sig'), "steam_reviews.csv")
                else:
                    st.warning("해당 기간의 리뷰가 없습니다.")
                    
            except Exception as e:
                st.error(f"오류 발생: {e}")

    # =========================================================
    # [TAB 2] 토론장 수집 (성공한 크롤링 로직 적용)
    # =========================================================
    with tab2:
        st.subheader("토론장 상세 수집 (본문+댓글)")
        
        target_url = st.text_input(
            "수집할 토론장 URL", 
            value="https://steamcommunity.com/app/1562700/discussions/"
        )
        
        pages_to_crawl = st.number_input("탐색할 페이지 수", min_value=1, max_value=20, value=2)
        
        if st.button("토론글 수집 시작", key="btn_discuss"):
            discussion_data = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
            }
            cookies = {'wants_mature_content': '1', 'birthtime': '660000001', 'lastagecheckage': '1-January-1990'}
            
            try:
                # URL 주소 보정
                if not target_url.endswith('/') and '?' not in target_url:
                    target_url += '/'

                for p in range(pages_to_crawl):
                    full_url = f"{target_url}?fp={p+1}"
                    status_text.text(f"{p+1}페이지 목록을 읽고 있습니다...")
                    
                    # 1. 목록 접속
                    time.sleep(random.uniform(1.0, 2.0))
                    res = requests.get(full_url, headers=headers, cookies=cookies, verify=False, timeout=15)
                    soup = BeautifulSoup(res.text, 'html.parser')
                    
                    # 게시글 목록 찾기 (forum_topic)
                    topic_rows = soup.find_all('div', class_='forum_topic')
                    
                    if not topic_rows:
                        st.warning(f"{p+1}페이지에서 글 목록을 찾지 못했습니다.")
                        break
                    
                    status_text.text(f"{p+1}페이지: {len(topic_rows)}개 글 발견. 상세 내용을 수집합니다...")
                    
                    # 2. 상세 내용 수집
                    for idx, row in enumerate(topic_rows):
                        try:
                            # 링크와 제목 찾기
                            link_tag = row.find('a', class_='forum_topic_overlay')
                            title_tag = row.find('div', class_='forum_topic_name')
                            
                            if not link_tag: continue
                            
                            link = link_tag['href']
                            title = title_tag.text.strip() if title_tag else "제목 없음"
                            
                            # 상세 페이지 접속
                            time.sleep(random.uniform(0.5, 1.0))
                            sub_res = requests.get(link, headers=headers, cookies=cookies, verify=False)
                            sub_soup = BeautifulSoup(sub_res.text, 'html.parser')
                            
                            # (A) 본문 수집
                            op_div = sub_soup.find('div', class_='forum_op')
                            if op_div:
                                # 작성자 (분석 결과 반영)
                                author_tag = op_div.find('a', class_='forum_op_author')
                                author = author_tag.text.strip() if author_tag else "Unknown"
                                
                                content_tag = op_div.find('div', class_='content')
                                content = content_tag.text.strip() if content_tag else ""
                                
                                date_tag = op_div.find('span', class_='date')
                                date = date_tag.text.strip() if date_tag else ""
                                
                                discussion_data.append({
                                    '구분': '게시글', '제목': title, '작성자': author, 
                                    '내용': content, '작성일': date, '링크': link
                                })
                            
                            # (B) 댓글 수집
                            comments = sub_soup.find_all('div', class_='commentthread_comment')
                            for comm in comments:
                                try:
                                    text_div = comm.find('div', class_='commentthread_comment_text')
                                    c_text = text_div.text.strip() if text_div else ""
                                    
                                    author_div = comm.find('a', class_='commentthread_author_link')
                                    c_author = author_div.text.strip() if author_div else "Unknown"
                                    
                                    if c_text:
                                        discussion_data.append({
                                            '구분': '댓글', '제목': f"(Re) {title}", 
                                            '작성자': c_author, '내용': c_text, 
                                            '작성일': '-', '링크': link
                                        })
                                except: continue

                        except Exception:
                            continue
                        
                        # 진행률 바 업데이트
                        current_progress = (p / pages_to_crawl) + ((idx + 1) / len(topic_rows) / pages_to_crawl)
                        progress_bar.progress(min(current_progress, 0.99))

                progress_bar.progress(1.0)
                
                if discussion_data:
                    df = pd.DataFrame(discussion_data)
                    st.success(f"수집 완료! 총 {len(df)}개의 데이터(본문+댓글)")
                    st.dataframe(df)
                    st.download_button("엑셀 다운로드", df.to_csv(index=False).encode('utf-8-sig'), "steam_discussion_final.csv")
                else:
                    st.error("수집된 데이터가 없습니다.")

            except Exception as e:
                st.error(f"오류 발생: {e}")