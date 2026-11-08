import os

# Tests must never use the live Postgres database, whatever is in .env.
os.environ["DATABASE_URL"] = ""