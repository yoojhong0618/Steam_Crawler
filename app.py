import streamlit as st
import requests
import pandas as pd
import json
import time

# 1. 화면 구성 (사이트 제목 등)
st.set_page_config(page_title="스팀 리뷰 크롤러", layout="wide")
st.title("🎮 Steam 게임 리뷰 수집기")

# 2. 왼쪽 사이드바 (설정 입력창)
with st.sidebar:
    st.header("설정 (Settings)")
    # 기본값은 배틀그라운드(578080)로 설정해두었습니다.
    app_id = st.text_input("스팀 게임 App ID 입력", value="578080")
    st.caption("※ App ID는 스팀 상점 URL의 숫자 부분입니다.")
    
    language = st.selectbox("언어 선택", ["english", "koreana", "japanese", "schinese", "all"])
    review_limit = st.number_input("가져올 리뷰 개수 (최대 100개 단위)", min_value=100, max_value=5000, step=100, value=100)
    
    run_btn = st.button("데이터 수집 시작 🚀")

# 3. 버튼을 눌렀을 때 작동하는 로직
if run_btn:
    if not app_id:
        st.error("App ID를 입력해주세요!")
    else:
        st.info(f"App ID: {app_id} 의 리뷰를 {language} 언어로 수집합니다...")
        
        all_reviews = []
        cursor = '*' # 다음 페이지를 찾기 위한 책갈피
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # 100개씩 끊어서 가져오기 계산
            num_requests = review_limit // 100
            
            for i in range(num_requests):
                # Steam 서버에 데이터 요청 (여기가 핵심!)
                url = f"https://store.steampowered.com/appreviews/{app_id}?json=1&cursor={cursor}&language={language}&num_per_page=100&purchase_type=all"
                response = requests.get(url)
                data = response.json()
                
                if 'reviews' in data and len(data['reviews']) > 0:
                    for review in data['reviews']:
                        review_data = {
                            '작성일': pd.to_datetime(review['timestamp_created'], unit='s'),
                            '작성자ID': review['author']['steamid'],
                            '플레이시간(분)': review['author']['playtime_forever'],
                            '추천여부': '추천' if review['voted_up'] else '비추천',
                            '내용': review['review'].replace('\n', ' '), # 줄바꿈 제거
                            '유용함_수': review['votes_up']
                        }
                        all_reviews.append(review_data)
                    
                    cursor = data['cursor'] # 다음 페이지 위치 저장
                    
                    # 진행률 업데이트
                    current_progress = (i + 1) / num_requests
                    progress_bar.progress(current_progress)
                    status_text.text(f"현재 {len(all_reviews)}개 수집 중...")
                    
                    # 서버에 무리를 주지 않기 위해 0.5초 쉬기 (매너)
                    time.sleep(0.5)
                else:
                    break 
            
            progress_bar.progress(100)
            
            # 4. 결과 보여주기 및 엑셀 저장
            if all_reviews:
                df = pd.DataFrame(all_reviews)
                st.success(f"완료! 총 {len(df)}개의 리뷰를 찾았습니다.")
                st.dataframe(df) # 화면에 표 보여주기
                
                # 엑셀 다운로드 버튼 생성
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 엑셀파일 다운로드",
                    data=csv,
                    file_name=f'steam_reviews_{app_id}_{language}.csv',
                    mime='text/csv',
                )
            else:
                st.warning("수집된 리뷰가 없습니다. (게임 ID를 확인해주세요)")
                
        except Exception as e:
            st.error(f"오류가 발생했습니다: {e}")
