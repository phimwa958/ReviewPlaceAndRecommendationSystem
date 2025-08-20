import pandas as pd
from django.core.cache import cache
from review_place.models import Review, CustomUser, Place, PlaceLike, UserActivity
from recommendations import cache_keys
from django.conf import settings
import logging
from itertools import islice

logger = logging.getLogger(__name__)

# --- Data Fetching Methods ---

def get_user_data(use_iterator=False):
    users = CustomUser.objects.all().values('id', 'gender', 'date_of_birth')
    if use_iterator:
        return users.iterator()
    return pd.DataFrame(list(users))

def get_place_data():
    places = Place.objects.all().values(
        'id', 'place_name', 'category', 'location', 'description',
        'average_rating', 'price_range', 'total_reviews', 'visit_count'
    )
    return pd.DataFrame(list(places))

def get_review_data(use_iterator=False):
    reviews = Review.objects.filter(status='published').values('user_id', 'place_id', 'rating')
    if use_iterator:
        return reviews.iterator()
    return pd.DataFrame(list(reviews))

def get_like_data(use_iterator=False):
    likes = PlaceLike.objects.all().values('user_id', 'place_id')
    if use_iterator:
        return likes.iterator()
    return pd.DataFrame(list(likes))

def get_visit_data(use_iterator=False):
    visits = UserActivity.objects.filter(activity_type='view', content_type__model='place').values('user_id', 'object_id')
    if use_iterator:
        return visits.iterator()
    df = pd.DataFrame(list(visits))
    df = df.rename(columns={'object_id': 'place_id'})
    return df

def get_share_data(use_iterator=False):
    shares = UserActivity.objects.filter(activity_type='share', content_type__model='place').values('user_id', 'object_id')
    if use_iterator:
        return shares.iterator()
    df = pd.DataFrame(list(shares))
    df = df.rename(columns={'object_id': 'place_id'})
    return df

# --- Data Cleaning Methods ---

def _clean_users_df(df):
    if df.empty:
        return df.set_index('id') if 'id' in df.columns else df

    df_cleaned = df.copy()
    df_cleaned.loc[:, 'gender'] = df_cleaned['gender'].fillna("Unknown")

    today = pd.to_datetime('today').date()
    df_cleaned.loc[:, 'age'] = df_cleaned['date_of_birth'].apply(
        lambda dob: (today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))) if pd.notnull(dob) else None
    )

    if 'age' in df_cleaned.columns and df_cleaned['age'].isnull().any():
        mean_age = df_cleaned['age'].mean()
        df_cleaned.loc[:, 'age'] = df_cleaned['age'].fillna(mean_age)

    df_cleaned.drop_duplicates(subset='id', inplace=True)
    df_cleaned.set_index('id', inplace=True)
    return df_cleaned

def _clean_places_df(df):
    if df.empty:
        return df.set_index('id') if 'id' in df.columns else df

    df_cleaned = df.copy()
    df_cleaned.rename(columns={'place_name': 'name'}, inplace=True)
    df_cleaned.loc[:, 'category'] = df_cleaned['category'].fillna("Unknown")
    df_cleaned.loc[:, 'location'] = df_cleaned['location'].fillna("Unknown")
    df_cleaned.loc[:, 'description'] = df_cleaned['description'].fillna("")

    if not df_cleaned['price_range'].mode().empty:
        df_cleaned.loc[:, 'price_range'] = df_cleaned['price_range'].fillna(df_cleaned['price_range'].mode()[0])
    else:
        df_cleaned.loc[:, 'price_range'] = df_cleaned['price_range'].fillna("Unknown")

    df_cleaned.loc[:, 'average_rating'] = df_cleaned['average_rating'].fillna(df_cleaned['average_rating'].mean())
    df_cleaned.loc[:, 'total_reviews'] = df_cleaned['total_reviews'].fillna(0)
    df_cleaned.loc[:, 'visit_count'] = df_cleaned['visit_count'].fillna(0)
    df_cleaned.drop_duplicates(subset='id', inplace=True)
    df_cleaned.set_index('id', inplace=True)
    return df_cleaned

