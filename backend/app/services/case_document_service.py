# app/services/case_document_service.py
import os
import json
import logging
import re
from typing import Dict, Any, Optional
import sqlite3
import pandas as pd
import pyarrow.parquet as pq

# Set up logging
logger = logging.getLogger(__name__)

class CaseDocumentService:
    def __init__(self):
        # Base paths
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        # Local paths - use the database in the current directory
        self.sqlite_db_path = os.path.join(self.base_dir, "case_lookup.db")
        
        # Full text directory (local path to your parquet files)
        self.full_text_dir = "/Users/josecarlosrodriguez/Desktop/Carlos-Projects/Qdrant-Test/caselaw_processing/downloads/datasets--laion--Caselaw_Access_Project_embeddings/snapshots/7777999929157e8a2fe1b5d65f1d9cfd2092e843/TeraflopAI___Caselaw_Access_Project_clusters"
        
        # Cache for frequently accessed parquet files
        self._df_cache = {}
        self._cache_size_limit = 10  # Limit cache to 10 files to manage memory usage
        
        logger.info(f"Using SQLite database: {self.sqlite_db_path}")
        logger.info(f"Using parquet directory: {self.full_text_dir}")
        
        # Ensure database exists
        if not os.path.exists(self.sqlite_db_path):
            logger.error(f"SQLite database not found at {self.sqlite_db_path}")
    
    def _get_parquet_file_path(self, file_name: str) -> str:
        """
        Get the full path to a parquet file.
        
        Args:
            file_name: Name of the parquet file
            
        Returns:
            Full path to the parquet file
        """
        return os.path.join(self.full_text_dir, file_name)
    
    def _load_parquet_file(self, file_path: str) -> Optional[pd.DataFrame]:
        """
        Load a parquet file, using cache when possible.
        
        Args:
            file_path: Path to the parquet file
            
        Returns:
            DataFrame containing the parquet file data, or None if an error occurs
        """
        # Check if file is in cache
        if file_path in self._df_cache:
            return self._df_cache[file_path]
        
        try:
            # Read the parquet file
            df = pd.read_parquet(file_path)
            
            # Add to cache if there's room
            if len(self._df_cache) < self._cache_size_limit:
                self._df_cache[file_path] = df
            # If cache is full, remove oldest entry
            elif self._df_cache:
                oldest_key = next(iter(self._df_cache))
                del self._df_cache[oldest_key]
                self._df_cache[file_path] = df
                
            return df
        except Exception as e:
            logger.error(f"Error reading parquet file {file_path}: {e}")
            return None
    
    def get_case_by_id(self, case_id: str, full_text: bool = False) -> Optional[Dict[str, Any]]:
        """
        Retrieve a case by its ID.
        
        Args:
            case_id: The ID of the case to retrieve
            full_text: Whether to retrieve the full text (default: False)
        
        Returns:
            A dictionary containing the case data, or None if the case could not be found
        """
        logger.info(f"Looking for case with ID: {case_id} (full_text: {full_text})")
        
        try:
            # Connect to SQLite database
            conn = sqlite3.connect(self.sqlite_db_path)
            cursor = conn.cursor()
            
            # Query to find the case and its parquet file
            cursor.execute("""
                SELECT id, file_name, court, jurisdiction, decision_date, name_abbreviation
                FROM cases 
                WHERE id = ?
            """, (case_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                logger.warning(f"Case with ID {case_id} not found in database")
                return None
            
            # Extract case metadata from the database
            db_id, file_name, court, jurisdiction, decision_date, name_abbreviation = result
            
            # Get the full path to the parquet file
            full_path = self._get_parquet_file_path(file_name)
            
            # Check if the file exists
            if not os.path.exists(full_path):
                logger.warning(f"Parquet file not found: {file_name}")
                return None
            
            # Load the parquet file
            df = self._load_parquet_file(full_path)
            if df is None:
                return None
            
            # Find the case in the parquet file
            case_row = df[df['id'].astype(str) == str(case_id)]
            
            if case_row.empty:
                logger.warning(f"Case ID {case_id} not found in file {file_name} despite being in the database")
                return None
            
            # Get the first (and should be only) matching row
            case_data_row = case_row.iloc[0]
            
            # Ensure values are not NaN
            def safe_get(row, col, default=''):
                val = row.get(col, default)
                return val if pd.notna(val) else default
            
            # Build case data dictionary
            case_data = {
                "id": str(case_id),
                "name_abbreviation": safe_get(case_data_row, 'name_abbreviation', name_abbreviation),
                "court": safe_get(case_data_row, 'court', court),
                "decision_date": safe_get(case_data_row, 'decision_date', decision_date),
                "jurisdiction": safe_get(case_data_row, 'jurisdiction', jurisdiction),
                "judges": safe_get(case_data_row, 'judges'),
                "cid": safe_get(case_data_row, 'cid'),
                "is_full_content": full_text
            }
            
            # Add text based on full_text parameter
            if full_text:
                case_data["text"] = safe_get(case_data_row, 'text')
                text_length = len(case_data["text"])
                logger.info(f"Retrieved full text for case ID {case_id} ({text_length} chars)")
            else:
                # For snippet, use snippet field if it exists, otherwise use first 500 chars of text
                if 'snippet' in case_data_row:
                    case_data["text"] = safe_get(case_data_row, 'snippet')
                else:
                    full_text = safe_get(case_data_row, 'text')
                    case_data["text"] = full_text[:500] + "..." if len(full_text) > 500 else full_text
            
            return case_data
            
        except Exception as e:
            logger.error(f"Error retrieving case by ID {case_id}: {e}")
            return None
    
    def get_case_by_cid(self, cid: str, full_text: bool = False) -> Optional[Dict[str, Any]]:
        """
        Retrieve a case by its CID.
        
        Args:
            cid: The CID of the case to retrieve
            full_text: Whether to retrieve the full text (default: False)
        
        Returns:
            A dictionary containing the case data, or None if the case could not be found
        """
        logger.info(f"Looking for case with CID: {cid} (full_text: {full_text})")
        
        try:
            # Connect to SQLite database
            conn = sqlite3.connect(self.sqlite_db_path)
            cursor = conn.cursor()
            
            # First try the primary CID index
            cursor.execute("SELECT case_id FROM cid_index WHERE cid = ?", (cid,))
            result = cursor.fetchone()
            
            # If not found, try the secondary CID index
            if not result:
                cursor.execute("SELECT case_id FROM secondary_cid_index WHERE secondary_cid = ?", (cid,))
                result = cursor.fetchone()
            
            conn.close()
            
            if not result:
                logger.warning(f"Case with CID {cid} not found in database")
                return None
            
            # Get the case ID and retrieve the case
            case_id = result[0]
            return self.get_case_by_id(case_id, full_text)
            
        except Exception as e:
            logger.error(f"Error retrieving case by CID {cid}: {e}")
            return None

    def generate_pdf(self, case_id: str) -> Optional[bytes]:
        """
        Generate a PDF for a case.
        
        Args:
            case_id: The ID of the case to generate a PDF for
            
        Returns:
            The PDF content as bytes, or None if the PDF could not be generated
        """
        logger.info(f"Generating PDF for case ID: {case_id}")
        
        try:
            # First, get the full case data
            case_data = self.get_case_by_id(case_id, full_text=True)
            
            if not case_data:
                logger.warning(f"Cannot generate PDF: Case ID {case_id} not found")
                return None
            
            # PDF generation code to be implemented
            # For now, log a warning
            logger.warning("PDF generation not yet implemented")
            return None
            
        except Exception as e:
            logger.error(f"Error generating PDF for case ID {case_id}: {e}")
            return None

# Create singleton instance
case_document_service = CaseDocumentService()