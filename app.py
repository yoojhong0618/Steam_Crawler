import streamlit as st
import requests
import pandas as pd
import time
import random
import urllib3
from datetime import datetime, time as dt_time
from bs4 import BeautifulSoup
from googleapiclient.discovery import build

# SSL 경고 메시지 숨기기
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 페이지 기본 설정
st.set_page_config(page_title="Steam & YouTube 데이터 수집기", layout="wide")

# --- 🔐 비밀번호 잠금 (구조 유지) ---
password = st.text_input("접속 암호", type="password")
if password != "smilegate":
    st.warning("암호를 입력하세요.")
    st.stop()

st.title("Steam & YouTube 데이터 수집기")

# --- 사이드바 (구조 유지) ---
with st.sidebar:
    st.header("설정")
    menu = st.selectbox("분석 채널", ["Steam (스팀)", "YouTube (유튜브)", "Reddit (준비중)"])
    st.divider()

# =========================================================
# [SECTION 1] Steam (스팀)
# =========================================================
if menu == "Steam (스팀)":
    tab1, tab2 = st.tabs(["리뷰 수집 (API)", "토론장 수집 (크롤링)"])
    
    # [TAB 1] 리뷰 수집 (기간 설정 기능 강화됨)
    with tab1:
        st.subheader("리뷰 데이터 수집")
        col1, col2 = st.columns(2)
        with col1:
            app_id_review = st.text_input("App ID (리뷰용)", value="1562700")
        with col2:
            language = st.selectbox("언어", ["all", "koreana", "english", "japanese", "schinese"], index=0)
        
        # --- [변경] 시작일/종료일 기간 설정 추가 ---
        col_start, col_end = st.columns(2)
        with col_start:
            start_date = st.date_input("수집 시작 날짜", datetime(2024, 1, 1))
        with col_end:
            end_date = st.date_input("수집 종료 날짜", datetime.now())
        
        if st.button("리뷰 수집 시작", key="btn_review"):
            all_reviews = []
            cursor = '*'
            status_box = st.info(f"데이터 수집 중... (목표 기간: {start_date} ~ {end_date})")
            
            try:
                # 안전 장치: 최대 200페이지 (약 2만개)
                for i in range(200): 
                    params = {
                        'json': 1, 'cursor': cursor, 'language': language,
                        'num_per_page': 100, 'purchase_type': 'all', 'filter': 'recent' # 최신순 정렬
                    }
                    res = requests.get(f"https://store.steampowered.com/appreviews/{app_id_review}", params=params, verify=False)
                    data = res.json()
                    
                    if 'reviews' in data and len(data['reviews']) > 0:
                        # 현재 페이지의 마지막 리뷰 날짜 확인
                        last_ts = data['reviews'][-1]['timestamp_created']
                        curr_date = pd.to_datetime(last_ts, unit='s').date()
                        
                        for r in data['reviews']:
                            r_date = pd.to_datetime(r['timestamp_created'], unit='s').date()
                            
                            # [로직] 종료 날짜보다 더 최신 글이면? -> 수집 안 하고 패스 (Continue)
                            if r_date > end_date:
                                continue
                            
                            # [로직] 시작 날짜보다 더 과거 글이면? -> 수집 중단 (Break)
                            if r_date < start_date:
                                # 여기서 바로 break하면 이중 루프 탈출이 안 되므로 플래그 사용하거나 예외 처리 필요
                                # 간단히 여기선 빈 리스트에 더미 추가해서 바깥에서 체크하도록 함
                                pass 
                            
                            # 기간 내의 글이면 수집
                            if start_date <= r_date <= end_date:
                                all_reviews.append({
                                    '작성일': r_date, 
                                    '내용': r['review'].replace('\n', ' '), 
                                    '추천수': r['votes_up'],
                                    '플레이시간(분)': r['author'].get('playtime_forever', 0)
                                })
                        
                        cursor = data['cursor']
                        status_box.info(f"현재 {len(all_reviews)}개 수집됨... (현재 탐색 위치: {curr_date})")
                        
                        # 탐색 위치가 시작 날짜보다 과거로 넘어가면 전체 반복 종료
                        if curr_date < start_date: 
                            break
                    else: 
                        break
                
                if all_reviews:
                    df = pd.DataFrame(all_reviews)
                    # 혹시 모를 중복이나 경계값 정렬
                    df = df.sort_values(by='작성일', ascending=False)
                    
                    st.success(f"완료! {start_date} ~ {end_date} 기간의 리뷰 {len(df)}개를 수집했습니다.")
                    st.dataframe(df)
                    st.download_button("엑셀 다운로드", df.to_csv(index=False).encode('utf-8-sig'), "steam_reviews.csv")
                else:
                    st.warning("해당 기간에 작성된 리뷰가 없습니다.")
            except Exception as e:
                st.error(f"오류 발생: {e}")

    # [TAB 2] 토론장 수집 (구조 유지)
    with tab2:
        st.subheader("토론장 상세 수집 (본문+댓글)")
        st.caption("※ 토론장은 웹 크롤링 방식이라 '페이지 수'로만 범위를 지정합니다.")
        
        target_url = st.text_input("수집할 토론장 URL", value="https://steamcommunity.com/app/1562700/discussions/")
        pages_to_crawl = st.number_input("탐색할 페이지 수", min_value=1, max_value=20, value=2)
        
        if st.button("토론글 수집 시작", key="btn_discuss"):
            discussion_data = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
            }
            cookies = {'wants_mature_content': '1', 'birthtime': '660000001', 'lastagecheckage': '1-January-1990'}
            
            try:
                if not target_url.endswith('/') and '?' not in target_url: target_url += '/'

                for p in range(pages_to_crawl):
                    full_url = f"{target_url}?fp={p+1}"
                    status_text.text(f"{p+1}페이지 목록을 읽고 있습니다...")
                    time.sleep(random.uniform(1.0, 2.0))
                    res = requests.get(full_url, headers=headers, cookies=cookies, verify=False, timeout=15)
                    soup = BeautifulSoup(res.text, 'html.parser')
                    topic_rows = soup.find_all('div', class_='forum_topic')
                    
                    if not topic_rows:
                        st.warning(f"{p+1}페이지에서 글 목록을 찾지 못했습니다.")
                        break
                    
                    status_text.text(f"{p+1}페이지: {len(topic_rows)}개 글 발견. 상세 내용을 수집합니다...")
                    
                    for idx, row in enumerate(topic_rows):
                        try:
                            link_tag = row.find('a', class_='forum_topic_overlay')
                            title_tag = row.find('div', class_='forum_topic_name')
                            if not link_tag: continue
                            link = link_tag['href']
                            title = title_tag.text.strip() if title_tag else "제목 없음"
                            
                            time.sleep(random.uniform(0.5, 1.0))
                            sub_res = requests.get(link, headers=headers, cookies=cookies, verify=False)
                            sub_soup = BeautifulSoup(sub_res.text, 'html.parser')
                            
                            op_div = sub_soup.find('div', class_='forum_op')
                            if op_div:
                                author = op_div.find('a', class_='forum_op_author').text.strip()
                                content = op_div.find('div', class_='content').text.strip()
                                discussion_data.append({'구분': '게시글', '제목': title, '작성자': author, '내용': content, '링크': link})
                            
                            comments = sub_soup.find_all('div', class_='commentthread_comment')
                            for comm in comments:
                                c_text = comm.find('div', class_='commentthread_comment_text').text.strip()
                                c_author = comm.find('a', class_='commentthread_author_link').text.strip()
                                if c_text:
                                    discussion_data.append({'구분': '댓글', '제목': f"(Re) {title}", '작성자': c_author, '내용': c_text, '링크': link})
                        except: continue
                        progress_bar.progress(min((p / pages_to_crawl) + ((idx + 1) / len(topic_rows) / pages_to_crawl), 0.99))

                progress_bar.progress(1.0)
                if discussion_data:
                    df = pd.DataFrame(discussion_data)
                    st.success(f"수집 완료! 총 {len(df)}개의 데이터")
                    st.dataframe(df)
                    st.download_button("엑셀 다운로드", df.to_csv(index=False).encode('utf-8-sig'), "steam_discussion_final.csv")
                else: st.error("수집된 데이터가 없습니다.")
            except Exception as e: st.error(f"오류 발생: {e}")

