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

# --- 🔐 비밀번호 잠금 ---
password = st.text_input("접속 암호", type="password")
if password != "smilegate":
    st.warning("암호를 입력하세요.")
    st.stop()

st.title("Steam & YouTube 데이터 수집기")

# --- 사이드바 ---
with st.sidebar:
    st.header("설정")
    menu = st.selectbox("분석 채널", ["Steam (스팀)", "YouTube (유튜브)", "4chan (해외 포럼)", "디시인사이드"])
    st.divider()

# =========================================================
# [SECTION 1] Steam (스팀) - 기존 코드 유지
# =========================================================
if menu == "Steam (스팀)":
    tab1, tab2 = st.tabs(["리뷰 수집 (API)", "토론장 수집 (크롤링)"])
    
    # [TAB 1] 리뷰 수집
    with tab1:
        st.subheader("리뷰 데이터 수집")
        col1, col2 = st.columns(2)
        with col1:
            app_id_review = st.text_input("App ID (리뷰용)", value="1562700")
        with col2:
            language = st.selectbox("언어", ["all", "koreana", "english", "japanese", "schinese"], index=0)
        
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
                for i in range(200): 
                    params = {
                        'json': 1, 'cursor': cursor, 'language': language,
                        'num_per_page': 100, 'purchase_type': 'all', 'filter': 'recent'
                    }
                    res = requests.get(f"https://store.steampowered.com/appreviews/{app_id_review}", params=params, verify=False)
                    data = res.json()
                    
                    if 'reviews' in data and len(data['reviews']) > 0:
                        last_ts = data['reviews'][-1]['timestamp_created']
                        curr_date = pd.to_datetime(last_ts, unit='s').date()
                        
                        for r in data['reviews']:
                            r_date = pd.to_datetime(r['timestamp_created'], unit='s').date()
                            if r_date > end_date: continue
                            if r_date < start_date: pass 
                            
                            if start_date <= r_date <= end_date:
                                all_reviews.append({
                                    '작성일': r_date, 
                                    '내용': r['review'].replace('\n', ' '), 
                                    '추천수': r['votes_up'],
                                    '플레이시간(분)': r['author'].get('playtime_forever', 0)
                                })
                        
                        cursor = data['cursor']
                        status_box.info(f"현재 {len(all_reviews)}개 수집됨... (현재 탐색 위치: {curr_date})")
                        
                        if curr_date < start_date: break
                    else: break
                
                if all_reviews:
                    df = pd.DataFrame(all_reviews)
                    df = df.sort_values(by='작성일', ascending=False)
                    st.success(f"완료! {start_date} ~ {end_date} 기간의 리뷰 {len(df)}개를 수집했습니다.")
                    st.dataframe(df)
                    st.download_button("엑셀 다운로드", df.to_csv(index=False).encode('utf-8-sig'), "steam_reviews.csv")
                else:
                    st.warning("해당 기간에 작성된 리뷰가 없습니다.")
            except Exception as e:
                st.error(f"오류 발생: {e}")

    # [TAB 2] 토론장 수집
    with tab2:
        st.subheader("토론장 상세 수집 (본문+댓글)")
        st.caption("※ 토론장은 웹 크롤링 방식이라 '페이지 수'로만 범위를 지정합니다.")
        target_url = st.text_input("수집할 토론장 URL", value="https://steamcommunity.com/app/1562700/discussions/")
        pages_to_crawl = st.number_input("탐색할 페이지 수", min_value=1, max_value=20, value=2)
        
        if st.button("토론글 수집 시작", key="btn_discuss"):
            discussion_data = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            headers = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'ko-KR'}
            cookies = {'wants_mature_content': '1', 'birthtime': '660000001', 'lastagecheckage': '1-January-1990'}
            
            try:
                if not target_url.endswith('/') and '?' not in target_url: target_url += '/'
                for p in range(pages_to_crawl):
                    full_url = f"{target_url}?fp={p+1}"
                    status_text.text(f"{p+1}페이지 수집 중...")
                    time.sleep(1)
                    res = requests.get(full_url, headers=headers, cookies=cookies, verify=False)
                    soup = BeautifulSoup(res.text, 'html.parser')
                    topic_rows = soup.find_all('div', class_='forum_topic')
                    
                    if not topic_rows: break
                    
                    for idx, row in enumerate(topic_rows):
                        try:
                            link_tag = row.find('a', class_='forum_topic_overlay')
                            title_tag = row.find('div', class_='forum_topic_name')
                            if not link_tag: continue
                            link = link_tag['href']
                            title = title_tag.text.strip() if title_tag else "제목 없음"
                            
                            time.sleep(0.5)
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
                    st.success(f"수집 완료! 총 {len(df)}개")
                    st.dataframe(df)
                    st.download_button("엑셀 다운로드", df.to_csv(index=False).encode('utf-8-sig'), "steam_discussion.csv")
                else: st.error("데이터 없음")
            except Exception as e: st.error(f"오류: {e}")

