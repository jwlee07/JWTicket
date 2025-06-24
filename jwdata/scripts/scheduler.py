import os
import sys
import django
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# Django 설정 로드
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ticket.settings')
django.setup()

from review.tasks import crawl_all_concerts_reviews
from review.chatgpt import update_reviews_with_sentiment_cron
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
        update_reviews_with_sentiment_cron()
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
    scheduler = BlockingScheduler()
    
    # 매일 저녁 8시에 크롤링
    scheduler.add_job(
        run_crawling,
        CronTrigger(hour=20, minute=0)
    )
    
    # 매주 화요일 오전 9시에 감정 분석
    scheduler.add_job(
        run_sentiment_analysis,
        CronTrigger(day_of_week='tue', hour=9, minute=0)
    )
    
    # 매주 화요일 오전 11시에 슬랙 알림
    scheduler.add_job(
        run_slack_notification,
        CronTrigger(day_of_week='tue', hour=11, minute=0)
    )
    
    print("Scheduler started...")
    scheduler.start() 