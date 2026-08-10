# backend/config/config.py

import os
from dotenv import load_dotenv

# Build the exact path to the project root .env file
# We search both in the parent project root folder and in backend/
config_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(config_dir)
root_dir = os.path.dirname(backend_dir)

env_path = os.path.join(root_dir, ".env")
if not os.path.exists(env_path):
    env_path = os.path.join(backend_dir, ".env")

# Load environment variables
load_dotenv(env_path)

# Check for either naming convention to prevent NoneType errors
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
NGROK_AUTH_TOKEN = os.getenv("NGROK_AUTH_TOKEN")
NGROK_DOMAIN = os.getenv("NGROK_DOMAIN")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "your_google_client_id_here")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "llm_provider")  # gemini_provider or llm_provider

# Qdrant Vector Database configurations
QDRANT_MODE = os.getenv("QDRANT_MODE", "local").lower().strip()
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_HOST = os.getenv("QDRANT_HOST")
QDRANT_PORT = os.getenv("QDRANT_PORT")

# LangGraph Multi-Agent Engine toggle (true = Compiled StateGraph, false = Procedural Pipeline)
USE_LANGGRAPH_ENGINE = os.getenv("USE_LANGGRAPH_ENGINE", "true").lower().strip() in ("true", "1", "yes")

