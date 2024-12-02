from django.shortcuts import render
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from .models import Concert
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
                time.sleep(3)

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
                time.sleep(3)

                # iframe 요소 모두 가져오기
                WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.TAG_NAME, 'iframe'))
                )
                iframes = driver.find_elements(By.TAG_NAME, 'iframe')

                # 각 iframe의 'name' 속성 출력
                for iframe in iframes:
                    iframe_name = iframe.get_attribute('name')
                    print(f"iframe name: {iframe_name}")
                time.sleep(3)

            finally:
                driver.quit()

    return render(request, 'review/index.html', {'data': data})
