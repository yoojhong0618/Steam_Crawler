import streamlit as st
import requests
import pandas as pd
import json
import time
from datetime import datetime, timedelta

# 페이지 기본 설정
st.set_page_config(page_title="스팀 리뷰 크롤러", layout="wide")

# --- 🔐 비밀번호 잠금 기능 ---
password = st.text_input("🔒 접속 암호를 입력하세요 (회사용)", type="password")
if password != "smilegate":
    st.warning("접속 권한이 없습니다. 비밀번호를 입력해주세요.")
    st.stop()
# ---------------------------

st.title("🎮 Steam 게임 리뷰 수집기 (날짜 지정)")
st.markdown("특정 기간의 스팀 리뷰를 수집하여 엑셀로 다운로드합니다.")

# 사이드바 설정
with st.sidebar:
    st.header("설정 (Settings)")
    app_id = st.text_input("스팀 게임 App ID", value="578080")
    
    # 날짜 선택 기능 추가 📅
    st.subheader("기간 설정")
    # 기본값: 오늘부터 30일 전까지
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("시작일", datetime.now() - timedelta(days=30))
    with col2:
        end_date = st.date_input("종료일", datetime.now())
        
    language = st.selectbox("언어 선택", ["english", "koreana", "japanese", "schinese", "all"])
    
    # 주의사항: 옛날 데이터를 보려면 개수를 늘려야 함
    st.caption("※ 과거 데이터를 보려면 수집 개수를 넉넉하게 늘려주세요.")
    review_limit = st.number_input("수집할 최대 리뷰 개수", min_value=100, max_value=10000, step=100, value=500)
    
    run_btn = st.button("데이터 수집 시작 🚀")

# 메인 로직
if run_btn:
    if not app_id:
        st.error("App ID를 입력해주세요!")
    else:
        st.info(f"App ID: {app_id} | 기간: {start_date} ~ {end_date} | 언어: {language}")
        
        all_reviews = []
        cursor = '*'
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # 1. 일단 넉넉하게 데이터 가져오기
            num_requests = review_limit // 100
            
            for i in range(num_requests):
                # filter=recent 파라미터로 최신순 정렬 보장
                url = f"https://store.steampowered.com/appreviews/{app_id}?json=1&cursor={cursor}&language={language}&num_per_page=100&purchase_type=all&filter=recent"
                response = requests.get(url)
                data = response.json()
                
                if 'reviews' in data and len(data['reviews']) > 0:
                    for review in data['reviews']:
                        # 날짜 변환
                        review_date = pd.to_datetime(review['timestamp_created'], unit='s').date()
                        
                        review_data = {
                            '작성일': review_date, # 날짜 형식으로 저장
                            '작성자ID': review['author']['steamid'],
                            '플레이시간(분)': review['author']['playtime_forever'],
                            '추천여부': '추천' if review['voted_up'] else '비추천',
                            '내용': review['review'].replace('\n', ' '),
                            '유용함_수': review['votes_up']
                        }
                        all_reviews.append(review_data)
                    
                    cursor = data['cursor']
                    
                    current_progress = (i + 1) / num_requests
                    progress_bar.progress(current_progress)
                    status_text.text(f"서버에서 {len(all_reviews)}개 글 읽어오는 중...")
                    time.sleep(0.3) 
                else:
                    break
            
            progress_bar.progress(100)
            
            # 2. 여기서 날짜로 거르기 (Filtering) 🧹
            if all_reviews:
                df = pd.DataFrame(all_reviews)
                
                # 날짜 필터링 적용
                mask = (df['작성일'] >= start_date) & (df['작성일'] <= end_date)
                filtered_df = df.loc[mask]
                
                # 결과 출력
                st.divider()
                if len(filtered_df) > 0:
                    st.success(f"✅ 설정한 기간 내의 리뷰 **{len(filtered_df)}개**를 찾았습니다! (전체 수집: {len(df)}개)")
                    st.dataframe(filtered_df)
                    
                    # 엑셀 다운로드
                    csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        label="📥 필터링된 결과 다운로드 (Excel)",
                        data=csv,
                        file_name=f'steam_{app_id}_{start_date}~{end_date}.csv',
                        mime='text/csv',
                    )
                else:
                    st.warning(f"수집된 {len(df)}개 리뷰 중에 해당 기간({start_date}~{end_date})의 글이 없습니다. 수집 개수를 더 늘려보세요!")
            else:
                st.warning("리뷰를 가져오지 못했습니다.")
                
        except Exception as e:
            st.error(f"오류가 발생했습니다: {e}")