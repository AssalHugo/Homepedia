import sys
from pathlib import Path

# Assurer que la racine du projet est dans sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Encodage UTF-8 pour le terminal Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import argparse
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup
from sqlalchemy import text
from tqdm import tqdm

from src.db.mongo import get_database
from src.db.postgres import get_postgres_engine

BASE_URL = "https://www.ville-ideale.fr"

def slugify(text_val: str) -> str:
    """
    Normalise le nom d'une commune pour l'URL de ville-ideale.fr.
    Ex: 'Aix-en-Provence' -> 'aix-en-provence'
        'Saint-Étienne' -> 'saint-etienne'
        'Le Havre' -> 'le-havre'
    """
    if not text_val:
        return ""
    text_val = unicodedata.normalize("NFKD", text_val).encode("ascii", "ignore").decode("utf-8")
    text_val = re.sub(r"[^\w\s-]", "", text_val.lower())
    return re.sub(r"[-\s]+", "-", text_val).strip("-")

class BatchScraper:
    def __init__(self, delay: float = 1.0, max_pages: int = 3, proxy: Optional[str] = None):
        self.delay = delay
        self.max_pages = max_pages
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.google.com/",
        })
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}

        self.db = get_database()
        self.collection = self.db["villes_avis"]
        self.collection.create_index("code_insee", unique=True)
        self.pg_engine = get_postgres_engine()

    def get_candidate_communes(self, limit: int = 100, min_population: int = 5000, department: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Récupère depuis la table PostgreSQL 'communes' les villes cibles,
        triées par population décroissante (les grandes villes ont le plus d'avis).
        """
        query = """
            SELECT code_insee, nom, code_departement, population, latitude, longitude
            FROM communes
            WHERE population IS NOT NULL AND population >= :min_pop
        """
        params = {"min_pop": min_population}
        if department:
            query += " AND code_departement = :dept"
            params["dept"] = department
            
        query += " ORDER BY population DESC"
        if limit and limit > 0:
            query += " LIMIT :limit"
            params["limit"] = limit

        with self.pg_engine.connect() as conn:
            result = conn.execute(text(query), params)
            rows = result.mappings().all()
            return [dict(r) for r in rows]

    @staticmethod
    def _clean_float(text_val: str) -> Optional[float]:
        if not text_val:
            return None
        text_val = text_val.replace(",", ".").strip()
        match = re.search(r"[-+]?\d*\.\d+|\d+", text_val)
        return float(match.group()) if match else None

    def _extract_reviews(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extrait les avis textuels d'une page BeautifulSoup."""
        avis_list = []
        for comm in soup.find_all("div", class_="comm"):
            avis = {}
            p_author = comm.find("p")
            if p_author:
                date_match = re.search(r"posté le ([0-9]{2}-[0-9]{2}-[0-9]{4}(?: à [0-9]{2}:[0-9]{2})?)", p_author.get_text())
                if date_match:
                    avis["date"] = date_match.group(1)
                strong_author = p_author.find("strong")
                if strong_author:
                    avis["auteur"] = strong_author.get_text(strip=True)

            moyenne = comm.find("strong", class_="moyenne")
            if moyenne:
                avis["note"] = self._clean_float(moyenne.get_text())

            positif = comm.find("b", string=re.compile(r"points positifs", re.I))
            if positif and positif.parent:
                avis["positif"] = re.sub(r"^Les points positifs\s*:\s*", "", positif.parent.get_text(strip=True), flags=re.I)

            negatif = comm.find("b", string=re.compile(r"points négatifs", re.I))
            if negatif and negatif.parent:
                avis["negatif"] = re.sub(r"^Les points négatifs\s*:\s*", "", negatif.parent.get_text(strip=True), flags=re.I)

            interact = comm.find("div", class_="interact")
            if interact:
                strongs = interact.find_all("strong")
                if len(strongs) >= 2:
                    avis["nb_accord"] = int(strongs[0].get_text(strip=True) or 0)
                    avis["nb_pas_accord"] = int(strongs[1].get_text(strip=True) or 0)

            avis_list.append(avis)
        return avis_list

    def scrape_single_city(self, insee: str, nom: str, lat: Optional[float] = None, lon: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Scrape la fiche d'une commune sur ville-ideale.fr avec gestion de la pagination.
        """
        slug = f"{slugify(nom)}_{insee}"
        url = f"{BASE_URL}/{slug}"

        try:
            resp = self.session.get(url, timeout=12)
            if resp.status_code != 200 or len(resp.content) < 500:
                return None

            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Nom & code postal
            h1 = soup.find("h1")
            h1_text = h1.get_text(strip=True) if h1 else nom
            cp_match = re.search(r"\(([0-9]{5})\)", h1_text)
            code_postal = cp_match.group(1) if cp_match else None
            nom_propre = re.sub(r"\([0-9]{5}\)", "", h1_text).strip()

            # Département
            departement = None
            info_div = soup.find("div", id="info")
            if info_div:
                for p in info_div.find_all("p"):
                    if "Département" in p.get_text():
                        strong = p.find("strong")
                        departement = strong.get_text(strip=True) if strong else p.get_text(strip=True)
                        break

            # Note globale
            note_globale = None
            ng = soup.find("p", id="ng")
            if ng and ng.contents:
                note_globale = self._clean_float(ng.contents[0])

            # Notes par critères
            notes_criteres = {}
            tablonotes = soup.find("table", id="tablonotes")
            if tablonotes:
                for row in tablonotes.find_all("tr"):
                    th = row.find("th")
                    td = row.find("td")
                    if th and td:
                        critere = th.get_text(strip=True).lower().replace(" ", "_")
                        notes_criteres[critere] = self._clean_float(td.get_text(strip=True))

            # Avis page 1
            all_avis = self._extract_reviews(soup)

            # Pagination (pages 2, 3...)
            for page in range(2, self.max_pages + 1):
                # Vérifier si un lien vers la page suivante existe
                if not soup.find("a", href=re.compile(rf"\?page={page}")):
                    break
                page_url = f"{BASE_URL}/{slug}?page={page}#commentaires"
                time.sleep(self.delay)
                p_resp = self.session.get(page_url, timeout=12)
                if p_resp.status_code == 200 and len(p_resp.content) > 500:
                    p_soup = BeautifulSoup(p_resp.text, "html.parser")
                    page_avis = self._extract_reviews(p_soup)
                    if not page_avis:
                        break
                    all_avis.extend(page_avis)
                else:
                    break

            doc = {
                "code_insee": insee,
                "nom_ville": nom_propre,
                "code_postal": code_postal,
                "departement": departement,
                "latitude": lat,
                "longitude": lon,
                "note_globale": note_globale,
                "notes_criteres": notes_criteres,
                "nb_avis": len(all_avis),
                "avis": all_avis,
                "url": url,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            return doc
        except Exception:
            return None

    def run(self, limit: int = 50, min_population: int = 10000, department: Optional[str] = None, force: bool = False):
        print("\n" + "=" * 65)
        print("  HOMEPEDIA - BATCH SCRAPER (ville-ideale.fr -> MongoDB)")
        print("=" * 65)

        candidates = self.get_candidate_communes(limit=limit, min_population=min_population, department=department)
        print(f"[*] {len(candidates)} communes sélectionnées depuis PostgreSQL (Pop >= {min_population:,}).")

        # Détection des villes déjà en base
        existing_insee = set(self.collection.distinct("code_insee"))
        print(f"[*] {len(existing_insee)} communes déjà enregistrées dans MongoDB.")

        to_scrape = []
        for c in candidates:
            if force or c["code_insee"] not in existing_insee:
                to_scrape.append(c)

        print(f"[*] {len(to_scrape)} communes à traiter dans cette session.")
        if not to_scrape:
            print("[OK] Toutes les communes ciblees sont deja a jour en base !")
            self.print_summary()
            return

        success_count = 0
        skipped_count = 0
        total_new_reviews = 0

        # Barre de progression tqdm
        pbar = tqdm(to_scrape, desc="Scraping des avis", unit="ville", dynamic_ncols=True)
        
        for c in pbar:
            insee = c["code_insee"]
            nom = c["nom"]
            pbar.set_postfix_str(f"{nom[:15]} ({insee})")

            doc = self.scrape_single_city(
                insee=insee,
                nom=nom,
                lat=c.get("latitude"),
                lon=c.get("longitude")
            )

            if doc:
                self.collection.update_one(
                    {"code_insee": insee},
                    {"$set": doc},
                    upsert=True
                )
                success_count += 1
                total_new_reviews += doc["nb_avis"]
                pbar.set_postfix_str(f"{nom[:12]} | OK ({doc['nb_avis']} avis)")
            else:
                skipped_count += 1

            time.sleep(self.delay)

        pbar.close()

        print("\n" + "-" * 65)
        print(f"[OK] Session terminee : {success_count} communes inserees/mises a jour, {skipped_count} introuvables ou filtrees.")
        print(f"[OK] {total_new_reviews} avis textuels recoltes durant ce run.")
        self.print_summary()

    def print_summary(self):
        """Affiche les statistiques completes de la base NoSQL MongoDB."""
        total_docs = self.collection.count_documents({})
        total_avis = sum(len(d.get("avis", [])) for d in self.collection.find({}, {"avis": 1}))

        print("\n" + "=" * 65)
        print("  ETAT DE LA COLLECTION MONGODB ('homepedia.villes_avis')")
        print("=" * 65)
        print(f" - Communes stockees      : {total_docs}")
        print(f" - Total avis citoyens    : {total_avis}")
        
        # Top 3 des villes les mieux notées
        top_villes = list(self.collection.find({"note_globale": {"$ne": None}}).sort("note_globale", -1).limit(3))
        if top_villes:
            print("\n Top 3 des villes les mieux notées en base :")
            for i, v in enumerate(top_villes, 1):
                print(f"   {i}. {v['nom_ville']} ({v['code_insee']}) : {v['note_globale']}/10 ({len(v.get('avis', []))} avis)")

        print("-" * 65)
        print(" Visualisation Web Mongo Express : http://localhost:8081")
        print("=" * 65 + "\n")

def main():
    parser = argparse.ArgumentParser(description="Batch Scraper pour ville-ideale.fr avec barre de progression")
    parser.add_argument("--limit", type=int, default=30, help="Nombre max de communes à scraper (défaut: 30)")
    parser.add_argument("--min-pop", type=int, default=10000, help="Population minimale pour filtrer les communes (défaut: 10000)")
    parser.add_argument("--dept", type=str, default=None, help="Filtrer sur un département spécifique (ex: 75, 92, 13)")
    parser.add_argument("--delay", type=float, default=1.0, help="Délai en secondes entre requêtes (défaut: 1.0s)")
    parser.add_argument("--max-pages", type=int, default=3, help="Pages d'avis max par ville (défaut: 3)")
    parser.add_argument("--proxy", type=str, default=None, help="Proxy optionnel (ex: http://ip:port)")
    parser.add_argument("--force", action="store_true", help="Re-scraper les villes même si déjà en base")
    args = parser.parse_args()

    scraper = BatchScraper(delay=args.delay, max_pages=args.max_pages, proxy=args.proxy)
    scraper.run(limit=args.limit, min_population=args.min_pop, department=args.dept, force=args.force)

if __name__ == "__main__":
    main()
