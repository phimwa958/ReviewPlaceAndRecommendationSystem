import logging
import redis
from django.conf import settings
from django.core.cache import cache

from recommendations import (
    cache_keys,
    cache_management,
    content_based,
    data_utils,
    hybrid,
    user_based
)

logger = logging.getLogger(__name__)

class RecommendationEngine:
    """
    The main interface for the recommendation system.
    This class orchestrates calls to the various underlying modules.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Load settings from Django's settings for easy access
        self.settings = settings.RECOMMENDATION_SETTINGS
        self.cache_config = self.settings.get('CACHING', {})

    # --- Public-Facing API Methods ---

    def get_hybrid_recommendations(self, user_id, collab_data, num_recommendations=50, filter_interacted=True, force_refresh=False):
        """
        The Serving Layer. Merges batch recommendations with real-time speed layer scores.
        This operation is fast and does not cache its own results to prevent race conditions.
        """
        # 1. Fetch Batch Layer Recommendations
        batch_scores = self._get_batch_recommendations(user_id, collab_data, force_refresh=force_refresh)

        # 2. Fetch Speed Layer Boost Scores
        boost_key = cache_keys.boost_scores_key(user_id)
        redis_client = redis.from_url(settings.CELERY_BROKER_URL)
        boost_scores_raw = redis_client.hgetall(boost_key)
        boost_scores = {int(k.decode()): float(v.decode()) for k, v in boost_scores_raw.items()}

        # 3. Merge Scores
        final_scores = batch_scores.copy()
        for place_id, boost in boost_scores.items():
            final_scores[place_id] = final_scores.get(place_id, 0) + boost

        # 4. Filter and Sort
        sorted_recommendations = sorted(final_scores.items(), key=lambda item: item[1], reverse=True)

        if filter_interacted:
            user_interacted_places = cache_management.get_user_interacted_places(user_id)
            sorted_recommendations = [rec for rec in sorted_recommendations if rec[0] not in user_interacted_places]

        final_recommendations_ids = [rec[0] for rec in sorted_recommendations[:num_recommendations]]
        return final_recommendations_ids

    def get_similar_places(self, place_id, num_recommendations=5, force_refresh=False):
        """
        Finds places that are most similar to a given place based on content.
        """
        return content_based.get_similar_places(place_id, num_recommendations, force_refresh)

    # --- Serving & Batch Layer ---

    def _get_batch_recommendations(self, user_id, collab_data, force_refresh=False):
        """
        Fetches pre-calculated batch recommendations. If they don't exist,
        it computes them synchronously for this user as a fallback.
        """
        batch_key = cache_keys.batch_recommendations_key(user_id)
        if not force_refresh:
            batch_scores = cache.get(batch_key)
            if batch_scores is not None:
                return batch_scores or {}

        self.logger.warning(f"No batch recommendations for user {user_id}. Generating synchronously.")
        # Fetch collab_data here and pass it down
        # collab_data is now passed from get_hybrid_recommendations
        batch_scores = self._compute_hybrid_scores(user_id, collab_data)
        if batch_scores:
            timeout = self.cache_config.get('GLOBAL_CACHE_TIMEOUT', 3600 * 2)
            cache.set(batch_key, batch_scores, timeout=timeout)
        return batch_scores or {}

    def _compute_hybrid_scores(self, user_id, collab_data):
        """
        A wrapper that calls the core hybrid score computation logic.
        """
        return hybrid.compute_hybrid_scores(user_id, collab_data)

    # --- Cache Rebuilding Facade ---
    # These methods provide a clean API for the Celery tasks to call.

    def rebuild_user_similarity_cache(self):
        """Triggers the rebuild of the user similarity cache."""
        return user_based.rebuild_user_similarity_cache()

    def rebuild_scaled_item_profiles_cache(self):
        """Triggers the rebuild of the scaled item profiles cache."""
        return content_based.rebuild_scaled_item_profiles_cache()

    # --- Data Loading Facade ---

    def load_and_clean_all_data(self, force_refresh=False):
        """Facade for the data loading and cleaning utility."""
        return data_utils.load_and_clean_all_data(force_refresh)

    def _get_all_scored_interactions(self, cleaned_data):
        """Facade for getting scored interactions."""
        return data_utils.get_all_scored_interactions(cleaned_data)

    def _create_item_profiles(self, places_df, users_df, all_interactions):
        """Facade for creating item profiles, needed by evaluation command."""
        # This is a bit of a leaky abstraction, but required for the eval command
        # without duplicating the logic there.
        return content_based._create_item_profiles(places_df, users_df, all_interactions)


# Singleton instance for easy access throughout the Django application
recommendation_engine = RecommendationEngine()
