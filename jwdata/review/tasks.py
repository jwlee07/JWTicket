from datetime import datetime

def crawling_scheduled_task():
    with open('/tmp/cron_test.log', 'a') as f:
        f.write(f"Task executed at {datetime.now()}\n")
