from django.shortcuts import render
from django.db.models import Count, Avg, Q, Min
from django.db.models.functions import Length
from .models import Concert, Review
from datetime import datetime
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

import re
import pandas as pd
from collections import Counter, defaultdict
from itertools import combinations
from konlpy.tag import Okt
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans

def search_and_crawl(request):
    concerts = Concert.objects.all()  # 모든 Concert 데이터를 가져옴
    active_concert_id = request.GET.get('active_concert_id')  # GET 파라미터에서 active_concert_id 가져오기

    if request.method == 'POST':
        query = request.POST.get('query', '')

        if query:
            driver = webdriver.Chrome()

            try:
                # Interpark 메인 페이지 이동
                driver.get("https://tickets.interpark.com/")
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@id="__next"]/div/header/div[2]/div[1]/div/div[3]/div'))
                )
                time.sleep(2)

                # 검색창 클릭
                search_box = driver.find_element(By.XPATH, '//*[@id="__next"]/div/header/div[2]/div[1]/div/div[3]/div')
                search_box.click()
                time.sleep(2)

                # 검색어 입력 및 실행
                active_input = driver.find_element(By.XPATH, '//*[@id="__next"]/div/header/div[2]/div[1]/div/div[3]/div/input')
                active_input.send_keys(query)
                time.sleep(2)
                active_input.send_keys(Keys.RETURN)

                # 첫 번째 검색 결과 클릭
                WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="contents"]/div/div/div[1]/div[2]/a[1]/ul'))
                ).click()
                time.sleep(2)

                # 새 창으로 전환
                driver.switch_to.window(driver.window_handles[1])
                time.sleep(2)

                # 예매 안내 닫기
                try:
                    popup_close_button = driver.find_element(By.XPATH, '//*[@id="popup-prdGuide"]/div/div[3]/button')
                    driver.execute_script("arguments[0].click();", popup_close_button)
                    time.sleep(2)
                except NoSuchElementException:
                    print("팝업 닫기 버튼을 찾을 수 없습니다. 무시하고 진행합니다.")

                # 공연 정보 크롤링
                name = driver.find_element(By.XPATH, '//*[@id="container"]/div[2]/div[1]/div[2]/div[1]/div/div[1]/h2').text
                place = driver.find_element(By.XPATH, '//*[@id="container"]/div[2]/div[1]/div[2]/div[1]/div/div[2]/ul/li[1]/div/a').text
                start_date_raw = driver.find_element(By.XPATH, '//*[@id="container"]/div[2]/div[1]/div[2]/div[1]/div/div[2]/ul/li[2]/div/p').text.split('~')[0].strip()
                end_date_raw = driver.find_element(By.XPATH, '//*[@id="container"]/div[2]/div[1]/div[2]/div[1]/div/div[2]/ul/li[2]/div/p').text.split('~')[1].strip()
                duration_minutes = driver.find_element(By.XPATH, '//*[@id="container"]/div[2]/div[1]/div[2]/div[1]/div/div[2]/ul/li[3]/div/p').text.replace('분', '').strip()

                # 날짜 변환 (YYYY.MM.DD -> YYYY-MM-DD)
                start_date = datetime.strptime(start_date_raw, "%Y.%m.%d").strftime("%Y-%m-%d")
                end_date = datetime.strptime(end_date_raw, "%Y.%m.%d").strftime("%Y-%m-%d")

                # 공연 정보를 DB에 저장
                concert, created = Concert.objects.get_or_create(
                    name=name,
                    place=place,
                    start_date=start_date,
                    end_date=end_date,
                    defaults={'duration_minutes': int(duration_minutes) if duration_minutes.isdigit() else None},
                )
                if created:
                    print(f"공연 정보 저장 완료: {concert}")
                time.sleep(2)

                # 관람후기 버튼 클릭
                review_category_button = driver.find_element(By.XPATH, '//*[@id="productMainBody"]/nav/ul/li[4]/a')
                driver.execute_script("arguments[0].click();", review_category_button)
                time.sleep(2)

                # 관람후기 총 개수
                review_total_count = 0
                try:
                    review_total_count_element = driver.find_element(By.XPATH, '//*[@id="prdReview"]/div/div[3]/div[1]/div[1]/div[1]/strong/span')
                    review_total_count = int(review_total_count_element.text)
                except NoSuchElementException:
                    try:
                        review_total_count_element = driver.find_element(By.XPATH, '//*[@id="prdReview"]/div/div[4]/div[1]/div[1]/div[1]/strong/span')
                        review_total_count = int(review_total_count_element.text)
                    except NoSuchElementException:
                        print("관람후기 총 개수를 찾을 수 없습니다.")

                review_num_pages = (review_total_count + 14) // 15

                for review_page in range(1, review_num_pages + 1):
                    # 리뷰 데이터 추출
                    reviews = driver.find_elements(By.XPATH, '//ul[@class="bbsList reviewList"]/li[@class="bbsItem"]')
                    for review in reviews:
                        try:
                            nickname = review.find_element(By.CLASS_NAME, 'name').text.strip()
                            date_raw = review.find_element(By.XPATH, './/li[@class="bbsItemInfoList"][2]').text.strip()
                            view_count = int(''.join(filter(str.isdigit, review.find_element(By.XPATH, './/li[@class="bbsItemInfoList"][3]').text)))
                            like_count = int(''.join(filter(str.isdigit, review.find_element(By.XPATH, './/li[@class="bbsItemInfoList"][4]').text)))
                            title = review.find_element(By.CLASS_NAME, 'bbsTitleText').text.strip()
                            description = review.find_element(By.CLASS_NAME, 'bbsText').text.strip()
                            star_rating = float(review.find_element(By.CLASS_NAME, 'prdStarIcon').get_attribute('data-star'))

                            # 날짜 변환
                            date = datetime.strptime(date_raw, "%Y.%m.%d").strftime("%Y-%m-%d")

                            # 리뷰 저장
                            if not Review.objects.filter(concert=concert, nickname=nickname, date=date, title=title).exists():
                                Review.objects.create(
                                    concert=concert,
                                    nickname=nickname,
                                    date=date,
                                    view_count=view_count,
                                    like_count=like_count,
                                    title=title,
                                    description=description,
                                    star_rating=star_rating,
                                )
                                print(f"리뷰 저장 완료 - 닉네임: {nickname}, 제목: {title}, 내용: {description}")
                        except Exception as e:
                            print(f"리뷰 처리 중 오류 발생: {e}")

                    # 다음 페이지 클릭
                    if review_page < review_num_pages:
                        try:
                            if review_page % 10 == 0:
                                group_index = review_page // 10
                                if group_index > 2:
                                    group_index = 2
                                next_group_button = None
                                try:
                                    next_group_button = driver.find_element(By.XPATH, f'//*[@id="prdReview"]/div/div[3]/div[2]/a[{group_index}]')
                                except NoSuchElementException:
                                    try:
                                        next_group_button = driver.find_element(By.XPATH, f'//*[@id="prdReview"]/div/div[4]/div[2]/a[{group_index}]')
                                    except NoSuchElementException:
                                        print("다음 그룹 버튼을 찾을 수 없습니다.")
                                        break
                                    
                                if next_group_button:
                                    driver.execute_script("arguments[0].click();", next_group_button)
                                    time.sleep(2)
                            else:
                                # 다음 페이지 버튼 클릭
                                next_page_text = str(review_page + 1)
                                try:
                                    next_page_button = WebDriverWait(driver, 5).until(
                                        EC.element_to_be_clickable((By.LINK_TEXT, next_page_text))
                                    )
                                    driver.execute_script("arguments[0].click();", next_page_button)
                                    time.sleep(2)
                                except NoSuchElementException:
                                    print(f"페이지 {next_page_text}로 이동 실패.")
                                    break
                        except Exception as e:
                            print(f"페이지 이동 처리 중 오류 발생: {e}")
                            break
                    print(f"----------{review_page}/{review_num_pages}----------")

            finally:
                driver.quit()

    return render(request, 'review/index.html', { 'concerts': concerts, 'active_concert_id': active_concert_id,})

