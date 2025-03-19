from django.conf import settings
from django.shortcuts import render, redirect
from django.db import transaction

import time

from review.models import Review

from openai import OpenAI

from review.slacks import chatgpt_review_send_slack_message

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
    
    # 응답 후 로그 출력
    print("analyze_sentiment 응답:")
    print(response)
    
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
        print(f"총 {total_count}개의 리뷰에 대해 감정 분석을 시작합니다.")
        for index, review in enumerate(reviews_to_update):
            sentiment = analyze_sentiment(review.description)
            if sentiment:
                review.emotion = sentiment
                review.save(update_fields=["emotion"])
            print(f"[{index+1}/{total_count}] 공연 명: {review.concert} / 리뷰 제목: {review.title} >>> 감정: {sentiment}")
            time.sleep(sleep_time)

    print(f"{total_count}개의 리뷰 감정 분석 완료 및 저장됨.")
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
    아래는 공연의 최근 긍정 리뷰입니다.
    긍정 리뷰를 요약하고 긍정적인 영역을 더욱 발전시킬 수 있는 인사이트를 3개 제안해주세요.
    아래 예시 형식을 지켜주세요.

    예시 형식:
    1. 요약
    - 최대 3줄 이내로 요약
    2. 인사이트
    - 3가지 항목 제안

    추가 조건:
    - 볼드체(**)나 이모티콘을 사용하지 마세요.
    - 공연의 긍정적인 특성을 강조하면서, 더 발전시킬 수 있는 아이디어를 제시해주세요.

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
    
    print("summarize_positive_reviews 응답:")
    print(response_positive)
    
    result_positive = response_positive.choices[0].message.content.strip()

    chatgpt_review_send_slack_message(
        user_ids=["U0809FLM811"],
        channel="C08JDKB6DC3",
        concert_name=positive_reviews[0].concert.name,
        emotion="긍정",
        message=result_positive
    )
    
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
    아래는 공연의 최근 부정 리뷰입니다.
    부정리뷰를 요약하고 개선할 수 있는 인사이트를 제안해주세요.
    아래 예시 형식을 지켜주세요.

    예시 형식:
    1. 요약
    - 최대 3줄 이내로 요약
    2. 인사이트
    - 3가지 항목 제안

    추가 조건:
    - 볼드체(**)나 이모티콘을 사용하지 마세요.
    - 구체적이고 실행 가능한 개선 아이디어를 제시해주세요.

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
    
    print("summarize_negative_reviews 응답:")
    print(response_negative)
    
    result_negative = response_negative.choices[0].message.content.strip()

    chatgpt_review_send_slack_message(
        user_ids=["U0809FLM811", "U07BZ99GETB", "U082KGZ7J3X"],
        channel="C08JDKB6DC3",
        concert_name=negative_reviews[0].concert.name,
        emotion="부정",
        message=result_negative
    )
    
    context = {
        "result_negative": result_negative,
        "negative_reviews": negative_reviews,
    }
    return render(request, "review/summarized_negative_reviews.html", context)
