import streamlit as st
import requests
import pandas as pd
import json
import time
from datetime import datetime, timedelta

# 페이지 설정
st.set_page_config(page_title="스팀 리뷰 크롤러", layout="wide")

# --- 🔐 비밀번호 잠금 ---
password = st.text_input("🔒 접속 암호 (회사용)", type="password")
if password != "smilegate":
    st.warning("권한이 없습니다.")
    st.stop()
# ---------------------

st.title("Steam 리뷰 수집기")

# 사이드바 설정
with st.sidebar:
    st.header("설정")
    app_id = st.text_input("App ID", value="578080")
    
    st.divider()
    
    st.subheader("📅 기간 설정")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("시작일", datetime.now() - timedelta(days=30))
    with col2:
        end_date = st.date_input("종료일", datetime.now())
        
    st.divider()
    
    language = st.selectbox("언어", ["english", "koreana", "japanese", "schinese", "all"])
    
    # 30만 개 고정 (사용자에게 노출 X)
    review_limit = 300000 
    
    st.write("")
    run_btn = st.button("수집 시작", type="primary")

# 메인 로직
if run_btn:
    st.info(f"탐색 시작: {start_date} ~ {end_date}")
    
    all_reviews = []
    cursor = '*'
    
    progress_bar = st.progress(0)
    status_text = st.empty() 
    date_monitor = st.empty()
    
    try:
        num_requests = review_limit // 100
        
        for i in range(num_requests):
            url = f"https://store.steampowered.com/appreviews/{app_id}?json=1&cursor={cursor}&language={language}&num_per_page=100&purchase_type=all&filter=recent"
            response = requests.get(url)
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
                
                # [수정됨] 꾸밈 없는 정직한 진행률 (30만 개 기준이라 바가 거의 안 움직일 수 있음)
                progress_bar.progress((i + 1) / num_requests)
                status_text.text(f"수집 중: {len(all_reviews)}개")
                
                date_monitor.info(f"현재 탐색 날짜: {current_date}")
                
                # 목표 날짜 도달 시 즉시 종료
                if current_date < start_date:
                    progress_bar.progress(100)
                    break
                
                time.sleep(0.2)
            else:
                break
        
        # 결과 처리
        if all_reviews:
            df = pd.DataFrame(all_reviews)
            mask = (df['작성일'] >= start_date) & (df['작성일'] <= end_date)
            filtered_df = df.loc[mask]
            
            st.divider()
            if len(filtered_df) > 0:
                st.write(f"결과: {len(filtered_df)}개 (전체 탐색: {len(df)}개)")
                st.dataframe(filtered_df)
                
                csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="엑셀 다운로드",
                    data=csv,
                    file_name=f'steam_{app_id}_{start_date}~{end_date}.csv',
                    mime='text/csv',
                )
            else:
                st.error("해당 기간의 데이터 없음")
                
    except Exception as e:
        st.error(f"Error: {e}")