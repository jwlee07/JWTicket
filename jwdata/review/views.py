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

import time

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

from .chatgpt import update_reviews_with_sentiment

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

# ==================================================================
# chatgpt
# ==================================================================

def update_sentiment_view(request):
    update_reviews_with_sentiment()
    return redirect('home')


# ==================================================================
# Analysis
# ==================================================================

@login_required
def concert_detail(request):
    # URL 쿼리스트링에서 공연 id를 가져옴
    concert_id = request.GET.get("concert_id")
    if not concert_id:
        return redirect("home")
    
    # 선택된 공연 객체 가져오기
    concert = get_object_or_404(Concert, id=concert_id)
    
    # 선택된 공연 리뷰
    reviews = Review.objects.filter(concert=concert)
    
    # 선택된 공연의 리뷰 통계
    selected_stats = reviews.aggregate(avg_rating=Avg("star_rating"), total_reviews=Count("id"))
    selected_avg = selected_stats["avg_rating"] or 0
    selected_count = selected_stats["total_reviews"] or 0

    # 전체 공연의 리뷰 통계
    overall_stats = Review.objects.aggregate(avg_rating=Avg("star_rating"), total_reviews=Count("id"))
    overall_avg = overall_stats["avg_rating"] or 0
    overall_count = overall_stats["total_reviews"] or 0

    # 선택된 공연과 동일 장르의 리뷰 통계
    genre_reviews = Review.objects.filter(concert__genre=concert.genre)
    genre_stats = genre_reviews.aggregate(avg_rating=Avg("star_rating"), total_reviews=Count("id"))
    genre_avg = genre_stats["avg_rating"] or 0
    genre_count = genre_stats["total_reviews"] or 0

    # 워드클라우드 및 감정 데이터 (선택된 공연 리뷰 기준)
    all_reviews_texts = reviews.values_list("description", flat=True)
    text_all = preprocess_text(all_reviews_texts)
    img_all = generate_wordcloud_image(text_all, wc_width=1200, wc_height=600, fig_width=12, fig_height=6)
    
    positive_reviews = reviews.filter(emotion="긍정").values_list("description", flat=True)
    text_positive = preprocess_text(positive_reviews)
    img_positive = generate_wordcloud_image(text_positive, wc_width=1200, wc_height=600, fig_width=12, fig_height=6)
    
    negative_reviews = reviews.filter(emotion="부정").values_list("description", flat=True)
    text_negative = preprocess_text(negative_reviews)
    img_negative = generate_wordcloud_image(text_negative, wc_width=1200, wc_height=600, fig_width=12, fig_height=6)
    
    # 감정 데이터 (선택된 공연 리뷰 기준)
    emotion_counts = reviews.values('emotion').annotate(count=Count('id'))
    emotion_data = {"positive": 0, "negative": 0, "neutral": 0}
    for row in emotion_counts:
        if row["emotion"] == "긍정":
            emotion_data["positive"] = row["count"]
        elif row["emotion"] == "부정":
            emotion_data["negative"] = row["count"]
        elif row["emotion"] == "중립":
            emotion_data["neutral"] = row["count"]

    context = {
        "selected_concert": concert,
        "reviews": reviews,
        "selected_avg": selected_avg * 2,
        "selected_count": comma_format(selected_count),
        "overall_avg": overall_avg * 2,
        "overall_count": comma_format(overall_count),
        "genre_avg": genre_avg * 2,
        "genre_count": comma_format(genre_count),
        "img_all": img_all,
        "img_positive": img_positive,
        "img_negative": img_negative,
        "emotion": emotion_data,
    }
    return render(request, "review/review_concert_detail.html", context)

