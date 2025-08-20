import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
import logging

logger = logging.getLogger(__name__)

def precision_at_k(recommended_items, relevant_items, k):
    """
    Calculates Precision@k.
    :param recommended_items: List of recommended item IDs.
    :param relevant_items: Set of relevant item IDs (ground truth).
    :param k: Number of top recommendations to consider.
    :return: Precision@k value.
    """
    if not recommended_items or k == 0:
        return 0.0
    
    recommended_at_k = recommended_items[:k]
    num_relevant_in_k = len(set(recommended_at_k) & relevant_items)
    return num_relevant_in_k / k

def recall_at_k(recommended_items, relevant_items, k):
    """
    Calculates Recall@k.
    :param recommended_items: List of recommended item IDs.
    :param relevant_items: Set of relevant item IDs (ground truth).
    :param k: Number of top recommendations to consider.
    :return: Recall@k value.
    """
    if not relevant_items or k == 0:
        return 0.0
    
    recommended_at_k = recommended_items[:k]
    num_relevant_in_k = len(set(recommended_at_k) & relevant_items)
    return num_relevant_in_k / len(relevant_items)

def f1_score_at_k(recommended_items, relevant_items, k):
    """
    Calculates F1-score@k.
    :param recommended_items: List of recommended item IDs.
    :param relevant_items: Set of relevant item IDs (ground truth).
    :param k: Number of top recommendations to consider.
    :return: F1-score@k value.
    """
    precision = precision_at_k(recommended_items, relevant_items, k)
    recall = recall_at_k(recommended_items, relevant_items, k)
    
    if precision + recall == 0:
        return 0.0
    return 2 * (precision * recall) / (precision + recall)

def average_precision_at_k(recommended_items, relevant_items, k):
    """
    Calculates Average Precision@k (AP@k).
    :param recommended_items: List of recommended item IDs.
    :param relevant_items: Set of relevant item IDs (ground truth).
    :param k: Number of top recommendations to consider.
    :return: AP@k value.
    """
    if not relevant_items or not recommended_items or k == 0:
        return 0.0

    ap = 0.0
    num_hits = 0
    for i, item in enumerate(recommended_items[:k]):
        if item in relevant_items:
            num_hits += 1
            ap += num_hits / (i + 1.0)
    
    return ap / min(len(relevant_items), k) # Normalize by min(num_relevant, k)

def dcg_at_k(recommended_items, relevant_items, k, relevance_scores=None):
    """
    Calculates Discounted Cumulative Gain (DCG@k).
    :param recommended_items: List of recommended item IDs.
    :param relevant_items: Set of relevant item IDs (ground truth).
    :param k: Number of top recommendations to consider.
    :param relevance_scores: Dictionary of {item_id: score} for graded relevance. If None, binary relevance (1 if relevant, 0 otherwise) is used.
    :return: DCG@k value.
    """
    dcg = 0.0
    for i, item in enumerate(recommended_items[:k]):
        if item in relevant_items:
            relevance = relevance_scores.get(item, 1.0) if relevance_scores else 1.0
            dcg += relevance / np.log2(i + 2) # i+1 is rank, so i+2 for log2(rank+1)
    return dcg

def ndcg_at_k(recommended_items, relevant_items, k, relevance_scores=None):
    """
    Calculates Normalized Discounted Cumulative Gain (NDCG@k).
    :param recommended_items: List of recommended item IDs.
    :param relevant_items: Set of relevant item IDs (ground truth).
    :param k: Number of top recommendations to consider.
    :param relevance_scores: Dictionary of {item_id: score} for graded relevance. If None, binary relevance (1 if relevant, 0 otherwise) is used.
    :return: NDCG@k value.
    """
    actual_dcg = dcg_at_k(recommended_items, relevant_items, k, relevance_scores)
    
    # Ideal DCG
    ideal_relevant_items = sorted([item for item in relevant_items], 
                                  key=lambda x: relevance_scores.get(x, 1.0) if relevance_scores else 1.0, 
                                  reverse=True)
    ideal_dcg = dcg_at_k(ideal_relevant_items, relevant_items, k, relevance_scores)
    
    if ideal_dcg == 0:
        return 0.0
    return actual_dcg / ideal_dcg

