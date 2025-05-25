# CaseLaw AI Backend API

A high-performance, scalable backend API powering the CaseLaw AI search platform. This service provides semantic search capabilities across 6.6 million case law records using vector embeddings, with comprehensive metadata retrieval and case enhancement features.

## Technology Stack

### Core Framework

- **FastAPI**: High-performance web framework for building APIs with Python 3.9+
  - Automatic OpenAPI documentation generation
  - Type checking with integrated Pydantic validation
  - Dependency injection system for clean service organization
  - Async request handling for optimal performance

### Data Storage

- **SQLite**: Lightweight yet powerful database for case metadata (6.3GB)
  - Optimized for read-heavy operations
  - Full-text search capabilities for fallback searches
  - Efficient indexing for quick metadata retrieval
  - Minimal server requirements compared to traditional RDBMS

- **Qdrant**: Specialized vector database for semantic search
  - High-dimensional vector storage and similarity search
  - Efficient approximate nearest neighbor (ANN) search
  - Filter combinations with vector search
  - Payload storage for additional metadata

### Vector Embeddings

- **OpenAI Embeddings**: High-quality vector representations of text
  - Dense vector representations capturing semantic meaning
  - Dimension reduction for storage efficiency
  - Cosine similarity matching for relevant results
  - Contextual understanding of legal terminology

### Data Validation and Schemas

- **Pydantic**: Data validation and settings management
  - Runtime validation of all API inputs and outputs
  - Automatic JSON schema generation
  - Type annotations throughout the codebase
  - Clean separation of data models and logic

## API Endpoints

### Search Endpoints

#### `GET /api/v1/search`

Search for cases based on a natural language query with optional filters.

**Query Parameters:**

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `q` | string | Natural language query | (required) |
| `jurisdiction` | string | Filter by jurisdiction | (optional) |
| `case_type` | string | Filter by case type | (optional) |
| `court` | string | Filter by court | (optional) |
| `start_date` | string (YYYY-MM-DD) | Filter cases after this date | (optional) |
| `end_date` | string (YYYY-MM-DD) | Filter cases before this date | (optional) |
| `offset` | integer | Pagination offset | 0 |
| `limit` | integer | Results per page | 10 |
| `sort` | string | Sort criteria (relevance, date_asc, date_desc) | "relevance" |

**Response:**

```json
{
  "results": [
    {
      "id": "12345",
      "name": "Smith v. Jones",
      "citation": "123 U.S. 456 (2010)",
      "court": "Supreme Court of the United States",
      "jurisdiction": "Federal",
      "case_type": "Civil",
      "date_decided": "2010-05-15",
      "docket_number": "08-1234",
      "snippet": "... the Fourth Amendment protects against unreasonable searches and seizures ...",
      "score": 0.92
    },
    // Additional results...
  ],
  "total": 245,
  "offset": 0,
  "limit": 10,
  "query_time_ms": 156
}
```

**Example Request:**

```bash
curl -X GET "http://localhost:8000/api/v1/search?q=fourth%20amendment%20search%20and%20seizure&jurisdiction=Federal&case_type=Civil&limit=10&offset=0" -H "accept: application/json"
```

### Case Endpoints

#### `GET /api/v1/case/{id}`

Retrieve basic metadata for a specific case.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Unique case identifier |

**Response:**

```json
{
  "id": "12345",
  "name": "Smith v. Jones",
  "citation": "123 U.S. 456 (2010)",
  "court": "Supreme Court of the United States",
  "jurisdiction": "Federal",
  "case_type": "Civil",
  "date_decided": "2010-05-15",
  "docket_number": "08-1234",
  "majority_author": "Roberts, C.J.",
  "dissent_author": "Sotomayor, J."
}
```

**Example Request:**

```bash
curl -X GET "http://localhost:8000/api/v1/case/12345" -H "accept: application/json"
```

#### `GET /api/v1/case/{id}/full`

Retrieve enhanced case details with full text, citations, and AI-generated summary.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Unique case identifier |

