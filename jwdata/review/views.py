from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages

from django.http import HttpResponse
from django.shortcuts import render

from django.db.models import F, Count, Min, Avg
from django.db.models.functions import Length
from django.db.models import Value
from django.db.models.functions import Concat, Cast
from django.db.models import CharField

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

from .models import Concert, Review, Seat

from datetime import date, timedelta

import io
import base64
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from wordcloud import WordCloud

import re
import pandas as pd
from collections import Counter, defaultdict
from itertools import combinations
from konlpy.tag import Okt
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.cluster import KMeans

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView, TemplateView, ListView

from .chatgpt import (
    update_reviews_with_sentiment, 
    summarize_positive_reviews,
    summarize_negative_reviews,
)

from .crawls import crawl_concert_info, crawl_concert_reviews, crawl_concert_seats

from .sheets import (
    sync_patterns_to_sheet,
    sync_db_concerts_to_sheet,
    sync_db_reviews_to_sheet,
    sync_db_seats_to_sheet,
    sync_concert_sheet_to_db,
    sync_reviews_sheet_to_db,
    sync_seats_sheet_to_db,
)

from .services import ConcertAnalysisService, HomeAnalysisService, ReviewAnalysisService, AllAnalysisService

# ==================================================================
# chatgpt
# ==================================================================

def update_sentiment_view(request):
    update_reviews_with_sentiment()
    return redirect('home')


# ==================================================================
# Analysis
# ==================================================================

class ConcertDetailView(LoginRequiredMixin, DetailView):
    model = Concert
    template_name = "review/review_concert_detail.html"
    context_object_name = "selected_concert"
    pk_url_kwarg = "pk"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 서비스 객체 생성
        analysis_service = ConcertAnalysisService(self.object.id)
        
        # 통계 데이터 가져오기
        stats = analysis_service.get_review_statistics()
        context.update({
            "selected_avg": stats["selected"]["avg"],
            "selected_count": stats["selected"]["count"],
            "overall_avg": stats["overall"]["avg"],
            "overall_count": stats["overall"]["count"],
            "genre_avg": stats["genre"]["avg"],
            "genre_count": stats["genre"]["count"],
        })
        
        # 워드클라우드 이미지 생성
        wordclouds = analysis_service.generate_wordclouds()
        context.update({
            "img_all": wordclouds["all"],
            "img_positive": wordclouds["positive"],
            "img_negative": wordclouds["negative"],
            "positive_reviews": wordclouds["positive_reviews"],
            "negative_reviews": wordclouds["negative_reviews"],
        })
        
        # 감정 통계 가져오기
        context["emotion"] = analysis_service.get_emotion_statistics()
        
        # 리뷰 추이 데이터 가져오기
        trends = analysis_service.get_review_trends()
        context.update({
            "selected_date_summary": trends["review_counts"],
            "selected_date_rating_summary": trends["rating_averages"],
        })
        
        return context

