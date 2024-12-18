from django.test import TestCase
import os

from review.tasks import log

class LogFunctionTest(TestCase):
    def test_log_function(self):
        log_file_path = '/tmp/cron_test.log'
        if os.path.exists(log_file_path):
            os.remove(log_file_path)

        test_message = "Test log message"
        log(test_message)

        # 로그 파일이 생성되었는지 확인
        self.assertTrue(os.path.exists(log_file_path), "로그 파일이 생성되지 않았습니다.")

        # 로그 파일의 내용 확인
        with open(log_file_path, 'r') as f:
            content = f.read()
            self.assertIn(test_message, content, "로그 메시지가 파일에 기록되지 않았습니다.")
