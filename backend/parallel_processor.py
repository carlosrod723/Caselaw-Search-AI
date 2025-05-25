# parallel_processor.py - Process Caselaw dataset with local embedding generation
# Optimized for Apple Silicon (M4 Max) with high performance embedding generation

import os
import time
import uuid
import json
import pickle
import logging
import threading
import multiprocessing
import random
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
import numpy as np
import pyarrow.parquet as pq
from dotenv import load_dotenv
from huggingface_hub import list_repo_files, hf_hub_download
import tiktoken
import tqdm
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from sentence_transformers import SentenceTransformer

# --- Configuration ---
load_dotenv()  # Load .env from project root

# --- Path Configuration ---
BASE_DIR = Path("./caselaw_processing")
DOWNLOAD_DIR = BASE_DIR / "downloads"
OUTPUT_DIR = BASE_DIR / "processed_embeddings"
LOGS_DIR = BASE_DIR / "logs"
TEMP_DIR = BASE_DIR / "temp"
MODEL_DIR = BASE_DIR / "models"  # Directory to store downloaded models

# --- Dataset Information ---
REPO_ID = "laion/Caselaw_Access_Project_embeddings"
CLUSTER_PREFIX = "TeraflopAI___Caselaw_Access_Project_clusters/"

# --- Embedding Model Configuration ---
EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"  # We'll use this same model locally
VECTOR_DIM = 768
USE_GPU = True  # Set to True to use GPU acceleration if available
BATCH_SIZE_EMBEDDING = 8  # Batching for the embedding model

# --- Token Limit Configuration ---
MAX_SAFE_TOKENS = 512  # SentenceTransformers typically handles ~512 tokens
MAX_TOKEN_ATTEMPTS = 3  # Number of times to try reducing tokens before giving up
TOKEN_REDUCTION_FACTOR = 0.8  # How much to reduce by on each attempt
TOKENIZER = tiktoken.get_encoding("cl100k_base")

# --- Parallelism Configuration ---
CPU_COUNT = multiprocessing.cpu_count()
NUM_WORKERS = max(1, min(CPU_COUNT - 2, 8))  # Save some cores for system, but max 8 workers
MAX_CONCURRENT_DOWNLOADS = 2  # Maximum concurrent downloads

# --- Processing Parameters ---
BATCH_SIZE = 1000  # Points per batch saved to disk (increased for local processing)
MAX_RETRIES = 3  # Retries for embedding generation

# --- Payload Configuration ---
PAYLOAD_FIELD_MAPPING = {
    "name_abbreviation": "title",
    "decision_date": "date",
    "citations": "citations", 
    "court": "court",
    "jurisdiction": "jurisdiction",
    "volume": "volume",
    "reporter": "reporter",
    "first_page": "page_first",
    "id": "case_id",
    "cid": "original_cid"
}
TEXT_FIELD = "text"
SNIPPET_LENGTH = 300

# --- Qdrant Configuration ---
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "caselaw")
USE_DIRECT_QDRANT = os.getenv("USE_DIRECT_QDRANT", "False").lower() in ("true", "1", "t")

