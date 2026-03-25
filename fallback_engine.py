import logging
import pandas as pd
from preference_Recommendation import generate_first_time_recommendations

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

class FallbackEngine:
    def __init__(self, ratings_df, collections):
        self.ratings = ratings_df.copy() if ratings_df is not None else pd.DataFrame()
        self.collections = collections
        self.restaurants_col = collections.get("restaurants")
        logging.debug(f"Ratings DataFrame shape: {self.ratings.shape}")
        if self.restaurants_col is None:
            logging.warning("restaurants_col not found in collections. Global popular recommendations may fail.")

    def preference_fallback(self, user_id, top_n=5):
        logging.debug(f"Calling preference_fallback for user {user_id}")
        try:
            pref_result = generate_first_time_recommendations(user_id)
            logging.debug(f"Preference result: {pref_result}")
            if pref_result and pref_result.get("recommendations"):
                flat_recs = [
                    (r[0], r[1]) 
                    for cat in pref_result["recommendations"].values() 
                    for r in cat
                ][:top_n]
                logging.debug(f"Flattened recommendations: {flat_recs}")
                return flat_recs
            else:
                logging.warning(f"No preference-based recommendations for user {user_id}")
                return None
        except Exception as e:
            logging.error(f"Error in preference_fallback for user {user_id}: {str(e)}")
            return None

    def global_popular_restaurants(self, top_n=5):
        """Get globally popular restaurants with multiple fallback strategies"""
        logging.debug(f"Getting global popular restaurants (top_n={top_n})")
        
        # Strategy 1: Use ratings data if available
        if not self.ratings.empty:
            try:
                if 'score' in self.ratings.columns:
                    self.ratings['score'] = self.ratings['score'].astype(str).str.replace(',', '.')
                    self.ratings['score'] = pd.to_numeric(self.ratings['score'], errors='coerce')
                    
                    # Get restaurants with at least 3 reviews for reliability
                    restaurant_counts = self.ratings.groupby("Restaurant").size()
                    reliable_restaurants = restaurant_counts[restaurant_counts >= 3].index
                    
                    if len(reliable_restaurants) > 0:
                        popular = self.ratings[self.ratings["Restaurant"].isin(reliable_restaurants)]
                        popular = popular.groupby("Restaurant")["score"].agg(['mean', 'count']).reset_index()
                        popular = popular.sort_values(by="mean", ascending=False).head(top_n)
                        
                        if 'restaurantId' in self.ratings.columns:
                            popular = popular.merge(
                                self.ratings[["Restaurant", "restaurantId"]].drop_duplicates(), 
                                on="Restaurant", how="left"
                            )
                            return [(row["Restaurant"], str(row["restaurantId"]) if pd.notna(row["restaurantId"]) else "Unknown", row["mean"]) for _, row in popular.iterrows()]
                        return [(row["Restaurant"], "Unknown", row["mean"]) for _, row in popular.iterrows()]
            except Exception as e:
                logging.error(f"Error processing ratings data: {str(e)}")

        # Strategy 2: Use restaurant collection with average ratings
        if self.restaurants_col is not None:
            try:
                # Get restaurants with good ratings and sufficient data
                pipeline = [
                    {"$match": {
                        "averageRating": {"$gte": 3.5, "$exists": True},
                        "nom": {"$exists": True, "$ne": ""}
                    }},
                    {"$sort": {"averageRating": -1}},
                    {"$limit": top_n * 2},  # Get more than needed
                    {"$project": {"_id": 1, "nom": 1, "averageRating": 1}}
                ]
                
                restaurants = list(self.restaurants_col.aggregate(pipeline))
                if restaurants:
                    logging.debug(f"Found {len(restaurants)} restaurants from collection")
                    return [(r['nom'], str(r['_id']), r['averageRating']) for r in restaurants[:top_n]]
            except Exception as e:
                logging.error(f"Error querying restaurants collection: {str(e)}")

        # Strategy 3: Get any restaurants as last resort
        if self.restaurants_col is not None:
            try:
                logging.warning("Using last resort: any available restaurants")
                cursor = self.restaurants_col.find({}, {"_id": 1, "nom": 1}).limit(top_n)
                restaurants = list(cursor)
                if restaurants:
                    return [(r['nom'], str(r['_id']), 3.0) for r in restaurants]  # Default rating
            except Exception as e:
                logging.error(f"Error in last resort restaurant query: {str(e)}")

        logging.warning("No global fallback restaurants available")
        return []

    def __repr__(self):
        return f"FallbackEngine(ratings_shape={self.ratings.shape}, collections_available={bool(self.collections)})"