class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "review/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 서비스 객체 생성
        service = HomeAnalysisService()
        
        # 기본 데이터
        context["concerts"] = service.concerts
        context["active_concert_id"] = self.request.GET.get("active_concert_id")
        
        # 장르별 리뷰 데이터 가져오기
        reviews_by_genre = service.get_genre_reviews()
        
        # 장르별 워드클라우드 생성
        wordclouds = service.generate_genre_wordclouds(reviews_by_genre)
        context.update({
            "img_all": wordclouds["all"],
            "img_play": wordclouds["play"],
            "img_musical": wordclouds["musical"],
            "img_concert": wordclouds["concert"],
        })
        
        # 감정별 리뷰 데이터 가져오기
        emotion_reviews = service.get_emotion_reviews(reviews_by_genre)
        
        # 감정별 워드클라우드 생성
        emotion_wordclouds = service.generate_emotion_wordclouds(emotion_reviews)
        context.update({
            "img_all_positive": emotion_wordclouds["all"]["positive"],
            "img_all_negative": emotion_wordclouds["all"]["negative"],
            "img_play_positive": emotion_wordclouds["play"]["positive"],
            "img_play_negative": emotion_wordclouds["play"]["negative"],
            "img_musical_positive": emotion_wordclouds["musical"]["positive"],
            "img_musical_negative": emotion_wordclouds["musical"]["negative"],
            "img_concert_positive": emotion_wordclouds["concert"]["positive"],
            "img_concert_negative": emotion_wordclouds["concert"]["negative"],
        })
        
        # 통계 데이터 가져오기
        stats = service.get_statistics()
        context.update({
            "avg_all": stats["all"]["avg"],
            "count_all": stats["all"]["count"],
            "avg_play": stats["play"]["avg"],
            "count_play": stats["play"]["count"],
            "avg_musical": stats["musical"]["avg"],
            "count_musical": stats["musical"]["count"],
            "avg_concert": stats["concert"]["avg"],
            "count_concert": stats["concert"]["count"],
        })
        
        # 감정 통계 가져오기
        emotion_stats = service.get_emotion_statistics()
        context.update({
            "emotion_all": emotion_stats["all"],
            "emotion_play": emotion_stats["play"],
            "emotion_musical": emotion_stats["musical"],
            "emotion_concert": emotion_stats["concert"],
        })
        
        # 공연 요약 데이터 가져오기
        concert_data = service.get_concert_summary()
        context.update({
            "concert_summary": concert_data["summary"],
            "concert_date_summary": concert_data["date_summary"],
            "concert_date_rating_summary": concert_data["rating_summary"],
        })
        
        return context

class ReviewAnalysisView(LoginRequiredMixin, TemplateView):
    template_name = "review/analysis.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        concert_id = self.kwargs.get("concert_id")
        analysis_type = self.kwargs.get("analysis_type")
        
        service = ReviewAnalysisService(concert_id)
        
        if analysis_type == "long_reviews":
            context["data"] = service.get_long_reviews()
            
        elif analysis_type == "frequent_reviewers":
            context["data"] = service.get_frequent_reviewers()
            
        elif analysis_type == "frequent_words":
            context["data"] = service.get_frequent_words()
            
        elif analysis_type == "frequent_words_mix":
            context["data"] = service.get_frequent_words_mix()
            
        elif analysis_type == "frequent_words_important":
            context["data"] = service.get_frequent_words_important()
            
        elif analysis_type == "similar_reviews":
            context["data"] = service.get_similar_reviews()
            
        elif analysis_type == "top_view_count_reviews":
            context["data"] = service.get_top_view_count_reviews()
            
        elif analysis_type == "low_star_rating_reviews":
            context["data"] = service.get_low_star_rating_reviews()
            
        else:
            context["data"] = []
            
        context["analysis_type"] = analysis_type
        return context

