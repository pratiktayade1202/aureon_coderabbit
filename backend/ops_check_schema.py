from sqlalchemy import create_engine, inspect
import os
import sys

# Get DB URL from env (required - no hardcoded credentials)
db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("ERROR: DATABASE_URL environment variable is required")
    sys.exit(1)
engine = create_engine(db_url)

print("--- ORM REFLECTION CHECK: audit_events ---")
try:
    insp = inspect(engine)
    if not insp.has_table("audit_events"):
        print("Table 'audit_events' DOES NOT EXIST in the database.")
    else:
        columns = insp.get_columns("audit_events")
        print(f"Table 'audit_events' exists with {len(columns)} columns:")
        for col in columns:
            print(f"- {col['name']} ({col['type']})")
except Exception as e:
    print(f"Error during reflection: {e}")
