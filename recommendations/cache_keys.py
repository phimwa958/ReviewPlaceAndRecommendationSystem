"""
Centralized cache key generation for the recommendation system.
"""
from django.conf import settings

# --- Key Constants ---
# These are defined here to avoid magic strings in the recommendation engine.
# They can be versioned by changing the string value.
CLEANED_DATA_KEY = 'cleaned_data_all_v4'
USER_COLLABORATIVE_FILTERING_DATA_KEY = 'user_collaborative_filtering_data_v1'
SCALED_PROFILES_KEY = 'scaled_item_profiles_v3'
POPULARITY_RECS_KEY = 'popularity_recs_v1'
USER_INTERACTED_PLACES_KEY_TEMPLATE = 'user_interacted_places_{user_id}_v2'


# --- Key Generation Functions ---



def place_similar_key(place_id):
    """
    Generate cache key for similar places using a template from settings.
    """
    template = settings.RECOMMENDATION_SETTINGS['CACHING'].get('SIMILAR_PLACES_KEY_TEMPLATE', 'similar_to:{place_id}_v1')
    return template.format(place_id=place_id)

def batch_recommendations_key(user_id):
    """
    Generate cache key for batch-generated recommendations with scores.
    """
    template = settings.RECOMMENDATION_SETTINGS['CACHING'].get('BATCH_RECS_KEY_TEMPLATE', 'batch_recs_{user_id}_v1')
    return template.format(user_id=user_id)

def boost_scores_key(user_id):
    """
    Generate cache key for the Redis Hash holding real-time boost scores.
    """
    template = settings.RECOMMENDATION_SETTINGS['CACHING'].get('BOOST_SCORES_KEY_TEMPLATE', 'user:{user_id}:boost_scores')
    return template.format(user_id=user_id)

def user_interacted_places_key(user_id):
    """
    Generate cache key for the set of places a user has interacted with.
    """
    return USER_INTERACTED_PLACES_KEY_TEMPLATE.format(user_id=user_id)