**Response:**

```json
{
  "id": "12345",
  "name": "Smith v. Jones",
  "citation": "123 U.S. 456 (2010)",
  "court": "Supreme Court of the United States",
  "jurisdiction": "Federal",
  "case_type": "Civil",
  "date_decided": "2010-05-15",
  "docket_number": "08-1234",
  "majority_author": "Roberts, C.J.",
  "dissent_author": "Sotomayor, J.",
  "full_text": "...[full text of the case]...",
  "syllabus": "...[case syllabus]...",
  "key_passages": [
    {
      "text": "The Fourth Amendment protects against unreasonable searches and seizures.",
      "relevance_score": 0.95
    },
    // Additional key passages...
  ],
  "ai_summary": "This case examines the boundaries of Fourth Amendment protections in digital searches...",
  "cited_cases": [
    {
      "citation": "389 U.S. 347 (1967)",
      "name": "Katz v. United States"
    },
    // Additional citations...
  ]
}
```

**Example Request:**

```bash
curl -X GET "http://localhost:8000/api/v1/case/12345/full" -H "accept: application/json"
```

#### `GET /api/v1/case/{id}/pdf`

Generate a PDF document of the case with proper formatting.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Unique case identifier |

**Response:**

Binary PDF file with appropriate content-type headers.

**Example Request:**

```bash
curl -X GET "http://localhost:8000/api/v1/case/12345/pdf" -H "accept: application/pdf" --output case.pdf
```

## Database Schema

### SQLite Schema

The SQLite database (`case_lookup.db`) contains the following key tables:

#### `cases`

Main table storing case metadata.

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | Primary key - unique case identifier |
| `name` | TEXT | Case name (e.g., "Smith v. Jones") |
| `citation` | TEXT | Official citation |
| `court_id` | TEXT | Foreign key to courts table |
| `jurisdiction_id` | TEXT | Foreign key to jurisdictions table |
| `case_type_id` | TEXT | Foreign key to case_types table |
| `date_decided` | TEXT | Decision date (YYYY-MM-DD) |
| `docket_number` | TEXT | Court docket number |
| `majority_author` | TEXT | Author of majority opinion |
| `dissent_author` | TEXT | Author of dissenting opinion |
| `cid` | TEXT | Content identifier for full text lookup |
| `created_at` | TEXT | Record creation timestamp |
| `updated_at` | TEXT | Record update timestamp |

#### `case_types`

Classification of cases into types.

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | Primary key |
| `name` | TEXT | Type name (Criminal, Civil, Administrative, Constitutional, Disciplinary) |
| `description` | TEXT | Detailed description of the case type |

#### `cid_index`

Content identifier index for fast lookups.

| Column | Type | Description |
|--------|------|-------------|
| `cid` | TEXT | Content identifier |
| `file_path` | TEXT | Path to file containing the case content |
| `offset` | INTEGER | Byte offset in file |
| `length` | INTEGER | Content length in bytes |

#### `secondary_cid_index`

Secondary identifiers for alternate retrieval paths.

| Column | Type | Description |
|--------|------|-------------|
| `secondary_id` | TEXT | Alternative identifier |
| `primary_cid` | TEXT | Primary content identifier |
| `id_type` | TEXT | Type of secondary identifier |

### Qdrant Vector Database

The Qdrant database stores vector embeddings with the following structure:

- **Collection**: `case_embeddings`
- **Vector dimension**: 1536 (OpenAI embedding dimension)
- **Distance metric**: Cosine similarity
- **Payload fields**:
  - `id`: Case identifier matching SQLite database
  - `citation`: Case citation for quick reference
  - `jurisdiction`: Jurisdiction for filtering
  - `case_type`: Case type for filtering
  - `court`: Court name for filtering
  - `date_decided`: Decision date for filtering and sorting
  
## Vector Search Implementation

### Embedding Generation

CaseLaw AI uses OpenAI's text-embedding-ada-002 model to generate vector embeddings for all cases in the dataset. The embedding process:

