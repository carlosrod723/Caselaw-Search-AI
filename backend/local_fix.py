# backend/local_fix.py
"""
Script to apply local development fixes to the backend.
"""

import os
import fileinput
import re
import sys

def patch_qdrant_service():
    """Patch the qdrant_service.py file to ensure local development works correctly."""
    file_path = "app/services/qdrant_service.py"
    
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found. Make sure you're in the backend directory.")
        return False
    
    # Create a backup
    backup_path = f"{file_path}.bak"
    os.system(f"cp {file_path} {backup_path}")
    print(f"Created backup at {backup_path}")
    
    # Patterns to find and replace
    replacements = [
        # Force explicit local connection
        (r'host=settings\.QDRANT_HOST', 'host="localhost"'),
        
        # Increase timeout values
        (r'DEFAULT_TIMEOUT = 120\.0', 'DEFAULT_TIMEOUT = 300.0'),
        (r'QUICK_SEARCH_TIMEOUT = 30\.0', 'QUICK_SEARCH_TIMEOUT = 120.0'),
        
        # Add more retry attempts
        (r'stop=stop_after_attempt\(5\)', 'stop=stop_after_attempt(10)'),
    ]
    
    # Apply the fixes
    for pattern, replacement in replacements:
        with fileinput.input(file_path, inplace=True) as file:
            for line in file:
                new_line = re.sub(pattern, replacement, line)
                sys.stdout.write(new_line)
    
    print(f"Successfully patched {file_path} for local development")
    return True

if __name__ == "__main__":
    patch_qdrant_service()