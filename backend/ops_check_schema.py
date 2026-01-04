from sqlalchemy import create_engine, inspect
import os

# Get DB URL from env or use default
# Explicitly using the one from .env we saw earlier for reliability
db_url = os.getenv("DATABASE_URL", "postgresql://aureon:aureon123@localhost:5432/custody_ai")
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