# --- Create directory structure ---
for directory in [DOWNLOAD_DIR, OUTPUT_DIR, LOGS_DIR, TEMP_DIR, MODEL_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# --- Setup Logging ---
log_file_path = LOGS_DIR / f"parallel_processor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file_path),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("parallel_processor")
logger.info(f"Local embedding parallel processing started with {NUM_WORKERS} workers")
logger.info(f"Logs will be saved to {log_file_path}")

# --- Global tracking variables ---
download_semaphore = threading.Semaphore(MAX_CONCURRENT_DOWNLOADS)
embedding_model_lock = threading.Lock()  # Lock for accessing the embedding model
global_stats = {
    "files_total": 0,
    "files_processed": 0,
    "records_processed": 0,
    "records_skipped": 0,
    "embedding_failures": 0,
    "batches_saved": 0,
    "start_time": time.time(),
    "processing_times": [],  # List of (records, seconds) tuples
    "files_in_progress": set(),  # Set of files currently being processed
}
stats_lock = threading.Lock()

# --- Embedding model cache (shared between processes) ---
# Note: Each process will load its own model instance
embedding_models = {}

# --- Helper Functions ---
def count_tokens(text: str) -> int:
    """Count the number of tokens in text using the tokenizer."""
    if not text:
        return 0
    try:
        tokens = TOKENIZER.encode(text)
        return len(tokens)
    except Exception:
        # Fallback estimation if tokenizer fails
        return len(text) // 4  # Rough estimate

def truncate_to_token_limit(text: str, max_tokens: int = MAX_SAFE_TOKENS) -> str:
    """Truncate text to stay within the token limit."""
    if not text:
        return ""
    
    try:
        tokens = TOKENIZER.encode(text)
        if len(tokens) > max_tokens:
            return TOKENIZER.decode(tokens[:max_tokens])
        return text
    except Exception:
        # Fallback if tokenizer fails
        char_estimate = max_tokens * 4  # Rough estimate
        return text[:char_estimate]

def adaptive_token_truncation(text: str, worker_id: int) -> Optional[str]:
    """Adaptively truncate text to fit within token limits, with multiple attempts."""
    if not text:
        return None
    
    worker_logger = logging.getLogger(f"worker_{worker_id}")
    current_text = text
    current_limit = MAX_SAFE_TOKENS
    
    for attempt in range(MAX_TOKEN_ATTEMPTS):
        try:
            # Truncate to current limit
            truncated = truncate_to_token_limit(current_text, current_limit)
            token_count = count_tokens(truncated)
            
            if token_count <= current_limit:
                if attempt > 0:
                    worker_logger.info(f"Successfully truncated text to {token_count} tokens after {attempt+1} attempts")
                return truncated
            
            # If still too long, reduce limit further
            current_limit = int(current_limit * TOKEN_REDUCTION_FACTOR)
            worker_logger.warning(f"Text still too long ({token_count} tokens). Reducing to {current_limit} tokens.")
        
        except Exception as e:
            worker_logger.error(f"Error during token truncation: {e}")
            current_limit = int(current_limit * TOKEN_REDUCTION_FACTOR)
    
    # If we get here, we failed to truncate sufficiently
    worker_logger.warning(f"Failed to truncate text after {MAX_TOKEN_ATTEMPTS} attempts. Skipping.")
    return None

def get_embedding_model(worker_id: int) -> SentenceTransformer:
    """Get or create an instance of the embedding model for this worker."""
    worker_logger = logging.getLogger(f"worker_{worker_id}")
    
    # Each process needs its own model instance
    process_id = os.getpid()
    if process_id not in embedding_models:
        worker_logger.info(f"Loading embedding model {EMBEDDING_MODEL} for worker {worker_id}")
        model_kwargs = {}
        
        # Configure device based on availability and settings
        if USE_GPU:
            try:
                import torch
                if torch.backends.mps.is_available():  # Apple Silicon GPU
                    device = "mps"
                    worker_logger.info(f"Using Apple Silicon GPU (MPS) for embeddings")
                elif torch.cuda.is_available():  # NVIDIA GPU
                    device = "cuda"
                    worker_logger.info(f"Using CUDA GPU for embeddings")
                else:
                    device = "cpu"
                    worker_logger.info(f"No GPU available, using CPU for embeddings")
                model_kwargs["device"] = device
            except:
                worker_logger.warning("Could not check GPU availability, defaulting to CPU")
        
        # Load the model
        try:
            # Download to a specific directory to cache
            model = SentenceTransformer(EMBEDDING_MODEL, cache_folder=str(MODEL_DIR), **model_kwargs)
            embedding_models[process_id] = model
            worker_logger.info(f"Successfully loaded embedding model for worker {worker_id}")
        except Exception as e:
            worker_logger.error(f"Error loading embedding model: {e}")
            raise
    
    return embedding_models[process_id]

def generate_embeddings_locally(texts: List[str], worker_id: int) -> List[Optional[List[float]]]:
    """Generate embeddings locally using SentenceTransformers."""
    if not texts:
        return []
    
    worker_logger = logging.getLogger(f"worker_{worker_id}")
    
    # Filter out empty texts
    valid_texts = [(i, text) for i, text in enumerate(texts) if text and isinstance(text, str) and len(text.strip()) > 0]
    if not valid_texts:
        return [None] * len(texts)
    
    indices, valid_texts_only = zip(*valid_texts)
    
    # Get embeddings for valid texts
    results = [None] * len(texts)
    
    try:
        # Get the embedding model for this worker
        model = get_embedding_model(worker_id)
        
        # Process in batches to optimize memory usage
        valid_embeddings = []
        for i in range(0, len(valid_texts_only), BATCH_SIZE_EMBEDDING):
            batch_texts = valid_texts_only[i:i+BATCH_SIZE_EMBEDDING]
            
            # Apply token truncation to each text in the batch
            truncated_texts = []
            for text in batch_texts:
                truncated = adaptive_token_truncation(text, worker_id)
                if truncated:
                    truncated_texts.append(truncated)
                else:
                    truncated_texts.append("") # Empty placeholder for failed truncation
            
            # Generate embeddings for the batch
            batch_embeddings = model.encode(truncated_texts, show_progress_bar=False)
            valid_embeddings.extend(batch_embeddings)
        
        # Assign embeddings back to their original positions
        for idx, embed_idx in enumerate(indices):
            # Skip if the text was empty or had failed truncation
            if valid_embeddings[idx].shape[0] == VECTOR_DIM:  # Check dimension
                results[embed_idx] = valid_embeddings[idx].tolist()
    
    except Exception as e:
        worker_logger.error(f"Error generating embeddings: {e}")
        # Return None for all in case of error
        return [None] * len(texts)
    
    return results

def download_parquet_file(file_path: str, worker_id: int) -> Optional[str]:
    """Download a parquet file with concurrency control."""
    worker_logger = logging.getLogger(f"worker_{worker_id}")
    
    # Mark file as in progress
    with stats_lock:
        global_stats["files_in_progress"].add(file_path)
    
    with download_semaphore:
        try:
            local_path = hf_hub_download(
                repo_id=REPO_ID,
                filename=file_path,
                repo_type="dataset",
                cache_dir=DOWNLOAD_DIR,
                resume_download=True
            )
            return local_path
        except Exception as e:
            worker_logger.error(f"Error downloading file {file_path}: {e}")
            # Remove from in-progress set
            with stats_lock:
                global_stats["files_in_progress"].discard(file_path)
            return None

def get_highest_batch_number(worker_id: int) -> int:
    """Find the highest existing batch number for a worker."""
    worker_dir = OUTPUT_DIR / f"worker_{worker_id}"
    if not worker_dir.exists():
        return 0
    
    # Find all batch files for this worker
    batch_files = list(worker_dir.glob(f"batch_{worker_id}_*.pkl"))
    if not batch_files:
        return 0
    
    # Extract batch numbers from filenames
    batch_numbers = []
    for batch_file in batch_files:
        try:
            # Format is batch_{worker_id}_{batch_number}.pkl
            batch_number = int(batch_file.stem.split('_')[-1])
            batch_numbers.append(batch_number)
        except (ValueError, IndexError):
            continue
    
    # Return highest batch number found, or 0 if none found
    return max(batch_numbers) + 1 if batch_numbers else 0

def save_batch(points: List[Dict[str, Any]], batch_id: str, worker_id: int) -> bool:
    """Save a batch of processed points to disk."""
    if not points:
        return True
    
    worker_logger = logging.getLogger(f"worker_{worker_id}")
    
    try:
        # Create a structured batch file
        batch_data = {
            "points": points,
            "metadata": {
                "batch_id": batch_id,
                "worker_id": worker_id,
                "timestamp": datetime.now().isoformat(),
                "count": len(points),
                "version": "1.0"
            }
        }
        
        # Ensure output directory exists
        worker_output_dir = OUTPUT_DIR / f"worker_{worker_id}"
        worker_output_dir.mkdir(exist_ok=True)
        
        # Save the batch
        output_file = worker_output_dir / f"batch_{batch_id}.pkl"
        with open(output_file, 'wb') as f:
            pickle.dump(batch_data, f)
        
        # Save a small sample in JSON for inspection (first batch only)
        if batch_id.endswith("_000000"):
            sample_file = worker_output_dir / f"sample_{batch_id}.json"
            with open(sample_file, 'w') as f:
                sample_data = {
                    "metadata": batch_data["metadata"],
                    "sample_points": [
                        {
                            "id": p["id"],
                            "vector_length": len(p["vector"]),
                            "vector_sample": p["vector"][:5],
                            "payload": p["payload"]
                        } 
                        for p in points[:3]  # Just first 3 points
                    ]
                }
                json.dump(sample_data, f, indent=2)
        
        # Update stats
        with stats_lock:
            global_stats["batches_saved"] += 1
        
        worker_logger.debug(f"Saved batch {batch_id} with {len(points)} points")
        return True
    
    except Exception as e:
        worker_logger.error(f"Error saving batch {batch_id}: {e}")
        return False

def upsert_to_qdrant(points: List[Dict[str, Any]], worker_id: int) -> bool:
    """Upsert points directly to Qdrant if enabled."""
    if not USE_DIRECT_QDRANT or not points:
        return False
    
    worker_logger = logging.getLogger(f"worker_{worker_id}")
    
    try:
        # Connect to Qdrant
        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        
        # Prepare points for Qdrant
        qdrant_points = [
            PointStruct(
                id=p["id"],
                vector=p["vector"],
                payload=p["payload"]
            )
            for p in points
        ]
        
        # Upsert in batches to avoid overwhelming Qdrant
        MAX_QDRANT_BATCH = 100
        for i in range(0, len(qdrant_points), MAX_QDRANT_BATCH):
            batch = qdrant_points[i:i+MAX_QDRANT_BATCH]
            client.upsert(
                collection_name=QDRANT_COLLECTION,
                points=batch
            )
            time.sleep(0.5)  # Small delay between batches
        
        worker_logger.info(f"Upserted {len(points)} points directly to Qdrant")
        return True
    
    except Exception as e:
        worker_logger.error(f"Error upserting to Qdrant: {e}")
        return False

def process_parquet_file(file_path: str, worker_id: int, batch_counter: int) -> Tuple[int, int, int, int]:
    """Process a single Parquet file, extracting data and generating embeddings."""
    worker_logger = logging.getLogger(f"worker_{worker_id}")
    worker_logger.info(f"Processing file: {file_path}")
    
    processed_count = 0
    skipped_count = 0
    embedding_failures = 0
    points_batch = []
    
    # Download file
    local_path = download_parquet_file(file_path, worker_id)
    if not local_path:
        worker_logger.error(f"Failed to download {file_path}. Skipping.")
        # Remove from in-progress
        with stats_lock:
            global_stats["files_in_progress"].discard(file_path)
        return 0, 0, 0, batch_counter
    
    try:
        # Process file
        start_time = time.time()
        parquet_file = pq.ParquetFile(local_path)
        total_rows = parquet_file.metadata.num_rows
        worker_logger.info(f"File contains {total_rows} rows in {parquet_file.metadata.num_row_groups} row groups")
        
        # Process in batches
        for batch_idx, batch in enumerate(parquet_file.iter_batches()):
            batch_start_time = time.time()
            data_dict = batch.to_pydict()
            rows_count = len(data_dict.get(TEXT_FIELD, []))
            
            worker_logger.info(f"Processing batch {batch_idx+1} with {rows_count} rows...")
            
            # Prepare batch of texts for embedding
            batch_texts = []
            batch_ids = []
            batch_payloads = []
            
            for i in range(rows_count):
                try:
                    # Extract text for embedding
                    if TEXT_FIELD not in data_dict or i >= len(data_dict[TEXT_FIELD]) or not data_dict[TEXT_FIELD][i]:
                        skipped_count += 1
                        continue
                    
                    text = data_dict[TEXT_FIELD][i]
                    
                    # Create payload with snippet
                    payload = {"snippet": text[:SNIPPET_LENGTH] if text else ""}
                    
                    # Extract other payload fields
                    for src_key, dst_key in PAYLOAD_FIELD_MAPPING.items():
                        if src_key in data_dict and i < len(data_dict[src_key]) and data_dict[src_key][i]:
                            payload[dst_key] = data_dict[src_key][i]
                    
                    # Get ID for point
                    id_field_value = None
                    if "id" in data_dict and i < len(data_dict["id"]) and data_dict["id"][i]:
                        id_field_value = str(data_dict["id"][i])
                    elif "cid" in data_dict and i < len(data_dict["cid"]) and data_dict["cid"][i]:
                        id_field_value = str(data_dict["cid"][i])
                    
                    if not id_field_value:
                        worker_logger.debug(f"Row {i}: Missing ID field. Using row index as fallback.")
                        id_field_value = f"{os.path.basename(file_path)}_{i}"
                    
                    # Create point ID
                    point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, id_field_value))
                    
                    # Add to embedding batch
                    batch_texts.append(text)
                    batch_ids.append(point_id)
                    batch_payloads.append(payload)
                    
                except Exception as e:
                    worker_logger.error(f"Error preparing row {i}: {e}")
                    skipped_count += 1
                    continue
            
            # Generate embeddings for the batch (more efficient than one by one)
            if batch_texts:
                worker_logger.info(f"Generating embeddings for {len(batch_texts)} texts")
                embeddings = generate_embeddings_locally(batch_texts, worker_id)
                
                # Create points with embeddings
                for idx, (point_id, payload, embedding) in enumerate(zip(batch_ids, batch_payloads, embeddings)):
                    if embedding:
                        points_batch.append({
                            "id": point_id,
                            "vector": embedding,
                            "payload": payload
                        })
                        processed_count += 1
                    else:
                        embedding_failures += 1
                        skipped_count += 1
            
            # Save batch when full
            if len(points_batch) >= BATCH_SIZE:
                batch_id = f"{worker_id}_{batch_counter:06d}"
                save_batch(points_batch, batch_id, worker_id)
                worker_logger.info(f"Saved batch {batch_id} with {len(points_batch)} points")
                
                # Also upsert to Qdrant if enabled
                if USE_DIRECT_QDRANT:
                    upsert_to_qdrant(points_batch, worker_id)
                
                points_batch = []
                batch_counter += 1
            
            # Log batch progress
            batch_time = time.time() - batch_start_time
            embedding_rate = len(batch_texts) / batch_time if batch_time > 0 and batch_texts else 0
            worker_logger.info(f"Processed batch {batch_idx} in {batch_time:.2f}s - Embedding rate: {embedding_rate:.2f} texts/sec - Running total: {processed_count} processed, {skipped_count} skipped")
        
        # Calculate processing stats
        elapsed_time = time.time() - start_time
        records_per_second = processed_count / elapsed_time if elapsed_time > 0 else 0
        
        worker_logger.info(f"Completed file {file_path} - Processed: {processed_count}, Skipped: {skipped_count}, Failures: {embedding_failures}")
        worker_logger.info(f"Processing rate: {records_per_second:.2f} records/second ({processed_count} in {elapsed_time:.2f}s)")
        
        # Update global stats
        with stats_lock:
            global_stats["files_processed"] += 1
            global_stats["records_processed"] += processed_count
            global_stats["records_skipped"] += skipped_count
            global_stats["embedding_failures"] += embedding_failures
            global_stats["processing_times"].append((processed_count, elapsed_time))
            global_stats["files_in_progress"].discard(file_path)
        
        # Save completion marker file for this file (for resumability)
        completion_marker = TEMP_DIR / "completed_files" / os.path.basename(file_path).replace(".parquet", ".done")
        os.makedirs(os.path.dirname(completion_marker), exist_ok=True)
        with open(completion_marker, 'w') as f:
            json.dump({
                "file": file_path,
                "processed": processed_count,
                "skipped": skipped_count,
                "failures": embedding_failures,
                "completed_at": datetime.now().isoformat()
            }, f)
        
        return processed_count, skipped_count, embedding_failures, batch_counter
        
    except Exception as e:
        worker_logger.error(f"Error processing file {file_path}: {e}")
        # Remove from in-progress
        with stats_lock:
            global_stats["files_in_progress"].discard(file_path)
        return 0, 0, 0, batch_counter

