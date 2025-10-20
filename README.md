
# ApexInvest Advisor

**ApexInvest Advisor** is a free, open‑source stock recommendation platform designed to run on self‑hosted infrastructure or cloud free tiers.  The project demonstrates how to ingest financial data, engineer features, train machine learning models and serve personalised stock recommendations through a modern web interface.  All major components rely on open‑source software to minimise cost while providing flexibility and transparency.

## Architecture Overview

The system follows a modular microservices approach.  The diagram below summarises the major components and technologies used:

- **Data Ingestion & ETL** – A Python script under `data_ingestion/` pulls historical prices from Yahoo Finance via `yfinance`, computes technical indicators and attaches sentiment scores.  Free news APIs such as NewsAPI and GNews impose request limits (e.g. 100 requests per day【478964853890087†L25-L45】【158754512984029†L79-L90】), so rate limiting is implemented.  If external APIs are unavailable the script generates synthetic data.
- **Model Training** – A training script in `ml_model/` reads the feature table and constructs a target based on next‑day returns.  It trains a `RandomForestClassifier` from `scikit‑learn`, a free and open‑source library【615955049487310†L510-L518】 featuring a large catalogue of algorithms【615955049487310†L543-L551】.  The trained model is saved for serving.
- **Backend Service** – A FastAPI application in `backend/` loads the dataset and model, exposes RESTful endpoints (`/stocks`, `/stock/{ticker}`, `/recommendations`) and performs inference.  FastAPI is chosen for its high performance and open‑source nature【615955049487310†L510-L518】.  It also incorporates simple risk profiling logic and returns confidence scores.
- **Frontend** – A React single‑page application under `frontend/` uses Axios to call the backend and Chart.js to display price charts.  The interface is dark themed and mobile friendly.  React is an open‑source UI library maintained by Meta【558584139989063†L38-L44】 and licensed under MIT【558584139989063†L80-L82】.  Chart.js is a flexible JavaScript charting library【365786000430738†L4-L70】.
- **Datastores & Caching** – PostgreSQL provides relational storage【877669858257060†L34-L63】, MongoDB stores unstructured news articles【270802976666718†L70-L80】【270802976666718†L148-L158】 and Redis offers in‑memory caching【957321726490158†L130-L135】.  MinIO supplies S3‑compatible object storage【528171312752189†L152-L154】 for raw data and model artefacts.
- **API Gateway & Security** – Nginx or Kong Gateway can sit in front of the backend, providing reverse proxying and rate limiting.  Nginx is an HTTP server, reverse proxy and load balancer【576734157715076†L43-L65】.  Kong acts as a lightweight, cloud‑native API gateway to manage and route requests【298927620301812†L96-L109】.
- **Monitoring & Logging** – Prometheus collects metrics and Grafana visualises them【733729005149423†L16-L50】【957201044962566†L1657-L1662】.  The ELK stack (Elasticsearch, Logstash, Kibana) captures logs and offers real‑time data exploration【190494098481125†L59-L82】【32038916605934†L294-L308】.
- **Deployment** – Dockerfiles are provided for each microservice and Kubernetes manifests in `k8s/` describe how to deploy the services using K3s.  The stack can run on a single VPS or a Raspberry Pi cluster.

## Project Layout

```
apexinvest-advisor/
├── apexinvest_advisor/        # Shared Python package (configuration)
├── backend/                   # FastAPI backend service
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── data_ingestion/            # ETL scripts
│   ├── ingest.py
│   └── dataset.csv            # Generated feature table (created by script)
├── ml_model/                  # Model training and artefacts
│   ├── train_model.py
│   └── model.pkl              # Trained RandomForest model
├── frontend/                  # React frontend
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── App.js
│   │   ├── index.js
│   │   ├── index.css
│   │   └── components/
│   │       ├── StockChart.js
│   │       └── Recommendations.js
│   ├── package.json
│   ├── tailwind.config.js
│   └── Dockerfile
├── k8s/                       # Kubernetes deployment manifests
└── README.md                  # Project documentation (this file)
```

## Getting Started (Local Development)

1. **Clone the repository**

