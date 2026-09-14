import unittest
from scrapy.http import HtmlResponse, Request
from homepedia_crawler.spiders.ville_ideale_spider import VilleIdealeSpider
from homepedia_crawler.pipelines import MongoPipeline
from homepedia_crawler.items import VilleIdealeItem
from src.db.mongo import get_database

HTML_PATH = r"C:\Users\hugoa\.gemini\antigravity\brain\8f737a1e-a0e4-46dc-b04e-a23bb4785fc2\.system_generated\steps\68\content.md"

class TestScrapySpider(unittest.TestCase):
    def setUp(self):
        with open(HTML_PATH, "r", encoding="utf-8") as f:
            self.html = f.read()
        self.spider = VilleIdealeSpider()
        self.request = Request(url="https://www.ville-ideale.fr/antony_92002")
        self.response = HtmlResponse(
            url="https://www.ville-ideale.fr/antony_92002",
            body=self.html.encode("utf-8"),
            encoding="utf-8",
            request=self.request
        )

    def test_spider_parse_city(self):
        generator = self.spider.parse_city(self.response, slug="antony", code_insee="92002")
        items = [x for x in generator if isinstance(x, VilleIdealeItem)]
        
        self.assertEqual(len(items), 1)
        item = items[0]
        
        self.assertEqual(item["code_insee"], "92002")
        self.assertEqual(item["nom_ville"], "ANTONY")
        self.assertEqual(item["code_postal"], "92160")
        self.assertEqual(item["departement"], "92 - Hauts-de-Seine")
        self.assertEqual(item["note_globale"], 8.3)
        self.assertIn("environnement", item["notes_criteres"])
        self.assertEqual(item["notes_criteres"]["environnement"], 8.1)
        self.assertGreater(len(item["avis"]), 0)
        
        print("\n[OK] Item Scrapy extrait avec succès :")
        print(f" - Commune : {item['nom_ville']} ({item['code_insee']})")
        print(f" - Note globale : {item['note_globale']}/10")
        print(f" - Nombre d'avis sur la page : {len(item['avis'])}")

    def test_pipeline_mongodb(self):
        pipeline = MongoPipeline()
        pipeline.open_spider(self.spider)
        
        generator = self.spider.parse_city(self.response, slug="antony", code_insee="92002")
        items = [x for x in generator if isinstance(x, VilleIdealeItem)]
        
        pipeline.process_item(items[0], self.spider)
        pipeline.close_spider(self.spider)
        
        db = get_database()
        saved = db["villes_avis"].find_one({"code_insee": "92002"})
        self.assertIsNotNone(saved)
        self.assertEqual(saved["code_insee"], "92002")
        print("[OK] Pipeline Scrapy -> MongoDB validé avec succès !")

if __name__ == "__main__":
    unittest.main()
