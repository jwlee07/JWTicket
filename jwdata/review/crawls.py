from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

from datetime import datetime
import time

from .models import Concert, Review, Seat

from .sheets import (
    create_or_update_concert_in_sheet,
    create_or_update_review_in_sheet,
    create_or_update_seat_in_sheet,
    sync_concert_sheet_to_db,
    sync_reviews_sheet_to_db,
    sync_seats_sheet_to_db
)

def crawl_concert_info(driver):
    """
    1) DB에 (name, place, start_date) 없으면 Concert 생성
    2) create_or_update_concert_in_sheet(concert)로 시트에 반영
    3) 마지막에 sync_concert_sheet_to_db()로 시트→DB
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

    print(f"[공연 정보][날짜 처리] 시작일: {start_date}, 종료일: {end_date}")

    # DB 저장 (중복 체크)
    concert_qs = Concert.objects.filter(name=name, place=place, start_date=start_date)

    if concert_qs.exists():
        concert = concert_qs.first()
        print(f"[공연 정보][DB 저장] 기존 Concert: {concert}")
    else:
        concert = Concert.objects.create(
            name=name,
            place=place,
            start_date=start_date,
            end_date=end_date,
            duration_minutes=int(duration_text) if duration_text.isdigit() else None
        )
        print(f"[공연 정보][DB 저장] 새 Concert: {concert}")

    # 시트에 없으면 append / 있으면 update
    # create_or_update_concert_in_sheet(concert)

    # 시트 전체→DB (pk 기준으로 없는 것만 insert)
    # sync_concert_sheet_to_db()

    return concert

def crawl_concert_reviews(driver, concert):
    """
    1) 리뷰 크롤링
    2) DB에 중복 없으면 저장
    3) 시트에 없으면 append / 있으면 update
    4) 끝나면 sync_reviews_sheet_to_db()로 시트→DB 동기화
    """

    # 관람후기 탭 버튼 클릭
    concert_type = None

    if '뮤지컬' in concert.name:
        concert_type = '뮤지컬'
        review_button_xpath = '//*[@id="productMainBody"]/nav/ul/li[4]/a'
    elif '연극' in concert.name:
        concert_type = '연극'
        review_button_xpath = '//*[@id="productMainBody"]/nav/ul/li[4]/a'
    elif '콘서트' in concert.name:
        concert_type = '콘서트'
        review_button_xpath = '//*[@id="productMainBody"]/nav/ul/li[3]/a'
    else:
        concert_type = '기타'
        review_button_xpath = '//*[@id="productMainBody"]/nav/ul/li[4]/a'

    print(f"[리뷰] 공연 타입: {concert_type}")

    # 관람후기 탭 버튼 클릭
    try:
        review_button = driver.find_element(By.XPATH, review_button_xpath)
        driver.execute_script("arguments[0].click();", review_button)
        time.sleep(2)
        print(f"[리뷰] 관람후기 탭 클릭 성공: {concert_type}")
    except NoSuchElementException:
        print(f"[리뷰] 관람후기 탭 버튼 찾을 수 없음: {concert_type}")
        return
    except Exception as e:
        print(f"[리뷰] 관람후기 탭 클릭 중 오류 발생: {e}")
        return
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
                
                # DB 저장
                if not existed:
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

                    # create_or_update_review_in_sheet(new_review)
                    # print(f"[리뷰][시트 저장] Review: {new_review}")

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

    # sync_reviews_sheet_to_db()
    # print("[리뷰] 시트 전체 → DB 동기화 완료")

def crawl_concert_seats(driver, concert):
    """
    1) 좌석 정보 크롤링
    2) DB에 저장
    3) 시트에 저장
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

                    # 시트에 저장
                    # create_or_update_seat_in_sheet(new_seat)
                    # print(f"[좌석][시트 저장] {new_seat}")

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
    # sync_seats_sheet_to_db()
    # print("[좌석] 시트 전체 → DB 동기화 완료")