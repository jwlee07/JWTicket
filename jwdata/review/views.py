from django.shortcuts import render
from django.db.models import F, Count, Max, Min, Avg
from django.db.models.functions import Length
from django.db.models.functions import TruncHour
from django.db.models import Value
from django.db.models.functions import Concat, Cast
from django.db.models import CharField
from .models import Concert, Review, Seat

from datetime import datetime
import time
import pytz

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
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.cluster import KMeans

# ==================================================================
# 텍스트 전처리 함수
# ==================================================================
def clean_text(text):
    """
    리뷰 텍스트를 정제하는 함수.
    - 한글, 영문, 숫자만 남기고 나머지 제거
    - 다중 공백을 하나의 공백으로 치환
    - 앞뒤 공백 제거
    """
    cleaned = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', text)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned
# ==================================================================
# DB 보조 함수
# ==================================================================
from .sheets import (
    create_or_update_concert_in_sheet,
    create_review_in_sheet,
    create_seat_in_sheet,
    read_all_concerts_from_sheet,
    read_all_reviews_from_sheet,
    read_all_seats_from_sheet,
)

def sync_concert_sheet_to_db():
    """
    (예시) 시트에서 모든 Concert를 읽어, DB에 없는 레코드만 저장.
    """
    rows = read_all_concerts_from_sheet()
    for row in rows:
        pk = row.get("id")

        if not pk:
            continue

        if Concert.objects.filter(pk=pk).exists():
            continue

        Concert.objects.create(
            pk=pk,
            name=row.get("name") or "",
            place=row.get("place") or "",
            start_date=row.get("start_date") or None,
            end_date=row.get("end_date") or None,
            duration_minutes=row.get("duration_minutes") or None,
        )

def sync_reviews_sheet_to_db():
    """
    시트에서 모든 리뷰를 읽어, DB에 없는 레코드만 저장.
    """
    rows = read_all_reviews_from_sheet()
    for row in rows:

        pk = row.get("id")

        if not pk:
            continue

        if Review.objects.filter(pk=pk).exists():
            continue

        concert_id = row.get("concert_id")

        if not concert_id:
            continue

        Review.objects.create(
            pk=pk,
            concert_id=concert_id,
            nickname=row.get("nickname") or "",
            date=row.get("date") or None,
            view_count=row.get("view_count") or 0,
            like_count=row.get("like_count") or 0,
            title=row.get("title") or "",
            description=row.get("description") or "",
            star_rating=row.get("star_rating") or None,
        )

def sync_seats_sheet_to_db():
    """
    시트에서 모든 Seat를 읽어, DB에 없는 레코드만 저장.
    """
    rows = read_all_seats_from_sheet()
    for row in rows:

        pk = row.get("id")
        if not pk:
            continue

        if Seat.objects.filter(pk=pk).exists():
            continue

        concert_id = row.get("concert_id")

        if not concert_id:
            continue

        from datetime import time
        round_time_str = row.get("round_time") or ""

        try:
            hh, mm, ss = round_time_str.split(':')
            round_time_obj = time(int(hh), int(mm), int(ss))
        except:
            round_time_obj = None

        Seat.objects.create(
            pk=pk,
            concert_id=concert_id,
            year=row.get("year") or 0,
            month=row.get("month") or 0,
            day_num=row.get("day_num") or 0,
            day_str=row.get("day_str") or "",
            round_name=row.get("round_name") or "",
            round_time=round_time_obj,
            seat_class=row.get("seat_class") or "",
            seat_count=row.get("seat_count") or 0,
            actors=row.get("actors") or "",
            created_at=row.get("created_at") or None,
        )

