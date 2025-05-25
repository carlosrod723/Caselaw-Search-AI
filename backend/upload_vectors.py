# upload_vectors.py

"""
Multi-threaded script to upload vector embeddings from pickle files to Qdrant.
Optimized for M4 Max with 16 cores and 128GB RAM, with improved error handling.
"""

import os
import pickle
import time
import logging
from pathlib import Path
import concurrent.futures
from tqdm import tqdm
from qdrant_client import QdrantClient
from qdrant_client.http import models
import backoff

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configuration
EMBEDDINGS_DIR = "caselaw_processing/processed_embeddings"
COLLECTION_NAME = "caselaw_bge_base_v2"
BATCH_SIZE = 1000  # Reduced batch size
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
QDRANT_TIMEOUT = 180.0  # 3-minute timeout
VECTOR_SIZE = 768  # BGE base dimension
NUM_WORKERS = 8  # Reduced to avoid overwhelming the server
MAX_FILES_PER_WORKER = None  # Set to a number for testing, None for all files

def get_qdrant_client():
    """Create a Qdrant client with appropriate timeout settings."""
    return QdrantClient(
        host=QDRANT_HOST, 
        port=QDRANT_PORT,
        timeout=QDRANT_TIMEOUT
    )

def ensure_collection_exists(client):
    """Make sure the collection exists in Qdrant with the right configuration."""
    try:
        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        if COLLECTION_NAME not in collection_names:
            logger.info(f"Creating collection {COLLECTION_NAME}...")
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=models.VectorParams(
                    size=VECTOR_SIZE,
                    distance=models.Distance.COSINE
                )
            )
            logger.info(f"Collection {COLLECTION_NAME} created successfully")
        else:
            logger.info(f"Collection {COLLECTION_NAME} already exists")
    except Exception as e:
        logger.error(f"Error ensuring collection exists: {e}")
        raise

def get_worker_dirs():
    """Get all worker directories from the embeddings directory."""
    base_dir = Path(EMBEDDINGS_DIR)
    worker_dirs = sorted([d for d in base_dir.iterdir() if d.is_dir() and d.name.startswith("worker_")])
    logger.info(f"Found {len(worker_dirs)} worker directories")
    return worker_dirs

def get_pickle_files(worker_dir, limit=None):
    """Get all pickle files in a worker directory, optionally limited."""
    worker_path = Path(worker_dir)
    pickle_files = sorted(list(worker_path.glob("batch_*.pkl")))
    
    if limit:
        pickle_files = pickle_files[:limit]
        
    logger.info(f"Found {len(pickle_files)} pickle files in {worker_dir}")
    return pickle_files

def process_pickle_file(file_path):
    """Process a single pickle file and extract points for Qdrant."""
    try:
        with open(file_path, 'rb') as f:
            data = pickle.load(f)
        
        if not isinstance(data, dict) or 'points' not in data or not data['points']:
            logger.warning(f"File {file_path} has no valid points data")
            return []
        
        points = []
        for point in data['points']:
            if 'id' not in point or 'vector' not in point:
                continue
                
            # Convert the point to Qdrant format
            points.append(models.PointStruct(
                id=point['id'],
                vector=point['vector'],
                payload=point.get('payload', {})
            ))
        
        logger.debug(f"Extracted {len(points)} points from {file_path}")
        return points
    except Exception as e:
        logger.error(f"Error processing file {file_path}: {e}")
        return []

@backoff.on_exception(backoff.expo, Exception, max_tries=5, max_time=300)
def upload_points_batch(client, points_batch, worker_name):
    """Upload a batch of points to Qdrant with retry logic."""
    try:
        if not points_batch:
            return 0
            
        logger.info(f"{worker_name}: Uploading batch of {len(points_batch)} points")
        result = client.upsert(
            collection_name=COLLECTION_NAME,
            points=points_batch,
            wait=True
        )
        logger.info(f"{worker_name}: Successfully uploaded {len(points_batch)} points")
        return len(points_batch)
    except Exception as e:
        logger.error(f"{worker_name}: Error uploading batch: {e}")
        raise  # Let backoff retry

def process_worker_directory(worker_dir_info):
    """Process all pickle files in a worker directory."""
    worker_dir, worker_idx = worker_dir_info
    worker_name = Path(worker_dir).name
    logger.info(f"Starting processing for {worker_name} (worker {worker_idx})")
    
    # Create a client for this worker
    client = get_qdrant_client()
    
    # Get all pickle files
    pickle_files = get_pickle_files(worker_dir, MAX_FILES_PER_WORKER)
    if not pickle_files:
        logger.warning(f"No pickle files found in {worker_name}")
        return 0
    
    total_points = 0
    points_batch = []
    
    for file_path in tqdm(pickle_files, desc=f"Processing {worker_name}", position=worker_idx):
        try:
            points = process_pickle_file(file_path)
            
            # Process in smaller sub-batches to avoid overwhelming Qdrant
            for i in range(0, len(points), BATCH_SIZE):
                sub_batch = points[i:i+BATCH_SIZE]
                if sub_batch:
                    uploaded = upload_points_batch(client, sub_batch, worker_name)
                    total_points += uploaded
        except Exception as e:
            logger.error(f"{worker_name}: Error processing file {file_path}: {e}")
            # Continue with next file
    
    logger.info(f"Completed {worker_name}: Total points uploaded: {total_points}")
    return total_points

def main():
    start_time = time.time()
    logger.info(f"Starting vector upload to Qdrant collection '{COLLECTION_NAME}'")
    
    # Initialize Qdrant client and ensure collection exists
    client = get_qdrant_client()
    ensure_collection_exists(client)
    
    # Get worker directories
    worker_dirs = get_worker_dirs()
    
    # Add worker index to each directory for positioning progress bars
    worker_dir_infos = [(worker_dir, idx) for idx, worker_dir in enumerate(worker_dirs)]
    
    # Use ProcessPoolExecutor to parallelize processing
    total_uploaded = 0
    with concurrent.futures.ProcessPoolExecutor(max_workers=NUM_WORKERS) as executor:
        # Submit all tasks
        future_to_worker = {executor.submit(process_worker_directory, worker_dir_info): worker_dir_info[0].name 
                            for worker_dir_info in worker_dir_infos}
        
        # Process results as they complete
        for future in tqdm(concurrent.futures.as_completed(future_to_worker), 
                          total=len(future_to_worker), 
                          desc="Processing worker directories"):
            worker_name = future_to_worker[future]
            try:
                count = future.result()
                total_uploaded += count
                logger.info(f"Worker {worker_name} completed: {count} points uploaded")
            except Exception as e:
                logger.error(f"Worker {worker_name} failed: {e}")
    
    # Get the final count from Qdrant
    try:
        final_count = client.count(collection_name=COLLECTION_NAME).count
        logger.info(f"Final collection count: {final_count}")
    except Exception as e:
        logger.error(f"Error getting final count: {e}")
    
    elapsed_time = time.time() - start_time
    hours, remainder = divmod(elapsed_time, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    logger.info(f"Upload complete. Total points uploaded: {total_uploaded}")
    logger.info(f"Total time: {int(hours)}h {int(minutes)}m {seconds:.2f}s")

if __name__ == "__main__":
    main()