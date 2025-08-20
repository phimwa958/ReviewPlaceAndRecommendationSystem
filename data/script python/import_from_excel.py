import os
import sys
import django
import pandas as pd
from datetime import date, timedelta, datetime as dt_datetime
from django.utils import timezone
from faker import Faker
import random
import logging
from collections import defaultdict

# --- Django Setup ---
print("Setting up Django environment...")
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(project_root)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'review.settings')

try:
    django.setup()
    print("Django setup completed successfully.")
except Exception as e:
    print(f"Error initializing Django: {e}")
    sys.exit(1)

# --- Model Imports ---
print("Importing Django models...")
from review_place.models import CustomUser, Place, Review, PlaceLike, UserActivity
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils.timezone import make_aware
from django.db.models.signals import post_save
from recommendations.signals import trigger_place_related_rebuild, trigger_user_profile_rebuild

# --- Configuration ---
print("Configuring data paths...")
BASE_DATA_PATH = os.path.join(project_root, 'data', 'data_traind')
USER_FILE = os.path.join(BASE_DATA_PATH, 'user.xlsx')
PLACES_FILE = os.path.join(BASE_DATA_PATH, 'places.xlsx')
REVIEWS_FILE = os.path.join(BASE_DATA_PATH, 'reviews.xlsx')
LIKES_FILE = os.path.join(BASE_DATA_PATH, 'place_likes.xlsx')
VISITS_FILE = os.path.join(BASE_DATA_PATH, 'visit_place.xlsx')
SHARES_FILE = os.path.join(BASE_DATA_PATH, 'place_shares.xlsx')

print(f"Data files will be loaded from: {BASE_DATA_PATH}")
fake = Faker('th_TH')
OVERALL_END_DATE = make_aware(dt_datetime(2025, 8, 20))
print(f"Overall end date for data generation set to: {OVERALL_END_DATE}")

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Helper Functions ---
def generate_random_time(start_date, end_date):
    if start_date >= end_date:
        return start_date

    # Calculate the total time difference in seconds
    delta_seconds = int((end_date - start_date).total_seconds())

    # Pick a random number of seconds in that range
    random_offset = random.randint(0, delta_seconds)

    # Add the random offset to the start date
    return start_date + timedelta(seconds=random_offset)

# --- Import Functions ---

@transaction.atomic
def import_users():
    print("\n" + "="*50)
    print("Starting USER import process...")
    logging.info("Starting user import...")
    
    if not os.path.exists(USER_FILE):
        print(f"❌ Error: User file not found at {USER_FILE}")
        logging.error(f"User file not found at {USER_FILE}")
        return
    
    print(f"Loading user data from {USER_FILE}...")
    df = pd.read_excel(USER_FILE)
    print(f"Found {len(df)} user records in the file.")
    
    end_date = OVERALL_END_DATE - timedelta(days=300) # 10 months ago
    start_date = OVERALL_END_DATE - timedelta(days=365) # 1 year ago
    print(f"User join dates will be between {start_date} and {end_date}")
    
    if 'larsname' in df.columns:
        df.rename(columns={'larsname': 'last_name'}, inplace=True)
        print("Renamed 'larsname' column to 'last_name'")

    total_created = 0
    total_skipped = 0
    
    for i, row in enumerate(df.iterrows(), 1):
        _, row = row
        user_id = row.get('id')
        username = row.get('username')
        
        if not username or pd.isna(username):
            username = fake.user_name()
            print(f"Generated username '{username}' for user ID {user_id}")
        
        if CustomUser.objects.filter(id=user_id).exists() or CustomUser.objects.filter(username=username).exists():
            total_skipped += 1
            if i % 100 == 0:
                print(f"Processed {i} users... (skipped {total_skipped} existing users)")
            continue
        
        date_joined = generate_random_time(start_date, end_date)
        email = f"{username}@{fake.free_email_domain()}"
        
        today = date.today()
        random_age = random.randint(18, 65)
        birth_year = today.year - random_age
        # Ensure the birth date is valid by handling leap years
        try:
            birth_date = date(birth_year, random.randint(1, 12), random.randint(1, 28))
        except ValueError:
            birth_date = date(birth_year, 1, 1) # Fallback for safety

        user = CustomUser(
            id=user_id,
            username=username,
            first_name=row.get('firstname', fake.first_name()),
            last_name=row.get('last_name', fake.last_name()),
            email=email,
            mobile_phone=f"0{random.randint(6, 9)}{''.join([str(random.randint(0, 9)) for _ in range(8)])}",
            gender='other',
            date_of_birth=birth_date,
            is_staff=False,
            is_superuser=False,
            date_joined=date_joined,
        )
        user.set_password("password123")
        user.save()
        total_created += 1
        
        if i % 100 == 0:
            print(f"Processed {i} users... (created {total_created} new users)")
    
    print(f"✅ User import completed. Total: {len(df)} records")
    print(f"  - New users created: {total_created}")
    print(f"  - Existing users skipped: {total_skipped}")
    logging.info(f"User import finished. Created {total_created} new users.")

