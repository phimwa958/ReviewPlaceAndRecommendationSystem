from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    CustomUser, Report, Place, Review, Comment, UserActivity, PlaceLike, Notification
)

# ปรับปรุงการแสดงผล PlaceLike ใน Admin
@admin.register(PlaceLike)
class PlaceLikeAdmin(admin.ModelAdmin):
    list_display = ('user', 'place', 'created_at')
    search_fields = ('user__username', 'place__place_name')
    list_filter = ('created_at',)
    ordering = ('-created_at',)
 
# ปรับปรุงการแสดงผล CustomUser ใน Admin
class CustomUserAdmin(UserAdmin):
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'mobile_phone', 'gender', 'date_of_birth')}),
        ('Permissions', {'fields': ('is_staff', 'is_active', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    list_display = ('username', 'email', 'first_name', 'last_name', 'mobile_phone', 'gender', 'date_of_birth', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'mobile_phone')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'gender')

# ปรับปรุงการแสดงผล Report ใน Admin
@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('report_type', 'place', 'review', 'reported_by', 'reported_at')
    list_filter = ('report_type', 'reported_at')
    search_fields = ('reason', 'reported_by__username', 'place__place_name', 'review__review_text')

# ปรับปรุงการแสดงผล Place ใน Admin
@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = ('place_name', 'category', 'location', 'average_rating', 'total_reviews', 'visit_count')
    search_fields = ('place_name', 'description', 'location')
    list_filter = ('category',)
    readonly_fields = ('average_rating', 'total_reviews', 'visit_count')  # ฟิลด์ที่คำนวณอัตโนมัติไม่ควรแก้ไข

# ปรับปรุงการแสดงผล Review ใน Admin
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'place', 'rating', 'review_date', 'status', 'helpful_count', 'report_count', 'visit_count')
    search_fields = ('user__username', 'place__place_name', 'review_text')
    list_filter = ('status', 'rating', 'review_date')
    ordering = ('-review_date',)
    readonly_fields = ('helpful_count', 'report_count', 'visit_count')  # ฟิลด์ที่คำนวณอัตโนมัติไม่ควรแก้ไข

# ปรับปรุงการแสดงผล Comment ใน Admin
@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('review', 'user', 'text', 'created_at', 'status')
    search_fields = ('user__username', 'review__review_text', 'text')
    list_filter = ('status', 'created_at')

# ปรับปรุงการแสดงผล UserActivity ใน Admin
@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'activity_type', 'timestamp', 'content_object')
    search_fields = ('user__username', 'activity_type', 'details')
    list_filter = ('activity_type', 'timestamp')
    readonly_fields = ('timestamp',)

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'actor', 'verb', 'unread', 'timestamp')
    list_filter = ('unread', 'timestamp')
    search_fields = ('recipient__username', 'actor__username', 'verb')


# ลงทะเบียน CustomUserAdmin
admin.site.register(CustomUser, CustomUserAdmin)