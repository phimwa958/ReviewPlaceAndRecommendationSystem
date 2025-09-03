from django.utils import timezone
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, FormView, View
)
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from django.contrib.auth import views as auth_views, login, get_user_model
from django.contrib.auth.views import LogoutView as AuthLogoutView, PasswordChangeView
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.db import models
from django.db.models import Count, Q, Case, When, TextField, F
from django.core.mail import send_mail
from django.conf import settings
from django.core.paginator import Paginator
from .forms import (
    RegistrationForm, UserUpdateForm, PlaceForm, ReviewForm, ReportReviewForm, ReportPlaceForm, PasswordUpdateForm, CommentForm, ReportCommentForm
)
from .models import  Place, Review, Report, UserActivity, PlaceLike, Comment, PlaceImage, ReviewImage, CustomUser, Notification
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
import csv
import json
from datetime import datetime, time
from django.db.models.functions import TruncDay, TruncMonth, TruncYear, Cast
from collections import Counter
from recommendations.engine import recommendation_engine
from recommendations import user_based
from recommendations.popularity_based import get_popularity_based_recommendations
from .mixins import OwnerOrStaffRequiredMixin, FormContextMixin, AdminActivityMixin, ImageHandlingMixin
from django.http import JsonResponse
from .models import Place

User = get_user_model()

class LoginView(auth_views.LoginView):
    template_name = 'review/form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Login'
        context['form_title'] = 'Login'
        context['form_btn'] = 'Login'
        context['is_login_form'] = True
        return context

    def form_valid(self, form):
        remember_me = self.request.POST.get('remember_me')
        response = super().form_valid(form)
        self.request.session.set_expiry(1209600 if remember_me else 0)
        if self.request.user.is_staff:
            self.request.session['redirect_to_admin'] = True
        return response

class LogoutView(AuthLogoutView):
    pass

