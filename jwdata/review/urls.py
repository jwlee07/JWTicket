from django.urls import path
from .views import search_and_crawl

urlpatterns = [
    path('', search_and_crawl, name='search_and_crawl'),
]
