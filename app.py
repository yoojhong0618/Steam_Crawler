import streamlit as st
import requests
import pandas as pd
import json
import time
from datetime import datetime, timedelta

# 페이지 설정
st.set_page_config(page_title="스팀 리뷰 수집기", layout="wide")

# --- 🔐 비밀번호 잠금 ---
# (회사용) 문구 삭제됨
password = st.text_input("🔒 접속 암호", type="password")

if password != "smilegate":
    st.warning("권한이 없습니다.")
    st.stop()
# ---------------------

# (연결 강화판) 문구 삭제됨
st.title("Steam 리뷰 수집기")

# 사이드바 설정
with st.sidebar:
    st.header("설정")
    app_id = st.text_input("App ID", value="1562700") # 산나비 ID 기본값
    
    st.divider()
    
    st.subheader("📅 기간 설정")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("시작일", datetime(2025, 2, 1)) # 2월 1일 기본값
    with col2:
        end_date = st.date_input("종료일", datetime.now())
        
    st.divider()
    
    language = st.selectbox("언어", ["all", "koreana", "english", "japanese", "schinese"], index=0)
    
    # 50만 개 설정
    MAX_LIMIT = 500000 
    
    run_btn = st.button("수집 시작", type="primary")

# 메인 로직
if run_btn:
    st.toast("탐색을 시작합니다... 🚀")
    
    all_reviews = []
    cursor = '*'
    
    # 상태 표시창
    progress_bar = st.progress(0)
    status_box = st.info(f"탐색 시작... (목표: {start_date} 까지)")
    
    try:
        num_requests = MAX_LIMIT // 100
        
        for i in range(num_requests):
            # 안전한 통신을 위한 파라미터 포장
            params = {
                'json': 1,
                'cursor': cursor,
                'language': language,
                'num_per_page': 100,
                'purchase_type': 'all',
                'filter': 'recent'
            }
            
            # 요청 보내기
            response = requests.get(f"https://store.steampowered.com/appreviews/{app_id}", params=params)
            
            if response.status_code != 200:
                st.error(f"서버 연결 실패 (코드: {response.status_code})")
                break
                
            data = response.json()
            
            if 'reviews' in data and len(data['reviews']) > 0:
                last_ts = data['reviews'][-1]['timestamp_created']
                current_date = pd.to_datetime(last_ts, unit='s').date()
                
                for review in data['reviews']:
                    r_date = pd.to_datetime(review['timestamp_created'], unit='s').date()
                    
                    review_data = {
                        '작성일': r_date,
                        '작성자ID': review['author']['steamid'],
                        '플레이시간(분)': review['author']['playtime_forever'],
                        '추천여부': '추천' if review['voted_up'] else '비추천',
                        '내용': review['review'].replace('\n', ' '),
                        '유용함_수': review['votes_up']
                    }
                    all_reviews.append(review_data)
                
                cursor = data['cursor']
                
                # 상태 업데이트
                progress_bar.progress(min((i + 1) / 100, 0.95))
                status_box.info(f"현재 **{len(all_reviews)}개** 수집 중... (현재 위치: **{current_date}**)")
                
                # 날짜 도달 체크
                if current_date < start_date:
                    progress_bar.progress(100)
                    st.success(f"목표 날짜({start_date})에 도달했습니다! ✅")
                    break
                
                time.sleep(0.25)
            else:
                st.warning("더 이상 리뷰가 없습니다. (탐색 종료)")
                break
        
        # 결과 처리
        if all_reviews:
            df = pd.DataFrame(all_reviews)
            mask = (df['작성일'] >= start_date) & (df['작성일'] <= end_date)
            filtered_df = df.loc[mask]
            
            st.divider()
            if len(filtered_df) > 0:
                st.markdown(f"### 결과: {len(filtered_df)}개 발견")
                st.dataframe(filtered_df)
                
                csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="엑셀 다운로드",
                    data=csv,
                    file_name=f'steam_{app_id}_{start_date}~{end_date}.csv',
                    mime='text/csv',
                )
            else:
                st.error("설정한 기간 내의 데이터가 없습니다.")
                st.caption(f"시스템은 {current_date}까지 확인했습니다.")
                
    except Exception as e:
        st.error(f"오류 발생: {e}")