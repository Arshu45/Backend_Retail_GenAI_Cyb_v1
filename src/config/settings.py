"""Application configuration using Pydantic Settings."""

import os
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database Configuration
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/ecommerce_db",
        description="PostgreSQL database connection URL"
    )
    
    # ChromaDB Configuration
    chroma_db_dir: str = Field(
        default="./data/vector_db/chroma_db_ingest_few",
        description="ChromaDB persistent storage directory"
    )
    collection_name: str = Field(
        default="product_catalog",
        description="ChromaDB collection name"
    )
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="Sentence transformer model for embeddings"
    )
    
    # LLM Configuration
    groq_api_key: str = Field(
        description="Groq API key for LLM"
    )
    groq_model: str = Field(
        default="llama-3.1-8b-instant",
        description="Groq model name"
    )
    
    # Agent Configuration
    agent_model: str = Field(
        default="llama-3.3-70b-versatile",
        description="Model for agent orchestration"
    )
    
    # System Prompts
    extract_attributes_system_prompt: str = Field(
        default="",
        description="System prompt for attribute extraction"
    )
    
    # API Configuration
    api_title: str = Field(
        default="E-commerce Product Search Agent API",
        description="API title"
    )
    api_version: str = Field(
        default="1.0.0",
        description="API version"
    )
    cors_origins: list[str] = Field(
        default=["*"],
        description="CORS allowed origins"
    )
    
    # Ingestion Configuration (optional fields from .env)

    csv_file_path: Optional[str] = Field(
        default="./data/catalog_corrected.csv",
        description="Path to CSV file for ingestion"
    )
    document_columns: Optional[str] = Field(
        default="title,embedding_text,keyword_tags",
        description="Comma-separated list of document columns"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "allow"  # Allow extra fields from .env that aren't defined


# Global settings instance
settings = Settings()
