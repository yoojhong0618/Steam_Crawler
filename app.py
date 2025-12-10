import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from datetime import datetime, time
import time as time_lib

# ==========================================
# 1. 공통 함수 및 설정
# ==========================================
st.set_page_config(page_title="Game Community Crawler", layout="wide")
st.title("🎮 통합 게임 여론 분석기 (Steam & YouTube)")

# 사이드바: API 키 및 설정
st.sidebar.header("⚙️ 설정 (Settings)")
youtube_api_key = st.sidebar.text_input("YouTube Data API Key", type="password", help="YouTube 데이터 수집을 위해 필수입니다.")

# ==========================================
# 2. Steam 관련 함수 (리뷰 & 토론장)
# ==========================================

def get_steam_game_id(game_name):
    """게임 이름으로 Steam App ID를 검색합니다."""
    url = "https://store.steampowered.com/search/"
    params = {'term': game_name}
    try:
        response = requests.get(url, params=params)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        search_results = soup.find_all('a', class_='search_result_row')
        
        games = []
        for result in search_results:
            try:
                title = result.find('span', class_='title').text
                app_id = result['data-ds-appid']
                games.append((title, app_id))
            except:
                continue
        return games
    except Exception as e:
        return []

def get_steam_reviews(app_id, language='english', num_reviews=100):
    """특정 게임의 리뷰를 수집합니다."""
    url = f"https://store.steampowered.com/appreviews/{app_id}"
    reviews = []
    cursor = '*'
    
    params = {
        'json': 1,
        'filter': 'updated',
        'language': language,
        'day_range': 9223372036854775807,
        'review_type': 'all',
        'purchase_type': 'all',
        'num_per_page': 100
    }

    while len(reviews) < num_reviews:
        params['cursor'] = cursor
        try:
            response = requests.get(url, params=params)
            data = response.json()
            
            if 'reviews' in data and len(data['reviews']) > 0:
                for r in data['reviews']:
                    reviews.append({
                        'Author': r['author']['steamid'],
                        'Playtime_Forever': r['author']['playtime_forever'],
                        'Review_Text': r['review'],
                        'Voted_Up': r['voted_up'],
                        'Votes_Up': r['votes_up'],
                        'Date_Posted': datetime.fromtimestamp(r['timestamp_created']).strftime('%Y-%m-%d')
                    })
                cursor = data['cursor']
            else:
                break
        except:
            break
            
    return pd.DataFrame(reviews[:num_reviews])

def get_steam_discussions(app_id, max_pages=3):
    """Steam 토론장의 제목과 내용을 수집합니다 (간이 크롤링)."""
    discussions = []
    base_url = f"https://steamcommunity.com/app/{app_id}/discussions/"
    
    # 토론장 목록 페이지 순회
    for page in range(1, max_pages + 1):
        try:
            # fp 파라미터가 없으면 1페이지, 이후는 Steam 방식이 복잡하여 단순 예시로 1페이지만 크롤링하거나
            # 정확한 페이지네이션을 위해서는 Selenium이 필요할 수 있습니다. 
            # 여기서는 requests로 가장 최신/인기 토론글 목록(1페이지)을 가져옵니다.
            res = requests.get(base_url)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            rows = soup.find_all('div', class_='forum_topic')
            if not rows: break

            for row in rows:
                topic = row.find('div', class_='forum_topic_name')
                author = row.find('div', class_='forum_topic_op')
                reply_count = row.find('div', class_='forum_topic_reply_count')
                
                if topic:
                    title_text = topic.get_text(strip=True)
                    # 상세 링크
                    link = topic.find('a')['href']
                    
                    discussions.append({
                        "Title": title_text,
                        "Author": author.get_text(strip=True) if author else "Unknown",
                        "Replies": reply_count.get_text(strip=True) if reply_count else "0",
                        "Link": link
                    })
        except Exception as e:
            st.error(f"토론장 크롤링 중 오류: {e}")
            break
            
    return pd.DataFrame(discussions)

# ==========================================
# 3. YouTube 관련 함수
# ==========================================