def analyze_reviews(request, concert_id, analysis_type):
    # 리뷰를 길게 남긴 사람은 뭐라고 작성했을까?
    if analysis_type == 'long_reviews':
        data = Review.objects.filter(concert_id=concert_id).annotate(
            content_length=Length('description')
        ).order_by('-content_length')

        # "뮤지컬 〈테일러〉"를 포함한 description을 제거
        data = data.exclude(description__icontains='뮤지컬 〈테일러〉')

    # 여러 번 리뷰를 작성한 고객은 어떤 리뷰를 달았을까?
    elif analysis_type == 'frequent_reviewers':
        frequent_reviewers = Review.objects.filter(concert_id=concert_id).values(
            'nickname'
        ).annotate(review_count=Count('id')).filter(review_count__gt=1).order_by('-review_count')

        data = []
        for reviewer in frequent_reviewers:
            reviews = Review.objects.filter(concert_id=concert_id, nickname=reviewer['nickname']).values(
                'nickname', 'description', 'star_rating'
            )
            data.append({
                'nickname': reviewer['nickname'],
                'review_count': reviewer['review_count'],
                'reviews': reviews
            })

    # 리뷰 텍스트에는 어떤 단어가 가장 많이 나왔을까?
    # 텍스트 데이터에서 가장 자주 등장하는 단어를 파악
    elif analysis_type == 'frequent_words':
        reviews = Review.objects.filter(concert_id=concert_id).values_list('description', flat=True)
        text = ' '.join(reviews)
    
        # Okt를 사용하여 명사 추출
        okt = Okt()
        
        stop_words = ['것', '정말', '노', '수', '이', '더', '보고', '진짜', '또', '그', 
                      '꼭', '테일러', '뮤지컬', '좀', '조금', '볼', '말', '은', '는', 
                      '이런', '그런', '저런', '그리고', '그러나', '그래서', '하지만', '그리고', 
                      '게다가', '다시', '계속', '정말', '너무', '많이', '많은', '모든', '합니다', 
                      '있어요', '없어요', '같아요', '보고', '봤습니다', '있습니다', '그렇죠', '맞아요', 
                      '아니요', '그래요', '배우', '스토리', '내용', '연기', '무대', '공연', '관람', 
                      '좋아요', '별점', '후기', '리뷰', '추천', '비추천',
        ]

        words = [word for word in okt.nouns(text) if word not in stop_words]        

        # 빈도 계산
        data = Counter(words).most_common(20)
        
    # 리뷰 텍스트에는 어떤 단어 조합이 가장 많이 나왔을까?
    # 리뷰 텍스트에서 가장 자주 등장한 단어 조합 추출
    elif analysis_type == 'frequent_words_mix':
        reviews = Review.objects.filter(concert_id=concert_id).values_list('description', flat=True)
        
        if not reviews:
            data = []
        else:
            # 리뷰 데이터를 DataFrame으로 변환
            df = pd.DataFrame(list(reviews), columns=['CONTENT'])

            # 불용어 설정
            stop_words = ['것', '정말', '노', '수', '이', '더', '보고', '진짜', '또', '그', 
              '꼭', '테일러', '뮤지컬', '좀', '조금', '볼', '말', '은', '는', 
              '이런', '그런', '저런', '그리고', '그러나', '그래서', '하지만', '그리고', 
              '게다가', '다시', '계속', '정말', '너무', '많이', '많은', '모든', '합니다', 
              '있어요', '없어요', '같아요', '보고', '봤습니다', '있습니다', '그렇죠', '맞아요', 
              '아니요', '그래요', '배우', '스토리', '내용', '연기', '무대', '공연', '관람', 
              '좋아요', '별점', '후기', '리뷰', '추천', '비추천',
            ]

            # CountVectorizer 설정
            cvect = CountVectorizer(
                ngram_range=(3, 6), 
                min_df=2, 
                max_df=0.8, 
                max_features=30, 
                stop_words=stop_words
            )
            X = cvect.fit_transform(df['CONTENT'])

            # 결과를 DataFrame으로 변환
            dtm = pd.DataFrame(X.toarray(), columns=cvect.get_feature_names_out())
            dtm_sum = dtm.sum().sort_values(ascending=False)

            # 데이터를 리스트 형태로 변환
            data = list(dtm_sum.items())
            
    # 상대적 중요도를 반영하여 단어를 조합하면 어떻게 될까?
    # 단순 빈도 기반이 아닌 상대적 중요도를 반영하여 단어 조합을 분석.
    elif analysis_type == 'frequent_words_important':
        reviews = Review.objects.filter(concert_id=concert_id).values_list('description', flat=True)
        
        if not reviews:
            data = []
        else:
            # 리뷰 데이터를 DataFrame으로 변환
            df = pd.DataFrame(list(reviews), columns=['CONTENT'])

            # 불용어 설정
            stop_words = ['것', '정말', '노', '수', '이', '더', '보고', '진짜', '또', '그', 
              '꼭', '테일러', '뮤지컬', '좀', '조금', '볼', '말', '은', '는', 
              '이런', '그런', '저런', '그리고', '그러나', '그래서', '하지만', '그리고', 
              '게다가', '다시', '계속', '정말', '너무', '많이', '많은', '모든', '합니다', 
              '있어요', '없어요', '같아요', '보고', '봤습니다', '있습니다', '그렇죠', '맞아요', 
              '아니요', '그래요', '배우', '스토리', '내용', '연기', '무대', '공연', '관람', 
              '좋아요', '별점', '후기', '리뷰', '추천', '비추천',
            ]

            # TF-IDF Vectorizer 설정
            tfidf = TfidfVectorizer(
                ngram_range=(3, 6),    # 3~6개의 단어 조합을 고려
                min_df=2,              # 최소 2번 이상 등장
                max_df=0.9,            # 전체 리뷰 중 90% 이하에서 등장
                max_features=30,       # 상위 50개의 중요 단어 조합만 선택
                stop_words=stop_words  # 불용어 제거
            )

            # TF-IDF 변환 수행
            X = tfidf.fit_transform(df['CONTENT'])

            # TF-IDF 결과를 DataFrame으로 변환
            tfidf_df = pd.DataFrame(X.toarray(), columns=tfidf.get_feature_names_out())

            # TF-IDF 값의 합계를 기준으로 단어 조합의 중요도를 계산
            tfidf_sum = tfidf_df.sum().sort_values(ascending=False)

            # 데이터를 리스트 형태로 변환 (단어 조합, 중요도)
            data = list(tfidf_sum.items())

    # 비슷한 리뷰 내용은 어떤 게 있을까?
    # 리뷰 내용의 유사도를 계산하여 클러스터링으로 그룹화.
    elif analysis_type == 'similar_reviews':
        reviews = Review.objects.filter(concert_id=concert_id).values('nickname', 'description')

        if not reviews:
            data = {}
        else:
            # 리뷰 데이터를 DataFrame으로 변환
            df = pd.DataFrame(list(reviews))

            # 텍스트 정제 함수 정의
            def clean_text(text):
                # 한글, 영문, 숫자만 남기고 나머지는 제거
                cleaned_text = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', text)
                # 여러 개의 공백을 하나의 공백으로 변경
                cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
                # 앞뒤 공백 제거
                cleaned_text = cleaned_text.strip()
                return cleaned_text

            # 모든 리뷰에 대해 정제 작업 수행
            df['CLEANED_CONTENT'] = df['description'].apply(clean_text)

            # TF-IDF 벡터화
            tfidf_vectorizer = TfidfVectorizer()
            review_dtm = tfidf_vectorizer.fit_transform(df['CLEANED_CONTENT'])

            # K-Means 클러스터링
            kmeans = KMeans(n_clusters=10, n_init='auto', random_state=42)
            kmeans.fit(review_dtm)
            clusters = kmeans.labels_

            # 클러스터 결과를 DataFrame에 추가
            df['CLUSTER'] = clusters

            # 클러스터별 닉네임과 리뷰 내용을 그룹화
            data = df.groupby('CLUSTER').apply(
                lambda group: [{"nickname": row['nickname'], "content": row['CLEANED_CONTENT']} for _, row in group.iterrows()]
            ).to_dict()

    # 조회수가 높은 리뷰들은 어떤 내용일까?
    elif analysis_type == 'top_view_count_reviews':
        data = Review.objects.filter(concert_id=concert_id).order_by('-view_count')
    
    # 평점이 3점 이하인 리뷰를 작성한 관객은 어떤 리뷰를 달았을까?
    elif analysis_type == 'low_star_rating_reviews':
        # 평점 3점 이하인 리뷰 필터링
        reviews = Review.objects.filter(concert_id=concert_id, star_rating__lte=3).order_by('star_rating')
        # "뮤지컬 〈테일러〉"가 포함되지 않은 리뷰만 선택
        data = [review for review in reviews if "뮤지컬 〈테일러〉" not in review.description]

        
    else:  # 잘못된 분석 유형 처리
        data = []

    return render(request, 'review/analysis.html', {'data': data, 'analysis_type': analysis_type})

