import os
import json
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
#import google.generativeai as genai
from groq import Groq
from groq import APIConnectionError, RateLimitError, InternalServerError
import time
import re

# =========================================================
# LOAD ENV
# =========================================================
try:
   load_dotenv()
except Exception as e:
   raise RuntimeError(f"❌ Failed to load .env file: {e}")

try:
   DB_DIR = os.path.abspath(os.getenv("CHROMA_DB_DIR"))
   COLLECTION_NAME = os.getenv("COLLECTION_NAME")
   EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")

   if not DB_DIR or not COLLECTION_NAME or not EMBEDDING_MODEL:
       raise ValueError("Missing required env variables")
except Exception as e:
   raise RuntimeError(f"❌ ENV configuration error: {e}")

#USER_QUERY = "give me maroon party dresses under 5K for girls"

USER_QUERY = input("🔍 Enter your search query: ").strip()

if not USER_QUERY:
   raise ValueError("❌ User query cannot be empty")

print("🗄️ DB dir:", DB_DIR)
print("📦 Collection:", COLLECTION_NAME)
print("🧠 Embedding model:", EMBEDDING_MODEL)

# =========================================================
# EMBEDDING FUNCTION
# =========================================================
try:
   embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
       model_name=EMBEDDING_MODEL
   )
except Exception as e:
   raise RuntimeError(f"❌ Failed to initialize embedding model: {e}")

# =========================================================
# CHROMA CLIENT
# =========================================================
try:
   client = chromadb.PersistentClient(path=DB_DIR)

   collection = client.get_or_create_collection(
       name=COLLECTION_NAME,
       embedding_function=embedding_function
   )

   print("Collections:", [c.name for c in client.list_collections()])
   print("Total vectors:", collection.count())

except Exception as e:
   raise RuntimeError(f"❌ ChromaDB initialization failed: {e}")


# ----------------------------
# Verify (Read Sample)
# ----------------------------
# sample = collection.get(limit=3)

# for i in range(len(sample["ids"])):
#     print("\n--- Sample Record", i + 1, "---")
#     print("ID:", sample["ids"][i])
#     print("Document:", sample["documents"][i])
#     print("Metadata:", sample["metadatas"][i])

# exit()

# =========================================================
# NORMALIZATION (MUST MATCH INGEST)
# =========================================================
def normalize_filter_value(val):
   if isinstance(val, str):
       return val.strip().lower()
   return val

# =========================================================
# 1️⃣ QUERY REWRITE (LLM)
# =========================================================
def rewrite_query_llm(user_query: str) -> str:
   """
   Replace this with Groq / Ollama / OpenAI call
   """

   # ---- Prompt ----
   prompt = f"""
Rewrite the user query to be concise and optimized for semantic search.
Preserve meaning. Do not add new attributes.

User query:
{user_query}
"""

   # ---- MOCK LLM OUTPUT (replace later) ----
   rewritten_query = user_query #"yellow party wear dresses for girls under 2000 INR"

   return rewritten_query.strip()


# =========================================================
# 2️⃣ ATTRIBUTE EXTRACTION (LLM)
# =========================================================

# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# GEMINI_MODEL = os.getenv("GEMINI_MODEL")

# if not GEMINI_API_KEY:
#     raise ValueError("❌ GEMINI_API_KEY not found in .env")

# if not GEMINI_MODEL:
#     raise ValueError("❌ GEMINI_MODEL not found in .env")

# genai.configure(api_key=GEMINI_API_KEY)

# def extract_attributes_llm(user_query: str) -> dict:
#     """
#     Extract attributes from user query for Chroma where filter.
#     Prompt is loaded from ENV.
#     Output is guaranteed lowercase + valid JSON.
#     """

#     prompt_template = os.getenv("EXTRACT_ATTRIBUTES_SYSTEM_PROMPT")
#     if not prompt_template:
#         raise ValueError("❌ EXTRACT_ATTRIBUTES_SYSTEM_PROMPT not found in .env")

#     prompt = prompt_template.format(user_query=user_query)

#     model = genai.GenerativeModel(model_name=GEMINI_MODEL)

#     response = model.generate_content(
#         prompt,
#         generation_config={
#             "temperature": 0,
#             "max_output_tokens": 256
#         }
#     )

#     raw_output = response.text.strip()
#     print(raw_output)
#     return safe_json_loads(raw_output)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

