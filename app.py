import streamlit as st
import requests
import pandas as pd
import time
import random
import urllib3
from bs4 import BeautifulSoup

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="스팀 정밀 수집기", layout="wide")
st.title("🕷️ 스팀 토론장 수집기 (HTML 분석 완료)")

# 사이드바
with st.sidebar:
    st.header("설정")
    target_url = st.text_input("수집할 토론장 URL", value="https://steamcommunity.com/app/1562700/discussions/")
    pages_to_crawl = st.number_input("탐색 페이지 수", min_value=1, value=2)
    run_btn = st.button("수집 시작 🚀", type="primary")

if run_btn:
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
        # URL 정리
        if not target_url.endswith('/') and '?' not in target_url:
            target_url += '/'

        for p in range(pages_to_crawl):
            full_url = f"{target_url}?fp={p+1}"
            status_text.text(f"📡 {p+1}페이지 목록 읽는 중...")
            
            # 1. 목록 페이지 접속
            time.sleep(random.uniform(1.0, 2.0))
            res = requests.get(full_url, headers=headers, cookies=cookies, verify=False, timeout=15)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 목록 찾기 (forum_topic 클래스 사용)
            topic_rows = soup.find_all('div', class_='forum_topic')
            
            if not topic_rows:
                st.warning(f"⚠️ {p+1}페이지: 글 목록을 못 찾았습니다.")
                break
            
            status_text.text(f"✅ {p+1}페이지: {len(topic_rows)}개 글 발견! 내용을 긁어옵니다...")
            
            # 2. 상세 페이지 루프
            for idx, row in enumerate(topic_rows):
                try:
                    # (A) 링크와 제목 찾기
                    link_tag = row.find('a', class_='forum_topic_overlay')
                    title_tag = row.find('div', class_='forum_topic_name')
                    
                    if not link_tag: continue
                    
                    link = link_tag['href']
                    title = title_tag.text.strip() if title_tag else "제목 없음"
                    
                    # (B) 상세 페이지 접속
                    time.sleep(random.uniform(0.3, 0.7))
                    sub_res = requests.get(link, headers=headers, cookies=cookies, verify=False)
                    sub_soup = BeautifulSoup(sub_res.text, 'html.parser')
                    
                    # --- [핵심 수정: 보내주신 HTML 분석 반영] ---
                    
                    # 1. 본문(OP) 수집
                    op_div = sub_soup.find('div', class_='forum_op')
                    if op_div:
                        # 작성자: forum_op_author 클래스 안의 텍스트
                        author_tag = op_div.find('a', class_='forum_op_author')
                        author = author_tag.text.strip() if author_tag else "Unknown"
                        
                        # 내용: content 클래스
                        content_tag = op_div.find('div', class_='content')
                        content = content_tag.text.strip() if content_tag else ""
                        
                        # 날짜: date 클래스
                        date_tag = op_div.find('span', class_='date')
                        date = date_tag.text.strip() if date_tag else ""
                        
                        discussion_data.append({
                            'Type': '게시글(본문)', 
                            'Title': title, 
                            'Author': author, 
                            'Content': content, 
                            'Date': date, 
                            'Link': link
                        })
                    
                    # 2. 댓글(Comments) 수집
                    # commentthread_comment 클래스를 가진 모든 div를 찾음
                    comments = sub_soup.find_all('div', class_='commentthread_comment')
                    
                    for comm in comments:
                        try:
                            # 댓글 내용: commentthread_comment_text 클래스
                            text_div = comm.find('div', class_='commentthread_comment_text')
                            c_text = text_div.text.strip() if text_div else ""
                            
                            # 댓글 작성자: commentthread_author_link 클래스
                            author_div = comm.find('a', class_='commentthread_author_link')
                            c_author = author_div.text.strip() if author_div else "Unknown"
                            
                            # 댓글 날짜: commentthread_comment_timestamp 클래스
                            date_span = comm.find('span', class_='commentthread_comment_timestamp')
                            c_date = date_span.text.strip() if date_span else "-"

                            # 내용이 있을 때만 저장
                            if c_text:
                                discussion_data.append({
                                    'Type': 'ㄴ댓글', 
                                    'Title': f"(Re) {title}", 
                                    'Author': c_author, 
                                    'Content': c_text, 
                                    'Date': c_date, 
                                    'Link': link
                                })
                        except:
                            continue # 특정 댓글 에러나면 건너뛰기

                except Exception as e:
                    # 글 하나 에러나도 멈추지 않음
                    continue
                
                # 진행률 업데이트
                current_progress = (p / pages_to_crawl) + ((idx + 1) / len(topic_rows) / pages_to_crawl)
                progress_bar.progress(min(current_progress, 0.99))

        progress_bar.progress(1.0)
        
        if discussion_data:
            df = pd.DataFrame(discussion_data)
            st.success(f"🎉 대성공! 총 {len(df)}개의 데이터(본문+댓글)를 가져왔습니다.")
            st.dataframe(df)
            st.download_button("토론장 엑셀 다운로드", df.to_csv(index=False).encode('utf-8-sig'), "steam_discuss_complete.csv")
        else:
            st.error("데이터 수집 실패. (목록은 찾았으나 상세 내용을 못 읽음)")

    except Exception as e:
        st.error(f"에러 발생: {e}")