#!/usr/bin/env python
"""
Tool to inspect the case_lookup.db SQLite database structure and content.
This helps verify the data integrity and structure, including the new case_types table.

Usage:
  python inspect_new_sqlite_database.py

Options:
  --table=<name>    Show specific table schema and sample data
  --search=<text>   Search for cases containing specific text in title
  --limit=<num>     Limit number of results (default: 10)
  --case-id=<id>    Look up a specific case by ID
  --case-type=<type> Show distribution and examples for specific case type
"""

import os
import sys
import sqlite3
import json
from collections import defaultdict

# Set up basic output formatting
def print_header(text):
    print("\n" + "=" * 80)
    print(f" {text} ".center(80, "="))
    print("=" * 80)

def print_section(text):
    print("\n" + "-" * 80)
    print(f" {text} ".center(80, "-"))
    print("-" * 80)

def connect_to_db():
    """Connect to the SQLite database"""
    db_path = os.path.join(os.getcwd(), "case_lookup.db")
    print(f"Connecting to database at: {db_path}")
    
    if not os.path.exists(db_path):
        print(f"ERROR: Database file not found at {db_path}")
        sys.exit(1)
    
    return sqlite3.connect(db_path)

def get_table_info(conn):
    """Get list of tables and their schemas"""
    cursor = conn.cursor()
    
    # Get list of tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [row[0] for row in cursor.fetchall()]
    
    table_info = {}
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table});")
        columns = cursor.fetchall()
        table_info[table] = columns
    
    return tables, table_info

def show_schema(conn):
    """Show database schema"""
    tables, table_info = get_table_info(conn)
    
    print_header("DATABASE SCHEMA")
    
    for table in tables:
        print(f"\nTable: {table}")
        print("-" * 40)
        
        # Print column information
        print(f"{'Column':<20} {'Type':<10} {'NotNull':<8} {'PK':<5} {'Default':<15}")
        print("-" * 60)
        
        for col in table_info[table]:
            cid, name, dtype, notnull, default_val, pk = col
            print(f"{name:<20} {dtype:<10} {notnull:<8} {pk:<5} {str(default_val):<15}")
        
        # Print sample data
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table} LIMIT 5;")
        rows = cursor.fetchall()
        
        if rows:
            print("\nSample data:")
            for row in rows:
                print(f"  {row}")

def inspect_case_relationships(conn):
    """Check relationships between cases, CIDs, and file paths"""
    cursor = conn.cursor()
    print_header("CASE RELATIONSHIP INSPECTION")
    
    # Check for cases with multiple CIDs
    try:
        cursor.execute("""
            SELECT case_id, COUNT(*) as cid_count
            FROM cid_index
            GROUP BY case_id
            HAVING COUNT(*) > 1
            LIMIT 10;
        """)
        rows = cursor.fetchall()
        
        if rows:
            print("\nCases with multiple CIDs:")
            print(f"{'Case ID':<15} {'CID Count':<10}")
            print("-" * 30)
            for row in rows:
                print(f"{row[0]:<15} {row[1]:<10}")
        else:
            print("\nNo cases with multiple CIDs found.")
    except sqlite3.OperationalError:
        print("\nCouldn't check for multiple CIDs (table structure may be different)")
    
    # Check for CIDs with multiple cases (shouldn't happen)
    try:
        cursor.execute("""
            SELECT cid, COUNT(*) as case_count
            FROM cid_index
            GROUP BY cid
            HAVING COUNT(*) > 1
            LIMIT 10;
        """)
        rows = cursor.fetchall()
        
        if rows:
            print("\nCIDs associated with multiple cases (potential issue):")
            print(f"{'CID':<15} {'Case Count':<10}")
            print("-" * 30)
            for row in rows:
                print(f"{row[0]:<15} {row[1]:<10}")
        else:
            print("\nNo CIDs with multiple cases found (good).")
    except sqlite3.OperationalError:
        print("\nCouldn't check for duplicate case mappings (table structure may be different)")

def search_cases(conn, search_term, limit=10):
    """Search for cases containing the specified text in title"""
    cursor = conn.cursor()
    print_header(f"SEARCH RESULTS FOR: '{search_term}'")
    
    try:
        cursor.execute("""
            SELECT c.id, c.name_abbreviation, c.court, c.jurisdiction, c.decision_date, c.file_name, ct.type
            FROM cases c
            LEFT JOIN case_types ct ON c.id = ct.case_id
            WHERE c.name_abbreviation LIKE ?
            LIMIT ?;
        """, (f"%{search_term}%", limit))
        
        rows = cursor.fetchall()
        
        if not rows:
            print("No matching cases found.")
            return
        
        print(f"Found {len(rows)} matching cases:")
        print(f"{'ID':<15} {'Title':<35} {'Court':<25} {'Case Type':<15}")
        print("-" * 90)
        
        for row in rows:
            case_id, title, court, jurisdiction, date, file_name, case_type = row
            print(f"{case_id:<15} {title[:35]:<35} {court[:25]:<25} {case_type:<15}")
            print(f"  Date: {date}, Jurisdiction: {jurisdiction}")
            print(f"  File: {file_name}")
            print("-" * 90)
    
    except sqlite3.OperationalError as e:
        print(f"Error executing search: {e}")
        print("Table structure may be different than expected.")