@login_required
def analyze_all_reviews(request):
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    reviews = Review.objects.all().select_related("concert")
    if start_date and end_date:
        reviews = reviews.filter(date__range=[start_date, end_date])

    # 공연별 요약 (평균 평점, 리뷰 개수)
    concert_summary = (
        reviews.values("concert__name", "concert__place")
        .annotate(average_rating=Avg("star_rating"), total_reviews=Count("id"))
        .order_by("concert__name")
    )

    # 공연별 날짜별 리뷰 수
    concert_date_summary = {
        c["concert__name"]: (
            reviews.filter(concert__name=c["concert__name"])
            .values("date")
            .annotate(reviews_count=Count("id"))
            .order_by("-date")
        )
        for c in concert_summary
    }

    # 공연별 날짜별 평균 평점
    concert_date_rating_summary = {
        c["concert__name"]: (
            reviews.filter(concert__name=c["concert__name"])
            .values("date")
            .annotate(average_rating=Avg("star_rating"))
            .order_by("-date")
        )
        for c in concert_summary
    }

    # 닉네임별 관람 공연 분석(여러 공연 관람한 닉네임)
    nicknames = (
        reviews.values("nickname", "concert__name")
        .annotate(first_date=Min("date"))
        .distinct()
    )
    nickname_to_concerts = defaultdict(list)
    for n in nicknames:
        nickname_to_concerts[n["nickname"]].append(
            {
                "concert__name": n["concert__name"],
                "first_date": n["first_date"].strftime("%Y-%m-%d"),
            }
        )

    common_nicknames = {
        nn: sorted(cs, key=lambda x: x["first_date"])
        for nn, cs in nickname_to_concerts.items()
        if len(cs) > 1
    }

    sorted_common_nicknames = dict(
        sorted(common_nicknames.items(), key=lambda i: len(i[1]), reverse=True)
    )

    # 공연별 닉네임 집합
    concerts_with_nicknames = reviews.values("concert__name", "nickname").distinct()
    concert_to_nicknames = defaultdict(set)
    for entry in concerts_with_nicknames:
        concert_to_nicknames[entry["concert__name"]].add(entry["nickname"])

    # 모든 공연 리스트
    all_concerts = list(concert_to_nicknames.keys())

    # 공연 조합별 닉네임 교집합 크기
    combination_counts = {}
    for r in range(1, len(all_concerts) + 1):
        for combo in combinations(all_concerts, r):
            intersected = set.intersection(*(concert_to_nicknames[c] for c in combo))
            combination_counts[", ".join(combo)] = len(intersected)

    # 전체 리뷰 데이터(테이블 형태로 조회 가능)
    review_data = [
        {
            "공연명": r.concert.name,
            "장소": r.concert.place,
            "작성자": r.nickname,
            "작성일": r.date,
            "평점": r.star_rating,
            "제목": r.title,
            "내용": r.description,
            "조회수": r.view_count,
            "좋아요": r.like_count,
        }
        for r in reviews
    ]

    return render(
        request,
        "review/all_reviews.html",
        {
            "start_date": start_date,
            "end_date": end_date,
            "concert_summary": concert_summary,
            "concert_date_summary": concert_date_summary,
            "concert_date_rating_summary": concert_date_rating_summary,
            "common_nicknames": sorted_common_nicknames,
            "combination_counts": combination_counts,
            "reviews": review_data,
        },
    )


@login_required
def analyze_all_seats(request):
    # GET 요청에서 필터 값 가져오기
    selected_concert = request.GET.get("concert")

    # 날짜를 'YYYY-MM-DD' 형태로 연결해서 가상 필드 date 생성
    seats_with_date = Seat.objects.annotate(
        date=Concat(
            Cast(F("year"), output_field=CharField()),
            Value("-"),
            Cast(F("month"), output_field=CharField()),
            Value("-"),
            Cast(F("day_num"), output_field=CharField()),
        )
    )

    # 공연 필터링
    if selected_concert:
        seats_with_date = seats_with_date.filter(concert__name=selected_concert)

    # 데이터 정렬 및 필요한 필드 선택
    seat_data = seats_with_date.order_by(
        "concert__name", "date", "day_str", "round_name", "seat_class", "created_at"
    ).values(
        "concert__name",
        "date",
        "day_str",
        "round_name",
        "seat_class",
        "created_at",
        "seat_count",
        "actors",
    )

    # 모든 공연 이름 리스트
    all_concerts = (
        Concert.objects.values_list("name", flat=True).distinct().order_by("name")
    )

    # 모든 회차 정보에서 중복 제거한 회차 목록
    unique_rounds = list(
        Seat.objects.values_list("round_name", flat=True)
        .distinct()
        .order_by("round_name")
    )

    return render(
        request,
        "review/all_seats.html",
        {
            "seat_data": seat_data,
            "selected_concert": selected_concert,
            "all_concerts": all_concerts,
            "unique_rounds": unique_rounds,
        },
    )


