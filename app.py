import streamlit as st
import requests
import pandas as pd
import time
import random
import urllib3
import os
from bs4 import BeautifulSoup

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="스팀 수집기 정밀 진단", layout="wide")

st.title("🕵️‍♀️ 스팀 토론장 정밀 진단기 (HTML 저장)")

st.info("이 코드는 수집 실패 원인을 찾기 위해, 스팀이 보내준 화면을 그대로 파일로 저장합니다.")

# 1. URL 입력
target_url = st.text_input("분석할 URL", value="https://steamcommunity.com/app/1562700/discussions/")

if st.button("진단 시작 🚀"):
    status_text = st.empty()
    status_text.text("서버 접속 중...")
    
    # 헤더 설정 (최대한 사람처럼)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://store.steampowered.com/'
    }
    cookies = {'wants_mature_content': '1', 'birthtime': '660000001', 'lastagecheckage': '1-January-1990'}
    
    try:
        # URL 보정
        if not target_url.endswith('/') and '?' not in target_url:
            target_url += '/'
        full_url = f"{target_url}?fp=1"
        
        # 2. 접속 시도 (verify=False 필수)
        res = requests.get(full_url, headers=headers, cookies=cookies, verify=False, timeout=15)
        
        status_text.text(f"응답 코드: {res.status_code}")
        
        if res.status_code == 200:
            # 3. [핵심] 가져온 HTML을 파일로 저장해버리기
            # 이 파일이 생성되면, 직접 열어서 눈으로 확인할 수 있습니다.
            with open("debug_steam.html", "w", encoding="utf-8") as f:
                f.write(res.text)
            
            st.success("✅ HTML 원본 저장 완료! (debug_steam.html)")
            
            # 4. 파싱 시도
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # (A) 우리가 찾는 클래스로 찾아보기
            topics = soup.find_all('a', class_='forum_topic_link')
            
            if len(topics) > 0:
                st.balloons()
                st.success(f"🎉 와! 찾았습니다! ({len(topics)}개 발견)")
                for t in topics[:3]: # 3개만 예시로 출력
                    st.write(f"- {t.text.strip()}")
            else:
                st.error("❌ 여전히 0개입니다.")
                
                # (B) 도대체 페이지에 뭐가 있는지 분석
                st.subheader("🔍 정밀 분석 결과")
                
                page_title = soup.title.string.strip() if soup.title else "제목 없음"
                st.write(f"**페이지 제목:** {page_title}")
                
                # 페이지 안에 있는 모든 링크 개수
                all_links = soup.find_all('a')
                st.write(f"**페이지 내 전체 링크 수:** {len(all_links)}개")
                
                # 페이지 텍스트 길이
                st.write(f"**가져온 HTML 길이:** {len(res.text)} 글자")

                st.warning("👉 지금 Cursor 파일 목록에 생긴 'debug_steam.html' 파일을 클릭해서 열어보세요. 그게 로봇이 본 진짜 화면입니다.")
                
        else:
            st.error("접속 실패 (200 OK 아님)")
            
    except Exception as e:
        st.error(f"에러 발생: {e}")