def worker_process(file_paths: List[str], worker_id: int) -> Dict[str, Any]:
    """Worker process that handles a set of files."""
    # Setup worker-specific logger
    worker_logger = logging.getLogger(f"worker_{worker_id}")
    worker_handler = logging.FileHandler(LOGS_DIR / f"worker_{worker_id}.log")
    worker_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s'))
    worker_logger.addHandler(worker_handler)
    
    worker_logger.info(f"Worker {worker_id} starting with {len(file_paths)} files to process")
    
    # Process each file
    worker_stats = {
        "worker_id": worker_id,
        "files_assigned": len(file_paths),
        "files_processed": 0,
        "files_failed": 0,
        "records_processed": 0,
        "records_skipped": 0,
        "embedding_failures": 0,
        "start_time": time.time()
    }
    
    # Initialize batch counter for this worker - check for existing batches
    batch_counter = get_highest_batch_number(worker_id)
    worker_logger.info(f"Starting with batch counter at {batch_counter} (continuing from existing batches)")
    
    for file_idx, file_path in enumerate(file_paths):
        worker_logger.info(f"Processing file {file_idx+1}/{len(file_paths)}: {file_path}")
        
        try:
            processed, skipped, failures, batch_counter = process_parquet_file(file_path, worker_id, batch_counter)
            
            worker_stats["files_processed"] += 1
            worker_stats["records_processed"] += processed
            worker_stats["records_skipped"] += skipped
            worker_stats["embedding_failures"] += failures
            
        except Exception as e:
            worker_logger.error(f"Error in worker process for file {file_path}: {e}")
            worker_stats["files_failed"] += 1
    
    worker_stats["elapsed_time"] = time.time() - worker_stats["start_time"]
    worker_logger.info(f"Worker {worker_id} finished. Processed {worker_stats['records_processed']} records in {worker_stats['elapsed_time']:.2f}s")
    
    return worker_stats