@login_required
def analyze_all_pattern(request):
    reviews = Review.objects.all().select_related("concert")

    # 닉네임별 (공연__name) 정보 수집
    nicknames = (
        reviews.values("nickname", "concert__name")
        .annotate(first_date=Min("date"))
        .distinct()
    )
    nickname_to_concerts = defaultdict(set)
    for n in nicknames:
        nickname_to_concerts[n["nickname"]].add(n["concert__name"])

    # 공연 리스트 생성
    all_concerts = list(set(reviews.values_list("concert__name", flat=True)))
    filtered_common_nicknames = {}

    for first_concert in all_concerts:
        common_nicknames = {}
        for nn, cs in nickname_to_concerts.items():
            if first_concert in cs and len(cs) > 1:
                sorted_concs = sorted(cs)
                concert_dates = []
                for concert in sorted_concs:
                    first_review = (
                        reviews.filter(nickname=nn, concert__name=concert)
                        .order_by("date")
                        .first()
                    )
                    if first_review:
                        date_str = first_review.date.strftime("%Y-%m-%d")
                    else:
                        date_str = "Unknown"
                    concert_dates.append({"concert": concert, "date": date_str})
                # 날짜 기준 정렬
                concert_dates_sorted = sorted(concert_dates, key=lambda x: x["date"])
                if concert_dates_sorted[0]["concert"] == first_concert:
                    common_nicknames[nn] = concert_dates_sorted

        # 샌키 다이어그램 데이터 생성
        sankey_data = {
            "type": "sankey",
            "orientation": "h",
            "node": {
                "pad": 15,
                "thickness": 20,
                "line": {"color": "black", "width": 0.5},
                "label": [],
            },
            "link": {"source": [], "target": [], "value": []},
        }
        node_index = {}
        idx = 0

        for nn, concerts in common_nicknames.items():
            for i in range(len(concerts) - 1):
                source = concerts[i]["concert"]
                target = concerts[i + 1]["concert"]

                if source not in node_index:
                    node_index[source] = idx
                    sankey_data["node"]["label"].append(source)
                    idx += 1
                if target not in node_index:
                    node_index[target] = idx
                    sankey_data["node"]["label"].append(target)
                    idx += 1

                sankey_data["link"]["source"].append(node_index[source])
                sankey_data["link"]["target"].append(node_index[target])
                sankey_data["link"]["value"].append(1)

        if sankey_data["node"]["label"]:
            filtered_common_nicknames[first_concert] = sankey_data

    # 닉네임 별 관람 패턴 (두 개 이상의 공연 관람한 경우만 수집)
    common_nicknames = {}
    for nn, cs in nickname_to_concerts.items():
        if len(cs) > 1:
            sorted_concs = sorted(cs)
            concert_dates = []
            for concert in sorted_concs:
                first_review = (
                    reviews.filter(nickname=nn, concert__name=concert)
                    .order_by("date")
                    .first()
                )
                if first_review:
                    date_str = first_review.date.strftime("%Y-%m-%d")
                else:
                    date_str = "Unknown"
                concert_dates.append({"concert": concert, "date": date_str})
            # 날짜 기준 정렬
            concert_dates_sorted = sorted(concert_dates, key=lambda x: x["date"])
            common_nicknames[nn] = concert_dates_sorted

    # 관람 패턴(닉네임별 공연 목록) 내림차순 정렬
    sorted_common_nicknames = dict(
        sorted(common_nicknames.items(), key=lambda item: len(item[1]), reverse=True)
    )

    # 공연 조합별 분포 계산(중간 생략)
    combination_counts = defaultdict(int)
    for concerts in nickname_to_concerts.values():
        for r in range(1, len(concerts) + 1):
            for combo in combinations(sorted(concerts), r):
                combination_key = ", ".join(combo)
                combination_counts[combination_key] += 1

    sorted_combinations = sorted(
        combination_counts.items(), key=lambda x: x[1], reverse=True
    )
    combination_counts_dict = dict(sorted_combinations)
    print("[패턴 정보 계산 완료]")

    # sync_patterns_to_sheet(sorted_common_nicknames)
    # print("[패턴 정보 업로드 완료]")

    return render(
        request,
        "review/all_pattern.html",
        {
            "filtered_common_nicknames": filtered_common_nicknames,
            "all_concerts": all_concerts,
            "common_nicknames": sorted_common_nicknames,
            "combination_counts": combination_counts_dict,
        },
    )


# ==================================================================
# Login / Logout
# ==================================================================

def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # 인증 성공 시 로그인 처리
            login(request, user)
            return redirect('review:home')
        else:
            # 인증 실패 시 메시지 띄우고 다시 로그인 페이지로
            messages.error(request, '아이디 또는 비밀번호가 잘못되었습니다.')
            return redirect('review:user_login')
    
    # GET 요청 시 로그인 폼 보여주기
    return render(request, 'review/login.html')

