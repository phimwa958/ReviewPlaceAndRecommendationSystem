from django.core.management.base import BaseCommand
from recommendations.evaluation import evaluate_recommendation_system
from django.conf import settings
from recommendations.engine import recommendation_engine
from review_place.models import CustomUser, Place, Review, PlaceLike, UserActivity
import pandas as pd
import logging
import numpy as np
from recommendations import user_based # Import the user_based module

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Evaluates the hybrid recommendation system.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting recommendation system evaluation...'))

        try:
            # Force rebuild of global caches to ensure settings changes are reflected
            self.stdout.write(self.style.NOTICE('Rebuilding global recommendation caches...'))
            # This now returns the data, so we can use it directly
            collab_data = recommendation_engine.rebuild_user_similarity_cache() 
            recommendation_engine.rebuild_scaled_item_profiles_cache()

            # Load and clean all data using the engine, forcing a refresh
            self.stdout.write(self.style.NOTICE('Loading and cleaning all data with force_refresh=True...'))
            cleaned_data = recommendation_engine.load_and_clean_all_data(force_refresh=True)
            users_df = cleaned_data['users_df']
            places_df = cleaned_data['places_df']

            # --- Prepare Ground Truth using the new scoring logic from the engine ---
            all_interactions = recommendation_engine._get_all_scored_interactions(cleaned_data)

            user_place_scores = all_interactions.groupby(['user_id', 'place_id'])['score'].sum().reset_index()
            
            like_weight = settings.RECOMMENDATION_SETTINGS['LIKE_WEIGHT']
            positive_interactions = user_place_scores[user_place_scores['score'] >= like_weight]
            
            ground_truth_dict = {
                user_id: set(group['place_id'].tolist())
                for user_id, group in positive_interactions.groupby('user_id')
            }

            # --- Filter Users for Meaningful Evaluation ---
            self.stdout.write(self.style.NOTICE('Filtering users for meaningful evaluation...'))
            user_item_matrix = collab_data.get('user_item_matrix')

            if user_item_matrix is None or user_item_matrix.empty:
                self.stdout.write(self.style.ERROR("User-item matrix is empty. Cannot perform evaluation."))
                return

            valid_user_ids = set(user_item_matrix.index)
            original_user_count = len(ground_truth_dict)
            
            # Filter the ground truth dictionary
            ground_truth_dict = {uid: places for uid, places in ground_truth_dict.items() if uid in valid_user_ids}
            
            filtered_user_count = len(ground_truth_dict)
            self.stdout.write(self.style.SUCCESS(
                f"Filtered evaluation users: {original_user_count} -> {filtered_user_count} "
                f"(Users with enough interactions for hybrid models)."
            ))

            if not ground_truth_dict:
                self.stdout.write(self.style.ERROR("No users with sufficient data to evaluate. Aborting."))
                return

            # --- Prepare Item Profiles for Diversity Calculation ---
            self.stdout.write(self.style.NOTICE('Generating item profiles for diversity calculation...'))
            item_profiles_for_eval, _, _ = recommendation_engine._create_item_profiles(places_df, users_df, all_interactions)
            
            if item_profiles_for_eval.empty:
                self.stdout.write(self.style.WARNING("Could not generate item profiles. Diversity will be 0."))
            else:
                self.stdout.write(self.style.SUCCESS("Successfully generated item profiles."))

            all_catalog_items = set(places_df.index.tolist())

            # --- Generate Recommendations ---
            self.stdout.write(self.style.NOTICE('Generating recommendations for users with ground truth...'))
            recommendations_dict = {}
            user_ids_to_evaluate = list(ground_truth_dict.keys())

            for user_id in user_ids_to_evaluate:
                recs = recommendation_engine.get_hybrid_recommendations(
                    user_id,
                    collab_data, # Pass collab_data here
                    num_recommendations=10,
                    filter_interacted=False,
                    force_refresh=True 
                )
                if recs:
                    recommendations_dict[user_id] = recs
            
            self.stdout.write(self.style.SUCCESS(f"Generated recommendations for {len(recommendations_dict)} users."))

            # --- Perform Evaluation ---
            self.stdout.write(self.style.NOTICE('Performing evaluation...'))
            results = evaluate_recommendation_system(
                recommendations_dict,
                ground_truth_dict,
                item_profiles_for_eval,
                all_catalog_items,
                k=10
            )

            self.stdout.write(self.style.SUCCESS('\nRecommendation System Evaluation Results (k=10):'))
            for metric, value in results.items():
                self.stdout.write(f'{metric.replace("_", " ").title()}: {value:.4f}')

        except Exception as e:
            logger.error(f"Error during evaluation: {e}", exc_info=True)
            self.stdout.write(self.style.ERROR(f'An error occurred during evaluation: {e}'))
