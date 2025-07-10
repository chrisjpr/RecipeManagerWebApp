DATABASE_URL="postgres://recipe_user:2411@localhost:5432/recipe_db?sslmode=disable"
DB_NAME="recipe_db"
DB_USER="recipe_user"
DB_PASSWORD=2411
DB_HOST="127.0.0.1"
DB_PORT=5432

import psycopg2

conn = psycopg2.connect(
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT,
    sslmode="disable"
)

print("✅ Connected successfully1")
print(conn)