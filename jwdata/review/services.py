from django.db.models import Avg, Count, F, Min
from django.db.models.functions import Cast, Concat, Length
from django.db.models import CharField, Value
from datetime import date, timedelta
from .models import Review, Concert, Seat
from .utils import preprocess_text, comma_format, clean_text
from collections import Counter, defaultdict
import pandas as pd
from konlpy.tag import Okt
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.cluster import KMeans
from itertools import combinations

class ConcertAnalysisService:
    def __init__(self, concert_id):
        self.concert = Concert.objects.get(id=concert_id)
        self.reviews = Review.objects.filter(concert_id=concert_id)

    def get_review_statistics(self):
        """공연의 기본 통계 정보를 가져옵니다."""
        # 선택된 공연 통계
        selected_stats = self.reviews.aggregate(
            avg_rating=Avg("star_rating"),
            total_reviews=Count("id")
        )
        
        # 전체 공연 통계
        overall_stats = Review.objects.aggregate(
            avg_rating=Avg("star_rating"),
            total_reviews=Count("id")
        )
        
        # 동일 장르 통계
        genre_reviews = Review.objects.filter(concert__genre=self.concert.genre)
        genre_stats = genre_reviews.aggregate(
            avg_rating=Avg("star_rating"),
            total_reviews=Count("id")
        )
        
        return {
            "selected": {
                "avg": (selected_stats["avg_rating"] or 0) * 2,
                "count": comma_format(selected_stats["total_reviews"] or 0)
            },
            "overall": {
                "avg": (overall_stats["avg_rating"] or 0) * 2,
                "count": comma_format(overall_stats["total_reviews"] or 0)
            },
            "genre": {
                "avg": (genre_stats["avg_rating"] or 0) * 2,
                "count": comma_format(genre_stats["total_reviews"] or 0)
            }
        }

    def generate_wordclouds(self):
        """감정별 워드클라우드를 생성합니다."""
        # 워드클라우드 기능 비활성화
        # 더미 데이터 반환
        positive_reviews = self.reviews.filter(emotion="긍정")
        negative_reviews = self.reviews.filter(emotion="부정")
        
        return {
            "all": "",
            "positive": "",
            "negative": "",
            "positive_reviews": positive_reviews.order_by("-date"),
            "negative_reviews": negative_reviews.order_by("-date")
        }

    def get_emotion_statistics(self):
        """감정 분석 통계를 가져옵니다."""
        emotion_counts = self.reviews.values("emotion").annotate(count=Count("id"))
        emotion_data = {"positive": 0, "negative": 0, "neutral": 0}
        
        for row in emotion_counts:
            if row["emotion"] == "긍정":
                emotion_data["positive"] = row["count"]
            elif row["emotion"] == "부정":
                emotion_data["negative"] = row["count"]
            elif row["emotion"] == "중립":
                emotion_data["neutral"] = row["count"]
                
        return emotion_data

    def get_review_trends(self):
        """리뷰가 존재하는 모든 날짜의 리뷰 추이 데이터를 가져옵니다."""
        # 날짜별 리뷰 수
        date_summary = (
            self.reviews
            .values("date")
            .annotate(reviews_count=Count("id"))
            .order_by("date")
            .annotate(date_str=Cast("date", output_field=CharField()))
            .values("date_str", "reviews_count")
        )
        
        # 날짜별 평균 평점
        date_rating_summary = (
            self.reviews
            .values("date")
            .annotate(average_rating=Avg("star_rating") * 2)
            .order_by("date")
            .annotate(date_str=Cast("date", output_field=CharField()))
            .values("date_str", "average_rating")
        )
        
        return {
            "review_counts": list(date_summary),
            "rating_averages": list(date_rating_summary)
        }

    def get_keywords_by_emotion(self):
        """감정별 주요 키워드를 추출합니다."""
        # 감정별 리뷰 분류
        all_reviews = self.reviews.values_list("description", flat=True)
        positive_reviews = self.reviews.filter(emotion="긍정").values_list("description", flat=True)
        negative_reviews = self.reviews.filter(emotion="부정").values_list("description", flat=True)
        
        # 각 감정별 키워드 추출
        def extract_keywords(reviews, top_n=10):
            if not reviews:
                return []
            
            try:
                # 텍스트 전처리
                processed_reviews = [clean_text(review) for review in reviews if review]
                if not processed_reviews:
                    return []
                
                text = " ".join(processed_reviews)
                if not text.strip():
                    return []
                
                # 불용어 설정
                stop_words = [
                    # 일반적인 불용어
                    "것", "등", "및", "에서", "그리고", "그런데", "하지만", "그래서", "때문에",
                    "이런", "저런", "이렇게", "저렇게", "매우", "정말", "진짜", "너무", "아주",
                    "거의", "모든", "어떤", "같은", "이런", "저런", "많은", "적은", "좀", "약간",
                    "다른", "어느", "바로", "정도", "대해", "통해", "더욱", "역시", "만약", "아마",
                    
                    # 시간 관련
                    "오늘", "내일", "모레", "어제", "그저께", "이번", "저번", "다음", "이전",
                    "올해", "작년", "내년", "최근", "요즘", "앞으로", "지금", "현재", "과거",
                    
                    # 문장 종결 표현
                    "입니다", "습니다", "었습니다", "였습니다", "합니다", "했습니다", "이에요",
                    "예요", "네요", "어요", "았어요", "였어요", "해요", "했어요",

                    "보고", "있는", "많이", "공연", "공연이", "긴긴밤", "긴긴밤을", "좋은",
                    "온더비트", "온더비트 온더비트", "비트", "비트 비트", "좋아요 좋아요", "이제",
                    "선택해서", "선택해서 관객들한테", "시키고", "으아아아아1인극 일다", "근데", "그냥", "시키는"
                ]
                
                # TF-IDF 벡터화 - 파라미터 조정
                tfidf = TfidfVectorizer(
                    ngram_range=(1, 2),  # 단일 단어와 두 단어 조합 모두 포함
                    min_df=1,  # 최소 1번 이상 등장한 단어 포함
                    max_df=1.0,  # max_df 제한 없음
                    max_features=50,  # 최대 50개의 특성만 사용
                    stop_words=stop_words  # 불용어 설정
                )
                
                X = tfidf.fit_transform([text])
                feature_names = tfidf.get_feature_names_out()
                scores = X.toarray()[0]
                
                # 점수가 높은 순으로 정렬
                keywords = [(feature_names[i], round(scores[i], 3)) 
                          for i in scores.argsort()[::-1][:top_n]]
                return keywords
            except Exception as e:
                print(f"키워드 추출 중 오류 발생: {str(e)}")
                return []
        
        return {
            "all": extract_keywords(all_reviews),
            "positive": extract_keywords(positive_reviews),
            "negative": extract_keywords(negative_reviews)
        }

