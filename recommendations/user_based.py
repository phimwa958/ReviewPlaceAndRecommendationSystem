import pandas as pd
import numpy as np
from django.core.cache import cache
from scipy.sparse import csr_matrix
from sklearn.metrics.pairwise import cosine_similarity
import logging
from django.conf import settings

from recommendations import cache_keys, data_utils, cache_management
from recommendations.decorators import cache_with_build_lock

logger = logging.getLogger(__name__)


def _rebuild_user_similarity_matrix():
    """
    Core logic to compute the user similarity matrix using iterators for memory efficiency.
    """
    logger.info("Starting user similarity matrix computation using iterators.")

    rec_settings = settings.RECOMMENDATION_SETTINGS
    REVIEW_MAX = rec_settings['REVIEW_MAX']
    LIKE_WEIGHT = rec_settings['LIKE_WEIGHT']
    VISIT_WEIGHT = rec_settings['VISIT_WEIGHT']
    SHARE_WEIGHT = rec_settings.get('SHARE_WEIGHT', 0.4)

    chunk_size = 2000
    interaction_chunks = []

    # Process reviews
    for chunk in data_utils.chunked_iterator(data_utils.get_review_data(use_iterator=True), chunk_size):
        df_chunk = data_utils.clean_interactions_df(pd.DataFrame(list(chunk)), 'reviews')
        interaction_chunks.append(df_chunk.assign(score=df_chunk['rating'] / REVIEW_MAX)[['user_id', 'place_id', 'score']])

    # Process likes
    for chunk in data_utils.chunked_iterator(data_utils.get_like_data(use_iterator=True), chunk_size):
        df_chunk = data_utils.clean_interactions_df(pd.DataFrame(list(chunk)), 'likes')
        interaction_chunks.append(df_chunk.assign(score=LIKE_WEIGHT)[['user_id', 'place_id', 'score']])

    # Process visits
    for chunk in data_utils.chunked_iterator(data_utils.get_visit_data(use_iterator=True), chunk_size):
        # The iterator returns dicts with 'object_id', so we must rename it here.
        df_chunk_raw = pd.DataFrame(list(chunk))
        if not df_chunk_raw.empty:
            df_chunk_renamed = df_chunk_raw.rename(columns={'object_id': 'place_id'})
            df_chunk_cleaned = data_utils.clean_interactions_df(df_chunk_renamed, 'visits')
            interaction_chunks.append(df_chunk_cleaned.assign(score=VISIT_WEIGHT)[['user_id', 'place_id', 'score']])

    # Process shares
    for chunk in data_utils.chunked_iterator(data_utils.get_share_data(use_iterator=True), chunk_size):
        df_chunk_raw = pd.DataFrame(list(chunk))
        if not df_chunk_raw.empty:
            df_chunk_renamed = df_chunk_raw.rename(columns={'object_id': 'place_id'})
            df_chunk_cleaned = data_utils.clean_interactions_df(df_chunk_renamed, 'shares')
            interaction_chunks.append(df_chunk_cleaned.assign(score=SHARE_WEIGHT)[['user_id', 'place_id', 'score']])

    if not interaction_chunks:
        logger.warning("No interaction data available for similarity matrix.")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    all_interactions = pd.concat(interaction_chunks, ignore_index=True)

    user_item_df = all_interactions.groupby(['user_id', 'place_id'])['score'].sum().unstack().fillna(0)
    if user_item_df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    user_means = user_item_df.replace(0, np.nan).mean(axis=1)
    user_item_df_centered = user_item_df.sub(user_means, axis=0).fillna(0)
    user_item_sparse = csr_matrix(user_item_df_centered.values)

    n_users = user_item_sparse.shape[0]
    sim_chunk_size = 500
    similarity_chunks = []
    for i in range(0, n_users, sim_chunk_size):
        end = min(i + sim_chunk_size, n_users)
        chunk = user_item_sparse[i:end]
        chunk_sim = cosine_similarity(chunk, user_item_sparse)
        similarity_chunks.append(chunk_sim)

    full_similarity_matrix = np.vstack(similarity_chunks)
    user_similarity_df = pd.DataFrame(full_similarity_matrix, index=user_item_df.index, columns=user_item_df.index)
    logger.info("Finished user similarity matrix computation.")
    return user_similarity_df, user_item_df, all_interactions

def rebuild_user_similarity_cache():
    """
    Computes and caches the user similarity matrix and the user-item matrix.
    This function is intended to be called by a cache-building process (e.g., a task).
    """
    try:
        user_similarity_df, user_item_matrix, all_interactions = _rebuild_user_similarity_matrix()
        if not user_similarity_df.empty and not user_item_matrix.empty and not all_interactions.empty:
            data_to_cache = {
                'similarity_matrix': user_similarity_df,
                'user_item_matrix': user_item_matrix,
                'all_interactions': all_interactions
            }
            cache_config = settings.RECOMMENDATION_SETTINGS.get('CACHING', {})
            timeout = cache_config.get('GLOBAL_CACHE_TIMEOUT', 3600 * 2)
            cache.set(cache_keys.USER_COLLABORATIVE_FILTERING_DATA_KEY, data_to_cache, timeout=timeout)
            logger.info("Successfully rebuilt and cached user collaborative filtering data.")
            return data_to_cache
        logger.warning("Rebuild process resulted in empty dataframes. Not caching.")
        return {}
    except Exception as e:
        logger.error(f"Error rebuilding user similarity cache: {e}")
        return {}

