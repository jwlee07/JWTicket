import os
import sys
import django
from datetime import datetime

# Django 설정 로드
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ticket.settings')
django.setup()

from review.tasks import crawl_all_concerts_reviews
from review.chatgpt import update_reviews_with_sentiment
from review.tasks import summarize_reviews_cron

def run_crawling():
    print(f"[{datetime.now()}] Starting review crawling...")
    try:
        crawl_all_concerts_reviews()
        print(f"[{datetime.now()}] Review crawling completed successfully")
    except Exception as e:
        print(f"[{datetime.now()}] Error during crawling: {str(e)}")

def run_sentiment_analysis():
    print(f"[{datetime.now()}] Starting sentiment analysis...")
    try:
        update_reviews_with_sentiment()
        print(f"[{datetime.now()}] Sentiment analysis completed successfully")
    except Exception as e:
        print(f"[{datetime.now()}] Error during sentiment analysis: {str(e)}")

def run_slack_notification():
    print(f"[{datetime.now()}] Starting slack notification...")
    try:
        summarize_reviews_cron()
        print(f"[{datetime.now()}] Slack notification sent successfully")
    except Exception as e:
        print(f"[{datetime.now()}] Error during slack notification: {str(e)}")

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python scheduled_tasks.py [crawling|sentiment|slack]")
        sys.exit(1)

    task = sys.argv[1]
    if task == 'crawling':
        run_crawling()
    elif task == 'sentiment':
        run_sentiment_analysis()
    elif task == 'slack':
        run_slack_notification()
    else:
        print(f"Unknown task: {task}") 