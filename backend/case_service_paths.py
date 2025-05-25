# case_service_paths.py

"""
Script to fix the paths in case_document_service.py for local development.
"""

import os
import fileinput
import sys

def fix_case_service_paths():
    """Fix the paths in case_document_service.py to use the correct SQLite and parquet locations."""
    file_path = "app/services/case_document_service.py"
    
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found. Make sure you're in the backend directory.")
        return False
    
    # Create a backup
    backup_path = f"{file_path}.bak2"
    os.system(f"cp {file_path} {backup_path}")
    print(f"Created backup at {backup_path}")
    
    # Get absolute paths - adjust these to your actual locations
    sqlite_db_path = os.path.abspath("../Qdrant-Test/case_lookup.db")
    parquet_dir = os.path.abspath("../Qdrant-Test/caselaw_processing/downloads/datasets--laion--Caselaw_Access_Project_embeddings/snapshots/7777999929157e8a2fe1b5d65f1d9cfd2092e843/TeraflopAI___Caselaw_Access_Project_clusters")
    
    print(f"Using SQLite DB path: {sqlite_db_path}")
    print(f"Using parquet directory: {parquet_dir}")
    
    # Apply the fixes
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Replace the paths
    updated_content = content.replace('self.sqlite_db_path = os.path.join(self.base_dir, "case_lookup.db")', 
                                    f'self.sqlite_db_path = "{sqlite_db_path}"')
    
    updated_content = updated_content.replace('self.full_text_dir = os.path.join(self.base_dir, "caselaw_processing/downloads/datasets--laion--Caselaw_Access_Project_embeddings/snapshots/7777999929157e8a2fe1b5d65f1d9cfd2092e843/TeraflopAI___Caselaw_Access_Project_clusters")', 
                                           f'self.full_text_dir = "{parquet_dir}"')
    
    # Write the updated content
    with open(file_path, 'w') as f:
        f.write(updated_content)
    
    print(f"Successfully updated paths in {file_path}")
    return True

if __name__ == "__main__":
    fix_case_service_paths()