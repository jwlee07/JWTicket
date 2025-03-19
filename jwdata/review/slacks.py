from django.shortcuts import redirect
import slack_sdk
from django.conf import settings

slack_token = settings.SLACK_OAUTH_TOKEN
client = slack_sdk.WebClient(token=slack_token)

def chatgpt_review_send_slack_message(user_ids=None, channel="C08JDKB6DC3", concert_name="공연명", emotion="", message="ChatGPT 리뷰 분석 내용"):

    if user_ids is None:
        user_ids = []

    user_mentions = " ".join(f"<@{uid}>" for uid in user_ids)

    slack_msg = f"""{user_mentions}\n\n*[{concert_name} {emotion} 리뷰 분석]*\n\n{message}"""

    client.chat_postMessage(
        channel=channel,
        text=slack_msg
    )

    return