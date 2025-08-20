import pandas as pd
import random
import os

# --- Configuration ---
# Get the project root directory
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BASE_DATA_PATH = os.path.join(project_root, 'data', 'data_traind')

# Input files
USER_FILE = os.path.join(BASE_DATA_PATH, 'user.xlsx')
PLACES_FILE = os.path.join(BASE_DATA_PATH, 'places.xlsx')

# Output file
OUTPUT_FILE = os.path.join(BASE_DATA_PATH, 'place_shares.xlsx')

# Share channels
SHARE_CHANNELS = ['facebook', 'twitter', 'linkedin', 'line', 'copy_link']

# Target number of total share records
TARGET_SHARE_RECORDS = 7000

# --- Main Script ---
def generate_shares():
    """
    Generates a realistic set of share activities for places by users across multiple channels.
    """
    print("Starting share generation script...")

    # --- Load existing data ---
    try:
        print(f"Loading users from {USER_FILE}...")
        user_df = pd.read_excel(USER_FILE)
        user_ids = user_df['id'].tolist()
        print(f"Loaded {len(user_ids)} user IDs.")

        print(f"Loading places from {PLACES_FILE}...")
        places_df = pd.read_excel(PLACES_FILE)
        place_ids = places_df['id'].tolist()
        print(f"Loaded {len(place_ids)} place IDs.")
    except FileNotFoundError as e:
        print(f"❌ Error: Input file not found. {e}")
        return

    # --- Generate Share Data ---
    all_shares = []
    # Use a set to track unique (user, place, channel) combinations
    unique_shares_tracker = set()

    print(f"Generating approximately {TARGET_SHARE_RECORDS} share records...")

    # Continue generating until the target is reached
    while len(all_shares) < TARGET_SHARE_RECORDS:
        user_id = random.choice(user_ids)
        place_id = random.choice(place_ids)

        # Randomly decide how many channels this user will share this place to (1 to 5)
        num_channels_to_share = random.randint(1, len(SHARE_CHANNELS))

        # Randomly select channels without replacement
        channels_for_this_share = random.sample(SHARE_CHANNELS, num_channels_to_share)

        for channel in channels_for_this_share:
            share_tuple = (user_id, place_id, channel)

            # Ensure the combination is unique before adding
            if share_tuple not in unique_shares_tracker:
                unique_shares_tracker.add(share_tuple)
                all_shares.append({
                    "user_id": user_id,
                    "place_id": place_id,
                    "shared_to": channel
                })

                # Check if we have enough records to stop early
                if len(all_shares) >= TARGET_SHARE_RECORDS:
                    break

        if len(all_shares) >= TARGET_SHARE_RECORDS:
            break

    print(f"Generated {len(all_shares)} unique share records.")

    # --- Create DataFrame and save to Excel ---
    if not all_shares:
        print("No shares were generated. Exiting.")
        return

    df = pd.DataFrame(all_shares)

    # Add a unique ID column
    df.insert(0, "id", range(1, len(df) + 1))

    print(f"Saving data to {OUTPUT_FILE}...")
    df.to_excel(OUTPUT_FILE, index=False)

    print(f"✅ Successfully created share data: {len(df)} rows saved to {os.path.basename(OUTPUT_FILE)}")

if __name__ == "__main__":
    generate_shares()
