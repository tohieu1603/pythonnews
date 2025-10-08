import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def test_postgresql_connection():
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
            port=os.getenv("DB_PORT", "5432"),
            database="postgres"  # Connect to default postgres database first
        )
        print("✅ PostgreSQL connection successful!")
        conn.close()
        return True
    except psycopg2.Error as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        return False

def test_database_exists():
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
            port=os.getenv("DB_PORT", "5432"),
            database=os.getenv("DB_NAME", "togogoanalysis")
        )
        print("✅ Database 'togogoanalysis' exists and accessible!")
        conn.close()
        return True
    except psycopg2.Error as e:
        print(f"❌ Database 'togogoanalysis' connection failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing PostgreSQL configuration...")
    if test_postgresql_connection():
        test_database_exists()
    else:
        print("Please check your PostgreSQL installation and credentials.")
