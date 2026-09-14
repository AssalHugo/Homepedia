import requests
import pandas as pd
from sqlalchemy import text
from src.db.postgres import get_postgres_engine

GEO_API_URL = "https://geo.api.gouv.fr/communes?fields=nom,code,codesPostaux,centre,population,codeDepartement,codeRegion"

def fetch_official_communes() -> pd.DataFrame:
    """
    Récupère la liste officielle des communes françaises depuis l'API publique geo.api.gouv.fr.
    Retourne un DataFrame pandas propre avec le Code INSEE comme identifiant.
    """
    print("Téléchargement du référentiel officiel des communes (geo.api.gouv.fr)...")
    response = requests.get(GEO_API_URL, timeout=30)
    response.raise_for_status()
    data = response.json()
    
    records = []
    for item in data:
        coords = item.get("centre", {}).get("coordinates", [None, None])
        records.append({
            "code_insee": item.get("code"),
            "nom": item.get("nom"),
            "code_departement": item.get("codeDepartement"),
            "code_region": item.get("codeRegion"),
            "codes_postaux": ",".join(item.get("codesPostaux", [])),
            "population": item.get("population"),
            "longitude": coords[0] if coords else None,
            "latitude": coords[1] if coords else None,
        })
        
    df = pd.DataFrame(records)
    print(f"{len(df)} communes officielles récupérées.")
    return df

def save_communes_to_postgres(df: pd.DataFrame):
    """Enregistre le référentiel des communes dans la table 'communes' de PostgreSQL."""
    engine = get_postgres_engine()
    print("Sauvegarde des communes dans PostgreSQL (table 'communes')...")
    df.to_sql("communes", engine, if_exists="replace", index=False)
    
    # Créer un index sur code_insee
    with engine.connect() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_communes_insee ON communes (code_insee);"))
        conn.commit()
    print("Table 'communes' créée et indexée dans PostgreSQL !")

if __name__ == "__main__":
    df = fetch_official_communes()
    print(df.head())
    save_communes_to_postgres(df)
