from django.urls import path
from . import views

urlpatterns = [
    # 검색 및 크롤링
    path('', views.search_and_crawl, name='search_and_crawl'),

    # 특정 공연에 대한 리뷰 분석
    path('analyze/<int:concert_id>/<str:analysis_type>/', views.analyze_reviews, name='analyze_reviews'),

    # 모든 리뷰 보기
    path('all/reviews', views.analyze_all_reviews, name='analyze_all_reviews'),
    
    # 잔여 좌석 분석
    path('all/seats', views.analyze_all_seats, name='analyze_all_seats'),
]