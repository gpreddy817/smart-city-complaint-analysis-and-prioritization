"""
migrate.py - Run this ONCE to fix the database
Run: python migrate.py
Then restart app.py normally
"""

import sqlite3

DATABASE = 'complaints.db'

db = sqlite3.connect(DATABASE)

# Get existing columns
existing_cols = [row[1] for row in db.execute("PRAGMA table_info(complaints)").fetchall()]
print("Existing columns:", existing_cols)

# Add missing columns
migrations = [
    ("address",  "ALTER TABLE complaints ADD COLUMN address TEXT DEFAULT ''"),
    ("landmark", "ALTER TABLE complaints ADD COLUMN landmark TEXT DEFAULT ''"),
    ("pincode",  "ALTER TABLE complaints ADD COLUMN pincode TEXT DEFAULT ''"),
]

for col, sql in migrations:
    if col not in existing_cols:
        db.execute(sql)
        print(f"✅ Added column: {col}")
    else:
        print(f"⏭️  Already exists: {col}")

db.commit()
db.close()
print("\n✅ Migration complete! Now run: python app.py")