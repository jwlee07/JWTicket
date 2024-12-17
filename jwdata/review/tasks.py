from datetime import datetime

def my_scheduled_task():
    with open('/tmp/cron_test.log', 'a') as f:
        f.write(f"Task executed at {datetime.now()}\n")
