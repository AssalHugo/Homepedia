import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

PG_USER = os.getenv("POSTGRES_USER", "homepedia")
PG_PASS = os.getenv("POSTGRES_PASSWORD", "homepedia_secret")
PG_HOST = os.getenv("POSTGRES_HOST", "localhost")
PG_PORT = os.getenv("POSTGRES_PORT", "5432")
PG_DB = os.getenv("POSTGRES_DB", "homepedia")

def get_postgres_engine():
    """Retourne un moteur SQLAlchemy connecté à PostgreSQL."""
    url = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}"
    return create_engine(url)

if __name__ == "__main__":
    try:
        engine = get_postgres_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();")).fetchone()
            print(f"Connexion réussie à PostgreSQL : {result[0]}")
    except Exception as e:
        print(f"Erreur de connexion à PostgreSQL : {e}")