@login_required
def home(request):
    concerts = Concert.objects.all()
    active_concert_id = request.GET.get("active_concert_id")

    # 모든 리뷰
    all_reviews = Review.objects.all().values_list("description", flat=True)
    play_reviews = Review.objects.filter(concert__genre="연극").values_list("description", flat=True)
    musical_reviews = Review.objects.filter(concert__genre="뮤지컬").values_list("description", flat=True)
    concert_reviews = Review.objects.filter(concert__genre="콘서트").values_list("description", flat=True)

    text_all = preprocess_text(all_reviews)
    text_play = preprocess_text(play_reviews)
    text_musical = preprocess_text(musical_reviews)
    text_concert = preprocess_text(concert_reviews)

    img_all = generate_wordcloud_image(text_all, wc_width=1200, wc_height=600, fig_width=12, fig_height=6)
    img_play = generate_wordcloud_image(text_play, wc_width=1200, wc_height=600, fig_width=12, fig_height=6)
    img_musical = generate_wordcloud_image(text_musical, wc_width=1200, wc_height=600, fig_width=12, fig_height=6)
    img_concert = generate_wordcloud_image(text_concert, wc_width=1200, wc_height=600, fig_width=12, fig_height=6)

    # 긍정/부정 리뷰 필터링 (전체)
    all_reviews_positive = Review.objects.filter(emotion="긍정").values_list("description", flat=True)
    all_reviews_negative = Review.objects.filter(emotion="부정").values_list("description", flat=True)
    text_all_positive = preprocess_text(all_reviews_positive)
    text_all_negative = preprocess_text(all_reviews_negative)
    img_all_positive = generate_wordcloud_image(text_all_positive, wc_width=1200, wc_height=600, fig_width=12, fig_height=6)
    img_all_negative = generate_wordcloud_image(text_all_negative, wc_width=1200, wc_height=600, fig_width=12, fig_height=6)

    # 긍정/부정 리뷰 필터링 (연극)
    play_reviews_positive = Review.objects.filter(concert__genre="연극", emotion="긍정").values_list("description", flat=True)
    play_reviews_negative = Review.objects.filter(concert__genre="연극", emotion="부정").values_list("description", flat=True)
    text_play_positive = preprocess_text(play_reviews_positive)
    text_play_negative = preprocess_text(play_reviews_negative)
    img_play_positive = generate_wordcloud_image(text_play_positive, wc_width=1200, wc_height=600, fig_width=12, fig_height=6)
    img_play_negative = generate_wordcloud_image(text_play_negative, wc_width=1200, wc_height=600, fig_width=12, fig_height=6)

    # 긍정/부정 리뷰 필터링 (뮤지컬)
    musical_reviews_positive = Review.objects.filter(concert__genre="뮤지컬", emotion="긍정").values_list("description", flat=True)
    musical_reviews_negative = Review.objects.filter(concert__genre="뮤지컬", emotion="부정").values_list("description", flat=True)
    text_musical_positive = preprocess_text(musical_reviews_positive)
    text_musical_negative = preprocess_text(musical_reviews_negative)
    img_musical_positive = generate_wordcloud_image(text_musical_positive, wc_width=1200, wc_height=600, fig_width=12, fig_height=6)
    img_musical_negative = generate_wordcloud_image(text_musical_negative, wc_width=1200, wc_height=600, fig_width=12, fig_height=6)

    # 긍정/부정 리뷰 필터링 (콘서트)
    concert_reviews_positive = Review.objects.filter(concert__genre="콘서트", emotion="긍정").values_list("description", flat=True)
    concert_reviews_negative = Review.objects.filter(concert__genre="콘서트", emotion="부정").values_list("description", flat=True)
    text_concert_positive = preprocess_text(concert_reviews_positive)
    text_concert_negative = preprocess_text(concert_reviews_negative)
    img_concert_positive = generate_wordcloud_image(text_concert_positive, wc_width=1200, wc_height=600, fig_width=12, fig_height=6)
    img_concert_negative = generate_wordcloud_image(text_concert_negative, wc_width=1200, wc_height=600, fig_width=12, fig_height=6)

    # 평점 관련 통계
    overall_stats = Review.objects.aggregate(avg_rating=Avg('star_rating'), total_reviews=Count('id'))
    avg_all = overall_stats['avg_rating'] * 2 if overall_stats['avg_rating'] else 0
    count_all = comma_format(overall_stats['total_reviews'] or 0)

    play_stats = Review.objects.filter(concert__genre='연극').aggregate(avg_rating=Avg('star_rating'), total_reviews=Count('id'))
    avg_play = (play_stats['avg_rating'] * 2) if play_stats['avg_rating'] else 0
    count_play = comma_format(play_stats['total_reviews'] or 0)

    musical_stats = Review.objects.filter(concert__genre='뮤지컬').aggregate(avg_rating=Avg('star_rating'), total_reviews=Count('id'))
    avg_musical = (musical_stats['avg_rating'] * 2) if musical_stats['avg_rating'] else 0
    count_musical = comma_format(musical_stats['total_reviews'] or 0)

    concert_stats = Review.objects.filter(concert__genre='콘서트').aggregate(avg_rating=Avg('star_rating'), total_reviews=Count('id'))
    avg_concert = (concert_stats['avg_rating'] * 2) if concert_stats['avg_rating'] else 0
    count_concert = comma_format(concert_stats['total_reviews'] or 0)

    # 감정 카운트
    overall_emotion_counts = Review.objects.values('emotion').annotate(count=Count('id'))
    emotion_dict_all = {'positive': 0, 'negative': 0, 'neutral': 0}
    for row in overall_emotion_counts:
        if row['emotion'] == '긍정':
            emotion_dict_all['positive'] = row['count']
        elif row['emotion'] == '부정':
            emotion_dict_all['negative'] = row['count']
        elif row['emotion'] == '중립':
            emotion_dict_all['neutral'] = row['count']

    play_emotion_counts = Review.objects.filter(concert__genre='연극').values('emotion').annotate(count=Count('id'))
    emotion_dict_play = {'positive': 0, 'negative': 0, 'neutral': 0}
    for row in play_emotion_counts:
        if row['emotion'] == '긍정':
            emotion_dict_play['positive'] = row['count']
        elif row['emotion'] == '부정':
            emotion_dict_play['negative'] = row['count']
        elif row['emotion'] == '중립':
            emotion_dict_play['neutral'] = row['count']

    musical_emotion_counts = Review.objects.filter(concert__genre='뮤지컬').values('emotion').annotate(count=Count('id'))
    emotion_dict_musical = {'positive': 0, 'negative': 0, 'neutral': 0}
    for row in musical_emotion_counts:
        if row['emotion'] == '긍정':
            emotion_dict_musical['positive'] = row['count']
        elif row['emotion'] == '부정':
            emotion_dict_musical['negative'] = row['count']
        elif row['emotion'] == '중립':
            emotion_dict_musical['neutral'] = row['count']

    concert_emotion_counts = Review.objects.filter(concert__genre='콘서트').values('emotion').annotate(count=Count('id'))
    emotion_dict_concert = {'positive': 0, 'negative': 0, 'neutral': 0}
    for row in concert_emotion_counts:
        if row['emotion'] == '긍정':
            emotion_dict_concert['positive'] = row['count']
        elif row['emotion'] == '부정':
            emotion_dict_concert['negative'] = row['count']
        elif row['emotion'] == '중립':
            emotion_dict_concert['neutral'] = row['count']

    context = {
        "concerts": concerts,
        "active_concert_id": active_concert_id,

        "img_all": img_all,
        "img_play": img_play,
        "img_musical": img_musical,
        "img_concert": img_concert,

        "img_all_positive": img_all_positive,
        "img_all_negative": img_all_negative,
        "img_play_positive": img_play_positive,
        "img_play_negative": img_play_negative,
        "img_musical_positive": img_musical_positive,
        "img_musical_negative": img_musical_negative,
        "img_concert_positive": img_concert_positive,
        "img_concert_negative": img_concert_negative,

        "avg_all": avg_all,
        "count_all": count_all,
        "avg_play": avg_play,
        "count_play": count_play,
        "avg_musical": avg_musical,
        "count_musical": count_musical,
        "avg_concert": avg_concert,
        "count_concert": count_concert,

        "emotion_all": emotion_dict_all,
        "emotion_play": emotion_dict_play,
        "emotion_musical": emotion_dict_musical,
        "emotion_concert": emotion_dict_concert,
    }

    return render(request, "review/index.html", context)