@transaction.atomic
def import_places():
    print("\n" + "="*50)
    print("Starting PLACE import process...")
    logging.info("Starting place import...")
    
    if not os.path.exists(PLACES_FILE):
        print(f"❌ Error: Places file not found at {PLACES_FILE}")
        logging.error(f"Places file not found at {PLACES_FILE}")
        return
    
    print(f"Loading place data from {PLACES_FILE}...")
    df = pd.read_excel(PLACES_FILE)
    print(f"Found {len(df)} place records in the file.")
    
    all_users = list(CustomUser.objects.all())
    if not all_users:
        print("❌ Error: Cannot import places - no users found in database!")
        logging.error("Cannot import places: No users found.")
        return
    
    print(f"Found {len(all_users)} potential owners in database.")
    place_creation_end_date = OVERALL_END_DATE - timedelta(days=180) # 6 months ago
    place_creation_start_date_rule = OVERALL_END_DATE - timedelta(days=270) # 9 months ago
    
    places_to_create = []
    existing_place_ids = set(Place.objects.values_list('id', flat=True))
    print(f"Found {len(existing_place_ids)} existing places in database.")

    for i, row in enumerate(df.iterrows(), 1):
        _, row = row
        place_id = row.get('id')
        
        if pd.isna(place_id):
            print(f"⚠️ Skipping row {i} - missing place ID. Data: {row.to_dict()}")
            continue
            
        if place_id in existing_place_ids:
            if i % 100 == 0:
                print(f"Processed {i} places... (skipping existing place ID {place_id})")
            continue
        
        owner = random.choice(all_users)
        actual_start_date = max(owner.date_joined, place_creation_start_date_rule)
        
        if actual_start_date >= place_creation_end_date:
            print(f"Skipping place {place_id} - creation date out of range")
            continue
            
        created_at = generate_random_time(actual_start_date, place_creation_end_date)
        
        places_to_create.append(
            Place(
                id=int(place_id),
                owner=owner,
                place_name=row.get('place_name'),
                description=row.get('description', ''),
                category='attraction',
                location=row.get('location', 'ไม่ระบุ'),
                created_at=created_at
            )
        )
        existing_place_ids.add(place_id)
        
        if i % 100 == 0:
            print(f"Processed {i} places... (prepared {len(places_to_create)} for creation)")

    if places_to_create:
        print(f"Creating {len(places_to_create)} new places in bulk...")

        # Temporarily disable auto_now_add to allow setting historical creation dates
        created_at_field = Place._meta.get_field('created_at')
        original_auto_now_add = created_at_field.auto_now_add
        created_at_field.auto_now_add = False

        try:
            Place.objects.bulk_create(places_to_create, batch_size=2000)
        finally:
            # Restore the original model state
            created_at_field.auto_now_add = original_auto_now_add

        print("Bulk creation completed.")
    
    print(f"✅ Place import completed. Total: {len(df)} records")
    print(f"  - New places created: {len(places_to_create)}")
    print(f"  - Existing places skipped: {len(df) - len(places_to_create)}")
    logging.info(f"Place import finished. Created {len(places_to_create)} new places.")

