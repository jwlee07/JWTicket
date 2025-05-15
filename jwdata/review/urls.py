from django.urls import path
from . import views, chatgpt

app_name = "review"

urlpatterns = [
    # 로그인
    path('login/', views.user_login, name='user_login'),

    # 홈
    path('', views.HomeView.as_view(), name='home'),

    # 공연 관리
    path('concerts/', views.ConcertListView.as_view(), name='concert_list'),
    path('concerts/create/', views.ConcertCreateView.as_view(), name='concert_create'),
    path('concerts/<int:pk>/update/', views.ConcertUpdateView.as_view(), name='concert_update'),
    path('concerts/<int:pk>/delete/', views.ConcertDeleteView.as_view(), name='concert_delete'),
    path('concerts/<int:pk>/toggle-crawling/', views.toggle_concert_crawling, name='toggle_concert_crawling'),
    path('concerts/<int:pk>/toggle-slack/', views.toggle_concert_slack, name='toggle_concert_slack'),
    path('execute-crawl-reviews/', views.execute_crawl_reviews, name='execute_crawl_reviews'),

    # 공연 상세
    path("concert/<int:pk>/", views.ConcertDetailView.as_view(), name="concert_detail"),

    # 로그아웃
    path('logout/', views.user_logout, name='user_logout'),

    # 특정 공연에 대한 리뷰 분석
    path('analyze/<int:concert_id>/<str:analysis_type>/', views.ReviewAnalysisView.as_view(), name='analyze_reviews'),

    # 모든 리뷰 보기
    path("all_reviews/", views.AllReviewsView.as_view(), name="all_reviews"),

    # 관람 패턴
    path("all_pattern/", views.AllPatternView.as_view(), name="all_pattern"),
    
    # 잔여 좌석 분석
    path("all_seats/", views.AllSeatsView.as_view(), name="all_seats"),

    # DB -> Google Sheet 동기화
    path('sync-db-to-sheet/', views.sync_all_db_to_sheet, name='sync_db_to_sheet'),

    # Google Sheet -> DB 동기화
    path('sync-sheet-to-db/', views.sync_all_sheet_to_db, name='sync_sheet_to_db'),

    # Chatgpt 감정 분석
    path('update-sentiment/', views.update_reviews_with_sentiment, name='update_sentiment'),

    # Chatgpt 긍정 리뷰 요약 분석
    path('summarize/positive/<int:concert_id>/', views.summarize_positive_reviews, name='summarize_positive_reviews'),

    # Chatgpt 부정 리뷰 요약 분석
    path('summarize/negative/<int:concert_id>/', views.summarize_negative_reviews, name='summarize_negative_reviews'),
]