def initialize_qdrant():
    """Initialize Qdrant collection if enabled and if it doesn't exist."""
    global USE_DIRECT_QDRANT
    
    if not USE_DIRECT_QDRANT:
        return
    
    try:
        logger.info(f"Initializing Qdrant collection {QDRANT_COLLECTION} at {QDRANT_HOST}:{QDRANT_PORT}")
        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        
        # Check if collection exists
        collections = client.get_collections().collections
        collection_names = [collection.name for collection in collections]
        
        if QDRANT_COLLECTION not in collection_names:
            logger.info(f"Creating Qdrant collection {QDRANT_COLLECTION}")
            client.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=VectorParams(
                    size=VECTOR_DIM, 
                    distance=Distance.COSINE
                )
            )
            logger.info(f"Collection {QDRANT_COLLECTION} created successfully")
        else:
            logger.info(f"Collection {QDRANT_COLLECTION} already exists")
            
    except Exception as e:
        logger.error(f"Error initializing Qdrant: {e}")
        logger.info("Continuing with local storage only")
        USE_DIRECT_QDRANT = False

def get_parquet_files():
    """Get list of Parquet files to process."""
    try:
        # Check if we already have a list of files
        file_list_path = TEMP_DIR / "parquet_files.json"
        
        if file_list_path.exists():
            with open(file_list_path, 'r') as f:
                file_list = json.load(f)
                logger.info(f"Loaded file list with {len(file_list)} files from {file_list_path}")
                return file_list
        
        # List files from the dataset repo
        logger.info(f"Listing Parquet files in {REPO_ID} with prefix {CLUSTER_PREFIX}...")
        all_files = list_repo_files(
            repo_id=REPO_ID,
            repo_type="dataset"
        )
        
        # Filter for Parquet files with the right prefix
        parquet_files = [f for f in all_files if f.startswith(CLUSTER_PREFIX) and f.endswith(".parquet")]
        
        # Save file list for future runs
        with open(file_list_path, 'w') as f:
            json.dump(parquet_files, f)
        
        logger.info(f"Saved file list with {len(parquet_files)} files to {file_list_path}")
        return parquet_files
    
    except Exception as e:
        logger.error(f"Error getting Parquet files: {e}")
        return []

