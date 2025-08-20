import os
import django
from django.conf import settings
from django.db.models import Count, Q
from collections import defaultdict

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'review.settings')
django.setup()

from review_place.models import CustomUser, Review, PlaceLike, UserActivity, Place
from django.contrib.contenttypes.models import ContentType

def check_user_interaction_counts():
    user_interaction_counts = defaultdict(int)

    # Get counts from Review model
    reviews_count = Review.objects.values('user').annotate(count=Count('id'))
    for item in reviews_count:
        user_interaction_counts[item['user']] += item['count']

    # Get counts from PlaceLike model
    likes_count = PlaceLike.objects.values('user').annotate(count=Count('id'))
    for item in likes_count:
        user_interaction_counts[item['user']] += item['count']

    # Get counts from UserActivity model for 'view' activities on 'Place' objects
    place_content_type = ContentType.objects.get_for_model(Place)
    view_activities_count = UserActivity.objects.filter(
        activity_type='view',
        content_type=place_content_type
    ).values('user').annotate(count=Count('id'))
    for item in view_activities_count:
        user_interaction_counts[item['user']] += item['count']

    # Fetch usernames for user_ids
    user_ids = list(user_interaction_counts.keys())
    users = CustomUser.objects.filter(id__in=user_ids).values('id', 'username')
    user_map = {user['id']: user['username'] for user in users}

    print("User Interaction Counts:")
    low_interaction_users = []
    for user_id, count in sorted(user_interaction_counts.items(), key=lambda item: item[1]):
        username = user_map.get(user_id, f"User {user_id}")
        print(f"  {username} (ID: {user_id}): {count} interactions")
        if count < settings.RECOMMENDATION_SETTINGS['WEIGHT_CONFIG']['low_threshold']:
            low_interaction_users.append((username, user_id, count))

    print(f"\nUsers with less than {settings.RECOMMENDATION_SETTINGS['WEIGHT_CONFIG']['low_threshold']} interactions:")
    if low_interaction_users:
        for username, user_id, count in low_interaction_users:
            print(f"  {username} (ID: {user_id}): {count} interactions")
    else:
        print("  None")

if __name__ == '__main__':
    check_user_interaction_counts()
