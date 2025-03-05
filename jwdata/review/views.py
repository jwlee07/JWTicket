from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages

from django.http import HttpResponse
from django.shortcuts import render

from django.db.models import F, Count, Min, Avg
from django.db.models.functions import Length
from django.db.models import Value
from django.db.models.functions import Concat, Cast
from django.db.models import CharField

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

from .models import Concert, Review, Seat

import time

import re
import pandas as pd
from collections import Counter, defaultdict
from itertools import combinations
from konlpy.tag import Okt
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.cluster import KMeans

from django.contrib.auth.decorators import login_required

from .crawls import (
    crawl_concert_info, 
    crawl_concert_reviews, 
    crawl_concert_seats
)

from .sheets import (
    sync_patterns_to_sheet,
    sync_db_concerts_to_sheet,
    sync_db_reviews_to_sheet,
    sync_db_seats_to_sheet,
    sync_concert_sheet_to_db,
    sync_reviews_sheet_to_db,
    sync_seats_sheet_to_db,
)

@login_required
def analyze_reviews(request, concert_id, analysis_type):
    # 길게 남긴 리뷰 (공연 ID 필터링 및 내용 길이 기준 정렬)
    if analysis_type == 'long_reviews':
        data = (Review.objects.filter(concert_id=concert_id)
                .annotate(content_length=Length('description'))
                .order_by('-content_length')
                .exclude(description__icontains='뮤지컬 〈테일러〉'))

    # 여러 번 리뷰를 작성한 고객
    elif analysis_type == 'frequent_reviewers':
        frequent_reviewers = (Review.objects.filter(concert_id=concert_id)
                              .values('nickname')
                              .annotate(review_count=Count('id'))
                              .filter(review_count__gt=1)
                              .order_by('-review_count'))

        data = []
        for fr in frequent_reviewers:
            fr_reviews = Review.objects.filter(concert_id=concert_id, nickname=fr['nickname']).values('nickname', 'description', 'star_rating')
            data.append({
                'nickname': fr['nickname'],
                'review_count': fr['review_count'],
                'reviews': fr_reviews
            })

    # 단어 빈도 분석
    elif analysis_type == 'frequent_words':
        reviews = Review.objects.filter(concert_id=concert_id).values_list('description', flat=True)
        text = ' '.join(reviews)
        okt = Okt()
        stop_words = [
            '것', '정말', '노', '수', '이', '더', '보고', '진짜', '또', '그', 
            '꼭', '테일러', '뮤지컬', '좀', '조금', '볼', '말', '은', '는', 
            '이런', '그런', '저런', '그리고', '그러나', '그래서', '하지만', '그리고', 
            '게다가', '다시', '계속', '정말', '너무', '많이', '많은', '모든', '합니다', 
            '있어요', '없어요', '같아요', '보고', '봤습니다', '있습니다', '그렇죠', '맞아요', 
            '아니요', '그래요', '배우', '스토리', '내용', '연기', '무대', '공연', '관람', 
            '좋아요', '별점', '후기', '리뷰', '추천', '비추천',
        ]
        words = [w for w in okt.nouns(text) if w not in stop_words]
        data = Counter(words).most_common(20)

    # 단어 조합 빈도
    elif analysis_type == 'frequent_words_mix':
        reviews = list(Review.objects.filter(concert_id=concert_id).values_list('description', flat=True))
        if not reviews:
            data = []
        else:
            cleaned_reviews = [clean_text(r) for r in reviews]
            df = pd.DataFrame(cleaned_reviews, columns=['CONTENT'])

            stop_words = [
                '것','정말','노','수','이','더','보고','진짜','또','그','꼭','테일러','뮤지컬','좀',
                '조금','볼','말','은','는','이런','그런','저런','그리고','그러나','그래서','하지만',
                '게다가','다시','계속','정말','너무','많이','많은','모든','합니다','있어요','없어요',
                '같아요','보고','봤습니다','있습니다','그렇죠','맞아요','아니요','그래요','테일러뮤지컬',
            ]
            
            cvect = CountVectorizer(ngram_range=(2,6), min_df=2, max_df=0.9, max_features=50, stop_words=stop_words)
            X = cvect.fit_transform(df['CONTENT'])
            dtm = pd.DataFrame(X.toarray(), columns=cvect.get_feature_names_out())
            dtm_sum = dtm.sum().sort_values(ascending=False)
            data = list(dtm_sum.items())

    # 단어 조합 중요도(TFIDF)
    elif analysis_type == 'frequent_words_important':
        reviews = list(Review.objects.filter(concert_id=concert_id).values_list('description', flat=True))
        if not reviews:
            data = []
        else:
            cleaned_reviews = [clean_text(r) for r in reviews]
            df = pd.DataFrame(cleaned_reviews, columns=['CONTENT'])

            stop_words = [
                '것','정말','노','수','이','더','보고','진짜','또','그','꼭','테일러','뮤지컬','좀',
                '조금','볼','말','은','는','이런','그런','저런','그리고','그러나','그래서','하지만',
                '게다가','다시','계속','정말','너무','많이','많은','모든','합니다','있어요','없어요',
                '같아요','보고','봤습니다','있습니다','그렇죠','맞아요','아니요','그래요','테일러뮤지컬',
            ]
            
            tfidf = TfidfVectorizer(ngram_range=(2,6), min_df=2, max_df=0.9, max_features=50, stop_words=stop_words)
            X = tfidf.fit_transform(df['CONTENT'])
            tfidf_df = pd.DataFrame(X.toarray(), columns=tfidf.get_feature_names_out())
            tfidf_sum = tfidf_df.sum().sort_values(ascending=False)
            data = [(word, round(val, 2)) for word, val in tfidf_sum.items()]

    # 비슷한 리뷰(KMeans 클러스터링)
    elif analysis_type == 'similar_reviews':
        reviews = list(Review.objects.filter(concert_id=concert_id).values('nickname', 'description'))
        if not reviews:
            data = {}
        else:
            df = pd.DataFrame(reviews)
            df['CLEANED_CONTENT'] = df['description'].apply(clean_text)
            tfidf_vectorizer = TfidfVectorizer()
            review_dtm = tfidf_vectorizer.fit_transform(df['CLEANED_CONTENT'])

            kmeans = KMeans(n_clusters=10, n_init='auto', random_state=42)
            kmeans.fit(review_dtm)
            df['CLUSTER'] = kmeans.labels_

            data = df.groupby('CLUSTER').apply(
                lambda g: [{"nickname": row['nickname'], "content": row['CLEANED_CONTENT']} for _, row in g.iterrows()]
            ).to_dict()

    # 조회수 높은 리뷰
    elif analysis_type == 'top_view_count_reviews':
        data = Review.objects.filter(concert_id=concert_id).order_by('-view_count')

    # 평점 3점 이하 리뷰
    elif analysis_type == 'low_star_rating_reviews':
        reviews = Review.objects.filter(concert_id=concert_id, star_rating__lte=3).order_by('star_rating')
        data = [r for r in reviews if "뮤지컬 〈테일러〉" not in r.description]

    else:
        data = []

    return render(request, 'review/analysis.html', {'data': data, 'analysis_type': analysis_type})

