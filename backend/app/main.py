# app/main.py
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.search import router as search_router
from app.api.v1.case import router as case_router  # Import the case router
from app.core.config import settings
from app.services.qdrant_service import qdrant_service, get_client
from app.services.openai_service import openai_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Track application stats
startup_time = None
request_count = 0
error_count = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Run‑once setup / teardown for every FastAPI worker.

    • Pre‑connect to Qdrant so the first user request isn't delayed.
    • Initialize services and track startup time.
    """
    global startup_time
    startup_time = time.time()
    
    logger.info("Application startup: initializing services")
    try:
        client = get_client()
        logger.info(f"Successfully connected to Qdrant at {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
        
        # Try to optimize collection for better performance
        try:
            qdrant_service.optimize_collection()
        except Exception as e:
            logger.warning(f"Collection optimization failed: {e}")
            
    except Exception as e:
        logger.error(f"Failed to connect to Qdrant: {e}")
        logger.warning("Application will continue but search functionality may be impaired")
    
    logger.info("Application startup complete")
    yield
    logger.info("Application shutdown")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for searching legal cases using vector embeddings",
    version="1.0.0",
    lifespan=lifespan,
)


# Middleware to log requests and track stats
@app.middleware("http")
async def log_requests(request: Request, call_next):
    global request_count, error_count
    
    # Increment request counter
    request_count += 1
    
    # Log request details
    logger.debug(f"Request: {request.method} {request.url.path}")
    
    # Track request timing
    start_time = time.time()
    
    try:
        # Process the request
        response = await call_next(request)
        
        # Log successful responses
        process_time = time.time() - start_time
        logger.debug(f"Response: {response.status_code} (took {process_time:.2f}s)")
        
        return response
    except Exception as e:
        # Log and count errors
        error_count += 1
        process_time = time.time() - start_time
        logger.error(f"Request error after {process_time:.2f}s: {str(e)}")
        raise


# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
logger.info(f"Including search router at {settings.API_V1_STR}")
app.include_router(search_router, prefix=settings.API_V1_STR)

# Add case router
logger.info(f"Including case router at {settings.API_V1_STR}")
app.include_router(case_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    logger.debug("Root endpoint accessed")
    return {
        "message": "Welcome to the Caselaw Search API",
        "version": "1.0.0",
        "docs_url": "/docs"
    }


@app.get("/health")
async def health():
    """
    Health check endpoint that verifies services are working.
    
    Returns:
        Status and health information for all services
    """
    logger.debug("Health check endpoint accessed")
    
    # Check Qdrant connection
    qdrant_status = "unknown"
    qdrant_info = {}
    try:
        # Try to get collection info
        collection_info = qdrant_service.get_collection_info()
        qdrant_status = "ok"
        # Extract essential info for health check
        qdrant_info = {
            "collection": qdrant_service.collection_name,
            "vector_size": collection_info.config.params.vectors.size,
            "points_count": getattr(collection_info, "points_count", "unknown"),
        }
    except Exception as e:
        logger.error(f"Health check failed for Qdrant: {e}")
        qdrant_status = "error"
        qdrant_info = {"error": str(e)}
    
    # Get OpenAI service stats
    openai_status = "unknown"
    openai_info = {}
    try:
        openai_info = openai_service.get_performance_stats()
        openai_status = "ok"
    except Exception as e:
        logger.error(f"Health check failed for OpenAI service: {e}")
        openai_status = "error"
        openai_info = {"error": str(e)}
    
    # App stats
    uptime = time.time() - startup_time if startup_time else 0
    
    return {
        "status": "ok" if qdrant_status == "ok" else "degraded",
        "services": {
            "qdrant": {
                "status": qdrant_status,
                "info": qdrant_info
            },
            "openai": {
                "status": openai_status,
                "info": openai_info
            }
        },
        "app": {
            "uptime_seconds": int(uptime),
            "request_count": request_count,
            "error_count": error_count,
        }
    }


@app.get("/metrics")
async def metrics():
    """
    Metrics endpoint for monitoring and debugging.
    
    Returns:
        Detailed performance metrics for the API
    """
    logger.debug("Metrics endpoint accessed")
    
    # Get OpenAI performance stats
    openai_stats = openai_service.get_performance_stats()
    
    # App stats
    uptime = time.time() - startup_time if startup_time else 0
    
    return {
        "app": {
            "uptime_seconds": int(uptime),
            "request_count": request_count,
            "error_count": error_count,
        },
        "services": {
            "openai": openai_stats,
        },
        "routes": {
        }
    }