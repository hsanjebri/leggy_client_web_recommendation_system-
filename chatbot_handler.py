import pandas as pd
import difflib
import re
import unicodedata
from data_loader import get_mongo_client, get_collections

# === Stopwords: English + French combined ===
STOPWORDS = set("""
a about above after again against all am an and any are aren't as at be because been
before being below between both but by can't cannot could couldn't did didn't do does doesn't
doing don't down during each few for from further had hadn't has hasn't have haven't having
he he'd he'll he's her here here's hers herself him himself his how how's i i'd i'll i'm
i've if in into is isn't it it's its itself let's me more most mustn't my myself no nor
not of off on once only or other ought our ours ourselves out over own same shan't she she'd
she'll she's should shouldn't so some such than that that's the their theirs them themselves then
there there's these they they'd they'll they're they've this those through to too under until up
very was wasn't we we'd we'll we're we've were weren't what what's when when's where where's which
while who who's whom why why's with won't would wouldn't you you'd you'll you're you've your yours
yourself yourselves
alors au aucun aussi autre avant avec avoir bon car ce cela ces ceux chaque chez comme comment
dans des du donc dos elle elles en encore est et être eu eux fait faites fois font hors ici il ils
je juste la le les leur là ma maintenant mais mes mien moins mon mot même ni nom nos notre nous ou
où par parce pas peu peut plus plusieurs pour pourquoi quand que quel quelle quels qui sa sans
ses seulement si sien son sont sous soyez sujet sur ta te tes tien toi ton toujours tous tout trop
très tu valeur votre vous vu ça étaient état était étions être
""".split())

# === Normalize text for consistent matching ===
def normalize(text):
    return ''.join(
        c for c in unicodedata.normalize('NFD', text.lower())
        if unicodedata.category(c) != 'Mn'
    )

# === Extract Keywords ===
def extract_keywords(text):
    normalized_text = normalize(text)
    words = re.findall(r'\b\w+\b', normalized_text)
    return [w for w in words if w not in STOPWORDS and len(w) > 2]

# === Load Data from MongoDB ===
try:
    client = get_mongo_client()
    collections = get_collections(client)

    # Load and process products
    products_df = pd.DataFrame(list(collections["products"].find()))
    if products_df.empty:
        print("⚠️ No products found in database!")
        merged_df = pd.DataFrame()
    else:
        products_df["restaurantId"] = products_df["restaurantId"].astype(str)

        # Load and process restaurants
        restaurants_cursor = collections["restaurants"].find({}, {"_id": 1, "nom": 1, "averageRating": 1})
        restaurants_df = pd.DataFrame(list(restaurants_cursor))
        if restaurants_df.empty:
            print("⚠️ No restaurants found in database!")
            merged_df = products_df
        else:
            restaurants_df["_id"] = restaurants_df["_id"].astype(str)
            restaurants_df.rename(columns={"_id": "restaurantId"}, inplace=True)

            # Merge products with restaurants
            merged_df = products_df.merge(
                restaurants_df,
                on="restaurantId",
                how="left"
            )
    
    print(f"✅ Loaded {len(merged_df)} products for chatbot")
    
except Exception as e:
    print(f"❌ Error loading data: {e}")
    merged_df = pd.DataFrame()

# === Chatbot Logic ===
def get_recommendations_from_text(user_message):
    try:
        if merged_df.empty:
            return {
                "matched_keywords": [],
                "results": [],
                "error": "No data available"
            }
            
        keywords = extract_keywords(user_message)
        matched_rows = []

        for _, row in merged_df.iterrows():
            name = normalize(str(row.get("name", "")))
            # Use description instead of categorieName since that's what exists
            description = normalize(str(row.get("description", "")))
            text = f"{name} {description}"

            # Fuzzy match using keywords
            if any(any(difflib.get_close_matches(k, text.split(), cutoff=0.8)) for k in keywords):
                matched_rows.append(row)

        if matched_rows:
            result_df = pd.DataFrame(matched_rows)
            # Sort by averageRating if it exists, otherwise by name
            if "averageRating" in result_df.columns:
                top_df = result_df.sort_values(by="averageRating", ascending=False).head(7)
            else:
                top_df = result_df.head(7)
                
            return {
                "matched_keywords": keywords,
                "results": [
                    {
                        "name": row.get("name", ""),
                        "price": row.get("pricePostCom", ""),
                        "description": row.get("description", ""),
                        "restaurant": row.get("nom", "Unknown"),
                        "rating": row.get("averageRating", 0)
                    }
                    for _, row in top_df.iterrows()
                ]
            }
        else:
            return {
                "matched_keywords": keywords,
                "results": [],
                "message": "No matching products found"
            }
    except Exception as e:
        return {
            "matched_keywords": [],
            "results": [],
            "error": f"Error processing request: {str(e)}"
        }
