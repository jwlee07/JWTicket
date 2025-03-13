from django.urls import path
from . import views

urlpatterns = [
    # 로그인
    path('login/', views.user_login, name='user_login'),

    # 홈
    path('', views.home, name='home'),

    # 공연 상세
    path('concert_detail/', views.concert_detail, name='concert_detail'),

    # 로그아웃
    path('', views.user_logout, name='user_logout'),

    # 홈
    # path('review_home', views.review_home, name='review_home'),

    # 특정 공연에 대한 리뷰 분석
    path('analyze/<int:concert_id>/<str:analysis_type>/', views.analyze_reviews, name='analyze_reviews'),

    # 모든 리뷰 보기
    path('all/reviews', views.analyze_all_reviews, name='analyze_all_reviews'),

    # 관람 패턴
    path('all/pattern', views.analyze_all_pattern, name='analyze_all_pattern'),
    
    # 잔여 좌석 분석
    path('all/seats', views.analyze_all_seats, name='analyze_all_seats'),

    # DB -> Google Sheet 동기화
    path('sync-db-to-sheet/', views.sync_all_db_to_sheet, name='sync_db_to_sheet'),

    # Google Sheet -> DB 동기화
    path('sync-sheet-to-db/', views.sync_all_sheet_to_db, name='sync_sheet_to_db'),

    # Chatgpt 감정 분석
    path('update-sentiment/', views.update_reviews_with_sentiment, name='update_sentiment'),
]
