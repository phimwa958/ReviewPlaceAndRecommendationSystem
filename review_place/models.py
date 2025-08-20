from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.conf import settings
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import urllib.parse

class CustomUser(AbstractUser):
    mobile_phone = models.CharField(max_length=15, unique=True, verbose_name="เบอร์มือถือ")
    
    GENDER_CHOICES = [
        ('male', 'ชาย'),
        ('female', 'หญิง'),
        ('other', 'อื่นๆ'),
    ]
    gender = models.CharField(max_length=6, choices=GENDER_CHOICES, verbose_name="เพศ", default='other')
    date_of_birth = models.DateField(verbose_name="วันเกิด", null=True, blank=True)
    profile_image = models.ImageField(upload_to='profile_pics/', default='default.jpg', blank=True, null=True, verbose_name="รูปโปรไฟล์")

    def clean(self):
        super().clean()
        if CustomUser.objects.filter(mobile_phone=self.mobile_phone).exclude(pk=self.pk).exists():
            raise ValidationError(_('หมายเลขโทรศัพท์มือถือซ้ำกัน'))

    def __str__(self):
        return self.username

    @property
    def age(self):
        if self.date_of_birth:
            today = timezone.now().date()
            return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        return None

class Place(models.Model):
    CATEGORY_CHOICES = [
        ('accommodation', 'ที่พัก'),
        ('attraction', 'สถานที่ท่องเที่ยว'),
        ('restaurant', 'ร้านอาหาร'),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="เจ้าของ"
    )
    place_name = models.CharField(max_length=255, verbose_name="ชื่อสถานที่")
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, verbose_name="หมวดหมู่")
    location = models.TextField(verbose_name="ที่ตั้ง")
    description = models.TextField(verbose_name="รายละเอียด", null=True, blank=True)
    average_rating = models.FloatField(default=0, verbose_name="คะแนนเฉลี่ย")
    total_reviews = models.IntegerField(default=0, verbose_name="จำนวนรีวิว")
    contact_info = models.TextField(verbose_name="ข้อมูลติดต่อ", null=True, blank=True)
    price_range = models.CharField(max_length=50, verbose_name="ช่วงราคา", null=True, blank=True)
    open_hours = models.CharField(max_length=255, verbose_name="เวลาทำการ", null=True, blank=True)
    visit_count = models.IntegerField(default=0, verbose_name="จำนวนการเข้าชม")
    
    # --- เพิ่มฟิลด์วันที่ ---
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="วันที่สร้าง")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="วันที่แก้ไขล่าสุด")

    def __str__(self):
        return self.place_name

    def get_absolute_url(self):
        return reverse('place_detail', args=[str(self.id)])

    def get_share_urls(self, request):
        absolute_url = request.build_absolute_uri(self.get_absolute_url())
        encoded_url = urllib.parse.quote(absolute_url)
        text = urllib.parse.quote(f"Check out this amazing place: {self.place_name}")
        title = urllib.parse.quote(self.place_name)

        return {
            'facebook': f"https://www.facebook.com/sharer/sharer.php?u={encoded_url}",
            'twitter': f"https://twitter.com/intent/tweet?url={encoded_url}&text={text}",
            'linkedin': f"https://www.linkedin.com/shareArticle?mini=true&url={encoded_url}&title={title}&summary={text}",
            'line': f"https://social-plugins.line.me/lineit/share?url={encoded_url}",
        }

    def update_average_rating(self):
        reviews = self.reviews.filter(status='published')
        if reviews.exists():
            self.average_rating = reviews.aggregate(models.Avg('rating'))['rating__avg']
            self.total_reviews = reviews.count()
        else:
            self.average_rating = 0
            self.total_reviews = 0
        self.save()

class PlaceImage(models.Model):
    place = models.ForeignKey(Place, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='places/')

    def __str__(self):
        return f"Image for {self.place.place_name}"

class PlaceLike(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='place_likes')
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'place')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} likes {self.place.place_name}'

class Review(models.Model):
    STATUS_CHOICES = [
        ('published', 'เผยแพร่'),
        ('deleted', 'ลบแล้ว'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="ผู้ใช้")
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='reviews', verbose_name="สถานที่")
    review_text = models.TextField(verbose_name="ข้อความรีวิว")
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="คะแนน"
    )
    review_date = models.DateTimeField(auto_now_add=True, verbose_name="วันที่รีวิว")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='published', verbose_name="สถานะ")
    helpful_count = models.IntegerField(default=0, verbose_name="จำนวนคนที่ช่วยเหลือ")
    report_count = models.IntegerField(default=0, verbose_name="จำนวนรายงาน")
    visit_count = models.IntegerField(default=0, verbose_name="จำนวนการเข้าชม")

    def __str__(self):
        return f"รีวิวโดย {self.user.username} สำหรับ {self.place.place_name}"

    def get_absolute_url(self):
        place_url = reverse('place_detail', args=[str(self.place.id)])
        return f'{place_url}#review-{self.id}'

    def get_share_urls(self, request):
        absolute_url = request.build_absolute_uri(self.get_absolute_url())
        encoded_url = urllib.parse.quote(absolute_url)
        text = urllib.parse.quote(f'"Check out this review for {self.place.place_name}: "{self.review_text[:50]}..."')
        title = urllib.parse.quote(f'Review for {self.place.place_name}')

        return {
            'facebook': f"https://www.facebook.com/sharer/sharer.php?u={encoded_url}",
            'twitter': f"https://twitter.com/intent/tweet?url={encoded_url}&text={text}",
            'linkedin': f"https://www.linkedin.com/shareArticle?mini=true&url={encoded_url}&title={title}&summary={text}",
            'line': f"https://social-plugins.line.me/lineit/share?url={encoded_url}",
        }

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.place.update_average_rating()

class ReviewImage(models.Model):
    review = models.ForeignKey(Review, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='reviews/')

    def __str__(self):
        return f"Image for review {self.review.id}"


class Comment(models.Model):
    STATUS_CHOICES = [
        ('published', 'เผยแพร่'),
        ('deleted', 'ลบแล้ว'),
    ]

    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='comments', verbose_name="รีวิว")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="ผู้ใช้")
    text = models.TextField(verbose_name="ข้อความ")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="วันที่สร้าง")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="วันที่แก้ไข")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='published', verbose_name="สถานะ")

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'ความคิดเห็นโดย {self.user.username} บนรีวิวของ {self.review.user.username}'

class Report(models.Model):
    REPORT_CHOICES = [
        ('place', 'สถานที่'),
        ('review', 'รีวิว'),
        ('comment', 'ความคิดเห็น'),
    ]

    report_type = models.CharField(max_length=10, choices=REPORT_CHOICES, verbose_name="ประเภทรายงาน")
    place = models.ForeignKey('Place', on_delete=models.CASCADE, null=True, blank=True, verbose_name="สถานที่")
    review = models.ForeignKey('Review', on_delete=models.CASCADE, null=True, blank=True, verbose_name="รีวิว")
    comment = models.ForeignKey('Comment', on_delete=models.CASCADE, null=True, blank=True, verbose_name="ความคิดเห็น")
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="รายงานโดย")
    reason = models.TextField(verbose_name="เหตุผล")
    reported_at = models.DateTimeField(auto_now_add=True, verbose_name="วันที่รายงาน")

    def __str__(self):
        return f"รายงาน {self.get_report_type_display()} โดย {self.reported_by.username}"

class UserActivity(models.Model):
    ACTIVITY_TYPES = [
        ('view', 'View'),
        ('share', 'Share'),
        ('search', 'Search'),
        ('click', 'Click'),
    ]

    ACTIVITY_TYPE_CHOICES_MAP = dict(ACTIVITY_TYPES)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=50, choices=ACTIVITY_TYPES)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(null=True, blank=True)

    # Generic relation to link to any model (Place, Review, etc.)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "User Activity"
        verbose_name_plural = "User Activities"

    def __str__(self):
        return f'{self.user.username} - {self.get_activity_type_display()} on {self.timestamp.strftime("%Y-%m-%d %H:%M")}'