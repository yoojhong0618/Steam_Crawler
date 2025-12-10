import streamlit as st
from googleapiclient.discovery import build
import pandas as pd
from datetime import datetime, time
import time as time_lib

# --- 설정 및 제목 ---
st.title("🎮 YouTube Game Comment Crawler")
st.markdown("""
특정 게임과 관련된 유튜브 영상을 검색하고, 기간을 설정하여 댓글을 수집합니다.
대량의 데이터 수집 시 **기간을 짧게(예: 1주 단위) 나누어** 진행하는 것을 권장합니다.
""")

# --- 사이드바: 설정 입력 ---
st.sidebar.header("설정 (Settings)")
api_key = st.sidebar.text_input("YouTube Data API Key", type="password")
game_name = st.sidebar.text_input("게임 이름 (검색어)", "Elden Ring")

# 날짜 선택 (기간 분할 수집의 핵심)
st.sidebar.subheader("수집 기간 설정")
start_date = st.sidebar.date_input("시작 날짜", value=datetime(2024, 1, 1))
end_date = st.sidebar.date_input("종료 날짜", value=datetime.now())

# 수집 제한 설정
max_videos = st.sidebar.slider("수집할 최대 영상 개수", 10, 50, 20)
max_comments_per_video = st.sidebar.slider("영상 당 최대 댓글 수", 10, 100, 50)

# --- 함수 정의 ---

def get_youtube_videos(api_key, query, start, end, max_results):
    """지정된 기간 내의 영상을 검색합니다."""
    youtube = build('youtube', 'v3', developerKey=api_key)
    
    # API에 맞는 날짜 형식 변환 (RFC 3339)
    # 시작일 00:00:00, 종료일 23:59:59로 설정
    start_dt = datetime.combine(start, time.min).isoformat() + "Z"
    end_dt = datetime.combine(end, time.max).isoformat() + "Z"
    
    video_list = []
    
    try:
        search_response = youtube.search().list(
            q=query,
            type="video",
            part="id,snippet",
            order="viewCount",  # 조회수 순으로 가져오기 (관련성 순: relevance)
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
        st.error(f"영상 검색 중 오류 발생: {e}")
        
    return video_list

def get_video_comments(youtube, video_id, max_comments):
    """특정 영상의 댓글을 수집합니다."""
    comments = []
    
    try:
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=min(max_comments, 100), # API 1회 최대 호출 100
            textFormat="plainText"
        )
        
        while request and len(comments) < max_comments:
            response = request.execute()
            
            for item in response['items']:
                comment_snip = item['snippet']['topLevelComment']['snippet']
                comments.append({
                    "author": comment_snip['authorDisplayName'],
                    "text": comment_snip['textDisplay'],
                    "like_count": comment_snip['likeCount'],
                    "published_at": comment_snip['publishedAt']
                })
                
            # 페이지네이션 (더 많은 댓글이 필요할 경우)
            if 'nextPageToken' in response and len(comments) < max_comments:
                request = youtube.commentThreads().list_next(request, response)
            else:
                break
                
    except Exception as e:
        # 댓글이 중지된 영상이거나 권한 문제일 경우 무시하고 진행
        pass
        
    return comments

# --- 메인 로직 ---

if st.button("데이터 수집 시작 (Start Crawling)"):
    if not api_key:
        st.warning("먼저 사이드바에 YouTube API Key를 입력해주세요.")
    else:
        # 1. 영상 검색 단계
        with st.status("영상을 검색하는 중입니다...", expanded=True) as status:
            st.write(f"📅 기간: {start_date} ~ {end_date}")
            st.write(f"🔍 검색어: {game_name}")
            
            videos = get_youtube_videos(api_key, game_name, start_date, end_date, max_videos)
            
            if not videos:
                status.update(label="해당 기간에 검색된 영상이 없습니다.", state="error")
            else:
                status.update(label=f"총 {len(videos)}개의 영상을 찾았습니다. 댓글 수집을 시작합니다!", state="running")
                
                # 2. 댓글 수집 단계
                all_data = []
                youtube = build('youtube', 'v3', developerKey=api_key)
                
                progress_bar = st.progress(0)
                
                for idx, video in enumerate(videos):
                    # 진행률 업데이트
                    progress = (idx + 1) / len(videos)
                    progress_bar.progress(progress)
                    
                    st.write(f"Collecting: {video['title'][:30]}...")
                    
                    comments = get_video_comments(youtube, video['video_id'], max_comments_per_video)
                    
                    # 수집된 댓글과 영상 정보를 결합
                    for c in comments:
                        row = {
                            "Game_Name": game_name,
                            "Video_ID": video['video_id'],
                            "Video_Title": video['title'],
                            "Video_Published": video['published_at'],
                            "Video_Channel": video['channel'],
                            "Comment_Author": c['author'],
                            "Comment_Text": c['text'],
                            "Comment_Likes": c['like_count'],
                            "Comment_Date": c['published_at']
                        }
                        all_data.append(row)
                    
                    # API 호출 간격을 조금 두어 과부하 방지 (선택사항)
                    time_lib.sleep(0.1)

                status.update(label="모든 작업이 완료되었습니다!", state="complete")
                
                # 3. 결과 출력 및 다운로드
                if all_data:
                    df = pd.DataFrame(all_data)
                    st.success(f"총 {len(df)}개의 댓글 데이터를 수집했습니다.")
                    
                    st.dataframe(df.head())
                    
                    # CSV 다운로드 버튼
                    csv = df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        label="CSV로 다운로드",
                        data=csv,
                        file_name=f"youtube_comments_{game_name}_{start_date}_{end_date}.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning("영상을 찾았으나 수집 가능한 댓글이 없습니다.")