from django.db import models
from django.utils.timezone import now

# 공연 정보를 저장하는 모델
class Concert(models.Model):
    name = models.CharField(max_length=255, verbose_name="공연명")
    place = models.CharField(max_length=255, verbose_name="공연 장소")
    start_date = models.DateField(verbose_name="공연 시작일")
    end_date = models.DateField(verbose_name="공연 종료일")
    duration_minutes = models.IntegerField(verbose_name="공연 시간(분)", null=True, blank=True)
    genre = models.CharField(max_length=100, verbose_name="공연 장르", null=True, blank=True)

    class Meta:
        verbose_name = "공연 정보"
        verbose_name_plural = "공연 정보"

    def __str__(self):
        return self.name


# 리뷰 정보를 저장하는 모델
class Review(models.Model):
    concert = models.ForeignKey(Concert, on_delete=models.CASCADE, related_name="reviews", verbose_name="공연")
    nickname = models.CharField(max_length=100, verbose_name="리뷰 작성자 닉네임")
    date = models.DateField(verbose_name="리뷰 작성일")
    view_count = models.IntegerField(verbose_name="리뷰 조회수", default=0)
    like_count = models.IntegerField(verbose_name="리뷰 좋아요 수", default=0)
    title = models.CharField(max_length=255, verbose_name="리뷰 제목")
    description = models.TextField(verbose_name="리뷰 내용", null=True, blank=True)
    star_rating = models.FloatField(verbose_name="리뷰 별점", null=True, blank=True)
    emotion = models.CharField(max_length=100, verbose_name="리뷰 감정", null=True, blank=True)

    class Meta:
        verbose_name = "리뷰"
        verbose_name_plural = "리뷰"

    def __str__(self):
        return f"{self.concert.name} - {self.title}"


# 잔여 좌석 정보를 저장하는 모델
class Seat(models.Model):
    concert = models.ForeignKey(Concert, on_delete=models.CASCADE, related_name="seats", verbose_name="공연")
    year = models.IntegerField(verbose_name="연도")
    month = models.IntegerField(verbose_name="월")
    day_num = models.IntegerField(verbose_name="일")
    day_str = models.CharField(verbose_name="요일", max_length=10)
    round_name = models.CharField(verbose_name="회차 번호", max_length=10)
    round_time = models.TimeField(verbose_name="회차 시간")
    seat_class = models.CharField(verbose_name="좌석 등급", max_length=10)
    seat_count = models.IntegerField(verbose_name="잔여 좌석")
    actors = models.TextField(verbose_name="캐스팅 배우들", blank=True, help_text="해당 회차에 캐스팅된 배우 목록을 저장합니다.")
    created_at = models.DateTimeField(verbose_name="데이터 삽입 시간", default=now, help_text="이 데이터가 생성된 시간을 저장합니다.")

    class Meta:
        verbose_name = "잔여 좌석 정보"
        verbose_name_plural = "잔여 좌석 정보"

    def __str__(self):
        return f"{self.concert.name} - {self.year}-{self.month:02d}-{self.day_num:02d} {self.round_name} {self.seat_class}"
