import re
import time
import os
import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any, List
from datetime import datetime
from src.db.mongo import get_database

BASE_URL = "https://www.ville-ideale.fr"

class VilleIdealeScraper:
    def __init__(self, proxy: Optional[str] = None):
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
        # Création de l'index sur code_insee pour des recherches instantanées
        self.collection.create_index("code_insee", unique=True)

    @staticmethod
    def _clean_float(text: str) -> Optional[float]:
        """Convertit une chaîne comme '8,30' ou '9.5' en float."""
        if not text:
            return None
        text = text.replace(",", ".").strip()
        match = re.search(r"[-+]?\d*\.\d+|\d+", text)
        return float(match.group()) if match else None

    def parse_city_page(self, html: str, default_insee: Optional[str] = None) -> Dict[str, Any]:
        """
        Extrait les données structurées et non-tabulaires d'une page ville-ideale.fr.
        """
        soup = BeautifulSoup(html, "html.parser")
        
        # 1. Nom de la ville et Code Postal
        h1 = soup.find("h1")
        h1_text = h1.get_text(strip=True) if h1 else ""
        
        nom_ville = h1_text
        code_postal = None
        cp_match = re.search(r"\(([0-9]{5})\)", h1_text)
        if cp_match:
            code_postal = cp_match.group(1)
            nom_ville = re.sub(r"\([0-9]{5}\)", "", h1_text).strip()

        # 2. Code INSEE
        code_insee = default_insee
        insee_link = soup.find("a", href=re.compile(r"geo=COM-([0-9A-Za-z]{5})"))
        if insee_link:
            match = re.search(r"geo=COM-([0-9A-Za-z]{5})", insee_link["href"])
            if match:
                code_insee = match.group(1)

        # 3. Département
        departement = None
        info_div = soup.find("div", id="info")
        if info_div:
            for p in info_div.find_all("p"):
                if "Département" in p.get_text():
                    strong = p.find("strong")
                    departement = strong.get_text(strip=True) if strong else p.get_text(strip=True)
                    break

        # 4. Note globale
        note_globale = None
        ng_elem = soup.find("p", id="ng")
        if ng_elem:
            note_globale = self._clean_float(ng_elem.contents[0] if ng_elem.contents else "")

        # 5. Notes par critères
        notes_criteres = {}
        tablonotes = soup.find("table", id="tablonotes")
        if tablonotes:
            for row in tablonotes.find_all("tr"):
                th = row.find("th")
                td = row.find("td")
                if th and td:
                    critere_nom = th.get_text(strip=True).lower().replace(" ", "_")
                    notes_criteres[critere_nom] = self._clean_float(td.get_text(strip=True))

        # 6. Extraction des avis textuels
        avis_list = []
        comm_divs = soup.find_all("div", class_="comm")
        for comm in comm_divs:
            avis_data = {}
            # Auteur et date
            p_author = comm.find("p")
            if p_author:
                date_match = re.search(r"posté le ([0-9]{2}-[0-9]{2}-[0-9]{4}(?: à [0-9]{2}:[0-9]{2})?)", p_author.get_text())
                if date_match:
                    avis_data["date"] = date_match.group(1)
                strong_author = p_author.find("strong")
                if strong_author:
                    avis_data["auteur"] = strong_author.get_text(strip=True)

            # Note moyenne de l'avis
            moyenne_elem = comm.find("strong", class_="moyenne")
            if moyenne_elem:
                avis_data["note"] = self._clean_float(moyenne_elem.get_text())

            # Points positifs
            positif_elem = comm.find("b", string=re.compile(r"points positifs", re.I))
            if positif_elem and positif_elem.parent:
                text_positif = positif_elem.parent.get_text(strip=True)
                avis_data["positif"] = re.sub(r"^Les points positifs\s*:\s*", "", text_positif, flags=re.I)

            # Points négatifs
            negatif_elem = comm.find("b", string=re.compile(r"points négatifs", re.I))
            if negatif_elem and negatif_elem.parent:
                text_negatif = negatif_elem.parent.get_text(strip=True)
                avis_data["negatif"] = re.sub(r"^Les points négatifs\s*:\s*", "", text_negatif, flags=re.I)

            # Votes d'accord / pas d'accord
            interact = comm.find("div", class_="interact")
            if interact:
                strongs = interact.find_all("strong")
                if len(strongs) >= 2:
                    avis_data["nb_accord"] = int(strongs[0].get_text(strip=True) or 0)
                    avis_data["nb_pas_accord"] = int(strongs[1].get_text(strip=True) or 0)

            avis_list.append(avis_data)

        # Structure du document MongoDB
        document = {
            "code_insee": code_insee,
            "nom_ville": nom_ville,
            "code_postal": code_postal,
            "departement": departement,
            "note_globale": note_globale,
            "notes_criteres": notes_criteres,
            "nb_avis_extraits": len(avis_list),
            "avis": avis_list,
            "updated_at": datetime.utcnow().isoformat()
        }
        return document

    def save_to_mongo(self, document: Dict[str, Any]):
        """Insère ou met à jour les avis d'une commune dans MongoDB."""
        if not document.get("code_insee"):
            print("Attention : document sans code INSEE, non enregistré.")
            return
            
        self.collection.update_one(
            {"code_insee": document["code_insee"]},
            {"$set": document},
            upsert=True
        )
        print(f"Commune enregistrée dans MongoDB : {document.get('nom_ville')} (INSEE: {document.get('code_insee')}) avec {document.get('nb_avis_extraits')} avis.")

    def scrape_and_save(self, slug_with_insee: str) -> Optional[Dict[str, Any]]:
        """
        Scrape une commune (ex: 'antony_92002') et l'enregistre en base MongoDB.
        """
        # Extraire le code INSEE de la fin du slug (ex: antony_92002 -> 92002)
        match = re.search(r"_([0-9A-Za-z]{5})$", slug_with_insee)
        code_insee = match.group(1) if match else None

        url = f"{BASE_URL}/{slug_with_insee}"
        print(f"Scraping de {url}...")
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code == 200 and len(resp.content) > 500:
                doc = self.parse_city_page(resp.text, default_insee=code_insee)
                self.save_to_mongo(doc)
                return doc
            else:
                print(f"Réponse vide ou restreinte ({resp.status_code}, taille {len(resp.content)} octets).")
                return None
        except Exception as e:
            print(f"Erreur lors du scraping de {url} : {e}")
            return None
