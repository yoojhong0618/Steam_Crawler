import streamlit as st
import requests
import pandas as pd
import time
import random
import urllib3
from datetime import datetime, time as dt_time
from bs4 import BeautifulSoup
from googleapiclient.discovery import build

# --- 📊 시각화 라이브러리 ---
from kiwipiepy import Kiwi
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from collections import Counter
import matplotlib.font_manager as fm

# SSL 경고 메시지 숨기기
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 페이지 기본 설정
st.set_page_config(page_title="Steam & YouTube 데이터 수집기", layout="wide")

# --- 📊 시각화 엔진 (언어별 분석 기능 탑재) ---
def visualize_data(df, col_name):
    """
    [Final] 언어별 독립 분석 시각화 엔진
    사용자가 한국어/영어를 선택하면 해당 언어의 키워드만 분석하여 보여줍니다.
    """
    if df is None or df.empty:
        return

    st.divider()
    st.subheader(f"📊 {len(df)}개 데이터 키워드 분석")
    
    # 1. 🎛️ 언어 선택 드롭다운 (한국어 vs 영어)
    lang_option = st.selectbox(
        "분석할 언어를 선택하세요:",
        ["🇰🇷 한국어", "🇺🇸 영어"],
        index=0
    )
    
    with st.spinner(f"💬 {lang_option} 데이터를 추출하고 분석 중입니다..."):
        try:
            kiwi = Kiwi()
            
            # 2. 불용어(Stopwords) 정의 - 언어별 분리
            stop_words_kr = {
                '게임', '진짜', '너무', '아니', '근데', '솔직히', '그냥', '이거', '정말', 
                '생각', '사람', '하고', '해서', '있는', '없는', '입니다', '합니다', '그게', '존나', '때문에',
                '스팀', '플레이', '정도', '하나', '지금', '일단', '뭔가', '보고', '하면', '해서', '하게', '같아요', '좋아요'
            }
            
            stop_words_en = {
                'the', 'a', 'an', 'is', 'are', 'was', 'were', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'it', 'this', 'that',
                'and', 'but', 'or', 'so', 'if', 'not', 'no', 'yes', 'can', 'will', 'my', 'your', 'he', 'she', 'they', 'we',
                'game', 'games', 'play', 'playing', 'player', 'played', 'review', 'steam', 'fun', 'good', 'bad', 'best', 'like', 'just', 'more',
                'time', 'story', 'really', 'very', 'much', 'get', 'even', 'make', 'made', 'about', 'from', 'out'
            }
            
            # 3. 텍스트 전처리
            text_list = df[col_name].dropna().astype(str).tolist()
            full_text = " ".join(text_list)
            
            # 속도 최적화 (너무 긴 텍스트는 자름)
            if len(full_text) > 100000:
                full_text = full_text[:100000]
                st.caption("※ 데이터가 너무 많아 분석 속도를 위해 일부 텍스트만 샘플링했습니다.")

            # 4. 토큰화 및 키워드 추출
            tokens = kiwi.tokenize(full_text)
            keywords = []

            # [핵심] 선택된 언어에 따라 로직 분리
            if lang_option == "🇰🇷 한국어":
                for t in tokens:
                    # 한국어 명사(NNG, NNP)만 추출
                    if t.tag in ['NNG', 'NNP'] and len(t.form) > 1:
                        if t.form not in stop_words_kr:
                            keywords.append(t.form)
                            
            elif lang_option == "🇺🇸 영어":
                for t in tokens:
                    # 영어 알파벳(SL)만 추출
                    if t.tag == 'SL' and len(t.form) > 2:
                        word_lower = t.form.lower()
                        if word_lower not in stop_words_en:
                            keywords.append(word_lower)
            
            if not keywords:
                st.warning(f"선택하신 언어({lang_option})로 작성된 유의미한 단어를 찾을 수 없습니다.")
                return

            # 5. 빈도수 계산
            count = Counter(keywords)
            top_20 = dict(count.most_common(20))

        except Exception as e:
            st.error(f"분석 중 오류가 발생했습니다: {e}")
            return

    # --- 시각화 화면 구성 ---
    col_vis1, col_vis2 = st.columns(2)

    with col_vis1:
        st.markdown(f"#### ☁️ 워드 클라우드 ({lang_option})")
        try:
            # 폰트 설정 (GitHub에 올린 폰트 파일명과 일치해야 함)
            font_path = "NanumGothic.ttf" 
            try:
                wc = WordCloud(
                    font_path=font_path, 
                    background_color='white',
                    width=600,
                    height=400,
                    max_words=100
                ).generate_from_frequencies(count)
            except:
                # 폰트 파일 없을 시 기본 폰트
                wc = WordCloud(
                    background_color='white',
                    width=600,
                    height=400,
                    max_words=100
                ).generate_from_frequencies(count)

            fig = plt.figure(figsize=(10, 6))
            plt.imshow(wc, interpolation='bilinear')
            plt.axis('off')
            st.pyplot(fig)
            if lang_option == "🇰🇷 한국어":
                st.caption("※ 한글이 □□로 보인다면 `NanumGothic.ttf` 파일을 업로드해주세요.")
        except Exception as e:
            st.error(f"워드 클라우드 생성 실패: {e}")

    with col_vis2:
        st.markdown(f"#### 📊 핵심 키워드 Top 10 ({lang_option})")
        top_10 = dict(list(top_20.items())[:10])
        st.bar_chart(top_10, color="#FF4B4B")
        
        with st.expander("📋 상세 데이터 보기"):
            st.dataframe(pd.DataFrame(list(top_20.items()), columns=['키워드', '빈도수']), use_container_width=True)


