from datetime import datetime
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from .models import Concert
from .views import crawl_concert_info, crawl_concert_reviews, crawl_concert_seats

def get_chrome_driver():
    """
    Headless Chrome 드라이버를 반환하는 함수.
    크론 실행 환경(백그라운드)에서 UI 없는 크롤링을 가능하게 함.
    """
    # chrome_options = Options()
    # chrome_options.add_argument('--headless')         # 화면 없이 동작
    # chrome_options.add_argument('--no-sandbox')        # 리눅스 환경에서 권한 문제 방지
    # chrome_options.add_argument('--disable-dev-shm-usage') # /dev/shm 사용 비활성화(메모리 부족 문제 회피)
    # chrome_options.add_argument('--disable-gpu')       # GPU 비활성화 (일부 환경에서 필요)
    # chrome_options.add_argument('--window-size=1920,1080') # 넉넉한 가상 화면 크기 지정

    # return webdriver.Chrome(options=chrome_options)
    return webdriver.Chrome()

def log(message):
    """
    메시지를 콘솔 출력하고 /tmp/cron_test.log 파일에도 기록하는 함수.
    """
    print(message)
    with open('/tmp/cron_test.log', 'a') as f:
        f.write(f"{message} (at {datetime.now()})\n")

def crawl_all_concerts_reviews():
    """
    매일 새벽 3시에 실행:
    DB에 있는 모든 공연(Concert)을 대상으로 리뷰 크롤링을 수행.
    """
    log("[crawl_all_concerts_reviews] 시작")
    driver = get_chrome_driver()
    try:
        concerts = Concert.objects.all()
        log(f"[crawl_all_concerts_reviews] 총 {concerts.count()}개의 공연에 대해 리뷰 크롤링을 시도합니다.")

        for concert in concerts:
            concert_name = concert.name.strip()
            if not concert_name:
                log("[WARN] 공연 이름이 비어있어 스킵합니다.")
                continue

            log(f"[INFO] 공연명: {concert_name}에 대한 리뷰 크롤링 시작")
            # 인터파크 메인 페이지 접근
            driver.get("https://tickets.interpark.com/")
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="__next"]/div/header/div[2]/div[1]/div/div[3]/div'))
            )
            time.sleep(2)

            # 검색 실행
            search_box = driver.find_element(By.XPATH, '//*[@id="__next"]/div/header/div[2]/div[1]/div/div[3]/div')
            search_box.click()
            time.sleep(2)

            active_input = driver.find_element(By.XPATH, '//*[@id="__next"]/div/header/div[2]/div[1]/div/div[3]/div/input')
            active_input.send_keys(concert_name)
            time.sleep(2)
            active_input.send_keys(Keys.RETURN)
            log(f"[DEBUG] '{concert_name}' 검색 완료, 검색 결과 페이지 로딩 중...")

            # 첫 번째 검색 결과 클릭
            try:
                element = WebDriverWait(driver, 10).until(
                    EC.any_of(
                        EC.element_to_be_clickable((By.XPATH, '//*[@id="contents"]/div/div/div[1]/div[2]/a[1]/ul')),
                        EC.element_to_be_clickable((By.XPATH, '//*[@id="contents"]/div/div/div[2]/div[2]/a[1]/ul'))
                    )
                )
                element.click()
                time.sleep(2)
                log(f"[DEBUG] '{concert_name}' 검색 결과 첫 번째 항목 클릭 성공")
            except Exception as e:
                log(f"[ERROR] [{concert_name}] 검색 결과 클릭 실패: {e}")
                continue

            # 새 창으로 전환(인터파크 상세 페이지)
            if len(driver.window_handles) > 1:
                driver.switch_to.window(driver.window_handles[1])
                time.sleep(2)
                log("[DEBUG] 상세 페이지로 전환")

            # 예매 안내 팝업 닫기
            try:
                popup_close_button = driver.find_element(By.XPATH, '//*[@id="popup-prdGuide"]/div/div[3]/button')
                driver.execute_script("arguments[0].click();", popup_close_button)
                time.sleep(2)
                log("[DEBUG] 팝업 닫기 성공")
            except NoSuchElementException:
                log(f"[INFO] [{concert_name}] 팝업 닫기 버튼 없음, 무시")

            # 공연 정보 크롤링
            crawled_concert = crawl_concert_info(driver)
            log(f"[INFO] 공연 정보 크롤링 완료: {crawled_concert}")

            # 리뷰 크롤링
            crawl_concert_reviews(driver, crawled_concert)
            log("[INFO] 리뷰 크롤링 완료")

            # 상세 페이지 닫기
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
            time.sleep(2)
            log("[DEBUG] 상세 페이지 닫기 및 메인 창 전환 완료")

    finally:
        driver.quit()
        log("[crawl_all_concerts_reviews] 종료")


