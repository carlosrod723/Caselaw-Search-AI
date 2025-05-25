#!/usr/bin/env python3
"""
Diagnostic script to verify parquet file access.
This script attempts to read a specific parquet file and case to diagnose issues.

Usage:
  python parquet_diagnostic.py --file FILE_PATH [--cid CID] [--case-id CASE_ID]
"""

import os
import argparse
import pandas as pd
import pyarrow as pa

def main():
    parser = argparse.ArgumentParser(description="Test parquet file access")
    parser.add_argument("--file", required=True, help="Parquet file to test")
    parser.add_argument("--cid", help="Content ID to look for")
    parser.add_argument("--case-id", help="Case ID to look for")
    args = parser.parse_args()

    file_path = args.file
    
    print(f"Testing parquet file access for: {file_path}")
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"ERROR: File does not exist: {file_path}")
        return
    
    # Get file size
    file_size = os.path.getsize(file_path)
    print(f"File size: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
    
    # Print Python, pandas, and pyarrow versions
    print(f"Python version: {pd.__version__}")
    print(f"PyArrow version: {pa.__version__}")
    
    # Try reading metadata only
    try:
        print("\nReading file metadata...")
        file_info = pd.read_parquet(file_path, columns=None)
        print(f"File contains {len(file_info):,} rows and {len(file_info.columns)} columns")
        print(f"Columns: {file_info.columns.tolist()}")
    except Exception as e:
        print(f"ERROR reading metadata: {e}")
        return
    
    # Try reading a specific CID if provided
    if args.cid:
        try:
            print(f"\nLooking for CID: {args.cid}")
            df = pd.read_parquet(file_path, filters=[("cid", "=", args.cid)])
            
            if df.empty:
                print(f"CID {args.cid} not found in file")
            else:
                print(f"Found CID {args.cid}:")
                for col in df.columns:
                    value = df.iloc[0][col]
                    if col == 'text':
                        print(f"  {col}: {len(value)} characters")
                    else:
                        print(f"  {col}: {value}")
        except Exception as e:
            print(f"ERROR finding CID: {e}")
    
    # Try reading a specific case_id if provided
    if args.case_id:
        try:
            print(f"\nLooking for case_id: {args.case_id}")
            df = pd.read_parquet(file_path, filters=[("case_id", "=", args.case_id)])
            
            if df.empty:
                print(f"Case ID {args.case_id} not found in file")
            else:
                print(f"Found case_id {args.case_id}:")
                for col in df.columns:
                    value = df.iloc[0][col]
                    if col == 'text':
                        print(f"  {col}: {len(value)} characters")
                    else:
                        print(f"  {col}: {value}")
        except Exception as e:
            print(f"ERROR finding case_id: {e}")
    
    # Try reading sample rows
    try:
        print("\nReading sample rows...")
        sample = pd.read_parquet(file_path).head(2)
        for i, row in sample.iterrows():
            print(f"\nROW {i+1}:")
            for col in row.index:
                if col == 'text':
                    print(f"  {col}: {len(row[col])} characters")
                else:
                    print(f"  {col}: {row[col]}")
    except Exception as e:
        print(f"ERROR reading sample rows: {e}")

if __name__ == "__main__":
    main()