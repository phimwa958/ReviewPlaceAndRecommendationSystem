from django.core.cache import cache
from django.conf import settings
import logging
from recommendations import cache_keys
from recommendations import data_utils

logger = logging.getLogger(__name__)

def get_user_interacted_places(user_id):
    """
    Retrieves the set of place IDs a user has interacted with.
    If not in cache, it calculates it from the database and caches it.
    """
    cache_config = settings.RECOMMENDATION_SETTINGS.get('CACHING', {})
    cache_key = cache_keys.user_interacted_places_key(user_id)

    interacted_set = cache.get(cache_key)

    if interacted_set is None:
        logger.info(f"Interacted places for user {user_id} not in cache. Calculating.")

        # We need the full cleaned data to get all interactions
        cleaned_data = data_utils.load_and_clean_all_data()
        all_interactions_df = data_utils.get_all_scored_interactions(cleaned_data)

        if all_interactions_df.empty:
            interacted_set = set()
        else:
            user_interactions = all_interactions_df[all_interactions_df['user_id'] == user_id]
            interacted_set = set(user_interactions['place_id'].unique())

        timeout = cache_config.get('USER_INTERACTIONS_TIMEOUT', 3600) # Cache for 1 hour
        cache.set(cache_key, interacted_set, timeout=timeout)

    return interacted_set