def crawl_all_concerts_seats():
    """
    매일 00시,06시,12시,18시에 실행:
    DB에 있는 모든 공연(Concert)에 대해 좌석 정보 크롤링 수행.
    """
    log("[crawl_all_concerts_seats] 시작")
    driver = get_chrome_driver()
    try:
        concerts = Concert.objects.all()
        log(f"[crawl_all_concerts_seats] 총 {concerts.count()}개의 공연에 대해 좌석 크롤링을 시도합니다.")

        for concert in concerts:
            concert_name = concert.name.strip()
            if not concert_name:
                log("[WARN] 공연 이름이 비어있어 스킵합니다.")
                continue

            log(f"[INFO] 공연명: {concert_name}에 대한 좌석 크롤링 시작")
            # 인터파크 메인 페이지 접근
            driver.get("https://tickets.interpark.com/")
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="__next"]/div/header/div[2]/div[1]/div/div[3]/div'))
            )
            time.sleep(2)

            # 검색 실행
            search_box = driver.find_element(By.XPATH, '//*[@id="__next"]/div/header/div[2]/div[1]/div/div[3]/div')
            search_box.click()
            time.sleep(2)

            active_input = driver.find_element(By.XPATH, '//*[@id="__next"]/div/header/div[2]/div[1]/div/div[3]/div/input')
            active_input.send_keys(concert_name)
            time.sleep(2)
            active_input.send_keys(Keys.RETURN)
            log(f"[DEBUG] '{concert_name}' 검색 완료, 검색 결과 페이지 로딩 중...")

            # 첫 번째 검색 결과 클릭
            try:
                element = WebDriverWait(driver, 10).until(
                    EC.any_of(
                        EC.element_to_be_clickable((By.XPATH, '//*[@id="contents"]/div/div/div[1]/div[2]/a[1]/ul')),
                        EC.element_to_be_clickable((By.XPATH, '//*[@id="contents"]/div/div/div[2]/div[2]/a[1]/ul'))
                    )
                )
                element.click()
                time.sleep(2)
                log(f"[DEBUG] '{concert_name}' 검색 결과 첫 번째 항목 클릭 성공")
            except Exception as e:
                log(f"[ERROR] [{concert_name}] 검색 결과 클릭 실패: {e}")
                continue

            # 새 창으로 전환(인터파크 상세 페이지)
            if len(driver.window_handles) > 1:
                driver.switch_to.window(driver.window_handles[1])
                time.sleep(2)
                log("[DEBUG] 상세 페이지로 전환")

            # 예매 안내 팝업 닫기
            try:
                popup_close_button = driver.find_element(By.XPATH, '//*[@id="popup-prdGuide"]/div/div[3]/button')
                driver.execute_script("arguments[0].click();", popup_close_button)
                time.sleep(2)
                log("[DEBUG] 팝업 닫기 성공")
            except NoSuchElementException:
                log(f"[INFO] [{concert_name}] 팝업 닫기 버튼 없음, 무시")

            # 공연 정보 크롤링
            crawled_concert = crawl_concert_info(driver)
            log(f"[INFO] 공연 정보 크롤링 완료: {crawled_concert}")

            # 좌석 크롤링
            crawl_concert_seats(driver, crawled_concert)
            log("[INFO] 좌석 크롤링 완료")

            # 상세 페이지 닫기
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
            time.sleep(2)
            log("[DEBUG] 상세 페이지 닫기 및 메인 창 전환 완료")

    finally:
        driver.quit()
        log("[crawl_all_concerts_seats] 종료")