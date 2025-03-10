import openai
import time
from django.conf import settings
from review.models import Review
from django.db import transaction

openai.api_key = settings.OPENAI_API_KEY

def analyze_sentiment(review_text):
    prompt = f"""
    아래 리뷰의 감정을 분석해주세요. 
    결과는 '긍정', '중립', '부정' 중 하나로만 답변해주세요.

    리뷰 내용: {review_text}
    """

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "당신은 감정 분석 전문가입니다."},
            {"role": "user", "content": prompt}
        ]
    )

    sentiment = response["choices"][0]["message"]["content"].strip()

    if "긍정" in sentiment:
        return "긍정"
    elif "중립" in sentiment:
        return "중립"
    elif "부정" in sentiment:
        return "부정"
    else:
        return None

def update_reviews_with_sentiment(sleep_time=2):
    reviews_to_update = Review.objects.filter(emotion__isnull=True, description__isnull=False).exclude(description="")

    if not reviews_to_update.exists():
        print("감정 분석이 필요한 리뷰가 없습니다.")
        return

    with transaction.atomic():
        for review in reviews_to_update:
            sentiment = analyze_sentiment(review.description)
            if sentiment:
                review.emotion = sentiment
                review.save(update_fields=["emotion"])
            
            print(f"'{review.title}' 리뷰의 감정 분석 완료: {sentiment}")
            
            # API 요청 간격 조절 (기본값: 1초)
            time.sleep(sleep_time)

    print(f"{reviews_to_update.count()}개의 리뷰 감정 분석 완료 및 저장됨.")
