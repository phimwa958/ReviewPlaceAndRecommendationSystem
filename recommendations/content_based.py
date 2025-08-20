import pandas as pd
import numpy as np
from django.core.cache import cache
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from pythainlp.tokenize import word_tokenize
from pythainlp.word_vector import WordVector
from pythainlp.corpus import thai_stopwords
from pythainlp.util import normalize
import logging
import re
import string
import time
from django.conf import settings

from review_place.models import CustomUser
from recommendations import cache_keys, data_utils, user_based, cache_management

logger = logging.getLogger(__name__)
_thai2vec_model = None

def preprocess_thai_text(text):
    if not isinstance(text, str):
        return []
    text = normalize(text)
    text = re.sub(rf'[\s{string.punctuation}a-zA-Z0-9]+', '', text)
    tokens = word_tokenize(text, engine='newmm')
    stop_words = thai_stopwords()
    filtered_tokens = [word for word in tokens if word not in stop_words and not word.isspace()]
    return filtered_tokens

def get_thai2vec_model(force_refresh=False):
    global _thai2vec_model
    if force_refresh or _thai2vec_model is None:
        try:
            _thai2vec_model = WordVector().get_model()
            logger.info("Successfully loaded KeyedVectors model using pythainlp.WordVector.")
        except Exception as e:
            logger.error(f"Error loading model from pythainlp: {e}")
            _thai2vec_model = None
    return _thai2vec_model

def _create_item_profiles(places_df, users_df, all_interactions):
    if places_df.empty:
        return pd.DataFrame(), [], 0

    all_gender_choices = [choice[0] for choice in CustomUser.GENDER_CHOICES]
    all_gender_dummies = pd.get_dummies(pd.DataFrame({'gender': all_gender_choices})['gender'], prefix='gender')
    gender_cols = list(all_gender_dummies.columns)

    interactions_with_users = all_interactions.merge(users_df, left_on='user_id', right_index=True)
    place_mean_age = interactions_with_users.groupby('place_id')['age'].mean().rename('mean_age')
    gender_dummies = pd.get_dummies(interactions_with_users['gender'], prefix='gender').reindex(columns=gender_cols, fill_value=0)
    interactions_with_gender = pd.concat([interactions_with_users[['place_id']], gender_dummies], axis=1)
    place_gender_dist = interactions_with_gender.groupby('place_id').mean()

    places_df = places_df.merge(place_mean_age, left_index=True, right_index=True, how='left')
    places_df = places_df.merge(place_gender_dist, left_index=True, right_index=True, how='left')
    places_df['mean_age'] = places_df['mean_age'].fillna(users_df['age'].mean())
    for col in gender_cols:
        places_df[col] = places_df[col].fillna(users_df['gender'].value_counts(normalize=True).get(col.replace('gender_',''), 0))

    thai2vec_model = get_thai2vec_model()
    if not thai2vec_model:
        raise RuntimeError("Thai2Vec model not available.")

    def get_doc_vector(text):
        tokens = preprocess_thai_text(text)
        vectors = [thai2vec_model[word] for word in tokens if word in thai2vec_model]
        return np.mean(vectors, axis=0) if vectors else np.zeros(thai2vec_model.vector_size)
    desc_vectors = np.vstack(places_df['description'].apply(get_doc_vector).values)

    encoder = OneHotEncoder(handle_unknown='ignore')
    categorical_features = encoder.fit_transform(places_df[['category', 'location', 'price_range']])
    demographic_features = places_df[['mean_age'] + gender_cols].values

    item_profiles_combined = np.hstack([
        desc_vectors,
        categorical_features.toarray(),
        places_df[['average_rating']].fillna(0).values,
        demographic_features
    ])

    return pd.DataFrame(item_profiles_combined, index=places_df.index), gender_cols, categorical_features.shape[1]

def _create_weighted_user_profile(user_id, user_item_matrix, unscaled_item_profiles):
    if user_id in user_item_matrix.index:
        user_ratings = user_item_matrix.loc[user_id]
        user_rated_items_indices = user_ratings[user_ratings > 0].index
        
        if not user_rated_items_indices.empty:
            weights = user_ratings[user_rated_items_indices].values
            rated_item_profiles = unscaled_item_profiles.loc[user_rated_items_indices].values
            sum_of_weights = np.sum(weights)
            
            if sum_of_weights > 0:
                return np.dot(weights, rated_item_profiles) / sum_of_weights
            else:
                return rated_item_profiles.mean(axis=0)

    logger.info(f"Using average item profile for user {user_id} due to insufficient interactions.")
    return unscaled_item_profiles.mean(axis=0)

def _calculate_content_similarity(user_profile, item_profiles):
    scaler = StandardScaler()
    scaled_item_profiles = scaler.fit_transform(item_profiles.values)
    scaled_user_profile = scaler.transform(user_profile.reshape(1, -1))
    similarity_scores = cosine_similarity(scaled_user_profile, scaled_item_profiles)
    return pd.DataFrame(similarity_scores.T, index=item_profiles.index, columns=['similarity'])

