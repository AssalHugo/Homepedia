import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

class MongoPipeline:
    """
    Pipeline Scrapy qui reçoit les items extraits et les enregistre/met à jour
    dans la base non-tabulaire MongoDB avec un index unique sur le code INSEE.
    """
    def __init__(self):
        self.mongo_user = os.getenv("MONGO_ROOT_USER", "root")
        self.mongo_pass = os.getenv("MONGO_ROOT_PASSWORD", "rootpassword")
        self.mongo_host = os.getenv("MONGO_HOST", "localhost")
        self.mongo_port = os.getenv("MONGO_PORT", "27017")
        self.mongo_db = os.getenv("MONGO_DB", "homepedia")
        self.collection_name = "villes_avis"

    def open_spider(self, spider):
        uri = f"mongodb://{self.mongo_user}:{self.mongo_pass}@{self.mongo_host}:{self.mongo_port}/"
        self.client = MongoClient(uri)
        self.db = self.client[self.mongo_db]
        self.collection = self.db[self.collection_name]
        # Création ou confirmation de l'index unique sur le code INSEE
        self.collection.create_index("code_insee", unique=True)
        spider.logger.info(f"MongoPipeline connecté à MongoDB : {self.mongo_db}.{self.collection_name}")

    def close_spider(self, spider):
        self.client.close()

    def process_item(self, item, spider):
        code_insee = item.get("code_insee")
        if not code_insee:
            spider.logger.warning(f"Item sans code INSEE ignoré : {item.get('nom_ville')}")
            return item

        data = dict(item)
        
        # Si la ville existe déjà, on fusionne les avis existants sans doublons
        existing = self.collection.find_one({"code_insee": code_insee})
        if existing and "avis" in existing:
            existing_dates_authors = {(a.get("date"), a.get("auteur")) for a in existing["avis"]}
            merged_avis = list(existing["avis"])
            for new_avis in data.get("avis", []):
                key = (new_avis.get("date"), new_avis.get("auteur"))
                if key not in existing_dates_authors:
                    merged_avis.append(new_avis)
            data["avis"] = merged_avis
            data["nb_avis"] = len(merged_avis)

        self.collection.update_one(
            {"code_insee": code_insee},
            {"$set": data},
            upsert=True
        )
        spider.logger.info(f"Commune sauvegardée dans MongoDB : {data.get('nom_ville')} ({code_insee}) - {data.get('nb_avis')} avis.")
        return item
