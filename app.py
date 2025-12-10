import streamlit as st
import requests
import os  # 👈 경로 확인용 필수 부품
import urllib3
from bs4 import BeautifulSoup

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="스팀 수집기 정밀 진단", layout="wide")
st.title("🕵️‍♀️ 파일 위치 추적기")

# 1. 현재 내가 서 있는 위치 확인
current_folder = os.getcwd()
st.info(f"📂 현재 프로그램이 실행 중인 폴더: {current_folder}")

target_url = st.text_input("분석할 URL", value="https://steamcommunity.com/app/1562700/discussions/")

if st.button("진단 시작 🚀"):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    cookies = {'wants_mature_content': '1', 'birthtime': '660000001', 'lastagecheckage': '1-January-1990'}
    
    try:
        full_url = target_url if target_url.endswith('/') else target_url + '/'
        full_url += "?fp=1"
        
        res = requests.get(full_url, headers=headers, cookies=cookies, verify=False, timeout=15)
        
        if res.status_code == 200:
            # 파일 저장 (절대 경로로 저장 위치 확인)
            file_name = "debug_steam.html"
            full_path = os.path.abspath(file_name)
            
            with open(file_name, "w", encoding="utf-8") as f:
                f.write(res.text)
            
            st.success("✅ 파일 저장 성공!")
            
            # 👇 여기가 핵심입니다! 저장된 진짜 위치를 알려줍니다.
            st.warning(f"📍 파일이 저장된 진짜 위치:\n{full_path}")
            st.code(full_path, language='bash')
            
            st.write(f"가져온 데이터 크기: {len(res.text)} 글자")
            
        else:
            st.error(f"접속 실패 (코드: {res.status_code})")
            
    except Exception as e:
        st.error(f"에러: {e}")