@transaction.atomic
def import_reviews():
    print("\n" + "="*50)
    print("Starting REVIEW import process...")
    logging.info("Starting review import (optimized)...")
    
    if not os.path.exists(REVIEWS_FILE):
        print(f"❌ Error: Reviews file not found at {REVIEWS_FILE}")
        logging.error(f"Reviews file not found at {REVIEWS_FILE}")
        return
    
    print(f"Loading review data from {REVIEWS_FILE}...")
    df = pd.read_excel(REVIEWS_FILE)
    print(f"Found {len(df)} review records in the file.")
    
    print("Cleaning and preparing review data...")
    df.dropna(subset=['id', 'user_id', 'place_id'], inplace=True)
    df = df.astype({'id': 'int', 'user_id': 'int', 'place_id': 'int'})
    print(f"After cleaning: {len(df)} valid reviews remaining.")

    print("Loading users and places from database...")
    users = {user.id: user for user in CustomUser.objects.all()}
    places = {place.id: place for place in Place.objects.all()}
    existing_review_ids = set(Review.objects.values_list('id', flat=True))
    
    print(f"Found {len(users)} users and {len(places)} places in database.")
    print(f"Found {len(existing_review_ids)} existing reviews in database.")

    activity_start_date_rule = OVERALL_END_DATE - timedelta(days=180)  # 6 months ago
    reviews_to_create = []
    skipped = 0
    
    for i, row in enumerate(df.iterrows(), 1):
        _, row = row
        review_id, user_id, place_id = row['id'], row['user_id'], row['place_id']
        
        if user_id not in users:
            skipped += 1
            continue
        if place_id not in places:
            skipped += 1
            continue
        if review_id in existing_review_ids:
            skipped += 1
            continue
            
        user, place = users[user_id], places[place_id]
        start_date = max(user.date_joined, place.created_at, activity_start_date_rule)
        
        if start_date >= OVERALL_END_DATE:
            skipped += 1
            continue
            
        review_date = generate_random_time(start_date, OVERALL_END_DATE)
        reviews_to_create.append(
            Review(
                id=review_id, 
                user=user, 
                place=place, 
                rating=row['rating'], 
                review_text=row.get('review_text', ''),
                review_date=review_date
            )
        )
        existing_review_ids.add(review_id)
        
        if i % 100 == 0:
            print(f"Processed {i} reviews... (prepared {len(reviews_to_create)} for creation, skipped {skipped})")

    if reviews_to_create:
        print(f"Creating {len(reviews_to_create)} new reviews in bulk...")

        # Temporarily disable auto_now_add to allow setting historical review dates
        review_date_field = Review._meta.get_field('review_date')
        original_auto_now_add = review_date_field.auto_now_add
        review_date_field.auto_now_add = False

        try:
            Review.objects.bulk_create(reviews_to_create, batch_size=2000)
        finally:
            # Restore the original model state
            review_date_field.auto_now_add = original_auto_now_add

        print("Bulk creation completed.")
    
    print(f"✅ Review import completed. Total: {len(df)} records")
    print(f"  - New reviews created: {len(reviews_to_create)}")
    print(f"  - Reviews skipped: {skipped}")
    logging.info(f"Review import finished. Created {len(reviews_to_create)} reviews.")

