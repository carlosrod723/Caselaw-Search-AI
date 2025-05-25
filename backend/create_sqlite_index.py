# create_sqlite_index.py

"""
Creates a new SQLite database index for the Caselaw Access Project parquet files.
This script scans all parquet files and builds a comprehensive index for efficient case lookups.
Includes case type classification for improved filtering.

Optimized for MacBook Pro with M4 Max (16-core CPU, 128GB RAM).
"""

import os
import sqlite3
import pandas as pd
import pyarrow.parquet as pq
import glob
import re
import argparse
import logging
import time
import concurrent.futures
from tqdm import tqdm
import multiprocessing
import json
import sys
from collections import Counter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("create_sqlite_index.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Case type classification patterns
CASE_TYPE_PATTERNS = {
    'criminal': {
        'terms': [
            # Strong indicators (weight 3)
            r'\b(?:criminal|felony|misdemeanor)\b',
            r'\b(?:indictment|arraignment|sentencing|convicted|conviction|guilty|acquitted|acquittal)\b',
            r'\b(?:prosecution|prosecutor|district attorney)\b',
            
            # Crime types (weight 2)
            r'\b(?:murder|homicide|manslaughter|robbery|burglary|theft|assault|rape|arson)\b',
            r'\b(?:battery|kidnapping|fraud|embezzlement|forgery|extortion|bribery)\b',
            r'\b(?:narcotics|cocaine|heroin|marijuana|drugs|controlled substance)\b',
            
            # Criminal procedure (weight 1)
            r'\b(?:trial court|criminal court|criminal trial|criminal case|criminal charge)\b',
            r'\b(?:plea|bail|parole|probation|sentence|imprisonment|incarceration)\b',
            r'\b(?:arrest|miranda|search warrant|probable cause|reasonable suspicion)\b',
            r'\bpenal code\b', r'\bcriminal code\b',
        ],
        'case_name': [
            # Very strong indicators (weight 15) - higher than civil case_name patterns
            r'^(?:State|People|United States|Commonwealth|Government|The People|The State)\s+v\.\s+',
            r'^(?:People\s+ex\s+rel|State\s+ex\s+rel)\.?\s+',
            r'^(?:U\.\s*S\.|USA)\s+v\.\s+'
        ],
        'court_hints': [
            # Court type indicators (weight 5)
            'criminal court', 'court of criminal appeals', 'criminal division'
        ],
        'weights': {
            'terms': [3, 3, 3, 2, 2, 2, 1, 1, 1, 1],
            'case_name': 20,  # Even stronger weight to override civil pattern
            'court_hints': 5
        }
    },
    'civil': {
        'terms': [
            # Strong indicators (weight 3)
            r'\b(?:civil action|civil case|civil dispute|civil matter|civil judgment)\b',
            r'\b(?:plaintiff|claimant|petitioner|respondent)\b',
            r'\b(?:damages|liability|negligence|breach|tort|injunction)\b',
            
            # Civil procedure (weight 2)
            r'\b(?:complaint|answer|motion to dismiss|summary judgment|demurrer)\b',
            r'\b(?:deposition|interrogatory|discovery|affidavit|stipulation)\b',
            r'\b(?:class action|joinder|counterclaim|cross-claim|impleader)\b',
            
            # Common civil case types (weight 1)
            r'\b(?:contract|property|easement|mortgage|foreclosure|landlord|tenant)\b',
            r'\b(?:personal injury|medical malpractice|product liability|wrongful death)\b',
            r'\b(?:divorce|custody|alimony|child support|family law|probate|will)\b'
        ],
        'case_name': [
            # Standard civil case format (weight 10) - lower than criminal case_name
            r'^[A-Za-z\-\'\s\.]+\s+v\.\s+[A-Za-z\-\'\s\.]+$',
            # Exclude patterns that match criminal or administrative cases
            r'^(?!(?:State|People|United States|Commonwealth|Government|U\.S\.|USA)\s+v\.)(?!.*\s+v\.\s+(?:Department|Commission|Board|Agency|Secretary|Administration))'
        ],
        'court_hints': [
            'civil court', 'court of civil appeals', 'civil division', 
            'family court', 'probate court', 'small claims'
        ],
        'weights': {
            'terms': [3, 3, 3, 2, 2, 2, 1, 1, 1],
            'case_name': 10,  # Lower weight than criminal
            'court_hints': 5
        }
    },
    'constitutional': {
        'terms': [
            # Strong indicators (weight 3)
            r'\b(?:constitutional|unconstitutional|constitution)\b',
            r'\b(?:first amendment|second amendment|fourth amendment|fifth amendment|fourteenth amendment)\b',
            r'\b(?:equal protection|due process|bill of rights|civil rights|civil liberties)\b',
            
            # Constitutional principles (weight 2)
            r'\b(?:freedom of speech|freedom of religion|establishment clause|free exercise)\b',
            r'\b(?:search and seizure|double jeopardy|self-incrimination|cruel and unusual)\b',
            r'\b(?:strict scrutiny|rational basis|intermediate scrutiny)\b',
            
            # Constitutional references (weight 1)
            r'\b(?:federalism|separation of powers|commerce clause|supremacy clause)\b',
            r'\b(?:constitutional amendment|constitutional challenge|constitutional claim|constitutional issue)\b',
            r'\b(?:founding fathers|framers|ratification|constitutional convention)\b'
        ],
        'case_name': [
            # Constitutional cases often follow standard naming patterns
            r'^(?:State|United States|Commonwealth)\s+v\.\s+',  # Same as criminal
            r'^[A-Za-z\-\'\s\.]+\s+v\.\s+[A-Za-z\-\'\s\.]+$'    # Same as civil
        ],
        'court_hints': [
            # Don't rely heavily on Supreme Court hints - too broad
            'constitutional court'
        ],
        'weights': {
            'terms': [3, 3, 3, 2, 2, 2, 1, 1, 1],
            'case_name': 2,  # Lower weight - case names aren't distinctive
            'court_hints': 2  # Lower weight - don't rely on court name
        }
    },
    'administrative': {
        'terms': [
            # Strong indicators (weight 3)
            r'\b(?:administrative law|administrative procedure|administrative review|administrative appeal)\b',
            r'\b(?:agency action|regulatory|rule(?:making)?|regulation)\b',
            r'\b(?:arbitrary and capricious|substantial evidence|abuse of discretion)\b',
            
            # Agency references (weight 2)
            r'\b(?:EPA|FCC|FDA|NLRB|FTC|SEC|EEOC|IRS|ICE|OSHA|SSA)\b',
            r'\b(?:Department of|Commission|Board of|Bureau of|Office of|Authority)\b',
            r'\b(?:administrative law judge|hearing officer|commissioner|administrator|secretary)\b',
            
            # Administrative processes (weight 1)
            r'\b(?:notice and comment|informal rulemaking|formal rulemaking|adjudication)\b',
            r'\b(?:licensing|permit|variance|waiver|certificate)\b',
            r'\b(?:appeals council|review board|administrative record|final agency action)\b'
        ],
        'case_name': [
            # Cases against agencies (weight 15)
            r'(?:[A-Za-z\-\'\s\.]+)\s+v\.\s+(?:[A-Za-z\'\s]+\s+)?(?:Department|Commission|Board|Agency|Secretary|Administration|Commissioner)\b',
            r'(?:[A-Za-z\-\'\s\.]+)\s+v\.\s+(?:[A-Za-z\'\s]+\s+)(?:Agency|Authority|Bureau|Commission)\b'
        ],
        'court_hints': [
            'tax court', 'administrative law', 'board of appeals', 'administrative appeals', 
            'benefits review', 'compensation board'
        ],
        'weights': {
            'terms': [3, 3, 3, 2, 2, 2, 1, 1, 1],
            'case_name': 15,  # Higher weight to catch agency cases
            'court_hints': 5
        }
    },
    'disciplinary': {
        'terms': [
            # Strong indicators (weight 3)
            r'\b(?:disbarment|disciplinary|professional misconduct|ethics violation)\b',
            r'\b(?:attorney discipline|judicial discipline|medical board|bar association)\b',
            r'\b(?:license revocation|suspension of license|professional license)\b',
            
            # Professional regulation (weight 2)
            r'\b(?:malpractice|professional negligence|unprofessional conduct)\b',
            r'\b(?:grievance committee|disciplinary board|ethics committee)\b',
            r'\b(?:professional responsibility|code of conduct|rules of professional conduct)\b'
        ],
        'case_name': [
            # Disciplinary case patterns (weight 15)
            r'^In\s+(?:re|the\s+Matter\s+of)(?:\s+(?:the\s+)?(?:Application\s+for\s+)?Disbarment\s+of)?\s+',
            r'^In\s+(?:re|the\s+Matter\s+of)(?:\s+(?:the\s+)?(?:Disciplinary\s+Proceeding\s+Against))?\s+',
            r'^(?:Disciplinary\s+Counsel|Office\s+of\s+Disciplinary\s+Counsel|Committee\s+on\s+Professional\s+Ethics)\s+v\.\s+'
        ],
        'court_hints': [
            'disciplinary board', 'ethics committee', 'professional responsibility'
        ],
        'weights': {
            'terms': [3, 3, 3, 2, 2, 2],
            'case_name': 15,
            'court_hints': 5
        }
    }
}

def preprocess_case_type(case_name: str, court: str, jurisdiction: str) -> str:
    """
    Pre-classify cases based on name patterns that strongly indicate a specific type.
    This handles clear patterns without needing to analyze the full text.
    
    Args:
        case_name: The name/title of the case
        court: The court name
        jurisdiction: The jurisdiction name
        
    Returns:
        Case type string if a clear match is found, None otherwise
    """
    if not case_name:
        return None
        
    case_name_lower = case_name.lower()
    
    # Clear criminal case patterns
    if re.match(r'^(?:state|people|united states|commonwealth|the state|the people|u\.s\.|usa)\s+v\.', case_name_lower):
        return 'criminal'
    
    # Clear administrative case patterns - check for agency names
    agency_pattern = r'v\.\s+(?:[a-z\'\s]+\s+)?(?:department|commission|board|agency|secretary|administration|commissioner)\b'
    if re.search(agency_pattern, case_name_lower):
        return 'administrative'
    
    # Clear disciplinary case patterns
    if re.match(r'^in\s+(?:re|the\s+matter\s+of)(?:\s+(?:the\s+)?(?:application\s+for\s+)?disbarment\s+of)?\s+', case_name_lower):
        return 'disciplinary'
    
    # Check for additional disciplinary patterns
    if re.match(r'^in\s+(?:re|the\s+matter\s+of)', case_name_lower):
        # Look for disciplinary keywords in court name
        court_lower = court.lower() if court else ""
        if any(term in court_lower for term in ['disciplinary', 'ethics', 'professional']):
            return 'disciplinary'
    
    return None

def classify_case(
    case_text: str, 
    case_name: str, 
    court: str, 
    jurisdiction: str
) -> tuple:
    """
    Classify a case into one of the predefined categories based on its text and metadata.
    Uses improved weighting system and preprocessing to handle edge cases.
    
    Args:
        case_text: The full text of the case
        case_name: The case name/title
        court: The court name
        jurisdiction: The jurisdiction
        
    Returns:
        Tuple of (case_type, confidence)
    """
    # First try preprocessing for clear pattern matches
    preprocessed_type = preprocess_case_type(case_name, court, jurisdiction)
    if preprocessed_type:
        return preprocessed_type, 100.0
    
    # Prepare text for analysis
    if case_text and len(case_text) > 15000:
        # Use first 10000 and last 5000 characters as representative sample
        case_sample = case_text[:10000] + ' ' + case_text[-5000:]
    else:
        case_sample = case_text or ""
    
    case_sample = case_sample.lower()
    case_name_lower = case_name.lower() if case_name else ""
    court_lower = court.lower() if court else ""
    
    # Initialize scores
    scores = {case_type: 0 for case_type in CASE_TYPE_PATTERNS}
    
    # Calculate scores for each case type
    for case_type, patterns in CASE_TYPE_PATTERNS.items():
        weights = patterns.get('weights', {})
        
        # Check case name patterns FIRST - they're often the strongest indicator
        for pattern in patterns['case_name']:
            if re.search(pattern, case_name_lower):
                # Apply case_name weight
                pattern_weight = weights.get('case_name', 10)
                scores[case_type] += pattern_weight
        
        # Now check term patterns in case text
        for i, pattern in enumerate(patterns['terms']):
            matches = re.findall(pattern, case_sample)
            if matches:
                # Get term weight (default to 1)
                term_weight = weights.get('terms', [1])[min(i, len(weights.get('terms', [1]))-1)]
                scores[case_type] += len(matches) * term_weight
        
        # Check court name hints
        for hint in patterns['court_hints']:
            if hint in court_lower:
                # Apply court_hints weight
                hint_weight = weights.get('court_hints', 5)
                scores[case_type] += hint_weight
    
    # Special case handling - additional patterns that weren't caught in preprocessing
    
    # 1. "People v." and "State v." patterns for criminal cases
    if (re.search(r'^people\s+v\.', case_name_lower) or 
        re.search(r'^state\s+v\.', case_name_lower) or
        re.search(r'^united states\s+v\.', case_name_lower) or
        re.search(r'^u\.s\.\s+v\.', case_name_lower) or
        re.search(r'^commonwealth\s+v\.', case_name_lower)):
        boost = 10
        scores['criminal'] += boost
    
    # 2. Agency related cases for administrative
    if re.search(r'v\.\s+(?:[a-z\'\s]+\s+)?(?:department|commission|board|agency)', case_name_lower):
        boost = 8
        scores['administrative'] += boost
    
    # 3. "In re" cases often need special handling
    if re.match(r'^in\s+re\s+', case_name_lower):
        # If contains disbarment terms, boost disciplinary
        if any(term in case_sample for term in ['disbar', 'disciplin', 'ethics', 'misconduct']):
            boost = 10
            scores['disciplinary'] += boost
    
    # Get highest scoring case type
    if max(scores.values()) > 0:
        best_type = max(scores.items(), key=lambda x: x[1])[0]
        
        # Calculate confidence score - normalize based on score magnitude
        score_value = scores[best_type]
        confidence = min(score_value / 30 * 100, 100)  # Normalize to percentage with cap at 100%
    else:
        best_type = "civil"  # Default to civil if no clear pattern
        confidence = 50.0
    
    return best_type, confidence

def setup_database(db_path, overwrite=False):
    """
    Create a new SQLite database with the appropriate schema.
    
    Args:
        db_path: Path where the database should be created
        overwrite: Whether to overwrite an existing database
    
    Returns:
        True if database was created successfully, False otherwise
    """
    # Check if database already exists
    if os.path.exists(db_path):
        if overwrite:
            logger.warning(f"Overwriting existing database: {db_path}")
            os.remove(db_path)
        else:
            logger.error(f"Database already exists: {db_path}")
            logger.error("Use --overwrite to replace it or specify a different path")
            return False
    
    try:
        # Connect to database (will create if it doesn't exist)
        conn = sqlite3.connect(db_path)
        
        # Set pragmas for better performance
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA cache_size = 100000")
        conn.execute("PRAGMA temp_store = MEMORY")
        conn.execute("PRAGMA mmap_size = 30000000000")  # 30GB memory mapping
        
        # Create tables
        logger.info("Creating database schema...")
        
        # Primary case table with metadata
        conn.execute("""
        CREATE TABLE cases (
            id TEXT PRIMARY KEY,
            file_name TEXT NOT NULL,
            cid TEXT,
            secondary_cid TEXT,
            court TEXT,
            jurisdiction TEXT,
            decision_date TEXT,
            name_abbreviation TEXT
        )
        """)
        
        # CID lookup index
        conn.execute("""
        CREATE TABLE cid_index (
            cid TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            file_name TEXT NOT NULL,
            FOREIGN KEY (case_id) REFERENCES cases(id)
        )
        """)
        
        # Secondary CID lookup index
        conn.execute("""
        CREATE TABLE secondary_cid_index (
            secondary_cid TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            file_name TEXT NOT NULL,
            FOREIGN KEY (case_id) REFERENCES cases(id)
        )
        """)
        
        # Case types table
        conn.execute("""
        CREATE TABLE case_types (
            case_id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            confidence REAL,
            FOREIGN KEY (case_id) REFERENCES cases(id)
        )
        """)
        
        # Create initial indexes for efficient insertion
        logger.info("Creating initial indexes...")
        conn.execute("CREATE INDEX idx_cases_file_name ON cases(file_name)")
        
        conn.commit()
        conn.close()
        
        logger.info(f"Database created successfully: {db_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error creating database: {e}")
        return False

def get_parquet_files(parquet_dir):
    """
    Get a list of all parquet files in the specified directory.
    
    Args:
        parquet_dir: Directory containing parquet files
    
    Returns:
        List of parquet file paths
    """
    # Verify directory exists
    if not os.path.exists(parquet_dir):
        logger.error(f"Parquet directory not found: {parquet_dir}")
        return []
    
    # Find all parquet files
    parquet_files = glob.glob(os.path.join(parquet_dir, "*.parquet"))
    logger.info(f"Found {len(parquet_files)} parquet files in {parquet_dir}")
    
    return parquet_files

def process_parquet_file(args):
    """
    Process a single parquet file and extract case metadata.
    Designed for parallel processing.
    
    Args:
        args: Tuple containing (file_path, file_idx)
        
    Returns:
        Tuple of (cases_data, cids_data, secondary_cids_data, case_types_data, error_count, empty_ids)
    """
    file_path, file_idx = args
    file_name = os.path.basename(file_path)
    
    # Track statistics
    error_count = 0
    empty_ids = 0
    
    # Data to return
    cases_data = []
    cids_data = []
    secondary_cids_data = []
    case_types_data = []
    
    try:
        # Read the parquet file
        df = pd.read_parquet(file_path)
        
        # Process each case
        for _, row in df.iterrows():
            try:
                # Extract case ID (ensuring it's a string)
                case_id = str(row.get('id', ''))
                
                # Handle empty case IDs
                if not case_id or case_id.lower() in ('nan', 'none', 'null'):
                    empty_ids += 1
                    continue
                
                # Get other fields, handling potential NaN values
                cid = str(row.get('cid', '')) if pd.notna(row.get('cid')) else ''
                secondary_cid = str(row.get('secondary_cid', '')) if pd.notna(row.get('secondary_cid')) else ''
                court = str(row.get('court', '')) if pd.notna(row.get('court')) else ''
                jurisdiction = str(row.get('jurisdiction', '')) if pd.notna(row.get('jurisdiction')) else ''
                decision_date = str(row.get('decision_date', '')) if pd.notna(row.get('decision_date')) else ''
                name_abbreviation = str(row.get('name_abbreviation', '')) if pd.notna(row.get('name_abbreviation')) else ''
                text = str(row.get('text', '')) if pd.notna(row.get('text')) else ''
                
                # Add to cases data
                cases_data.append((
                    case_id,
                    file_name,
                    cid,
                    secondary_cid,
                    court,
                    jurisdiction,
                    decision_date,
                    name_abbreviation
                ))
                
                # Add to CID index if present
                if cid:
                    cids_data.append((cid, case_id, file_name))
                
                # Add to secondary CID index if present
                if secondary_cid:
                    secondary_cids_data.append((secondary_cid, case_id, file_name))
                
                # Classify the case
                case_type, confidence = classify_case(
                    text, 
                    name_abbreviation, 
                    court, 
                    jurisdiction
                )
                
                # Add to case types data
                case_types_data.append((case_id, case_type, confidence))
                
            except Exception as e:
                error_count += 1
                if error_count <= 5:  # Limit error messages
                    logger.warning(f"Error processing case in {file_name}: {e}")
    
    except Exception as e:
        logger.error(f"Error processing file {file_name}: {e}")
        error_count += 1
    
    return (cases_data, cids_data, secondary_cids_data, case_types_data, error_count, empty_ids)

def insert_batch_data(conn, table, columns, data_batch):
    """
    Insert a batch of data into a SQLite table.
    
    Args:
        conn: SQLite connection
        table: Table name
        columns: Column names
        data_batch: List of data tuples to insert
        
    Returns:
        Number of rows inserted
    """
    if not data_batch:
        return 0
    
    try:
        placeholders = ', '.join(['?'] * len(columns))
        columns_str = ', '.join(columns)
        
        query = f"INSERT OR IGNORE INTO {table} ({columns_str}) VALUES ({placeholders})"
        conn.executemany(query, data_batch)
        
        return len(data_batch)
    except Exception as e:
        logger.error(f"Error inserting batch data into {table}: {e}")
        return 0

def create_final_indexes(db_path):
    """
    Create the final indexes on the database for efficient queries.
    
    Args:
        db_path: Path to the SQLite database
        
    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info("Creating final indexes for optimized queries...")
        
        conn = sqlite3.connect(db_path)
        
        # Create indexes for cases table
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_cases_court ON cases(court)",
            "CREATE INDEX IF NOT EXISTS idx_cases_jurisdiction ON cases(jurisdiction)",
            "CREATE INDEX IF NOT EXISTS idx_cases_decision_date ON cases(decision_date)",
            
            # Create indexes for cid_index table
            "CREATE INDEX IF NOT EXISTS idx_cid_index_case_id ON cid_index(case_id)",
            "CREATE INDEX IF NOT EXISTS idx_cid_index_file_name ON cid_index(file_name)",
            
            # Create indexes for secondary_cid_index table
            "CREATE INDEX IF NOT EXISTS idx_secondary_cid_index_case_id ON secondary_cid_index(case_id)",
            "CREATE INDEX IF NOT EXISTS idx_secondary_cid_index_file_name ON secondary_cid_index(file_name)",
            
            # Create index for case_types table
            "CREATE INDEX IF NOT EXISTS idx_case_types_type ON case_types(type)"
        ]
        
        for index_cmd in indexes:
            logger.info(f"Creating index: {index_cmd}")
            conn.execute(index_cmd)
        
        # Analyze for better query planning
        conn.execute("ANALYZE")
        
        conn.commit()
        conn.close()
        
        return True
    
    except Exception as e:
        logger.error(f"Error creating final indexes: {e}")
        return False

def analyze_database(db_path):
    """
    Analyze the final database to provide statistics.
    
    Args:
        db_path: Path to the SQLite database
        
    Returns:
        Dictionary with database statistics
    """
    stats = {}
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get count of cases
        cursor.execute("SELECT COUNT(*) FROM cases")
        stats["total_cases"] = cursor.fetchone()[0]
        
        # Get count of CIDs
        cursor.execute("SELECT COUNT(*) FROM cid_index")
        stats["total_cids"] = cursor.fetchone()[0]
        
        # Get count of secondary CIDs
        cursor.execute("SELECT COUNT(*) FROM secondary_cid_index")
        stats["total_secondary_cids"] = cursor.fetchone()[0]
        
        # Get count of case types
        cursor.execute("SELECT COUNT(*) FROM case_types")
        stats["total_case_types"] = cursor.fetchone()[0]
        
        # Get case type distribution
        cursor.execute("SELECT type, COUNT(*) FROM case_types GROUP BY type")
        type_counts = cursor.fetchall()
        stats["case_type_distribution"] = {case_type: count for case_type, count in type_counts}
        
        # Get unique courts count
        cursor.execute("SELECT COUNT(DISTINCT court) FROM cases")
        stats["unique_courts"] = cursor.fetchone()[0]
        
        # Get unique jurisdictions count
        cursor.execute("SELECT COUNT(DISTINCT jurisdiction) FROM cases")
        stats["unique_jurisdictions"] = cursor.fetchone()[0]
        
        # Get date range
        cursor.execute("SELECT MIN(decision_date), MAX(decision_date) FROM cases WHERE decision_date != ''")
        min_date, max_date = cursor.fetchone()
        stats["date_range"] = (min_date, max_date)
        
        # Get database size
        cursor.execute("PRAGMA page_count")
        page_count = cursor.fetchone()[0]
        cursor.execute("PRAGMA page_size")
        page_size = cursor.fetchone()[0]
        stats["db_size_bytes"] = page_count * page_size
        
        conn.close()
        
        return stats
    
    except Exception as e:
        logger.error(f"Error analyzing database: {e}")
        return {"error": str(e)}

def validate_database(db_path, parquet_dir, sample_size=20):
    """
    Validate the database against original parquet files.
    
    Args:
        db_path: Path to the SQLite database
        parquet_dir: Directory containing parquet files
        sample_size: Number of cases to validate
        
    Returns:
        Tuple of (validation_success, details)
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Sample random cases
        cursor.execute(f"SELECT id, file_name FROM cases ORDER BY RANDOM() LIMIT {sample_size}")
        sample_cases = cursor.fetchall()
        
        validation_results = []
        
        for case_id, file_name in sample_cases:
            # Get case details from database
            cursor.execute("SELECT court, jurisdiction, decision_date FROM cases WHERE id = ?", (case_id,))
            db_case = cursor.fetchone()
            
            if not db_case:
                validation_results.append({
                    "case_id": case_id,
                    "file_name": file_name,
                    "success": False,
                    "error": "Case not found in database"
                })
                continue
            
            db_court, db_jurisdiction, db_decision_date = db_case
            
            # Get case type
            cursor.execute("SELECT type, confidence FROM case_types WHERE case_id = ?", (case_id,))
            case_type_row = cursor.fetchone()
            db_case_type = case_type_row[0] if case_type_row else None
            db_confidence = case_type_row[1] if case_type_row else None
            
            # Get case from parquet file
            file_path = os.path.join(parquet_dir, file_name)
            
            if not os.path.exists(file_path):
                validation_results.append({
                    "case_id": case_id,
                    "file_name": file_name,
                    "success": False,
                    "error": "Parquet file not found"
                })
                continue
            
            try:
                df = pd.read_parquet(file_path)
                parquet_case = df[df['id'].astype(str) == case_id]
                
                if parquet_case.empty:
                    validation_results.append({
                        "case_id": case_id,
                        "file_name": file_name,
                        "success": False,
                        "error": "Case not found in parquet file"
                    })
                    continue
                
                # Get values from parquet (handling potential NaN)
                parquet_row = parquet_case.iloc[0]
                parquet_court = str(parquet_row.get('court', '')) if pd.notna(parquet_row.get('court')) else ''
                parquet_jurisdiction = str(parquet_row.get('jurisdiction', '')) if pd.notna(parquet_row.get('jurisdiction')) else ''
                parquet_decision_date = str(parquet_row.get('decision_date', '')) if pd.notna(parquet_row.get('decision_date')) else ''
                
                # Compare values
                fields_match = (
                    db_court == parquet_court and
                    db_jurisdiction == parquet_jurisdiction and
                    db_decision_date == parquet_decision_date
                )
                
                validation_results.append({
                    "case_id": case_id,
                    "file_name": file_name,
                    "success": fields_match,
                    "case_type": db_case_type,
                    "confidence": db_confidence,
                    "db_values": {
                        "court": db_court,
                        "jurisdiction": db_jurisdiction,
                        "decision_date": db_decision_date
                    },
                    "parquet_values": {
                        "court": parquet_court,
                        "jurisdiction": parquet_jurisdiction,
                        "decision_date": parquet_decision_date
                    } if not fields_match else "matches"
                })
                
            except Exception as e:
                validation_results.append({
                    "case_id": case_id,
                    "file_name": file_name,
                    "success": False,
                    "error": f"Error processing parquet file: {e}"
                })
        
        conn.close()
        
        # Check overall success
        success_count = sum(1 for result in validation_results if result["success"])
        overall_success = success_count / len(validation_results) if validation_results else 0
        
        return (overall_success >= 0.95, validation_results)
    
    except Exception as e:
        logger.error(f"Error validating database: {e}")
        return (False, {"error": str(e)})

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Create SQLite index for Caselaw Access Project parquet files")
    parser.add_argument("--db", default="./case_lookup.db", help="Path for the SQLite database")
    parser.add_argument("--parquet-dir", required=True, help="Directory containing parquet files")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing database")
    parser.add_argument("--workers", type=int, default=multiprocessing.cpu_count(), help="Number of parallel workers")
    parser.add_argument("--batch-size", type=int, default=10000, help="Batch size for database insertions")
    parser.add_argument("--stats-output", default="db_stats.json", help="File to save database statistics")
    parser.add_argument("--skip-validation", action="store_true", help="Skip database validation")
    parser.add_argument("--limit", type=int, help="Limit the number of parquet files processed (for testing)")
    
    args = parser.parse_args()
    
    start_time = time.time()
    
    # Display options
    logger.info(f"Database path: {args.db}")
    logger.info(f"Parquet directory: {args.parquet_dir}")
    logger.info(f"Using {args.workers} parallel workers")
    logger.info(f"Batch size: {args.batch_size}")
    
    # Check if database path is valid
    db_dir = os.path.dirname(os.path.abspath(args.db))
    if not os.path.exists(db_dir):
        logger.error(f"Database directory does not exist: {db_dir}")
        return 1
    
    # Create new database
    if not setup_database(args.db, args.overwrite):
        return 1
    
    # Get list of parquet files
    parquet_files = get_parquet_files(args.parquet_dir)
    if not parquet_files:
        return 1
    
    # Limit files if requested
    if args.limit and args.limit < len(parquet_files):
        logger.info(f"Limiting to {args.limit} files (out of {len(parquet_files)})")
        parquet_files = parquet_files[:args.limit]
    
    # Prepare files for processing
    file_args = [(f, i) for i, f in enumerate(parquet_files)]
    
    # Process parquet files in parallel
    logger.info(f"Processing {len(parquet_files)} parquet files with {args.workers} workers...")
    
    # Track overall statistics
    total_cases = 0
    total_cids = 0
    total_secondary_cids = 0
    total_case_types = 0
    total_errors = 0
    total_empty_ids = 0
    
    # Track case type distribution
    case_type_counts = Counter()
    
    # Connect to database for batch inserts
    conn = sqlite3.connect(args.db)
    
    # Set pragmas for better performance
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = 100000")
    conn.execute("PRAGMA temp_store = MEMORY")
    
    # Begin transaction
    conn.execute("BEGIN TRANSACTION")
    
    # Track batch data
    cases_batch = []
    cids_batch = []
    secondary_cids_batch = []
    case_types_batch = []
    
    # Process files using ProcessPoolExecutor
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(process_parquet_file, arg) for arg in file_args]
        
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Processing files"):
            try:
                cases_data, cids_data, secondary_cids_data, case_types_data, error_count, empty_ids = future.result()
                
                # Add to statistics
                total_cases += len(cases_data)
                total_cids += len(cids_data)
                total_secondary_cids += len(secondary_cids_data)
                total_case_types += len(case_types_data)
                total_errors += error_count
                total_empty_ids += empty_ids
                
                # Track case type distribution
                for _, case_type, _ in case_types_data:
                    case_type_counts[case_type] += 1
                
                # Add to batches
                cases_batch.extend(cases_data)
                cids_batch.extend(cids_data)
                secondary_cids_batch.extend(secondary_cids_data)
                case_types_batch.extend(case_types_data)
                
                # Insert batches when they reach the batch size
                if len(cases_batch) >= args.batch_size:
                    insert_batch_data(conn, "cases", 
                                     ["id", "file_name", "cid", "secondary_cid", "court", "jurisdiction", "decision_date", "name_abbreviation"], 
                                     cases_batch)
                    cases_batch = []
                
                if len(cids_batch) >= args.batch_size:
                    insert_batch_data(conn, "cid_index", ["cid", "case_id", "file_name"], cids_batch)
                    cids_batch = []
                
                if len(secondary_cids_batch) >= args.batch_size:
                    insert_batch_data(conn, "secondary_cid_index", ["secondary_cid", "case_id", "file_name"], secondary_cids_batch)
                    secondary_cids_batch = []
                
                if len(case_types_batch) >= args.batch_size:
                    insert_batch_data(conn, "case_types", ["case_id", "type", "confidence"], case_types_batch)
                    case_types_batch = []
                
                # Periodically commit to avoid transaction getting too large
                if total_cases % (args.batch_size * 10) == 0:
                    conn.commit()
                    conn.execute("BEGIN TRANSACTION")
                    logger.info(f"Progress: {total_cases:,} cases processed")
                    logger.info(f"Case type distribution: {dict(case_type_counts)}")
                
            except Exception as e:
                logger.error(f"Error processing file batch: {e}")
                total_errors += 1
    
    # Insert any remaining batches
    if cases_batch:
        insert_batch_data(conn, "cases", 
                         ["id", "file_name", "cid", "secondary_cid", "court", "jurisdiction", "decision_date", "name_abbreviation"], 
                         cases_batch)
    
    if cids_batch:
        insert_batch_data(conn, "cid_index", ["cid", "case_id", "file_name"], cids_batch)
    
    if secondary_cids_batch:
        insert_batch_data(conn, "secondary_cid_index", ["secondary_cid", "case_id", "file_name"], secondary_cids_batch)
    
    if case_types_batch:
        insert_batch_data(conn, "case_types", ["case_id", "type", "confidence"], case_types_batch)
    
    # Commit the transaction
    conn.commit()
    conn.close()
    
    processing_time = time.time() - start_time
    logger.info(f"Processing completed in {processing_time:.2f} seconds")
    logger.info(f"Processed {len(parquet_files):,} files with {total_errors:,} errors")
    logger.info(f"Inserted {total_cases:,} cases, {total_cids:,} CIDs, and {total_secondary_cids:,} secondary CIDs")
    logger.info(f"Classified {total_case_types:,} cases by type")
    logger.info(f"Found {total_empty_ids:,} empty case IDs (skipped)")
    logger.info(f"Case type distribution: {dict(case_type_counts)}")
    
    # Create final indexes
    if not create_final_indexes(args.db):
        logger.error("Failed to create final indexes")
        return 1
    
    # Analyze database
    logger.info("Analyzing database...")
    stats = analyze_database(args.db)
    
    # Save stats to file
    with open(args.stats_output, 'w') as f:
        json.dump({
            "processing_stats": {
                "files_processed": len(parquet_files),
                "processing_time_seconds": processing_time,
                "cases_processed": total_cases,
                "cids_processed": total_cids,
                "secondary_cids_processed": total_secondary_cids,
                "case_types_processed": total_case_types,
                "case_type_distribution": dict(case_type_counts),
                "errors": total_errors,
                "empty_ids_skipped": total_empty_ids
            },
            "database_stats": stats
        }, f, indent=2)
    
    logger.info(f"Statistics saved to {args.stats_output}")
    
    # Validate database
    if not args.skip_validation:
        logger.info("Validating database against original parquet files...")
        validation_success, validation_details = validate_database(args.db, args.parquet_dir)
        
        if validation_success:
            logger.info("Database validation successful")
        else:
            logger.warning("Database validation found issues")
            logger.warning(f"Validation details: {validation_details}")
    
    total_time = time.time() - start_time
    logger.info(f"Total time: {total_time:.2f} seconds")
    logger.info("Database creation completed successfully")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())