def get_previously_processed_files():
    """Get list of previously processed files."""
    completed_dir = TEMP_DIR / "completed_files"
    if not completed_dir.exists():
        return set()
    
    processed_files = set()
    for done_file in completed_dir.glob("*.done"):
        try:
            with open(done_file, 'r') as f:
                data = json.load(f)
                if data and "file" in data:
                    processed_files.add(data["file"])
        except Exception:
            pass
    
    return processed_files

def divide_work(files: List[str], num_workers: int) -> List[List[str]]:
    """Divide the files among workers in a balanced way."""
    if not files:
        return [[] for _ in range(num_workers)]
    
    # Sort files by name to ensure deterministic division
    sorted_files = sorted(files)
    
    # Divide files among workers
    chunks = [[] for _ in range(num_workers)]
    for i, file_path in enumerate(sorted_files):
        chunks[i % num_workers].append(file_path)
    
    return chunks

def display_progress_stats():
    """Display progress statistics and estimated time remaining."""
    with stats_lock:
        files_processed = global_stats["files_processed"]
        files_total = global_stats["files_total"]
        records_processed = global_stats["records_processed"]
        elapsed_time = time.time() - global_stats["start_time"]
        embedding_failures = global_stats["embedding_failures"]
        batches_saved = global_stats["batches_saved"]
    
    if files_processed == 0:
        return "Waiting for first file to complete..."
    
    # Calculate progress percentages
    file_progress = (files_processed / files_total) * 100 if files_total > 0 else 0
    
    # Calculate processing rates
    files_per_hour = (files_processed / elapsed_time) * 3600 if elapsed_time > 0 else 0
    records_per_hour = (records_processed / elapsed_time) * 3600 if elapsed_time > 0 else 0
    
    # Estimate remaining time
    if files_per_hour > 0 and files_total > 0:
        remaining_files = files_total - files_processed
        remaining_seconds = (remaining_files / files_per_hour) * 3600
        remaining_time = timedelta(seconds=int(remaining_seconds))
    else:
        remaining_time = "Unknown"
    
    # Calculate ETA
    if isinstance(remaining_time, timedelta):
        eta = datetime.now() + remaining_time
        eta_str = eta.strftime("%Y-%m-%d %H:%M:%S")
    else:
        eta_str = "Unknown"
    
    # Format progress message
    progress_msg = (
        f"Progress: {files_processed}/{files_total} files ({file_progress:.1f}%)\n"
        f"Records processed: {records_processed:,}\n"
        f"Embedding failures: {embedding_failures:,}\n"
        f"Batches saved: {batches_saved:,}\n"
        f"Processing rate: {files_per_hour:.2f} files/hour, {records_per_hour:.2f} records/hour\n"
        f"Elapsed time: {str(timedelta(seconds=int(elapsed_time)))}\n"
        f"Estimated time remaining: {str(remaining_time)}\n"
        f"Estimated completion: {eta_str}"
    )
    
    return progress_msg

