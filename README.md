# Retail GenAI Chatbot

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
git clone https://bitbucket.cybage.com/scm/rga/poc1_virtual_shopping_bot.git

cd poc1_virtual_shopping_bot
```

### 2. Create Virtual Environment
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```
---

### 4. Configure the environment variables
1. Copy the sample environment file:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` and fill in your API keys (Groq is required for AI features).

### `.env` Key Variables:
- `CSV_FILE_PATH`: Path to the normalized CSV file to ingest into ChromaDB & use for attribute schema generation.
- `COLLECTION_NAME`: Name of the ChromaDB collection to create.
- `DB_NAME` : Your PostgreSQL Database name (Eg: ecommerce_db)
- `DB_USER` : Your PostgreSQL Database user (Eg: postgres)
- `DB_PASSWORD` : Your PostgreSQL password (Eg: postgres)
- `DB_HOST` : Your PostgreSQL Database hostname (Eg: localhost)
- `DB_PORT` : Default Port Number on which PostgreSQL is running (Eg: 5432)
- `GROQ_API_KEY` : Your key from console.groq.com.
- `DATABASE_URL` : Your SQLAlchemy connection string (e.g., PostgreSQL).
- `CHROMA_DB_DIR` : Path to the ChromaDB vector database folder.
- `SCHEMA_DIR` : Path to the directory that contains attribute schema generated files.
- `FOLLOWUP_EXCLUDE_ATTRIBUTES` : Attributes to exclude from follow-up questions prompt(comma-separated)
- `EXCLUDED_ATTR_EXTRACTION_FIELDS` : Attributes to exclude from attribute extraction(comma-separated)
- `EXCLUDED_FINAL_ANS_FIELDS` : Attributes to exclude from final answer(comma-separated)
- `DEFAULT_KEY_FEATURES` : Default key features(comma-separated)
- `MAX_KEY_FEATURES` : Maximum number of key features
- `EXCLUDED_KEY_FEATURES` : Attributes to exclude from key features(comma-separated)

---

### 5. ( Mandatory Step ) Run the data processing pipeline.
Refer the Readme.md in the `scripts/pipeline` directory for data processing pipeline.



## Running the Application

Start the development server:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level info
```

The API will be available at: `http://localhost:8000`

Swagger Documentation: `http://localhost:8000/docs`

---

## 📂 Project Structure
- **`app/main.py`**: FastAPI application entrypoint.
- **`src/interfaces/api/`**: API endpoints and schemas.
- **`src/application/services/`**: Orchestration logic (Search, Recommendations).
- **`src/infrastructure/`**: Database and LLM integrations.
- **`src/agents/`**: Conversational agent tools and logic.
- **`data/`**: Storage for product catalog and vector indexes.

---