class HomeAnalysisService:
    def __init__(self):
        self.reviews = Review.objects.all()
        self.concerts = Concert.objects.all()

    def get_genre_reviews(self):
        """장르별 리뷰 데이터를 가져옵니다."""
        return {
            "all": self.reviews.values_list("description", flat=True),
            "play": self.reviews.filter(concert__genre="연극").values_list("description", flat=True),
            "musical": self.reviews.filter(concert__genre="뮤지컬").values_list("description", flat=True),
            "concert": self.reviews.filter(concert__genre="콘서트").values_list("description", flat=True)
        }

    def generate_genre_wordclouds(self, reviews_by_genre):
        """장르별 워드클라우드를 생성합니다."""
        # 워드클라우드 기능 비활성화
        # 더미 데이터 반환
        wordclouds = {}
        for genre in reviews_by_genre.keys():
            wordclouds[genre] = ""
        return wordclouds

    def get_emotion_reviews(self, reviews_by_genre):
        """장르별 감정 리뷰를 가져옵니다."""
        emotion_reviews = {}
        for genre, base_query in [
            ("all", self.reviews),
            ("play", self.reviews.filter(concert__genre="연극")),
            ("musical", self.reviews.filter(concert__genre="뮤지컬")),
            ("concert", self.reviews.filter(concert__genre="콘서트"))
        ]:
            emotion_reviews[genre] = {
                "positive": base_query.filter(emotion="긍정").values_list("description", flat=True),
                "negative": base_query.filter(emotion="부정").values_list("description", flat=True)
            }
        return emotion_reviews

    def generate_emotion_wordclouds(self, emotion_reviews):
        """감정별 워드클라우드를 생성합니다."""
        # 워드클라우드 기능 비활성화
        # 더미 데이터 반환
        wordclouds = {}
        for genre, emotions in emotion_reviews.items():
            wordclouds[genre] = {}
            for emotion in emotions.keys():
                wordclouds[genre][emotion] = ""
        return wordclouds

    def get_statistics(self):
        """장르별 통계 정보를 가져옵니다."""
        stats = {}
        
        # 전체 통계
        overall_stats = self.reviews.aggregate(
            avg_rating=Avg('star_rating'),
            total_reviews=Count('id')
        )
        stats["all"] = {
            "avg": (overall_stats['avg_rating'] or 0) * 2,
            "count": comma_format(overall_stats['total_reviews'] or 0)
        }
        
        # 장르별 통계
        for genre, genre_name in [
            ("play", "연극"),
            ("musical", "뮤지컬"),
            ("concert", "콘서트")
        ]:
            genre_stats = self.reviews.filter(concert__genre=genre_name).aggregate(
                avg_rating=Avg('star_rating'),
                total_reviews=Count('id')
            )
            stats[genre] = {
                "avg": (genre_stats['avg_rating'] or 0) * 2,
                "count": comma_format(genre_stats['total_reviews'] or 0)
            }
            
        return stats

    def get_emotion_statistics(self):
        """장르별 감정 통계를 가져옵니다."""
        emotion_stats = {}
        
        # 전체 및 장르별 감정 통계
        for genre, base_query in [
            ("all", self.reviews),
            ("play", self.reviews.filter(concert__genre="연극")),
            ("musical", self.reviews.filter(concert__genre="뮤지컬")),
            ("concert", self.reviews.filter(concert__genre="콘서트"))
        ]:
            emotion_counts = base_query.values('emotion').annotate(count=Count('id'))
            emotion_dict = {'positive': 0, 'negative': 0, 'neutral': 0}
            
            for row in emotion_counts:
                if row['emotion'] == '긍정':
                    emotion_dict['positive'] = row['count']
                elif row['emotion'] == '부정':
                    emotion_dict['negative'] = row['count']
                elif row['emotion'] == '중립':
                    emotion_dict['neutral'] = row['count']
                    
            emotion_stats[genre] = emotion_dict
            
        return emotion_stats

    def get_concert_summary(self):
        """공연별 요약 정보를 가져옵니다."""
        all_reviews = self.reviews.all()
        
        # 공연별 요약
        concert_summary = (
            all_reviews.values("concert__name", "concert__place", "concert__genre",
                             "concert__start_date", "concert__end_date")
            .annotate(
                average_rating=Avg("star_rating") * 2,
                total_reviews=Count("id")
            )
            .order_by("-concert__end_date", "concert__name")
        )
        
        # 최근 30일 기준 날짜 계산
        thirty_days_ago = date.today() - timedelta(days=30)
        
        # 공연별 날짜별 리뷰 수
        concert_date_summary = {}
        concert_date_rating_summary = {}
        
        for concert in concert_summary:
            concert_name = concert["concert__name"]
            
            # 리뷰 수 집계
            date_summary = (
                all_reviews.filter(
                    concert__name=concert_name,
                    date__gte=thirty_days_ago
                )
                .values("date")
                .annotate(reviews_count=Count("id"))
                .order_by("-date")
                .annotate(date_str=Cast("date", output_field=CharField()))
                .values("date_str", "reviews_count")
            )
            concert_date_summary[concert_name] = list(date_summary)
            
            # 평균 평점 집계
            date_rating_summary = (
                all_reviews.filter(
                    concert__name=concert_name,
                    date__gte=thirty_days_ago
                )
                .values("date")
                .annotate(average_rating=Avg("star_rating") * 2)
                .order_by("-date")
                .annotate(date_str=Cast("date", output_field=CharField()))
                .values("date_str", "average_rating")
            )
            concert_date_rating_summary[concert_name] = list(date_rating_summary)
        
        return {
            "summary": concert_summary,
            "date_summary": concert_date_summary,
            "rating_summary": concert_date_rating_summary
        }

