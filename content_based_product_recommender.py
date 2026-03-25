import pandas as pd
import numpy as np
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from nltk.stem import PorterStemmer
from nltk.corpus import stopwords
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import nltk
import logging
import os
from typing import List, Optional

# ========= NLTK & Sentiment Setup =========
NLTK_DATA = os.getenv("NLTK_DATA", "/app/nltk_data")
nltk.data.path.append(NLTK_DATA)

# Ensure stopwords corpus is available
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    logging.info("Downloading NLTK stopwords")
    nltk.download('stopwords', download_dir=NLTK_DATA, quiet=True)

# Initialize sentiment analyzer
vader_analyzer = SentimentIntensityAnalyzer()

# Load stopwords in English + French (fallback defined if NLTK not available)
try:
    stop_words = set(stopwords.words('english') + stopwords.words('french'))
except Exception as e:
    logging.warning(f"Failed to load stopwords: {e}")
    stop_words = set(["the", "a", "an", "and", "or", "of", "to", "in", "et", "le", "la", "de", "un", "une"])


class ContentBasedProductRecommender:
    """
    A recommender system based on content similarity (TF-IDF, price, rating, sentiment).
    Used to suggest products to users based on their order history and product descriptions.
    """
    def __init__(self, product_repository, order_repository, weights, Category):
        self.product_repository = product_repository
        self.order_repository = order_repository
        self.weights = weights  # (IngredientSimilarity, Price, Rating, Sentiment)

        # Load category mapping (id → category name)
        categories = list(Category.find())
        self.category_id_to_name = {str(cat['_id']): cat['name'] for cat in categories}

        # Load all products into a DataFrame with enriched features
        self.df = self._load_products()

    # ======== Data Preparation ========
    def _load_products(self):
        """
        Loads products from MongoDB and prepares them for recommendation:
        - Clean description text
        - Extract price, sentiment, category
        """
        products = self.product_repository.get_all_products()
        df = pd.DataFrame(products)

        if df.empty:
            logging.error("No products loaded from repository")
            return pd.DataFrame()
        if "pricePostCom" not in df.columns:
            logging.error("No 'pricePostCom' field found in products collection. Please check your data.")
            return pd.DataFrame()

        # Keep only rows with valid price, description and restaurantId
        df = df[df["pricePostCom"].notnull() & df["description"].notnull() & df["restaurantId"].notnull()]
        df["description"] = df["description"].astype(str)
        df["_id"] = df["_id"].astype(str)
        df["restaurantId"] = df["restaurantId"].astype(str)

        # Add human-readable category
        if 'categoryId' in df.columns:
            df['category_name'] = df['categoryId'].apply(lambda cid: self.category_id_to_name.get(str(cid), 'Unknown'))

        # Text preprocessing for TF-IDF
        df["CleanText"] = df["description"].apply(self._preprocess_text)

        # Ensure numeric price
        df["PriceValue"] = pd.to_numeric(df["pricePostCom"], errors='coerce')
        df = df.dropna(subset=["PriceValue"])

        # Default rating and sentiment
        df["Rating"] = 3.5  # default value if no real ratings exist
        df["Sentiment"] = df["description"].apply(self._compute_sentiment)

        df = df.reset_index(drop=True)
        logging.debug(f"Loaded {len(df)} products")
        return df

    def _preprocess_text(self, text):
        """Lowercase, remove punctuation, stem words, and remove stopwords."""
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)  # remove punctuation
        ps = PorterStemmer()
        tokens = text.split()
        return ' '.join([ps.stem(word) for word in tokens if word not in stop_words])

    def _compute_sentiment(self, text):
        """Compute sentiment score (-1 to 1) using VADER sentiment analysis."""
        try:
            return vader_analyzer.polarity_scores(text)['compound']
        except Exception as e:
            logging.warning(f"Sentiment analysis failed: {e}")
            return 0.0

    # ======== User History ========
    def _get_user_product_ids(self, client_id: str) -> List[str]:
        """
        Fetch all product IDs from the user’s past orders.
        Used as the base for computing similarity.
        """
        orders = self.order_repository.get_orders_by_client_id(client_id)
        product_ids = []
        for order in orders:
            for item in order.get("items", []):
                pid = item.get("productId")
                if pid:
                    product_ids.append(str(pid))
        product_ids = list(set(product_ids))
        logging.debug(f"User {client_id} has {len(product_ids)} product IDs: {product_ids}")
        return product_ids

    # ======== Main Entry Point ========
    def recommend_for_user(self, client_id: str, restaurant_id: Optional[str], top_n: int = 5) -> List[dict]:
        """
        Main function: recommend products for a user.
        - If restaurant_id is given: limit to that restaurant
        - If user has no history: use fallback
        - Else: compute content-based recommendations
        """
        if self.df.empty:
            logging.warning("No products available in database")
            return []

        user_product_ids = self._get_user_product_ids(client_id)
        logging.debug(f"Processing recommendations for user {client_id}, restaurant {restaurant_id}")

        # Case 1: Restaurant-specific recommendations
        if restaurant_id:
            rest_df = self.df[self.df["restaurantId"] == str(restaurant_id)]
            if rest_df.empty:
                logging.debug(f"No products for restaurant {restaurant_id}")
                return []
            if not user_product_ids:
                logging.debug(f"No order history for {client_id}, using random fallback for restaurant {restaurant_id}")
                return self._random_fallback(rest_df, top_n, restaurant_id)
            return self._recommend_similar_products(rest_df, user_product_ids, top_n)

        # Case 2: User has no history → fallback to random
        if not user_product_ids:
            logging.debug(f"No order history for {client_id}, using random fallback")
            return self._random_fallback(self.df, top_n, None)

        # Case 3: Full recommendation from all restaurants
        logging.debug(f"Recommending similar products for {client_id} from all restaurants")
        return self._recommend_similar_products(self.df, user_product_ids, top_n)

    # ======== Recommendation Logic ========
    def _recommend_similar_products(self, target_df: pd.DataFrame, user_product_ids: List[str], top_n: int) -> List[dict]:
        """
        Core recommendation logic:
        - Compute TF-IDF similarity between user’s products and all candidates
        - Adjust scores with price proximity, rating, sentiment
        - Return top-N results
        """
        user_df = self.df[self.df["_id"].isin(user_product_ids)]
        if user_df.empty:
            logging.debug(f"No matching products for user history, using random fallback")
            return self._random_fallback(target_df, top_n, target_df["restaurantId"].iloc[0] if not target_df.empty else None)

        # Compute average price from user history
        avg_price = user_df["PriceValue"].mean()

        # Build TF-IDF matrix on all product descriptions
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform(self.df["CleanText"])

        # Represent user’s product history as mean TF-IDF vector
        user_vector = vectorizer.transform(user_df["CleanText"])
        mean_user_vector = np.asarray(user_vector.mean(axis=0)).reshape(1, -1)

        # Ingredient similarity (cosine similarity between user and target products)
        target_df["IngredientSimilarity"] = cosine_similarity(mean_user_vector, tfidf_matrix[target_df.index]).flatten()

        # Price proximity (closer to user’s average price = higher score)
        price_range = target_df["PriceValue"].max() - target_df["PriceValue"].min()
        target_df["PriceProximity"] = 1 - abs(target_df["PriceValue"] - avg_price) / (price_range if price_range > 0 else 1)
        target_df["PriceProximity"] = target_df["PriceProximity"].fillna(0.5)

        # Weighted final score (weights come from config.yaml)
        w1, w2, w3, w4 = self.weights
        target_df["FinalScore"] = (
                w1 * target_df["IngredientSimilarity"] +
                w2 * target_df["PriceProximity"] +
                w3 * (target_df["Rating"] / 5.0) +
                w4 * ((target_df["Sentiment"] + 1) / 2) +  # scale sentiment -1→1 to 0→1
                np.random.uniform(0, 0.01, len(target_df)) # tie-breaking noise
        )

        # Remove already purchased products
        filtered_df = target_df[~target_df["_id"].isin(user_product_ids)]
        logging.debug(f"Filtered {len(filtered_df)} products for client")

        if filtered_df.empty:
            logging.debug(f"No filtered products, using random fallback")
            return self._random_fallback(target_df, top_n, target_df["restaurantId"].iloc[0] if not target_df.empty else None)

        # Sort by score and return top-N products
        logging.debug(f"Scores: {filtered_df[['_id', 'name', 'IngredientSimilarity', 'PriceProximity', 'FinalScore']].to_dict('records')}")
        top_df = filtered_df.sort_values(by="FinalScore", ascending=False).head(top_n)
        return top_df.to_dict(orient="records")

    # ======== Fallback Strategy ========
    def _random_fallback(self, df: pd.DataFrame, top_n: int, restaurant_id: Optional[str]) -> List[dict]:
        """
        Fallback if user has no history:
        - Filter by restaurant if provided
        - Prefer high-rated products
        - Ensure category diversity
        - Randomly select top-N
        """
        if df.empty:
            return []

        # Filter by restaurant scope
        if restaurant_id:
            df = df[df["restaurantId"] == str(restaurant_id)]
            if df.empty:
                logging.debug(f"No products available for restaurant {restaurant_id} in fallback")
                return []

        # Prioritize popular products (by Rating if exists)
        if "Rating" in df.columns:
            top_df = df.sort_values(by="Rating", ascending=False).head(top_n * 2)
        else:
            top_df = df

        # Try to ensure category diversity (1 product per category)
        if "category_name" in top_df.columns:
            top_df = top_df.groupby("category_name").apply(
                lambda x: x.sample(n=min(1, len(x)), random_state=None)
            ).reset_index(drop=True)
            if len(top_df) >= top_n:
                return top_df.head(top_n).to_dict(orient="records")

        # If still too many candidates, pick random
        top_df = top_df.sample(n=min(top_n, len(top_df)), random_state=None)
        logging.debug(f"Random fallback selected {len(top_df)} products")
        return top_df.to_dict(orient="records")
