from django.shortcuts import render
from django.db.models import Count
from django.db.models.functions import Length
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from .models import Concert, Review
from datetime import datetime
import time
import re
from konlpy.tag import Okt
from collections import Counter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

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
        ).order_by('-content_length')[:10] 
    # 여러번 리뷰를 작성한 고객은 어떤 리뷰를 달았을까?        
    elif analysis_type == 'frequent_reviewers':
        frequent_reviewers = Review.objects.filter(concert_id=concert_id).values(
            'nickname'
        ).annotate(review_count=Count('id')).filter(review_count__gt=1).order_by('-review_count')

        data = []
        for reviewer in frequent_reviewers:
            reviews = Review.objects.filter(concert_id=concert_id, nickname=reviewer['nickname']).values(
                'nickname', 'description'
            )
            data.append({
                'nickname': reviewer['nickname'],
                'review_count': reviewer['review_count'],
                'reviews': reviews
            })
    # 리뷰 텍스트에는 어떤 단어가 가장 많이 나왔을까?
    elif analysis_type == 'frequent_words':
        reviews = Review.objects.filter(concert_id=concert_id).values_list('description', flat=True)
        text = ' '.join(reviews)
        words = re.findall(r'\w+', text.lower())
        data = Counter(words).most_common(20)
    # 비슷한 리뷰 내용은 어떤 게 있을까?
    elif analysis_type == 'similar_reviews':
        reviews = Review.objects.filter(concert_id=concert_id).values_list('description', flat=True)
        if len(reviews) < 2:
            data = []
        else:
            tfidf_vectorizer = TfidfVectorizer(stop_words='korean')
            tfidf_matrix = tfidf_vectorizer.fit_transform(reviews)
            similarity_matrix = cosine_similarity(tfidf_matrix, tfidf_matrix)
            data = [
                (reviews[i], reviews[j], similarity_matrix[i, j])
                for i in range(len(reviews)) for j in range(i + 1, len(reviews))
                if similarity_matrix[i, j] > 0.5
            ][:10]
    else:
        data = []

    return render(request, 'review/analysis.html', {'data': data, 'analysis_type': analysis_type})

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

    # 리뷰 텍스트에서 가장 많이 나온 단어를 추출
    elif analysis_type == 'frequent_words':
        reviews = Review.objects.filter(concert_id=concert_id).values_list('description', flat=True)
        text = ' '.join(reviews)
    
        # Okt를 사용하여 명사 추출
        okt = Okt()
        words = okt.nouns(text)
    
        # 빈도 계산
        data = Counter(words).most_common(20)

    # 비슷한 리뷰 내용은 어떤 게 있을까?
    elif analysis_type == 'similar_reviews':
        # 닉네임별 리뷰 수 계산
        frequent_reviewers = Review.objects.filter(concert_id=concert_id).values('nickname').annotate(review_count=Count('id')).filter(review_count__gt=1)
        nicknames = [reviewer['nickname'] for reviewer in frequent_reviewers]

        # 닉네임이 두 번 이상인 리뷰만 선택
        reviews_qs = Review.objects.filter(concert_id=concert_id, nickname__in=nicknames)
        reviews_list = list(reviews_qs.values('description', 'nickname'))

        if len(reviews_list) < 2:
            data = []
        else:
            # 리뷰 설명만 추출
            descriptions = [review['description'] for review in reviews_list]
            nicknames_list = [review['nickname'] for review in reviews_list]

            # 불용어 목록 정의
            korean_stop_words = [
                '이', '그', '저', '그리고', '하지만', '그러나', '그래서', '또한', '더구나', '게다가', '즉',
                '따라서', '결론적으로', '때문에', '만약', '이러한', '어떤', '어느', '어느정도', '조금', '아주',
                '너무', '잘', '정말', '좋은', '수', '것', '더', '진짜', '또', '보고', '극',
                '그', '봤습니다', '꼭', '을', '뮤지컬', '좀', '좋고', '같아요', '그래도', '하고', '많이', '볼', '한번',
                '근데', '생각보다', '있는', '공연', '다', '이야기', '어떻게', '함께', '계속', '다시', '많은',
                '짱', '다른', '읽고', '이렇게', '모든', '보러', '너무너무', '다들', '보면',
                '긴긴밤', '테일러', '본', '배우들의', '공연을', '건', '하는', '조금', '무대', '극이', '한', '번',
                '느낌이', '배우', '있어요', '합니다', '배우님들', '하지만'
            ]

            # TF-IDF 벡터화
            tfidf_vectorizer = TfidfVectorizer(stop_words=korean_stop_words)
            tfidf_matrix = tfidf_vectorizer.fit_transform(descriptions)
            similarity_matrix = cosine_similarity(tfidf_matrix, tfidf_matrix)

            # 유사한 리뷰 페어 추출 (닉네임 중복 제거)
            seen_nicknames = set()
            pairs = []
            for i in range(len(reviews_list)):
                for j in range(i + 1, len(reviews_list)):
                    if (
                        similarity_matrix[i, j] > 0.5 and 
                        similarity_matrix[i, j] < 0.9 and 
                        nicknames_list[i] not in seen_nicknames and
                        nicknames_list[j] not in seen_nicknames
                    ):
                        pairs.append((reviews_list[i], reviews_list[j], similarity_matrix[i, j]))
                        seen_nicknames.add(nicknames_list[i])
                        seen_nicknames.add(nicknames_list[j])

            # 유사도 순으로 정렬
            data = sorted(pairs, key=lambda x: x[2], reverse=True)

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