def extract_attributes_llm(user_query: str) -> dict:
   prompt_template = os.getenv("EXTRACT_ATTRIBUTES_SYSTEM_PROMPT")
   if not prompt_template:
       raise ValueError("EXTRACT_ATTRIBUTES_SYSTEM_PROMPT not found")

   max_retries = 3
   sleep_seconds = 3
   last_error = None

   for attempt in range(1, max_retries + 1):
       try:
           response = client.chat.completions.create(
               model=GROQ_MODEL,
               temperature=0,
               messages=[
                   {"role": "system", "content": prompt_template},
                   {"role": "user", "content": user_query}
               ]
           )

           raw = response.choices[0].message.content.strip()
           return json.loads(raw)

       # 🔁 Retry-safe Groq errors
       except (APIConnectionError, RateLimitError, InternalServerError) as e:
           last_error = e
           print(f"[Retry {attempt}/{max_retries}] Groq error: {e}")

           if attempt < max_retries:
               time.sleep(sleep_seconds)
           else:
               break

       # 🚫 Prompt / model bug → NO retry
       except json.JSONDecodeError:
           raise ValueError(f"Invalid JSON returned:\n{raw}")

       # 🚫 Any other error → fail fast
       except Exception as e:
           raise RuntimeError(f"Unexpected error: {e}")

   raise RuntimeError(
       f"Groq API failed after {max_retries} attempts: {last_error}"
   )

   # try:
   #     filters = json.loads(raw_output)
   # except json.JSONDecodeError:
   #     raise ValueError(
   #         f"❌ Gemini returned invalid JSON:\n{raw_output}"
   #     )

   # return filters

   # ---- MOCK LLM OUTPUT (replace later) ----
   # llm_response = """
   # {
   # "color": "Maroon",
   # "occasion": "Party",
   # "gender": "girls",
   # "price": { "$lte": 5000 }
   # }
   # """

   # return json.loads(llm_response)



def is_truncated(text: str) -> bool:
   return text.count("{") != text.count("}")

def safe_json_loads(text: str) -> dict:
   """
   Safely extract JSON from Gemini output.
   Handles markdown fences, extra text, and whitespace.
   """

   # 1️⃣ Remove markdown code fences
   text = text.strip()

   if text.startswith("```"):
       text = re.sub(r"^```(?:json)?", "", text)
       text = re.sub(r"```$", "", text)
       text = text.strip()

   # 2️⃣ Try direct JSON parse
   try:
       return json.loads(text)
   except json.JSONDecodeError:
       pass

   # 3️⃣ Extract JSON object between first { and last }
   match = re.search(r"\{.*\}", text, re.DOTALL)
   if not match:
       raise ValueError("❌ No JSON object found in Gemini response")

   json_str = match.group()

   try:
       return json.loads(json_str)
   except json.JSONDecodeError as e:
       raise ValueError(f"❌ Gemini returned invalid JSON:\n{json_str}") from e


# =========================================================
# RUN LLM PIPELINE
# =========================================================
rewritten_query = rewrite_query_llm(USER_QUERY)
raw_filters = extract_attributes_llm(USER_QUERY)
print("🎯 LLM filters:", raw_filters)

# Convert flat filters → Chroma-compatible $and filter
filters = []

for key, value in raw_filters.items():
   if value is None:
       continue  # 🚫 skip null filters

   # ---------------- AGE HANDLING ----------------
   if key == "age":
       # Range case: 3–4
       if "$gte" in value and "$lte" in value:
           min_age = value["$gte"]
           max_age = value["$lte"]

           # filters.append({ "age_min": { "$lte": max_age } })
           # filters.append({ "age_max": { "$gte": min_age } })

           filters.append({ "age_max": { "$lte": max_age } })
           filters.append({ "age_min": { "$gte": min_age } })

       # Single age: 6
       elif "$eq" in value:
           age = value["$eq"]

           filters.append({ "age_min": { "$lte": age } })
           filters.append({ "age_max": { "$gte": age } })

       # Less than
       elif "$lt" in value:
           filters.append({ "age_min": { "$lt": value["$lt"] } })

       # Greater than
       elif "$gt" in value:
           filters.append({ "age_max": { "$gt": value["$gt"] } })

       continue

   if isinstance(value, dict):  # range filters
       for op, num in value.items():
           filters.append({key: {op: num}})
   else:
       filters.append({key: normalize_filter_value(value)})

# 🔒 Build final Chroma where clause
if not filters:
   where_filter = {}          # or None
elif len(filters) == 1:
   where_filter = filters[0] # 👈 single filter → NO $and
else:
   where_filter = {"$and": filters}

print("\n🔁 Rewritten Query:", rewritten_query)
print("🎯 Final Chroma Filter:", json.dumps(where_filter, indent=2))

# =========================================================
# 3️⃣ VECTOR SEARCH + METADATA FILTER
# =========================================================
try:
   results = collection.query(
       query_texts=[rewritten_query],
       n_results=5,
       where=where_filter
   )
except Exception as e:
   raise RuntimeError(f"❌ Chroma query failed: {e}")

# =========================================================
# 4️⃣ DISPLAY RESULTS
# =========================================================
try:
   if not results.get("documents") or not results["documents"][0]:
       print("\n❌ No results found")
   else:
       for i, doc in enumerate(results["documents"][0]):
           print(f"\n✅ Result {i+1}")
           print("Document:", doc)
           print("Metadata:", results["metadatas"][0][i])
except Exception as e:
   print(f"⚠️ Error displaying results: {e}")