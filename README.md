# JWTicket

공연 리뷰 및 좌석 정보를 자동으로 수집하고 분석하여 슬랙으로 알림을 전송하는 Django 기반 웹 애플리케이션입니다.

## 주요 기능

### 1. 공연 정보 관리
- 공연 등록/수정/삭제
- 공연별 크롤링 설정
- 공연별 슬랙 알림 설정

### 2. 자동 데이터 수집
- 인터파크 티켓 사이트에서 리뷰 자동 크롤링
- 공연별 좌석 정보 수집
- 설정된 URL 기반 자동 크롤링

### 3. 리뷰 분석
- ChatGPT를 활용한 리뷰 감정 분석
- 긍정/부정 리뷰 요약 생성
- 리뷰 트렌드 분석

### 4. 슬랙 알림
- 분석된 리뷰 요약 자동 전송
- 공연별 개별 채널 설정
- 긍정/부정 리뷰 분리 전송

## 자동화 스케줄링

프로젝트는 다음과 같은 자동화 작업이 스케줄링되어 있습니다:

1. 리뷰 크롤링 (매일 저녁 8시)
   - 실행 함수: `review.tasks.crawl_all_concerts_reviews`
   - 크롤링이 활성화된 공연의 리뷰 수집
   - 중복 리뷰 자동 필터링

2. 감정 분석 (매주 화요일 오전 10시)
   - 실행 함수: `review.chatgpt.update_reviews_with_sentiment`
   - ChatGPT를 활용한 리뷰 감정 분석
   - 분석되지 않은 리뷰 자동 처리

3. 슬랙 알림 전송 (매주 화요일 오전 11시)
   - 실행 함수: `review.tasks.summarize_reviews_cron`
   - 분석된 리뷰 요약 생성
   - 설정된 슬랙 채널로 자동 전송

## 실행 방법

### 1. 환경 설정
```bash
# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 2. 환경 변수 설정
```bash
# .env 파일 생성
cp .env.example .env

# 필요한 환경 변수 설정
- OPENAI_API_KEY: ChatGPT API 키
- SLACK_BOT_TOKEN: 슬랙 봇 토큰
```

### 3. 데이터베이스 설정
```bash
# 마이그레이션 적용
python manage.py migrate
```

### 4. 크론 작업 설정
```bash
# 크론 작업 등록
python manage.py crontab add
```

### 5. 서버 실행
```bash
python manage.py runserver
```

## 수동 실행 기능

웹 인터페이스에서 다음 기능들을 수동으로 실행할 수 있습니다:

1. 리뷰 크롤링 실행
   - 공연 목록 페이지의 "리뷰 크롤링 실행" 버튼
   - 크롤링이 활성화된 모든 공연 처리

2. 슬랙 알림 전송
   - 공연 목록 페이지의 "슬랙알림 전송" 버튼
   - 슬랙 알림이 활성화된 모든 공연 처리

## 기술 스택

- Backend: Django
- Database: SQLite
- Crawling: Selenium
- Analysis: OpenAI GPT-3.5
- Notification: Slack API
- Scheduling: Django-crontab
