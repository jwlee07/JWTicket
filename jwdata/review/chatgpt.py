from django.conf import settings

from django.shortcuts import redirect

import time

from review.models import Review
from django.db import transaction

from openai import OpenAI

client = OpenAI(api_key=settings.OPENAI_API_KEY)

def analyze_sentiment(review_text):
    prompt = f"""
    아래 리뷰의 감정을 분석해주세요. 
    결과는 '긍정', '중립', '부정' 중 하나로만 답변해주세요.

    리뷰 내용: {review_text}
    """
    
    response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "당신은 감정 분석 전문가입니다."},
            {"role": "user", "content": prompt}
        ],
        model="gpt-3.5-turbo",
    )
    
    sentiment = response.choices[0].message.content.strip()
    
    if "긍정" in sentiment:
        return "긍정"
    elif "중립" in sentiment:
        return "중립"
    elif "부정" in sentiment:
        return "부정"
    else:
        return None

def update_reviews_with_sentiment(request):
    sleep_time = 2
    max_updates = 5

    reviews_to_update = Review.objects.filter(emotion__isnull=True, description__isnull=False).exclude(description="")[:max_updates]

    if not reviews_to_update.exists():
        print("감정 분석이 필요한 리뷰가 없습니다.")
        return redirect("home")

    with transaction.atomic():
        for index, review in enumerate(reviews_to_update):
            if index >= max_updates:
                break

            sentiment = analyze_sentiment(review.description)
            if sentiment:
                review.emotion = sentiment
                review.save(update_fields=["emotion"])

            print(f"리뷰: {review.description} -> 감정: {sentiment}")
            time.sleep(sleep_time)

    print(f"{len(reviews_to_update)}개의 리뷰 감정 분석 완료 및 저장됨.")
    return redirect("home")
