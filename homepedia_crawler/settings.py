BOT_NAME = "homepedia_crawler"

SPIDER_MODULES = ["homepedia_crawler.spiders"]
NEWSPIDER_MODULE = "homepedia_crawler.spiders"

# Politesse et respect du serveur
ROBOTSTXT_OBEY = False
DOWNLOAD_DELAY = 1.5
CONCURRENT_REQUESTS = 4
CONCURRENT_REQUESTS_PER_DOMAIN = 2

# AutoThrottle : ajuste automatiquement la cadence selon la réponse du serveur
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1.0
AUTOTHROTTLE_MAX_DELAY = 6.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0

# En-têtes HTTP simulant un navigateur standard
DEFAULT_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.google.com/",
}

# Activation du Pipeline MongoDB
ITEM_PIPELINES = {
    "homepedia_crawler.pipelines.MongoPipeline": 300,
}

# Encodage et logs
FEED_EXPORT_ENCODING = "utf-8"
LOG_LEVEL = "INFO"
