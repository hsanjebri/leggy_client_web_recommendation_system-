from kafka import KafkaConsumer
import json
from pymongo.errors import ConnectionFailure
from data_loader import get_mongo_client, get_collections, reload_users
from api import orchestrator, save_recommendations, restaurants, products, oid_list, clean_doc
from model_handler import BERTModelHandler
from collaborative_engine import CollaborativeEngine
from product_repository import ProductRepository
from order_repository import OrderRepository
import logging
import time
import traceback
import yaml

# ========== Logging ==========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

# === Load config.yaml ===
with open("config.yaml") as f:
    config = yaml.safe_load(f)

logging.getLogger("kafka").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

MONGO_URI = config.get("mongo_uri")
KAFKA_BOOTSTRAP_SERVERS = config.get("kafka_brokers")

# ========== Connection Functions ==========
def connect_mongo(retries=5, delay=5):
    for attempt in range(retries):
        try:
            client = get_mongo_client()
            client.admin.command("ping")
            logging.info("✅ MongoDB connection successful")
            return client
        except ConnectionFailure as e:
            logging.error(f"MongoDB connection attempt {attempt + 1} failed: {str(e)}")
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                exit(1)

def connect_kafka(topic, brokers, group_id, retries=5, delay=5):
    for attempt in range(retries):
        try:
            consumer = KafkaConsumer(
                topic,
                bootstrap_servers=brokers,
                group_id=group_id,
                auto_offset_reset='earliest',
                value_deserializer=lambda x: json.loads(x.decode('utf-8'))
            )
            logging.info("✅ Kafka consumer connected successfully")
            return consumer
        except Exception as e:
            logging.error(f"Kafka connection attempt {attempt + 1} failed: {str(e)}")
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                exit(1)

# ========== Initialization ==========
mongo_client = connect_mongo()
db = mongo_client[config.get("database_name")]
logging.info(f"Using database: {db.name}")
collections = get_collections(mongo_client)
neighbors_col = db["user_neighbors"]

if "user_recommendations" not in db.list_collection_names():
    db.create_collection("user_recommendations")
    logging.info("Created user_recommendations collection")

# ========== Model & Engines ==========
model_path = config.get("model_path", "models/bert_preference_model")
vectors_path = config.get("vectors_path", "models/user_vectors.pkl")

model_handler = BERTModelHandler(model_path, vectors_path)
users_df, name_to_id, id_to_name = reload_users(collections["users"])
model_handler.add_missing_user_vectors(users_df)
id_to_vector = model_handler.id_to_vector

restaurant_name_to_id = {
    r.get("nom").strip().lower(): str(r["_id"])
    for r in collections["restaurants"].find()
    if "nom" in r and "_id" in r
}

product_repo = ProductRepository(collections["products"])
order_repo = OrderRepository(collections["orders"])
engine = CollaborativeEngine(
    model_handler, collections, id_to_vector, name_to_id, id_to_name,
    ["cares_about_food_quality"], restaurant_name_to_id, order_repo, product_repo
)

# ========== Kafka Consumer ==========
consumer = connect_kafka('recommendation_requests', KAFKA_BOOTSTRAP_SERVERS, 'flask-recommender')
logging.info("Subscribed to topic 'recommendation_requests' with group 'flask-recommender'")

print("📥 Kafka consumer listening for recommendation_requests...")

for msg in consumer:
    logging.debug(f"Received Kafka message: {msg.value}")
    print("📥 Received Kafka message:", msg.value)

    raw_user_id = msg.value.get("user_id")
    if not raw_user_id:
        logging.error("❌ No user_id in Kafka message")
        continue

    # Resolve if it’s a username
    user_id = name_to_id.get(raw_user_id, raw_user_id)

    try:
        # === Rebuild vector from both reviews and orders ===
        model_handler.build_user_vector(user_id, collections["avis-restaurant"], collections["orders"])

        # === Recompute neighbors ===
        neighbors = engine.get_top_neighbors(user_id, top_n=10)
        if neighbors:
            neighbors_col.replace_one(
                {"user_id": user_id},
                {
                    "user_id": user_id,
                    "neighbors": [{"user_id": n_id, "score": float(sim)} for n_id, sim in neighbors]
                },
                upsert=True
            )
            logging.info(f"✅ Recomputed neighbors for user {user_id}")
        else:
            logging.warning(f"⚠️ No neighbors computed for user {user_id}")

        # === Trigger recommendations ===
        res = orchestrator.get_recommendations(user_id, top_n=5, allow_fallback=False)

        if not res or ("Recommendations" not in res and "Products" not in res):
            logging.warning(f"⚠️ No recommendations for user {user_id}")
            continue

        # === Save restaurant recs ===
        if res.get("Recommendations"):
            rest_ids = [rid for _, rid in res["Recommendations"]]
            docs = restaurants.find({"_id": {"$in": oid_list(rest_ids)}})
            payload = {"RecommendedRestaurants": [clean_doc(d) for d in docs]}
            save_recommendations(user_id, "restaurant", payload)
            print(f"✅ Stored restaurant recommendations for user {user_id}")

        # === Save product recs ===
        if res.get("Products"):
            product_recs = []
            for rest_name, product_list in res["Products"].items():
                rest_id = next((rid for name, rid in res["Recommendations"] if name.lower() == rest_name.lower()), None)
                if rest_id:
                    docs = products.find({"_id": {"$in": oid_list(product_list)}})
                    product_recs.append({
                        "restaurant_id": rest_id,
                        "products": [clean_doc(d) for d in docs]
                    })
            if product_recs:
                save_recommendations(user_id, "product", {"RecommendedProducts": product_recs})
                print(f"✅ Stored product recommendations for user {user_id}")

    except Exception as e:
        logging.error(f"❌ Error processing recommendation for user {user_id}: {str(e)}\n{traceback.format_exc()}")
