from django.shortcuts import render
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from .models import Concert
from datetime import datetime  # 날짜 변환용 라이브러리
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
                popup_close_button = driver.find_element(By.XPATH, '//*[@id="popup-prdGuide"]/div/div[3]/button')
                driver.execute_script("arguments[0].click();", popup_close_button)
                time.sleep(2)
                
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
                if not Concert.objects.filter(name=name, start_date=start_date, end_date=end_date).exists():
                    concert = Concert.objects.create(
                        name=name,
                        place=place,
                        start_date=start_date,
                        end_date=end_date,
                        duration_minutes=int(duration_minutes),
                    )
                    print(f"공연 정보 저장 완료: {concert}")
                time.sleep(2)
                
                # 관람후기 버튼 클릭
                review_category_button = driver.find_element(By.XPATH, '//*[@id="productMainBody"]/nav/ul/li[4]/a')
                driver.execute_script("arguments[0].click();", review_category_button)
                time.sleep(2)

            finally:
                driver.quit()

    return render(request, 'review/index.html', {'data': data})