class ReviewAnalysisService:
    def __init__(self, concert_id):
        self.concert_id = concert_id
        self.reviews = Review.objects.filter(concert_id=concert_id)

    def get_long_reviews(self):
        """긴 리뷰들을 가져옵니다."""
        return (
            self.reviews
            .annotate(content_length=Length("description"))
            .order_by("-content_length")
            .exclude(description__icontains="뮤지컬 〈테일러〉")
        )

    def get_frequent_reviewers(self):
        """자주 리뷰를 작성한 사용자들의 정보를 가져옵니다."""
        frequent_reviewers = (
            self.reviews
            .values("nickname")
            .annotate(review_count=Count("id"))
            .filter(review_count__gt=1)
            .order_by("-review_count")
        )

        data = []
        for fr in frequent_reviewers:
            fr_reviews = self.reviews.filter(
                nickname=fr["nickname"]
            ).values("nickname", "description", "star_rating")
            data.append({
                "nickname": fr["nickname"],
                "review_count": fr["review_count"],
                "reviews": fr_reviews,
            })
        return data

    def get_frequent_words(self):
        """자주 등장하는 단어들을 분석합니다."""
        reviews = self.reviews.values_list("description", flat=True)
        text = " ".join(reviews)
        okt = Okt()
        stop_words = [
            "것", "정말", "노", "수", "이", "더", "보고", "진짜", "또", "그",
            "꼭", "테일러", "뮤지컬", "좀", "조금", "볼", "말", "은", "는",
            "이런", "그런", "저런", "그리고", "그러나", "그래서", "하지만",
            "그리고", "게다가", "다시", "계속", "정말", "너무", "많이", "많은",
            "모든", "합니다", "있어요", "없어요", "같아요", "보고", "봤습니다",
            "있습니다", "그렇죠", "맞아요", "아니요", "그래요", "배우", "스토리",
            "내용", "연기", "무대", "공연", "관람", "좋아요", "별점", "후기",
            "리뷰", "추천", "비추천",
        ]
        words = [w for w in okt.nouns(text) if w not in stop_words]
        return Counter(words).most_common(20)

    def get_frequent_words_mix(self):
        """자주 등장하는 단어 조합을 분석합니다."""
        reviews = list(self.reviews.values_list("description", flat=True))
        if not reviews:
            return []

        cleaned_reviews = [clean_text(r) for r in reviews]
        df = pd.DataFrame(cleaned_reviews, columns=["CONTENT"])

        stop_words = [
            "것", "정말", "노", "수", "이", "더", "보고", "진짜", "또", "그",
            "꼭", "테일러", "뮤지컬", "좀", "조금", "볼", "말", "은", "는",
            "이런", "그런", "저런", "그리고", "그러나", "그래서", "하지만",
            "게다가", "다시", "계속", "정말", "너무", "많이", "많은", "모든",
            "합니다", "있어요", "없어요", "같아요", "보고", "봤습니다",
            "있습니다", "그렇죠", "맞아요", "아니요", "그래요", "테일러뮤지컬",
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
        return list(dtm_sum.items())

    def get_frequent_words_important(self):
        """TF-IDF를 사용하여 중요한 단어 조합을 분석합니다."""
        reviews = list(self.reviews.values_list("description", flat=True))
        if not reviews:
            return []

        cleaned_reviews = [clean_text(r) for r in reviews]
        df = pd.DataFrame(cleaned_reviews, columns=["CONTENT"])

        stop_words = [
            "것", "정말", "노", "수", "이", "더", "보고", "진짜", "또", "그",
            "꼭", "테일러", "뮤지컬", "좀", "조금", "볼", "말", "은", "는",
            "이런", "그런", "저런", "그리고", "그러나", "그래서", "하지만",
            "게다가", "다시", "계속", "정말", "너무", "많이", "많은", "모든",
            "합니다", "있어요", "없어요", "같아요", "보고", "봤습니다",
            "있습니다", "그렇죠", "맞아요", "아니요", "그래요", "테일러뮤지컬",
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
        return [(word, round(val, 2)) for word, val in tfidf_sum.items()]

    def get_similar_reviews(self):
        """KMeans 클러스터링을 사용하여 비슷한 리뷰들을 그룹화합니다."""
        reviews = list(self.reviews.values("nickname", "description"))
        if not reviews:
            return {}

        df = pd.DataFrame(reviews)
        df["CLEANED_CONTENT"] = df["description"].apply(clean_text)
        tfidf_vectorizer = TfidfVectorizer()
        review_dtm = tfidf_vectorizer.fit_transform(df["CLEANED_CONTENT"])

        kmeans = KMeans(n_clusters=10, n_init="auto", random_state=42)
        kmeans.fit(review_dtm)
        df["CLUSTER"] = kmeans.labels_

        return df.groupby("CLUSTER").apply(
            lambda g: [
                {"nickname": row["nickname"], "content": row["CLEANED_CONTENT"]}
                for _, row in g.iterrows()
            ]
        ).to_dict()

    def get_top_view_count_reviews(self):
        """조회수가 높은 리뷰들을 가져옵니다."""
        return self.reviews.order_by("-view_count")

    def get_low_star_rating_reviews(self):
        """낮은 평점의 리뷰들을 가져옵니다."""
        reviews = self.reviews.filter(star_rating__lte=3).order_by("star_rating")
        return [r for r in reviews if "뮤지컬 〈테일러〉" not in r.description]

class AllAnalysisService:
    def __init__(self):
        self.reviews = Review.objects.all().select_related("concert")
        self.seats = Seat.objects.all()
        self.concerts = Concert.objects.all()

    def get_filtered_reviews(self, start_date=None, end_date=None):
        """날짜 범위로 필터링된 리뷰를 반환합니다."""
        reviews = self.reviews
        if start_date and end_date:
            reviews = reviews.filter(date__range=[start_date, end_date])
        return reviews

    def get_review_summary(self, reviews):
        """리뷰 요약 정보를 가져옵니다."""
        # 공연별 요약
        concert_summary = (
            reviews.values("concert__name", "concert__place")
            .annotate(
                average_rating=Avg("star_rating"),
                total_reviews=Count("id")
            )
            .order_by("concert__name")
        )

        # 공연별 날짜별 리뷰 수와 평균 평점
        concert_date_summary = {}
        concert_date_rating_summary = {}
        
        for concert in concert_summary:
            concert_name = concert["concert__name"]
            concert_reviews = reviews.filter(concert__name=concert_name)
            
            concert_date_summary[concert_name] = (
                concert_reviews
                .values("date")
                .annotate(reviews_count=Count("id"))
                .order_by("-date")
            )
            
            concert_date_rating_summary[concert_name] = (
                concert_reviews
                .values("date")
                .annotate(average_rating=Avg("star_rating"))
                .order_by("-date")
            )

        return {
            "concert_summary": concert_summary,
            "date_summary": concert_date_summary,
            "rating_summary": concert_date_rating_summary
        }

    def get_viewer_patterns(self, reviews):
        """관람객 패턴을 분석합니다."""
        # 닉네임별 관람 공연 정보 수집
        nicknames = (
            reviews.values("nickname", "concert__name")
            .annotate(first_date=Min("date"))
            .distinct()
        )
        
        nickname_to_concerts = defaultdict(list)
        for n in nicknames:
            nickname_to_concerts[n["nickname"]].append({
                "concert__name": n["concert__name"],
                "first_date": n["first_date"].strftime("%Y-%m-%d")
            })

        # 2개 이상 공연을 본 관람객 필터링
        common_nicknames = {
            nn: sorted(cs, key=lambda x: x["first_date"])
            for nn, cs in nickname_to_concerts.items()
            if len(cs) > 1
        }

        return dict(
            sorted(common_nicknames.items(), key=lambda i: len(i[1]), reverse=True)
        )

    def get_concert_combinations(self, reviews):
        """공연 조합별 관람객 수를 분석합니다."""
        concerts_with_nicknames = reviews.values("concert__name", "nickname").distinct()
        concert_to_nicknames = defaultdict(set)
        
        for entry in concerts_with_nicknames:
            concert_to_nicknames[entry["concert__name"]].add(entry["nickname"])

        all_concerts = list(concert_to_nicknames.keys())
        combination_counts = {}
        
        for r in range(1, len(all_concerts) + 1):
            for combo in combinations(all_concerts, r):
                intersected = set.intersection(
                    *(concert_to_nicknames[c] for c in combo)
                )
                combination_counts[", ".join(combo)] = len(intersected)

        return combination_counts

    def get_review_data(self, reviews):
        """전체 리뷰 데이터를 테이블 형태로 반환합니다."""
        return [{
            "공연명": r.concert.name,
            "장소": r.concert.place,
            "작성자": r.nickname,
            "작성일": r.date,
            "평점": r.star_rating,
            "제목": r.title,
            "내용": r.description,
            "조회수": r.view_count,
            "좋아요": r.like_count,
        } for r in reviews]

    def get_seat_data(self, concert_name=None):
        """좌석 데이터를 분석합니다."""
        # 날짜 필드 생성
        seats_with_date = self.seats.annotate(
            date=Concat(
                Cast(F("year"), output_field=CharField()),
                Value("-"),
                Cast(F("month"), output_field=CharField()),
                Value("-"),
                Cast(F("day_num"), output_field=CharField()),
            )
        )

        # 공연 필터링
        if concert_name:
            seats_with_date = seats_with_date.filter(concert__name=concert_name)

        # 데이터 정렬 및 필드 선택
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

        return {
            "seat_data": seat_data,
            "all_concerts": self.concerts.values_list("name", flat=True).distinct().order_by("name"),
            "unique_rounds": self.seats.values_list("round_name", flat=True).distinct().order_by("round_name")
        }

    def get_pattern_analysis(self):
        """관람 패턴을 분석합니다."""
        # 닉네임별 공연 정보 수집
        nicknames = (
            self.reviews.values("nickname", "concert__name")
            .annotate(first_date=Min("date"))
            .distinct()
        )
        
        nickname_to_concerts = defaultdict(set)
        for n in nicknames:
            nickname_to_concerts[n["nickname"]].add(n["concert__name"])

        all_concerts = list(set(self.reviews.values_list("concert__name", flat=True)))
        filtered_common_nicknames = {}

        # 각 공연별 관람 패턴 분석
        for first_concert in all_concerts:
            common_nicknames = {}
            for nn, cs in nickname_to_concerts.items():
                if first_concert in cs and len(cs) > 1:
                    sorted_concs = sorted(cs)
                    concert_dates = []
                    for concert in sorted_concs:
                        first_review = (
                            self.reviews.filter(nickname=nn, concert__name=concert)
                            .order_by("date")
                            .first()
                        )
                        date_str = first_review.date.strftime("%Y-%m-%d") if first_review else "Unknown"
                        concert_dates.append({"concert": concert, "date": date_str})
                    
                    concert_dates_sorted = sorted(concert_dates, key=lambda x: x["date"])
                    if concert_dates_sorted[0]["concert"] == first_concert:
                        common_nicknames[nn] = concert_dates_sorted

            # 샌키 다이어그램 데이터 생성
            sankey_data = self._generate_sankey_data(common_nicknames)
            if sankey_data["node"]["label"]:
                filtered_common_nicknames[first_concert] = sankey_data

        return {
            "filtered_common_nicknames": filtered_common_nicknames,
            "all_concerts": all_concerts
        }

    def _generate_sankey_data(self, common_nicknames):
        """샌키 다이어그램 데이터를 생성합니다."""
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

        return sankey_data 