@login_required
def analyze_reviews(request, concert_id, analysis_type):
    # 길게 남긴 리뷰 (공연 ID 필터링 및 내용 길이 기준 정렬)
    if analysis_type == "long_reviews":
        data = (
            Review.objects.filter(concert_id=concert_id)
            .annotate(content_length=Length("description"))
            .order_by("-content_length")
            .exclude(description__icontains="뮤지컬 〈테일러〉")
        )

    # 여러 번 리뷰를 작성한 고객
    elif analysis_type == "frequent_reviewers":
        frequent_reviewers = (
            Review.objects.filter(concert_id=concert_id)
            .values("nickname")
            .annotate(review_count=Count("id"))
            .filter(review_count__gt=1)
            .order_by("-review_count")
        )

        data = []
        for fr in frequent_reviewers:
            fr_reviews = Review.objects.filter(
                concert_id=concert_id, nickname=fr["nickname"]
            ).values("nickname", "description", "star_rating")
            data.append(
                {
                    "nickname": fr["nickname"],
                    "review_count": fr["review_count"],
                    "reviews": fr_reviews,
                }
            )

    # 단어 빈도 분석
    elif analysis_type == "frequent_words":
        reviews = Review.objects.filter(concert_id=concert_id).values_list(
            "description", flat=True
        )
        text = " ".join(reviews)
        okt = Okt()
        stop_words = [
            "것",
            "정말",
            "노",
            "수",
            "이",
            "더",
            "보고",
            "진짜",
            "또",
            "그",
            "꼭",
            "테일러",
            "뮤지컬",
            "좀",
            "조금",
            "볼",
            "말",
            "은",
            "는",
            "이런",
            "그런",
            "저런",
            "그리고",
            "그러나",
            "그래서",
            "하지만",
            "그리고",
            "게다가",
            "다시",
            "계속",
            "정말",
            "너무",
            "많이",
            "많은",
            "모든",
            "합니다",
            "있어요",
            "없어요",
            "같아요",
            "보고",
            "봤습니다",
            "있습니다",
            "그렇죠",
            "맞아요",
            "아니요",
            "그래요",
            "배우",
            "스토리",
            "내용",
            "연기",
            "무대",
            "공연",
            "관람",
            "좋아요",
            "별점",
            "후기",
            "리뷰",
            "추천",
            "비추천",
        ]
        words = [w for w in okt.nouns(text) if w not in stop_words]
        data = Counter(words).most_common(20)

    # 단어 조합 빈도
    elif analysis_type == "frequent_words_mix":
        reviews = list(
            Review.objects.filter(concert_id=concert_id).values_list(
                "description", flat=True
            )
        )
        if not reviews:
            data = []
        else:
            cleaned_reviews = [clean_text(r) for r in reviews]
            df = pd.DataFrame(cleaned_reviews, columns=["CONTENT"])

            stop_words = [
                "것",
                "정말",
                "노",
                "수",
                "이",
                "더",
                "보고",
                "진짜",
                "또",
                "그",
                "꼭",
                "테일러",
                "뮤지컬",
                "좀",
                "조금",
                "볼",
                "말",
                "은",
                "는",
                "이런",
                "그런",
                "저런",
                "그리고",
                "그러나",
                "그래서",
                "하지만",
                "게다가",
                "다시",
                "계속",
                "정말",
                "너무",
                "많이",
                "많은",
                "모든",
                "합니다",
                "있어요",
                "없어요",
                "같아요",
                "보고",
                "봤습니다",
                "있습니다",
                "그렇죠",
                "맞아요",
                "아니요",
                "그래요",
                "테일러뮤지컬",
            ]

            cvect = CountVectorizer(
                ngram_range=(2, 6),
                min_df=2,
                max_df=0.9,
                max_features=50,
                stop_words=stop_words,
            )
            X = cvect.fit_transform(df["CONTENT"])
            dtm = pd.DataFrame(X.toarray(), columns=cvect.get_feature_names_out())
            dtm_sum = dtm.sum().sort_values(ascending=False)
            data = list(dtm_sum.items())

    # 단어 조합 중요도(TFIDF)
    elif analysis_type == "frequent_words_important":
        reviews = list(
            Review.objects.filter(concert_id=concert_id).values_list(
                "description", flat=True
            )
        )
        if not reviews:
            data = []
        else:
            cleaned_reviews = [clean_text(r) for r in reviews]
            df = pd.DataFrame(cleaned_reviews, columns=["CONTENT"])

            stop_words = [
                "것",
                "정말",
                "노",
                "수",
                "이",
                "더",
                "보고",
                "진짜",
                "또",
                "그",
                "꼭",
                "테일러",
                "뮤지컬",
                "좀",
                "조금",
                "볼",
                "말",
                "은",
                "는",
                "이런",
                "그런",
                "저런",
                "그리고",
                "그러나",
                "그래서",
                "하지만",
                "게다가",
                "다시",
                "계속",
                "정말",
                "너무",
                "많이",
                "많은",
                "모든",
                "합니다",
                "있어요",
                "없어요",
                "같아요",
                "보고",
                "봤습니다",
                "있습니다",
                "그렇죠",
                "맞아요",
                "아니요",
                "그래요",
                "테일러뮤지컬",
            ]

            tfidf = TfidfVectorizer(
                ngram_range=(2, 6),
                min_df=2,
                max_df=0.9,
                max_features=50,
                stop_words=stop_words,
            )
            X = tfidf.fit_transform(df["CONTENT"])
            tfidf_df = pd.DataFrame(X.toarray(), columns=tfidf.get_feature_names_out())
            tfidf_sum = tfidf_df.sum().sort_values(ascending=False)
            data = [(word, round(val, 2)) for word, val in tfidf_sum.items()]

    # 비슷한 리뷰(KMeans 클러스터링)
    elif analysis_type == "similar_reviews":
        reviews = list(
            Review.objects.filter(concert_id=concert_id).values(
                "nickname", "description"
            )
        )
        if not reviews:
            data = {}
        else:
            df = pd.DataFrame(reviews)
            df["CLEANED_CONTENT"] = df["description"].apply(clean_text)
            tfidf_vectorizer = TfidfVectorizer()
            review_dtm = tfidf_vectorizer.fit_transform(df["CLEANED_CONTENT"])

            kmeans = KMeans(n_clusters=10, n_init="auto", random_state=42)
            kmeans.fit(review_dtm)
            df["CLUSTER"] = kmeans.labels_

            data = (
                df.groupby("CLUSTER")
                .apply(
                    lambda g: [
                        {"nickname": row["nickname"], "content": row["CLEANED_CONTENT"]}
                        for _, row in g.iterrows()
                    ]
                )
                .to_dict()
            )

    # 조회수 높은 리뷰
    elif analysis_type == "top_view_count_reviews":
        data = Review.objects.filter(concert_id=concert_id).order_by("-view_count")

    # 평점 3점 이하 리뷰
    elif analysis_type == "low_star_rating_reviews":
        reviews = Review.objects.filter(
            concert_id=concert_id, star_rating__lte=3
        ).order_by("star_rating")
        data = [r for r in reviews if "뮤지컬 〈테일러〉" not in r.description]

    else:
        data = []

    return render(
        request, "review/analysis.html", {"data": data, "analysis_type": analysis_type}
    )


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
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            # messages.success(request, f"{username} 님, 반가워요!")
            return redirect("home")
        else:
            messages.error(request, "티켓스퀘어 PM 이진욱님에게 문의하세요:)")
            return render(request, "review/login.html")
    else:
        return render(request, "review/login.html")


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
    plt.imshow(wordcloud, interpolation="bilinear")
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

        # 불용어(stopwords)가 있다면 여기서 제거 (선택)
        stop_words = {'이','것','정말','너무','그리고'}
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
