import sqlite3, json, os

# Resolve path to app.db (project root / workflowos/app.db)
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# The DB is located at workflowos/app.db (one level up from this script's folder)
 db_path = os.path.join(base_dir, 'app.db')

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Get list of tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
tables = [row[0] for row in cur.fetchall()]

schema = {}
records = {}
for tbl in tables:
    # Columns info
    cur.execute(f"PRAGMA table_info('{tbl}')")
    cols = [{'cid': c[0], 'name': c[1], 'type': c[2], 'notnull': c[3], 'dflt_value': c[4], 'pk': c[5]} for c in cur.fetchall()]
    schema[tbl] = cols
    # Data rows
    cur.execute(f"SELECT * FROM {tbl}")
    rows = cur.fetchall()
    records[tbl] = rows

conn.close()

result = {
    'tables': tables,
    'schema': schema,
    'records': records
}
print(json.dumps(result, indent=2))