# --- 🔐 비밀번호 잠금 ---
password = st.text_input("접속 암호", type="password")
if password != "smilegate":
    st.warning("암호를 입력하세요.")
    st.stop()

st.title("Steam & YouTube 데이터 수집기 (Visualized)")

# --- 사이드바 ---
with st.sidebar:
    st.header("설정")
    menu = st.selectbox("분석 채널", ["Steam (스팀)", "YouTube (유튜브)", "4chan (해외 포럼)", "디시인사이드"])
    st.divider()
    st.info("💡 **시각화 기능 안내**\n\n'Steam 리뷰'와 'YouTube 댓글' 수집 시에만 하단에 워드 클라우드와 분석 차트가 나타납니다.")

# =========================================================
# [SECTION 1] Steam (스팀)
# =========================================================
if menu == "Steam (스팀)":
    tab1, tab2 = st.tabs(["리뷰 수집 (API) - 📊시각화", "토론장 수집 (크롤링)"])
    
    # [TAB 1] 리뷰 수집 (시각화 적용 O)
    with tab1:
        st.subheader("리뷰 데이터 수집 및 분석")
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
                    status_box.success(f"완료! {start_date} ~ {end_date} 기간의 리뷰 {len(df)}개를 수집했습니다.")
                    
                    st.dataframe(df)
                    st.download_button("엑셀 다운로드", df.to_csv(index=False).encode('utf-8-sig'), "steam_reviews.csv")

                    # 🔥 [시각화 엔진 가동]
                    visualize_data(df, "내용")

                else:
                    st.warning("해당 기간에 작성된 리뷰가 없습니다.")
            except Exception as e:
                st.error(f"오류 발생: {e}")

    # [TAB 2] 토론장 수집 (시각화 적용 X)
    with tab2:
        st.subheader("토론장 상세 수집 (본문+댓글)")
        st.caption("※ 토론장은 텍스트 구조가 복잡하여 현재 시각화 기능을 지원하지 않습니다.")
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
# [SECTION 2] YouTube (유튜브)
# =========================================================
elif menu == "YouTube (유튜브)":
    st.subheader("🟥 YouTube 데이터 수집기")
    yt_api_key = st.text_input("YouTube Data API Key", type="password")

    tab_yt1, tab_yt2 = st.tabs(["🔍 키워드 검색 - 📊시각화", "🔗 개별 영상 링크 - 📊시각화"])

    # [TAB 1] 키워드 검색 (시각화 적용 O)
    with tab_yt1:
        st.caption("특정 키워드(게임명 등)를 검색하여 댓글을 수집하고 분석합니다.")
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
                st.error("맨 위에 YouTube API Key를 입력해주세요.")
            else:
                status_box = st.status("데이터 수집 및 분석 중...", expanded=True)
                youtube_data = []
                
                try:
                    youtube = build('youtube', 'v3', developerKey=yt_api_key)
                    start_dt = datetime.combine(start_date_yt, dt_time.min).isoformat() + "Z"
                    end_dt = datetime.combine(end_date_yt, dt_time.max).isoformat() + "Z"
                    
                    search_response = youtube.search().list(
                        q=search_keyword, type='video', part='id', order='viewCount',
                        publishedAfter=start_dt, publishedBefore=end_dt, maxResults=max_videos
                    ).execute()
                    
                    video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
                    
                    if not video_ids:
                        status_box.update(label="검색된 영상이 없습니다.", state="error")
                    else:
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
                            prog_bar = st.progress(0)
                            for idx, video in enumerate(target_videos):
                                vid = video['id']
                                v_title = video['snippet']['title']
                                v_views = video['statistics'].get('viewCount', 0)
                                v_date = video['snippet']['publishedAt'][:10]
                                
                                status_box.write(f"Collecting comments from: {v_title[:30]}...")
                                
                                try:
                                    comment_request = youtube.commentThreads().list(
                                        part="snippet", videoId=vid, maxResults=50, textFormat="plainText", order="relevance"
                                    )
                                    comment_response = comment_request.execute()
                                    
                                    for item in comment_response.get('items', []):
                                        c_snip = item['snippet']['topLevelComment']['snippet']
                                        youtube_data.append({
                                            '영상제목': v_title, '조회수': v_views, '영상게시일': v_date,
                                            '작성자': c_snip['authorDisplayName'], '댓글내용': c_snip['textDisplay'],
                                            '좋아요': c_snip['likeCount'], '댓글작성일': c_snip['publishedAt'][:10]
                                        })
                                except: pass
                                prog_bar.progress((idx + 1) / len(target_videos))
                            
                            status_box.update(label="수집 완료!", state="complete")
                            
                            if youtube_data:
                                df_yt = pd.DataFrame(youtube_data)
                                st.dataframe(df_yt)
                                st.download_button("결과 다운로드", df_yt.to_csv(index=False).encode('utf-8-sig'), f"yt_keyword_{search_keyword}.csv")
                                
                                # 🔥 [시각화 엔진 가동]
                                visualize_data(df_yt, "댓글내용")
                            else: st.warning("댓글을 찾을 수 없습니다.")
                except Exception as e:
                    status_box.update(label="에러 발생", state="error")
                    st.error(f"오류: {e}")

    # [TAB 2] 개별 영상 링크 (시각화 적용 O)
    with tab_yt2:
        st.caption("개별 영상의 댓글을 집중적으로 분석합니다.")
        target_url = st.text_input("YouTube 영상 주소 (URL)", placeholder="예: https://www.youtube.com/watch?v=...")
        max_comments_single = st.number_input("수집할 댓글 수 (최대)", min_value=10, max_value=500, value=100, step=10)

        if st.button("단일 영상 댓글 수집", key="btn_yt_link"):
            if not yt_api_key or not target_url:
                st.error("API Key와 영상 주소를 확인해주세요.")
            else:
                video_id = None
                if "v=" in target_url: video_id = target_url.split("v=")[1].split("&")[0]
                elif "youtu.be" in target_url: video_id = target_url.split("/")[-1].split("?")[0]
                
                if not video_id:
                    st.error("올바른 YouTube URL이 아닙니다.")
                else:
                    status_box = st.status(f"영상 ID: {video_id} 분석 중...", expanded=True)
                    single_yt_data = []
                    try:
                        youtube = build('youtube', 'v3', developerKey=yt_api_key)
                        
                        # 영상 정보 확인
                        video_response = youtube.videos().list(part='snippet,statistics', id=video_id).execute()
                        if not video_response.get('items'):
                            status_box.update(label="영상을 찾을 수 없습니다.", state="error")
                        else:
                            v_info = video_response['items'][0]
                            v_title = v_info['snippet']['title']
                            status_box.write(f"📺 분석 대상: {v_title}")

                            # 댓글 수집
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
                                if not next_page_token or comments_collected >= max_comments_single: break
                            
                            status_box.update(label="수집 완료!", state="complete")
                            
                            if single_yt_data:
                                df_single = pd.DataFrame(single_yt_data)
                                st.success(f"총 {len(df_single)}개의 댓글을 수집했습니다.")
                                st.dataframe(df_single)
                                st.download_button("결과 다운로드", df_single.to_csv(index=False).encode('utf-8-sig'), f"yt_single_{video_id}.csv")
                                
                                # 🔥 [시각화 엔진 가동]
                                visualize_data(df_single, "댓글내용")
                            else:
                                st.warning("댓글이 없거나 차단된 영상입니다.")
                    except Exception as e:
                        status_box.update(label="에러 발생", state="error")
                        st.error(f"오류: {e}")