def user_logout(request):
    response = render(request, "review/login.html")

    logout(request)
    request.session.flush()
    for cookie in request.COOKIES:
        response.delete_cookie(cookie)

    return response

# ==================================================================
# Google sheets <-> DB
# ==================================================================


@login_required
def sync_all_db_to_sheet(request):
    logs = []

    # 1) Concert 동기화
    sync_db_concerts_to_sheet()
    logs.append("[DB -> Sheet] Concert 동기화 완료")
    print("[DB -> Sheet] Concert 동기화 완료")

    # 2) Review 동기화
    sync_db_reviews_to_sheet()
    logs.append("[DB -> Sheet] Review 동기화 완료")
    print("[DB -> Sheet] Review 동기화 완료")

    # 3) Seat 동기화
    sync_db_seats_to_sheet()
    logs.append("[DB -> Sheet] Seat 동기화 완료")
    print("[DB -> Sheet] Seat 동기화 완료")

    response_text = "\n".join(logs)
    return redirect("home")


@login_required
def sync_all_sheet_to_db(request):
    logs = []

    sync_concert_sheet_to_db()
    logs.append("[Sheet -> DB] Concert 동기화 완료")
    print("[Sheet -> DB] Concert 동기화 완료")

    sync_reviews_sheet_to_db()
    logs.append("[Sheet -> DB] Review 동기화 완료")
    print("[Sheet -> DB] Review 동기화 완료")

    sync_seats_sheet_to_db()
    logs.append("[Sheet -> DB] Seat 동기화 완료")
    print("[Sheet -> DB] Seat 동기화 완료")

    response_text = "\n".join(logs)
    return redirect("home")


# ==================================================================
# 텍스트 전처리 함수
# ==================================================================

stop_words = ['이','것','정말','너무','그리고', '공연', '좀', '공연', '연극', '뮤지컬', 
            '콘서트', '더', '진짜', '또', '수', '나', '배우', '연기', '보고', '넘버', '작품', 
            '생각', '조금', '타인', '삶', '그', '왜', '때', '때문', '일단', '끝', '못', '볼', 
            '저', '막', '안', '내용', '거', '말', '게', '데', '진', '무명', '준희', '라이카', 
            '요', '너', '광역시', '광주', '한편', '확인', '어디가', '전', '극', '제대로']

