# Backend Retail GenAI

Backend for retail e-commerce, featuring semantic product search, LLM-powered recommendations, and dynamic attribute filtering.

## 🚀 Features
- **Semantic Search**: Vector-based search using ChromaDB and Sentence Transformers.
- **AI Recommendations**: Structured logic using Groq LLMs for personalized insights.
- **Clean Architecture**: Decoupled layers for API, Services, Infrastructure, and Agents.
- **Dynamic Filtering**: Category-specific attribute filtering (color, size, price range).
- **FastAPI Entrypoint**: Modern, high-performance API with robust validation.

---

## 🛠️ Installation

### 1. Clone the Repository
```bash
git clone <repository-url>
cd Backend_Retail_GenAI_v1
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## ⚙️ Configuration

1. Copy the sample environment file:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` and fill in your API keys (Groq is required for AI features).

### `.env` Key Variables:
- `GROQ_API_KEY`: Your key from console.groq.com.
- `DATABASE_URL`: Your SQLAlchemy connection string (e.g., SQLite or PostgreSQL).
- `CHROMA_DB_DIR`: Path to the vector database folder.

---

## 🏃 Running the Application

Start the development server:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level info
```

The API will be available at: `http://127.0.0.1:8000`
Swagger Documentation: `http://127.0.0.1:8000/docs`

---

## 📂 Project Structure
- **`app/main.py`**: FastAPI application entrypoint.
- **`src/interfaces/api/`**: API endpoints and schemas.
- **`src/application/services/`**: Orchestration logic (Search, Recommendations).
- **`src/infrastructure/`**: Database and LLM integrations.
- **`src/agents/`**: Conversational agent tools and logic.
- **`data/`**: Storage for product catalog and vector indexes.

---


