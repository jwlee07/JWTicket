from django.urls import path
from . import views

urlpatterns = [
    path('', views.search_and_crawl, name='search_and_crawl'),
    path('analyze/<int:concert_id>/<str:analysis_type>/', views.analyze_reviews, name='analyze_reviews'),
]