# 모든 공연의 리뷰
def analyze_all_reviews(request):
    # 기간 필터링
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # 리뷰 데이터 필터링
    reviews = Review.objects.all().select_related('concert')
    if start_date and end_date:
        reviews = reviews.filter(date__range=[start_date, end_date])

    # 공연별 요약
    concert_summary = (
        reviews
        .values("concert__name", "concert__place")
        .annotate(
            average_rating=Avg("star_rating"),
            total_reviews=Count("id")
        )
        .order_by("concert__name")
    )

    # 공연별 날짜별 리뷰 수 집계
    concert_date_summary = {
        concert["concert__name"]: (
            reviews
            .filter(concert__name=concert["concert__name"])
            .values("date")
            .annotate(reviews_count=Count("id"))
            .order_by("-date")
        )
        for concert in concert_summary
    }

    # 공연별 날짜별 평균 평점 집계
    concert_date_rating_summary = {
        concert["concert__name"]: (
            reviews
            .filter(concert__name=concert["concert__name"])
            .values("date")
            .annotate(average_rating=Avg("star_rating"))
            .order_by("-date")
        )
        for concert in concert_summary
    }

    # 공연의 닉네임과 관련 정보 가져오기
    nicknames = (
        reviews
        .values('nickname', 'concert__name')
        .annotate(first_date=Min('date'))
        .distinct()
    )

    # 닉네임별로 관련 공연과 최초 작성일을 그룹화
    nickname_to_concerts = defaultdict(list)
    for entry in nicknames:
        nickname_to_concerts[entry['nickname']].append({
            'concert__name': entry['concert__name'],
            'first_date': entry['first_date'].strftime("%Y-%m-%d")
        })

    # 두 개 이상의 공연에 등장한 닉네임 찾기 및 관련 공연 수로 정렬
    common_nicknames = {
        nickname: sorted(concerts, key=lambda x: x['first_date'])
        for nickname, concerts in nickname_to_concerts.items()
        if len(concerts) > 1
    }

    sorted_common_nicknames = dict(
        sorted(common_nicknames.items(), key=lambda item: len(item[1]), reverse=True)
    )
    
    # 공연별 닉네임 집계
    concerts_with_nicknames = reviews.values('concert__name', 'nickname').distinct()
    concert_to_nicknames = defaultdict(set)
    for entry in concerts_with_nicknames:
        concert_to_nicknames[entry['concert__name']].add(entry['nickname'])

    # 모든 공연 리스트
    concerts = list(concert_to_nicknames.keys())

    # 조합별 닉네임 계산
    combination_counts = {}
    for r in range(1, len(concerts) + 1):
        for combo in combinations(concerts, r):
            # 조합에 포함된 공연들의 닉네임 교집합 계산
            intersected_nicknames = set.intersection(*(concert_to_nicknames[c] for c in combo))
            combination_counts[", ".join(combo)] = len(intersected_nicknames)
    
    # 전체 리뷰 데이터 정리
    review_data = [
        {
            "공연명": review.concert.name,
            "장소": review.concert.place,
            "작성자": review.nickname,
            "작성일": review.date,
            "평점": review.star_rating,
            "제목": review.title,
            "내용": review.description,
            "조회수": review.view_count,
            "좋아요": review.like_count,
        }
        for review in reviews
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