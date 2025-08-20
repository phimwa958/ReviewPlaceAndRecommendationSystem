from django.urls import path, include
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.HomePageView.as_view(), name='home'),
    path('places/all/', views.PlaceAllView.as_view(), name='place_all'),
    path('places/popular/', views.PopularityView.as_view(), name='place_popular'),
    path('places/recommendations/', views.RecommendationView.as_view(), name='place_recommendations'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/edit/', views.ProfileUpdateView.as_view(), name='profile_edit'),
    path('profile/password/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    path('place/add/', views.PlaceCreateView.as_view(), name='add_place'),
    path('place/<int:place_id>/', views.PlaceDetailView.as_view(), name='place_detail'),
    path('place/<int:place_id>/edit/', views.PlaceUpdateView.as_view(), name='edit_place'),
    path('place/<int:place_id>/delete/', views.PlaceDeleteView.as_view(), name='delete_place'),
    path('place/<int:place_id>/review/add/', views.ReviewCreateView.as_view(), name='add_review'),
    path('review/<int:review_id>/comment/add/', views.CommentCreateView.as_view(), name='add_comment'),
    path('review/<int:review_id>/edit/', views.ReviewUpdateView.as_view(), name='edit_review'),
    path('review/<int:review_id>/delete/', views.ReviewDeleteView.as_view(), name='delete_review'),
    path('review/<int:review_id>/report/', views.ReportReviewView.as_view(), name='report_review'),
    path('comment/<int:comment_id>/edit/', views.CommentUpdateView.as_view(), name='edit_comment'),
    path('comment/<int:comment_id>/delete/', views.CommentDeleteView.as_view(), name='delete_comment'),
    path('comment/<int:comment_id>/report/', views.ReportCommentView.as_view(), name='report_comment'),
    path('place/<int:place_id>/report/', views.ReportPlaceView.as_view(), name='report_place'),
    path('place/<int:place_id>/like/', views.LikePlaceView.as_view(), name='like_place'),
    path('record_share_activity/', views.RecordShareActivityView.as_view(), name='record_share_activity'),

    # Admin activity visualization
    path('admin/activity/', views.AdminActivityView.as_view(), name='admin_activity'),
    path('admin/activity/export/', views.AdminActivityExportView.as_view(), name='admin_activity_export'),

    # Password reset links (Django's built-in views)
    path('password_reset/', auth_views.PasswordResetView.as_view(
        template_name='review/form.html',
        extra_context={'form_title': 'Reset Password', 'form_btn': 'Request Reset'}
    ), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='review/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='review/form.html',
        extra_context={'form_title': 'Set New Password', 'form_btn': 'Save New Password'}
    ), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='review/password_reset_complete.html'), name='password_reset_complete'),
]