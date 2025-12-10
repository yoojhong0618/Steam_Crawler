import streamlit as st
import requests
import pandas as pd
import time
import random
import urllib3
from bs4 import BeautifulSoup

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="스팀 수집기 (Final Fix)", layout="wide")

st.title("🕷️ 스팀 토론장 수집기 (구조 변경 대응판)")

# 사이드바 설정
with st.sidebar:
    st.header("설정")
    target_url = st.text_input("수집할 토론장 URL", value="https://steamcommunity.com/app/1562700/discussions/")
    pages_to_crawl = st.number_input("탐색 페이지 수", min_value=1, value=3)
    run_btn = st.button("수집 시작 🚀", type="primary")

if run_btn:
    st.toast("스팀 서버에 접속합니다...")
    
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
            
            # 1. 목록 페이지 접속
            res = requests.get(full_url, headers=headers, cookies=cookies, verify=False, timeout=15)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 🔍 [수정된 부분] class="forum_topic" 인 덩어리를 먼저 찾습니다.
            topic_divs = soup.find_all('div', class_='forum_topic')
            
            if not topic_divs:
                st.warning(f"⚠️ {p+1}페이지: 글을 못 찾았습니다.")
                # 혹시 모르니 HTML 구조 힌트 남기기
                with st.expander("HTML 구조 확인"):
                    st.code(soup.prettify()[:1000], language='html')
                break
            
            status_text.text(f"✅ {p+1}페이지: {len(topic_divs)}개 글 발견! 상세 내용을 읽습니다...")
            
            # 2. 상세 수집 루프
            for idx, div in enumerate(topic_divs):
                try:
                    # (A) 링크 찾기 (overlay 클래스에서 href 추출)
                    overlay_link = div.find('a', class_='forum_topic_overlay')
                    if overlay_link:
                        link = overlay_link['href']
                    else:
                        continue # 링크 없으면 패스

                    # (B) 제목 찾기 (topic_name 클래스에서 텍스트 추출)
                    name_div = div.find('div', class_='forum_topic_name')
                    title = name_div.text.strip() if name_div else "제목 없음"
                    
                    # (C) 상세 페이지 접속 (Deep Dive)
                    time.sleep(random.uniform(0.3, 0.8)) # 딜레이
                    
                    sub_res = requests.get(link, headers=headers, cookies=cookies, verify=False)
                    sub_soup = BeautifulSoup(sub_res.text, 'html.parser')
                    
                    # 본문 내용
                    content_div = sub_soup.find('div', class_='forum_op')
                    if content_div:
                        author = content_div.find('div', class_='author').text.strip()
                        main_text = content_div.find('div', class_='content').text.strip()
                        date_posted = content_div.find('div', class_='date').text.strip()
                        
                        discussion_data.append({
                            'Type': '본문', 
                            'Title': title, 
                            'Author': author, 
                            'Content': main_text, 
                            'Date': date_posted, 
                            'Link': link
                        })
                        
                        # 댓글 내용
                        comments = sub_soup.find_all('div', class_='commentthread_comment')
                        for comm in comments:
                            try:
                                c_author = comm.find('bdi').text.strip()
                                c_text = comm.find('div', class_='commentthread_comment_text').text.strip()
                                discussion_data.append({
                                    'Type': '댓글', 
                                    'Title': f"(Re) {title}", 
                                    'Author': c_author, 
                                    'Content': c_text, 
                                    'Date': '-', 
                                    'Link': link
                                })
                            except: continue

                except Exception as e:
                    print(f"글 파싱 에러: {e}")
                    continue
                
                # 진행률 업데이트
                current_progress = (p / pages_to_crawl) + ((idx + 1) / len(topic_divs) / pages_to_crawl)
                progress_bar.progress(min(current_progress, 0.99))

        progress_bar.progress(1.0)
        
        if discussion_data:
            df = pd.DataFrame(discussion_data)
            st.success(f"🎉 성공! 총 {len(df)}개의 데이터를 수집했습니다.")
            st.dataframe(df)
            st.download_button("엑셀 다운로드", df.to_csv(index=False).encode('utf-8-sig'), "steam_final_data.csv")
        else:
            st.error("데이터를 수집하지 못했습니다.")

    except Exception as e:
        st.error(f"에러 발생: {e}")