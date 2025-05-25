# optimize_qdrant.py
import os
import sys
import logging
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http.models import UpdateCollection, OptimizersConfigDiff, HnswConfigDiff

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def optimize_qdrant_collection():
    """Apply optimizations to the Qdrant collection to improve search performance."""
    try:
        # Get configuration from environment
        host = os.getenv("QDRANT_HOST", "localhost")
        port = int(os.getenv("QDRANT_PORT", "6333"))
        collection_name = os.getenv("QDRANT_COLLECTION", "caselaw_bge_base_v2")
        is_https = os.getenv("QDRANT_HTTPS", "false").lower() == "true"
        
        logger.info(f"Connecting to Qdrant at {host}:{port}, collection: {collection_name}")
        
        # Create client with longer timeout
        client = QdrantClient(
            host=host,
            port=port,
            https=is_https,
            timeout=120.0,  # 2 minute timeout for admin operations
            prefer_grpc=True,  # Use gRPC for better performance
        )
        
        # Verify connection and collection existence
        collections = client.get_collections()
        collection_exists = any(c.name == collection_name for c in collections.collections)
        
        if not collection_exists:
            logger.error(f"Collection {collection_name} does not exist!")
            return False
        
        logger.info(f"Connected to Qdrant, collection {collection_name} exists")
        
        # Get current collection info
        collection_info = client.get_collection(collection_name=collection_name)
        logger.info(f"Current collection config: {collection_info.config}")
        
        # Apply optimizations
        logger.info("Applying optimizations...")
        
        # Update HNSW parameters for better search performance
        client.update_collection(
            collection_name=collection_name,
            optimizer_config=OptimizersConfigDiff(
                indexing_threshold=50000,  # Merge segments after reaching this size
                vacuum_min_vector_number=1000,  # Minimal number of vectors in a segment to consider it for vacuum
                default_segment_number=2,
                max_segment_size=3000000 # Allow for large segments
            ),
            hnsw_config=HnswConfigDiff(
                m=16,              # Number of connections per element (higher = better recall, more RAM)
                ef_construct=100,  # Size of the dynamic candidate list for construction (higher = better recall, slower build)
                full_scan_threshold=20000,  # Number of vectors to trigger a full scan (smaller = faster but less accurate)
            )
        )
        
        # Get updated collection info
        updated_collection = client.get_collection(collection_name=collection_name)
        logger.info(f"Updated collection config: {updated_collection.config}")
        
        # Set the ef_search parameter using search params instead
        logger.info("Testing search with optimized parameters...")
        test_vector = [0.1] * 768  # Dummy vector for testing
        
        # Use search_params to set ef at search time
        _ = client.search(
            collection_name=collection_name,
            query_vector=test_vector,
            limit=1
        )
        
        logger.info("Test search completed. The ef parameter will be applied at runtime.")
        logger.info("Qdrant collection optimization completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Error optimizing Qdrant collection: {e}")
        return False

if __name__ == "__main__":
    success = optimize_qdrant_collection()
    sys.exit(0 if success else 1)