# =========================================================
# [SECTION 2] YouTube (유튜브) - 기존 코드 유지
# =========================================================
elif menu == "YouTube (유튜브)":
    st.subheader("🟥 YouTube 영상 및 댓글 수집")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        yt_api_key = st.text_input("YouTube Data API Key", type="password")
    with col2:
        max_videos = st.number_input("검색할 영상 수", min_value=1, max_value=50, value=10)

    search_keyword = st.text_input("검색어 (게임명)", value="Elden Ring")
    
    col_start, col_end, col_view = st.columns([1, 1, 1])
    with col_start:
        start_date_yt = st.date_input("시작 날짜", datetime(2024, 1, 1))
    with col_end:
        end_date_yt = st.date_input("종료 날짜", datetime.now())
    with col_view:
        min_view_count = st.number_input("최소 조회수 제한", min_value=0, value=10000, step=1000)

    st.markdown("---")

    if st.button("YouTube 데이터 수집 시작", key="btn_yt"):
        if not yt_api_key:
            st.error("YouTube API Key를 입력해주세요.")
        else:
            status_box = st.status("데이터 수집을 시작합니다...", expanded=True)
            youtube_data = []
            
            try:
                youtube = build('youtube', 'v3', developerKey=yt_api_key)
                
                start_dt = datetime.combine(start_date_yt, dt_time.min).isoformat() + "Z"
                end_dt = datetime.combine(end_date_yt, dt_time.max).isoformat() + "Z"
                
                status_box.write("🔍 조건에 맞는 영상을 검색 중입니다...")
                search_response = youtube.search().list(
                    q=search_keyword,
                    type='video',
                    part='id',
                    order='viewCount',
                    publishedAfter=start_dt,
                    publishedBefore=end_dt,
                    maxResults=max_videos
                ).execute()
                
                video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
                
                if not video_ids:
                    status_box.update(label="검색된 영상이 없습니다.", state="error")
                else:
                    status_box.write(f"📊 검색된 {len(video_ids)}개 영상의 조회수를 확인 중...")
                    
                    stats_response = youtube.videos().list(
                        part='snippet,statistics',
                        id=','.join(video_ids)
                    ).execute()
                    
                    target_videos = []
                    for v_item in stats_response.get('items', []):
                        views = int(v_item['statistics'].get('viewCount', 0))
                        if views >= min_view_count:
                            target_videos.append(v_item)
                    
                    if not target_videos:
                        status_box.update(label=f"조회수 {min_view_count}회 이상인 영상이 없습니다.", state="error")
                    else:
                        status_box.write(f"✅ 조회수 조건을 만족하는 {len(target_videos)}개 영상에서 댓글을 수집합니다.")
                        
                        prog_bar = st.progress(0)
                        
                        for idx, video in enumerate(target_videos):
                            vid = video['id']
                            v_title = video['snippet']['title']
                            v_channel = video['snippet']['channelTitle']
                            v_date = video['snippet']['publishedAt'][:10]
                            v_views = video['statistics'].get('viewCount', 0)
                            
                            status_box.write(f"Collecting: {v_title[:30]} (조회수: {v_views})...")
                            
                            try:
                                comment_request = youtube.commentThreads().list(
                                    part="snippet",
                                    videoId=vid,
                                    maxResults=50,
                                    textFormat="plainText",
                                    order="relevance"
                                )
                                comment_response = comment_request.execute()
                                
                                for item in comment_response.get('items', []):
                                    c_snip = item['snippet']['topLevelComment']['snippet']
                                    youtube_data.append({
                                        '영상제목': v_title,
                                        '조회수': v_views,
                                        '채널명': v_channel,
                                        '영상게시일': v_date,
                                        '작성자': c_snip['authorDisplayName'],
                                        '댓글내용': c_snip['textDisplay'],
                                        '좋아요': c_snip['likeCount'],
                                        '댓글작성일': c_snip['publishedAt'][:10]
                                    })
                            except: pass
                            
                            prog_bar.progress((idx + 1) / len(target_videos))
                            time.sleep(0.1)
                        
                        status_box.update(label="작업 완료!", state="complete")
                        
                        if youtube_data:
                            df_yt = pd.DataFrame(youtube_data)
                            st.success(f"총 {len(df_yt)}개의 댓글을 수집했습니다.")
                            st.dataframe(df_yt)
                            st.download_button("YouTube 결과 다운로드", df_yt.to_csv(index=False).encode('utf-8-sig'), f"youtube_{search_keyword}.csv", "text/csv")
                        else:
                            st.warning("수집 가능한 댓글이 없습니다.")

            except Exception as e:
                status_box.update(label="에러 발생", state="error")
                st.error(f"오류 내용: {e}")

# =========================================================
# [SECTION 3] Reddit (준비중)
# =========================================================
elif menu == "Reddit (준비중)":
    st.info("Reddit 크롤러는 추후 업데이트 예정입니다.")