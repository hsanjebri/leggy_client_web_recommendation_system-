import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime
import logging
from bson import ObjectId
import traceback

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class CollaborativeEngine:
    def __init__(self, model_handler, collections, id_to_vector, name_to_id, id_to_name, labels,
                 restaurant_name_to_id, order_repository, product_repository, alpha=0.01):
        self.model_handler = model_handler
        self.collections = collections
        self.reviews_col = collections["avis-restaurant"]
        self.neighbors_col = collections["user_neighbors"]
        self.id_to_vector = id_to_vector
        self.name_to_id = name_to_id
        self.id_to_name = id_to_name
        self.labels = labels
        self.restaurant_name_to_id = restaurant_name_to_id
        self.order_repository = order_repository
        self.product_repository = product_repository
        self.alpha = alpha
        self.MAX_NEIGHBORS = 10
        self.MAX_RECOMMENDATIONS = 10

        reviews = list(self.reviews_col.find({}))
        self.ratings = pd.DataFrame(reviews)
        logging.debug(f"Ratings DataFrame shape: {self.ratings.shape}")
        if not self.ratings.empty:
            self.ratings.rename(columns={
                "User": "User",
                "restaurent_Id": "restaurantId",  # Fix typo
                "restaurantId": "RestaurantId",   # Rename to expected case
                "User Rating": "UserRating",
                "createdAt": "CreatedAt"
            }, inplace=True)

            # Convert Rating to numeric, handling commas
            if 'score' in self.ratings.columns:
                self.ratings['score'] = pd.to_numeric(
                    self.ratings['score'].astype(str).str.replace(',', '.'),
                    errors='coerce'
                )
                self.ratings['Rating'] = self.ratings['score']

            if 'CreatedAt' in self.ratings.columns:
                self.ratings['CreatedAt'] = pd.to_datetime(self.ratings['CreatedAt'], errors='coerce')
            else:
                self.ratings['CreatedAt'] = pd.NaT

            # Remove duplicate columns
            self.ratings = self.ratings.loc[:, ~self.ratings.columns.duplicated()]
            logging.debug(f"Ratings columns after rename: {self.ratings.columns.tolist()}")

    def rebuild_user_profile(self, user_id: str) -> bool:
        """
        Rebuild the user profile vector from reviews.
        Works with both UUID userId (from Mongo) and username (fallback).
        """
        try:
            # If user_id is actually a username, resolve it
            real_user_id = self.name_to_id.get(user_id, user_id)

            # Query reviews by the resolved userId
            user_reviews = list(self.reviews_col.find({"userId": real_user_id}))
            if not user_reviews:
                logging.warning(f"No reviews found for user {real_user_id}")
                return False

            # Compute vectors from review text or comments
            vectors = []
            for r in user_reviews:
                review_text = r.get("Review") or r.get("comment")  # support both fields
                if review_text:
                    vec = self.model_handler.compute_vector(review_text)
                    if vec is not None:
                        vectors.append(vec)

            if not vectors:
                logging.warning(f"No valid review vectors for user {real_user_id}")
                return False

            # Average vector
            mean_vector = np.mean(vectors, axis=0)
            self.id_to_vector[user_id] = mean_vector  # store under original ID
            self.model_handler.save_vectors()

            logging.debug(f"✅ Rebuilt profile for user {user_id} (resolved: {real_user_id})")
            return True

        except Exception as e:
            logging.error(f"Error rebuilding profile for user {user_id}: {str(e)}\n{traceback.format_exc()}")
            return False

    def vector_similarity(self, u1, u2):
        v1 = self.id_to_vector.get(u1)
        v2 = self.id_to_vector.get(u2)
        if v1 is None or v2 is None:
            logging.warning(f"Missing vectors for users {u1} and/or {u2}")
            return 0
        return cosine_similarity([v1], [v2])[0][0]

    def apply_time_decay(self, created_at, current_time):
        if pd.isna(created_at):
            return 1.0
        days_since = (current_time - created_at).days
        return np.exp(-self.alpha * days_since)

    def get_precomputed_neighbors(self, user_id):
        try:
            doc = self.neighbors_col.find_one({"user_id": user_id})
            if not doc or "neighbors" not in doc:
                logging.warning(f"No precomputed neighbors for user {user_id}")
                return []
            return [(n["user_id"], n["score"]) for n in doc["neighbors"]]
        except Exception as e:
            logging.error(f"Error getting neighbors for user {user_id}: {str(e)}\n{traceback.format_exc()}")
            return []

    def recommend_restaurants(self, user_id, top_n=5):
        try:
            top_n = min(top_n, self.MAX_RECOMMENDATIONS)
            user_name = self.id_to_name.get(user_id, user_id)  # fallback to raw ID
            now = datetime.now()

            if user_id not in self.id_to_vector:
                if not self.rebuild_user_profile(user_id):
                    logging.warning(f"Failed to rebuild profile for user {user_id}")
                    return None, []

            sorted_similar = self.get_precomputed_neighbors(user_id)
            if not sorted_similar:
                logging.warning(f"No precomputed neighbors for user {user_id}, computing dynamically")
                sorted_similar = self.get_top_neighbors(user_id, top_n=self.MAX_NEIGHBORS)
                if not sorted_similar:
                    logging.warning(f"No neighbors found for user {user_id}")
                    return None, []

            neighbors = [u for u, _ in sorted_similar]
            if not neighbors:
                logging.warning(f"No neighbors available for user {user_id}")
                return None, []

            # Dynamically handle column name
            rating_col = "RestaurantId" if "RestaurantId" in self.ratings.columns else "restaurantId"
            user_rated = set(self.ratings[self.ratings["User"] == user_name][rating_col])
            logging.debug(f"Restaurants rated by user {user_name}: {user_rated}")

            neighbor_names = [self.id_to_name.get(uid, uid) for uid in neighbors]
            neighbor_ratings = self.ratings[self.ratings["User"].isin(neighbor_names)].copy()
            logging.debug(f"Neighbor ratings shape: {neighbor_ratings.shape}")
            if neighbor_ratings.empty:
                logging.warning(f"No ratings from neighbors {neighbor_names}")
                return None, []

            neighbor_ratings['decay_factor'] = neighbor_ratings['CreatedAt'].apply(
                lambda x: self.apply_time_decay(x, now)
            )
            neighbor_ratings['WeightedRating'] = neighbor_ratings['UserRating'] * neighbor_ratings['decay_factor']

            recs = neighbor_ratings[~neighbor_ratings[rating_col].isin(user_rated)]
            logging.debug(f"Filtered neighbor ratings shape: {recs.shape}")

            top_restaurants = recs.groupby(rating_col)["WeightedRating"].mean().reset_index() \
                .sort_values(by="WeightedRating", ascending=False).head(top_n)

            if not top_restaurants.empty:
                logging.debug(f"Top restaurants for user {user_id}: {top_restaurants.to_dict()}")
                return top_restaurants, sorted_similar

            logging.warning(f"No recommendations for user {user_id}")
            return None, []
        except Exception as e:
            logging.error(f"Error recommending restaurants for user {user_id}: {str(e)}\n{traceback.format_exc()}")
            return None, []

    def get_top_neighbors(self, user_id, top_n=10):
        try:
            if user_id not in self.id_to_vector:
                success = self.rebuild_user_profile(user_id)
                if not success or user_id not in self.id_to_vector:
                    logging.warning(f"No profile for user {user_id}")
                    return []

            user_vector = self.id_to_vector[user_id].reshape(1, -1)
            similarities = []
            for other_id, other_vector in self.id_to_vector.items():
                if other_id == user_id:
                    continue
                score = cosine_similarity(user_vector, other_vector.reshape(1, -1))[0][0]
                similarities.append((other_id, score))

            top_neighbors = sorted(similarities, key=lambda x: x[1], reverse=True)[:top_n]
            logging.debug(f"Top neighbors for user {user_id}: {top_neighbors}")
            return top_neighbors
        except Exception as e:
            logging.error(f"Error getting top neighbors for user {user_id}: {str(e)}\n{traceback.format_exc()}")
            return []