@transaction.atomic
def import_place_likes():
    print("\n" + "="*50)
    print("Starting PLACE LIKES import process...")
    logging.info("Starting place like import (optimized)...")
    
    if not os.path.exists(LIKES_FILE):
        print(f"⚠️ Place likes file not found at {LIKES_FILE} - skipping")
        return
    
    print(f"Loading place likes data from {LIKES_FILE}...")
    df = pd.read_excel(LIKES_FILE)
    print(f"Found {len(df)} like records in the file.")
    
    print("Getting Place content type...")
    place_content_type = ContentType.objects.get(app_label='review_place', model='place')
    
    print("Loading users and places from database...")
    users = {user.id: user for user in CustomUser.objects.all()}
    places = {place.id: place for place in Place.objects.all()}
    existing_likes = set(PlaceLike.objects.values_list('user_id', 'place_id'))
    
    print(f"Found {len(users)} users and {len(places)} places in database.")
    print(f"Found {len(existing_likes)} existing likes in database.")

    activity_start_date_rule = OVERALL_END_DATE - timedelta(days=180)  # 6 months ago
    likes_to_create, activities_to_create = [], []
    skipped = 0
    
    for i, row in enumerate(df.iterrows(), 1):
        _, row = row
        user_id, place_id = row.get('user_id'), row.get('place_id')
        
        if pd.isna(user_id) or pd.isna(place_id):
            print(f"⚠️ Skipping interaction row {i} due to missing user_id or place_id. Data: {row.to_dict()}")
            skipped += 1
            continue
        if user_id not in users:
            skipped += 1
            continue
        if place_id not in places:
            skipped += 1
            continue
        if (user_id, place_id) in existing_likes:
            skipped += 1
            continue
            
        user, place = users[user_id], places[place_id]
        start_date = max(user.date_joined, place.created_at, activity_start_date_rule)
        
        if start_date >= OVERALL_END_DATE:
            skipped += 1
            continue
            
        ts = generate_random_time(start_date, OVERALL_END_DATE)
        likes_to_create.append(PlaceLike(user=user, place=place, created_at=ts))
        activities_to_create.append(
            UserActivity(
                user=user, 
                activity_type='click', 
                content_type=place_content_type, 
                object_id=place.id, 
                timestamp=ts
            )
        )
        existing_likes.add((user_id, place_id))
        
        if i % 100 == 0:
            print(f"Processed {i} likes... (prepared {len(likes_to_create)} likes and activities, skipped {skipped})")

    if likes_to_create:
        print(f"Creating {len(likes_to_create)} new likes in bulk...")
        like_created_at_field = PlaceLike._meta.get_field('created_at')
        original_like_auto_now = like_created_at_field.auto_now_add
        like_created_at_field.auto_now_add = False
        try:
            PlaceLike.objects.bulk_create(likes_to_create, batch_size=2000)
        finally:
            like_created_at_field.auto_now_add = original_like_auto_now
        print("Likes bulk creation completed.")
    
    if activities_to_create:
        print(f"Creating {len(activities_to_create)} new activities in bulk...")
        activity_timestamp_field = UserActivity._meta.get_field('timestamp')
        original_activity_auto_now = activity_timestamp_field.auto_now_add
        activity_timestamp_field.auto_now_add = False
        try:
            UserActivity.objects.bulk_create(activities_to_create, batch_size=2000)
        finally:
            activity_timestamp_field.auto_now_add = original_activity_auto_now
        print("Activities bulk creation completed.")
    
    print(f"✅ Place like import completed. Total: {len(df)} records")
    print(f"  - New likes created: {len(likes_to_create)}")
    print(f"  - New activities created: {len(activities_to_create)}")
    print(f"  - Records skipped: {skipped}")
    logging.info(f"Place like import finished. Created {len(likes_to_create)} likes and activities.")

