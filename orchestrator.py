import numpy as np
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import logging
import traceback
import time
from bson import ObjectId
from typing import List, Dict, Any
from mmr import apply_mmr

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")


class RecommendationOrchestrator:
    def __init__(
            self,
            collaborative_engine,
            content_engine,
            fallback_engine,
            id_to_name,
            id_to_vector,
            labels,
            restaurant_name_to_id,
            collections,
            lambda_mmr=0.7,
            like_weight=0.1,
            dislike_penalty=0.2,
    ):
        self.collab = collaborative_engine
        self.content = content_engine
        self.fallback = fallback_engine
        self.id_to_name = id_to_name
        self.id_to_vector = id_to_vector
        self.labels = labels
        self.restaurant_name_to_id = restaurant_name_to_id
        self.collections = collections
        self.lambda_mmr = lambda_mmr
        self.like_weight = like_weight
        self.dislike_penalty = dislike_penalty
        self.products_col = self.collections["products"]
        self.restaurants_col = self.collections["restaurants"]
        self.feedback_col = self.collections["restaurant_reactions"]

    def get_recommendations(self, user_id: str, top_n: int = 5, allow_fallback: bool = True) -> Dict[str, Any]:
        logging.debug(f"Fetching recommendations for user {user_id}")

        try:
            # Check if user has any history (reviews, orders, preferences)
            user_has_history = self._check_user_history(user_id)
            
            if not user_has_history:
                logging.info(f"🆕 New user detected: {user_id} - using cold start strategies")
                return self._handle_cold_start_user(user_id, top_n)

            # Try computing neighbors on the fly
            neighbor_record = self.collections["user_neighbors"].find_one({"user_id": user_id})
            if not neighbor_record or not neighbor_record.get("neighbors"):
                logging.warning(f"No neighbors found in DB for user {user_id}, attempting to compute them...")
                neighbors = self.collab.get_top_neighbors(user_id, top_n=10)
                if neighbors:
                    self.collections["user_neighbors"].insert_one({
                        "user_id": user_id,
                        "neighbors": [{"user_id": n_id, "score": float(sim)} for n_id, sim in neighbors]
                    })
                    logging.info(f"✅ Neighbors computed and stored for user {user_id}")
                else:
                    logging.warning(f"⚠️ No neighbors could be computed for user {user_id}")
                    if allow_fallback:
                        return self._handle_cold_start_user(user_id, top_n)
                    return {
                        "Recommendations": [],
                        "Products": {},
                        "Message": "No neighbors available for this user"
                    }

            top_restaurants, sims = self.collab.recommend_restaurants(user_id, top_n)
            if top_restaurants is not None and not top_restaurants.empty:
                logging.debug(f"Collaborative recommendations: {top_restaurants.to_dict()}")
                return self._format_recommendation_result(user_id, top_restaurants, sims, top_n)

            # If collaborative filtering fails, use fallback
            if allow_fallback:
                logging.info(f"🔄 Collaborative filtering failed for user {user_id}, using fallback strategies")
                return self._handle_cold_start_user(user_id, top_n)

            return {
                "Recommendations": [],
                "Products": {},
                "Message": "No recommendations available for this user"
            }

        except Exception as e:
            logging.error(f"Error in get_recommendations for user {user_id}: {str(e)}\n{traceback.format_exc()}")
            # Even on error, try fallback if allowed
            if allow_fallback:
                logging.info(f"🆘 Error occurred, attempting fallback for user {user_id}")
                return self._handle_cold_start_user(user_id, top_n)
            raise

    def _format_recommendation_result(self, user_id: str, top_restaurants: pd.DataFrame, sims: List, top_n: int) -> Dict[str, Any]:
        recommended_products = {}
        rest_ids = [rid for rid in top_restaurants["RestaurantId"].tolist()[:top_n * 3] if ObjectId.is_valid(rid)]

        rest_docs = list(self.restaurants_col.find({"_id": {"$in": [ObjectId(rid) for rid in rest_ids]}}))
        id_to_name = {str(d["_id"]): d.get("nom", "").strip().lower() for d in rest_docs}
        top_names = [id_to_name.get(rid, "Unknown") for rid in rest_ids]
        relevance = top_restaurants["WeightedRating"].tolist()[:top_n * 3]
        norm_names = [n for n in top_names if n != "Unknown"]

        if len(norm_names) < top_n:
            logging.warning(f"Only {len(norm_names)} valid restaurants found for user {user_id}, falling back")
            global_recs = self.fallback.global_popular_restaurants(top_n)
            if global_recs:
                additional_names = [r[0].strip().lower() for r in global_recs if r[0].strip().lower() not in norm_names]
                norm_names.extend(additional_names[:top_n - len(norm_names)])
                relevance.extend([1.0] * (top_n - len(relevance)))

        with ThreadPoolExecutor(max_workers=3) as exe:
            feedback_docs, _, product_docs = exe.map(
                lambda f: f(),
                [
                    lambda: list(self.feedback_col.find({"userId": user_id})),
                    lambda: rest_docs,
                    lambda: list(self.products_col.find({"restaurantId": {"$in": rest_ids}})),
                ]
            )

        user_likes = {d["restaurantId"] for d in feedback_docs if d.get("reaction") == "LIKE"}
        user_dislikes = {d["restaurantId"] for d in feedback_docs if d.get("reaction") == "DISLIKE"}

        name_to_cat = {d["nom"].strip().lower(): d.get("mainCuisineType", "").lower() for d in rest_docs}
        categories = [name_to_cat.get(n, "") for n in norm_names]
        mmr_names = apply_mmr(norm_names, relevance[:len(norm_names)], categories, self.lambda_mmr, top_n)

        rest_scores = {}
        for name in mmr_names:
            rid = self.restaurant_name_to_id.get(name)
            if not rid:
                continue
            boost = self.like_weight if rid in user_likes else 0
            boost -= self.dislike_penalty if rid in user_dislikes else 0
            rest_scores[rid] = 1.0 + boost

        sorted_rids = sorted(rest_scores, key=rest_scores.get, reverse=True)[:top_n]

        for rid in sorted_rids:
            rest_name = next((n for n, _id in self.restaurant_name_to_id.items() if _id == rid), None)
            if not rest_name:
                continue

            products = self.content.cbf.recommend_for_user(user_id, rid, top_n=top_n)
            product_ids = [str(prod["_id"]) for prod in products if "_id" in prod]

            if len(product_ids) < top_n:
                remaining = top_n - len(product_ids)
                fallback_products = self.content.cbf.recommend_for_user(user_id, None, top_n=remaining)
                fallback_ids = [str(p["_id"]) for p in fallback_products if p["_id"] not in product_ids]
                product_ids.extend(fallback_ids[:remaining])

            if product_ids:
                recommended_products[rest_name] = product_ids[:top_n]

        neighbor_names = [self.id_to_name.get(uid, f"User_{uid}") for uid, _ in sims]
        neighbor_info = {self.id_to_name.get(uid, uid): norm_names for uid, _ in sims}
        neighbor_prefs = {
            self.id_to_name.get(uid, uid): dict(zip(self.labels, self.id_to_vector[uid].round(4).tolist()))
            for uid, _ in sims
        }
        target_vec = self.id_to_vector.get(user_id)
        target_pref = dict(zip(self.labels, target_vec.round(4).tolist())) if isinstance(target_vec, np.ndarray) else {}

        recommendations = [(n, self.restaurant_name_to_id.get(n, "Unknown")) for n in mmr_names[:top_n]]

        return {
            "Recommendations": recommendations,
            "Products": recommended_products,
            "Restaurants Rated by Target User": [],
            "Neighboring Users (IDs)": [uid for uid, _ in sims],
            "Neighboring Users (Names)": neighbor_names,
            "Restaurants Rated by Neighbors": neighbor_info,
            "Neighbor Preferences": neighbor_prefs,
            "Target User Preference": target_pref,
            "Message": "Optimized recommendations with product fallbacks",
        }

    def _check_user_history(self, user_id: str) -> bool:
        """Check if user has any history (reviews, orders, preferences)"""
        try:
            # Check for reviews
            review_count = self.collections["avis-restaurant"].count_documents({"userId": user_id})
            if review_count > 0:
                logging.debug(f"User {user_id} has {review_count} reviews")
                return True

            # Check for orders
            order_count = self.collections["orders"].count_documents({"userId": user_id})
            if order_count > 0:
                logging.debug(f"User {user_id} has {order_count} orders")
                return True

            # Check for preferences
            pref_count = self.collections["user_preferences"].count_documents({"userId": user_id})
            if pref_count > 0:
                logging.debug(f"User {user_id} has {pref_count} preference records")
                return True

            # Check for reactions
            reaction_count = self.collections["restaurant_reactions"].count_documents({"userId": user_id})
            if reaction_count > 0:
                logging.debug(f"User {user_id} has {reaction_count} reactions")
                return True

            logging.debug(f"User {user_id} has no history")
            return False
        except Exception as e:
            logging.error(f"Error checking user history for {user_id}: {str(e)}")
            return False

    def _handle_cold_start_user(self, user_id: str, top_n: int) -> Dict[str, Any]:
        """Handle recommendations for new users with no history"""
        logging.info(f"🆕 Handling cold start for user {user_id}")
        
        try:
            # Strategy 1: Try preference-based recommendations
            pref_recs = self.fallback.preference_fallback(user_id, top_n)
            if pref_recs:
                logging.info(f"✅ Preference-based recommendations found for user {user_id}")
                return self._format_cold_start_result(user_id, pref_recs, top_n, "preference-based")

            # Strategy 2: Use global popular restaurants
            global_recs = self.fallback.global_popular_restaurants(top_n)
            if global_recs:
                logging.info(f"✅ Global popular recommendations found for user {user_id}")
                return self._format_cold_start_result(user_id, global_recs, top_n, "global-popular")

            # Strategy 3: Use demographic-based recommendations (if available)
            demo_recs = self._get_demographic_recommendations(user_id, top_n)
            if demo_recs:
                logging.info(f"✅ Demographic-based recommendations found for user {user_id}")
                return self._format_cold_start_result(user_id, demo_recs, top_n, "demographic-based")

            # Strategy 4: Random high-rated restaurants as last resort
            random_recs = self._get_random_high_rated_restaurants(top_n)
            if random_recs:
                logging.info(f"✅ Random high-rated recommendations found for user {user_id}")
                return self._format_cold_start_result(user_id, random_recs, top_n, "random-high-rated")

            # If all strategies fail
            logging.warning(f"❌ All cold start strategies failed for user {user_id}")
            return {
                "Recommendations": [],
                "Products": {},
                "Message": "Unable to generate recommendations for new user",
                "ColdStart": True
            }

        except Exception as e:
            logging.error(f"Error in cold start handling for user {user_id}: {str(e)}")
            return {
                "Recommendations": [],
                "Products": {},
                "Message": f"Error generating cold start recommendations: {str(e)}",
                "ColdStart": True
            }

    def _format_cold_start_result(self, user_id: str, recommendations: List, top_n: int, strategy: str) -> Dict[str, Any]:
        """Format cold start recommendations into the expected structure"""
        try:
            # Convert recommendations to the expected format
            formatted_recs = []
            recommended_products = {}
            
            for i, rec in enumerate(recommendations[:top_n]):
                if isinstance(rec, tuple) and len(rec) >= 2:
                    rest_name, rest_id = rec[0], rec[1]
                    formatted_recs.append((rest_name, rest_id))
                    
                    # Get products for this restaurant
                    products = self.content.cbf.recommend_for_user(user_id, rest_id, top_n=top_n)
                    if products:
                        product_ids = [str(prod["_id"]) for prod in products if "_id" in prod]
                        recommended_products[rest_name] = product_ids[:top_n]

            return {
                "Recommendations": formatted_recs,
                "Products": recommended_products,
                "Restaurants Rated by Target User": [],
                "Neighboring Users (IDs)": [],
                "Neighboring Users (Names)": [],
                "Restaurants Rated by Neighbors": {},
                "Neighbor Preferences": {},
                "Target User Preference": {},
                "Message": f"Cold start recommendations using {strategy} strategy",
                "ColdStart": True,
                "Strategy": strategy
            }
        except Exception as e:
            logging.error(f"Error formatting cold start result for user {user_id}: {str(e)}")
            return {
                "Recommendations": [],
                "Products": {},
                "Message": f"Error formatting cold start recommendations: {str(e)}",
                "ColdStart": True
            }

    def _get_demographic_recommendations(self, user_id: str, top_n: int) -> List:
        """Get recommendations based on user demographics (age, location, etc.)"""
        try:
            # Get user demographics
            user_doc = self.collections["users"].find_one({"_id": ObjectId(user_id) if ObjectId.is_valid(user_id) else user_id})
            if not user_doc:
                return []

            # For now, return empty - this can be expanded based on available demographic data
            # Example: age-based, location-based, etc.
            logging.debug(f"Demographic recommendations not yet implemented for user {user_id}")
            return []
        except Exception as e:
            logging.error(f"Error getting demographic recommendations for user {user_id}: {str(e)}")
            return []

    def _get_random_high_rated_restaurants(self, top_n: int) -> List:
        """Get random high-rated restaurants as last resort"""
        try:
            # Get restaurants with high ratings
            pipeline = [
                {"$match": {"averageRating": {"$gte": 4.0}}},
                {"$sample": {"size": top_n * 2}},  # Get more than needed
                {"$project": {"_id": 1, "nom": 1, "averageRating": 1}}
            ]
            
            restaurants = list(self.restaurants_col.aggregate(pipeline))
            if restaurants:
                return [(r["nom"], str(r["_id"]), r.get("averageRating", 0)) for r in restaurants[:top_n]]
            return []
        except Exception as e:
            logging.error(f"Error getting random high-rated restaurants: {str(e)}")
            return []
