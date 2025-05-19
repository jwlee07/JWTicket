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

    분석 기준:
    1. 공연 특수성 고려
    - 슬픈 내용의 공연에서 울었다는 것은 긍정적 반응
    - 배우의 연기가 너무 실감나서 불편했다는 것은 긍정적 반응
    - 공연장 시설, 관람 환경 관련 내용은 별도로 구분

    2. 감정 판단 기준
    - 긍정: 감동, 재미, 만족, 호평, 추천 의사 등
    - 중립: 장단점 공존, 객관적 서술만 있는 경우
    - 부정: 실망, 불만족, 비추천, 부정적 경험

    3. 주의사항
    - 공연 자체의 내용과 관람 경험을 구분하여 판단
    - 티켓 가격 대비 만족도 고려
    - 공연의 장르별 특성 반영

    위 기준을 바탕으로 '긍정', '중립', '부정' 중 하나로만 답변해주세요.

    리뷰 내용: {review_text}
    """
    
    response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "당신은 공연 리뷰 감정 분석 전문가입니다."},
            {"role": "user", "content": prompt}
        ],
        model="gpt-4",
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
    return redirect('review:home')

def summarize_positive_reviews(request, concert_id, slack_channel_id=None):
    positive_reviews = Review.objects.filter(
        concert_id=concert_id,
        emotion="긍정",
        description__isnull=False
    ).exclude(description="").order_by("-date")[:50]
    
    if not positive_reviews:
        print("분석할 긍정 리뷰가 없습니다.")
        return redirect('review:home')
    
    # 긍정 리뷰 내용 합치기
    positive_text = "\n\n".join([review.description for review in positive_reviews])
    
    # 긍정 리뷰 요약 및 개선점 프롬프트 구성
    prompt_positive = f"""
    아래는 공연의 최근 긍정 리뷰입니다. 다음 구조로 분석해주세요.

    1. 핵심 요약 (3줄 이내)
    - 전반적인 관람객 만족도
    - 가장 두드러진 장점
    - 공통적으로 언급되는 특징

    2. 상세 분석
    a) 공연 구성 요소별 강점
    - 연기/실연 관련
    - 연출/기술적 요소
    - 스토리/음악적 요소

    b) 관객 반응 패턴
    - 주요 감동/만족 포인트
    - 기대 대비 만족도
    - 재관람/추천 의향

    3. 발전적 제안 (3가지)
    - 현재의 강점을 더욱 강화할 수 있는 구체적 방안
    - 마케팅/홍보에 활용할 수 있는 요소
    - 관객 경험 향상을 위한 아이디어

    추가 조건:
    - 볼드체나 이모티콘 사용 금지
    - 객관적 데이터에 근거한 분석
    - 실현 가능한 제안 위주로 작성

    리뷰 내용:
    {positive_text}
    """
    
    response_positive = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "당신은 공연 리뷰 분석 전문가입니다."},
            {"role": "user", "content": prompt_positive}
        ],
        model="gpt-4",
    )
    
    print("summarize_positive_reviews 응답:")
    print(response_positive)
    
    result_positive = response_positive.choices[0].message.content.strip()

    if slack_channel_id:
        chatgpt_review_send_slack_message(
            channel=slack_channel_id,
            concert_name=positive_reviews[0].concert.name,
            emotion="긍정",
            message=result_positive
        )
    
    context = {
        "result_positive": result_positive,
        "positive_reviews": positive_reviews,
    }
    return render(request, "review/summarized_positive_reviews.html", context)

def summarize_negative_reviews(request, concert_id, slack_channel_id=None):
    negative_reviews = Review.objects.filter(
        concert_id=concert_id,
        emotion="부정",
        description__isnull=False
    ).exclude(description="").order_by("-date")[:50]
    
    if not negative_reviews:
        print("분석할 부정 리뷰가 없습니다.")
        return redirect('review:home')
    
    # 부정 리뷰 내용 합치기
    negative_text = "\n\n".join([review.description for review in negative_reviews])
    
    # 부정 리뷰 요약 및 개선점 프롬프트 구성
    prompt_negative = f"""
    아래는 공연의 최근 부정 리뷰입니다. 다음 구조로 분석해주세요.

    1. 핵심 요약 (3줄 이내)
    - 주요 불만족 사항
    - 가장 시급한 개선점
    - 공통적으로 제기되는 문제

    2. 상세 분석
    a) 문제점 카테고리별 분류
    - 공연 내적 요소 (연기, 연출, 스토리 등)
    - 공연 외적 요소 (시설, 서비스, 티켓팅 등)
    - 기대 격차 요소 (홍보 내용과 실제 차이)

    b) 영향도 분석
    - 관객 만족도에 미치는 영향
    - 재관람/추천 의사에 미치는 영향
    - 공연 평판에 미치는 영향

    3. 개선 제안 (3가지)
    - 단기적으로 즉시 개선 가능한 사항
    - 중장기적 개선이 필요한 사항
    - 우선순위가 높은 핵심 개선점

    추가 조건:
    - 볼드체나 이모티콘 사용 금지
    - 건설적이고 실행 가능한 해결책 제시
    - 문제의 근본 원인 분석에 중점

    리뷰 내용:
    {negative_text}
    """
    
    response_negative = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "당신은 공연 리뷰 분석 전문가입니다."},
            {"role": "user", "content": prompt_negative}
        ],
        model="gpt-4",
    )
    
    print("summarize_negative_reviews 응답:")
    print(response_negative)
    
    result_negative = response_negative.choices[0].message.content.strip()

    if slack_channel_id:
        chatgpt_review_send_slack_message(
            channel=slack_channel_id,
            concert_name=negative_reviews[0].concert.name,
            emotion="부정",
            message=result_negative
        )
    
    context = {
        "result_negative": result_negative,
        "negative_reviews": negative_reviews,
    }
    return render(request, "review/summarized_negative_reviews.html", context)
