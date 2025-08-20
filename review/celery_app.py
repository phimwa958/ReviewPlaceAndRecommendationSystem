# celery_app.py
import os
from celery import Celery
from celery.schedules import crontab

# -----------------------------
# Django settings
# -----------------------------
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'review.settings')

# -----------------------------
# Celery app initialization
# -----------------------------
app = Celery('review')
app.config_from_object('django.conf:settings', namespace='CELERY')

# Autodiscover tasks from installed apps
app.autodiscover_tasks()

# -----------------------------
# Celery Beat Schedule
# -----------------------------
app.conf.beat_schedule = {
    # Batch recommendation every 6 hours
    'generate-batch-recommendations-every-6-hours': {
        'task': 'recommendations.tasks.generate_batch_recommendations',
        'schedule': crontab(minute=0, hour='*/6'),
    },
    # Global rebuild every 30 minutes
    'schedule-global-rebuild-every-30-minutes': {
        'task': 'recommendations.tasks.schedule_global_rebuild_if_needed',
        'schedule': crontab(minute='*/30'),
    },
}

# -----------------------------
# Debug task
# -----------------------------
@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
