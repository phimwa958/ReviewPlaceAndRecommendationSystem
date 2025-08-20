from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from review_place.models import Review, PlaceLike, Place, CustomUser, UserActivity
from django.conf import settings
from recommendations.tasks import (
    invalidate_similar_places_task,
    process_realtime_interaction,
    schedule_global_rebuild_if_needed
)

# --- Review Signal Handlers ---

@receiver(post_save, sender=Review)
def handle_review_save(sender, instance, created, **kwargs):
    """
    Handles created or updated reviews by sending the latest score
    to the Speed Layer. This provides an immediate boost based on the new rating.
    """
    user = instance.user
    place = instance.place
    score = instance.rating / settings.RECOMMENDATION_SETTINGS.get('REVIEW_MAX', 5.0)

    if user and place and score > 0:
        # On update, this sends the new score, effectively boosting the item.
        # On create, it adds the initial score.
        process_realtime_interaction.delay(user.id, place.id, score)

@receiver(post_delete, sender=Review)
def handle_review_delete(sender, instance, **kwargs):
    """
    Handles a deleted review by reversing its score in the Speed Layer.
    """
    user = instance.user
    place = instance.place
    score = instance.rating / settings.RECOMMENDATION_SETTINGS.get('REVIEW_MAX', 5.0)

    if user and place and score > 0:
        process_realtime_interaction.delay(user.id, place.id, -score)


# --- Other Interaction Handlers (Create/Delete only) ---

@receiver(post_save, sender=PlaceLike)
@receiver(post_save, sender=UserActivity)
def handle_interaction_creation(sender, instance, created, **kwargs):
    """
    Handles new interactions (Likes, Visits, Shares) by triggering the Speed Layer.
    Updates are ignored for these models.
    """
    if not created:
        return

    user = instance.user
    place = None
    score = 0.0

    if sender is PlaceLike:
        place = instance.place
        score = settings.RECOMMENDATION_SETTINGS.get('LIKE_WEIGHT', 0.8)
    elif sender is UserActivity and isinstance(instance.content_object, Place):
        place = instance.content_object
        if instance.activity_type == 'view':
            score = settings.RECOMMENDATION_SETTINGS.get('VISIT_WEIGHT', 0.5)
        elif instance.activity_type == 'share':
            score = settings.RECOMMENDATION_SETTINGS.get('SHARE_WEIGHT', 0.4)

    if user and place and score > 0:
        process_realtime_interaction.delay(user.id, place.id, score)


@receiver(post_delete, sender=PlaceLike)
@receiver(post_delete, sender=UserActivity)
def handle_interaction_deletion(sender, instance, **kwargs):
    """
    Handles deleted interactions (Likes, Visits, Shares) by reversing the score.
    """
    user = instance.user
    place = None
    score = 0.0

    if sender is PlaceLike:
        place = instance.place
        score = settings.RECOMMENDATION_SETTINGS.get('LIKE_WEIGHT', 0.8)
    elif sender is UserActivity and isinstance(instance.content_object, Place):
        place = instance.content_object
        if instance.activity_type == 'view':
            score = settings.RECOMMENDATION_SETTINGS.get('VISIT_WEIGHT', 0.5)
        elif instance.activity_type == 'share':
            score = settings.RECOMMENDATION_SETTINGS.get('SHARE_WEIGHT', 0.4)

    if user and place and score > 0:
        process_realtime_interaction.delay(user.id, place.id, -score)


# --- Global Cache Rebuild Triggers ---

@receiver([post_save, post_delete], sender=Place)
def trigger_place_related_rebuild(sender, instance, **kwargs):
    """
    Handles cache updates after a Place is created, updated, or deleted.
    Schedules a global cache rebuild, as a change in place data is significant.
    """
    invalidate_similar_places_task.delay(instance.id)
    schedule_global_rebuild_if_needed.delay()

@receiver([post_save, post_delete], sender=CustomUser)
def trigger_user_profile_rebuild(sender, instance, **kwargs):
    """
    Handles cache updates after a CustomUser is created, updated, or deleted.
    Schedules a global cache rebuild, as a change in user data is significant.
    """
    schedule_global_rebuild_if_needed.delay()