def hit_rate_at_k(recommended_items, relevant_items, k):
    """
    Calculates Hit Rate@k.
    :param recommended_items: List of recommended item IDs.
    :param relevant_items: Set of relevant item IDs (ground truth).
    :param k: Number of top recommendations to consider.
    :return: 1 if at least one relevant item is in top k, 0 otherwise.
    """
    if not relevant_items or not recommended_items or k == 0:
        return 0.0
    
    recommended_at_k = recommended_items[:k]
    return 1.0 if len(set(recommended_at_k) & relevant_items) > 0 else 0.0

def diversity_at_k(recommended_items, item_profiles_df, k):
    """
    Calculates Diversity@k based on item profiles.
    :param recommended_items: List of recommended item IDs.
    :param item_profiles_df: DataFrame where index is item_id and columns are feature vectors.
    :param k: Number of top recommendations to consider.
    :return: Diversity@k value (1 - average pairwise cosine similarity).
    """
    if len(recommended_items) < 2 or k < 2:
        return 1.0 # Max diversity if less than 2 items to compare

    recommended_profiles = []
    for item_id in recommended_items[:k]:
        if item_id in item_profiles_df.index:
            recommended_profiles.append(item_profiles_df.loc[item_id].values)
    
    if len(recommended_profiles) < 2:
        return 1.0 # Still max diversity if not enough profiles found

    recommended_profiles_matrix = np.array(recommended_profiles)
    
    # Calculate pairwise cosine similarity
    similarity_matrix = cosine_similarity(recommended_profiles_matrix)
    
    # Exclude self-similarity (diagonal) and duplicate pairs
    num_pairs = 0
    total_similarity = 0.0
    for i in range(len(similarity_matrix)):
        for j in range(i + 1, len(similarity_matrix)):
            total_similarity += similarity_matrix[i, j]
            num_pairs += 1
            
    if num_pairs == 0:
        return 1.0 # Should not happen if len(recommended_profiles) >= 2
        
    average_similarity = total_similarity / num_pairs
    return 1.0 - average_similarity

def catalog_coverage(all_recommended_items, all_catalog_items):
    """
    Calculates Catalog Coverage.
    :param all_recommended_items: Set of all unique items ever recommended across all users.
    :param all_catalog_items: Set of all item IDs in the catalog.
    :return: Catalog Coverage value.
    """
    if not all_catalog_items:
        return 0.0
    return len(all_recommended_items) / len(all_catalog_items)

def evaluate_recommendation_system(recommendations_dict, ground_truth_dict, item_profiles_df, all_catalog_items, k=10):
    """
    Evaluates the recommendation system using various metrics.
    :param recommendations_dict: Dictionary of {user_id: [recommended_item_ids]}.
    :param ground_truth_dict: Dictionary of {user_id: set(relevant_item_ids)}.
    :param item_profiles_df: DataFrame of item profiles for diversity calculation.
    :param all_catalog_items: Set of all item IDs in the catalog for coverage calculation.
    :param k: Number of top recommendations to consider for metrics.
    :return: Dictionary of average metric scores.
    """
    metrics = {
        'precision': [], 'recall': [], 'f1_score': [], 'map': [], 
        'ndcg': [], 'hit_rate': [], 'diversity': []
    }
    
    all_recommended_items_overall = set()

    for user_id, recommended_items in recommendations_dict.items():
        relevant_items = ground_truth_dict.get(user_id, set())
        
        # Ensure recommended_items is a list
        if not isinstance(recommended_items, list):
            recommended_items = list(recommended_items)

        metrics['precision'].append(precision_at_k(recommended_items, relevant_items, k))
        metrics['recall'].append(recall_at_k(recommended_items, relevant_items, k))
        metrics['f1_score'].append(f1_score_at_k(recommended_items, relevant_items, k))
        metrics['map'].append(average_precision_at_k(recommended_items, relevant_items, k))
        metrics['ndcg'].append(ndcg_at_k(recommended_items, relevant_items, k)) # Assuming binary relevance for now
        metrics['hit_rate'].append(hit_rate_at_k(recommended_items, relevant_items, k))
        metrics['diversity'].append(diversity_at_k(recommended_items, item_profiles_df, k))
        
        all_recommended_items_overall.update(recommended_items[:k])

    avg_metrics = {metric: np.mean(scores) for metric, scores in metrics.items()}
    avg_metrics['catalog_coverage'] = catalog_coverage(all_recommended_items_overall, all_catalog_items)
    
    return avg_metrics
