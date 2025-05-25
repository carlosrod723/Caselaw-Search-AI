# app/core/config.py
import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Load values from .env file
load_dotenv()


class Settings(BaseSettings):
    # ────────────────────────  API  ────────────────────────
    API_V1_STR:   str = "/api/v1"
    PROJECT_NAME: str = "Praxis"

    # ────────────────────  Qdrant / Networking  ────────────────────
    QDRANT_HOST: str  = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT: int  = int(os.getenv("QDRANT_PORT", "6333"))
    QDRANT_HTTPS: bool = bool(int(os.getenv("QDRANT_HTTPS", "0")))   # 0 → HTTP, 1 → HTTPS

    # Fine‑tuned timeouts (seconds)
    QDRANT_CONNECT_TIMEOUT: int = int(os.getenv("QDRANT_CONNECT_TIMEOUT", "5"))
    QDRANT_READ_TIMEOUT:    int = int(os.getenv("QDRANT_READ_TIMEOUT", "20"))

    # Collection name used by the backend
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "caselaw_bge_base_v2")

    # ────────────────────────  OpenAI  ────────────────────────
    OPENAI_API_KEY:         str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_EMBEDDING_MODEL: str = os.getenv("OPENAI_EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")
    OPENAI_COMPLETION_MODEL: str = os.getenv("OPENAI_COMPLETION_MODEL", "gpt-3.5-turbo")

    # ────────────────────────  Vectors  ────────────────────────
    VECTOR_DIMENSION: int = 768  # BGE‑base‑en‑v1.5 dimension
    
    # ────────────────────────  Database  ────────────────────────
    # Path to SQLite database for fast filtering
    SQLITE_DB_PATH: str = os.getenv(
        "SQLITE_DB_PATH", 
        "./case_lookup.db" 
    )
    
    # Directory containing parquet files with full case text
    PARQUET_DIR: str = os.getenv(
        "PARQUET_DIR",
        "/Users/josecarlosrodriguez/Desktop/Carlos-Projects/Qdrant-Test/caselaw_processing/downloads/datasets--laion--Caselaw_Access_Project_embeddings/snapshots/7777999929157e8a2fe1b5d65f1d9cfd2092e843/TeraflopAI___Caselaw_Access_Project_clusters"
    )

    class Config:
        case_sensitive = True


# Importable settings instance
settings = Settings()