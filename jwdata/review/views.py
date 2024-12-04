from django.shortcuts import render
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from .models import Concert, Review
from datetime import datetime
import time


def search_and_crawl(request):
    data = []

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
                review_total_count = int(driver.find_element(By.XPATH, '//*[@id="prdReview"]/div/div[4]/div[1]/div[1]/div[1]/strong/span').text)
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
                                next_group_button = driver.find_element(By.XPATH, '//*[@id="prdReview"]/div/div[4]/div[2]/a')
                                driver.execute_script("arguments[0].click();", next_group_button)
                            else:
                                next_page_button = driver.find_element(By.LINK_TEXT, str(review_page + 1))
                                driver.execute_script("arguments[0].click();", next_page_button)
                            time.sleep(2)
                        except NoSuchElementException:
                            print(f"페이지 {review_page + 1}로 이동 실패.")
                            break
                        print(f"----------{review_page}/{review_total_count}----------")


            finally:
                driver.quit()

    return render(request, 'review/index.html', {'data': data})