# ==================================================================
# 크롤링 보조 함수
# ==================================================================
def crawl_concert_info(driver):
    """
    공연 정보를 크롤링한 뒤,
    1) DB에 (name, place, start_date) 중복 확인하여 없으면 생성
    2) 시트에 해당 id가 있으면 업데이트, 없으면 새로 append
    (즉, 같은 id로 중복 행이 추가되지 않도록 수정)
    """
    # 공연 정보 파싱
    name = driver.find_element(By.XPATH, '//*[@id="container"]/div[2]/div[1]/div[2]/div[1]/div/div[1]/h2').text
    place = driver.find_element(By.XPATH, '//*[@id="container"]/div[2]/div[1]/div[2]/div[1]/div/div[2]/ul/li[1]/div/div/a').text
    date_text = driver.find_element(By.XPATH, '//*[@id="container"]/div[2]/div[1]/div[2]/div[1]/div/div[2]/ul/li[2]/div/p').text
    duration_text = driver.find_element(By.XPATH, '//*[@id="container"]/div[2]/div[1]/div[2]/div[1]/div/div[2]/ul/li[3]/div/p').text.replace('분', '').strip()

    print(f"[공연 정보] 공연명: {name}, 장소: {place}, 기간: {date_text}, 시간: {duration_text}")

    # 날짜 처리
    try:
        if '~' in date_text:
            start_str, end_str = date_text.split('~')
            start_date = datetime.strptime(start_str.strip(), "%Y.%m.%d").date()
            end_date = datetime.strptime(end_str.strip(), "%Y.%m.%d").date()
        else:
            start_date = datetime.strptime(date_text.strip(), "%Y.%m.%d").date()
            end_date = start_date
    except ValueError:
        start_date = None
        end_date = None

    print(f"[날짜 처리] 시작일: {start_date}, 종료일: {end_date}")

    # DB 저장 (중복 체크)
    concert_qs = Concert.objects.filter(name=name, place=place, start_date=start_date)

    if concert_qs.exists():
        concert = concert_qs.first()
        print(f"[DB] 이미 존재하는 Concert: {concert}")
    else:
        concert = Concert.objects.create(
            name=name,
            place=place,
            start_date=start_date,
            end_date=end_date,
            duration_minutes=int(duration_text) if duration_text.isdigit() else None
        )
        print(f"[DB 저장] 새 Concert: {concert}")

    # 구글 시트에 반영
    create_or_update_concert_in_sheet(concert)
    print(f"[시트 동기화] Concert(pk={concert.pk}, name={concert.name}) 완료")

    return concert

