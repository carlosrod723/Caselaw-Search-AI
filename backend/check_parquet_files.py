#!/usr/bin/env python3
"""
Check what parquet files actually exist in the directory.
"""

import os
import argparse
import glob

def main():
    parser = argparse.ArgumentParser(description="Check parquet files in directory")
    parser.add_argument("--dir", required=True, help="Directory to check")
    args = parser.parse_args()

    base_dir = args.dir
    
    if not os.path.exists(base_dir):
        print(f"ERROR: Directory does not exist: {base_dir}")
        return
    
    print(f"Checking directory: {base_dir}")
    
    # Look for parquet files
    parquet_pattern = os.path.join(base_dir, "*.parquet")
    parquet_files = glob.glob(parquet_pattern)
    
    print(f"Found {len(parquet_files)} parquet files")
    
    # Look for other files matching potential naming conventions
    patterns_to_check = [
        "file_*",
        "TeraflopAI___*",
        "*_4284*",
        "*4284*"
    ]
    
    for pattern in patterns_to_check:
        file_pattern = os.path.join(base_dir, pattern)
        matching_files = glob.glob(file_pattern)
        
        if matching_files:
            print(f"\nFiles matching pattern '{pattern}':")
            for file in matching_files[:10]:  # Show first 10 only if many
                print(f"  {os.path.basename(file)}")
            
            if len(matching_files) > 10:
                print(f"  ... and {len(matching_files) - 10} more")
    
    # List a sample of files in the directory to identify naming patterns
    all_files = os.listdir(base_dir)[:20]  # List a sample of files
    
    if all_files:
        print("\nSample of files in directory:")
        for file in all_files:
            print(f"  {file}")
    
    # Check if we can infer the correct file name for file_4284
    for file in all_files:
        if "4284" in file:
            print(f"\nPossible match for file_4284: {file}")
            expected_path = os.path.join(base_dir, "file_4284")
            actual_path = os.path.join(base_dir, file)
            print(f"Expected path: {expected_path}")
            print(f"Actual path: {actual_path}")

if __name__ == "__main__":
    main()