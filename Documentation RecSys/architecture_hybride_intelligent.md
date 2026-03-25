## Architecture – Système Hybride Intelligent (Recommendation System)

La vue ci-dessous modélise l'architecture logique du système de recommandation hybride qui combine filtrage collaboratif, contenu/présence sémantique (BERT), et un réordonnancement MMR, orchestré derrière des APIs et une interface chatbot.

```mermaid
flowchart LR
    %% Entrées Utilisateur
    U[(Utilisateur)] ---|messages, clics, commandes| UI[Chatbot / Frontend]

    %% API Layer
    UI --> API{{API / Chatbot API}}
    API --> ORCH[Orchestrator]

    %% Orchestrateur
    subgraph Orchestration
        ORCH[Orchestrator<br/>`orchestrator.py`]
        MMR[MMR Re-Ranker<br/>`mmr.py`]
    end

    ORCH -->|fusion & scoring| MMR

    %% Moteurs de recommandation
    subgraph Engines
        direction TB
        CE[Content Engine<br/>`content_engine.py`]
        CBF[Content-Based Product Recommender<br/>`content_based_product_recommender.py`]
        COL[Collaborative Engine<br/>`collaborative_engine.py`]
        FBE[Fallback Engine<br/>`fallback_engine.py`]
    end

    ORCH --> CE
    ORCH --> COL
    ORCH --> FBE
    CE --> CBF

    %% Modèle de préférences (BERT)
    subgraph Preferences Model
        direction TB
        MH[Model Handler<br/>`model_handler.py`]
        BERT[(BERT Preferences<br/>`models/bert_preference_model/`)]
    end

    CE --> MH
    MH --> BERT

    %% Données & Storage
    subgraph Data Layer
        direction TB
        PR[(Product Repository<br/>`product_repository.py`)]
        UR[(User Repository<br/>`user_repository.py`)]
        OR[(Order Repository<br/>`order_repository.py`)]
        MONGO[(MongoDB / Collections<br/>`mongo_utils.py`)]
        REDIS[(Redis Cache<br/>tests: `test_redis.py`)]
        VEC[(User Vectors<br/>`models/user_vectors.pkl`)]
    end

    PR --- MONGO
    UR --- MONGO
    OR --- MONGO
    REDIS --- ORCH
    VEC --- COL
    PR --- CE
    PR --- COL

    %% Ingestion temps réel / batch
    subgraph Streaming & Batch
        direction TB
        KAFKA[(Kafka Consumer<br/>`kafka_consumer.py`)]
        PRE[Precompute Neighbors<br/>`precompute_neighbors.py`]
        DL[Data Loader<br/>`data_loader.py`]
        DRIVE[Drive Utils<br/>`drive_utils.py`]
    end

    KAFKA --> ORCH
    PRE --> VEC
    DL --> MONGO
    DRIVE --> DL

    %% Flux de sortie
    MMR --> API
    API --> UI

    %% Outils de démarrage & exécution
    subgraph Runtime
        direction TB
        START[start_chatbot.py / main_runner.py]
        DOCKER[Docker & Supervisor<br/>`Dockerfile` `docker-compose.yml`<br/>`supervisord.conf`]
        CFG[Config<br/>`config.yaml`]
    end

    START --> API
    DOCKER --> START
    CFG --> ORCH
```

### Notes
- Le système est hybride: il combine un moteur collaboratif (`collaborative_engine.py`) et un moteur basé contenu/semantique (`content_engine.py` + BERT via `model_handler.py`), avec un mécanisme de re-rang MMR (`mmr.py`).
- Les dépôts (`product_repository.py`, `user_repository.py`, `order_repository.py`) s'appuient sur MongoDB (`mongo_utils.py`). Redis sert de cache à faible latence.
- Le composant `precompute_neighbors.py` met à jour les représentations/vecteurs utilisateurs (`models/user_vectors.pkl`) pour accélérer le collaboratif.
- L'API et le Chatbot (voir `api.py`, `chatbot_api.py`, `chatbot_handler.py`) exposent les recommandations au frontend.
- `kafka_consumer.py` permet l'ingestion d'événements en temps réel pour adapter les recommandations.

### Export de l'image
- Vous pouvez ouvrir ce fichier dans un éditeur compatible Mermaid (VS Code avec l'extension Mermaid) puis exporter en PNG/SVG.
- Ou utiliser la CLI Mermaid (mmdc):

```bash
npx @mermaid-js/mermaid-cli -i "Documentation RecSys/architecture_hybride_intelligent.md" -o "Documentation RecSys/architecture_hybride_intelligent.svg"
```