def get_case_by_id(conn, case_id):
    """Look up case details by ID"""
    cursor = conn.cursor()
    print_header(f"CASE DETAILS FOR ID: {case_id}")
    
    try:
        # Get case metadata
        cursor.execute("""
            SELECT c.*, ct.type, ct.confidence
            FROM cases c
            LEFT JOIN case_types ct ON c.id = ct.case_id
            WHERE c.id = ?;
        """, (case_id,))
        
        case_data = cursor.fetchone()
        
        if not case_data:
            print(f"No case found with ID: {case_id}")
            return
        
        # Get column names
        column_names = [description[0] for description in cursor.description]
        
        # Print case details
        print("Case Metadata:")
        for i, col in enumerate(column_names):
            print(f"{col}: {case_data[i]}")
        
        # Try to find CIDs for this case
        try:
            cursor.execute("""
                SELECT cid FROM cid_index WHERE case_id = ?;
            """, (case_id,))
            
            cids = cursor.fetchall()
            
            if cids:
                print("\nAssociated CIDs:")
                for cid in cids:
                    print(f"  {cid[0]}")
            else:
                print("\nNo CIDs associated with this case.")
        
        except sqlite3.OperationalError:
            print("\nCouldn't retrieve CIDs (table structure may be different)")
    
    except sqlite3.OperationalError as e:
        print(f"Error retrieving case: {e}")
        print("Table structure may be different than expected.")

def analyze_case_types(conn, specific_type=None):
    """Analyze the case_types table data"""
    cursor = conn.cursor()
    
    if specific_type:
        print_header(f"CASE TYPE ANALYSIS: {specific_type.upper()}")
    else:
        print_header("CASE TYPE ANALYSIS")
    
    try:
        # Get case type distribution
        cursor.execute("""
            SELECT type, COUNT(*) as count
            FROM case_types
            GROUP BY type
            ORDER BY count DESC;
        """)
        type_counts = cursor.fetchall()
        
        if not type_counts:
            print("No case type data found.")
            return
        
        # Calculate total for percentages
        total_cases = sum(count for _, count in type_counts)
        
        print("Case type distribution:")
        print(f"{'Type':<15} {'Count':<10} {'Percentage':<10}")
        print("-" * 40)
        for case_type, count in type_counts:
            percentage = (count / total_cases) * 100
            print(f"{case_type:<15} {count:<10} {percentage:.2f}%")
            
        # Get confidence statistics
        cursor.execute("""
            SELECT type, AVG(confidence) as avg_confidence
            FROM case_types
            GROUP BY type
            ORDER BY avg_confidence DESC;
        """)
        confidence_data = cursor.fetchall()
        
        print("\nClassification confidence by type:")
        print(f"{'Type':<15} {'Avg Confidence':<15}")
        print("-" * 35)
        for case_type, avg_confidence in confidence_data:
            print(f"{case_type:<15} {avg_confidence:.2f}%")
        
        # If specific type requested, show sample cases
        if specific_type:
            cursor.execute("""
                SELECT c.id, c.name_abbreviation, c.court, c.jurisdiction, 
                       c.decision_date, ct.confidence
                FROM cases c
                JOIN case_types ct ON c.id = ct.case_id
                WHERE ct.type = ?
                ORDER BY ct.confidence DESC
                LIMIT 10;
            """, (specific_type,))
            
            sample_cases = cursor.fetchall()
            
            if sample_cases:
                print(f"\nSample {specific_type} cases (highest confidence):")
                print(f"{'ID':<15} {'Title':<35} {'Court':<25} {'Confidence':<10}")
                print("-" * 90)
                
                for case in sample_cases:
                    case_id, title, court, jurisdiction, date, confidence = case
                    print(f"{case_id:<15} {title[:35]:<35} {court[:25]:<25} {confidence:.2f}%")
                    print(f"  Date: {date}, Jurisdiction: {jurisdiction}")
                    print("-" * 90)
            else:
                print(f"\nNo sample cases found for type: {specific_type}")
    
    except sqlite3.OperationalError as e:
        print(f"Error analyzing case types: {e}")
        print("Table structure may be different than expected.")

