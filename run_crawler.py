import argparse
import sys
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from src.db.mongo import get_database

def main():
    parser = argparse.ArgumentParser(description="Homepedia - Scraper ville-ideale.fr avec Scrapy et MongoDB")
    parser.add_argument("--limit", type=int, default=None, help="Nombre maximal de communes à extraire")
    parser.add_argument("--city", type=str, default=None, help="Cibler une commune spécifique (ex: antony_92002)")
    parser.add_argument("--proxy", type=str, default=None, help="URL de proxy HTTP/HTTPS optionnel")
    args = parser.parse_args()

    settings = get_project_settings()
    if args.proxy:
        settings.set("HTTP_PROXY", args.proxy)
        settings.set("HTTPS_PROXY", args.proxy)

    process = CrawlerProcess(settings)
    spider_kwargs = {}
    if args.limit:
        spider_kwargs["limit"] = args.limit
    if args.city:
        spider_kwargs["city"] = args.city

    print("=" * 60)
    print(" Lancement du Crawler Scrapy Homepedia (ville-ideale.fr)")
    print(f" Cible : {'Toutes les villes' if not args.city else args.city}")
    print(f" Limite : {args.limit or 'Aucune'}")
    print(" Destination : MongoDB (collection 'villes_avis')")
    print("=" * 60)

    process.crawl("ville_ideale", **spider_kwargs)
    process.start()

    # Bilan MongoDB après exécution
    db = get_database()
    total_villes = db["villes_avis"].count_documents({})
    total_avis = sum(len(doc.get("avis", [])) for doc in db["villes_avis"].find({}, {"avis": 1}))
    print("\n" + "=" * 60)
    print(" BILAN MONGODB")
    print(f" Total communes en base : {total_villes}")
    print(f" Total avis collectés : {total_avis}")
    print(" Interface visuelle : http://localhost:8081")
    print("=" * 60)

if __name__ == "__main__":
    main()