def _rebuild_scaled_item_profiles():
    logger.info("Starting scaled item profiles computation.")
    cleaned_data = data_utils.load_and_clean_all_data(force_refresh=True)
    places_df = cleaned_data['places_df']
    if places_df.empty: return pd.DataFrame()
    users_df = cleaned_data['users_df']
    all_interactions = data_utils.get_all_scored_interactions(cleaned_data)
    unscaled_profiles, _, _ = _create_item_profiles(places_df, users_df, all_interactions)
    if unscaled_profiles.empty: return pd.DataFrame()
    scaler = StandardScaler()
    scaled_profiles_values = scaler.fit_transform(unscaled_profiles.values)
    return pd.DataFrame(scaled_profiles_values, index=unscaled_profiles.index)

def rebuild_scaled_item_profiles_cache():
    try:
        scaled_profiles_df = _rebuild_scaled_item_profiles()
        if not scaled_profiles_df.empty:
            cache_config = settings.RECOMMENDATION_SETTINGS.get('CACHING', {})
            timeout = cache_config.get('GLOBAL_CACHE_TIMEOUT', 3600 * 2)
            cache.set(cache_keys.SCALED_PROFILES_KEY, scaled_profiles_df, timeout=timeout)
            logger.info("Successfully rebuilt and cached scaled item profiles.")
        return scaled_profiles_df
    except Exception as e:
        logger.error(f"Error rebuilding scaled item profiles cache: {e}")
        return pd.DataFrame()

def get_scaled_item_profiles(force_refresh=False):
    if not force_refresh:
        cached_value = cache.get(cache_keys.SCALED_PROFILES_KEY)
        if cached_value is not None: return cached_value
    lock_key = f"item_profiles_lock:{cache_keys.SCALED_PROFILES_KEY}"
    if cache.add(lock_key, 'building', timeout=600):
        try:
            return rebuild_scaled_item_profiles_cache()
        finally:
            cache.delete(lock_key)
    else:
        time.sleep(5)
        return get_scaled_item_profiles(force_refresh=False)

def get_content_based_recommendations(user_id, collab_data, num_recommendations=10, filter_interacted=True):
    logger.info(f"CBF: Starting content-based recommendations for user {user_id}")
    try:
        if not collab_data:
            logger.warning(f"CBF: Exiting for user {user_id} because collab_data is empty.")
            return []
        
        user_item_matrix = collab_data.get('user_item_matrix')
        logger.info(f"CBF: Loading cleaned data for user {user_id}...")
        cleaned_data = data_utils.load_and_clean_all_data()
        users_df = cleaned_data['users_df']
        places_df = cleaned_data['places_df']

        if user_item_matrix is None:
            logger.warning(f"CBF: Exiting for user {user_id} because user_item_matrix is None.")
            return []
        if places_df.empty:
            logger.warning(f"CBF: Exiting for user {user_id} because places_df is empty.")
            return []
        if users_df.empty:
            logger.warning(f"CBF: Exiting for user {user_id} because users_df is empty.")
            return []

        logger.info(f"CBF: Creating item profiles for user {user_id}...")
        unscaled_item_profiles, _, _ = _create_item_profiles(places_df, users_df, collab_data.get('all_interactions'))

        if unscaled_item_profiles.empty:
            logger.warning(f"CBF: Exiting for user {user_id} because unscaled_item_profiles is empty.")
            return []
        
        if user_id not in users_df.index: 
            logger.warning(f"CBF: Exiting because user {user_id} not in users_df.")
            return []

        logger.info(f"CBF: Creating weighted user profile for user {user_id}.")
        user_profile = _create_weighted_user_profile(user_id, user_item_matrix, unscaled_item_profiles)
        
        logger.info(f"CBF: Calculating similarity for user {user_id}.")
        similarity_df = _calculate_content_similarity(user_profile, unscaled_item_profiles)
        
        recommendations_df = similarity_df.sort_values(by='similarity', ascending=False)
        if filter_interacted:
            interacted = cache_management.get_user_interacted_places(user_id)
            recommendations_df = recommendations_df.drop(index=recommendations_df.index.intersection(interacted), errors='ignore')

        logger.info(f"CBF: Successfully generated recommendations for user {user_id}.")
        return recommendations_df.head(num_recommendations).index.tolist()
    except Exception as e:
        logger.error(f"Error in content-based recommendations for user {user_id}: {e}", exc_info=True)
        return []

def get_similar_places(place_id, num_recommendations=5, force_refresh=False):
    cache_config = settings.RECOMMENDATION_SETTINGS.get('CACHING', {})
    cache_key = cache_keys.place_similar_key(place_id)
    if not force_refresh:
        cached = cache.get(cache_key)
        if cached is not None: return cached
    item_profiles = get_scaled_item_profiles(force_refresh=force_refresh)
    if item_profiles.empty or place_id not in item_profiles.index: return []
    target_vector = item_profiles.loc[[place_id]]
    sim_scores = cosine_similarity(target_vector, item_profiles)
    sim_df = pd.DataFrame(sim_scores.T, index=item_profiles.index, columns=['similarity'])
    recs = sim_df.drop(place_id).sort_values(by='similarity', ascending=False).head(num_recommendations).index.tolist()
    timeout = cache_config.get('SIMILAR_PLACES_TIMEOUT', 3600 * 2)
    cache.set(cache_key, recs, timeout=timeout)
    return recs
