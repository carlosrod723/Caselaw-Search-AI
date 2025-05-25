# app/services/openai_service.py
"""
OpenAI service wrapper for embeddings, query refinement, and async summaries.

Features:
- Local embedding with Sentence-Transformer or OpenAI API
- Normalized 768-dimension embeddings for Qdrant compatibility
- LRU caching to avoid redundant embedding generation
- Automatic retry for transient errors and rate limits
- Concurrent summarization with controlled concurrency
- Thread-safe performance monitoring
"""

from __future__ import annotations

import asyncio
import functools
import logging
import threading
import time
from collections import Counter
from typing import List, Sequence

import numpy as np
import openai as openai_mod  # For typed exception aliases
from openai import AsyncOpenAI, OpenAI
from openai.types.chat import ChatCompletion
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings

logger = logging.getLogger(__name__)


# Configuration constants
EMBEDDING_TIMEOUT = 15.0
COMPLETION_TIMEOUT = 30.0

OPENAI_EMBED_MODEL = "text-embedding-3-small"  # 1536-d will be truncated to 768-d
OPENAI_CHAT_MODEL = "gpt-4o-mini"

DEFAULT_PROVIDER = "local"  # "local" | "openai"
LOCAL_MODEL_NAME = "BAAI/bge-base-en-v1.5"


# Utility functions
def _fit_to_768(vec: Sequence[float]) -> tuple[float, ...]:
    """Ensure vector is exactly 768 dimensions by truncating or zero-padding."""
    if len(vec) > 768:
        vec = vec[:768]
    elif len(vec) < 768:
        vec = list(vec) + [0.0] * (768 - len(vec))
    return tuple(vec)


# Shared retry policy for API calls
_retry_policy = dict(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(4),
    retry=retry_if_exception_type(
        (
            TimeoutError,
            ConnectionError,
            openai_mod.APIConnectionError,
            openai_mod.APITimeoutError,
            openai_mod.RateLimitError,
        )
    ),
    reraise=True,
)


