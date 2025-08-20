import os
from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('DJANGO_SECRET_KEY')
DEBUG = config('DJANGO_DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = []

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'review_place',
    'recommendations.apps.RecommendationsConfig',
    'django_celery_beat',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'review.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'review.wsgi.application'

# Environment variables
MYSQL_HOST = config('MYSQL_HOST', default='db')
MYSQL_PORT = config('MYSQL_PORT', default=3307, cast=int)
MYSQL_USER = config('MYSQL_USER')
MYSQL_PASSWORD = config('MYSQL_PASSWORD')
MYSQL_DATABASE = config('MYSQL_DATABASE')

# DATABASES
if MYSQL_HOST and MYSQL_USER and MYSQL_DATABASE:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'HOST': MYSQL_HOST,
            'PORT': MYSQL_PORT,
            'USER': MYSQL_USER,
            'PASSWORD': MYSQL_PASSWORD,
            'NAME': MYSQL_DATABASE,
            'OPTIONS': {
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            }
        }
    }
    print("Using MySQL database")
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
    print("MySQL not configured, using SQLite")

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'th'
TIME_ZONE = 'Asia/Bangkok'  # หรือ 'UTC' ถ้าอยากเก็บข้อมูลเป็น UTC แล้วแปลงภายหลัง

USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'review_place.CustomUser'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='test.mailer@gmail.com')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='fake-password-for-dev')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='Test Project <test.mailer@gmail.com>')
CONTACT_EMAIL = config('CONTACT_EMAIL', default='support@testproject.local')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
        'review_place_file': {
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'review_place.log'),
            'formatter': 'standard',
        },
        'recommendations_file': {
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'recommendations.log'),
            'formatter': 'standard',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'review_place': {
            'handlers': ['console', 'review_place_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'recommendations': {
            'handlers': ['console', 'recommendations_file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://redis:6379/1", # URL for Redis server
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "TIMEOUT": 3600, # 1 hour
    }
}

# Recommendation Engine Settings
RECOMMENDATION_SETTINGS = {
    'REVIEW_MAX': 5.0,
    'LIKE_WEIGHT': 0.6,
    'VISIT_WEIGHT': 0.3,
    'SHARE_WEIGHT': 0.7,
    'DECAY_ALPHA': 0.99,
    'USER_BASED_SETTINGS': {
        'min_similarity': 0.1, # ลองปรับค่าให้ต่ำลง
},
    'POPULARITY_WEIGHTS': {
        'rating': 0.3,
        'reviews': 0.2,
        'visits': 0.1,
        'likes': 0.2,
        'shares': 0.2
    },
    'WEIGHT_CONFIG': {
        "low_threshold": 50,
        "medium_threshold": 200,
        "low_weight": (0.1, 0.3, 0.6),
        "medium_weight": (0.3, 0.4, 0.3),
        "high_weight": (0.6, 0.4, 0.0)
    },
    'CACHING': {
#        'USER_RECS_KEY_TEMPLATE': 'recommendations_{user_id}_{filter_interacted}_v3',
        'SIMILAR_PLACES_KEY_TEMPLATE': 'place_{place_id}_similar_places_v2',
        'BATCH_RECS_KEY_TEMPLATE': 'batch_recs_{user_id}_v1',
        'BOOST_SCORES_KEY_TEMPLATE': 'user:{user_id}:boost_scores',
        'USER_INTERACTIONS_TIMEOUT': 3600 * 3, # 3 hours
        'GLOBAL_CACHE_TIMEOUT': 3600 * 6, #62 hours
        'SIMILAR_PLACES_TIMEOUT': 3600 * 6, # 6 hours
        'LOCK_TIMEOUT': 300 # 5 minutes
    }
}

# Custom settings for recommendation ordering
RECOMMENDATION_ORDER_DEFAULT = 99999

# Celery Configuration
CELERY_BROKER_URL = 'redis://redis:6379/0'
CELERY_RESULT_BACKEND = 'redis://redis:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Bangkok'
CELERY_TASK_ALWAYS_EAGER = config('CELERY_TASK_ALWAYS_EAGER', default=False, cast=bool)