@transaction.atomic
def import_visits():
    print("\n" + "="*50)
    print("Starting VISIT import process...")
    logging.info("Starting visit import (optimized)...")
    
    if not os.path.exists(VISITS_FILE):
        print(f"⚠️ Visits file not found at {VISITS_FILE} - skipping")
        return
    
    print(f"Loading visit data from {VISITS_FILE}...")
    df = pd.read_excel(VISITS_FILE)
    print(f"Found {len(df)} visit records in the file.")
    
    print("Getting Place content type...")
    place_content_type = ContentType.objects.get(app_label='review_place', model='place')
    
    print("Loading users and places from database...")
    users = {user.id: user for user in CustomUser.objects.all()}
    places = {place.id: place for place in Place.objects.all()}
    print(f"Found {len(users)} users and {len(places)} places in database.")

    activity_start_date_rule = OVERALL_END_DATE - timedelta(days=180)  # 6 months ago
    activities_to_create = []
    place_visit_counts = defaultdict(int)
    skipped = 0
    total_visits = 0
    
    for i, row in enumerate(df.iterrows(), 1):
        _, row = row
        user_id, place_id = row.get('user_id'), row.get('place_id')
        num_visits = int(pd.to_numeric(row.get('visit_place'), errors='coerce', downcast='integer') or 1)
        
        if pd.isna(user_id) or pd.isna(place_id):
            print(f"⚠️ Skipping interaction row {i} due to missing user_id or place_id. Data: {row.to_dict()}")
            skipped += 1
            continue
        if user_id not in users:
            skipped += 1
            continue
        if place_id not in places:
            skipped += 1
            continue
            
        user, place = users[user_id], places[place_id]
        start_date = max(user.date_joined, place.created_at, activity_start_date_rule)
        
        if start_date >= OVERALL_END_DATE:
            skipped += 1
            continue
            
        for _ in range(num_visits):
            ts = generate_random_time(start_date, OVERALL_END_DATE)
            activities_to_create.append(
                UserActivity(
                    user=user, 
                    activity_type='view', 
                    content_type=place_content_type, 
                    object_id=place.id, 
                    timestamp=ts
                )
            )
        place_visit_counts[place.id] += num_visits
        total_visits += num_visits
        
        if i % 100 == 0:
            print(f"Processed {i} visit records... (prepared {total_visits} visit activities, skipped {skipped} records)")

    if activities_to_create:
        print(f"Creating {len(activities_to_create)} visit activities in bulk...")
        activity_timestamp_field = UserActivity._meta.get_field('timestamp')
        original_activity_auto_now = activity_timestamp_field.auto_now_add
        activity_timestamp_field.auto_now_add = False
        try:
            UserActivity.objects.bulk_create(activities_to_create, batch_size=2000)
        finally:
            activity_timestamp_field.auto_now_add = original_activity_auto_now
        print("Activities bulk creation completed.")
    
    print(f"Updating visit counts for {len(place_visit_counts)} places...")
    places_to_update = Place.objects.filter(id__in=place_visit_counts.keys())
    for place in places_to_update:
        place.visit_count += place_visit_counts[place.id]
    
    if places_to_update:
        Place.objects.bulk_update(places_to_update, ['visit_count'], batch_size=2000)
        print("Visit counts updated.")
    
    print(f"✅ Visit import completed. Total: {len(df)} records")
    print(f"  - New visit activities created: {len(activities_to_create)}")
    print(f"  - Total visits processed: {total_visits}")
    print(f"  - Records skipped: {skipped}")
    logging.info("Visit import finished.")