def save_stats_snapshot():
    """Save a snapshot of the current statistics."""
    try:
        stats_file = LOGS_DIR / f"stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with stats_lock:
            # Create a copy of stats that can be JSON serialized
            stats_copy = global_stats.copy()
            stats_copy["processing_times"] = [(r, t) for r, t in stats_copy["processing_times"]]
            stats_copy["files_in_progress"] = list(stats_copy["files_in_progress"])
            stats_copy["elapsed_time"] = time.time() - stats_copy["start_time"]
            stats_copy["timestamp"] = datetime.now().isoformat()
        
        with open(stats_file, 'w') as f:
            json.dump(stats_copy, f, indent=2)
            
        logger.info(f"Saved stats snapshot to {stats_file}")
        
    except Exception as e:
        logger.error(f"Error saving stats snapshot: {e}")

def load_embeddings_to_qdrant():
    """Load saved embeddings to Qdrant."""
    if not os.getenv("QDRANT_LOAD_EMBEDDINGS", "False").lower() in ("true", "1", "t"):
        logger.info("Skipping Qdrant loading as QDRANT_LOAD_EMBEDDINGS is not set to True")
        return
    
    logger.info(f"Loading saved embeddings to Qdrant collection {QDRANT_COLLECTION}")
    
    try:
        # Connect to Qdrant
        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        
        # Ensure collection exists
        collections = client.get_collections().collections
        collection_names = [collection.name for collection in collections]
        
        if QDRANT_COLLECTION not in collection_names:
            logger.info(f"Creating Qdrant collection {QDRANT_COLLECTION}")
            client.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=VectorParams(
                    size=VECTOR_DIM, 
                    distance=Distance.COSINE
                )
            )
        
        # Count existing points
        existing_count = client.count(collection_name=QDRANT_COLLECTION).count
        logger.info(f"Collection currently has {existing_count} points")
        
        # Find all batch files
        batch_files = []
        for worker_dir in OUTPUT_DIR.glob("worker_*"):
            if worker_dir.is_dir():
                for batch_file in worker_dir.glob("batch_*.pkl"):
                    batch_files.append(batch_file)
        
        logger.info(f"Found {len(batch_files)} batch files to load")
        
        # Load and upsert each batch
        loaded_count = 0
        for i, batch_file in enumerate(tqdm.tqdm(batch_files, desc="Loading batches")):
            try:
                with open(batch_file, 'rb') as f:
                    batch_data = pickle.load(f)
                
                points = [
                    PointStruct(
                        id=p["id"],
                        vector=p["vector"],
                        payload=p["payload"]
                    )
                    for p in batch_data["points"]
                ]
                
                # Upsert in smaller batches to not overwhelm Qdrant
                MAX_UPSERT_BATCH = 100
                for j in range(0, len(points), MAX_UPSERT_BATCH):
                    sub_batch = points[j:j+MAX_UPSERT_BATCH]
                    client.upsert(
                        collection_name=QDRANT_COLLECTION,
                        points=sub_batch
                    )
                
                loaded_count += len(points)
                
                # Log progress periodically
                if (i + 1) % 10 == 0:
                    logger.info(f"Loaded {loaded_count} points from {i+1}/{len(batch_files)} batch files")
                
                # Small delay to avoid overwhelming Qdrant
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error loading batch {batch_file}: {e}")
        
        # Final count
        final_count = client.count(collection_name=QDRANT_COLLECTION).count
        logger.info(f"Completed loading. Collection now has {final_count} points")
        logger.info(f"Added {final_count - existing_count} new points")
        
    except Exception as e:
        logger.error(f"Error loading embeddings to Qdrant: {e}")