def clean_text(text):
    cleaned = re.sub(r"[^가-힣a-zA-Z0-9\s]", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

def generate_wordcloud_image(text, wc_width=800, wc_height=800, fig_width=8, fig_height=8):
    if not text.strip():
        return None

    wordcloud = WordCloud(
        font_path='/Library/Fonts/AppleGothic.ttf',
        width=wc_width, 
        height=wc_height, 
        background_color="white"
    ).generate(text)

    fig = plt.figure(figsize=(fig_width, fig_height))
    plt.imshow(wordcloud.to_array(), interpolation="bilinear")
    plt.axis("off")

    buffer = io.BytesIO()
    plt.savefig(buffer, format="png", bbox_inches="tight")
    buffer.seek(0)
    image_png = buffer.getvalue()
    buffer.close()
    plt.close(fig)

    base64_img = base64.b64encode(image_png).decode("utf-8")
    return base64_img

def preprocess_text(texts):
    okt = Okt()

    # 최종 토큰을 모을 리스트
    all_nouns = []

    for doc in texts:
        # 원본 텍스트에서 특수문자 제거 + 여백 정리
        cleaned = clean_text(doc)

        # 명사만 추출
        nouns = okt.nouns(cleaned)
        nouns = [n for n in nouns if n not in stop_words]

        # 전체 리스트에 추가
        all_nouns.extend(nouns)

    # 추출된 모든 명사를 공백으로 join
    final_text = " ".join(all_nouns)
    return final_text

def comma_format(num):
    if not num:
        return "0"
    return f"{num:,}"

class AllReviewsView(LoginRequiredMixin, TemplateView):
    template_name = "review/all_reviews.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")

        reviews = Review.objects.all().select_related("concert")
        if start_date and end_date:
            reviews = reviews.filter(date__range=[start_date, end_date])

        # 공연별 요약 (평균 평점, 리뷰 개수)
        concert_summary = (
            reviews.values("concert__name", "concert__place")
            .annotate(average_rating=Avg("star_rating"), total_reviews=Count("id"))
            .order_by("concert__name")
        )

        # 공연별 날짜별 리뷰 수
        concert_date_summary = {
            c["concert__name"]: (
                reviews.filter(concert__name=c["concert__name"])
                .values("date")
                .annotate(reviews_count=Count("id"))
                .order_by("-date")
            )
            for c in concert_summary
        }

        # 공연별 날짜별 평균 평점
        concert_date_rating_summary = {
            c["concert__name"]: (
                reviews.filter(concert__name=c["concert__name"])
                .values("date")
                .annotate(average_rating=Avg("star_rating"))
                .order_by("-date")
            )
            for c in concert_summary
        }

        # 닉네임별 관람 공연 분석(여러 공연 관람한 닉네임)
        nicknames = (
            reviews.values("nickname", "concert__name")
            .annotate(first_date=Min("date"))
            .distinct()
        )
        nickname_to_concerts = defaultdict(list)
        for n in nicknames:
            nickname_to_concerts[n["nickname"]].append(
                {
                    "concert__name": n["concert__name"],
                    "first_date": n["first_date"].strftime("%Y-%m-%d"),
                }
            )

        common_nicknames = {
            nn: sorted(cs, key=lambda x: x["first_date"])
            for nn, cs in nickname_to_concerts.items()
            if len(cs) > 1
        }

        sorted_common_nicknames = dict(
            sorted(common_nicknames.items(), key=lambda i: len(i[1]), reverse=True)
        )

        # 전체 리뷰 데이터(테이블 형태로 조회 가능)
        review_data = [
            {
                "공연명": r.concert.name,
                "장소": r.concert.place,
                "작성자": r.nickname,
                "작성일": r.date,
                "평점": r.star_rating,
                "제목": r.title,
                "내용": r.description,
                "조회수": r.view_count,
                "좋아요": r.like_count,
            }
            for r in reviews
        ]

        context.update({
            "start_date": start_date,
            "end_date": end_date,
            "concert_summary": concert_summary,
            "concert_date_summary": concert_date_summary,
            "concert_date_rating_summary": concert_date_rating_summary,
            "common_nicknames": sorted_common_nicknames,
            "reviews": review_data,
        })
        return context

class AllSeatsView(LoginRequiredMixin, TemplateView):
    template_name = "review/all_seats.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_concert = self.request.GET.get("concert")

        # 날짜를 'YYYY-MM-DD' 형태로 연결해서 가상 필드 date 생성
        seats_with_date = Seat.objects.annotate(
            date=Concat(
                Cast(F("year"), output_field=CharField()),
                Value("-"),
                Cast(F("month"), output_field=CharField()),
                Value("-"),
                Cast(F("day_num"), output_field=CharField()),
            )
        )

        # 공연 필터링
        if selected_concert:
            seats_with_date = seats_with_date.filter(concert__name=selected_concert)

        # 데이터 정렬 및 필요한 필드 선택
        seat_data = seats_with_date.order_by(
            "concert__name", "date", "day_str", "round_name", "seat_class", "created_at"
        ).values(
            "concert__name",
            "date",
            "day_str",
            "round_name",
            "seat_class",
            "created_at",
            "seat_count",
            "actors",
        )

        # 모든 공연 이름 리스트
        all_concerts = (
            Concert.objects.values_list("name", flat=True).distinct().order_by("name")
        )

        # 모든 회차 정보에서 중복 제거한 회차 목록
        unique_rounds = list(
            Seat.objects.values_list("round_name", flat=True)
            .distinct()
            .order_by("round_name")
        )

        context.update({
            "seat_data": seat_data,
            "selected_concert": selected_concert,
            "all_concerts": all_concerts,
            "unique_rounds": unique_rounds,
        })
        return context

