import re
from datetime import datetime, timezone
import scrapy
from bs4 import BeautifulSoup
from homepedia_crawler.items import VilleIdealeItem

class VilleIdealeSpider(scrapy.Spider):
    name = "ville_ideale"
    allowed_domains = ["ville-ideale.fr"]
    
    # URL de départ : Accueil et Palmarès qui contiennent des dizaines de liens de villes
    start_urls = [
        "https://www.ville-ideale.fr/",
        "https://www.ville-ideale.fr/palmares.php",
        "https://www.ville-ideale.fr/classements.php",
    ]

    def __init__(self, limit=None, city=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.limit = int(limit) if limit else None
        self.count = 0
        if city:
            # Permet de scraper une ville spécifique ex: scrapy crawl ville_ideale -a city=antony_92002
            self.start_urls = [f"https://www.ville-ideale.fr/{city}"]

    @staticmethod
    def _clean_float(text: str):
        if not text:
            return None
        text = text.replace(",", ".").strip()
        match = re.search(r"[-+]?\d*\.\d+|\d+", text)
        return float(match.group()) if match else None

    def parse(self, response):
        """
        1. Si la page actuelle est une fiche de ville (ex: /antony_92002), on l'extrait.
        2. Sinon (ou en plus), on découvre et suit tous les liens vers d'autres villes.
        """
        # Vérifier si l'URL courante est une page de ville (termine par _codeInsee)
        city_match = re.search(r"/([a-z0-9\-]+)_([0-9A-Za-z]{4,5})(?:\?page=\d+)?(?:#.*)?$", response.url)
        
        if city_match:
            slug = city_match.group(1)
            code_insee = city_match.group(2)
            yield from self.parse_city(response, slug=slug, code_insee=code_insee)

        # Découverte de nouvelles villes sur la page
        if self.limit and self.count >= self.limit:
            return

        all_links = response.css("a::attr(href)").getall()
        for link in all_links:
            # Détecter les URLs du format /nom-ville_codeInsee
            if re.match(r"^/[a-z0-9\-]+_[0-9A-Za-z]{4,5}$", link) or re.match(r"^https://www\.ville-ideale\.fr/[a-z0-9\-]+_[0-9A-Za-z]{4,5}$", link):
                yield response.follow(link, callback=self.parse)

    def parse_city(self, response, slug: str, code_insee: str):
        soup = BeautifulSoup(response.text, "html.parser")
        
        # 1. Nom & Code postal
        h1 = soup.find("h1")
        h1_text = h1.get_text(strip=True) if h1 else slug
        cp_match = re.search(r"\(([0-9]{5})\)", h1_text)
        code_postal = cp_match.group(1) if cp_match else None
        nom_ville = re.sub(r"\([0-9]{5}\)", "", h1_text).strip()

        # 2. Département
        departement = None
        info_div = soup.find("div", id="info")
        if info_div:
            for p in info_div.find_all("p"):
                if "Département" in p.get_text():
                    strong = p.find("strong")
                    departement = strong.get_text(strip=True) if strong else p.get_text(strip=True)
                    break

        # 3. Note globale
        note_globale = None
        ng = soup.find("p", id="ng")
        if ng and ng.contents:
            note_globale = self._clean_float(ng.contents[0])

        # 4. Notes par critère
        notes_criteres = {}
        tablonotes = soup.find("table", id="tablonotes")
        if tablonotes:
            for row in tablonotes.find_all("tr"):
                th = row.find("th")
                td = row.find("td")
                if th and td:
                    critere = th.get_text(strip=True).lower().replace(" ", "_")
                    notes_criteres[critere] = self._clean_float(td.get_text(strip=True))

        # 5. Extraction des avis de la page courante
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

        # Création de l'item
        item = VilleIdealeItem(
            code_insee=code_insee,
            nom_ville=nom_ville,
            code_postal=code_postal,
            departement=departement,
            note_globale=note_globale,
            notes_criteres=notes_criteres,
            nb_avis=len(avis_list),
            avis=avis_list,
            url=response.url,
            scraped_at=datetime.now(timezone.utc).isoformat()
        )
        
        self.count += 1
        yield item

        # 6. Suivre la pagination des avis (ex: ?page=2#commentaires)
        next_page = response.css("nav#pages a:contains('Suivant')::attr(href)").get()
        if next_page and (not self.limit or self.count < self.limit):
            yield response.follow(next_page, callback=self.parse)