1. Preprocesses case text to extract most relevant content
2. Generates embeddings for each case (1536-dimensional vectors)
3. Stores embeddings in Qdrant with metadata payload
4. Updates embeddings when case content changes

```python
# Example embedding generation code
from app.services.openai_service import OpenAIService

openai_service = OpenAIService()
embedding = openai_service.create_embedding(case_text)
```

### Query Refinement

Raw user queries are processed before vector search:

1. Query analysis to identify legal terms and concepts
2. Expansion of legal abbreviations and citations
3. Reformulation to prioritize legally significant terms
4. Generation of embedding for the refined query

### Hybrid Search Approach

CaseLaw AI combines vector similarity search with traditional text-based search:

1. Primary search using vector similarity in Qdrant
2. Secondary search using SQLite full-text search
3. Results combination with custom scoring algorithm
4. Fallback to text search when vector search returns low confidence results

```python
# Simplified hybrid search implementation
vector_results = qdrant_service.search(query_vector, filters, limit)
if vector_results.confidence < THRESHOLD:
    text_results = sqlite_service.full_text_search(query, filters, limit)
    results = combine_results(vector_results, text_results)
else:
    results = vector_results
```

### Performance Optimizations

Several optimizations ensure fast search across the large dataset:

1. Vector quantization to reduce storage requirements
2. Optimized HNSW index in Qdrant for fast ANN search
3. Caching of frequent queries and results
4. Pagination with cursor-based implementation
5. Parallel processing of search results
6. Background preprocessing of frequent filter combinations

## Local Development

### Prerequisites

- Python 3.9+
- Docker and Docker Compose (for Qdrant)
- 16GB+ RAM recommended
- 100GB+ free disk space for the full dataset

### Setup and Installation

1. Clone the repository (if not already done):
   ```bash
   git clone https://github.com/yourusername/caselaw-ai.git
   cd caselaw-ai/backend
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up Qdrant using Docker:
   ```bash
   docker-compose up -d qdrant
   ```

5. Download the case_lookup.db file (6.3GB) and place it in the backend directory.

### Environment Variables

Create a `.env` file in the backend directory with the following variables:

```
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=true
ENVIRONMENT=development

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key

# Qdrant Configuration
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=case_embeddings

# SQLite Configuration
SQLITE_DB_PATH=./case_lookup.db

# Cache Configuration
CACHE_TTL=3600
ENABLE_RESPONSE_CACHE=true
```

### Running the Server

Start the FastAPI server:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at http://localhost:8000 and the interactive documentation at http://localhost:8000/docs.

## Testing

### Running Tests

Execute the test suite:

```bash
pytest
```

Run specific test modules:

```bash
pytest test_case_retrieval.py
```

Run with coverage report:

```bash
pytest --cov=app --cov-report=term-missing
```

### Test Data

The repository includes a small test dataset in `tests/fixtures` for running tests without requiring the full database.

## Performance Considerations

### Working with the Large Dataset

The complete dataset (6.6 million cases, 81GB) requires careful handling:

1. **Memory management**: 
   - Use streaming responses for large result sets
   - Implement pagination for all endpoints
   - Use connection pooling for database access

2. **Query optimization**:
   - Limit vector search dimensions when possible
   - Use filters in Qdrant to reduce search space
   - Implement tiered caching strategy

3. **Scaling considerations**:
   - Horizontal scaling with multiple API instances
   - Qdrant clustering for larger deployments
   - Read replicas for SQLite database

4. **Monitoring**:
   - Track query performance and slow queries
   - Monitor memory usage during peak loads
   - Set up alerts for service degradation

### Resource Requirements

Minimum recommended specifications for running the full dataset:

- **CPU**: 4+ cores
- **RAM**: 16GB+
- **Disk**: 100GB+ SSD storage
- **Network**: 1Gbps for optimal inter-service communication

## License

This project is licensed under the MIT License - see the LICENSE file for details.