class AllPatternView(LoginRequiredMixin, TemplateView):
    template_name = "review/all_pattern.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reviews = Review.objects.all().select_related("concert")

        # 닉네임별 (공연__name) 정보 수집
        nicknames = (
            reviews.values("nickname", "concert__name")
            .annotate(first_date=Min("date"))
            .distinct()
        )
        nickname_to_concerts = defaultdict(set)
        for n in nicknames:
            nickname_to_concerts[n["nickname"]].add(n["concert__name"])

        # 공연 리스트 생성
        all_concerts = list(set(reviews.values_list("concert__name", flat=True)))
        filtered_common_nicknames = {}

        for first_concert in all_concerts:
            common_nicknames = {}
            for nn, cs in nickname_to_concerts.items():
                if first_concert in cs and len(cs) > 1:
                    sorted_concs = sorted(cs)
                    concert_dates = []
                    for concert in sorted_concs:
                        first_review = (
                            reviews.filter(nickname=nn, concert__name=concert)
                            .order_by("date")
                            .first()
                        )
                        if first_review:
                            date_str = first_review.date.strftime("%Y-%m-%d")
                        else:
                            date_str = "Unknown"
                        concert_dates.append({"concert": concert, "date": date_str})
                    # 날짜 기준 정렬
                    concert_dates_sorted = sorted(concert_dates, key=lambda x: x["date"])
                    if concert_dates_sorted[0]["concert"] == first_concert:
                        common_nicknames[nn] = concert_dates_sorted

            # 샌키 다이어그램 데이터 생성
            sankey_data = {
                "type": "sankey",
                "orientation": "h",
                "node": {
                    "pad": 15,
                    "thickness": 20,
                    "line": {"color": "black", "width": 0.5},
                    "label": [],
                },
                "link": {"source": [], "target": [], "value": []},
            }
            node_index = {}
            idx = 0

            for nn, concerts in common_nicknames.items():
                for i in range(len(concerts) - 1):
                    source = concerts[i]["concert"]
                    target = concerts[i + 1]["concert"]

                    if source not in node_index:
                        node_index[source] = idx
                        sankey_data["node"]["label"].append(source)
                        idx += 1
                    if target not in node_index:
                        node_index[target] = idx
                        sankey_data["node"]["label"].append(target)
                        idx += 1

                    sankey_data["link"]["source"].append(node_index[source])
                    sankey_data["link"]["target"].append(node_index[target])
                    sankey_data["link"]["value"].append(1)

            if sankey_data["node"]["label"]:
                filtered_common_nicknames[first_concert] = sankey_data

        # 닉네임 별 관람 패턴 (두 개 이상의 공연 관람한 경우만 수집)
        common_nicknames = {}
        for nn, cs in nickname_to_concerts.items():
            if len(cs) > 1:
                sorted_concs = sorted(cs)
                concert_dates = []
                for concert in sorted_concs:
                    first_review = (
                        reviews.filter(nickname=nn, concert__name=concert)
                        .order_by("date")
                        .first()
                    )
                    if first_review:
                        date_str = first_review.date.strftime("%Y-%m-%d")
                    else:
                        date_str = "Unknown"
                    concert_dates.append({"concert": concert, "date": date_str})
                # 날짜 기준 정렬
                concert_dates_sorted = sorted(concert_dates, key=lambda x: x["date"])
                common_nicknames[nn] = concert_dates_sorted

        # 관람 패턴(닉네임별 공연 목록) 내림차순 정렬
        sorted_common_nicknames = dict(
            sorted(common_nicknames.items(), key=lambda item: len(item[1]), reverse=True)
        )

        # 공연 조합별 분포 계산
        combination_counts = defaultdict(int)
        for concerts in nickname_to_concerts.values():
            for r in range(1, len(concerts) + 1):
                for combo in combinations(sorted(concerts), r):
                    combination_key = ", ".join(combo)
                    combination_counts[combination_key] += 1

        sorted_combinations = sorted(
            combination_counts.items(), key=lambda x: x[1], reverse=True
        )
        combination_counts_dict = dict(sorted_combinations)

        context.update({
            "filtered_common_nicknames": filtered_common_nicknames,
            "all_concerts": all_concerts,
            "common_nicknames": sorted_common_nicknames,
            "combination_counts": combination_counts_dict,
        })
        return context