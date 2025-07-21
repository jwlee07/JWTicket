# JWTicket - 공연 리뷰 분석 시스템

공연 리뷰 및 좌석 정보를 자동으로 수집하고 AI를 활용하여 분석한 후 슬랙으로 알림을 전송하는 Django 기반 웹 애플리케이션입니다.

## 📋 목차
- [주요 기능](#주요-기능)
- [시스템 아키텍처](#시스템-아키텍처)
- [데이터베이스 구조](#데이터베이스-구조)
- [설치 및 설정](#설치-및-설정)
- [사용법](#사용법)
- [자동화 스케줄링](#자동화-스케줄링)
- [API 및 외부 서비스 연동](#api-및-외부-서비스-연동)
- [프로젝트 구조](#프로젝트-구조)
- [기술 스택](#기술-스택)
- [트러블슈팅](#트러블슈팅)

## 🚀 주요 기능

### 1. 공연 정보 관리
- **공연 등록/수정/삭제**: 웹 인터페이스를 통한 공연 정보 관리
- **공연별 설정**: 크롤링, 슬랙 알림, 감정분석 활성화 개별 설정
- **장르별 분류**: 연극, 뮤지컬, 콘서트 등 장르별 관리

### 2. 자동 데이터 수집
- **리뷰 크롤링**: 인터파크 티켓 사이트에서 공연 리뷰 자동 수집
- **좌석 정보 수집**: 실시간 잔여 좌석 정보 및 캐스팅 정보 수집
- **중복 데이터 필터링**: 동일 리뷰 자동 제거 및 데이터 정합성 보장

### 3. AI 기반 리뷰 분석
- **감정 분석**: OpenAI GPT를 활용한 리뷰 감정 분석 (긍정/중립/부정)
- **리뷰 요약**: 긍정/부정 리뷰 자동 요약 및 인사이트 제공
- **키워드 추출**: TF-IDF 기반 주요 키워드 및 트렌드 분석
- **워드클라우드**: 장르별, 감정별 시각화 (기능 비활성화 상태)

### 4. 고급 분석 기능
- **리뷰 통계**: 평점 분포, 리뷰 수 추이, 감정별 통계
- **관람 패턴 분석**: 다중 공연 관람객 분석 및 관람 패턴 추적
- **클러스터링**: KMeans를 활용한 유사 리뷰 그룹화
- **좌석 분석**: 잔여 좌석 현황 및 예매 트렌드 분석

### 5. 슬랙 연동 알림
- **자동 알림**: 분석된 리뷰 요약 자동 전송
- **공연별 채널**: 개별 공연별 슬랙 채널 설정
- **감정별 분리**: 긍정/부정 리뷰 분석 결과 분리 전송

### 6. 데이터 동기화
- **Google Sheets 연동**: DB와 구글 스프레드시트 양방향 동기화
- **데이터 백업**: 자동 데이터 백업 및 복원 기능

## 🏗️ 시스템 아키텍처

### 전체 시스템 구조

```mermaid
graph TB
    %% 사용자 인터페이스 레이어
    subgraph "Frontend Layer"
        UI["`**웹 인터페이스**
        • 공연 관리
        • 분석 대시보드
        • 설정 관리
        • 리뷰 분석`"]
        
        ADMIN["`**Django Admin**
        • 데이터 관리
        • 사용자 관리`"]
    end
    
    %% Django 애플리케이션 레이어
    subgraph "Application Layer"
        subgraph "Django Framework"
            VIEWS["`**Views & URLs**
            • ConcertDetailView
            • HomeView
            • ReviewAnalysisView
            • API Endpoints`"]
            
            MODELS["`**Models**
            • Concert
            • Review
            • Seat`"]
            
            SERVICES["`**Service Classes**
            • ConcertAnalysisService
            • HomeAnalysisService
            • ReviewAnalysisService`"]
        end
        
        subgraph "Business Logic"
            CRAWL["`**크롤링 모듈**
            crawls.py
            • 리뷰 수집
            • 좌석 정보 수집
            • 공연 정보 파싱`"]
            
            AI["`**AI 분석 모듈**
            chatgpt.py
            • 감정 분석
            • 리뷰 요약
            • 키워드 추출`"]
            
            SLACK["`**알림 모듈**
            slacks.py
            • 메시지 전송
            • 채널별 알림`"]
            
            SHEETS["`**데이터 동기화**
            sheets.py
            • Google Sheets 연동
            • 양방향 동기화`"]
        end
    end
    
    %% 스케줄링 레이어
    subgraph "Automation Layer"
        CRON["`**Django-Crontab**
        • 매일 20:00 리뷰 크롤링
        • 매주 화 10:00 감정분석
        • 매주 화 11:00 슬랙알림`"]
        
        TASKS["`**Tasks Module**
        tasks.py
        • crawl_all_concerts_reviews
        • summarize_reviews_cron`"]
        
        SCRIPTS["`**Windows Scripts**
        scripts/
        • run_crawling.bat
        • run_sentiment.bat
        • run_slack.bat`"]
    end
    
    %% 데이터 레이어
    subgraph "Data Layer"
        DB["`**SQLite Database**
        • Concert 테이블
        • Review 테이블
        • Seat 테이블
        • 사용자 인증`"]
        
        CACHE["`**Django Cache**
        • LocMemCache
        • 성능 최적화`"]
    end
    
    %% 외부 서비스
    subgraph "External Services"
        INTERPARK["`**인터파크 티켓**
        tickets.interpark.com
        • 리뷰 데이터
        • 좌석 정보
        • 공연 상세정보`"]
        
        OPENAI["`**OpenAI API**
        • GPT-3.5-turbo (감정분석)
        • GPT-4o (리뷰요약)
        • 자연어 처리`"]
        
        SLACKAPI["`**Slack API**
        • 채널별 메시지 전송
        • 사용자 멘션
        • 마크다운 지원`"]
        
        GOOGLEAPI["`**Google Sheets API**
        • 서비스 계정 인증
        • 실시간 동기화
        • 데이터 백업`"]
    end
    
    %% 분석 및 ML 레이어
    subgraph "Analytics Layer"
        NLP["`**자연어 처리**
        • KoNLPy (한국어)
        • TF-IDF 키워드
        • 텍스트 전처리`"]
        
        ML["`**머신러닝**
        • scikit-learn
        • KMeans 클러스터링
        • 통계 분석`"]
        
        VIZ["`**시각화**
        • Chart.js
        • Matplotlib
        • 워드클라우드`"]
    end
    
    %% 연결 관계
    UI --> VIEWS
    ADMIN --> MODELS
    VIEWS --> MODELS
    VIEWS --> SERVICES
    SERVICES --> CRAWL
    SERVICES --> AI
    SERVICES --> SLACK
    SERVICES --> SHEETS
    
    MODELS --> DB
    SERVICES --> CACHE
    
    CRON --> TASKS
    TASKS --> CRAWL
    TASKS --> AI
    TASKS --> SLACK
    
    CRAWL --> INTERPARK
    AI --> OPENAI
    SLACK --> SLACKAPI
    SHEETS --> GOOGLEAPI
    
    AI --> NLP
    SERVICES --> ML
    UI --> VIZ
    
    %% 스타일링
    classDef frontend fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef django fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef automation fill:#e8f5e8,stroke:#1b5e20,stroke-width:2px
    classDef data fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef external fill:#fce4ec,stroke:#880e4f,stroke-width:2px
    classDef analytics fill:#f1f8e9,stroke:#33691e,stroke-width:2px
    
    class UI,ADMIN frontend
    class VIEWS,MODELS,SERVICES,CRAWL,AI,SLACK,SHEETS django
    class CRON,TASKS,SCRIPTS automation
    class DB,CACHE data
    class INTERPARK,OPENAI,SLACKAPI,GOOGLEAPI external
    class NLP,ML,VIZ analytics
```

### 데이터 플로우 다이어그램

```mermaid
flowchart TD
    %% 데이터 수집 플로우
    subgraph "데이터 수집 (Data Collection)"
        START([시작: 매일 20:00 크론 실행])
        CHECK_CONCERTS{크롤링 활성화된<br/>공연 확인}
        SELENIUM[Selenium WebDriver<br/>Chrome 브라우저 실행]
        NAVIGATE[인터파크 티켓 페이지<br/>접속 및 네비게이션]
        EXTRACT[리뷰 데이터 추출<br/>• 제목, 내용, 평점<br/>• 작성자, 날짜<br/>• 조회수, 좋아요]
        FILTER[중복 데이터 필터링<br/>DB 중복 체크]
        SAVE_REVIEW[(리뷰 데이터<br/>DB 저장)]
    end
    
    %% AI 분석 플로우
    subgraph "AI 분석 (AI Analysis)"
        CRON_AI([매주 화요일 10:00<br/>감정분석 크론 실행])
        CHECK_SENTIMENT{감정분석 활성화된<br/>공연의 미분석 리뷰}
        PREPROCESS[텍스트 전처리<br/>• 불용어 제거<br/>• 정규화]
        GPT_ANALYSIS[OpenAI GPT API 호출<br/>감정 분석 요청<br/>모델: gpt-3.5-turbo]
        CLASSIFY[감정 분류<br/>긍정/중립/부정]
        UPDATE_EMOTION[(감정 분석 결과<br/>DB 업데이트)]
    end
    
    %% 리뷰 요약 플로우
    subgraph "리뷰 요약 (Review Summarization)"
        CRON_SLACK([매주 화요일 11:00<br/>슬랙 알림 크론 실행])
        CHECK_SLACK{슬랙 알림 활성화된<br/>공연 확인}
        GATHER_POSITIVE[긍정 리뷰 수집<br/>최근 50개]
        GATHER_NEGATIVE[부정 리뷰 수집<br/>최근 50개]
        GPT_SUMMARY[OpenAI GPT API 호출<br/>리뷰 요약 생성<br/>모델: gpt-4o]
        FORMAT_MESSAGE[슬랙 메시지 포맷팅<br/>마크다운 적용]
        SEND_SLACK[Slack API 호출<br/>채널별 메시지 전송]
    end
    
    %% 데이터 동기화 플로우
    subgraph "데이터 동기화 (Data Sync)"
        MANUAL_SYNC([수동 동기화 실행])
        EXPORT_DB[DB 데이터 추출<br/>• Concert<br/>• Review<br/>• Seat]
        GOOGLE_AUTH[Google Sheets API<br/>서비스 계정 인증]
        UPDATE_SHEETS[구글 시트 업데이트<br/>양방향 동기화]
        BACKUP_COMPLETE[(백업 완료)]
    end
    
    %% 분석 및 시각화 플로우
    subgraph "분석 및 시각화 (Analytics & Visualization)"
        USER_REQUEST([사용자 대시보드<br/>접근])
        LOAD_DATA[데이터베이스<br/>데이터 로드]
        CALC_STATS[통계 계산<br/>• 평점 평균<br/>• 리뷰 수<br/>• 감정 분포]
        EXTRACT_KEYWORDS[키워드 추출<br/>TF-IDF 분석]
        CLUSTERING[리뷰 클러스터링<br/>KMeans 알고리즘]
        GENERATE_CHARTS[차트 생성<br/>Chart.js]
        RENDER_PAGE[웹페이지 렌더링<br/>Bootstrap UI]
    end
    
    %% 연결 관계
    START --> CHECK_CONCERTS
    CHECK_CONCERTS -->|활성화됨| SELENIUM
    CHECK_CONCERTS -->|비활성화| START
    SELENIUM --> NAVIGATE
    NAVIGATE --> EXTRACT
    EXTRACT --> FILTER
    FILTER --> SAVE_REVIEW
    
    CRON_AI --> CHECK_SENTIMENT
    CHECK_SENTIMENT -->|미분석 리뷰 존재| PREPROCESS
    CHECK_SENTIMENT -->|분석 완료| CRON_AI
    PREPROCESS --> GPT_ANALYSIS
    GPT_ANALYSIS --> CLASSIFY
    CLASSIFY --> UPDATE_EMOTION
    
    CRON_SLACK --> CHECK_SLACK
    CHECK_SLACK -->|활성화됨| GATHER_POSITIVE
    CHECK_SLACK -->|활성화됨| GATHER_NEGATIVE
    GATHER_POSITIVE --> GPT_SUMMARY
    GATHER_NEGATIVE --> GPT_SUMMARY
    GPT_SUMMARY --> FORMAT_MESSAGE
    FORMAT_MESSAGE --> SEND_SLACK
    
    MANUAL_SYNC --> EXPORT_DB
    EXPORT_DB --> GOOGLE_AUTH
    GOOGLE_AUTH --> UPDATE_SHEETS
    UPDATE_SHEETS --> BACKUP_COMPLETE
    
    USER_REQUEST --> LOAD_DATA
    LOAD_DATA --> CALC_STATS
    LOAD_DATA --> EXTRACT_KEYWORDS
    LOAD_DATA --> CLUSTERING
    CALC_STATS --> GENERATE_CHARTS
    EXTRACT_KEYWORDS --> GENERATE_CHARTS
    CLUSTERING --> GENERATE_CHARTS
    GENERATE_CHARTS --> RENDER_PAGE
    
    %% 트리거 연결
    SAVE_REVIEW -.->|새 리뷰 저장| CHECK_SENTIMENT
    UPDATE_EMOTION -.->|감정분석 완료| GATHER_POSITIVE
    UPDATE_EMOTION -.->|감정분석 완료| GATHER_NEGATIVE
    
    %% 스타일링
    classDef cronJob fill:#e8f5e8,stroke:#2e7d32,stroke-width:3px
    classDef process fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    classDef decision fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef database fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    classDef external fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    
    class START,CRON_AI,CRON_SLACK,MANUAL_SYNC,USER_REQUEST cronJob
    class SELENIUM,EXTRACT,PREPROCESS,GPT_ANALYSIS,GPT_SUMMARY,CALC_STATS process
    class CHECK_CONCERTS,CHECK_SENTIMENT,CHECK_SLACK decision
    class SAVE_REVIEW,UPDATE_EMOTION,BACKUP_COMPLETE database
    class NAVIGATE,SEND_SLACK,UPDATE_SHEETS external
```

### 기술 스택 의존성 다이어그램

```mermaid
graph LR
    %% 프론트엔드 스택
    subgraph "Frontend Stack"
        HTML["`**HTML5 Templates**
        Django 템플릿 시스템`"]
        
        CSS["`**CSS Framework**
        Bootstrap 5.3.0
        Pretendard Font`"]
        
        JS["`**JavaScript Libraries**
        Chart.js (차트)
        Bootstrap JS
        jQuery (AJAX)`"]
    end
    
    %% 백엔드 스택
    subgraph "Backend Stack"
        DJANGO["`**Django 5.0.2**
        웹 프레임워크
        ORM, Admin, Auth`"]
        
        PYTHON["`**Python 3.11+**
        메인 언어`"]
        
        MIDDLEWARE["`**Middleware**
        CSRF Protection
        Authentication
        Session Management`"]
    end
    
    %% 데이터베이스 및 캐시
    subgraph "Database & Cache"
        SQLITE["`**SQLite**
        메인 데이터베이스
        개발/소규모 운영`"]
        
        CACHE_SYS["`**Django Cache**
        LocMemCache
        5분 TTL`"]
    end
    
    %% AI 및 분석 스택
    subgraph "AI & Analytics Stack"
        OPENAI_LIB["`**OpenAI 1.79.0**
        GPT API 클라이언트`"]
        
        SKLEARN["`**scikit-learn 1.4.1**
        머신러닝
        • TF-IDF
        • KMeans 클러스터링`"]
        
        KONLPY["`**KoNLPy 0.6.0**
        한국어 NLP
        형태소 분석`"]
        
        PANDAS["`**Pandas 2.2.1**
        데이터 처리
        분석`"]
        
        MATPLOTLIB["`**Matplotlib 3.8.3**
        데이터 시각화
        차트 생성`"]
    end
    
    %% 웹 크롤링 스택
    subgraph "Web Scraping Stack"
        SELENIUM["`**Selenium 4.18.1**
        웹 브라우저 자동화`"]
        
        BEAUTIFULSOUP["`**BeautifulSoup 4.12.3**
        HTML 파싱`"]
        
        REQUESTS["`**Requests 2.31.0**
        HTTP 클라이언트`"]
        
        WEBDRIVER["`**WebDriver Manager**
        Chrome 드라이버 관리`"]
    end
    
    %% 외부 API 스택
    subgraph "External APIs"
        SLACK_SDK["`**slack-sdk 3.27.1**
        Slack API 클라이언트`"]
        
        GSPREAD["`**gspread 6.0.2**
        Google Sheets API`"]
        
        GOOGLE_AUTH["`**google-auth 2.28.2**
        Google 인증`"]
        
        OAUTH2["`**oauth2client 4.1.3**
        OAuth2 인증`"]
    end
    
    %% 스케줄링 및 자동화
    subgraph "Automation Stack"
        CRONTAB["`**django-crontab 0.7.1**
        크론 작업 관리`"]
        
        SCHEDULER["`**APScheduler 3.11.0**
        고급 스케줄링`"]
        
        THREADING["`**Python Threading**
        비동기 작업`"]
    end
    
    %% 개발 도구
    subgraph "Development Tools"
        DECOUPLE["`**python-decouple 3.8**
        환경변수 관리`"]
        
        DOTENV["`**python-dotenv 1.0.1**
        .env 파일 로드`"]
        
        LOGGING["`**Python Logging**
        로깅 시스템`"]
    end
    
    %% 의존성 연결
    HTML --> CSS
    CSS --> JS
    
    PYTHON --> DJANGO
    DJANGO --> MIDDLEWARE
    DJANGO --> SQLITE
    DJANGO --> CACHE_SYS
    
    DJANGO --> OPENAI_LIB
    DJANGO --> SKLEARN
    PANDAS --> SKLEARN
    KONLPY --> SKLEARN
    MATPLOTLIB --> PANDAS
    
    DJANGO --> SELENIUM
    SELENIUM --> BEAUTIFULSOUP
    SELENIUM --> WEBDRIVER
    BEAUTIFULSOUP --> REQUESTS
    
    DJANGO --> SLACK_SDK
    DJANGO --> GSPREAD
    GSPREAD --> GOOGLE_AUTH
    GOOGLE_AUTH --> OAUTH2
    
    DJANGO --> CRONTAB
    CRONTAB --> SCHEDULER
    SCHEDULER --> THREADING
    
    DJANGO --> DECOUPLE
    DECOUPLE --> DOTENV
    DJANGO --> LOGGING
    
    %% 브라우저 연결
    JS --> DJANGO
    
    %% 스타일링
    classDef frontend fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef backend fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef database fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef ai fill:#e8f5e8,stroke:#1b5e20,stroke-width:2px
    classDef scraping fill:#fce4ec,stroke:#880e4f,stroke-width:2px
    classDef api fill:#f1f8e9,stroke:#33691e,stroke-width:2px
    classDef automation fill:#fff8e1,stroke:#f57f17,stroke-width:2px
    classDef dev fill:#fafafa,stroke:#424242,stroke-width:2px
    
    class HTML,CSS,JS frontend
    class DJANGO,PYTHON,MIDDLEWARE backend
    class SQLITE,CACHE_SYS database
    class OPENAI_LIB,SKLEARN,KONLPY,PANDAS,MATPLOTLIB ai
    class SELENIUM,BEAUTIFULSOUP,REQUESTS,WEBDRIVER scraping
    class SLACK_SDK,GSPREAD,GOOGLE_AUTH,OAUTH2 api
    class CRONTAB,SCHEDULER,THREADING automation
    class DECOUPLE,DOTENV,LOGGING dev
```

## 🗄️ 데이터베이스 구조

### Concert (공연 정보)
```python
- name: 공연명
- place: 공연 장소
- start_date/end_date: 공연 기간
- genre: 장르 (연극/뮤지컬/콘서트)
- crawling_url: 크롤링 대상 URL
- is_crawling_enabled: 크롤링 활성화 여부
- slack_channel_id: 슬랙 채널 ID
- is_slack_enabled: 슬랙 알림 활성화 여부
- is_sentiment_enabled: 감정분석 활성화 여부
```

### Review (리뷰 정보)
```python
- concert: 공연 외래키
- nickname: 작성자 닉네임
- date: 작성일
- view_count/like_count: 조회수/좋아요수
- title/description: 제목/내용
- star_rating: 별점 (1-5)
- emotion: AI 분석 감정 (긍정/중립/부정)
```

### Seat (좌석 정보)
```python
- concert: 공연 외래키
- year/month/day_num: 공연일
- round_name/round_time: 회차 정보
- seat_class: 좌석 등급
- seat_count: 잔여 좌석 수
- actors: 캐스팅 배우 정보
- created_at: 데이터 수집 시간
```

## ⚙️ 설치 및 설정

### 1. 시스템 요구사항
- Python 3.11+
- Chrome 브라우저 (크롤링용)
- Git

### 2. 프로젝트 클론 및 환경 설정
```bash
# 프로젝트 클론
git clone <repository-url>
cd JWTicket

# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 3. 환경 변수 설정
프로젝트 루트에 `.env` 파일을 생성하고 다음 내용을 설정:

```env
# OpenAI API 설정
OPENAI_API_KEY=your_openai_api_key_here

# Slack 설정
SLACK_OAUTH_TOKEN=xoxb-your-slack-bot-token

# Google Sheets 설정
GOOGLE_SHEET_KEY=your_google_sheet_key
```

### 4. Google Sheets 서비스 계정 설정
1. Google Cloud Console에서 서비스 계정 생성
2. JSON 키 파일을 `jwdata/ts-ticket-data-599d02f2629e.json`으로 저장
3. 구글 스프레드시트에 서비스 계정 이메일 공유 권한 부여

### 5. 데이터베이스 초기화
```bash
cd jwdata
python manage.py migrate
python manage.py createsuperuser  # 관리자 계정 생성
```

### 6. 크론 작업 설정 (선택사항)
```bash
# 크론 작업 등록
python manage.py crontab add

# 크론 작업 확인
python manage.py crontab show

# 크론 작업 제거 (필요시)
python manage.py crontab remove
```

## 💻 사용법

### 1. 서버 실행
```bash
cd jwdata
python manage.py runserver
```

웹 브라우저에서 `http://localhost:8000/review/`로 접속

### 2. 공연 등록 및 설정
1. **공연 등록**: 공연 목록 페이지에서 새 공연 추가
2. **크롤링 설정**: 
   - 크롤링 URL 설정 (인터파크 티켓 상세 페이지)
   - 크롤링 활성화 토글
3. **슬랙 설정**:
   - 슬랙 채널 ID 입력
   - 슬랙 알림 활성화 토글
4. **감정분석 설정**: 감정분석 활성화 토글

### 3. 수동 실행
- **리뷰 크롤링**: 공연 목록 페이지의 "리뷰 크롤링 실행" 버튼
- **감정 분석**: 개별 공연 또는 전체 리뷰 대상
- **슬랙 알림**: "슬랙알림 전송" 버튼으로 즉시 전송

### 4. 분석 결과 확인
- **홈 대시보드**: 전체 장르별 통계 및 워드클라우드
- **공연 상세**: 개별 공연의 상세 분석 결과
- **리뷰 분석**: 다양한 분석 유형별 세부 결과

## ⏰ 자동화 스케줄링

시스템은 다음과 같은 자동화 작업을 지원합니다:

### 1. 리뷰 크롤링 (매일 20:00)
```python
# Cron: 0 20 * * *
# 함수: review.tasks.crawl_all_concerts_reviews
```
- 크롤링이 활성화된 모든 공연의 리뷰 수집
- 중복 리뷰 자동 필터링
- 실패한 크롤링에 대한 로그 기록

### 2. 감정 분석 (매주 화요일 10:00)
```python
# Cron: 0 10 * * TUE
# 함수: review.chatgpt.update_reviews_with_sentiment_cron
```
- 감정분석이 활성화된 공연의 미분석 리뷰 처리
- OpenAI GPT를 활용한 감정 분류
- 배치 처리로 API 호출 최적화

### 3. 슬랙 알림 전송 (매주 화요일 11:00)
```python
# Cron: 0 11 * * TUE
# 함수: review.tasks.summarize_reviews_cron
```
- 슬랙 알림이 활성화된 공연의 리뷰 요약 생성
- 긍정/부정 리뷰 분리 전송
- 설정된 슬랙 채널로 자동 전송

### Windows 환경 대안 스케줄링
`jwdata/scripts/` 디렉토리의 배치 파일 활용:
- `run_crawling.bat`: 리뷰 크롤링 실행
- `run_sentiment.bat`: 감정 분석 실행
- `run_slack.bat`: 슬랙 알림 전송
- `start_scheduler.bat`: 전체 스케줄러 시작

## 🔗 API 및 외부 서비스 연동

### 1. OpenAI GPT API
```python
# 설정: jwdata/review/chatgpt.py
client = OpenAI(api_key=settings.OPENAI_API_KEY)

# 사용 모델:
# - 감정분석: gpt-3.5-turbo
# - 리뷰요약: gpt-4o
```

### 2. Slack API
```python
# 설정: jwdata/review/slacks.py
client = slack_sdk.WebClient(token=settings.SLACK_OAUTH_TOKEN)

# 기능:
# - 채널별 메시지 전송
# - 사용자 멘션 지원
# - 마크다운 형식 지원
```

### 3. Google Sheets API
```python
# 설정: jwdata/review/sheets.py
# 서비스 계정 인증 방식 사용
# 양방향 데이터 동기화 지원

# 시트 구조:
# - concerts: 공연 정보
# - reviews: 리뷰 데이터
# - seats: 좌석 정보
```

### 4. 웹 크롤링 (Selenium)
```python
# 대상 사이트: tickets.interpark.com
# 수집 데이터:
# - 리뷰 내용, 평점, 작성자, 날짜
# - 잔여 좌석 정보, 캐스팅 정보
# - 공연 상세 정보
```

## 📁 프로젝트 구조

```
JWTicket/
├── jwdata/                      # Django 프로젝트 루트
│   ├── ticket/                  # 프로젝트 설정
│   │   ├── settings.py         # Django 설정 파일
│   │   ├── urls.py             # URL 라우팅
│   │   └── wsgi.py             # WSGI 설정
│   ├── review/                  # 메인 애플리케이션
│   │   ├── models.py           # 데이터 모델 정의
│   │   ├── views.py            # 뷰 로직
│   │   ├── urls.py             # URL 패턴
│   │   ├── services.py         # 비즈니스 로직
│   │   ├── chatgpt.py          # AI 분석 로직
│   │   ├── crawls.py           # 웹 크롤링 로직
│   │   ├── slacks.py           # 슬랙 연동
│   │   ├── sheets.py           # 구글 시트 연동
│   │   ├── tasks.py            # 스케줄링 작업
│   │   ├── utils.py            # 유틸리티 함수
│   │   ├── templates/          # HTML 템플릿
│   │   └── migrations/         # 데이터베이스 마이그레이션
│   ├── scripts/                # 실행 스크립트
│   │   ├── scheduler.py        # 스케줄러 관리
│   │   └── *.bat               # Windows 배치 파일
│   ├── manage.py               # Django 관리 명령
│   └── db.sqlite3              # 데이터베이스 파일
├── requirements.txt            # 의존성 목록
├── .env                        # 환경 변수 (생성 필요)
└── README.md                   # 프로젝트 문서
```

## 🛠️ 기술 스택

### Backend
- **Django 5.0.2**: 웹 프레임워크
- **SQLite**: 데이터베이스
- **Django-crontab**: 스케줄링

### 데이터 수집 및 처리
- **Selenium 4.18.1**: 웹 크롤링
- **Beautiful Soup 4.12.3**: HTML 파싱
- **Pandas 2.2.1**: 데이터 처리

### AI 및 분석
- **OpenAI 1.79.0**: GPT API 클라이언트
- **scikit-learn 1.4.1**: 머신러닝
- **KoNLPy 0.6.0**: 한국어 자연어 처리
- **Matplotlib 3.8.3**: 데이터 시각화

### 외부 연동
- **slack-sdk 3.27.1**: 슬랙 API
- **gspread 6.0.2**: 구글 시트 API
- **google-auth 2.28.2**: 구글 인증

### Frontend
- **Bootstrap 5**: UI 프레임워크
- **Chart.js**: 차트 라이브러리
- **django-bootstrap5**: Django-Bootstrap 통합

## 🔧 트러블슈팅

### 1. OpenAI API 오류
```python
# 오류: Client.__init__() got an unexpected keyword argument 'proxies'
# 해결: jwdata/review/chatgpt.py에서 OpenAI 클라이언트 초기화 수정
client = OpenAI(api_key=settings.OPENAI_API_KEY)
```

### 2. 크롤링 실패
- Chrome 드라이버 버전 확인
- 웹사이트 구조 변경 대응
- 네트워크 연결 상태 확인

### 3. 슬랙 알림 실패
- 슬랙 봇 토큰 권한 확인
- 채널 ID 정확성 검증
- API 요청 제한 확인

### 4. 감정분석 오류
- OpenAI API 키 및 할당량 확인
- 모델 이름 정확성 검증
- 요청 텍스트 길이 제한 확인

### 5. 크론 작업 미실행
```bash
# 크론 작업 상태 확인
python manage.py crontab show

# 로그 확인
tail -f /var/log/syslog | grep CRON
```

## 📝 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 🤝 기여

프로젝트 개선을 위한 기여를 환영합니다. 이슈 제보나 풀 리퀘스트를 통해 참여해 주세요.

## 📞 문의

프로젝트 관련 문의사항이 있으시면 이슈를 통해 연락해 주세요.
