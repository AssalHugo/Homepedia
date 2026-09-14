import scrapy

class VilleIdealeItem(scrapy.Item):
    code_insee = scrapy.Field()       # Clé de jointure principale (ex: "92002")
    nom_ville = scrapy.Field()        # Nom de la commune (ex: "Antony")
    code_postal = scrapy.Field()      # Code postal (ex: "92160")
    departement = scrapy.Field()      # Département (ex: "92 - Hauts-de-Seine")
    note_globale = scrapy.Field()     # Note moyenne globale sur 10
    notes_criteres = scrapy.Field()   # Dict des 9 critères (sécurité, transports...)
    nb_avis = scrapy.Field()          # Nombre d'avis collectés
    avis = scrapy.Field()             # Liste des dictionnaires d'avis textuels
    url = scrapy.Field()              # URL de la fiche scrapée
    scraped_at = scrapy.Field()       # Horodatage ISO