def crawl_concert_reviews(driver, concert):
    """
    1) 리뷰 목록 크롤링
    2) DB에 없는 리뷰만 저장
    3) 시트에 없는 리뷰만 저장
    4) 시트 전체 → DB 역동기화
    """

    # 관람후기 탭 버튼 클릭
    review_button = driver.find_element(By.XPATH, '//*[@id="productMainBody"]/nav/ul/li[4]/a')
    driver.execute_script("arguments[0].click();", review_button)
    time.sleep(2)

    # 관람후기 총 개수 파악
    review_total_count = 0
    try:
        review_total_count_element = driver.find_element(By.XPATH, '//*[@id="prdReview"]/div/div[3]/div[1]/div[1]/div[1]/strong/span')
        review_total_count = int(review_total_count_element.text)
    except NoSuchElementException:
        try:
            review_total_count_element = driver.find_element(By.XPATH, '//*[@id="prdReview"]/div/div[4]/div[1]/div[1]/div[1]/strong/span')
            review_total_count = int(review_total_count_element.text)
        except NoSuchElementException:
            print("[리뷰] 총 개수를 찾을 수 없습니다.")

    review_num_pages = (review_total_count + 14) // 15

    for page in range(1, review_num_pages + 1):
        print(f"[리뷰] {page}/{review_num_pages} 페이지 처리 중")

        review_elements = driver.find_elements(By.XPATH, '//ul[@class="bbsList reviewList"]/li[@class="bbsItem"]')

        for rev_el in review_elements:
            try:
                nickname = rev_el.find_element(By.CLASS_NAME, 'name').text.strip()
                date_raw = rev_el.find_element(By.XPATH, './/li[@class="bbsItemInfoList"][2]').text.strip()
                view_count = int(''.join(filter(str.isdigit, rev_el.find_element(By.XPATH, './/li[@class="bbsItemInfoList"][3]').text)))
                like_count = int(''.join(filter(str.isdigit, rev_el.find_element(By.XPATH, './/li[@class="bbsItemInfoList"][4]').text)))
                title = rev_el.find_element(By.CLASS_NAME, 'bbsTitleText').text.strip()
                description = rev_el.find_element(By.CLASS_NAME, 'bbsText').text.strip()
                star_rating = float(rev_el.find_element(By.CLASS_NAME, 'prdStarIcon').get_attribute('data-star'))
                date = datetime.strptime(date_raw, "%Y.%m.%d").strftime("%Y-%m-%d")

                # DB 중복 체크 (concert, nickname, date, title 기준)
                existed = Review.objects.filter(
                    concert=concert,
                    nickname=nickname,
                    date=date,
                    title=title
                ).exists()
                
                if not existed:
                    # DB 저장
                    new_review = Review.objects.create(
                        concert=concert,
                        nickname=nickname,
                        date=date,
                        view_count=view_count,
                        like_count=like_count,
                        title=title,
                        description=description,
                        star_rating=star_rating
                    )
                    print(f"[리뷰][DB 저장] Review: {new_review}")

                    # 시트에도 없으면 저장
                    create_review_in_sheet(new_review)
                    print(f"[리뷰][시트 저장] Review: {new_review}")

            except Exception as e:
                print(f"[리뷰] 처리 중 오류 발생: {e}")

        # 페이지 이동
        if page < review_num_pages:
            try:
                if page % 10 == 0:
                    group_index = page // 10
                    if group_index > 2:
                        group_index = 2
                    next_group_button = None
                    try:
                        next_group_button = driver.find_element(By.XPATH, f'//*[@id="prdReview"]/div/div[3]/div[2]/a[{group_index}]')
                    except NoSuchElementException:
                        try:
                            next_group_button = driver.find_element(By.XPATH, f'//*[@id="prdReview"]/div/div[4]/div[2]/a[{group_index}]')
                        except NoSuchElementException:
                            print("[리뷰] 다음 그룹 버튼 찾을 수 없음")
                            break
                    if next_group_button:
                        driver.execute_script("arguments[0].click();", next_group_button)
                        time.sleep(2)
                else:
                    next_page_text = str(page + 1)
                    next_page_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.LINK_TEXT, next_page_text))
                    )
                    driver.execute_script("arguments[0].click();", next_page_button)
                    time.sleep(2)
            except Exception as e:
                print(f"[리뷰] 페이지 이동 오류: {e}")
                break

    sync_reviews_sheet_to_db()
    print("[리뷰] 시트 전체 → DB 동기화 완료")