def get_youtube_videos(api_key, query, start, end, max_results):
    """기간 내 영상 검색"""
    youtube = build('youtube', 'v3', developerKey=api_key)
    
    start_dt = datetime.combine(start, time.min).isoformat() + "Z"
    end_dt = datetime.combine(end, time.max).isoformat() + "Z"
    
    video_list = []
    try:
        search_response = youtube.search().list(
            q=query,
            type="video",
            part="id,snippet",
            order="viewCount",  # 조회수 높은 순 검색
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
        st.error(f"YouTube 검색 오류: {e}")
        
    return video_list

def get_youtube_comments(api_key, video_id, max_comments):
    """영상 댓글 수집 (인기순 정렬)"""
    youtube = build('youtube', 'v3', developerKey=api_key)
    comments = []
    
    try:
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=min(max_comments, 100),
            textFormat="plainText",
            order="relevance"  # ★ 핵심: 인기 댓글 순 정렬 ★
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
    except Exception as e:
        pass # 댓글 중지된 영상 등 예외 처리
        
    return comments

# ==========================================
# 4. 메인 UI (탭 구성)
# ==========================================

tab1, tab2, tab3 = st.tabs(["🟦 Steam Reviews", "💬 Steam Discussions", "🟥 YouTube Crawler"])

# --- Tab 1: Steam 리뷰 ---
with tab1:
    st.header("Steam 게임 리뷰 수집")
    game_name_input = st.text_input("게임 이름을 입력하세요 (예: Elden Ring)", key="steam_review_search")
    
    if game_name_input:
        games = get_steam_game_id(game_name_input)
        if games:
            game_options = {name: app_id for name, app_id in games}
            selected_game = st.selectbox("게임을 선택하세요", list(game_options.keys()), key="review_select")
            app_id = game_options[selected_game]
            
            num_reviews = st.slider("수집할 리뷰 개수", 10, 1000, 100, step=10, key="review_slider")
            
            if st.button("리뷰 수집 시작", key="btn_review"):
                with st.spinner("리뷰를 가져오는 중..."):
                    df_reviews = get_steam_reviews(app_id, num_reviews=num_reviews)
                    if not df_reviews.empty:
                        st.success(f"{len(df_reviews)}개의 리뷰를 수집했습니다!")
                        st.dataframe(df_reviews)
                        
                        csv = df_reviews.to_csv(index=False).encode('utf-8-sig')
                        st.download_button("CSV 다운로드", csv, f"steam_reviews_{app_id}.csv", "text/csv")
                    else:
                        st.warning("리뷰를 찾지 못했습니다.")
        else:
            st.warning("게임을 찾을 수 없습니다.")

# --- Tab 2: Steam 토론장 ---
with tab2:
    st.header("Steam 토론장 주제 수집")
    st.info("현재 활성화된 토론 주제 목록을 가져옵니다.")
    
    # 위와 동일한 검색 로직 사용
    game_name_input_disc = st.text_input("게임 이름을 입력하세요", key="steam_disc_search")
    
    if game_name_input_disc:
        games = get_steam_game_id(game_name_input_disc)
        if games:
            game_options = {name: app_id for name, app_id in games}
            selected_game_disc = st.selectbox("게임을 선택하세요", list(game_options.keys()), key="disc_select")
            app_id_disc = game_options[selected_game_disc]
            
            if st.button("토론장 글 목록 수집", key="btn_disc"):
                with st.spinner("토론장을 검색 중입니다..."):
                    df_disc = get_steam_discussions(app_id_disc)
                    if not df_disc.empty:
                        st.success(f"현재 페이지의 토론 글 {len(df_disc)}개를 가져왔습니다.")
                        st.dataframe(df_disc)
                        
                        # 링크 클릭 가능하게 만들기 (선택 사항)
                        for index, row in df_disc.iterrows():
                            st.markdown(f"**[{row['Title']}]({row['Link']})** - 작성자: {row['Author']} (댓글: {row['Replies']})")
                    else:
                        st.warning("토론 글을 가져오지 못했습니다.")

# --- Tab 3: YouTube ---
with tab3:
    st.header("YouTube 영상 및 인기 댓글 수집")
    
    if not youtube_api_key:
        st.warning("⚠️ 사이드바에 YouTube API Key를 먼저 입력해주세요!")
    else:
        col1, col2 = st.columns(2)
        with col1:
            yt_query = st.text_input("검색어 (게임 이름)", "League of Legends")
            start_date = st.date_input("시작 날짜", value=datetime(2024, 1, 1))
        with col2:
            max_vids = st.slider("최대 영상 개수", 5, 50, 10)
            end_date = st.date_input("종료 날짜", value=datetime.now())
            
        st.caption("※ 댓글은 '인기순(Relevance)'으로 정렬되어 수집됩니다.")

        if st.button("YouTube 데이터 수집 시작", key="btn_yt"):
            with st.status("데이터 수집 진행 중...", expanded=True) as status:
                st.write("🔍 영상을 검색합니다...")
                videos = get_youtube_videos(youtube_api_key, yt_query, start_date, end_date, max_vids)
                
                if not videos:
                    status.update(label="영상을 찾지 못했습니다.", state="error")
                else:
                    st.write(f"총 {len(videos)}개의 영상을 찾았습니다. 댓글 수집을 시작합니다.")
                    
                    all_yt_data = []
                    progress_bar = st.progress(0)
                    
                    for idx, video in enumerate(videos):
                        progress_bar.progress((idx + 1) / len(videos))
                        # 영상 정보 표시
                        st.write(f"📺 Processing: {video['title'][:30]}...")
                        
                        # 댓글 수집 (영상당 최대 50개 제한 예시)
                        comments = get_youtube_comments(youtube_api_key, video['video_id'], 50)
                        
                        for c in comments:
                            all_yt_data.append({
                                "Video_Title": video['title'],
                                "Video_Channel": video['channel'],
                                "Video_Publish_Date": video['published_at'],
                                "Comment_Author": c['Author'],
                                "Comment_Text": c['Comment'],
                                "Comment_Likes": c['Likes'],
                                "Comment_Date": c['Date']
                            })
                        time_lib.sleep(0.1) # API 부하 방지
                    
                    status.update(label="수집 완료!", state="complete")
                    
                    if all_yt_data:
                        df_yt = pd.DataFrame(all_yt_data)
                        st.success(f"총 {len(df_yt)}개의 댓글을 수집했습니다.")
                        st.dataframe(df_yt.head())
                        
                        csv_yt = df_yt.to_csv(index=False).encode('utf-8-sig')
                        st.download_button(
                            label="CSV 다운로드 (YouTube)",
                            data=csv_yt,
                            file_name=f"youtube_{yt_query}_comments.csv",
                            mime="text/csv"
                        )
                    else:
                        st.warning("수집된 댓글이 없습니다.")