import pickle
import numpy as np
import torch
from transformers import BertTokenizer, BertForSequenceClassification
from torch.nn.functional import softmax
import yaml
import os
import logging
from drive_utils import ensure_model_files

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

with open('config.yaml') as f:
    config = yaml.safe_load(f)

class BERTModelHandler:
    def __init__(self, model_path, vectors_path):
        ensure_model_files()
        logger.info(f"Loading BERT model from {model_path}")
        self.tokenizer = BertTokenizer.from_pretrained(model_path)
        self.model = BertForSequenceClassification.from_pretrained(model_path)
        self.model.eval()
        self.vectors_path = vectors_path
        self.id_to_vector = self.load_vectors()

    def compute_vector(self, text):
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=128)
        with torch.no_grad():
            logits = self.model(**inputs).logits
            probs = softmax(logits, dim=1).squeeze().numpy()
        return probs

    def save_vectors(self):
        try:
            with open(self.vectors_path, "wb") as f:
                pickle.dump(self.id_to_vector, f)
            logger.info(f"Saved vectors to {self.vectors_path}")
        except Exception as e:
            logger.error(f"Failed to save vectors: {e}")
            raise

    def load_vectors(self):
        if not os.path.exists(self.vectors_path):
            logger.warning(f"Vectors file not found at {self.vectors_path}. Starting with empty vectors.")
            return {}

        if os.path.getsize(self.vectors_path) == 0:
            logger.warning(f"Vectors file is empty at {self.vectors_path}. Starting with empty vectors.")
            return {}

        try:
            with open(self.vectors_path, "rb") as f:
                vectors = pickle.load(f)
                if isinstance(vectors, dict):
                    logger.info(f"Loaded {len(vectors)} vectors from {self.vectors_path}")
                    return vectors
                else:
                    logger.warning(f"Unexpected vector format in {self.vectors_path}. Starting empty.")
                    return {}
        except Exception as e:
            logger.error(f"Could not load vectors: {e}. Starting with empty.")
            return {}

    def add_missing_user_vectors(self, users_df):
        added = 0
        for _, row in users_df.iterrows():
            user_id = row.get("user_id")
            if user_id in self.id_to_vector:
                continue

            profile_text = row.get("bio") or row.get("preferences") or row.get("username")
            if not profile_text:
                continue

            try:
                vector = self.compute_vector(profile_text)
                self.id_to_vector[user_id] = vector
                added += 1
            except Exception as e:
                logger.warning(f"Could not compute vector for {user_id}: {e}")

        if added > 0:
            self.save_vectors()
            logger.info(f"✅ Added {added} missing user vectors.")

    def build_user_vector(self, user_id: str, review_collection, order_collection):
        """
        Rebuild the user vector based on both review comments and order product names.
        """
        # Fetch review comments
        comments = [r["comment"] for r in review_collection.find({"userId": user_id}) if "comment" in r]

        # Fetch product names from past orders
        orders = list(order_collection.find({"clientId": user_id}))
        order_texts = []
        for order in orders:
            for item in order.get("items", []):
                name = item.get("productName")
                if name:
                    order_texts.append(name)

        combined = comments + order_texts

        if not combined:
            logger.warning(f"No text data found for user {user_id}. Skipping vector rebuild.")
            return

        logger.info(f"Recomputing vector for user {user_id} from {len(combined)} texts")

        try:
            vectors = [self.compute_vector(text) for text in combined]
            mean_vector = np.mean(vectors, axis=0)
            self.id_to_vector[user_id] = mean_vector
            self.save_vectors()
            logger.info(f"✅ Updated vector for user {user_id}")
        except Exception as e:
            logger.error(f"Error computing vector for user {user_id}: {e}")
