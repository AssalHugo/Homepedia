import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Charger les variables d'environnement (.env)
load_dotenv()

MONGO_USER = os.getenv("MONGO_ROOT_USER", "root")
MONGO_PASS = os.getenv("MONGO_ROOT_PASSWORD", "rootpassword")
MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = os.getenv("MONGO_PORT", "27017")
MONGO_DB = os.getenv("MONGO_DB", "homepedia")

def get_mongo_client() -> MongoClient:
    """Retourne une instance de client MongoDB connecté."""
    uri = f"mongodb://{MONGO_USER}:{MONGO_PASS}@{MONGO_HOST}:{MONGO_PORT}/"
    return MongoClient(uri)

def get_database():
    """Retourne la base de données homepedia."""
    client = get_mongo_client()
    return client[MONGO_DB]

if __name__ == "__main__":
    try:
        db = get_database()
        # Test ping
        db.command("ping")
        print(f"Connexion réussie à MongoDB (base: '{MONGO_DB}') !")
    except Exception as e:
        print(f"Erreur de connexion a MongoDB : {e}")