# =========================================================
# [SECTION 2] YouTube (유튜브) - [구조 변경됨]
# =========================================================
elif menu == "YouTube (유튜브)":
    st.subheader("🟥 YouTube 데이터 수집기")
    
    # API 키는 두 탭에서 공통으로 쓰므로 맨 위로 뺌
    yt_api_key = st.text_input("YouTube Data API Key", type="password")

    # 탭 분리: 키워드 검색 vs 개별 링크
    tab_yt1, tab_yt2 = st.tabs(["🔍 키워드 검색 (다수 영상)", "🔗 개별 영상 링크 (1개)"])

    # [TAB 1] 기존 기능: 키워드 검색
    with tab_yt1:
        st.caption("특정 키워드(게임명 등)를 검색하여, 조회수가 높은 영상들의 댓글을 한꺼번에 수집합니다.")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            search_keyword = st.text_input("검색어 (예: Elden Ring Review)", value="Elden Ring")
        with col2:
            max_videos = st.number_input("분석할 영상 수", min_value=1, max_value=50, value=10)
        
        col_start, col_end, col_view = st.columns([1, 1, 1])
        with col_start:
            start_date_yt = st.date_input("영상 게시 시작일", datetime(2024, 1, 1))
        with col_end:
            end_date_yt = st.date_input("영상 게시 종료일", datetime.now())
        with col_view:
            min_view_count = st.number_input("최소 조회수 컷", min_value=0, value=10000, step=1000)

        if st.button("키워드 검색 및 수집 시작", key="btn_yt_keyword"):
            if not yt_api_key:
                st.error("맨 위에 YouTube API Key를 먼저 입력해주세요.")
            else:
                status_box = st.status("데이터 수집을 시작합니다...", expanded=True)
                youtube_data = []
                
                try:
                    youtube = build('youtube', 'v3', developerKey=yt_api_key)
                    start_dt = datetime.combine(start_date_yt, dt_time.min).isoformat() + "Z"
                    end_dt = datetime.combine(end_date_yt, dt_time.max).isoformat() + "Z"
                    
                    # 1. 영상 검색
                    search_response = youtube.search().list(
                        q=search_keyword, type='video', part='id', order='viewCount',
                        publishedAfter=start_dt, publishedBefore=end_dt, maxResults=max_videos
                    ).execute()
                    
                    video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
                    
                    if not video_ids:
                        status_box.update(label="검색된 영상이 없습니다.", state="error")
                    else:
                        # 2. 조회수 필터링
                        stats_response = youtube.videos().list(
                            part='snippet,statistics', id=','.join(video_ids)
                        ).execute()
                        
                        target_videos = []
                        for v_item in stats_response.get('items', []):
                            views = int(v_item['statistics'].get('viewCount', 0))
                            if views >= min_view_count:
                                target_videos.append(v_item)
                        
                        if not target_videos:
                            status_box.update(label="조회수 조건을 만족하는 영상이 없습니다.", state="error")
                        else:
                            # 3. 댓글 수집
                            prog_bar = st.progress(0)
                            for idx, video in enumerate(target_videos):
                                vid = video['id']
                                v_title = video['snippet']['title']
                                v_channel = video['snippet']['channelTitle']
                                v_date = video['snippet']['publishedAt'][:10]
                                v_views = video['statistics'].get('viewCount', 0)
                                
                                status_box.write(f"Collecting: {v_title[:30]}...")
                                
                                try:
                                    # 댓글 가져오기 (최대 50개)
                                    comment_request = youtube.commentThreads().list(
                                        part="snippet", videoId=vid, maxResults=50, textFormat="plainText", order="relevance"
                                    )
                                    comment_response = comment_request.execute()
                                    
                                    for item in comment_response.get('items', []):
                                        c_snip = item['snippet']['topLevelComment']['snippet']
                                        youtube_data.append({
                                            '영상제목': v_title, '조회수': v_views, '채널명': v_channel, '영상게시일': v_date,
                                            '작성자': c_snip['authorDisplayName'], '댓글내용': c_snip['textDisplay'],
                                            '좋아요': c_snip['likeCount'], '댓글작성일': c_snip['publishedAt'][:10]
                                        })
                                except: pass
                                prog_bar.progress((idx + 1) / len(target_videos))
                            
                            status_box.update(label="완료!", state="complete")
                            
                            if youtube_data:
                                df_yt = pd.DataFrame(youtube_data)
                                st.dataframe(df_yt)
                                st.download_button("결과 다운로드", df_yt.to_csv(index=False).encode('utf-8-sig'), f"yt_keyword_{search_keyword}.csv")
                            else: st.warning("댓글을 찾을 수 없습니다.")
                except Exception as e:
                    status_box.update(label="에러 발생", state="error")
                    st.error(f"오류: {e}")

    # [TAB 2] 신규 기능: 개별 영상 링크
    with tab_yt2:
        st.caption("특정 YouTube 영상의 주소(URL)를 입력하면, 해당 영상의 댓글을 집중적으로 수집합니다.")
        
        target_url = st.text_input("YouTube 영상 주소 (URL)", placeholder="예: https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        max_comments_single = st.number_input("수집할 댓글 수 (최대)", min_value=10, max_value=500, value=100, step=10)

        if st.button("단일 영상 댓글 수집", key="btn_yt_link"):
            if not yt_api_key:
                st.error("맨 위에 YouTube API Key를 입력해주세요.")
            elif not target_url:
                st.error("영상 주소를 입력해주세요.")
            else:
                # URL에서 Video ID 추출 로직
                video_id = None
                if "v=" in target_url:
                    video_id = target_url.split("v=")[1].split("&")[0]
                elif "youtu.be" in target_url:
                    video_id = target_url.split("/")[-1].split("?")[0]
                
                if not video_id:
                    st.error("올바른 YouTube URL이 아닙니다.")
                else:
                    status_box = st.status(f"영상 ID: {video_id} 분석 중...", expanded=True)
                    single_yt_data = []
                    
                    try:
                        youtube = build('youtube', 'v3', developerKey=yt_api_key)
                        
                        # 1. 영상 정보 가져오기
                        video_response = youtube.videos().list(
                            part='snippet,statistics', id=video_id
                        ).execute()
                        
                        if not video_response.get('items'):
                            status_box.update(label="영상을 찾을 수 없습니다.", state="error")
                        else:
                            v_info = video_response['items'][0]
                            v_title = v_info['snippet']['title']
                            v_channel = v_info['snippet']['channelTitle']
                            v_views = v_info['statistics'].get('viewCount', 0)
                            v_date = v_info['snippet']['publishedAt'][:10]
                            
                            status_box.write(f"📺 영상 발견: {v_title}")
                            status_box.write(f"👀 조회수: {v_views} | 📅 게시일: {v_date}")
                            
                            # 2. 댓글 수집 (Paging 처리로 많이 가져오기)
                            comments_collected = 0
                            next_page_token = None
                            
                            while comments_collected < max_comments_single:
                                request = youtube.commentThreads().list(
                                    part="snippet", videoId=video_id, maxResults=100, 
                                    textFormat="plainText", pageToken=next_page_token, order="relevance"
                                )
                                response = request.execute()
                                
                                for item in response.get('items', []):
                                    c_snip = item['snippet']['topLevelComment']['snippet']
                                    single_yt_data.append({
                                        '영상제목': v_title, '작성자': c_snip['authorDisplayName'],
                                        '댓글내용': c_snip['textDisplay'], '좋아요': c_snip['likeCount'],
                                        '작성일': c_snip['publishedAt'][:10]
                                    })
                                    comments_collected += 1
                                    
                                next_page_token = response.get('nextPageToken')
                                if not next_page_token or comments_collected >= max_comments_single:
                                    break
                            
                            status_box.update(label="수집 완료!", state="complete")
                            
                            if single_yt_data:
                                df_single = pd.DataFrame(single_yt_data)
                                st.success(f"총 {len(df_single)}개의 댓글을 가져왔습니다.")
                                st.dataframe(df_single)
                                st.download_button("결과 다운로드", df_single.to_csv(index=False).encode('utf-8-sig'), f"yt_single_{video_id}.csv")
                            else:
                                st.warning("댓글이 없거나 댓글이 중지된 영상입니다.")
                                
                    except Exception as e:
                        status_box.update(label="에러 발생", state="error")
                        st.error(f"오류 내용: {e}")

# =========================================================
# [SECTION 3] 4chan (포챈) - 해외 코어 게이머 반응
# =========================================================
elif menu == "4chan (해외 포럼)": 
    st.subheader("🍀 4chan (/v/ - Video Games) 실시간 반응")
    st.caption("API Key 없이 해외 하드코어 게이머들의 '날것' 반응을 수집합니다.")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        # 4chan은 검색 API가 따로 없어서, 전체 카탈로그를 가져와서 필터링해야 합니다.
        search_keyword = st.text_input("검색어 (영어, 예: Elden Ring)", value="Elden Ring")
    with col2:
        result_limit = st.number_input("가져올 스레드 수", min_value=1, max_value=20, value=3)

    st.info("※ 참고: 4chan은 익명 사이트 특성상 거친 표현이나 비속어가 포함될 수 있습니다.")

    if st.button("4chan 데이터 수집 시작", key="btn_4chan"):
        status_box = st.status("4chan /v/ 게시판을 스캔 중입니다...", expanded=True)
        fourchan_data = []
        
        try:
            # 1. /v/ (Video Games) 게시판의 전체 목록(Catalog) 가져오기
            # 공식 JSON API (인증 불필요)
            catalog_url = "https://a.4cdn.org/v/catalog.json"
            res = requests.get(catalog_url, verify=False)
            
            if res.status_code == 200:
                pages = res.json()
                found_threads = []
                
                # 2. 키워드가 포함된 스레드 찾기 (제목 or 본문 검색)
                status_box.write(f"🔍 현재 활성화된 모든 스레드에서 '{search_keyword}' 검색 중...")
                
                for page in pages:
                    for thread in page.get('threads', []):
                        # 제목(sub)이 없으면 빈 문자열, 내용(com)이 없으면 빈 문자열 처리
                        title = thread.get('sub', '') 
                        comment = thread.get('com', '')
                        
                        # 대소문자 무시하고 검색
                        if search_keyword.lower() in title.lower() or search_keyword.lower() in comment.lower():
                            found_threads.append(thread['no']) # 스레드 번호 저장
                            if len(found_threads) >= result_limit:
                                break
                    if len(found_threads) >= result_limit:
                        break
                
                if not found_threads:
                    status_box.update(label="검색 결과가 없습니다. (현재 활성화된 스레드가 없음)", state="error")
                else:
                    status_box.write(f"✅ {len(found_threads)}개의 관련 스레드 발견! 상세 내용을 긁어옵니다...")
                    
                    # 3. 각 스레드의 댓글 상세 수집
                    progress_bar = st.progress(0)
                    
                    for idx, thread_id in enumerate(found_threads):
                        thread_url = f"https://a.4cdn.org/v/thread/{thread_id}.json"
                        t_res = requests.get(thread_url, verify=False)
                        
                        if t_res.status_code == 200:
                            posts = t_res.json().get('posts', [])
                            
                            # 첫 번째 글(OP) 정보
                            op_post = posts[0]
                            op_title = op_post.get('sub', 'No Title')
                            # HTML 태그 제거 및 텍스트만 추출
                            op_content = BeautifulSoup(op_post.get('com', ''), "html.parser").get_text()
                            
                            # 원글 저장
                            fourchan_data.append({
                                '구분': '원글(Thread)',
                                '글번호': thread_id,
                                '제목/요약': op_title,
                                '작성일': datetime.fromtimestamp(op_post['time']).strftime('%Y-%m-%d %H:%M'),
                                '내용': op_content,
                                '이미지': f"https://i.4cdn.org/v/{op_post['tim']}{op_post['ext']}" if 'tim' in op_post else None
                            })
                            
                            # 댓글들(Replies) 저장
                            for reply in posts[1:]:
                                reply_content = BeautifulSoup(reply.get('com', ''), "html.parser").get_text()
                                fourchan_data.append({
                                    '구분': '댓글(Reply)',
                                    '글번호': thread_id,
                                    '제목/요약': '-', 
                                    '작성일': datetime.fromtimestamp(reply['time']).strftime('%Y-%m-%d %H:%M'),
                                    '내용': reply_content,
                                    '이미지': None
                                })
                        
                        time.sleep(0.5) # 서버 부하 방지용 딜레이
                        progress_bar.progress((idx + 1) / len(found_threads))
                    
                    status_box.update(label="수집 완료!", state="complete")
                    
                    if fourchan_data:
                        df_4chan = pd.DataFrame(fourchan_data)
                        st.success(f"총 {len(df_4chan)}개의 반응을 수집했습니다.")
                        st.dataframe(df_4chan)
                        st.download_button("엑셀 다운로드", df_4chan.to_csv(index=False).encode('utf-8-sig'), f"4chan_{search_keyword}.csv")
            else:
                st.error("4chan 서버 접속에 실패했습니다.")
                
        except Exception as e:
            st.error(f"오류 발생: {e}")

# =========================================================
# [SECTION 4] DC Inside (디시인사이드) - 한국 코어 커뮤니티
# =========================================================
elif menu == "디시인사이드":
    st.subheader("🔵 DC Inside 갤러리 수집")
    st.caption("국내 최대 커뮤니티의 특정 갤러리 반응을 수집합니다. (검색어 포함)")

    # 1. 설정 입력 (2단 컬럼)
    col1, col2 = st.columns(2)
    with col1:
        # 갤러리 ID는 URL에서 ?id= 뒤에 오는 값입니다.
        gallery_id = st.text_input("갤러리 ID (예: indiegame, aoegame)", value="indiegame")
        is_minor = st.checkbox("마이너 갤러리 여부", value=True, help="체크 시 '마이너 갤러리' 주소로 탐색합니다. (대부분의 게임 갤러리는 마이너입니다.)")
    with col2:
        keyword = st.text_input("검색어 (옵션, 비워두면 전체 수집)", value="")
        pages_to_crawl = st.number_input("수집할 페이지 수", min_value=1, max_value=20, value=3)

    st.info("💡 팁: 갤러리 ID는 주소창의 `id=xxxxx` 부분입니다. (예: `.../lists/?id=indiegame` -> `indiegame`)")

    if st.button("디시인사이드 수집 시작", key="btn_dc"):
        dc_data = []
        status_box = st.status("갤러리에 접속 중입니다...", expanded=True)
        
        # 주소 결정 (마이너 갤러리 vs 정식 갤러리)
        base_url = "https://gall.dcinside.com/mgallery/board/lists/" if is_minor else "https://gall.dcinside.com/board/lists/"
        
        headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://gall.dcinside.com/',
        'Connection': 'keep-alive'
    }

        try:
            progress_bar = st.progress(0)
            
            for i in range(pages_to_crawl):
                page_num = i + 1
                
                # 파라미터 설정
                params = {'id': gallery_id, 'page': page_num}
                if keyword:
                    params['s_type'] = 'search_subject_memo' # 제목+내용 검색
                    params['s_keyword'] = keyword

                status_box.write(f"📄 {page_num}페이지 읽는 중...")
                
                res = requests.get(base_url, headers=headers, params=params)
                
                if res.status_code != 200:
                    st.error(f"페이지 접속 실패 (코드: {res.status_code}) - 갤러리 ID나 마이너 여부를 확인하세요.")
                    break
                
                soup = BeautifulSoup(res.text, 'html.parser')
                
                # 게시글 리스트 행(tr) 찾기 (디시 클래스 구조: .ub-content)
                rows = soup.find_all('tr', class_='ub-content')
                
                if not rows:
                    status_box.warning(f"{page_num}페이지에서 글을 찾지 못했습니다. (마지막 페이지거나 갤러리 ID 오류)")
                    break

                for row in rows:
                    try:
                        # 공지사항/설문 제외
                        if 'ub-notice' in row.get('class', []): continue
                        
                        # 데이터 추출
                        title_tag = row.find('td', class_='gall_tit').find('a')
                        title = title_tag.text.strip()
                        link = "https://gall.dcinside.com" + title_tag['href']
                        
                        writer_tag = row.find('td', class_='gall_writer')
                        writer = writer_tag.get('data-nick', 'ㅇㅇ')
                        
                        date = row.find('td', class_='gall_date').text.strip()
                        views = row.find('td', class_='gall_count').text.strip()
                        recommend = row.find('td', class_='gall_recommend').text.strip()
                        
                        dc_data.append({
                            '갤러리ID': gallery_id,
                            '제목': title,
                            '작성자': writer,
                            '날짜': date,
                            '조회수': views,
                            '추천수': recommend,
                            '링크': link
                        })
                    except Exception as e:
                        continue # 파싱 에러 난 행은 건너뜀
                
                time.sleep(0.5) # 서버 부하 방지 딜레이
                progress_bar.progress((i + 1) / pages_to_crawl)

            status_box.update(label="수집 완료!", state="complete")
            
            if dc_data:
                df_dc = pd.DataFrame(dc_data)
                st.success(f"총 {len(df_dc)}개의 게시글을 수집했습니다.")
                st.dataframe(df_dc)
                
                # 파일명 생성
                csv_name = f"dc_{gallery_id}_{keyword}.csv" if keyword else f"dc_{gallery_id}_recent.csv"
                st.download_button("엑셀 다운로드", df_dc.to_csv(index=False).encode('utf-8-sig'), csv_name)
            else:
                st.warning("수집된 데이터가 없습니다. 갤러리 ID를 확인해주세요.")

        except Exception as e:
            st.error(f"오류 발생: {e}")