def crawl_concert_seats(driver, concert):
    """
    1) 좌석 정보 크롤링
    2) DB에 없는 Seat만 저장
    3) 시트에 없는 Seat만 저장
    4) 마지막에 시트 전체 → DB 동기화
    """

    while True:
        current_month = driver.find_element(By.XPATH, '//li[@data-view="month current"]').text
        print(f"[좌석] 현재 달: {current_month}")

        days = driver.find_elements(By.XPATH, '//ul[@data-view="days"]/li[not(contains(@class, "disabled")) and not(contains(@class, "muted"))]')
        print(f"[좌석] 활성화된 날짜 수: {len(days)}")

        for day in days:
            day_num = day.text

            try:
                WebDriverWait(driver, 10).until(EC.element_to_be_clickable(day))
                driver.execute_script("arguments[0].click();", day)
                print(f"[좌석] 날짜 클릭: {current_month}-{day_num}")
            except Exception as e:
                print(f"[좌석] 날짜 클릭 실패: {e}")
                continue

            time.sleep(2)

            # 회차별
            rounds = driver.find_elements(By.CLASS_NAME, 'timeTableLabel')
            for round_element in rounds:
                round_text = round_element.get_attribute('data-text').split()
                round_name = round_text[0]
                round_time_str = round_text[1] if len(round_text) > 1 else ""

                try:
                    driver.execute_script("arguments[0].click();", round_element)
                except Exception as e:
                    print(f"[좌석] 회차 클릭 실패: {e}")
                    continue
                time.sleep(2)

                seats = driver.find_elements(By.CLASS_NAME, 'seatTableItem')
                for seat_el in seats:
                    seat_class = seat_el.find_element(By.CLASS_NAME, 'seatTableName').text
                    count_text = seat_el.find_element(By.CLASS_NAME, 'seatTableStatus').text
                    try:
                        seat_count = int(''.join(filter(str.isdigit, count_text)))
                    except ValueError:
                        seat_count = 0

                    # 배우 정보
                    try:
                        actors_element = driver.find_element(By.XPATH, '//*[@id="productSide"]/div/div[1]/div[3]/div[2]/div/p')
                        actors = actors_element.text
                    except NoSuchElementException:
                        actors = ""

                    # 날짜 정보 처리
                    date_parts = current_month.split('.')  # 예: ["2025","01"]
                    year = int(date_parts[0])
                    month = int(date_parts[1])
                    day_num_int = int(day_num)

                    # 요일 계산
                    KOREAN_DAYS = ['월', '화', '수', '목', '금', '토', '일']
                    def get_korean_day_of_week(y, m, d):
                        try:
                            dt_obj = datetime(y, m, d)
                            return KOREAN_DAYS[dt_obj.weekday()]
                        except:
                            return ''
                    day_str = get_korean_day_of_week(year, month, day_num_int)

                    # DB 중복 체크
                    seat_existed = Seat.objects.filter(
                        concert=concert,
                        year=year,
                        month=month,
                        day_num=day_num_int,
                        round_name=round_name,
                        seat_class=seat_class
                    ).exists()

                    if not seat_existed:
                        new_seat = Seat.objects.create(
                            concert=concert,
                            year=year,
                            month=month,
                            day_num=day_num_int,
                            day_str=day_str,
                            round_name=round_name,
                            round_time=round_time_str,
                            seat_class=seat_class,
                            seat_count=seat_count,
                            actors=actors
                        )
                        print(f"[좌석][DB 저장] {new_seat}")

                        # 시트에 없으면 저장
                        create_seat_in_sheet(new_seat)
                        print(f"[좌석][시트 저장] {new_seat}")

            # 날짜 처리 후 뒤로가기
            driver.back()
            time.sleep(2)

        # 다음 달 버튼
        try:
            next_month_btn = driver.find_element(By.XPATH, '//li[@data-view="month next" and not(contains(@class, "disabled"))]')
            driver.execute_script("arguments[0].click();", next_month_btn)
            time.sleep(2)
        except NoSuchElementException:
            print("[좌석] 더 이상 다음 달 없음 -> 종료")
            break

    # 마지막에 시트 전체 → DB 동기화
    sync_seats_sheet_to_db()
    print("[좌석] 시트 전체 → DB 동기화 완료")

# ==================================================================
# 뷰 함수들
# ==================================================================
def search_and_crawl(request):
    """
    사용자가 입력한 검색어로 인터파크에서 공연 정보를 검색 후,
    공연 정보/리뷰/좌석 데이터를 크롤링하는 뷰.
    
    GET 파라미터:
    - active_concert_id: 현재 선택된 공연 ID (optional)
    
    POST 파라미터:
    - query: 검색어
    - search_type: 'review' 또는 'seat' (기본 'review')
      * 'review' 선택 시 공연 정보 + 리뷰 크롤링
      * 'seat' 선택 시 공연 정보 + 좌석 정보 크롤링
    
    최종적으로 'review/index.html' 템플릿 렌더링
    """
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

                # 첫 번째 검색 결과 클릭 (음악/콘서트 검색 결과 영역 중 하나)
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

    return render(request, 'review/index.html', { 'concerts': concerts, 'active_concert_id': active_concert_id, })

