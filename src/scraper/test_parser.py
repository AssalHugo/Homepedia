import os
from src.scraper.ville_ideale import VilleIdealeScraper
from src.db.mongo import get_database

HTML_PATH = r"C:\Users\hugoa\.gemini\antigravity\brain\8f737a1e-a0e4-46dc-b04e-a23bb4785fc2\.system_generated\steps\68\content.md"

def test_pipeline():
    scraper = VilleIdealeScraper()
    
    # Lire le contenu HTML réel d'Antony
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    print("Parsing de la page d'Antony...")
    doc = scraper.parse_city_page(html, default_insee="92002")
    
    print(f"Nom : {doc['nom_ville']}")
    print(f"Code INSEE : {doc['code_insee']}")
    print(f"Code Postal : {doc['code_postal']}")
    print(f"Département : {doc['departement']}")
    print(f"Note globale : {doc['note_globale']}")
    print(f"Notes critères : {doc['notes_criteres']}")
    print(f"Nombre d'avis extraits sur cette page : {doc['nb_avis_extraits']}")
    
    if doc['avis']:
        premier_avis = doc['avis'][0]
        print("\n--- Exemple de premier avis extrait ---")
        print(f"Auteur : {premier_avis.get('auteur')}")
        print(f"Date : {premier_avis.get('date')}")
        print(f"Note : {premier_avis.get('note')}")
        print(f"Positif : {premier_avis.get('positif')[:120]}...")
        print(f"Négatif : {premier_avis.get('negatif')[:120]}...")

    # Sauvegarder dans MongoDB
    scraper.save_to_mongo(doc)

    # Vérification dans MongoDB
    db = get_database()
    saved = db["villes_avis"].find_one({"code_insee": "92002"})
    print("\n[VERIFICATION DANS MONGODB]")
    print(f"ID MongoDB : {saved['_id']}")
    print(f"Ville en base : {saved['nom_ville']} (INSEE: {saved['code_insee']})")
    print(f"Nombre d'avis stockés : {len(saved['avis'])}")

if __name__ == "__main__":
    test_pipeline()
