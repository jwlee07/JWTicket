from django.conf import settings
from django.shortcuts import render, redirect
import time
from review.models import Review
from django.db import transaction
from openai import OpenAI

client = OpenAI(api_key=settings.OPENAI_API_KEY)

def analyze_sentiment(review_text):
    prompt = f"""
    아래 공연 리뷰의 감정을 분석해주세요.
    공연 리뷰라는 것을 명심해주세요.
    공연은 감동을 받거나 눈물을 흘리는 것은 긍정적인 감정일 수 있어요.
    결과는 '긍정', '중립', '부정' 중 하나로만 답변해주세요.

    리뷰 내용: {review_text}
    """
    
    response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "당신은 공연 리뷰 감정 분석 전문가입니다."},
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

    reviews_to_update = Review.objects.filter(emotion__isnull=True, description__isnull=False).exclude(description="")

    if not reviews_to_update.exists():
        print("감정 분석이 필요한 리뷰가 없습니다.")
        return redirect("home")

    with transaction.atomic():
        total_count = reviews_to_update.count()
        for index, review in enumerate(reviews_to_update):
            sentiment = analyze_sentiment(review.description)
            if sentiment:
                review.emotion = sentiment
                review.save(update_fields=["emotion"])
            print(f"[{index}/{total_count}] 공연 명: {review.concert} 리뷰: {review.title} >>> 감정: {sentiment}")
            time.sleep(sleep_time)

    print(f"{len(reviews_to_update)}개의 리뷰 감정 분석 완료 및 저장됨.")
    return redirect("home")

def summarize_positive_reviews(request, concert_id):
    positive_reviews = Review.objects.filter(
        concert_id=concert_id,
        emotion="긍정",
        description__isnull=False
    ).exclude(description="").order_by("-date")[:30]
    
    if not positive_reviews:
        print("분석할 긍정 리뷰가 없습니다.")
        return redirect("home")
    
    # 긍정 리뷰 내용 합치기
    positive_text = "\n\n".join([review.description for review in positive_reviews])
    
    # 긍정 리뷰 요약 및 개선점 프롬프트 구성
    prompt_positive = f"""
    아래는 선택된 공연의 최근 30개의 긍정 리뷰입니다.
    긍정적인 부분을 더욱 강조하고, 개선할 점을 찾아주세요.
    볼드체나 이모티콘은 사용하지 마세요.
    이 리뷰들을 요약하고, 공연을 더욱 발전시킬 수 있는 개선점 3가지를 제안해주세요.
    리뷰 내용:
    {positive_text}
    """
    
    response_positive = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "당신은 공연 리뷰 분석 전문가입니다."},
            {"role": "user", "content": prompt_positive}
        ],
        model="gpt-3.5-turbo",
    )
    result_positive = response_positive.choices[0].message.content.strip()
    
    context = {
        "result_positive": result_positive,
        "positive_reviews": positive_reviews,
    }
    return render(request, "review/summarized_positive_reviews.html", context)

def summarize_negative_reviews(request, concert_id):
    negative_reviews = Review.objects.filter(
        concert_id=concert_id,
        emotion="부정",
        description__isnull=False
    ).exclude(description="").order_by("-date")[:30]
    
    if not negative_reviews:
        print("분석할 부정 리뷰가 없습니다.")
        return redirect("home")
    
    # 부정 리뷰 내용 합치기
    negative_text = "\n\n".join([review.description for review in negative_reviews])
    
    # 부정 리뷰 요약 및 개선점 프롬프트 구성
    prompt_negative = f"""
    아래는 선택된 공연의 최근 30개의 부정 리뷰입니다.
    부정적인 부분을 더욱 강조하고, 개선할 점을 찾아주세요.
    볼드체나 이모티콘은 사용하지 마세요.
    이 리뷰들을 요약하고, 부정 리뷰 개선을 위한 3가지 개선점을 제안해주세요.
    리뷰 내용:
    {negative_text}
    """
    
    response_negative = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "당신은 공연 리뷰 분석 전문가입니다."},
            {"role": "user", "content": prompt_negative}
        ],
        model="gpt-3.5-turbo",
    )
    result_negative = response_negative.choices[0].message.content.strip()
    
    context = {
        "result_negative": result_negative,
        "negative_reviews": negative_reviews,
    }
    return render(request, "review/summarized_negative_reviews.html", context)