class RegisterView(FormContextMixin, FormView):
    form_class = RegistrationForm
    template_name = 'review/form.html'
    success_url = reverse_lazy('home')
    title = 'Register'
    form_title = 'Create an Account'
    form_btn = 'Register'

    def form_valid(self, form):
        data = form.cleaned_data
        user = CustomUser.objects.create_user(
            username=data['username'],
            email=data['email'],
            password=data['password'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            mobile_phone=data['mobile_phone'],
            gender=data['gender'],
            date_of_birth=data['date_of_birth']
        )
        login(self.request, user)
        return super().form_valid(form)

class ProfileView(LoginRequiredMixin, DetailView):
    model = User
    template_name = 'review/profile.html'
    context_object_name = 'profile_user' # Use a different name to avoid conflict with 'user'

    def get_object(self, queryset=None):
        # Return the currently logged-in user
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.get_object()
        context['user_places'] = Place.objects.filter(owner=user).order_by('-created_at')
        return context

class ProfileUpdateView(FormContextMixin, LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = 'review/form.html'
    success_url = reverse_lazy('profile')
    success_message = 'โปรไฟล์ถูกอัปเดตเรียบร้อยแล้ว'

    form_title = 'Edit Profile'
    form_btn = 'Save Changes'
    with_media = True

    def get_object(self, queryset=None):
        return self.request.user

    def get_cancel_url(self):
        return self.success_url

class CustomPasswordChangeView(FormContextMixin, LoginRequiredMixin, SuccessMessageMixin, PasswordChangeView):
    form_class = PasswordUpdateForm
    template_name = 'review/form.html'
    success_url = reverse_lazy('profile')
    success_message = 'รหัสผ่านถูกเปลี่ยนเรียบร้อยแล้ว'

    form_title = 'Change Password'
    form_btn = 'Save Changes'

    def get_cancel_url(self):
        return self.success_url

class HomePageView(TemplateView):
    template_name = 'review/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search_query = self.request.GET.get('search')
        category_query = self.request.GET.get('category')

        # Pass categories for the search dropdown
        context['categories'] = Place.CATEGORY_CHOICES
        context['selected_category'] = category_query

        # Handle search
        if search_query or category_query:
            places_queryset = Place.objects.all()
            if search_query:
                places_queryset = places_queryset.filter(
                    Q(place_name__icontains=search_query) |
                    Q(description__icontains=search_query) |
                    Q(location__icontains=search_query)
                )
                if self.request.user.is_authenticated:
                    # Avoid creating duplicate search logs for the same query
                    if not UserActivity.objects.filter(user=self.request.user, activity_type='search', details__query=search_query).exists():
                        UserActivity.objects.create(
                            user=self.request.user,
                            activity_type='search',
                            details={'query': search_query, 'category': category_query}
                        )
            if category_query:
                places_queryset = places_queryset.filter(category=category_query)

            paginator = Paginator(places_queryset.order_by('-id'), 10)
            page_number = self.request.GET.get('page')
            page_obj = paginator.get_page(page_number)

            context['page_obj'] = page_obj
            context['places'] = page_obj.object_list
            context['is_search'] = True
            context['search_query'] = search_query
            return context

        # If not a search, populate the homepage sections
        context['is_search'] = False

        # For all users
        # Section 2: Popular Places
        popular_place_ids = get_popularity_based_recommendations(num_recommendations=10)
        if popular_place_ids:
            ordering = Case(*[When(id=place_id, then=pos) for pos, place_id in enumerate(popular_place_ids)], output_field=models.IntegerField())
            context['popular_places'] = Place.objects.filter(id__in=popular_place_ids).order_by(ordering)
        else:
            # Fallback to simple ordering if recommendation fails
            context['popular_places'] = Place.objects.order_by('-visit_count', '-average_rating')[:10]

        # Section 3: Latest Places
        context['latest_places'] = Place.objects.all().order_by('-id')[:20]

        # For logged-in users only
        if self.request.user.is_authenticated:
            # Section 1: Recommended Places
            collab_data = user_based.get_user_collaborative_filtering_data()
            recommended_place_ids = recommendation_engine.get_hybrid_recommendations(self.request.user.id, collab_data, num_recommendations=10)
            if recommended_place_ids:
                ordering = Case(*[When(id=place_id, then=pos) for pos, place_id in enumerate(recommended_place_ids)], output_field=models.IntegerField())
                context['recommended_places'] = Place.objects.filter(id__in=recommended_place_ids).order_by(ordering)
            else:
                # Fallback if no recommendations
                context['recommended_places'] = []

        return context

class PlaceCreateView(ImageHandlingMixin, FormContextMixin, LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Place
    form_class = PlaceForm
    template_name = 'review/form.html'
    success_message = 'สถานที่ถูกเพิ่มเรียบร้อยแล้ว'

    form_title = 'Add New Place'
    form_btn = 'Add Place'
    with_media = True

    image_model = PlaceImage
    image_form_field = 'images'
    image_foreign_key_field = 'place'

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('place_detail', kwargs={'place_id': self.object.id})


class PlaceDetailView(DetailView):
    model = Place
    template_name = 'review/place_detail.html'
    context_object_name = 'place'
    pk_url_kwarg = 'place_id'

    def get_queryset(self):
        # Prefetch related data to avoid N+1 queries in the template for the main place object.
        return super().get_queryset().prefetch_related('images', 'likes')

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        # Atomically update visit count using an F() expression to avoid race conditions.
        Place.objects.filter(pk=self.object.pk).update(visit_count=F('visit_count') + 1)

        # Refresh the object from the database to get the updated count for the template.
        self.object.refresh_from_db(fields=['visit_count'])

        # Log user activity, but only once per session to avoid duplicate logs on refresh.
        if request.user.is_authenticated:
            session_key = f'viewed_place_{self.object.pk}'
            if not request.session.get(session_key):
                UserActivity.objects.create(
                    user=request.user,
                    activity_type='view',
                    content_type=ContentType.objects.get_for_model(self.object),
                    object_id=self.object.id,
                    details={'place_name': self.object.place_name}
                )
                request.session[session_key] = True

        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Efficiently query reviews, their authors, their comments, and the authors of those comments.
        reviews = self.object.reviews.filter(status='published').select_related('user').prefetch_related('comments__user', 'images')
        context['reviews'] = reviews
        context['share_urls'] = self.object.get_share_urls(self.request)
        context['place_absolute_url'] = self.request.build_absolute_uri(self.object.get_absolute_url())
        
        user = self.request.user
        if user.is_authenticated:
            # This is a single, efficient query.
            context['user_liked_place'] = PlaceLike.objects.filter(place=self.object, user=user).exists()
            # Get similar places instead of personalized recommendations
            similar_place_ids = recommendation_engine.get_similar_places(self.object.id, num_recommendations=3)
            # This query is also efficient as it fetches a few specific places.
            context['recommended_places'] = Place.objects.filter(id__in=similar_place_ids)
        else:
            context['user_liked_place'] = False
            # For anonymous users, also show similar places
            similar_place_ids = recommendation_engine.get_similar_places(self.object.id, num_recommendations=3)
            context['recommended_places'] = Place.objects.filter(id__in=similar_place_ids)

        # Use the prefetched 'likes' to get the count without an extra query.
        context['total_likes'] = self.object.likes.count()

        return context

class PlaceUpdateView(ImageHandlingMixin, FormContextMixin, LoginRequiredMixin, OwnerOrStaffRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Place
    form_class = PlaceForm
    template_name = 'review/form.html'
    pk_url_kwarg = 'place_id'
    success_message = 'แก้ไขสถานที่เรียบร้อยแล้ว'

    form_title = 'Edit Place'
    form_btn = 'Save Changes'
    with_media = True

    image_model = PlaceImage
    image_form_field = 'images'
    image_foreign_key_field = 'place'

    def get_form_subtitle(self):
        return self.object.place_name

    def get_cancel_url(self):
        return self.get_success_url()

    def get_success_url(self):
        return reverse('place_detail', kwargs={'place_id': self.object.id})


class BaseDeleteView(LoginRequiredMixin, OwnerOrStaffRequiredMixin, SuccessMessageMixin, DeleteView):
    template_name = 'review/confirm_delete.html'

    delete_title = ''
    delete_message_template = ''

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['delete_title'] = self.get_delete_title()
        context['delete_message'] = self.get_delete_message()
        context['cancel_url'] = self.get_cancel_url()
        return context

    def get_delete_title(self):
        return self.delete_title

    def get_delete_message(self):
        return self.delete_message_template.format(object=self.object)

    def get_cancel_url(self):
        # This default assumes the object has a get_absolute_url method.
        # It can be overridden if the cancel logic is different.
        if hasattr(self.object, 'get_absolute_url'):
            return self.object.get_absolute_url()
        return reverse('home')


class PlaceDeleteView(BaseDeleteView):
    model = Place
    pk_url_kwarg = 'place_id'
    success_message = 'ลบสถานที่เรียบร้อยแล้ว'
    success_url = reverse_lazy('home')

    delete_title = 'Delete Place'
    delete_message_template = "Are you sure you want to delete the place named '{object.place_name}'? This action cannot be undone."

    def get_cancel_url(self):
        return reverse('place_detail', kwargs={'place_id': self.object.id})

class BaseReportView(FormContextMixin, LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Report
    template_name = 'review/form.html'
    form_btn = 'Send Report'

    report_type = None
    related_object = None

    def dispatch(self, request, *args, **kwargs):
        self.related_object = self.get_related_object()
        return super().dispatch(request, *args, **kwargs)

    def get_related_object(self):
        raise NotImplementedError("Subclasses must implement get_related_object.")

    def form_valid(self, form):
        form.instance.reported_by = self.request.user
        form.instance.report_type = self.report_type
        setattr(form.instance, self.report_type, self.related_object)
        return super().form_valid(form)

    def get_form_title(self):
        return f"Report {self.report_type.capitalize()}"

    def get_form_subtitle(self):
        return f"You are reporting: {self.related_object}"

    def get_cancel_url(self):
        return self.get_success_url()

    def get_success_url(self):
        """
        Determines the redirect URL after a report is successfully submitted.
        Uses a dictionary mapping for scalability and readability.
        """
        url_mappers = {
            'place': lambda: reverse('place_detail', kwargs={'place_id': self.related_object.id}),
            'review': lambda: reverse('place_detail', kwargs={'place_id': self.related_object.place.id}),
            'comment': lambda: reverse('place_detail', kwargs={'place_id': self.related_object.review.place.id}),
        }

        # Get the appropriate URL mapping, or return the default 'home' URL if not found.
        url_func = url_mappers.get(self.report_type, lambda: reverse('home'))
        return url_func()

class ReportPlaceView(BaseReportView):
    form_class = ReportPlaceForm
    success_message = 'สถานที่ถูกรายงานเรียบร้อยแล้ว'
    report_type = 'place'

    def get_related_object(self):
        return get_object_or_404(Place, id=self.kwargs['place_id'])

class ReviewCreateView(ImageHandlingMixin, FormContextMixin, LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Review
    form_class = ReviewForm
    template_name = 'review/form.html'
    success_message = 'รีวิวถูกเพิ่มเรียบร้อยแล้ว'

    form_title = 'Add Review for'
    form_btn = 'Submit Review'
    with_media = True

    image_model = ReviewImage
    image_form_field = 'images'
    image_foreign_key_field = 'review'

    def dispatch(self, request, *args, **kwargs):
        self.place = get_object_or_404(Place, id=self.kwargs['place_id'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.user = self.request.user
        form.instance.place = self.place
        return super().form_valid(form)

    def get_form_subtitle(self):
        return self.place.place_name

    def get_cancel_url(self):
        return self.get_success_url()

    def get_success_url(self):
        return reverse('place_detail', kwargs={'place_id': self.place.id})

class ReviewDeleteView(BaseDeleteView):
    model = Review
    success_message = 'รีวิวถูกลบเรียบร้อยแล้ว'
    pk_url_kwarg = 'review_id'

    delete_title = 'Delete Review'
    delete_message_template = "Are you sure you want to delete this review? This action cannot be undone."

    def get_success_url(self):
        return reverse('place_detail', kwargs={'place_id': self.object.place.id})

    def get_cancel_url(self):
        return self.get_success_url()


class ReviewUpdateView(ImageHandlingMixin, FormContextMixin, LoginRequiredMixin, OwnerOrStaffRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Review
    form_class = ReviewForm
    template_name = 'review/form.html'
    pk_url_kwarg = 'review_id'
    success_message = 'รีวิวถูกแก้ไขเรียบร้อยแล้ว'

    form_title = 'Edit Review for'
    form_btn = 'Save Changes'
    with_media = True

    image_model = ReviewImage
    image_form_field = 'images'
    image_foreign_key_field = 'review'

    def handle_no_permission(self):
        messages.error(self.request, 'คุณไม่มีสิทธิ์แก้ไขรีวิวนี้')
        # self.object is set by the OwnerOrStaffRequiredMixin before this method is called
        return redirect('place_detail', place_id=self.object.place.id)

    def get_form_subtitle(self):
        return self.object.place.place_name

    def get_cancel_url(self):
        return self.get_success_url()

    def get_success_url(self):
        return reverse('place_detail', kwargs={'place_id': self.object.place.id})


class ReportReviewView(BaseReportView):
    form_class = ReportReviewForm
    success_message = 'รีวิวถูกรายงานเรียบร้อยแล้ว'
    report_type = 'review'

    def get_related_object(self):
        return get_object_or_404(Review, id=self.kwargs['review_id'])

    def get_form_subtitle(self):
        return f"You are reporting a review by {self.related_object.user.username} for {self.related_object.place.place_name}"

class CommentCreateView(FormContextMixin, LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Comment
    form_class = CommentForm
    template_name = 'review/form.html'
    success_message = "ความคิดเห็นถูกเพิ่มเรียบร้อยแล้ว"

    form_title = 'Add Comment'
    form_btn = 'Post Comment'

    def dispatch(self, request, *args, **kwargs):
        self.review = get_object_or_404(Review, id=self.kwargs['review_id'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.user = self.request.user
        form.instance.review = self.review
        return super().form_valid(form)

    def get_form_subtitle(self):
        return f"Replying to a review for {self.review.place.name}"

    def get_cancel_url(self):
        return self.get_success_url()

    def get_success_url(self):
        return reverse('place_detail', kwargs={'place_id': self.review.place.id})

class CommentUpdateView(FormContextMixin, LoginRequiredMixin, OwnerOrStaffRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Comment
    form_class = CommentForm
    template_name = 'review/form.html'
    pk_url_kwarg = 'comment_id'
    success_message = "ความคิดเห็นถูกแก้ไขเรียบร้อยแล้ว"

    form_title = 'Edit Comment'
    form_btn = 'Save Changes'

    def get_cancel_url(self):
        return self.get_success_url()

    def get_success_url(self):
        return reverse('place_detail', kwargs={'place_id': self.object.review.place.id})

class CommentDeleteView(BaseDeleteView):
    model = Comment
    pk_url_kwarg = 'comment_id'
    success_message = "ความคิดเห็นถูกลบเรียบร้อยแล้ว"

    delete_title = 'Delete Comment'
    delete_message_template = "Are you sure you want to delete this comment? This action cannot be undone."

    def get_success_url(self):
        return reverse('place_detail', kwargs={'place_id': self.object.review.place.id})

    def get_cancel_url(self):
        return self.get_success_url()

class ReportCommentView(BaseReportView):
    form_class = ReportCommentForm
    success_message = "ความคิดเห็นถูกรายงานเรียบร้อยแล้ว"
    report_type = 'comment'

    def get_related_object(self):
        return get_object_or_404(Comment, id=self.kwargs['comment_id'])

    def get_form_subtitle(self):
        return f"Reporting a comment by {self.related_object.user.username}"

class RecordShareActivityView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        shared_type = request.POST.get('shared_type')
        shared_id = request.POST.get('shared_id')
        shared_to = request.POST.get('shared_to')

        if not all([shared_type, shared_id, shared_to]):
            return JsonResponse({'status': 'error', 'message': 'Missing data'}, status=400)

        try:
            shared_id = int(shared_id)
            if shared_type == 'place':
                content_object = Place.objects.get(id=shared_id)
                
            elif shared_type == 'review':
                content_object = Review.objects.get(id=shared_id)
            else:
                return JsonResponse({'status': 'error', 'message': 'Invalid shared_type'}, status=400)

            UserActivity.objects.create(
                user=request.user,
                activity_type='share',
                content_type=ContentType.objects.get_for_model(content_object),
                object_id=content_object.id,
                details={'shared_to': shared_to}
            )
            return JsonResponse({'status': 'success'})
        except (Place.DoesNotExist, Review.DoesNotExist, ValueError) as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

class LikePlaceView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        place = get_object_or_404(Place, id=self.kwargs['place_id'])
        like, created = PlaceLike.objects.get_or_create(user=request.user, place=place)

        if not created:
            # The user has already liked the place, so this is an 'unlike' action.
            like.delete()
            action_detail = 'unlike_place'
        else:
            # The user is liking the place for the first time.
            action_detail = 'like_place'

        # Record the activity
        UserActivity.objects.create(
            user=request.user,
            activity_type='click',
            content_type=ContentType.objects.get_for_model(place),
            object_id=place.id,
            details={'action': action_detail}
        )
        return redirect('place_detail', place_id=place.id)

class AdminActivityView(AdminActivityMixin, LoginRequiredMixin, View):
    template_name = 'review/admin_activity.html'

    def _get_user_activity_data(self, activities_qs):
        """Analyzes and aggregates user activity."""
        user_activity = activities_qs.values('user__username', 'activity_type').annotate(count=Count('id')).order_by('user__username')
        user_activity_data = {}
        for item in user_activity:
            user = item['user__username']
            if user not in user_activity_data:
                user_activity_data[user] = {}
            user_activity_data[user][item['activity_type']] = item['count']
        return user_activity_data

    def _get_content_popularity_data(self, activities_qs):
        """Determines the most popular content based on views and shares."""
        content_popularity = (
            activities_qs.filter(activity_type__in=['view', 'share'])
            .values('content_type__model', 'object_id')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        place_ids = [item['object_id'] for item in content_popularity if item['content_type__model'] == 'place']
        review_ids = [item['object_id'] for item in content_popularity if item['content_type__model'] == 'review']
        places = Place.objects.in_bulk(place_ids)
        reviews = Review.objects.in_bulk(review_ids)
        content_popularity_data = []
        for item in content_popularity:
            if item['content_type__model'] == 'place':
                name = places.get(item['object_id'], 'Unknown Place').place_name
            elif item['content_type__model'] == 'review':
                review_obj = reviews.get(item['object_id'])
                name = f"Review for {review_obj.place.place_name}" if review_obj else "Unknown Review"
            else:
                name = f"{item['content_type__model']} #{item['object_id']}"
            content_popularity_data.append({'name': name, 'count': item['count']})
        return content_popularity_data

    def _get_sharing_behavior_data(self, activities_qs):
        """Analyzes how content is being shared."""
        return dict(
            activities_qs.filter(activity_type='share', details__shared_to__isnull=False)
            .values_list('details__shared_to')
            .annotate(count=Count('id'))
            .values_list('details__shared_to', 'count')
        )

    def _get_time_based_analysis_data(self, activities_qs, time_agg):
        """Analyzes activity over time for chart data."""
        if time_agg == 'total':
            return {'Total': activities_qs.count()}

        trunc_func, date_format = self.get_time_aggregation_params(time_agg)
        time_based_chart_data = (activities_qs.annotate(period=trunc_func)
            .values('period').annotate(count=Count('id')).order_by('period'))

        return {
            item['period'].strftime(date_format): item['count']
            for item in time_based_chart_data if item['period']
        }

    def _get_click_action_data(self, activities_qs):
        """Analyzes specific click actions."""
        return dict(
            activities_qs.filter(activity_type='click', details__action__isnull=False)
            .values_list('details__action')
            .annotate(count=Count('id'))
            .values_list('details__action', 'count')
        )

    def get(self, request, *args, **kwargs):
        activities_qs, selected_activity_type, time_agg = self.get_activities_queryset()

        # Generate data using helper methods
        user_activity_data = self._get_user_activity_data(activities_qs)
        content_popularity_data = self._get_content_popularity_data(activities_qs)
        sharing_behavior_data = self._get_sharing_behavior_data(activities_qs)
        time_based_analysis_data = self._get_time_based_analysis_data(activities_qs, time_agg)
        click_action_data = self._get_click_action_data(activities_qs)

        # Unified Table Data Generation remains in the mixin
        table_rows = self.get_aggregated_table_data(activities_qs, time_agg)

        context = {
            'selected_activity_type': selected_activity_type,
            'selected_time_agg': time_agg,
            'activity_types': UserActivity.ACTIVITY_TYPES,
            'user_activity_data': json.dumps(user_activity_data),
            'content_popularity_data': json.dumps(content_popularity_data),
            'sharing_behavior_data': json.dumps(sharing_behavior_data),
            'time_based_analysis_data': json.dumps(time_based_analysis_data),
            'click_action_data': json.dumps(click_action_data),
            'table_rows': table_rows,
        }
        return render(request, self.template_name, context)


class AdminActivityExportView(AdminActivityMixin, LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        activities_qs, _, time_agg = self.get_activities_queryset()

        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = 'attachment; filename="activity_export.csv"'
        writer = csv.writer(response)
        writer.writerow(['Period', 'Activity Type', 'Count'])

        table_rows = self.get_aggregated_table_data(activities_qs, time_agg)
        for row in table_rows:
            writer.writerow([row['period'], row['activity_type'], row['count']])

        return response

class PlaceAllView(ListView):
    model = Place
    template_name = 'review/place_all.html'
    context_object_name = 'places'
    paginate_by = 10
    queryset = Place.objects.all().order_by('-id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'สถานที่ใหม่ทั้งหมด'
        context['title_class'] = 'recommend-title text-3xl font-bold text-transparent bg-clip-text drop-shadow-lg mt-8 animate-gradient'
        return context

class PopularityView(ListView):
    model = Place
    template_name = 'review/popularity.html'
    context_object_name = 'places'
    paginate_by = 10

    def get_queryset(self):
        popular_place_ids = get_popularity_based_recommendations(num_recommendations=50)
        if not popular_place_ids:
            return Place.objects.order_by('-visit_count', '-average_rating')

        ordering = Case(*[When(id=place_id, then=pos) for pos, place_id in enumerate(popular_place_ids)], output_field=models.IntegerField())
        return Place.objects.filter(id__in=popular_place_ids).order_by(ordering)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'สถานที่ยอดนิยม'
        context['title_class'] = 'recommend-title text-3xl font-bold text-transparent bg-clip-text drop-shadow-lg mt-8 animate-gradient'
        return context

class RecommendationView(LoginRequiredMixin, ListView):
    model = Place
    template_name = 'review/recommend.html'
    context_object_name = 'places'
    paginate_by = 10

    def get_queryset(self):
        collab_data = user_based.get_user_collaborative_filtering_data()
        recommended_place_ids = recommendation_engine.get_hybrid_recommendations(self.request.user.id, collab_data, num_recommendations=50)
        if not recommended_place_ids:
            return Place.objects.none()

        ordering = Case(*[When(id=place_id, then=pos) for pos, place_id in enumerate(recommended_place_ids)], output_field=models.IntegerField())
        return Place.objects.filter(id__in=recommended_place_ids).order_by(ordering)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'เเนะนำสำหรับคุณ'
        context['title_class'] = 'recommend-title text-3xl font-bold text-transparent bg-clip-text drop-shadow-lg mt-8 animate-gradient'
        return context

class ViewPlaceReportsView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Report
    template_name = 'review/view_reports.html'
    context_object_name = 'reports'

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        place_id = self.kwargs['place_id']
        return Report.objects.filter(place_id=place_id).order_by('-reported_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Reports for Place #{self.kwargs['place_id']}"
        return context

class ViewReviewReportsView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Report
    template_name = 'review/view_reports.html'
    context_object_name = 'reports'

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        review_id = self.kwargs['review_id']
        return Report.objects.filter(review_id=review_id).order_by('-reported_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Reports for Review #{self.kwargs['review_id']}"
        return context

class ViewCommentReportsView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Report
    template_name = 'review/view_reports.html'
    context_object_name = 'reports'

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        comment_id = self.kwargs['comment_id']
        return Report.objects.filter(comment_id=comment_id).order_by('-reported_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Reports for Comment #{self.kwargs['comment_id']}"
        return context

class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = 'review/notifications.html'
    context_object_name = 'notifications'
    paginate_by = 10

    def get_queryset(self):
        return self.request.user.notifications.all()

class MarkNotificationAsReadView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        notification_id = self.kwargs.get('notification_id')
        notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
        notification.unread = False
        notification.save()
        redirect_url = reverse('notifications') # Default fallback
        if notification.action_object and hasattr(notification.action_object, 'get_absolute_url'):
            redirect_url = notification.action_object.get_absolute_url()
        elif notification.target and hasattr(notification.target, 'get_absolute_url'):
            redirect_url = notification.target.get_absolute_url()
        return HttpResponseRedirect(redirect_url)

class MarkAllNotificationsAsReadView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        request.user.notifications.update(unread=False)
        return redirect('notifications')

class DeleteNotificationView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        notification_id = self.kwargs.get('notification_id')
        notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
        notification.delete()
        return redirect('notifications')

class DeleteAllNotificationsView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        request.user.notifications.all().delete()
        return redirect('notifications')