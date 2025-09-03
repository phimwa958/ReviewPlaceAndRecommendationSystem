from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import ImproperlyConfigured

class OwnerOrStaffRequiredMixin(UserPassesTestMixin):
    """
    Mixin to verify that the current user is the owner of the object or is a staff member.
    It checks for an 'owner' or 'user' attribute on the object.
    """
    def test_func(self):
        # Set self.object so it can be used by other methods like handle_no_permission
        self.object = self.get_object()
        user = self.request.user

        if user.is_staff:
            return True

        if hasattr(self.object, 'owner'):
            return self.object.owner == user
        elif hasattr(self.object, 'user'):
            return self.object.user == user
        else:
            raise ImproperlyConfigured(
                "OwnerOrStaffRequiredMixin requires the object to have an 'owner' or 'user' attribute."
            )

from django.db.models.functions import TruncDay, TruncMonth, TruncYear
from django.db.models import Count
from .models import UserActivity

class FormContextMixin:
    """
    A mixin to automatically add form-related context variables.
    Allows setting static variables as class attributes (e.g., form_title)
    and dynamic ones via methods (e.g., get_form_subtitle).
    """
    title = ''
    form_title = ''
    form_btn = 'Submit'
    with_media = False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['title'] = self.get_title()
        context['form_title'] = self.get_form_title()
        context['form_btn'] = self.get_form_btn()
        context['with_media'] = self.with_media

        if hasattr(self, 'get_form_subtitle'):
            context['form_subtitle'] = self.get_form_subtitle()

        if hasattr(self, 'get_cancel_url'):
            context['cancel_url'] = self.get_cancel_url()

        return context

    def get_title(self):
        return self.title

    def get_form_title(self):
        return self.form_title or self.title

    def get_form_btn(self):
        return self.form_btn


class ImageHandlingMixin:
    """
    A mixin to handle the creation and deletion of related image objects.

    Views using this mixin must define:
    - `image_model`: The model class for image instances (e.g., PlaceImage).
    - `image_form_field`: The form field name for new images (e.g., 'images').
    - `image_foreign_key_field`: The foreign key field on the image model (e.g., 'place').
    """
    image_model = None
    image_form_field = None
    image_foreign_key_field = None

    def form_valid(self, form):
        # Proceed with the default form validation, which saves the main object.
        # This ensures the main object is valid and saved before we modify related images.
        response = super().form_valid(form)

        # Check for required attributes for image handling.
        if not all([self.image_model, self.image_form_field, self.image_foreign_key_field]):
            raise ImproperlyConfigured(
                "ImageHandlingMixin requires 'image_model', 'image_form_field', "
                "and 'image_foreign_key_field' to be set."
            )

        # Handle image deletion.
        # The form is valid, so 'delete_images' is in cleaned_data if it was submitted.
        if 'delete_images' in form.cleaned_data:
            images_to_delete = form.cleaned_data['delete_images']
            if images_to_delete:
                images_to_delete.delete()  # Bulk delete selected images

        # Handle new image uploads.
        for image_file in self.request.FILES.getlist(self.image_form_field):
            image_data = {
                self.image_foreign_key_field: self.object,
                'image': image_file
            }
            self.image_model.objects.create(**image_data)

        return response


class AdminActivityMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff

    def get_activities_queryset(self):
        # Determine the source of parameters (GET for display, POST for export)
        params = self.request.POST if self.request.method == 'POST' else self.request.GET

        activities_qs = UserActivity.objects.select_related('user', 'content_type').all()

        # Filtering parameters
        selected_activity_type = params.get('activity_type')
        time_agg = params.get('time_agg', 'total')

        filters = {}
        if selected_activity_type and selected_activity_type != 'all':
            filters['activity_type'] = selected_activity_type

        if filters:
            activities_qs = activities_qs.filter(**filters)

        return activities_qs, selected_activity_type, time_agg

    def get_time_aggregation_params(self, time_agg):
        if time_agg == 'yearly':
            trunc_func = TruncYear('timestamp')
            date_format = '%Y'
        elif time_agg == 'monthly':
            trunc_func = TruncMonth('timestamp')
            date_format = '%Y-%m'
        else: # daily
            trunc_func = TruncDay('timestamp')
            date_format = '%Y-%m-%d'
        return trunc_func, date_format

    def get_aggregated_table_data(self, activities_qs, time_agg):
        if time_agg == 'total':
            table_data_qs = (activities_qs
                             .values('activity_type')
                             .annotate(count=Count('id'))
                             .order_by('activity_type'))
            table_rows = [
                {'period': 'Total', 'activity_type': UserActivity.ACTIVITY_TYPE_CHOICES_MAP.get(item['activity_type'], item['activity_type']), 'count': item['count']}
                for item in table_data_qs
            ]
        else:
            trunc_func, date_format = self.get_time_aggregation_params(time_agg)
            table_data_qs = (activities_qs.annotate(period=trunc_func)
                             .values('period', 'activity_type')
                             .annotate(count=Count('id'))
                             .order_by('-period', 'activity_type'))
            table_rows = [
                {'period': item['period'].strftime(date_format), 'activity_type': UserActivity.ACTIVITY_TYPE_CHOICES_MAP.get(item['activity_type'], item['activity_type']), 'count': item['count']}
                for item in table_data_qs if item['period']
            ]
        return table_rows