# =========================================================
# [SECTION 3] 4chan (포챈) - 시각화 제외
# =========================================================
elif menu == "4chan (해외 포럼)": 
    st.subheader("🍀 4chan (/v/ - Video Games) 실시간 반응")
    col1, col2 = st.columns([3, 1])
    with col1:
        search_keyword = st.text_input("검색어 (영어, 예: Elden Ring)", value="Elden Ring")
    with col2:
        result_limit = st.number_input("가져올 스레드 수", min_value=1, max_value=20, value=3)

    if st.button("4chan 데이터 수집 시작", key="btn_4chan"):
        status_box = st.status("4chan 스캔 중...", expanded=True)
        fourchan_data = []
        try:
            catalog_url = "https://a.4cdn.org/v/catalog.json"
            res = requests.get(catalog_url, verify=False)
            if res.status_code == 200:
                pages = res.json()
                found_threads = []
                for page in pages:
                    for thread in page.get('threads', []):
                        title = thread.get('sub', '') 
                        comment = thread.get('com', '')
                        if search_keyword.lower() in title.lower() or search_keyword.lower() in comment.lower():
                            found_threads.append(thread['no'])
                            if len(found_threads) >= result_limit: break
                    if len(found_threads) >= result_limit: break
                
                if found_threads:
                    status_box.write(f"✅ {len(found_threads)}개 스레드 발견. 상세 수집 중...")
                    progress_bar = st.progress(0)
                    for idx, thread_id in enumerate(found_threads):
                        thread_url = f"https://a.4cdn.org/v/thread/{thread_id}.json"
                        t_res = requests.get(thread_url, verify=False)
                        if t_res.status_code == 200:
                            posts = t_res.json().get('posts', [])
                            op_post = posts[0]
                            op_content = BeautifulSoup(op_post.get('com', ''), "html.parser").get_text()
                            fourchan_data.append({
                                '구분': '원글', '내용': op_content, '작성일': datetime.fromtimestamp(op_post['time']).strftime('%Y-%m-%d %H:%M')
                            })
                            for reply in posts[1:]:
                                reply_content = BeautifulSoup(reply.get('com', ''), "html.parser").get_text()
                                fourchan_data.append({
                                    '구분': '댓글', '내용': reply_content, '작성일': datetime.fromtimestamp(reply['time']).strftime('%Y-%m-%d %H:%M')
                                })
                        time.sleep(0.5)
                        progress_bar.progress((idx + 1) / len(found_threads))
                    
                    status_box.update(label="완료!", state="complete")
                    if fourchan_data:
                        df_4chan = pd.DataFrame(fourchan_data)
                        st.dataframe(df_4chan)
                        st.download_button("엑셀 다운로드", df_4chan.to_csv(index=False).encode('utf-8-sig'), f"4chan_{search_keyword}.csv")
                else: status_box.update(label="검색 결과 없음", state="error")
            else: st.error("접속 실패")
        except Exception as e: st.error(f"오류: {e}")

