from django.db import migrations, models
from django.utils.timezone import now

class Migration(migrations.Migration):

    dependencies = [
        ('review', '0003_rename_count_seat_seat_count_seat_created_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='seat',
            name='created_at',
            field=models.DateTimeField(default=now, help_text='이 데이터가 생성된 시간을 저장합니다.', verbose_name='데이터 삽입 시간'),
        ),
    ]