@transaction.atomic
def import_place_shares():
    print("\n" + "="*50)
    print("Starting PLACE SHARES import process...")
    logging.info("Starting place share import (optimized)...")
    
    if not os.path.exists(SHARES_FILE):
        print(f"⚠️ Shares file not found at {SHARES_FILE} - skipping")
        return
    
    print(f"Loading share data from {SHARES_FILE}...")
    df = pd.read_excel(SHARES_FILE)
    print(f"Found {len(df)} share records in the file.")
    
    print("Getting Place content type...")
    place_content_type = ContentType.objects.get(app_label='review_place', model='place')
    
    print("Loading users and places from database...")
    users = {user.id: user for user in CustomUser.objects.all()}
    places = {place.id: place for place in Place.objects.all()}
    # The new place_shares_gen.py ensures uniqueness, so we can simplify the check here
    # or trust the source file is clean. For this script, we'll trust the generator.
    print(f"Found {len(users)} users and {len(places)} places in database.")

    activity_start_date_rule = OVERALL_END_DATE - timedelta(days=180)  # 6 months ago
    activities_to_create = []
    skipped = 0
    
    for i, row in enumerate(df.iterrows(), 1):
        _, row = row
        user_id = row.get('user_id')
        place_id = row.get('place_id')
        shared_to = row.get('shared_to') # Read the new channel column
        
        if pd.isna(user_id) or pd.isna(place_id):
            print(f"⚠️ Skipping interaction row {i} due to missing user_id or place_id. Data: {row.to_dict()}")
            skipped += 1
            continue
        if user_id not in users:
            skipped += 1
            continue
        if place_id not in places:
            skipped += 1
            continue
            
        user, place = users[user_id], places[place_id]
        start_date = max(user.date_joined, place.created_at, activity_start_date_rule)
        
        if start_date >= OVERALL_END_DATE:
            skipped += 1
            continue
            
        ts = generate_random_time(start_date, OVERALL_END_DATE)
        activities_to_create.append(
            UserActivity(
                user=user, 
                activity_type='share', 
                content_type=place_content_type, 
                object_id=place.id, 
                timestamp=ts,
                details={'shared_to': shared_to} # Add channel to details
            )
        )
        
        if i % 100 == 0:
            print(f"Processed {i} share records... (prepared {len(activities_to_create)} new shares, skipped {skipped})")

    if activities_to_create:
        print(f"Creating {len(activities_to_create)} new share activities in bulk...")
        activity_timestamp_field = UserActivity._meta.get_field('timestamp')
        original_activity_auto_now = activity_timestamp_field.auto_now_add
        activity_timestamp_field.auto_now_add = False
        try:
            UserActivity.objects.bulk_create(activities_to_create, batch_size=2000)
        finally:
            activity_timestamp_field.auto_now_add = original_activity_auto_now
        print("Activities bulk creation completed.")
    
    print(f"✅ Share import completed. Total: {len(df)} records")
    print(f"  - New shares created: {len(activities_to_create)}")
    print(f"  - Records skipped: {skipped}")
    logging.info("Place share import finished.")

def recalculate_all_ratings():
    print("\n" + "="*50)
    print("Starting RATING RECALCULATION process...")
    logging.info("Starting recalculation of all place ratings...")
    
    places = Place.objects.all()
    print(f"Found {len(places)} places to recalculate ratings for.")
    
    for i, place in enumerate(places, 1):
        place.update_average_rating()
        if i % 100 == 0:
            print(f"Recalculated ratings for {i} places...")
    
    print(f"✅ Rating recalculation completed for {len(places)} places.")
    logging.info(f"Finished recalculating ratings for {len(places)} places.")

# --- Main Execution ---
if __name__ == "__main__":
    print("\n" + "="*50)
    print("=== STARTING DATA IMPORT SCRIPT ===")
    print("="*50 + "\n")

    print("Disconnecting signals to prevent loops during import...")
    post_save.disconnect(trigger_place_related_rebuild, sender=Place)
    post_save.disconnect(trigger_user_profile_rebuild, sender=CustomUser)
    
    import_users()
    import_places()
    import_reviews()
    import_place_likes()
    import_visits()
    import_place_shares()
    recalculate_all_ratings()
    
    print("\nReconnecting signals...")
    post_save.connect(trigger_place_related_rebuild, sender=Place)
    post_save.connect(trigger_user_profile_rebuild, sender=CustomUser)

    print("\n" + "="*50)
    print("=== DATA IMPORT SCRIPT COMPLETED ===")
    print("="*50 + "\n")
    logging.info("--- Data Import Script Finished ---")