def analyze_database_statistics(conn):
    """Generate statistics about the database"""
    cursor = conn.cursor()
    print_header("DATABASE STATISTICS")
    
    stats = {}
    
    # Count cases
    try:
        cursor.execute("SELECT COUNT(*) FROM cases;")
        stats["total_cases"] = cursor.fetchone()[0]
        print(f"Total cases: {stats['total_cases']}")
    except sqlite3.OperationalError:
        print("Couldn't count cases (table structure may be different)")
    
    # Count case types
    try:
        cursor.execute("SELECT COUNT(*) FROM case_types;")
        stats["total_case_types"] = cursor.fetchone()[0]
        print(f"Total classified cases: {stats['total_case_types']}")
        
        # Coverage percentage
        if stats.get("total_cases"):
            coverage = (stats["total_case_types"] / stats["total_cases"]) * 100
            print(f"Classification coverage: {coverage:.2f}%")
    except sqlite3.OperationalError:
        print("Couldn't count case types (table might not exist)")
    
    # Count jurisdictions
    try:
        cursor.execute("SELECT COUNT(DISTINCT jurisdiction) FROM cases;")
        stats["jurisdictions"] = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT jurisdiction, COUNT(*) as count
            FROM cases
            GROUP BY jurisdiction
            ORDER BY count DESC
            LIMIT 10;
        """)
        jurisdiction_counts = cursor.fetchall()
        
        print(f"\nJurisdictions: {stats['jurisdictions']}")
        print("\nTop jurisdictions:")
        print(f"{'Jurisdiction':<25} {'Count':<10}")
        print("-" * 35)
        for jur, count in jurisdiction_counts:
            print(f"{jur:<25} {count:<10}")
    
    except sqlite3.OperationalError:
        print("Couldn't analyze jurisdictions (table structure may be different)")
    
    # Analyze courts
    try:
        cursor.execute("SELECT COUNT(DISTINCT court) FROM cases;")
        stats["courts"] = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT court, COUNT(*) as count
            FROM cases
            GROUP BY court
            ORDER BY count DESC
            LIMIT 10;
        """)
        court_counts = cursor.fetchall()
        
        print(f"\nCourts: {stats['courts']}")
        print("\nTop courts:")
        print(f"{'Court':<50} {'Count':<10}")
        print("-" * 60)
        for court, count in court_counts:
            print(f"{court[:50]:<50} {count:<10}")
    
    except sqlite3.OperationalError:
        print("Couldn't analyze courts (table structure may be different)")
    
    # Analyze date range
    try:
        cursor.execute("SELECT MIN(decision_date), MAX(decision_date) FROM cases;")
        min_date, max_date = cursor.fetchone()
        stats["date_range"] = (min_date, max_date)
        
        print(f"\nDate range: {min_date} to {max_date}")
    
    except sqlite3.OperationalError:
        print("Couldn't analyze date range (table structure may be different)")
    
    return stats

def main():
    """Main function"""
    # Parse command line arguments
    args = {arg.split('=')[0][2:]: arg.split('=')[1] for arg in sys.argv[1:] if arg.startswith('--') and '=' in arg}
    
    # Connect to the database
    conn = connect_to_db()
    
    try:
        # Handle specific command
        if 'table' in args:
            # Show schema for specific table
            cursor = conn.cursor()
            table_name = args['table']
            
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            
            if not columns:
                print(f"Table {table_name} not found.")
                return
            
            print_header(f"TABLE SCHEMA: {table_name}")
            
            print(f"{'Column':<20} {'Type':<10} {'NotNull':<8} {'PK':<5} {'Default':<15}")
            print("-" * 60)
            
            for col in columns:
                cid, name, dtype, notnull, default_val, pk = col
                print(f"{name:<20} {dtype:<10} {notnull:<8} {pk:<5} {str(default_val):<15}")
            
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 10;")
            rows = cursor.fetchall()
            
            if rows:
                print("\nSample data:")
                for row in rows:
                    print(f"  {row}")
            
            return
        
        if 'search' in args:
            # Search for cases
            limit = int(args.get('limit', 10))
            search_cases(conn, args['search'], limit)
            return
        
        if 'case-id' in args:
            # Look up specific case
            get_case_by_id(conn, args['case-id'])
            return
        
        if 'case-type' in args:
            # Analyze specific case type
            analyze_case_types(conn, args['case-type'])
            return
        
        # Default: show general database info
        show_schema(conn)
        analyze_database_statistics(conn)
        analyze_case_types(conn)  # Show case type distribution
        inspect_case_relationships(conn)
    
    finally:
        conn.close()

if __name__ == "__main__":
    main()