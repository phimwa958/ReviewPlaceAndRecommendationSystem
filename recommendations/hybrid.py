import logging
from django.conf import settings

from review_place.models import Review, PlaceLike, UserActivity
from recommendations import user_based, content_based, popularity_based

logger = logging.getLogger(__name__)

def get_dynamic_weights(user_id):
    """
    Determines the weights for each recommendation model based on the user's
    interaction history.
    """
    rec_settings = settings.RECOMMENDATION_SETTINGS
    WEIGHT_CONFIG = rec_settings['WEIGHT_CONFIG']

    try:
        num_reviews = Review.objects.filter(user_id=user_id).count()
        num_likes = PlaceLike.objects.filter(user_id=user_id).count()
        num_visits = UserActivity.objects.filter(user_id=user_id, activity_type='view', content_type__model='place').count()

        total_interactions = num_reviews + num_likes + num_visits

        if total_interactions < WEIGHT_CONFIG["low_threshold"]:
            return WEIGHT_CONFIG["low_weight"]
        elif total_interactions < WEIGHT_CONFIG["medium_threshold"]:
            return WEIGHT_CONFIG["medium_weight"]
        else:
            return WEIGHT_CONFIG["high_weight"]

    except Exception as e:
        logger.error(f"Could not determine dynamic weights for user {user_id}: {e}")
        # Fallback to medium weights
        return WEIGHT_CONFIG.get("medium_weight", (0.4, 0.5, 0.1))

def compute_hybrid_scores(user_id, collab_data):
    """
    The core computation logic for generating hybrid recommendation scores.
    This is called by the batch layer.
    """
    rec_settings = settings.RECOMMENDATION_SETTINGS
    DECAY_ALPHA = rec_settings['DECAY_ALPHA']

    # 1. Get dynamic weights based on user activity
    base_weights = list(get_dynamic_weights(user_id))

    # 2. Get recommendations from all models
    user_based_recs = user_based.get_user_based_recommendations(user_id, collab_data, 50, filter_interacted=False)
    content_based_recs = content_based.get_content_based_recommendations(user_id, collab_data, 50, filter_interacted=False)
    popularity_recs = popularity_based.get_popularity_based_recommendations(num_recommendations=50)

    recs_lists = [user_based_recs, content_based_recs, popularity_recs]

    # 3. Adjust weights if some models return no results
    valid_indices = [i for i, recs in enumerate(recs_lists) if recs]

    if not valid_indices:
        logger.warning(f"No recommendations could be generated for user {user_id} from any model.")
        return {}

    adjusted_weights = [0.0] * len(base_weights)
    total_weight_of_valid_models = sum(base_weights[i] for i in valid_indices)

    if total_weight_of_valid_models > 0:
        for i in valid_indices:
            adjusted_weights[i] = base_weights[i] / total_weight_of_valid_models
    else: # Edge case: if all valid models had a weight of 0, distribute weight equally
        for i in valid_indices:
            adjusted_weights[i] = 1.0 / len(valid_indices)

    user_based_weight, content_based_weight, popularity_weight = adjusted_weights

    # 4. Calculate decayed scores for each model's recommendations
    def get_decayed_scores(recs):
        return {place_id: DECAY_ALPHA ** i for i, place_id in enumerate(recs)}

    ub_scores = get_decayed_scores(user_based_recs)
    cb_scores = get_decayed_scores(content_based_recs)
    pop_scores = get_decayed_scores(popularity_recs)

    # 5. Normalize scores within each model
    def normalize_scores(scores):
        total_score = sum(scores.values())
        return {k: v / total_score for k, v in scores.items()} if total_score > 0 else {}

    ub_scores = normalize_scores(ub_scores)
    cb_scores = normalize_scores(cb_scores)
    pop_scores = normalize_scores(pop_scores)

    # 6. Combine scores using adjusted weights
    hybrid_scores = {}
    all_recs = set(ub_scores.keys()) | set(cb_scores.keys()) | set(pop_scores.keys())

    for place_id in all_recs:
        hybrid_scores[place_id] = (user_based_weight * ub_scores.get(place_id, 0)) + \
                                  (content_based_weight * cb_scores.get(place_id, 0)) + \
                                  (popularity_weight * pop_scores.get(place_id, 0))

    return hybrid_scores