class OpenAIService:
    """
    Service for text embeddings, query refinement, and summarization.
    Supports both local models and OpenAI API with automatic fallback.
    """

    def __init__(self) -> None:
        """Initialize the OpenAI service with appropriate clients and models."""
        # Thread-safe performance counters
        self._lock = threading.Lock()
        self._stats = Counter(
            embedding_calls=0,
            embedding_time_total=0.0,
            refine_calls=0,
            refine_time_total=0.0,
            summarize_calls=0,
            summarize_time_total=0.0,
        )

        # Initialize API clients
        self.embedding_client = OpenAI(
            api_key=settings.OPENAI_API_KEY, 
            timeout=EMBEDDING_TIMEOUT
        )
        
        self.chat_client = OpenAI(
            api_key=settings.OPENAI_API_KEY, 
            timeout=COMPLETION_TIMEOUT
        )
        
        self.async_chat_client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY, 
            timeout=COMPLETION_TIMEOUT
        )
        
        # Make model constants accessible as instance variables
        self.OPENAI_EMBED_MODEL = OPENAI_EMBED_MODEL
        self.OPENAI_CHAT_MODEL = OPENAI_CHAT_MODEL

        # Set embedding provider configuration
        self.embedding_provider = getattr(
            settings, "EMBEDDING_PROVIDER", DEFAULT_PROVIDER
        ).lower()
        
        self.local_model_name = getattr(
            settings, "LOCAL_EMBEDDING_MODEL_NAME", LOCAL_MODEL_NAME
        )

        # Initialize local model if using local embeddings
        if self.embedding_provider == "local":
            from sentence_transformers import SentenceTransformer
            
            logger.info(f"Loading local embedding model: {self.local_model_name}")
            self._local_model = SentenceTransformer(self.local_model_name)

    def _inc(self, key: str, value: int | float = 1) -> None:
        """Thread-safe increment of performance counters."""
        with self._lock:
            self._stats[key] += value

    @functools.lru_cache(maxsize=512)
    def _openai_embed_cached(self, text: str) -> tuple[float, ...]:
        """Generate embeddings using OpenAI API with caching."""
        resp = self.embedding_client.embeddings.create(
            input=text, model=OPENAI_EMBED_MODEL
        )
        raw_vec = resp.data[0].embedding
        return _fit_to_768(raw_vec)

    @functools.lru_cache(maxsize=512)
    def _local_embed_cached(self, text: str) -> tuple[float, ...]:
        """Generate embeddings using local model with caching."""
        raw_vec = self._local_model.encode(text)
        return _fit_to_768(raw_vec)

    @retry(**_retry_policy)
    def get_embedding(self, text: str) -> List[float]:
        """
        Generate a 768-dimension embedding vector for the given text.
        Uses either local model or OpenAI API based on configuration.
        
        Args:
            text: The text to embed
            
        Returns:
            A list of 768 float values representing the embedding
        """
        t0 = time.time()
        self._inc("embedding_calls")
        
        try:
            if self.embedding_provider == "local":
                vec = self._local_embed_cached(text)
            else:
                vec = self._openai_embed_cached(text)
            return list(vec)
        finally:
            self._inc("embedding_time_total", time.time() - t0)

    @retry(**_retry_policy)
    def refine_query(self, raw_query: str) -> str:
        """
        Rewrite a user query into a more effective search query.
        
        Args:
            raw_query: The original user query
            
        Returns:
            A refined query optimized for semantic search
        """
        t0 = time.time()
        self._inc("refine_calls")
        
        try:
            completion: ChatCompletion = self.chat_client.chat.completions.create(
                model=OPENAI_CHAT_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Rewrite the user's input into a concise, standalone query "
                            "for semantic search over U.S. caselaw."
                        ),
                    },
                    {"role": "user", "content": raw_query},
                ],
                max_tokens=32,
                temperature=0.2,
            )
            return completion.choices[0].message.content.strip()
        finally:
            self._inc("refine_time_total", time.time() - t0)

    def _summarize_sync(self, text: str) -> str:
        """
        Synchronous fallback for text summarization.
        
        Args:
            text: Text to summarize
            
        Returns:
            Summarized text or truncated original on error
        """
        try:
            completion = self.chat_client.chat.completions.create(
                model=OPENAI_CHAT_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Create a concise, plain-language summary of this court "
                            "opinion."
                        ),
                    },
                    {"role": "user", "content": text},
                ],
                max_tokens=100,
                temperature=0.3,
            )
            return completion.choices[0].message.content.strip()
        except Exception:
            # Fallback to a simple truncation if summarization fails
            return text[:150] + "…"

    async def summarize_text_async(self, text: str) -> str:
        """
        Asynchronously summarize a single text.
        
        Args:
            text: Text to summarize
            
        Returns:
            Summarized text, or original if already short
        """
        if len(text) < 120:
            return text  # Already brief enough
    
        completion = await self.async_chat_client.chat.completions.create(
            model=OPENAI_CHAT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Create a concise, plain-language summary of this court "
                        "opinion."
                    ),
                },
                {"role": "user", "content": text},
            ],
            max_tokens=100,
            temperature=0.3,
        )
        return completion.choices[0].message.content.strip()

    async def summarize_many(
        self, texts: List[str], concurrency: int = 8
    ) -> List[str]:
        """
        Summarize multiple texts concurrently with controlled concurrency.
        
        Args:
            texts: List of texts to summarize
            concurrency: Maximum number of concurrent summarizations
            
        Returns:
            List of summarized texts in the same order
        """
        t0 = time.time()
        self._inc("summarize_calls")
    
        # Limit concurrent API calls
        sem = asyncio.Semaphore(concurrency)
    
        async def _one(t: str) -> str:
            async with sem:
                try:
                    return await self.summarize_text_async(t)
                except Exception:
                    # Fallback to sync version in executor
                    loop = asyncio.get_running_loop()
                    return await loop.run_in_executor(None, self._summarize_sync, t)
    
        results = await asyncio.gather(*(_one(tx) for tx in texts))
        self._inc("summarize_time_total", time.time() - t0)
        return results

    def get_performance_stats(self) -> dict:
        """
        Get performance statistics for monitoring and debugging.
        
        Returns:
            Dictionary with call counts and average times
        """
        with self._lock:
            stats = dict(self._stats)
    
        # Calculate average times
        def _avg(total: str, count: str) -> float:
            n = stats.get(count, 0)
            return round(stats.get(total, 0.0) / n, 4) if n else 0.0
    
        stats["embedding_avg_time"] = _avg("embedding_time_total", "embedding_calls")
        stats["refine_avg_time"] = _avg("refine_time_total", "refine_calls")
        stats["summarize_avg_time"] = _avg("summarize_time_total", "summarize_calls")
        return stats

# Back-compat exception aliases
class OpenAITimeoutError(openai_mod.APITimeoutError):
    """Alias for OpenAI timeout errors to avoid direct SDK imports."""
    pass

class OpenAIRateLimitError(openai_mod.RateLimitError):
    """Alias for OpenAI rate limit errors to avoid direct SDK imports."""
    pass

# Module-level singleton for application-wide use
openai_service = OpenAIService()