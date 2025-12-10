import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from datetime import datetime, time
import time as time_lib

# ==========================================
# 1. 페이지 설정
# ==========================================
st.set_page_config(page_title="Game Community Crawler", layout="wide")

# ==========================================
# 2. 크롤링 함수 정의
# ==========================================

def get_steam_reviews(app_id, num_reviews=100):
    """Steam App ID를 기반으로 리뷰를 수집합니다."""
    url = f"https://store.steampowered.com/appreviews/{app_id}"
    reviews = []
    cursor = '*'
    
    params = {
        'json': 1,
        'filter': 'updated', # 최근 수정된 순
        'language': 'english', # 필요시 'all' 또는 'koreana'로 변경 가능
        'day_range': 9223372036854775807,
        'review_type': 'all',
        'purchase_type': 'all',
        'num_per_page': 100
    }

    try:
        while len(reviews) < num_reviews:
            params['cursor'] = cursor
            response = requests.get(url, params=params)
            
            if response.status_code != 200:
                st.error(f"Steam API 오류: 상태 코드 {response.status_code}")
                break
                
            data = response.json()
            
            if 'reviews' in data and len(data['reviews']) > 0:
                for r in data['reviews']:
                    reviews.append({
                        'Author_ID': r['author']['steamid'],
                        'Playtime_Forever': r['author']['playtime_forever'],
                        'Review_Text': r['review'],
                        'Voted_Up': r['voted_up'],
                        'Votes_Up': r['votes_up'],
                        'Date_Posted': datetime.fromtimestamp(r['timestamp_created']).strftime('%Y-%m-%d')
                    })
                cursor = data['cursor']
            else:
                break
    except Exception as e:
        st.error(f"오류 발생: {e}")
            
    return pd.DataFrame(reviews[:num_reviews])

def get_steam_discussions(app_id):
    """Steam 토론장(General)의 1페이지 게시글 목록을 수집합니다."""
    discussions = []
    # 기본 토론장 URL 구조
    target_url = f"https://steamcommunity.com/app/{app_id}/discussions/"
    
    try:
        res = requests.get(target_url)
        if res.status_code != 200:
            st.error("토론장 페이지를 불러올 수 없습니다. App ID를 확인해주세요.")
            return pd.DataFrame()

        soup = BeautifulSoup(res.text, 'html.parser')
        rows = soup.find_all('div', class_='forum_topic')
        
        for row in rows:
            topic = row.find('div', class_='forum_topic_name')
            author = row.find('div', class_='forum_topic_op')
            reply_count = row.find('div', class_='forum_topic_reply_count')
            
            if topic:
                title_text = topic.get_text(strip=True)
                link = topic.find('a')['href']
                
                discussions.append({
                    "Title": title_text,
                    "Author": author.get_text(strip=True) if author else "Unknown",
                    "Replies": reply_count.get_text(strip=True) if reply_count else "0",
                    "Link": link
                })
    except Exception as e:
        st.error(f"크롤링 중 오류: {e}")
            
    return pd.DataFrame(discussions)

def get_youtube_videos(api_key, query, start, end, max_results):
    """기간 내 Youtube 영상 검색"""
    youtube = build('youtube', 'v3', developerKey=api_key)
    
    start_dt = datetime.combine(start, time.min).isoformat() + "Z"
    end_dt = datetime.combine(end, time.max).isoformat() + "Z"
    
    video_list = []
    try:
        search_response = youtube.search().list(
            q=query,
            type="video",
            part="id,snippet",
            order="viewCount",
            publishedAfter=start_dt,
            publishedBefore=end_dt,
            maxResults=max_results
        ).execute()

        for item in search_response.get("items", []):
            video_list.append({
                "video_id": item["id"]["videoId"],
                "title": item["snippet"]["title"],
                "published_at": item["snippet"]["publishedAt"],
                "channel": item["snippet"]["channelTitle"]
            })
    except Exception as e:
        st.error(f"YouTube 검색 오류 (API Key를 확인하세요): {e}")
        
    return video_list

def get_youtube_comments(api_key, video_id, max_comments):
    """영상 댓글 수집 (인기순)"""
    youtube = build('youtube', 'v3', developerKey=api_key)
    comments = []
    
    try:
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=min(max_comments, 100),
            textFormat="plainText",
            order="relevance" 
        )
        
        while request and len(comments) < max_comments:
            response = request.execute()
            for item in response['items']:
                comment_snip = item['snippet']['topLevelComment']['snippet']
                comments.append({
                    "Author": comment_snip['authorDisplayName'],
                    "Comment": comment_snip['textDisplay'],
                    "Likes": comment_snip['likeCount'],
                    "Date": comment_snip['publishedAt']
                })
            
            if 'nextPageToken' in response and len(comments) < max_comments:
                request = youtube.commentThreads().list_next(request, response)
            else:
                break
    except:
        pass
        
    return comments

# ==========================================
# 3. 사이드바 메뉴 구성
# ==========================================
st.sidebar.title("Navigation")
menu = st.sidebar.radio("데이터 소스 선택", ["Steam Reviews", "Steam Discussions", "Youtube Crawler", "Reddit (준비중)"])

st.title("통합 게임 여론 분석기")

# ==========================================
# 4. 메뉴별 메인 화면 로직
# ==========================================

