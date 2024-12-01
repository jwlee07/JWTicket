from django.db import models

# 공연 정보를 저장하는 모델
class Concert(models.Model):
    name = models.CharField(max_length=255, verbose_name="공연명")
    place = models.CharField(max_length=255, verbose_name="공연 장소")
    start_date = models.DateField(verbose_name="공연 시작일")
    end_date = models.DateField(verbose_name="공연 종료일")
    duration_minutes = models.IntegerField(verbose_name="공연 시간(분)", null=True, blank=True)

    class Meta:
        verbose_name = "공연 정보"
        verbose_name_plural = "공연 정보들"

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

    class Meta:
        verbose_name = "리뷰"
        verbose_name_plural = "리뷰들"

    def __str__(self):
        return f"{self.concert.name} - {self.title}"
