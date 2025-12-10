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

st.title("Steam 리뷰 & 토론 수집기")

# --- 사이드바 ---
with st.sidebar:
    st.header("설정")
    menu = st.selectbox("분석 채널", ["Steam (스팀)", "Reddit (준비중)", "YouTube (준비중)"])
    st.divider()

if menu == "Steam (스팀)":
    tab1, tab2 = st.tabs(["⭐ 리뷰 수집", "🗣️ 토론장 수집"])
    
    # [TAB 1] 리뷰 수집 (기존과 동일)
    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            app_id_review = st.text_input("App ID (리뷰용)", value="1562700")
        with col2:
            language = st.selectbox("언어", ["all", "koreana", "english", "japanese", "schinese"], index=0)
        start_date = st.date_input("시작일", datetime(2025, 2, 1))
        
        if st.button("리뷰 수집 시작", key="btn_review"):
            # (기존 리뷰 코드 생략 - 잘 되니까 그대로 두셔도 됩니다)
            st.toast("기존 리뷰 수집 로직 실행")
            # ... (이전 코드 그대로 사용하시면 됩니다) ...

    # [TAB 2] 토론장 수집 (목록 -> 상세 내용 -> 댓글까지 수집)
    with tab2:
        st.info("💡 1. 목록 페이지(이미지1)를 읽고 -> 2. 각 글(이미지2)로 들어가서 내용과 댓글을 가져옵니다.")
        
        # URL 직접 입력 방식 (질문자님이 원하시는 그 주소!)
        target_url = st.text_input(
            "수집할 토론장 URL", 
            value="https://steamcommunity.com/app/1562700/discussions/"
        )
        
        pages_to_crawl = st.number_input("탐색할 페이지 수 (목록 페이지 기준)", min_value=1, max_value=50, value=3)
        
        if st.button("토론글 상세 수집 시작", key="btn_discuss"):
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
                # URL 끝에 '/'가 없으면 붙여줌 (안전장치)
                if not target_url.endswith('/') and '?' not in target_url:
                    target_url += '/'

                for p in range(pages_to_crawl):
                    # 1. 목록 페이지 접속 (이미지 1)
                    full_url = f"{target_url}?fp={p+1}"
                    
                    res = requests.get(full_url, headers=headers, cookies=cookies) 
                    soup = BeautifulSoup(res.text, 'html.parser')
                    
                    # 글 목록(제목+링크) 찾기
                    topics = soup.find_all('a', class_='forum_topic_link')
                    
                    # [예외처리] 목록이 없으면? (로비 페이지거나 에러)
                    if len(topics) == 0:
                        st.warning(f"⚠️ {p+1}페이지에서 글 목록을 못 찾았습니다.")
                        
                        # 혹시 '일반 토론' 링크가 있는지 찾아봅니다 (자동 길찾기)
                        general_link = soup.find('a', class_='forum_link', string=lambda t: "General" in t if t else False)
                        if general_link:
                            st.info(f"👉 '{general_link.text.strip()}' 게시판을 발견했습니다. URL을 {general_link['href']} 로 바꿔서 다시 시도해보세요.")
                        else:
                            with st.expander("개발자용 힌트 (접속 화면)"):
                                st.write(f"접속 URL: {full_url}")
                                st.write("페이지 제목: " + (soup.title.string.strip() if soup.title else "없음"))
                        break 
                    
                    status_text.text(f"📄 {p+1}페이지 목록 확보! ({len(topics)}개 글). 상세 내용을 긁어옵니다...")
                    
                    # 2. 각 글 안으로 들어가기 (이미지 2 - Deep Dive)
                    for idx, topic in enumerate(topics):
                        title = topic.text.strip()
                        link = topic['href']
                        
                        # 상세 페이지 접속
                        sub_res = requests.get(link, headers=headers, cookies=cookies)
                        sub_soup = BeautifulSoup(sub_res.text, 'html.parser')
                        
                        # (A) 본문 내용 가져오기
                        content_div = sub_soup.find('div', class_='forum_op')
                        if content_div:
                            author = content_div.find('div', class_='author').text.strip()
                            main_text = content_div.find('div', class_='content').text.strip()
                            date_posted = content_div.find('div', class_='date').text.strip()
                            
                            # 게시글 데이터 저장
                            post_item = {
                                'Type': '게시글(본문)', 
                                'Title': title, 
                                'Author': author, 
                                'Content': main_text, 
                                'Date': date_posted, 
                                'Link': link
                            }
                            discussion_data.append(post_item)
                            
                            # (B) 댓글 내용 가져오기
                            comments = sub_soup.find_all('div', class_='commentthread_comment')
                            for comm in comments:
                                try:
                                    c_author = comm.find('bdi').text.strip()
                                    c_text = comm.find('div', class_='commentthread_comment_text').text.strip()
                                    
                                    # 댓글 데이터 저장 (제목은 본문 제목 따라감)
                                    comment_item = {
                                        'Type': 'ㄴ댓글', 
                                        'Title': f"(Re) {title}", 
                                        'Author': c_author, 
                                        'Content': c_text, 
                                        'Date': '-', 
                                        'Link': link
                                    }
                                    discussion_data.append(comment_item)
                                except: continue
                        
                        # 너무 빠르면 차단당하니까 살짝 쉬기
                        time.sleep(0.5)
                        
                        # 진행상황 업데이트 (목록 1개 처리할 때마다)
                        current_progress = (p / pages_to_crawl) + ((idx + 1) / len(topics) / pages_to_crawl)
                        progress_bar.progress(min(current_progress, 0.99))

                progress_bar.progress(1.0)
                
                if discussion_data:
                    df = pd.DataFrame(discussion_data)
                    st.success(f"🎉 수집 완료! 총 {len(df)}개의 글과 댓글을 가져왔습니다.")
                    st.dataframe(df)
                    st.download_button("토론장 엑셀 다운로드", df.to_csv(index=False).encode('utf-8-sig'), "steam_discuss_full.csv")
                else:
                    st.error("데이터를 찾지 못했습니다.")
                    
            except Exception as e:
                st.error(f"오류 발생: {e}")