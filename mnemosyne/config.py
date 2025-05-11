import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "your_password")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your_openai_api_key")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4-turbo")

DATA_FOLDER = os.getenv("DATA_FOLDER", "./data")