def clean_interactions_df(df, interaction_type):
    if df.empty:
        return df
    df_cleaned = df.copy()
    df_cleaned.dropna(subset=['user_id', 'place_id'], inplace=True)
    if interaction_type == 'reviews':
        df_cleaned.loc[:, 'rating'] = pd.to_numeric(df_cleaned['rating'], errors='coerce')
        df_cleaned.loc[:, 'rating'] = df_cleaned['rating'].fillna(df_cleaned['rating'].mean())
        df_cleaned.drop_duplicates(subset=['user_id', 'place_id'], keep='last', inplace=True)
    else: # likes/visits
        df_cleaned.drop_duplicates(subset=['user_id', 'place_id'], inplace=True)
    return df_cleaned

# --- Data Loading and Caching ---

def load_and_clean_all_data(force_refresh=False):
    cache_config = settings.RECOMMENDATION_SETTINGS.get('CACHING', {})
    if not force_refresh:
        cached_data = cache.get(cache_keys.CLEANED_DATA_KEY)
        if cached_data is not None:
            logger.info("Serving cleaned data from cache.")
            return cached_data

    logger.info("Loading and cleaning all data from database.")
    users_df = _clean_users_df(get_user_data())
    places_df = _clean_places_df(get_place_data())
    reviews_df = clean_interactions_df(get_review_data(), 'reviews')
    likes_df = clean_interactions_df(get_like_data(), 'likes')
    visits_df = clean_interactions_df(get_visit_data(), 'visits')
    shares_df = clean_interactions_df(get_share_data(), 'shares')

    data = {
        'users_df': users_df,
        'places_df': places_df,
        'reviews_df': reviews_df,
        'likes_df': likes_df,
        'visits_df': visits_df,
        'shares_df': shares_df
    }

    timeout = cache_config.get('GLOBAL_CACHE_TIMEOUT', 3600 * 2)
    cache.set(cache_keys.CLEANED_DATA_KEY, data, timeout=timeout)
    return data

def get_all_scored_interactions(cleaned_data):
    # Load settings from Django's settings
    rec_settings = settings.RECOMMENDATION_SETTINGS
    REVIEW_MAX = rec_settings['REVIEW_MAX']
    LIKE_WEIGHT = rec_settings['LIKE_WEIGHT']
    VISIT_WEIGHT = rec_settings['VISIT_WEIGHT']
    SHARE_WEIGHT = rec_settings.get('SHARE_WEIGHT', 0.4) # Default to 0.4 if not set

    reviews_df = cleaned_data.get('reviews_df', pd.DataFrame())
    likes_df = cleaned_data.get('likes_df', pd.DataFrame())
    visits_df = cleaned_data.get('visits_df', pd.DataFrame())
    shares_df = cleaned_data.get('shares_df', pd.DataFrame())

    reviews_df_scored = reviews_df.assign(score=reviews_df['rating'] / REVIEW_MAX) if not reviews_df.empty else pd.DataFrame(columns=['user_id', 'place_id', 'score'])
    likes_df_scored = likes_df.assign(score=LIKE_WEIGHT) if not likes_df.empty else pd.DataFrame(columns=['user_id', 'place_id', 'score'])
    visits_df_scored = visits_df.assign(score=VISIT_WEIGHT) if not visits_df.empty else pd.DataFrame(columns=['user_id', 'place_id', 'score'])
    shares_df_scored = shares_df.assign(score=SHARE_WEIGHT) if not shares_df.empty else pd.DataFrame(columns=['user_id', 'place_id', 'score'])

    all_interactions = pd.concat([
        reviews_df_scored[['user_id', 'place_id', 'score']],
        likes_df_scored[['user_id', 'place_id', 'score']],
        visits_df_scored[['user_id', 'place_id', 'score']],
        shares_df_scored[['user_id', 'place_id', 'score']]
    ])
    return all_interactions

def chunked_iterator(iterable, size):
    """Yield successive n-sized chunks from an iterable."""
    it = iter(iterable)
    while True:
        chunk = tuple(islice(it, size))
        if not chunk:
            return
        yield chunk
