from django.contrib import admin
from django.urls import path, include # Import include
from django.conf import settings # Import settings
from django.conf.urls.static import static # Import static

urlpatterns = [
    path('', include('review_place.urls')), # Moved this line up
    path('admin/', admin.site.urls),
]

# Add the following lines for media files
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
