"""700 shop niches: accounts, keys, top-ups, monitoring, crypto and services.

These are built from real product categories that sell on Telegram every day.
Each brand gets its own bot rather than one mega-shop, because a buyer
searching "Steam аккаунты" converts on a bot that is only about that.

Entries are (slug, brand, topic) and are expanded per category with the
category's archetype, tier and copy template.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Category tables. (slug, brand shown in the name, topic used in copy)
# --------------------------------------------------------------------------

GAMING_ACCOUNTS = [
    ("steam", "Steam", "аккаунты Steam"),
    ("epic-games", "Epic Games", "аккаунты Epic Games"),
    ("battlenet", "Battle.net", "аккаунты Battle.net"),
    ("ea-app", "EA App", "аккаунты EA"),
    ("ubisoft", "Ubisoft", "аккаунты Ubisoft Connect"),
    ("gog", "GOG", "аккаунты GOG"),
    ("riot", "Riot Games", "аккаунты Riot"),
    ("valorant", "Valorant", "аккаунты Valorant"),
    ("league-legends", "League of Legends", "аккаунты League of Legends"),
    ("cs2", "CS2", "аккаунты CS2"),
    ("dota2", "Dota 2", "аккаунты Dota 2"),
    ("pubg", "PUBG", "аккаунты PUBG"),
    ("fortnite", "Fortnite", "аккаунты Fortnite"),
    ("roblox", "Roblox", "аккаунты Roblox"),
    ("minecraft", "Minecraft", "аккаунты Minecraft"),
    ("gta5", "GTA V", "аккаунты GTA V"),
    ("rdr2", "Red Dead Redemption 2", "аккаунты RDR2"),
    ("genshin", "Genshin Impact", "аккаунты Genshin Impact"),
    ("honkai", "Honkai Star Rail", "аккаунты Honkai"),
    ("zenless", "Zenless Zone Zero", "аккаунты Zenless"),
    ("brawl-stars", "Brawl Stars", "аккаунты Brawl Stars"),
    ("clash-clans", "Clash of Clans", "аккаунты Clash of Clans"),
    ("clash-royale", "Clash Royale", "аккаунты Clash Royale"),
    ("mobile-legends-acc", "Mobile Legends", "аккаунты Mobile Legends"),
    ("free-fire", "Free Fire", "аккаунты Free Fire"),
    ("standoff2", "Standoff 2", "аккаунты Standoff 2"),
    ("wot", "World of Tanks", "аккаунты World of Tanks"),
    ("warthunder", "War Thunder", "аккаунты War Thunder"),
    ("warface", "Warface", "аккаунты Warface"),
    ("rust", "Rust", "аккаунты Rust"),
    ("apex", "Apex Legends", "аккаунты Apex Legends"),
    ("overwatch", "Overwatch 2", "аккаунты Overwatch 2"),
    ("rainbow6", "Rainbow Six", "аккаунты Rainbow Six"),
    ("cod", "Call of Duty", "аккаунты Call of Duty"),
    ("destiny2", "Destiny 2", "аккаунты Destiny 2"),
    ("wow", "World of Warcraft", "аккаунты WoW"),
    ("ffxiv", "Final Fantasy XIV", "аккаунты FFXIV"),
    ("albion", "Albion Online", "аккаунты Albion"),
    ("eve", "EVE Online", "аккаунты EVE Online"),
    ("tarkov", "Escape from Tarkov", "аккаунты Tarkov"),
    ("psn", "PlayStation Network", "аккаунты PSN"),
    ("xbox", "Xbox", "аккаунты Xbox"),
    ("nintendo", "Nintendo", "аккаунты Nintendo"),
]

STREAMING_ACCOUNTS = [
    ("netflix", "Netflix", "аккаунты Netflix"),
    ("spotify", "Spotify", "аккаунты Spotify"),
    ("youtube-premium", "YouTube Premium", "аккаунты YouTube Premium"),
    ("disney-plus", "Disney+", "аккаунты Disney+"),
    ("hbo-max", "HBO Max", "аккаунты HBO Max"),
    ("apple-music", "Apple Music", "аккаунты Apple Music"),
    ("apple-tv", "Apple TV+", "аккаунты Apple TV+"),
    ("amazon-prime", "Amazon Prime", "аккаунты Amazon Prime"),
    ("crunchyroll", "Crunchyroll", "аккаунты Crunchyroll"),
    ("deezer", "Deezer", "аккаунты Deezer"),
    ("tidal", "Tidal", "аккаунты Tidal"),
    ("twitch", "Twitch", "аккаунты Twitch"),
    ("kinopoisk", "Кинопоиск", "подписки Кинопоиск"),
    ("ivi", "IVI", "подписки IVI"),
    ("okko", "Okko", "подписки Okko"),
    ("wink", "Wink", "подписки Wink"),
    ("premier", "Premier", "подписки Premier"),
    ("yandex-plus", "Яндекс Плюс", "подписки Яндекс Плюс"),
    ("vk-music", "VK Музыка", "подписки VK Музыка"),
    ("zvuk", "Звук", "подписки Звук"),
    ("start", "START", "подписки START"),
    ("more-tv", "MORE.TV", "подписки MORE.TV"),
    ("paramount", "Paramount+", "аккаунты Paramount+"),
    ("peacock", "Peacock", "аккаунты Peacock"),
    ("hulu", "Hulu", "аккаунты Hulu"),
    ("dazn", "DAZN", "аккаунты DAZN"),
    ("audible", "Audible", "аккаунты Audible"),
    ("litres", "Литрес", "подписки Литрес"),
]

AI_ACCOUNTS = [
    ("chatgpt-plus", "ChatGPT Plus", "аккаунты ChatGPT Plus"),
    ("claude-pro", "Claude Pro", "аккаунты Claude Pro"),
    ("midjourney", "Midjourney", "аккаунты Midjourney"),
    ("perplexity", "Perplexity Pro", "аккаунты Perplexity"),
    ("gemini-advanced", "Gemini Advanced", "аккаунты Gemini"),
    ("copilot", "GitHub Copilot", "аккаунты Copilot"),
    ("runway", "Runway", "аккаунты Runway"),
    ("elevenlabs", "ElevenLabs", "аккаунты ElevenLabs"),
    ("suno", "Suno", "аккаунты Suno"),
    ("leonardo-ai", "Leonardo AI", "аккаунты Leonardo"),
    ("openai-api", "OpenAI API", "доступ к OpenAI API"),
    ("anthropic-api", "Anthropic API", "доступ к Anthropic API"),
    ("stable-diffusion", "Stable Diffusion", "доступ к Stable Diffusion"),
    ("heygen", "HeyGen", "аккаунты HeyGen"),
    ("synthesia", "Synthesia", "аккаунты Synthesia"),
    ("descript", "Descript", "аккаунты Descript"),
    ("jasper", "Jasper AI", "аккаунты Jasper"),
    ("copy-ai", "Copy.ai", "аккаунты Copy.ai"),
    ("grammarly", "Grammarly", "аккаунты Grammarly"),
    ("notion-ai", "Notion AI", "аккаунты Notion AI"),
    ("cursor-ai", "Cursor", "аккаунты Cursor"),
    ("replit", "Replit", "аккаунты Replit"),
    ("luma-ai", "Luma AI", "аккаунты Luma"),
    ("pika", "Pika", "аккаунты Pika"),
    ("ideogram", "Ideogram", "аккаунты Ideogram"),
    ("krea", "Krea AI", "аккаунты Krea"),
    ("gamma-app", "Gamma", "аккаунты Gamma"),
    ("deepl", "DeepL Pro", "аккаунты DeepL"),
    ("otter-ai", "Otter.ai", "аккаунты Otter.ai"),
    ("chatpdf", "ChatPDF", "аккаунты ChatPDF"),
]

SOCIAL_ACCOUNTS = [
    ("telegram", "Telegram", "аккаунты Telegram"),
    ("discord", "Discord", "аккаунты Discord"),
    ("instagram", "Instagram", "аккаунты Instagram"),
    ("tiktok", "TikTok", "аккаунты TikTok"),
    ("twitter-x", "X (Twitter)", "аккаунты X"),
    ("facebook", "Facebook", "аккаунты Facebook"),
    ("vkontakte", "ВКонтакте", "аккаунты ВКонтакте"),
    ("odnoklassniki", "Одноклассники", "аккаунты Одноклассники"),
    ("reddit", "Reddit", "аккаунты Reddit"),
    ("linkedin", "LinkedIn", "аккаунты LinkedIn"),
    ("snapchat", "Snapchat", "аккаунты Snapchat"),
    ("pinterest", "Pinterest", "аккаунты Pinterest"),
    ("threads", "Threads", "аккаунты Threads"),
    ("youtube-channel", "YouTube", "аккаунты YouTube"),
    ("twitch-channel", "Twitch", "каналы Twitch"),
    ("whatsapp", "WhatsApp", "аккаунты WhatsApp"),
    ("viber", "Viber", "аккаунты Viber"),
    ("signal", "Signal", "аккаунты Signal"),
    ("medium", "Medium", "аккаунты Medium"),
    ("bluesky", "Bluesky", "аккаунты Bluesky"),
    ("rutube", "RUTUBE", "аккаунты RUTUBE"),
    ("dzen", "Дзен", "аккаунты Дзен"),
    ("likee", "Likee", "аккаунты Likee"),
    ("kwai", "Kwai", "аккаунты Kwai"),
]

EMAIL_CLOUD_ACCOUNTS = [
    ("gmail", "Gmail", "аккаунты Gmail"),
    ("google-workspace", "Google Workspace", "аккаунты Google Workspace"),
    ("outlook", "Outlook", "аккаунты Outlook"),
    ("yandex-mail", "Яндекс Почта", "аккаунты Яндекс Почты"),
    ("mailru", "Mail.ru", "аккаунты Mail.ru"),
    ("protonmail", "Proton Mail", "аккаунты Proton Mail"),
    ("icloud", "iCloud", "аккаунты iCloud"),
    ("dropbox", "Dropbox", "аккаунты Dropbox"),
    ("google-drive", "Google Drive", "хранилище Google Drive"),
    ("mega-nz", "MEGA", "аккаунты MEGA"),
    ("onedrive", "OneDrive", "аккаунты OneDrive"),
    ("yandex-disk", "Яндекс Диск", "аккаунты Яндекс Диска"),
    ("zoho-mail", "Zoho Mail", "аккаунты Zoho"),
    ("gmx", "GMX", "аккаунты GMX"),
    ("tutanota", "Tuta", "аккаунты Tuta"),
    ("firstmail", "Firstmail", "аккаунты Firstmail"),
]

DEV_WORK_ACCOUNTS = [
    ("github", "GitHub", "аккаунты GitHub"),
    ("gitlab", "GitLab", "аккаунты GitLab"),
    ("jetbrains", "JetBrains", "лицензии JetBrains"),
    ("figma", "Figma", "аккаунты Figma"),
    ("canva-pro", "Canva Pro", "аккаунты Canva Pro"),
    ("adobe-cc", "Adobe Creative Cloud", "аккаунты Adobe CC"),
    ("notion", "Notion", "аккаунты Notion"),
    ("slack", "Slack", "аккаунты Slack"),
    ("zoom", "Zoom", "аккаунты Zoom"),
    ("trello", "Trello", "аккаунты Trello"),
    ("asana", "Asana", "аккаунты Asana"),
    ("miro", "Miro", "аккаунты Miro"),
    ("envato", "Envato Elements", "аккаунты Envato"),
    ("shutterstock", "Shutterstock", "аккаунты Shutterstock"),
    ("freepik", "Freepik", "аккаунты Freepik"),
    ("coursera", "Coursera", "аккаунты Coursera"),
    ("udemy", "Udemy", "аккаунты Udemy"),
    ("skillbox", "Skillbox", "доступы Skillbox"),
    ("duolingo", "Duolingo", "аккаунты Duolingo Plus"),
    ("linkedin-learning", "LinkedIn Learning", "аккаунты LinkedIn Learning"),
]

VPN_PROXY_ACCOUNTS = [
    ("nordvpn", "NordVPN", "аккаунты NordVPN"),
    ("expressvpn", "ExpressVPN", "аккаунты ExpressVPN"),
    ("surfshark", "Surfshark", "аккаунты Surfshark"),
    ("protonvpn", "Proton VPN", "аккаунты Proton VPN"),
    ("cyberghost", "CyberGhost", "аккаунты CyberGhost"),
    ("mullvad", "Mullvad", "аккаунты Mullvad"),
    ("socks5-proxy", "SOCKS5", "прокси SOCKS5"),
    ("http-proxy", "HTTP-прокси", "HTTP-прокси"),
    ("mobile-proxy", "Мобильные прокси", "мобильные прокси"),
    ("residential-proxy", "Резидентные прокси", "резидентные прокси"),
    ("static-proxy", "Статичные прокси", "статичные прокси"),
    ("vless-config", "VLESS", "конфиги VLESS"),
    ("outline-vpn", "Outline", "ключи Outline"),
    ("wireguard", "WireGuard", "конфиги WireGuard"),
    ("sms-numbers", "Виртуальные номера", "виртуальные номера для SMS"),
]

CRYPTO_ACCOUNTS = [
    ("binance-acc", "Binance", "аккаунты Binance"),
    ("bybit-acc", "Bybit", "аккаунты Bybit"),
    ("okx-acc", "OKX", "аккаунты OKX"),
    ("kucoin-acc", "KuCoin", "аккаунты KuCoin"),
    ("mexc-acc", "MEXC", "аккаунты MEXC"),
    ("bitget-acc", "Bitget", "аккаунты Bitget"),
    ("htx-acc", "HTX", "аккаунты HTX"),
    ("gate-io", "Gate.io", "аккаунты Gate.io"),
    ("kraken-acc", "Kraken", "аккаунты Kraken"),
    ("coinbase-acc", "Coinbase", "аккаунты Coinbase"),
    ("bingx-acc", "BingX", "аккаунты BingX"),
    ("blofin", "BloFin", "аккаунты BloFin"),
]

MARKETPLACE_ACCOUNTS = [
    ("amazon-acc", "Amazon", "аккаунты Amazon"),
    ("ebay-acc", "eBay", "аккаунты eBay"),
    ("avito-acc", "Авито", "аккаунты Авито"),
    ("wildberries-acc", "Wildberries", "кабинеты Wildberries"),
    ("ozon-acc", "Ozon", "кабинеты Ozon"),
    ("aliexpress-acc", "AliExpress", "аккаунты AliExpress"),
    ("etsy-acc", "Etsy", "аккаунты Etsy"),
    ("upwork-acc", "Upwork", "аккаунты Upwork"),
    ("fiverr-acc", "Fiverr", "аккаунты Fiverr"),
    ("uber-acc", "Uber", "аккаунты Uber"),
    ("bolt-acc", "Bolt", "аккаунты Bolt"),
    ("yandex-go", "Яндекс Go", "аккаунты Яндекс Go"),
    ("paypal-acc", "PayPal", "аккаунты PayPal"),
    ("wise-acc", "Wise", "аккаунты Wise"),
    ("revolut-acc", "Revolut", "аккаунты Revolut"),
    ("payoneer-acc", "Payoneer", "аккаунты Payoneer"),
]

KEYS_AND_CARDS = [
    ("steam-gift", "Steam Gift Card", "подарочные карты Steam"),
    ("psn-card", "PSN Card", "карты PlayStation Store"),
    ("xbox-card", "Xbox Gift Card", "карты Xbox"),
    ("nintendo-card", "Nintendo eShop", "карты Nintendo eShop"),
    ("itunes-card", "iTunes Card", "карты iTunes"),
    ("google-play-card", "Google Play", "карты Google Play"),
    ("amazon-card", "Amazon Gift Card", "карты Amazon"),
    ("netflix-card", "Netflix Card", "карты Netflix"),
    ("spotify-card", "Spotify Card", "карты Spotify"),
    ("windows-key", "Windows", "ключи Windows"),
    ("office-key", "Microsoft Office", "ключи Office"),
    ("antivirus-key", "Антивирусы", "ключи антивирусов"),
    ("game-keys-shop", "Ключи игр", "ключи для игр"),
    ("discord-nitro", "Discord Nitro", "Discord Nitro"),
    ("telegram-premium", "Telegram Premium", "Telegram Premium"),
    ("roblox-card", "Roblox Card", "карты Roblox"),
    ("valve-key", "Valve", "ключи Valve"),
    ("ea-play", "EA Play", "подписки EA Play"),
    ("gamepass", "Game Pass", "подписки Game Pass"),
    ("psplus", "PS Plus", "подписки PS Plus"),
]

GAME_TOPUP = [
    ("robux-topup", "Robux", "пополнение Robux"),
    ("vbucks-topup", "V-Bucks", "пополнение V-Bucks"),
    ("uc-pubg", "PUBG UC", "пополнение UC в PUBG"),
    ("genshin-crystals", "Genshin", "кристаллы Genshin"),
    ("brawl-gems", "Brawl Stars", "гемы Brawl Stars"),
    ("mlbb-diamonds", "Mobile Legends", "алмазы Mobile Legends"),
    ("free-fire-diamonds", "Free Fire", "алмазы Free Fire"),
    ("standoff-gold", "Standoff 2", "золото Standoff 2"),
    ("cod-points", "Call of Duty", "CP в Call of Duty"),
    ("valorant-points", "Valorant", "Valorant Points"),
    ("lol-rp", "League of Legends", "Riot Points"),
    ("wot-gold", "World of Tanks", "золото World of Tanks"),
    ("clash-gems", "Clash of Clans", "гемы Clash of Clans"),
    ("roblox-premium", "Roblox Premium", "подписка Roblox Premium"),
    ("honkai-crystals", "Honkai", "кристаллы Honkai"),
    ("wow-gold", "WoW", "золото World of Warcraft"),
    ("steam-wallet", "Steam", "пополнение кошелька Steam"),
    ("telegram-stars-topup", "Telegram Stars", "пополнение Telegram Stars"),
    ("tiktok-coins", "TikTok", "монеты TikTok"),
    ("discord-boost", "Discord", "бусты Discord-сервера"),
]

GAME_SERVICES = [
    ("cs2-rank-boost", "CS2 Буст", "прокачка ранга CS2"),
    ("dota-mmr", "Dota 2 MMR", "буст MMR в Dota 2"),
    ("valorant-boost", "Valorant Буст", "буст ранга Valorant"),
    ("lol-boost", "LoL Буст", "буст ранга League of Legends"),
    ("apex-boost", "Apex Буст", "буст ранга Apex"),
    ("wow-boost", "WoW Буст", "буст в World of Warcraft"),
    ("tarkov-boost", "Tarkov Буст", "прокачка в Escape from Tarkov"),
    ("genshin-farm", "Genshin Фарм", "фарм в Genshin Impact"),
    ("destiny-carry", "Destiny 2 Carry", "рейды в Destiny 2"),
    ("fifa-coins", "FIFA Монеты", "монеты FIFA Ultimate Team"),
    ("pubg-boost", "PUBG Буст", "буст ранга PUBG"),
    ("cod-boost", "CoD Буст", "прокачка в Call of Duty"),
    ("overwatch-boost", "Overwatch Буст", "буст ранга Overwatch"),
    ("r6-boost", "R6 Буст", "буст ранга Rainbow Six"),
    ("brawl-boost", "Brawl Буст", "прокачка Brawl Stars"),
]

MONITORING = [
    ("price-monitor", "Мониторинг Цен", "отслеживание цен"),
    ("wb-monitor", "Wildberries Монитор", "мониторинг цен Wildberries"),
    ("ozon-monitor", "Ozon Монитор", "мониторинг цен Ozon"),
    ("avito-monitor", "Авито Монитор", "мониторинг объявлений Авито"),
    ("steam-monitor", "Steam Монитор", "мониторинг скидок Steam"),
    ("skins-monitor", "Мониторинг Скинов", "мониторинг цен на скины"),
    ("crypto-alerts", "Крипто Алерты", "оповещения о курсах криптовалют"),
    ("whale-alerts", "Whale Alerts", "отслеживание крупных транзакций"),
    ("gas-monitor", "Gas Монитор", "мониторинг комиссий сети"),
    ("uptime-monitor", "Uptime Монитор", "мониторинг доступности сайтов"),
    ("domain-monitor", "Домен Монитор", "мониторинг освобождения доменов"),
    ("ssl-monitor", "SSL Монитор", "мониторинг сертификатов"),
    ("sneaker-monitor", "Sneaker Монитор", "мониторинг дропов кроссовок"),
    ("ticket-monitor", "Билет Монитор", "мониторинг билетов"),
    ("flight-monitor", "Авиа Монитор", "мониторинг цен на авиабилеты"),
    ("job-monitor", "Вакансии Монитор", "мониторинг вакансий"),
    ("tender-monitor", "Тендер Монитор", "мониторинг тендеров"),
    ("stock-monitor", "Наличие Монитор", "мониторинг наличия товара"),
    ("realty-monitor", "Недвижимость Монитор", "мониторинг объявлений недвижимости"),
    ("auction-monitor", "Аукцион Монитор", "мониторинг аукционов"),
]

CRYPTO_SERVICES = [
    ("crypto-exchange", "Обмен Крипты", "обмен криптовалют"),
    ("usdt-exchange", "USDT Обмен", "обмен USDT"),
    ("btc-exchange", "BTC Обмен", "обмен биткоина"),
    ("ton-exchange", "TON Обмен", "обмен TON"),
    ("cash-crypto", "Крипта за Наличные", "обмен крипты на наличные"),
    ("p2p-service", "P2P Сервис", "P2P-обмен"),
    ("crypto-wallet-setup", "Настройка Кошелька", "настройка криптокошелька"),
    ("crypto-tax-help", "Крипто Налоги", "отчётность по криптоактивам"),
    ("mining-rent", "Аренда Мощностей", "аренда мощностей для майнинга"),
    ("node-hosting", "Хостинг Нод", "хостинг блокчейн-нод"),
    ("smart-audit", "Аудит Контрактов", "аудит смарт-контрактов"),
    ("token-launch", "Запуск Токена", "запуск токена"),
]

# Note: no follower/view/review "boosting" products here. Those are sold as
# engagement but delivered as fakes — they breach every platform's terms and
# the buyer's customers are the ones deceived. The services below are real work.
DIGITAL_SERVICES = [
    ("design-service", "Дизайн на Заказ", "графический дизайн"),
    ("logo-service", "Логотипы", "разработка логотипов"),
    ("video-edit-service", "Видеостудия", "монтаж видео под ключ"),
    ("translate-service", "Переводы", "перевод текстов"),
    ("copywriting-service", "Копирайтинг", "написание текстов"),
    ("bot-dev-service", "Боты на Заказ", "разработка Telegram-ботов"),
    ("site-dev-service", "Сайты на Заказ", "разработка сайтов"),
    ("hosting-service", "Хостинг", "хостинг и VPS"),
    ("domain-service", "Домены", "регистрация доменов"),
]


#: Products with no meaningful market outside Russia/CIS. Selling Кинопоиск
#: subscriptions or Авито accounts to a German buyer is not a product, so
#: these run in the RU fleet only.
RU_ONLY_SLUGS = {
    "kinopoisk", "ivi", "okko", "wink", "premier", "yandex-plus", "vk-music",
    "zvuk", "start", "more-tv", "litres",
    "vkontakte", "odnoklassniki", "rutube", "dzen", "likee", "kwai",
    "yandex-mail", "mailru", "yandex-disk", "firstmail",
    "avito-acc", "wildberries-acc", "ozon-acc", "yandex-go",
    "skillbox", "warface", "standoff2", "standoff-gold",
}

#: English names for entries whose "brand" is really a Russian phrase. Without
#: this the EU fleet would ship bots called «Обмен Крипты».
EN_BRANDS = {
    # proxies / privacy
    "http-proxy": "HTTP Proxies", "mobile-proxy": "Mobile Proxies",
    "residential-proxy": "Residential Proxies", "static-proxy": "Static Proxies",
    "sms-numbers": "Virtual Numbers",
    # keys
    "game-keys-shop": "Game Keys", "antivirus-key": "Antivirus",
    # monitoring
    "price-monitor": "Price Watch", "wb-monitor": "Marketplace Price Watch",
    "ozon-monitor": "Retail Price Watch", "avito-monitor": "Classifieds Watch",
    "steam-monitor": "Steam Deals", "skins-monitor": "Skin Price Watch",
    "crypto-alerts": "Crypto Alerts", "whale-alerts": "Whale Alerts",
    "gas-monitor": "Gas Fee Watch", "uptime-monitor": "Uptime Watch",
    "domain-monitor": "Domain Drop Watch", "ssl-monitor": "SSL Expiry Watch",
    "sneaker-monitor": "Sneaker Drops", "ticket-monitor": "Ticket Watch",
    "flight-monitor": "Flight Price Watch", "job-monitor": "Job Alerts",
    "tender-monitor": "Tender Alerts", "stock-monitor": "Restock Alerts",
    "realty-monitor": "Property Alerts", "auction-monitor": "Auction Alerts",
    # boosting
    "cs2-rank-boost": "CS2 Boosting", "dota-mmr": "Dota 2 MMR Boosting",
    "valorant-boost": "Valorant Boosting", "lol-boost": "LoL Boosting",
    "apex-boost": "Apex Boosting", "wow-boost": "WoW Boosting",
    "tarkov-boost": "Tarkov Boosting", "genshin-farm": "Genshin Farming",
    "destiny-carry": "Destiny 2 Carries", "fifa-coins": "FUT Coins",
    "pubg-boost": "PUBG Boosting", "cod-boost": "CoD Boosting",
    "overwatch-boost": "Overwatch Boosting", "r6-boost": "Rainbow Six Boosting",
    "brawl-boost": "Brawl Stars Boosting",
    # crypto services
    "crypto-exchange": "Crypto Exchange", "usdt-exchange": "USDT Exchange",
    "btc-exchange": "BTC Exchange", "ton-exchange": "TON Exchange",
    "cash-crypto": "Crypto to Cash", "p2p-service": "P2P Desk",
    "crypto-wallet-setup": "Wallet Setup", "crypto-tax-help": "Crypto Tax Reports",
    "mining-rent": "Hashrate Rental", "node-hosting": "Node Hosting",
    "smart-audit": "Contract Audits", "token-launch": "Token Launch",
    # digital services
    "design-service": "Graphic Design", "logo-service": "Logo Design",
    "video-edit-service": "Video Studio", "translate-service": "Translation",
    "copywriting-service": "Copywriting", "bot-dev-service": "Custom Bots",
    "site-dev-service": "Web Development", "hosting-service": "Managed Hosting",
    "domain-service": "Domain Registration",
    # top-ups
    "steam-wallet": "Steam Wallet", "telegram-stars-topup": "Telegram Stars",
    "discord-boost": "Discord Boosts",
}

# --------------------------------------------------------------------------
# Expansion
# --------------------------------------------------------------------------

#: category → (archetype, tier, name suffix, tagline template)
CATEGORY_META = {
    "gaming_accounts":   ("accounts", "budget",   "Аккаунты", "{brand}: моментальная выдача, гарантия и замена"),
    "streaming":         ("accounts", "budget",   "Подписки", "{brand} дешевле официальной подписки, выдача сразу"),
    "ai":                ("accounts", "standard", "Доступ",   "{brand} без карты и VPN — доступ за минуту"),
    "social":            ("accounts", "budget",   "Аккаунты", "{brand}: отлежавшиеся аккаунты с гарантией"),
    "email_cloud":       ("accounts", "budget",   "Аккаунты", "{brand}: чистые аккаунты для работы и регистраций"),
    "dev_work":          ("accounts", "standard", "Доступ",   "{brand} по цене в разы ниже подписки"),
    "vpn_proxy":         ("accounts", "budget",   "Доступ",   "{brand}: быстрая выдача, замена при проблемах"),
    "crypto_accounts":   ("accounts", "premium",  "Аккаунты", "{brand}: верифицированные аккаунты под задачи"),
    "marketplace":       ("accounts", "standard", "Аккаунты", "{brand}: готовые аккаунты для работы"),
    "keys":              ("keys",     "standard", "",         "{brand}: ключи и коды с моментальной выдачей"),
    "game_topup":        ("topup",    "budget",   "",         "{brand}: пополнение по выгодному курсу за 15 минут"),
    "game_services":     ("service",  "standard", "",         "{brand}: результат под ключ, оплата после согласования"),
    "monitoring":        ("monitor",  "standard", "",         "{brand}: уведомления в этот чат в реальном времени"),
    "crypto_services":   ("service",  "premium",  "",         "{brand}: быстро, по курсу, без лишних вопросов"),
    "digital_services":  ("service",  "standard", "",         "{brand}: делаем под ключ, сроки фиксируем"),
}

CATEGORIES = {
    "gaming_accounts": GAMING_ACCOUNTS,
    "streaming": STREAMING_ACCOUNTS,
    "ai": AI_ACCOUNTS,
    "social": SOCIAL_ACCOUNTS,
    "email_cloud": EMAIL_CLOUD_ACCOUNTS,
    "dev_work": DEV_WORK_ACCOUNTS,
    "vpn_proxy": VPN_PROXY_ACCOUNTS,
    "crypto_accounts": CRYPTO_ACCOUNTS,
    "marketplace": MARKETPLACE_ACCOUNTS,
    "keys": KEYS_AND_CARDS,
    "game_topup": GAME_TOPUP,
    "game_services": GAME_SERVICES,
    "monitoring": MONITORING,
    "crypto_services": CRYPTO_SERVICES,
    "digital_services": DIGITAL_SERVICES,
}

# English copy for the EU/USA half of the fleet.
EN_META = {
    "gaming_accounts":   ("accounts", "budget",   "Accounts", "{brand} accounts — instant delivery, warranty included"),
    "streaming":         ("accounts", "budget",   "Subs",     "{brand} for less than the official plan, delivered instantly"),
    "ai":                ("accounts", "standard", "Access",   "{brand} access in under a minute, no card needed"),
    "social":            ("accounts", "budget",   "Accounts", "{brand}: aged accounts with a replacement warranty"),
    "email_cloud":       ("accounts", "budget",   "Accounts", "{brand}: clean accounts for work and sign-ups"),
    "dev_work":          ("accounts", "standard", "Access",   "{brand} at a fraction of the subscription price"),
    "vpn_proxy":         ("accounts", "budget",   "Access",   "{brand}: fast delivery, replaced if anything fails"),
    "crypto_accounts":   ("accounts", "premium",  "Accounts", "{brand}: verified accounts, ready to trade"),
    "marketplace":       ("accounts", "standard", "Accounts", "{brand}: ready-to-use accounts for sellers"),
    "keys":              ("keys",     "standard", "Keys",     "{brand}: keys and codes delivered instantly"),
    "game_topup":        ("topup",    "budget",   "Top-Up",   "{brand} top-ups at a better rate, credited in 15 minutes"),
    "game_services":     ("service",  "standard", "",         "{brand}: done for you, agreed before you pay"),
    "monitoring":        ("monitor",  "standard", "Monitor",  "{brand}: real-time alerts straight into this chat"),
    "crypto_services":   ("service",  "premium",  "",         "{brand}: fast, fair rate, no runaround"),
    "digital_services":  ("service",  "standard", "",         "{brand}: delivered turnkey on a fixed timeline"),
}

EN_TOPICS = {
    "gaming_accounts": "{brand} game accounts",
    "streaming": "{brand} subscriptions",
    "ai": "{brand} AI access",
    "social": "{brand} social accounts",
    "email_cloud": "{brand} email and cloud accounts",
    "dev_work": "{brand} software access",
    "vpn_proxy": "{brand} privacy access",
    "crypto_accounts": "{brand} exchange accounts",
    "marketplace": "{brand} marketplace accounts",
    "keys": "{brand} keys and gift cards",
    "game_topup": "{brand} in-game currency",
    "game_services": "{brand} boosting services",
    "monitoring": "{brand} alerts",
    "crypto_services": "{brand} crypto services",
    "digital_services": "{brand} digital services",
}


# --------------------------------------------------------------------------
# EU/USA-only categories. The Western market buys tooling and infrastructure
# subscriptions that have little RU demand, so these 100 run in the EU fleet
# only, bringing it to 400 shop bots.
# --------------------------------------------------------------------------

EU_SAAS_TOOLS = [
    ("hubspot", "HubSpot", "CRM access"),
    ("salesforce", "Salesforce", "CRM access"),
    ("mailchimp", "Mailchimp", "email marketing access"),
    ("klaviyo", "Klaviyo", "email marketing access"),
    ("activecampaign", "ActiveCampaign", "automation access"),
    ("semrush", "Semrush", "SEO tool access"),
    ("ahrefs", "Ahrefs", "SEO tool access"),
    ("moz-pro", "Moz Pro", "SEO tool access"),
    ("similarweb", "Similarweb", "analytics access"),
    ("hotjar", "Hotjar", "analytics access"),
    ("mixpanel", "Mixpanel", "product analytics access"),
    ("amplitude", "Amplitude", "product analytics access"),
    ("segment", "Segment", "data pipeline access"),
    ("intercom", "Intercom", "support tool access"),
    ("zendesk", "Zendesk", "helpdesk access"),
    ("freshdesk", "Freshdesk", "helpdesk access"),
    ("calendly", "Calendly", "scheduling access"),
    ("typeform", "Typeform", "form tool access"),
    ("airtable", "Airtable", "database access"),
    ("monday", "Monday.com", "project tool access"),
    ("clickup", "ClickUp", "project tool access"),
    ("linear-app", "Linear", "issue tracker access"),
    ("jira", "Jira", "issue tracker access"),
    ("confluence", "Confluence", "wiki access"),
    ("basecamp", "Basecamp", "project tool access"),
]

EU_HOSTING_INFRA = [
    ("aws-acc", "AWS", "cloud accounts"),
    ("gcp-acc", "Google Cloud", "cloud accounts"),
    ("azure-acc", "Azure", "cloud accounts"),
    ("digitalocean", "DigitalOcean", "VPS accounts"),
    ("hetzner", "Hetzner", "server accounts"),
    ("vultr", "Vultr", "VPS accounts"),
    ("linode", "Akamai Linode", "VPS accounts"),
    ("cloudflare-acc", "Cloudflare", "CDN accounts"),
    ("vercel", "Vercel", "hosting accounts"),
    ("netlify", "Netlify", "hosting accounts"),
    ("railway-app", "Railway", "hosting accounts"),
    ("render-com", "Render", "hosting accounts"),
    ("fly-io", "Fly.io", "hosting accounts"),
    ("namecheap", "Namecheap", "domain accounts"),
    ("godaddy", "GoDaddy", "domain accounts"),
]

EU_CREATIVE = [
    ("adobe-stock", "Adobe Stock", "stock media access"),
    ("getty", "Getty Images", "stock media access"),
    ("unsplash-plus", "Unsplash+", "stock media access"),
    ("artlist", "Artlist", "music licence access"),
    ("epidemic-sound", "Epidemic Sound", "music licence access"),
    ("motion-array", "Motion Array", "template access"),
    ("placeit", "Placeit", "mockup access"),
    ("capcut-pro", "CapCut Pro", "editor access"),
    ("filmora", "Filmora", "editor access"),
    ("davinci", "DaVinci Resolve", "editor licences"),
    ("affinity", "Affinity", "design licences"),
    ("sketch-app", "Sketch", "design access"),
    ("procreate", "Procreate", "app licences"),
    ("blender-market", "Blender Market", "asset access"),
    ("skillshare", "Skillshare", "course access"),
]

EU_FINANCE_TOOLS = [
    ("quickbooks", "QuickBooks", "accounting access"),
    ("xero", "Xero", "accounting access"),
    ("freshbooks", "FreshBooks", "invoicing access"),
    ("stripe-atlas", "Stripe Atlas", "incorporation help"),
    ("tradingview", "TradingView", "charting access"),
    ("koyfin", "Koyfin", "market data access"),
    ("seeking-alpha", "Seeking Alpha", "research access"),
    ("morningstar", "Morningstar", "research access"),
    ("bloomberg-lite", "Market Data", "market data access"),
    ("yahoo-finance-plus", "Yahoo Finance Plus", "research access"),
    ("wsj", "WSJ", "news subscriptions"),
    ("ft-com", "Financial Times", "news subscriptions"),
    ("economist", "The Economist", "news subscriptions"),
    ("nyt", "New York Times", "news subscriptions"),
    ("bloomberg-news", "Bloomberg", "news subscriptions"),
]

EU_SECURITY = [
    ("1password", "1Password", "password manager access"),
    ("bitwarden", "Bitwarden", "password manager access"),
    ("lastpass", "LastPass", "password manager access"),
    ("dashlane", "Dashlane", "password manager access"),
    ("malwarebytes", "Malwarebytes", "security licences"),
    ("bitdefender", "Bitdefender", "security licences"),
    ("kaspersky-eu", "Kaspersky", "security licences"),
    ("eset", "ESET", "security licences"),
    ("norton", "Norton", "security licences"),
    ("mcafee", "McAfee", "security licences"),
]

EU_LEARNING = [
    ("datacamp", "DataCamp", "course access"),
    ("pluralsight", "Pluralsight", "course access"),
    ("codecademy", "Codecademy", "course access"),
    ("educative", "Educative", "course access"),
    ("frontend-masters", "Frontend Masters", "course access"),
    ("leetcode-premium", "LeetCode Premium", "practice access"),
    ("brilliant", "Brilliant", "course access"),
    ("masterclass", "MasterClass", "course access"),
    ("babbel", "Babbel", "language access"),
    ("busuu", "Busuu", "language access"),
    ("rosetta", "Rosetta Stone", "language access"),
    ("italki", "italki", "tutoring credits"),
    ("preply", "Preply", "tutoring credits"),
    ("khan-plus", "Khan Academy", "course access"),
    ("edx", "edX", "course access"),
    ("futurelearn", "FutureLearn", "course access"),
    ("mindvalley", "Mindvalley", "course access"),
    ("blinkist", "Blinkist", "summaries access"),
    ("headway-app", "Headway", "summaries access"),
    ("scribd", "Scribd", "library access"),
    ("audible-plus", "Audible Plus", "audiobook access"),
    ("coursera-plus", "Coursera Plus", "course access"),
    ("udacity", "Udacity", "nanodegree access"),
]

EU_GAMING_EXTRA = [
    ("gamivo", "Gamivo", "game key marketplace accounts"),
    ("g2a-acc", "G2A", "marketplace accounts"),
    ("humble-bundle", "Humble Bundle", "bundle accounts"),
    ("fanatical", "Fanatical", "store accounts"),
    ("greenman", "Green Man Gaming", "store accounts"),
    ("itch-io", "itch.io", "store accounts"),
    ("geforce-now", "GeForce Now", "cloud gaming access"),
    ("shadow-pc", "Shadow PC", "cloud PC access"),
    ("boosteroid", "Boosteroid", "cloud gaming access"),
    ("faceit", "FACEIT", "competitive accounts"),
    ("esea", "ESEA", "competitive accounts"),
    ("gamersclub", "GamersClub", "competitive accounts"),
]

EU_PRODUCTIVITY = [
    ("evernote", "Evernote", "notes access"),
    ("todoist", "Todoist", "task manager access"),
    ("obsidian-sync", "Obsidian Sync", "sync access"),
    ("roam", "Roam Research", "notes access"),
    ("superhuman", "Superhuman", "email access"),
    ("grammarly-biz", "Grammarly Business", "writing access"),
    ("loom", "Loom", "video messaging access"),
    ("descript-pro", "Descript Pro", "editor access"),
    ("zapier", "Zapier", "automation access"),
    ("make-com", "Make", "automation access"),
    ("n8n-cloud", "n8n Cloud", "automation access"),
    ("ifttt-pro", "IFTTT Pro", "automation access"),
    ("readwise", "Readwise", "reading access"),
    ("raycast", "Raycast Pro", "productivity access"),
]

EU_ONLY = {
    "eu_saas":     ("accounts", "standard", "Access", "{brand} access without a company card"),
    "eu_hosting":  ("accounts", "standard", "Accounts", "{brand}: ready accounts and credits"),
    "eu_creative": ("accounts", "budget",   "Access", "{brand} for a fraction of the licence price"),
    "eu_finance":  ("accounts", "premium",  "Access", "{brand}: research and data access on demand"),
    "eu_security": ("keys",     "budget",   "Keys",   "{brand} licence keys, delivered instantly"),
    "eu_learning": ("accounts", "budget",   "Access", "{brand} course access at a fraction of the price"),
    "eu_gaming":   ("accounts", "budget",   "Accounts", "{brand}: ready accounts, instant delivery"),
    "eu_prod":     ("accounts", "standard", "Access", "{brand} without a yearly commitment"),
}

EU_ONLY_CATEGORIES = {
    "eu_saas": EU_SAAS_TOOLS,
    "eu_hosting": EU_HOSTING_INFRA,
    "eu_creative": EU_CREATIVE,
    "eu_finance": EU_FINANCE_TOOLS,
    "eu_security": EU_SECURITY,
    "eu_learning": EU_LEARNING,
    "eu_gaming": EU_GAMING_EXTRA,
    "eu_prod": EU_PRODUCTIVITY,
}


def _entry(slug, archetype, name, tagline, topic, tier, region, lang, currency):
    return {
        "slug": slug,
        "archetype": archetype,
        "name": name,
        "tagline": tagline,
        "topic": topic,
        "tier": tier,
        "region": region,
        "lang": lang,
        "currency": currency,
    }


def ru_shop_entries() -> list[dict]:
    out: list[dict] = []
    for category, items in CATEGORIES.items():
        archetype, tier, suffix, tagline_tpl = CATEGORY_META[category]
        for slug, brand, topic in items:
            name = f"{brand} {suffix}".strip()
            out.append(
                _entry(
                    slug,
                    archetype,
                    name,
                    tagline_tpl.format(brand=brand),
                    topic,
                    tier,
                    "ru",
                    "ru",
                    "RUB",
                )
            )
    return out


def eu_shop_entries() -> list[dict]:
    out: list[dict] = []
    for category, items in EU_ONLY_CATEGORIES.items():
        archetype, tier, suffix, tagline_tpl = EU_ONLY[category]
        for slug, brand, topic in items:
            out.append(
                _entry(
                    f"{slug}-eu",
                    archetype,
                    f"{brand} {suffix}".strip(),
                    tagline_tpl.format(brand=brand),
                    f"{brand} {topic}",
                    tier,
                    "eu",
                    "en",
                    "EUR",
                )
            )

    for category, items in CATEGORIES.items():
        archetype, tier, suffix, tagline_tpl = EN_META[category]
        topic_tpl = EN_TOPICS[category]
        for slug, brand, _ru_topic in items:
            if slug in RU_ONLY_SLUGS:
                continue
            brand = EN_BRANDS.get(slug, brand)
            name = f"{brand} {suffix}".strip()
            out.append(
                _entry(
                    f"{slug}-eu",
                    archetype,
                    name,
                    tagline_tpl.format(brand=brand),
                    topic_tpl.format(brand=brand),
                    tier,
                    "eu",
                    "en",
                    "EUR",
                )
            )
    return out


if __name__ == "__main__":  # pragma: no cover - sanity check
    ru, eu = ru_shop_entries(), eu_shop_entries()
    slugs = [e["slug"] for e in ru + eu]
    assert len(slugs) == len(set(slugs)), "duplicate shop slugs"
    print(f"shop niches — RU: {len(ru)}  EU: {len(eu)}")
    for name, items in CATEGORIES.items():
        print(f"  {name:<20} {len(items)}")