```bash
git clone https://your-repo-url.git
cd apexinvest-advisor
```

2. **Prepare a Python virtual environment** (optional but recommended)

```bash
python3 -m venv venv
source venv/bin/activate
```

3. **Install dependencies and run the ETL pipeline**

The ingestion script fetches historical data for a handful of tickers.  You can modify the list and date range if desired.  When run in this environment the script generates synthetic data if external APIs are unreachable.

```bash
pip install -r backend/requirements.txt
python3 data_ingestion/ingest.py
```

4. **Train the machine learning model**

```bash
python3 ml_model/train_model.py
```

5. **Run the backend API**

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

6. **Run the frontend**

You need Node.js and npm installed.  Build and start the development server:

```bash
cd frontend
npm install
npm start
```

The React app will be available at `http://localhost:3000` and will proxy API requests to `http://localhost:8000` (configured via `REACT_APP_BACKEND_URL`).

## Docker Compose (Optional)

To simplify deployment you can use Docker Compose to start all services.  Below is a sample `docker-compose.yml` you can adapt:

```yaml
version: '3.9'
services:
  backend:
    build: ./backend
    volumes:
      - ./data_ingestion/dataset.csv:/app/data_ingestion/dataset.csv:ro
      - ./ml_model/model.pkl:/app/ml_model/model.pkl:ro
      - ./apexinvest_advisor/config.py:/app/apexinvest_advisor/config.py:ro
    ports:
      - "8000:8000"

  frontend:
    build: ./frontend
    environment:
      - REACT_APP_BACKEND_URL=http://backend:8000
    ports:
      - "3000:80"

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_USER=apexinvest
      - POSTGRES_PASSWORD=apexinvest
      - POSTGRES_DB=apexinvest_db
    ports:
      - "5432:5432"

  mongodb:
    image: mongo:6
    environment:
      - MONGO_INITDB_ROOT_USERNAME=apexinvest
      - MONGO_INITDB_ROOT_PASSWORD=apexinvest
    ports:
      - "27017:27017"

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  minio:
    image: minio/minio
    command: server /data
    environment:
      - MINIO_ACCESS_KEY=minioadmin
      - MINIO_SECRET_KEY=minioadmin
    ports:
      - "9000:9000"
```

Run it with `docker-compose up --build` to launch all services.

## Kubernetes Deployment

The `k8s/` directory contains YAML manifests to deploy the backend, frontend, PostgreSQL, MongoDB, Redis and MinIO on a K3s cluster.  To deploy:

```bash
kubectl apply -f k8s/
```

These manifests define Deployments, Services and persistent volumes.  You may wish to add Ingress resources and TLS certificates depending on your environment.

## Security Notes

Please ensure that you set real API keys and secure passwords in `apexinvest_advisor/config.py` or via environment variables before deploying.  The default values are placeholders intended solely for development.  If exposing the API publicly you should integrate proper authentication (JWT or OAuth), use HTTPS and apply additional rate limiting with Nginx or Kong.

## Further Improvements

This repository provides a minimal but complete implementation of the ApexInvest Advisor.  Potential enhancements include:

* **Improved data ingestion** – Integrate EDGAR filings, FRED economic indicators and World Bank data.  Respect each provider’s terms and free tier limits【845412093651616†L49-L52】【478964853890087†L25-L45】【188755984008105†L179-L185】.
* **Real‑time sentiment analysis** – Stream news using Kafka and process it with a language model.  Use VADER or transformers for sentiment scoring.
* **User accounts and persistence** – Store user profiles, preferences and portfolios in PostgreSQL or MongoDB.
* **Model experimentation** – Try LSTM or XGBoost models for better predictive performance.  Consider TensorFlow【387320105798078†L55-L83】 or PyTorch【966743948575414†L14-L29】 for deep learning models.
* **Monitoring and alerting** – Add Prometheus scrape targets and Grafana dashboards【733729005149423†L16-L50】【957201044962566†L1657-L1662】.  Centralise logs with the ELK stack【190494098481125†L59-L82】【32038916605934†L294-L308】.

We hope this project helps you explore open‑source tools to build sophisticated financial analytics while maintaining complete control over your infrastructure.