# =========================================================
# [SECTION 4] 디시인사이드 - 시각화 제외
# =========================================================
elif menu == "디시인사이드":
    st.subheader("🔵 디시인사이드 갤러리 수집")
    col1, col2 = st.columns(2)
    with col1:
        gallery_id = st.text_input("갤러리 ID", value="indiegame")
        is_minor = st.checkbox("마이너 갤러리 여부", value=True)
    with col2:
        keyword = st.text_input("검색어", value="")
        pages_to_crawl = st.number_input("페이지 수", value=1)

    if st.button("디시인사이드 수집 시작", key="btn_dc"):
        status_box = st.status("접속 중...", expanded=True)
        dc_data = []
        base_url = "https://gall.dcinside.com/mgallery/board/lists/" if is_minor else "https://gall.dcinside.com/board/lists/"
        target_referer = f"{base_url}?id={gallery_id}"
        
        # 모바일 위장 헤더 사용 (차단 우회용)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Mobile Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': target_referer,
            'Connection': 'keep-alive'
        }

        try:
            progress_bar = st.progress(0)
            for i in range(pages_to_crawl):
                params = {'id': gallery_id, 'page': i+1}
                if keyword:
                    params['s_type'] = 'search_subject_memo'
                    params['s_keyword'] = keyword
                
                # 랜덤 딜레이 (봇 탐지 우회)
                wait_time = random.uniform(2, 4)
                status_box.write(f"⏳ {i+1}페이지 수집 전 {wait_time:.1f}초 대기...")
                time.sleep(wait_time)
                
                res = requests.get(base_url, headers=headers, params=params)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, 'html.parser')
                    rows = soup.find_all('tr', class_='ub-content')
                    for row in rows:
                        try:
                            if 'ub-notice' in row.get('class', []): continue
                            title_tag = row.find('td', class_='gall_tit').find('a')
                            title = title_tag.text.strip()
                            dc_data.append({'갤러리ID': gallery_id, '제목': title})
                        except: continue
                    progress_bar.progress((i + 1) / pages_to_crawl)
                else:
                    st.error(f"접속 실패 Code: {res.status_code}")
                    break
            
            status_box.update(label="완료!", state="complete")
            if dc_data:
                df_dc = pd.DataFrame(dc_data)
                st.dataframe(df_dc)
                st.download_button("엑셀 다운로드", df_dc.to_csv(index=False).encode('utf-8-sig'), f"dc_{gallery_id}.csv")
            else: st.warning("데이터 없음")
        except Exception as e: st.error(f"오류: {e}")