# Note: The decorator needs a class instance to work, so we can't decorate a standalone function
# in the same way. We will handle the locking logic inside the getter function instead.
def get_user_collaborative_filtering_data(force_refresh=False, allow_rebuild=False):
    """
    Gets user collaborative filtering data from cache.
    If not available, it can trigger a rebuild if `allow_rebuild` is True.
    """
    if not force_refresh:
        cached_value = cache.get(cache_keys.USER_COLLABORATIVE_FILTERING_DATA_KEY)
        if cached_value is not None:
            logger.debug(f"Serving '{cache_keys.USER_COLLABORATIVE_FILTERING_DATA_KEY}' from cache.")
            return cached_value

    if not allow_rebuild:
        logger.warning(f"User collaborative filtering data not found in cache. "
                       f"Rebuild not allowed in this context. Returning empty data.")
        return {}

    lock_key = f"user_collab_lock:{cache_keys.USER_COLLABORATIVE_FILTERING_DATA_KEY}"
    lock_timeout = 600

    if cache.add(lock_key, 'building', timeout=lock_timeout):
        logger.info(f"Acquired lock '{lock_key}' to build resource.")
        try:
            new_value = rebuild_user_similarity_cache()
            return new_value
        finally:
            cache.delete(lock_key)
            logger.info(f"Released lock '{lock_key}'.")
    else:
        logger.info(f"Cache build for '{cache_keys.USER_COLLABORATIVE_FILTERING_DATA_KEY}' is locked. Waiting...")
        time.sleep(5)
        # In a waiting scenario, we should not force a rebuild, just try to get the value again.
        return get_user_collaborative_filtering_data(force_refresh=False, allow_rebuild=False)


def get_user_based_recommendations(user_id, collab_data, num_recommendations=10, filter_interacted=True):
    logger.info(f"UBF: Starting user-based recommendations for user {user_id}")
    try:
        if not collab_data:
            logger.warning(f"UBF: Exiting for user {user_id} because collab_data is not available.")
            return []

        user_similarity_df = collab_data.get('similarity_matrix')
        user_item_matrix = collab_data.get('user_item_matrix')

        if user_similarity_df is None or user_item_matrix is None or user_similarity_df.empty or user_item_matrix.empty:
            logger.warning(f"UBF: Exiting for user {user_id} due to missing or empty matrices.")
            return []
        
        if user_id not in user_similarity_df.index:
            logger.warning(f"UBF: Exiting because user {user_id} not in similarity matrix.")
            return []

        num_users = len(user_similarity_df.columns)
        top_k = max(10, int(num_users * 0.1))
        logger.info(f"UBF: User {user_id}: Found {num_users} users in matrix, using top_k={top_k}.")

        similar_users = user_similarity_df[user_id].sort_values(ascending=False)
        similar_users = similar_users[similar_users > 0][1:top_k + 1]

        if similar_users.empty:
            logger.warning(f"UBF: User {user_id} has no similar users with score > 0. Exiting.")
            return []
        
        logger.info(f"UBF: User {user_id}: Found {len(similar_users)} similar users.")

        place_scores = {}
        total_similarity = {}

        for similar_user_id, similarity_score in similar_users.items():
            if similar_user_id in user_item_matrix.index:
                similar_user_ratings = user_item_matrix.loc[similar_user_id]
                for place_id, rating in similar_user_ratings[similar_user_ratings > 0].items():
                    place_scores.setdefault(place_id, 0)
                    place_scores[place_id] += similarity_score * rating
                    total_similarity.setdefault(place_id, 0)
                    total_similarity[place_id] += similarity_score
        
        if not place_scores:
            logger.warning(f"UBF: User {user_id}: No place scores generated from similar users. Exiting.")
            return []

        recommendation_scores = {
            place_id: score / total_similarity[place_id]
            for place_id, score in place_scores.items() if total_similarity.get(place_id, 0) > 0
        }
        
        logger.info(f"UBF: User {user_id}: Generated {len(recommendation_scores)} raw recommendations.")

        if filter_interacted:
            user_interacted_places = cache_management.get_user_interacted_places(user_id)
            logger.info(f"UBF: User {user_id}: Found {len(user_interacted_places)} interacted places to filter.")
            for place_id in user_interacted_places:
                recommendation_scores.pop(place_id, None)

        sorted_recommendations = sorted(recommendation_scores.items(), key=lambda item: item[1], reverse=True)
        
        final_recs = [place_id for place_id, score in sorted_recommendations[:num_recommendations]]
        logger.info(f"UBF: User {user_id}: Successfully generated {len(final_recs)} final recommendations.")
        return final_recs

    except Exception as e:
        logger.error(f"Error in user-based recommendations for user {user_id}: {e}", exc_info=True)
        return []
