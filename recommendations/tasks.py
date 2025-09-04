import logging
from celery import shared_task
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
import redis
from review_place.models import CustomUser
from recommendations import cache_keys, user_based, data_utils
from recommendations.engine import recommendation_engine

logger = logging.getLogger(__name__)

# Lock timeout (in seconds)
GLOBAL_INVALIDATION_LOCK_TIMEOUT = 600  # 10 minutes

def get_redis_client():
    return redis.from_url(settings.CELERY_BROKER_URL)

def is_lock_active(lock_key='global_rebuild_lock'):
    return cache.get(lock_key) is not None

def set_lock(lock_key='global_rebuild_lock', timeout=GLOBAL_INVALIDATION_LOCK_TIMEOUT):
    return cache.add(lock_key, 'locked', timeout=timeout)

def release_lock(lock_key='global_rebuild_lock'):
    cache.delete(lock_key)

# -----------------------------
# Global Cache Rebuild
# -----------------------------
@shared_task(bind=True, max_retries=None, default_retry_delay=10)
def schedule_global_rebuild_if_needed(self):
    """
    Schedule global rebuild if not already running.
    Retry automatically if lock is active.
    """
    lock_key = 'global_rebuild_lock'
    if set_lock(lock_key):
        logger.info("Acquired global rebuild lock. Scheduling rebuild task.")
        rebuild_global_recommendation_caches.delay()
    else:
        logger.info("Lock active, retrying in 10 seconds...")
        raise self.retry()  # Retry task automatically

@shared_task
def rebuild_global_recommendation_caches():
    """
    Rebuilds all shared caches required by the recommendation system.
    This is the single source of truth for rebuilding caches.
    """
    lock_key = 'global_rebuild_lock'
    logger.info("Starting proactive global cache rebuild.")
    try:
        # First, rebuild the base cleaned data, allowing it to write to the cache.
        data_utils.load_and_clean_all_data(force_refresh=True, allow_rebuild=True)

        # Now, rebuild the other caches that depend on the cleaned data.
        recommendation_engine.rebuild_user_similarity_cache()
        recommendation_engine.rebuild_scaled_item_profiles_cache()

        logger.info("Finished proactive global cache rebuild.")
    finally:
        release_lock(lock_key)

# -----------------------------
# Similar Places Invalidation
# -----------------------------
@shared_task
def invalidate_similar_places_task(place_id):
    key = cache_keys.place_similar_key(place_id)
    cache.delete(key)
    logger.info(f"Invalidated similar places cache for place {place_id}.")

# -----------------------------
# Batch Recommendations
# -----------------------------
@shared_task
def generate_batch_recommendations():
    logger.info("Starting batch recommendation generation.")

    seven_days_ago = timezone.now() - timedelta(days=7)
    active_users = CustomUser.objects.filter(last_login__gte=seven_days_ago)

    if not active_users.exists():
        logger.info("No active users found for batch processing.")
        return

    # Pre-fetch collaborative filtering data once before the loop.
    # force_refresh=True ensures we get the latest data, not a potentially stale cache.
    # allow_rebuild=True is critical for the background task to be able to build the cache.
    collab_data = user_based.get_user_collaborative_filtering_data(force_refresh=True, allow_rebuild=True)

    if not collab_data or collab_data.get('user_item_matrix') is None or collab_data.get('user_item_matrix').empty:
        logger.error("Failed to generate batch recommendations: Collaborative filtering data is not available or empty.")
        return

    logger.info(f"Found {active_users.count()} active users for batch processing.")

    for user in active_users:
        try:
            # Pass the pre-fetched collab_data to the scoring function
            scores = recommendation_engine._compute_hybrid_scores(user.id, collab_data)
            if scores:
                key = cache_keys.batch_recommendations_key(user.id)
                timeout = recommendation_engine.cache_config.get('GLOBAL_CACHE_TIMEOUT', 3600 * 2)
                cache.set(key, scores, timeout=timeout)
                logger.info(f"Successfully generated batch recommendations for user {user.id}")
        except Exception as e:
            logger.error(f"Failed to generate batch recommendations for user {user.id}: {e}")

    logger.info("Finished batch recommendation generation.")

# -----------------------------
# Realtime Interaction
# -----------------------------
@shared_task
def process_realtime_interaction(user_id, place_id, interaction_score):
    try:
        similar_places = recommendation_engine.get_similar_places(place_id)
        if not similar_places:
            logger.info(f"No similar places found for place {place_id}, skipping boost.")
            return

        boost_value = interaction_score * 0.1  # 10% boost
        key = cache_keys.boost_scores_key(user_id)
        redis_client = get_redis_client()

        pipeline = redis_client.pipeline()
        for similar_place_id in similar_places:
            pipeline.hincrbyfloat(key, similar_place_id, boost_value)

        pipeline.expire(key, 3600 * 24)
        pipeline.execute()

        logger.info(f"Applied boost scores for user {user_id} based on place {place_id}.")
    except Exception as e:
        logger.error(f"Error processing realtime interaction for user {user_id}, place {place_id}: {e}")