# --- [1] Steam Reviews ---
if menu == "Steam Reviews":
    st.header("🟦 Steam Review Crawler")
    st.markdown("특정 게임의 **App ID**를 입력하여 리뷰를 수집합니다.")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        app_id = st.text_input("Steam App ID", value="1245620", help="상점 페이지 URL의 숫자 부분입니다. 예: Elden Ring = 1245620")
    with col2:
        num_reviews = st.slider("수집할 리뷰 수 (최신순)", 50, 2000, 100, step=50)

    if st.button("리뷰 수집 시작"):
        if not app_id.isdigit():
            st.error("App ID는 숫자여야 합니다.")
        else:
            with st.spinner(f"App ID {app_id}의 리뷰를 가져오는 중..."):
                df = get_steam_reviews(app_id, num_reviews)
                if not df.empty:
                    st.success(f"총 {len(df)}개의 리뷰 수집 완료!")
                    st.dataframe(df)
                    
                    csv = df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button("CSV 다운로드", csv, f"steam_reviews_{app_id}.csv", "text/csv")
                else:
                    st.warning("리뷰를 찾지 못했습니다. App ID를 확인해주세요.")

# --- [2] Steam Discussions ---
elif menu == "Steam Discussions":
    st.header("💬 Steam Discussion Crawler")
    st.markdown("특정 게임의 **토론장(General)** 글 목록을 수집합니다.")
    
    app_id_disc = st.text_input("Steam App ID", value="1245620", help="상점 페이지 URL의 숫자 부분입니다.")
    
    if st.button("토론장 글 목록 수집"):
        if not app_id_disc.isdigit():
            st.error("App ID는 숫자여야 합니다.")
        else:
            with st.spinner("토론장을 검색 중입니다..."):
                df_disc = get_steam_discussions(app_id_disc)
                if not df_disc.empty:
                    st.success(f"현재 페이지의 토론 글 {len(df_disc)}개를 가져왔습니다.")
                    st.dataframe(df_disc)
                    
                    # 링크 클릭 가능하게 표시
                    for index, row in df_disc.iterrows():
                        st.markdown(f"**[{row['Title']}]({row['Link']})** (댓글: {row['Replies']})")
                        
                    csv_disc = df_disc.to_csv(index=False).encode('utf-8-sig')
                    st.download_button("CSV 다운로드", csv_disc, f"steam_discussion_{app_id_disc}.csv", "text/csv")
                else:
                    st.warning("게시글을 찾지 못했습니다. App ID가 정확한지 확인해주세요.")

# --- [3] Youtube Crawler ---
elif menu == "Youtube Crawler":
    st.header("🟥 Youtube Comment Crawler")
    
    # API 키 입력 (이 탭에서만 보임)
    api_key_input = st.text_input("YouTube Data API Key", type="password")
    
    st.markdown("---")
    
    col_search, col_count = st.columns([3, 1])
    with col_search:
        yt_query = st.text_input("검색어 (게임 이름)", "League of Legends")
    with col_count:
        max_vids = st.number_input("영상 개수 제한", min_value=1, max_value=50, value=5)

    col_start, col_end = st.columns(2)
    with col_start:
        start_date = st.date_input("시작 날짜", value=datetime(2024, 1, 1))
    with col_end:
        end_date = st.date_input("종료 날짜", value=datetime.now())

    if st.button("YouTube 데이터 수집 시작"):
        if not api_key_input:
            st.error("API Key를 입력해주세요.")
        else:
            with st.status("데이터 수집 진행 중...", expanded=True) as status:
                st.write("🔍 영상을 검색합니다...")
                videos = get_youtube_videos(api_key_input, yt_query, start_date, end_date, max_vids)
                
                if not videos:
                    status.update(label="해당 기간에 검색된 영상이 없습니다.", state="error")
                else:
                    st.write(f"총 {len(videos)}개의 영상을 찾았습니다. 댓글 수집 시작 (인기순)...")
                    
                    all_yt_data = []
                    prog_bar = st.progress(0)
                    
                    for idx, video in enumerate(videos):
                        prog_bar.progress((idx + 1) / len(videos))
                        st.write(f"Collecting: {video['title'][:30]}...")
                        
                        # 영상당 댓글 최대 50개 (조절 가능)
                        comments = get_youtube_comments(api_key_input, video['video_id'], 50)
                        
                        for c in comments:
                            all_yt_data.append({
                                "Video_Title": video['title'],
                                "Video_Publish_Date": video['published_at'],
                                "Video_Channel": video['channel'],
                                "Comment_Author": c['Author'],
                                "Comment_Text": c['Comment'],
                                "Comment_Likes": c['Likes'],
                                "Comment_Date": c['Date']
                            })
                        time_lib.sleep(0.1) 
                    
                    status.update(label="수집 완료!", state="complete")
                    
                    if all_yt_data:
                        df_yt = pd.DataFrame(all_yt_data)
                        st.success(f"총 {len(df_yt)}개의 댓글 수집 완료.")
                        st.dataframe(df_yt.head())
                        
                        csv_yt = df_yt.to_csv(index=False).encode('utf-8-sig')
                        st.download_button(
                            label="CSV 다운로드",
                            data=csv_yt,
                            file_name=f"youtube_{yt_query}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.warning("댓글을 가져오지 못했습니다.")

# --- [4] Reddit (Placeholder) ---
elif menu == "Reddit (준비중)":
    st.header("🟧 Reddit Crawler")
    st.info("이 기능은 현재 개발 중입니다. (Reddit API 연동 예정)")