@login_required
def analyze_all_reviews(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    reviews = Review.objects.all().select_related('concert')
    if start_date and end_date:
        reviews = reviews.filter(date__range=[start_date, end_date])

    # 공연별 요약 (평균 평점, 리뷰 개수)
    concert_summary = (reviews
        .values("concert__name", "concert__place")
        .annotate(average_rating=Avg("star_rating"), total_reviews=Count("id"))
        .order_by("concert__name"))

    # 공연별 날짜별 리뷰 수
    concert_date_summary = {
        c["concert__name"]: (
            reviews
            .filter(concert__name=c["concert__name"])
            .values("date")
            .annotate(reviews_count=Count("id"))
            .order_by("-date")
        ) for c in concert_summary
    }

    # 공연별 날짜별 평균 평점
    concert_date_rating_summary = {
        c["concert__name"]: (
            reviews
            .filter(concert__name=c["concert__name"])
            .values("date")
            .annotate(average_rating=Avg("star_rating"))
            .order_by("-date")
        ) for c in concert_summary
    }

    # 닉네임별 관람 공연 분석(여러 공연 관람한 닉네임)
    nicknames = reviews.values('nickname', 'concert__name').annotate(first_date=Min('date')).distinct()
    nickname_to_concerts = defaultdict(list)
    for n in nicknames:
        nickname_to_concerts[n['nickname']].append({
            'concert__name': n['concert__name'],
            'first_date': n['first_date'].strftime("%Y-%m-%d")
        })

    common_nicknames = {
        nn: sorted(cs, key=lambda x: x['first_date'])
        for nn, cs in nickname_to_concerts.items()
        if len(cs) > 1
    }

    sorted_common_nicknames = dict(sorted(common_nicknames.items(), key=lambda i: len(i[1]), reverse=True))

    # 공연별 닉네임 집합
    concerts_with_nicknames = reviews.values('concert__name', 'nickname').distinct()
    concert_to_nicknames = defaultdict(set)
    for entry in concerts_with_nicknames:
        concert_to_nicknames[entry['concert__name']].add(entry['nickname'])

    # 모든 공연 리스트
    all_concerts = list(concert_to_nicknames.keys())

    # 공연 조합별 닉네임 교집합 크기
    combination_counts = {}
    for r in range(1, len(all_concerts) + 1):
        for combo in combinations(all_concerts, r):
            intersected = set.intersection(*(concert_to_nicknames[c] for c in combo))
            combination_counts[", ".join(combo)] = len(intersected)

    # 전체 리뷰 데이터(테이블 형태로 조회 가능)
    review_data = [
        {
            "공연명": r.concert.name,
            "장소": r.concert.place,
            "작성자": r.nickname,
            "작성일": r.date,
            "평점": r.star_rating,
            "제목": r.title,
            "내용": r.description,
            "조회수": r.view_count,
            "좋아요": r.like_count,
        } for r in reviews
    ]

    return render(request, 'review/all_reviews.html', {
        'start_date': start_date,
        'end_date': end_date,
        'concert_summary': concert_summary,
        'concert_date_summary': concert_date_summary,
        'concert_date_rating_summary': concert_date_rating_summary,
        'common_nicknames': sorted_common_nicknames,
        'combination_counts': combination_counts,
        'reviews': review_data,
    })

@login_required
def analyze_all_seats(request):
    # GET 요청에서 필터 값 가져오기
    selected_concert = request.GET.get('concert')

    # 날짜를 'YYYY-MM-DD' 형태로 연결해서 가상 필드 date 생성
    seats_with_date = (
        Seat.objects.annotate(
            date=Concat(
                Cast(F('year'), output_field=CharField()), Value('-'),
                Cast(F('month'), output_field=CharField()), Value('-'),
                Cast(F('day_num'), output_field=CharField())
            )
        )
    )

    # 공연 필터링
    if selected_concert:
        seats_with_date = seats_with_date.filter(concert__name=selected_concert)

    # 데이터 정렬 및 필요한 필드 선택
    seat_data = (
        seats_with_date.order_by('concert__name', 'date', 'day_str', 'round_name', 'seat_class', 'created_at')
        .values(
            'concert__name',
            'date',
            'day_str',
            'round_name',
            'seat_class',
            'created_at',
            'seat_count',
            'actors'
        )
    )

    # 모든 공연 이름 리스트
    all_concerts = Concert.objects.values_list('name', flat=True).distinct().order_by('name')

    # 모든 회차 정보에서 중복 제거한 회차 목록
    unique_rounds = list(
        Seat.objects.values_list('round_name', flat=True).distinct().order_by('round_name')
    )

    return render(request, 'review/all_seats.html', {
        'seat_data': seat_data,
        'selected_concert': selected_concert,
        'all_concerts': all_concerts,
        'unique_rounds': unique_rounds,
    })

@login_required
def analyze_all_pattern(request):
    reviews = Review.objects.all().select_related('concert')
    
    # 닉네임별 (공연__name) 정보 수집
    nicknames = reviews.values('nickname', 'concert__name').annotate(first_date=Min('date')).distinct()
    nickname_to_concerts = defaultdict(set)
    for n in nicknames:
        nickname_to_concerts[n['nickname']].add(n['concert__name'])
    
    # 공연 리스트 생성
    all_concerts = list(set(reviews.values_list('concert__name', flat=True)))
    filtered_common_nicknames = {}

    for first_concert in all_concerts:
        common_nicknames = {}
        for nn, cs in nickname_to_concerts.items():
            if first_concert in cs and len(cs) > 1:
                sorted_concs = sorted(cs)
                concert_dates = []
                for concert in sorted_concs:
                    first_review = reviews.filter(nickname=nn, concert__name=concert).order_by('date').first()
                    if first_review:
                        date_str = first_review.date.strftime("%Y-%m-%d")
                    else:
                        date_str = 'Unknown'
                    concert_dates.append({'concert': concert, 'date': date_str})
                # 날짜 기준 정렬
                concert_dates_sorted = sorted(concert_dates, key=lambda x: x['date'])
                if concert_dates_sorted[0]['concert'] == first_concert:
                    common_nicknames[nn] = concert_dates_sorted

        # 샌키 다이어그램 데이터 생성
        sankey_data = {
            "type": "sankey",
            "orientation": "h",
            "node": {
                "pad": 15,
                "thickness": 20,
                "line": {"color": "black", "width": 0.5},
                "label": [],
            },
            "link": {"source": [], "target": [], "value": []},
        }
        node_index = {}
        idx = 0

        for nn, concerts in common_nicknames.items():
            for i in range(len(concerts) - 1):
                source = concerts[i]['concert']
                target = concerts[i + 1]['concert']

                if source not in node_index:
                    node_index[source] = idx
                    sankey_data['node']['label'].append(source)
                    idx += 1
                if target not in node_index:
                    node_index[target] = idx
                    sankey_data['node']['label'].append(target)
                    idx += 1

                sankey_data['link']['source'].append(node_index[source])
                sankey_data['link']['target'].append(node_index[target])
                sankey_data['link']['value'].append(1)

        if sankey_data['node']['label']:
            filtered_common_nicknames[first_concert] = sankey_data
    
    # 닉네임 별 관람 패턴 (두 개 이상의 공연 관람한 경우만 수집)
    common_nicknames = {}
    for nn, cs in nickname_to_concerts.items():
        if len(cs) > 1:
            sorted_concs = sorted(cs)
            concert_dates = []
            for concert in sorted_concs:
                first_review = reviews.filter(nickname=nn, concert__name=concert).order_by('date').first()
                if first_review:
                    date_str = first_review.date.strftime("%Y-%m-%d")
                else:
                    date_str = 'Unknown'
                concert_dates.append({'concert': concert, 'date': date_str})
            # 날짜 기준 정렬
            concert_dates_sorted = sorted(concert_dates, key=lambda x: x['date'])
            common_nicknames[nn] = concert_dates_sorted
    
    # 관람 패턴(닉네임별 공연 목록) 내림차순 정렬
    sorted_common_nicknames = dict(
        sorted(common_nicknames.items(), key=lambda item: len(item[1]), reverse=True)
    )
    
    # 공연 조합별 분포 계산(중간 생략)
    combination_counts = defaultdict(int)
    for concerts in nickname_to_concerts.values():
        for r in range(1, len(concerts) + 1):
            for combo in combinations(sorted(concerts), r):
                combination_key = ", ".join(combo)
                combination_counts[combination_key] += 1

    sorted_combinations = sorted(combination_counts.items(), key=lambda x: x[1], reverse=True)
    combination_counts_dict = dict(sorted_combinations)
    print("[패턴 정보 계산 완료]")
    
    # sync_patterns_to_sheet(sorted_common_nicknames)
    # print("[패턴 정보 업로드 완료]")

    return render(request, 'review/all_pattern.html', {
        'filtered_common_nicknames': filtered_common_nicknames,
        'all_concerts': all_concerts,
        'common_nicknames': sorted_common_nicknames,
        'combination_counts': combination_counts_dict,
    })
    
# ==================================================================
# DB <-> Google Sheet 데이터 동기화
# ==================================================================

@login_required
def sync_all_db_to_sheet(request):
    logs = []

    # 1) Concert 동기화
    sync_db_concerts_to_sheet()
    logs.append("[DB -> Sheet] Concert 동기화 완료")
    print("[DB -> Sheet] Concert 동기화 완료")

    # 2) Review 동기화
    sync_db_reviews_to_sheet()
    logs.append("[DB -> Sheet] Review 동기화 완료")
    print("[DB -> Sheet] Review 동기화 완료")

    # 3) Seat 동기화
    sync_db_seats_to_sheet()
    logs.append("[DB -> Sheet] Seat 동기화 완료")
    print("[DB -> Sheet] Seat 동기화 완료")

    response_text = "\n".join(logs)
    return HttpResponse(response_text, content_type="text/plain")

@login_required
def sync_all_sheet_to_db(request):
    logs = []

    sync_concert_sheet_to_db()
    logs.append("[Sheet -> DB] Concert 동기화 완료")
    print("[Sheet -> DB] Concert 동기화 완료")

    sync_reviews_sheet_to_db()
    logs.append("[Sheet -> DB] Review 동기화 완료")
    print("[Sheet -> DB] Review 동기화 완료")

    sync_seats_sheet_to_db()
    logs.append("[Sheet -> DB] Seat 동기화 완료")
    print("[Sheet -> DB] Seat 동기화 완료")

    response_text = "\n".join(logs)
    return HttpResponse(response_text, content_type="text/plain")

# ==================================================================
# 크롤링
# ==================================================================

@login_required
def search_and_crawl(request):
    concerts = Concert.objects.all()
    active_concert_id = request.GET.get('active_concert_id')

    if request.method == 'POST':
        query = request.POST.get('query', '')
        search_type = request.POST.get('search_type', 'review')

        if query:
            # 크롬 드라이버 실행
            driver = webdriver.Chrome()
            try:
                # 인터파크 메인 페이지 진입
                driver.get("https://tickets.interpark.com/")
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@id="__next"]/div/header/div[2]/div[1]/div/div[3]/div'))
                )
                time.sleep(2)

                # 검색창 클릭
                search_box = driver.find_element(By.XPATH, '//*[@id="__next"]/div/header/div[2]/div[1]/div/div[3]/div')
                search_box.click()
                time.sleep(2)

                # 검색어 입력 후 엔터
                active_input = driver.find_element(By.XPATH, '//*[@id="__next"]/div/header/div[2]/div[1]/div/div[3]/div/input')
                active_input.send_keys(query)
                time.sleep(2)
                active_input.send_keys(Keys.RETURN)

                # 첫 번째 검색 결과 클릭
                element = WebDriverWait(driver, 10).until(
                    EC.any_of(
                        EC.element_to_be_clickable((By.XPATH, '//*[@id="contents"]/div/div/div[1]/div[2]/a[1]/ul')),
                        EC.element_to_be_clickable((By.XPATH, '//*[@id="contents"]/div/div/div[2]/div[2]/a[1]/ul'))
                    )
                )
                element.click()
                time.sleep(2)

                # 새 창으로 전환(인터파크 상세 페이지)
                driver.switch_to.window(driver.window_handles[1])
                time.sleep(2)

                # 예매 안내 팝업 닫기
                try:
                    popup_close_button = driver.find_element(By.XPATH, '//*[@id="popup-prdGuide"]/div/div[3]/button')
                    driver.execute_script("arguments[0].click();", popup_close_button)
                    time.sleep(2)
                except NoSuchElementException:
                    print("팝업 닫기 버튼 없음, 무시")

                # 공연 정보 크롤링
                concert = crawl_concert_info(driver)
                if not concert:
                    print(f"[WARN] '{query}' 검색 결과와 매칭되는 DB 공연 정보가 없어 크롤링 스킵")
                    return render(request, 'review/index.html', {
                        'concerts': concerts,
                        'active_concert_id': active_concert_id,
                    })

                print(f"[공연 정보 크롤링 완료] 공연명: {concert.name}")

                # 검색 타입에 따른 크롤링 로직 분기
                if search_type == 'review':
                    print(f"[리뷰 크롤링 시작] 공연명: {concert.name}")
                    crawl_concert_reviews(driver, concert)
                    print(f"[리뷰 크롤링 완료] 공연명: {concert.name}")
                elif search_type == 'seat':
                    print(f"[좌석 크롤링 시작] 공연명: {concert.name}")
                    crawl_concert_seats(driver, concert)
                    print(f"[좌석 크롤링 완료] 공연명: {concert.name}")

            finally:
                driver.quit()

    return render(request, 'review/index.html', {
        'concerts': concerts,
        'active_concert_id': active_concert_id,
    })

# ==================================================================
# 로그인
# ==================================================================

def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)  

        if user is not None:
            login(request, user)
            # messages.success(request, f"{username} 님, 반가워요!")
            return redirect('search_and_crawl')  
        else:
            messages.error(request, "티켓스퀘어 PM 이진욱님에게 문의하세요:)")
            return render(request, 'review/login.html')
    else:
        return render(request, 'review/login.html')

def user_logout(request):
    response = render(request, 'review/login.html')

    logout(request)
    request.session.flush()
    for cookie in request.COOKIES:
        response.delete_cookie(cookie)
    
    return response

# ==================================================================
# 텍스트 전처리 함수
# ==================================================================

def clean_text(text):
    cleaned = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', text)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned