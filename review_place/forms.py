from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
import re
from django.utils import timezone
from datetime import datetime
from .models import Place, Review, Comment, Report

class MultipleFileInput(forms.FileInput):
    allow_multiple_selected = True

class MultipleImageField(forms.ImageField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput)
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result

User = get_user_model()

class RegistrationForm(forms.Form):
    FIRST_NAME_CHOICES = [('male', 'ชาย'), ('female', 'หญิง'), ('other', 'อื่นๆ')]

    username = forms.CharField(max_length=30, required=True, label='ชื่อผู้ใช้')
    first_name = forms.CharField(max_length=30, required=True, label='ชื่อ')
    last_name = forms.CharField(max_length=30, required=True, label='นามสกุล')
    email = forms.EmailField(required=True, label='อีเมล')
    mobile_phone = forms.CharField(max_length=15, required=True, label='เบอร์มือถือ')
    gender = forms.ChoiceField(choices=FIRST_NAME_CHOICES, required=True, label='เพศ')

    day = forms.ChoiceField(
        choices=[('', 'เลือกวันที่')] + [(str(i), str(i)) for i in range(1, 32)],
        required=True,
        label='วัน'
    )
    month = forms.ChoiceField(
        choices=[('', 'เลือกเดือน')] + [(str(i), str(i)) for i in range(1, 13)],
        required=True,
        label='เดือน'
    )
    year = forms.ChoiceField(
        choices=[('', 'เลือกปี')] + [(str(i), str(i)) for i in range(timezone.now().year, timezone.now().year - 101, -1)],
        required=True,
        label='ปี'
    )
    password = forms.CharField(widget=forms.PasswordInput(), required=True, label='รหัสผ่าน')
    confirm_password = forms.CharField(widget=forms.PasswordInput(), required=True, label='ยืนยันรหัสผ่าน')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("อีเมลนี้ถูกใช้งานแล้ว")
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError("ชื่อผู้ใช้นี้ถูกใช้งานแล้ว")
        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            raise ValidationError("รหัสผ่านไม่ตรงกัน")

        if not re.match(r"[^@]+@[^@]+\.[^@]+", cleaned_data.get("email", "")):
            raise ValidationError("รูปแบบอีเมล์ไม่ถูกต้อง")

        day = cleaned_data.get("day")
        month = cleaned_data.get("month")
        year = cleaned_data.get("year")

        if day and month and year:
            try:
                birth_date = datetime(int(year), int(month), int(day))
                cleaned_data['date_of_birth'] = birth_date
            except ValueError:
                raise ValidationError("วันเกิดไม่ถูกต้อง กรุณาเลือกวัน เดือน ปี ที่ถูกต้อง")

        return cleaned_data

class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'mobile_phone', 'profile_image']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError("อีเมลนี้ถูกใช้งานแล้ว")
        return email

    def clean__phone(self):
        mobile_phone = self.cleaned_data.get('mobile_phone')
        if User.objects.filter(mobile_phone=mobile_phone).exclude(pk=self.instance.pk).exists():
            raise ValidationError("เบอร์มือถือนี้ถูกใช้งานแล้ว")
        return mobile_phone

class PasswordUpdateForm(PasswordChangeForm):
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        self.fields['old_password'].label = "รหัสผ่านเก่า"
        self.fields['new_password1'].label = "รหัสผ่านใหม่"
        self.fields['new_password2'].label = "ยืนยันรหัสผ่านใหม่"

class PlaceForm(forms.ModelForm):
    images = MultipleImageField(required=False)

    class Meta:
        model = Place
        fields = ['place_name', 'category', 'location', 'description', 'contact_info', 'price_range', 'open_hours']

    def clean_images(self):
        images = self.files.getlist('images')
        if len(images) > 15:
            raise ValidationError("สามารถอัปโหลดรูปภาพได้สูงสุด 15 รูป")
        return images

class ReviewForm(forms.ModelForm):
    review_images = MultipleImageField(required=False)

    class Meta:
        model = Review
        fields = ['review_text', 'rating']
        widgets = {
            'rating': forms.NumberInput(attrs={'min': 1, 'max': 5})
        }

    def clean_review_images(self):
        images = self.files.getlist('review_images')
        if len(images) > 5:
            raise ValidationError("สามารถอัปโหลดรูปภาพได้สูงสุด 5 รูป")
        return images

class ReportReviewForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['reason']
        widgets = {
            'reason': forms.Textarea(attrs={'rows': 3}),
        }
        labels = {
            'reason': 'เหตุผลในการรายงาน',
        }

class ReportPlaceForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['reason']
        widgets = {
            'reason': forms.Textarea(attrs={'rows': 3}),
        }
        labels = {
            'reason': 'เหตุผลในการรายงาน',
        }

class ReportCommentForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['reason']
        widgets = {
            'reason': forms.Textarea(attrs={'rows': 3}),
        }
        labels = {
            'reason': 'เหตุผลในการรายงาน',
        }

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 2, 'placeholder': 'แสดงความคิดเห็น...'}),
        }
        labels = {
            'text': ''
        }
