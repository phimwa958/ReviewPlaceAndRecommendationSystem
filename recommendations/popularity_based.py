import pandas as pd
from django.core.cache import cache
from sklearn.preprocessing import MinMaxScaler
from django.conf import settings
import logging

from recommendations import cache_keys
from recommendations import data_utils

logger = logging.getLogger(__name__)

def get_popularity_based_recommendations(num_recommendations=10, force_refresh=False):
    """
    Generates a list of places ranked by a popularity score.
    The result is cached.
    """
    rec_settings = settings.RECOMMENDATION_SETTINGS
    cache_config = rec_settings.get('CACHING', {})
    POPULARITY_WEIGHTS = rec_settings.get('POPULARITY_WEIGHTS', {
        'rating': 0.3, 'reviews': 0.2, 'visits': 0.2, 'likes': 0.2, 'shares': 0.1
    })

    cache_key = cache_keys.POPULARITY_RECS_KEY
    if not force_refresh:
        cached_recs = cache.get(cache_key)
        if cached_recs:
            logger.info("Returning cached popularity recommendations.")
            return cached_recs[:num_recommendations]

    logger.info("Calculating popularity based recommendations.")

    try:
        cleaned_data = data_utils.load_and_clean_all_data(force_refresh=force_refresh)
        places_df = cleaned_data['places_df'].copy()
        likes_df = cleaned_data['likes_df']
        shares_df = cleaned_data['shares_df']

        if places_df.empty:
            return []

        # Calculate counts
        likes_count = likes_df.groupby('place_id').size().rename('likes_count') if 'place_id' in likes_df else pd.Series(name='likes_count')
        shares_count = shares_df.groupby('place_id').size().rename('shares_count') if 'place_id' in shares_df else pd.Series(name='shares_count')

        # Merge counts into places_df
        pop_df = places_df.merge(likes_count, left_index=True, right_index=True, how='left')
        pop_df = pop_df.merge(shares_count, left_index=True, right_index=True, how='left')

        # Fill NaN values for counts
        pop_df['likes_count'] = pop_df['likes_count'].fillna(0)
        pop_df['shares_count'] = pop_df['shares_count'].fillna(0)

        # Select and normalize features
        features = ['average_rating', 'total_reviews', 'visit_count', 'likes_count', 'shares_count']

        # Ensure we don't try to scale a single row or constant columns which results in NaN
        for feature in features:
            if pop_df[feature].min() == pop_df[feature].max():
                pop_df[f'{feature}_norm'] = 0.5 # or 0, or 1, depending on desired behavior
            else:
                scaler = MinMaxScaler()
                pop_df[f'{feature}_norm'] = scaler.fit_transform(pop_df[[feature]])

        # Calculate weighted popularity score
        weights = POPULARITY_WEIGHTS
        pop_df['popularity_score'] = (
            pop_df['average_rating_norm'] * weights['rating'] +
            pop_df['total_reviews_norm'] * weights['reviews'] +
            pop_df['visit_count_norm'] * weights['visits'] +
            pop_df['likes_count_norm'] * weights['likes'] +
            pop_df['shares_count_norm'] * weights['shares']
        )

        # Sort and get recommendations
        sorted_df = pop_df.sort_values(by='popularity_score', ascending=False)
        recommendations = sorted_df.index.tolist()

        # Cache the result
        timeout = cache_config.get('GLOBAL_CACHE_TIMEOUT', 3600 * 2)
        cache.set(cache_key, recommendations, timeout=timeout)

        return recommendations[:num_recommendations]

    except Exception as e:
        logger.error(f"Error in popularity-based recommendations: {e}")
        return []