def run_parallel_processing():
    """Main function to run the parallel processing workflow."""
    logger.info("Starting parallel processing workflow")
    
    # Initialize Qdrant if enabled
    if USE_DIRECT_QDRANT:
        initialize_qdrant()
    
    # Get list of Parquet files to process
    parquet_files = get_parquet_files()
    logger.info(f"Found {len(parquet_files)} Parquet files to process")
    
    # Check for previously processed files
    processed_files = get_previously_processed_files()
    logger.info(f"Found {len(processed_files)} previously processed files")
    
    # Filter out already processed files
    remaining_files = [f for f in parquet_files if f not in processed_files]
    logger.info(f"Starting processing with {len(remaining_files)} remaining files")
    
    # Update global stats
    with stats_lock:
        global_stats["files_total"] = len(remaining_files)
    
    # Divide work among workers
    work_chunks = divide_work(remaining_files, NUM_WORKERS)
    logger.info(f"Divided {len(remaining_files)} files among {NUM_WORKERS} workers")
    
    # Create a progress bar
    progress_bar = tqdm.tqdm(total=len(remaining_files), desc="Processing files")
    
    # Create and start the worker processes
    with ProcessPoolExecutor(max_workers=NUM_WORKERS) as executor:
        # Submit jobs
        future_to_worker = {
            executor.submit(worker_process, chunk, worker_id): worker_id
            for worker_id, chunk in enumerate(work_chunks)
        }
        
        # Process as they complete
        try:
            last_status_time = time.time()
            last_save_time = time.time()
            
            for future in as_completed(future_to_worker):
                worker_id = future_to_worker[future]
                
                try:
                    worker_stats = future.result()
                    logger.info(f"Worker {worker_id} completed: processed {worker_stats['records_processed']} records in {worker_stats['elapsed_time']:.2f}s")
                    
                    # Update progress bar
                    progress_bar.update(worker_stats["files_processed"])
                    
                    # Display periodic status updates
                    current_time = time.time()
                    if current_time - last_status_time > 60:  # Every minute
                        status = display_progress_stats()
                        logger.info(f"\nStatus Update:\n{status}")
                        last_status_time = current_time
                    
                    # Save periodic stats snapshots
                    if current_time - last_save_time > 300:  # Every 5 minutes
                        save_stats_snapshot()
                        last_save_time = current_time
                        
                except Exception as e:
                    logger.error(f"Error in worker {worker_id}: {e}")
        
        except KeyboardInterrupt:
            logger.warning("Process interrupted by user.")
            executor.shutdown(wait=False)
            
            # Save final stats
            save_stats_snapshot()
            return
    
    # Close progress bar
    progress_bar.close()
    
    # Final stats
    logger.info("Processing completed!")
    status = display_progress_stats()
    logger.info(f"\nFinal Status:\n{status}")
    
    # Save final stats
    save_stats_snapshot()
    
    # Load to Qdrant if requested
    if not USE_DIRECT_QDRANT and os.getenv("QDRANT_LOAD_EMBEDDINGS", "False").lower() in ("true", "1", "t"):
        load_embeddings_to_qdrant()

if __name__ == "__main__":
    # Start time for the entire process
    start_time = time.time()
    logger.info(f"Starting parallel processing at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        run_parallel_processing()
    except KeyboardInterrupt:
        logger.warning("Process interrupted by user.")
    except Exception as e:
        logger.error(f"Error in main process: {e}")
    
    # Log total runtime
    total_time = time.time() - start_time
    logger.info(f"Process ended after {total_time:.2f} seconds")