import sqlite3

def inspect_case_id(case_id, db_path="case_lookup.db"):
    """Inspect a specific case ID in the database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get case details
        cursor.execute("SELECT * FROM cases WHERE id = ?", (case_id,))
        case = cursor.fetchone()
        if case:
            columns = [desc[0] for desc in cursor.description]
            case_dict = dict(zip(columns, case))
            print(f"Found case ID {case_id}:")
            for key, value in case_dict.items():
                print(f"  {key}: {value}")
            
            # Get file info
            file_name = case_dict.get('file_name')
            print(f"\nExamining file: {file_name}")
            
            # Check other cases in the same file
            cursor.execute("SELECT id, name_abbreviation FROM cases WHERE file_name = ? LIMIT 10", (file_name,))
            file_cases = cursor.fetchall()
            print(f"\nOther cases in the same file (showing max 10):")
            for fc_id, fc_name in file_cases:
                print(f"  ID: {fc_id}, Name: {fc_name}")
            
            # Check if we can find a case with the requested title
            requested_title = "State v. Frizzelle"  # Replace with the actual requested title
            print(f"\nSearching for cases with title like '{requested_title}':")
            cursor.execute("SELECT id, name_abbreviation, file_name FROM cases WHERE name_abbreviation LIKE ? LIMIT 5", (f"%{requested_title.split(' v.')[0].strip()}%",))
            title_matches = cursor.fetchall()
            for tm_id, tm_name, tm_file in title_matches:
                print(f"  ID: {tm_id}, Name: {tm_name}, File: {tm_file}")
            
        else:
            print(f"No case found with ID {case_id}")
    except Exception as e:
        print(f"Error inspecting case: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

# Change this to the case ID you want to inspect
case_id_to_check = "8486057"
inspect_case_id(case_id_to_check)