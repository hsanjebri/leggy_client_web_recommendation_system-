# 🍽️ Legy Recommendation System

![Python version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Docker version](https://img.shields.io/badge/Docker-Supported-blue.svg)
![Kafka version](https://img.shields.io/badge/Kafka-Ready-orange.svg)

This repository houses the core **Recommendation Engine** for the Legy food delivery mobile application. It is a highly modular, scalable system that provides personalized restaurant and product suggestions to Legy users. 

This project operates as a dedicated microservice within the broader Legy ecosystem. While the Legy client is built with **Angular** and the primary backend relies on **Spring Boot**, this recommendation microservice leverages **Python**, **Machine Learning**, and **Kafka** to deliver intelligent, real-time recommendations.

---

## 🏗️ Architecture within Legy Ecosystem

The recommendation engine is completely decoupled from the main Spring backend, communicating via RESTful APIs and asynchronous Kafka messages.

```mermaid
graph TD
    %% Define Nodes
    Client[📱 Angular Client App]
    Spring[🌱 Spring Boot Backend]
    RecSys[🐍 Python Recommendation System]
    Mongo[(🍃 MongoDB)]
    Kafka((⚡ Kafka Broker))

    %% Connections
    Client <-->|REST APIs| Spring
    Spring -->|Publishes Events\n(User actions, new orders)| Kafka
    Kafka -->|Consumes Events| RecSys
    Client <-->|REST APIs\n(Fetch recommendations)| RecSys
    
    %% DB Connections
    Spring <--> Mongo
    RecSys <--> Mongo

    style Client fill:#dd1b16,stroke:#fff,stroke-width:2px,color:#fff
    style Spring fill:#6db33f,stroke:#fff,stroke-width:2px,color:#fff
    style RecSys fill:#3776ab,stroke:#fff,stroke-width:2px,color:#fff
    style Mongo fill:#4DB33D,stroke:#fff,stroke-width:2px,color:#fff
    style Kafka fill:#231f20,stroke:#fff,stroke-width:2px,color:#fff

```

### How Data Flows
1. **User Interactions:** When a user orders food, likes a restaurant, or leaves a review, the **Spring Backend** registers these actions in MongoDB and publishes an event to **Kafka**.
2. **Real-time Processing:** The **Python Recommendation System** (specifically `kafka_consumer.py`) listens to these Kafka topics, updates the user's vector representation on-the-fly, and precomputes new recommendations.
3. **Serving Recommendations:** When the **Angular Client** needs to display suggestions, it directly queries the Python `api.py` REST endpoints for fast delivery.

---

## ✨ Core Features

The orchestrator (`orchestrator.py`) intelligently combines several strategies to provide the best possible recommendations:

- **👥 Collaborative Filtering (`collaborative_engine.py`)**: Uses user behavioral vectors (e.g., cares about price, quality) and finds similar "neighbor" users to suggest restaurants they liked.
- **🍔 Content-Based Filtering (`content_engine.py`)**: Analyzes product features (ingredients, categories, prices) to suggest specific menu items from a chosen restaurant.
- **💬 Nuanced Sentiment Analysis**: Employs VADER and BERT models to analyze textual reviews, understanding not just ratings, but actual sentiment towards food, service, and cleanliness to refine user profiles.
- **⚖️ Maximal Marginal Relevance (MMR)**: Ensures diversity in recommendations. If you love pizza, it will show you the best pizza place, but won't fill your top 5 *only* with pizza places—it diversifies the cuisine types.
- **⏳ Time Decay Weighting**: Recent interactions heavily influence suggestions compared to older habits.
- **🧊 Robust Cold Start Strategies (`fallback_engine.py`)**: Ensures brand new users still get excellent suggestions using generalized preferences, global popularity, or random high-rated options until enough data is collected.

---

## 🛠️ Technology Stack

| Component | Technology |
| :--- | :--- |
| **Core API** | Flask |
| **Data Processing** | Pandas, NumPy |
| **Machine Learning** | PyTorch, Scikit-learn, Transformers (BERT) |
| **NLP** | NLTK, VADER Sentiment |
| **Database** | MongoDB |
| **Event Streaming** | Apache Kafka |
| **Deployment** | Docker, Docker Compose, Gunicorn, Supervisor |

---

## 🚀 Installation & Setup

### Option 1: Docker (Recommended for Production)

The easiest way to run the entire stack (including MongoDB and Kafka) is using Docker Compose.

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd Legy-recommendation-system
   ```

2. Start the services:
   ```bash
   docker-compose up -d
   ```
   *This will spin up Zookeeper, Kafka, MongoDB, and the Python application.*

3. The API will be available at `http://localhost:8000`.

### Option 2: Local Development Setup

If you need to run the Python app directly for development:

1. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure your environment:
   Ensure `config.yaml` points to your running MongoDB and Kafka instances. By default, it looks for `config.yaml` in the root directory.

4. Run the API:
   ```bash
   python api.py
   ```

5. Run the Kafka Consumer (in a separate terminal):
   ```bash
   python kafka_consumer.py
   ```

---

## 🔌 API Endpoints

The system exposes RESTful endpoints for the Angular client to consume.

### 1. Generate Restaurant Recommendations
Computes and returns the top 5 restaurants for a user.

- **URL:** `/recommendations/restaurants`
- **Method:** `GET`
- **Query Params:** `user_id=[string]` (Username or Object ID)

### 2. Generate Product Recommendations
Returns specific product suggestions categorized by recommended restaurants.

- **URL:** `/recommendations/products`
- **Method:** `GET`
- **Query Params:** `user_id=[string]`

### 3. Get Stored Recommendations
Retrieves precomputed recommendations (faster, updated via Kafka).

- **URL:** `/stored/recommendations/restaurants` or `/stored/recommendations/products`
- **Method:** `GET`
- **Query Params:** `user_id=[string]`

### 4. Admin / Testing Endpoints
- **Reload Users:** `POST /reload/users` - Forces memory reload of user vectors from DB.
- **Cold Start Test:** `GET /recommendations/cold-start-test?user_id=[string]` - Simulates a brand new user.

---

## 📁 Key Project Files

- `api.py`: The Flask application serving REST endpoints.
- `kafka_consumer.py`: Background worker listening for app events.
- `orchestrator.py`: The "brain" that balances collaborative, content, and fallback engines.
- `collaborative_engine.py` & `content_engine.py`: Core recommendation logic.
- `model_handler.py`: Manages the BERT ML models and user vectors.

---
*Built with ❤️ for the Legy Food Delivery App*
---test
