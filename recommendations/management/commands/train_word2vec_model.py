import logging
import re
import string
import pandas as pd
from gensim.models import Word2Vec
from pythainlp.corpus import thai_stopwords
from pythainlp.tokenize import word_tokenize
from pythainlp.util import normalize
from django.core.management.base import BaseCommand
from review_place.models import Place

class Command(BaseCommand):
    help = 'Trains and saves the Thai2Vec Word2Vec model.'

    # Path where the trained model will be saved.
    # Note: This saves to the CWD of the manage.py command.
    THAI2VEC_MODEL_PATH = 'thai2vec.model'

    def _get_place_data(self):
        """Fetches place data from the database."""
        places = Place.objects.all().values('id', 'description')
        return pd.DataFrame(list(places))

    def _preprocess_thai_text(self, text):
        """Preprocesses Thai text for Word2Vec training."""
        if not isinstance(text, str):
            return []
        text = normalize(text)
        text = re.sub(rf'[\s{string.punctuation}a-zA-Z0-9]+', '', text)
        tokens = word_tokenize(text, engine='newmm')
        stop_words = thai_stopwords()
        filtered_tokens = [word for word in tokens if word not in stop_words and not word.isspace()]
        return filtered_tokens

    def handle(self, *args, **options):
        """The main logic of the management command."""
        logger = logging.getLogger(__name__)
        self.stdout.write(self.style.SUCCESS('Starting Thai2Vec model training...'))

        places_df = self._get_place_data()

        if places_df.empty or 'description' not in places_df.columns or places_df['description'].isnull().all():
            self.stdout.write(self.style.WARNING('No description data available to train the model. Aborting.'))
            return

        self.stdout.write(f'Preprocessing text from {len(places_df)} places...')
        sentences = [self._preprocess_thai_text(text) for text in places_df['description'].dropna()]

        if not any(sentences):
            self.stdout.write(self.style.WARNING('No valid sentences found after preprocessing. Aborting.'))
            return

        self.stdout.write('Training Word2Vec model...')
        try:
            # Train the model
            model = Word2Vec(sentences, vector_size=300, window=5, min_count=1, workers=4)

            # Save the trained model
            model.save(self.THAI2VEC_MODEL_PATH)

            self.stdout.write(self.style.SUCCESS(f'Successfully trained and saved the model to {self.THAI2VEC_MODEL_PATH}'))
        except Exception as e:
            logger.error(f"Error during model training: {e}")
            self.stdout.write(self.style.ERROR(f'An error occurred during model training: {e}'))