def analyze_reviews(request, concert_id, analysis_type):
    """
    특정 공연(concert_id)의 리뷰를 다양한 관점에서 분석하는 뷰.
    
    analysis_type에 따라 다른 분석 로직 수행:
    - long_reviews: 길이가 긴 리뷰
    - frequent_reviewers: 여러 번 리뷰를 남긴 리뷰어
    - frequent_words: 단일 단어 빈도 분석
    - frequent_words_mix: 단어 조합 빈도 분석
    - frequent_words_important: TF-IDF 기반 중요도 높은 단어/단어 조합
    - similar_reviews: KMeans 클러스터링으로 유사한 리뷰 그룹 분석
    - top_view_count_reviews: 조회수가 높은 리뷰
    - low_star_rating_reviews: 별점 3점 이하 리뷰
    """
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

def analyze_all_reviews(request):
    """
    모든 공연에 대한 리뷰 종합 분석 뷰.
    
    - 기간 필터링(start_date, end_date)
    - 공연별 요약 정보(평균 평점, 리뷰 수)
    - 날짜별 리뷰 수, 날짜별 평균 평점
    - 닉네임별 관람 패턴(여러 공연 관람한 닉네임 등)
    - 리뷰 상세 데이터
    
    최종적으로 'review/all_reviews.html' 템플릿에 렌더링.
    """
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

def analyze_all_seats(request):
    """
    모든 공연에 대한 좌석 데이터 종합 분석 뷰.
    - 공연명으로 필터링 가능
    - 해당 좌석 정보를 'review/all_seats.html'에 렌더링
    """
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
    all_concerts = Concert.objects.values_list('name', flat=True).distinct()

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

def analyze_all_pattern(request):
    """
    모든 공연에 대한 관람 패턴 분석 뷰.
    
    - 공연 조합별 관객 분포 (관람 공연 수가 높은 순)
    - 닉네임 별 관람 패턴 (관람 공연 수가 많은 순)
    
    최종적으로 'review/all_pattern.html' 템플릿에 렌더링.
    """
    # 모든 리뷰 데이터 가져오기
    reviews = Review.objects.all().select_related('concert')
    
    # 닉네임별 관람 공연 정보 수집
    nicknames = reviews.values('nickname', 'concert__name').annotate(first_date=Min('date')).distinct()
    nickname_to_concerts = defaultdict(set)
    for n in nicknames:
        nickname_to_concerts[n['nickname']].add(n['concert__name'])
    
    # 닉네임 별 관람 패턴 (두 개 이상의 공연을 관람한 경우)
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
            # 오름차순으로 날짜 정렬
            concert_dates_sorted = sorted(concert_dates, key=lambda x: x['date'])
            common_nicknames[nn] = concert_dates_sorted
    
    # 닉네임 별 관람 공연 수를 기준으로 정렬 (내림차순)
    sorted_common_nicknames = dict(sorted(common_nicknames.items(), key=lambda item: len(item[1]), reverse=True))
    
    # 공연 조합별 관객 분포 계산
    combination_counts = defaultdict(int)
    
    for concerts in nickname_to_concerts.values():
        for r in range(1, len(concerts) + 1):
            for combo in combinations(sorted(concerts), r):
                combination_key = ", ".join(combo)
                combination_counts[combination_key] += 1
    
    # 관람 공연 수가 높은 순으로 정렬 (내림차순)
    sorted_combinations = sorted(combination_counts.items(), key=lambda x: x[1], reverse=True)
    
    # 상위 10개 조합만 선택 (필요에 따라 조정 가능)
    top_combination_counts = dict(sorted_combinations[:10])
    
    return render(request, 'review/all_pattern.html', {
        'common_nicknames': sorted_common_nicknames,
        'combination_counts': top_combination_counts,
    })