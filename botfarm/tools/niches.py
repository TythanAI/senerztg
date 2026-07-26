"""The niche catalogue: 200 RU + 100 EU/US products.

Each entry is (slug, archetype, name, tagline, topic, tier). The archetype
decides the business model — what is sold, in how many tiers, and which bot
modules are switched on. The generator expands an entry into a full,
deployable bot; nothing here is a placeholder.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# RU segment — 200 bots, priced in RUB, YooKassa + SBP + crypto + Stars.
# --------------------------------------------------------------------------

RU: list[tuple[str, str, str, str, str, str]] = [
    # ---- Финансы и инвестиции (18) ----
    ("invest-start", "course", "ИнвестСтарт", "Инвестиции с нуля: от первого счёта до портфеля", "инвестиции", "standard"),
    ("dividend-club", "club", "Дивидендный клуб", "Портфель на дивидендах: разборы и сделки", "дивидендные акции", "premium"),
    ("bond-lab", "course", "Облигации Лаб", "Облигации и фонды: доход выше вклада", "облигации", "standard"),
    ("trader-signals", "signals", "Трейдер Сигналы", "Сигналы по фьючерсам МосБиржи", "трейдинг", "premium"),
    ("finplan-pro", "consult", "ФинПлан Про", "Личный финансовый план за одну встречу", "финансовое планирование", "premium"),
    ("debt-free", "course", "Долги Стоп", "Пошаговый выход из кредитной ямы", "закрытие долгов", "budget"),
    ("budget-family", "saas", "Семейный Бюджет", "Учёт денег семьи без таблиц", "семейный бюджет", "budget"),
    ("pension-plan", "course", "Пенсия Сам", "Собственный пенсионный капитал", "пенсионные накопления", "standard"),
    ("tax-refund", "service", "Налог Возврат", "Возврат НДФЛ под ключ", "налоговые вычеты", "standard"),
    ("credit-score", "service", "Кредитный Рейтинг", "Поднимаем скоринг перед ипотекой", "кредитная история", "standard"),
    ("ipo-radar", "signals", "IPO Радар", "Разборы размещений и аллокации", "IPO", "premium"),
    ("etf-portfolio", "course", "ETF Портфель", "Пассивный портфель на фондах", "ETF", "standard"),
    ("forex-academy", "course", "Форекс Академия", "Валютный рынок: система, а не казино", "форекс", "premium"),
    ("options-desk", "club", "Опционный Стол", "Опционные стратегии на практике", "опционы", "elite"),
    ("bank-deals", "signals", "Банк Выгода", "Лучшие вклады, карты и кэшбэк недели", "банковские продукты", "budget"),
    ("realty-invest", "course", "Недвижка Инвест", "Доходная недвижимость без ипотеки", "инвестиции в недвижимость", "premium"),
    ("passive-income", "club", "Пассивный Доход", "Пять потоков дохода за год", "пассивный доход", "standard"),
    ("insurance-check", "consult", "Страховка Чек", "Аудит полисов и подбор защиты", "страхование", "standard"),

    # ---- Криптовалюты (14) ----
    ("crypto-base", "course", "Крипта База", "Первая крипта: кошельки, биржи, безопасность", "криптовалюты", "standard"),
    ("defi-farm", "club", "DeFi Ферма", "Фарминг и стейкинг с расчётом рисков", "DeFi", "premium"),
    ("nft-drop", "signals", "NFT Дроп", "Ранние дропы и вайтлисты", "NFT", "standard"),
    ("airdrop-hunter", "club", "Аирдроп Хантер", "Ретродропы: чек-листы и активности", "аирдропы", "standard"),
    ("btc-cycle", "signals", "BTC Цикл", "Циклический анализ биткоина", "биткоин", "premium"),
    ("altcoin-scan", "signals", "Альт Скан", "Скринер альткоинов и точки входа", "альткоины", "premium"),
    ("p2p-arbitrage", "course", "P2P Арбитраж", "Связки и работа с рисками P2P", "P2P-арбитраж", "premium"),
    ("mining-calc", "saas", "Майнинг Калькулятор", "Окупаемость ферм в реальном времени", "майнинг", "standard"),
    ("ton-dev", "course", "TON Разработка", "Смарт-контракты и мини-аппы TON", "разработка на TON", "premium"),
    ("crypto-tax-ru", "service", "Крипта Налог", "Декларация по криптоактивам", "налоги на крипту", "premium"),
    ("wallet-secure", "course", "Кошелёк Защита", "Как не потерять крипту: безопасность", "безопасность криптокошельков", "budget"),
    ("stables-yield", "club", "Стейбл Доход", "Доходность на стейблкоинах", "стейблкоины", "standard"),
    ("web3-jobs", "club", "Web3 Работа", "Вакансии и гранты web3", "работа в web3", "standard"),
    ("trading-bots", "saas", "Торговый Бот", "Сетки и DCA без программирования", "торговые боты", "premium"),

    # ---- Обучение и EdTech (20) ----
    ("english-daily", "club", "Английский Каждый День", "10 минут в день до уровня B2", "английский язык", "budget"),
    ("ielts-target", "course", "IELTS Цель", "Подготовка к IELTS на 7.0+", "IELTS", "premium"),
    ("chinese-start", "course", "Китайский Старт", "HSK 1-3 за четыре месяца", "китайский язык", "standard"),
    ("spanish-club", "club", "Испанский Клуб", "Разговорная практика с носителем", "испанский язык", "standard"),
    ("ege-math", "course", "ЕГЭ Математика", "Профиль на 80+ баллов", "ЕГЭ по математике", "standard"),
    ("ege-russian", "course", "ЕГЭ Русский", "Сочинение и тест без ошибок", "ЕГЭ по русскому", "standard"),
    ("oge-prep", "club", "ОГЭ Подготовка", "Все предметы девятого класса", "ОГЭ", "budget"),
    ("kids-logic", "club", "Детская Логика", "Задачи для 6-10 лет каждый день", "развитие детей", "budget"),
    ("speed-read", "course", "Скорочтение", "Читать втрое быстрее с пониманием", "скорочтение", "budget"),
    ("memory-gym", "saas", "Тренажёр Памяти", "Мнемотехники и ежедневные тренировки", "тренировка памяти", "budget"),
    ("essay-help", "service", "Помощь с Работой", "Курсовые и дипломы под ключ", "учебные работы", "premium"),
    ("uni-abroad", "consult", "Универ за Рубежом", "Поступление в вузы Европы", "образование за рубежом", "elite"),
    ("prof-orient", "consult", "Профориентация", "Выбор профессии по данным, а не по интуиции", "профориентация", "standard"),
    ("teacher-tools", "saas", "Учитель Инструменты", "Генератор заданий и проверок", "инструменты для учителей", "standard"),
    ("music-theory", "course", "Теория Музыки", "От нот до собственных треков", "теория музыки", "standard"),
    ("guitar-start", "course", "Гитара Старт", "Первые песни за 30 дней", "игра на гитаре", "budget"),
    ("public-speak", "course", "Публичные Выступления", "Речь, которая держит зал", "ораторское мастерство", "premium"),
    ("writing-craft", "club", "Мастерская Текста", "Пишем сильные тексты каждую неделю", "копирайтинг", "standard"),
    ("chess-school", "club", "Шахматная Школа", "Разборы партий и дебютный репертуар", "шахматы", "standard"),
    ("math-olymp", "club", "Олимпиадная Математика", "Задачи всероса с разборами", "олимпиадная математика", "standard"),

    # ---- Здоровье, фитнес, питание (18) ----
    ("fit-home", "club", "Фит Дома", "Тренировки без зала, 20 минут в день", "домашние тренировки", "budget"),
    ("gym-program", "course", "Зал Программа", "Персональная программа на 12 недель", "тренировки в зале", "standard"),
    ("nutrition-plan", "service", "План Питания", "КБЖУ и меню под вашу цель", "питание", "standard"),
    ("keto-guide", "course", "Кето Гид", "Кето без ошибок и срывов", "кето-диета", "standard"),
    ("run-coach", "club", "Беговой Тренер", "От нуля до полумарафона", "бег", "standard"),
    ("yoga-daily", "club", "Йога Каждый День", "Практики по 15 минут", "йога", "budget"),
    ("sleep-fix", "course", "Сон Наладить", "Протокол восстановления сна", "качество сна", "budget"),
    ("back-health", "course", "Здоровая Спина", "Упражнения при сидячей работе", "здоровье спины", "standard"),
    ("women-health", "club", "Женское Здоровье", "Цикл, гормоны, самочувствие", "женское здоровье", "standard"),
    ("mens-power", "club", "Мужская Форма", "Тестостерон, сила, выносливость", "мужское здоровье", "standard"),
    ("quit-smoking", "course", "Бросить Курить", "21 день без сигарет", "отказ от курения", "budget"),
    ("detox-week", "course", "Детокс Неделя", "Мягкая перезагрузка организма", "детокс", "budget"),
    ("mama-fit", "club", "Мама в Форме", "Восстановление после родов", "фитнес для мам", "standard"),
    ("senior-fit", "club", "Актив 50+", "Движение и здоровье после пятидесяти", "фитнес 50+", "budget"),
    ("supplement-guide", "consult", "Нутрициолог Онлайн", "Подбор добавок по анализам", "нутрициология", "premium"),
    ("marathon-prep", "course", "Марафон Подготовка", "42 км: план на 16 недель", "марафон", "premium"),
    ("swim-tech", "course", "Техника Плавания", "Кроль без одышки", "плавание", "standard"),
    ("bio-age", "service", "Биовозраст", "Расшифровка анализов и план", "биохакинг", "elite"),

    # ---- Красота и уход (10) ----
    ("skin-care", "consult", "Косметолог Онлайн", "Индивидуальный уход по типу кожи", "уход за кожей", "standard"),
    ("makeup-school", "course", "Школа Макияжа", "Макияж на каждый день и вечер", "макияж", "standard"),
    ("hair-care", "course", "Уход за Волосами", "Восстановление после окрашивания", "уход за волосами", "budget"),
    ("nails-pro", "course", "Ногтевой Сервис", "Профессия мастера маникюра", "маникюр", "premium"),
    ("brows-master", "course", "Мастер Бровей", "Архитектура и окрашивание", "брови", "standard"),
    ("style-guide", "consult", "Стилист Онлайн", "Гардероб, который работает", "стиль и гардероб", "premium"),
    ("perfume-club", "club", "Парфюм Клуб", "Разборы ароматов и находки", "парфюмерия", "budget"),
    ("spa-home", "course", "SPA Дома", "Салонные процедуры своими руками", "домашний уход", "budget"),
    ("beauty-shop", "shop", "Бьюти Гайды", "Готовые гайды по уходу и макияжу", "бьюти-гайды", "budget"),
    ("tattoo-book", "leadgen", "Тату Запись", "Портфолио, эскизы и запись к мастеру", "татуировки", "standard"),

    # ---- Бизнес и маркетинг (20) ----
    ("smm-factory", "service", "SMM Фабрика", "Ведение соцсетей под ключ", "SMM", "premium"),
    ("target-ads", "course", "Таргет Про", "Реклама во ВК и Telegram Ads", "таргетированная реклама", "premium"),
    ("marketplace-wb", "course", "Wildberries Старт", "Первая поставка и выход в прибыль", "торговля на Wildberries", "premium"),
    ("ozon-seller", "course", "Ozon Продавец", "Карточки, реклама, юнит-экономика", "торговля на Ozon", "premium"),
    ("avito-flow", "course", "Авито Поток", "Продажи на Авито системно", "продажи на Авито", "standard"),
    ("sales-script", "shop", "Скрипты Продаж", "Готовые скрипты для отдела продаж", "скрипты продаж", "standard"),
    ("crm-setup", "service", "CRM Внедрение", "amoCRM и Битрикс24 под ключ", "внедрение CRM", "elite"),
    ("unit-econ", "course", "Юнит-Экономика", "Считаем прибыль до запуска", "юнит-экономика", "premium"),
    ("brand-pack", "service", "Бренд Пакет", "Логотип, фирстиль, гайдлайн", "брендинг", "premium"),
    ("content-plan", "saas", "Контент План", "Календарь публикаций и идеи", "контент-маркетинг", "standard"),
    ("email-flow", "course", "Email Воронки", "Письма, которые продают", "email-маркетинг", "standard"),
    ("seo-boost", "service", "SEO Рост", "Продвижение сайта в топ", "SEO", "elite"),
    ("landing-fast", "service", "Лендинг Быстро", "Продающая страница за 72 часа", "лендинги", "premium"),
    ("hr-hiring", "course", "Найм Без Боли", "Подбор команды на потоке", "подбор персонала", "premium"),
    ("franchise-buy", "consult", "Франшиза Аудит", "Проверяем франшизу до покупки", "франшизы", "elite"),
    ("business-plan", "service", "Бизнес-План", "План для банка и инвестора", "бизнес-планы", "premium"),
    ("import-china", "course", "Импорт из Китая", "Поставщики, логистика, таможня", "импорт из Китая", "premium"),
    ("tender-win", "course", "Тендеры 44-ФЗ", "Выигрываем госзакупки", "тендеры", "premium"),
    ("local-biz", "leadgen", "Локальный Бизнес", "Клиенты из вашего района", "локальный маркетинг", "standard"),
    ("ads-audit", "consult", "Аудит Рекламы", "Находим слив бюджета за час", "аудит рекламы", "premium"),

    # ---- IT и разработка (16) ----
    ("python-start", "course", "Python Старт", "От синтаксиса до первого проекта", "Python", "standard"),
    ("frontend-job", "course", "Фронтенд Работа", "React-разработчик за 6 месяцев", "фронтенд", "premium"),
    ("qa-manual", "course", "QA Тестировщик", "Вход в IT через тестирование", "тестирование ПО", "standard"),
    ("devops-lab", "course", "DevOps Лаб", "Docker, CI/CD, Kubernetes", "DevOps", "elite"),
    ("data-analyst", "course", "Аналитик Данных", "SQL, Python, дашборды", "аналитика данных", "premium"),
    ("ml-practice", "club", "ML Практика", "Разбор задач машинного обучения", "машинное обучение", "premium"),
    ("bot-dev", "course", "Разработка Ботов", "Telegram-боты как источник дохода", "разработка ботов", "premium"),
    ("game-dev", "course", "Геймдев Старт", "Unity: первая игра", "разработка игр", "premium"),
    ("mobile-dev", "course", "Мобильная Разработка", "Flutter от нуля до релиза", "мобильная разработка", "premium"),
    ("it-resume", "service", "IT Резюме", "Резюме и LinkedIn, которые зовут", "трудоустройство в IT", "standard"),
    ("code-review", "consult", "Код Ревью", "Разбор вашего кода экспертом", "код-ревью", "premium"),
    ("freelance-it", "club", "IT Фриланс", "Заказы, чеки, переговоры", "IT-фриланс", "standard"),
    ("cyber-def", "course", "Кибербезопасность", "Защита инфраструктуры на практике", "кибербезопасность", "elite"),
    ("linux-admin", "course", "Linux Админ", "Сервер под нагрузкой", "администрирование Linux", "premium"),
    ("nocode-app", "course", "Nocode Приложения", "Продукт без единой строки кода", "no-code", "standard"),
    ("ai-tools", "club", "Нейросети Практика", "Инструменты и промпты для работы", "нейросети", "standard"),

    # ---- Локальные услуги (16) ----
    ("repair-flat", "leadgen", "Ремонт Квартир", "Смета и бригада за один день", "ремонт квартир", "premium"),
    ("clean-service", "leadgen", "Клининг Заказ", "Уборка квартир и офисов", "клининг", "standard"),
    ("moving-help", "leadgen", "Переезд Просто", "Грузчики и транспорт по городу", "переезды", "standard"),
    ("plumber-call", "leadgen", "Сантехник Вызов", "Мастер за 60 минут", "сантехника", "standard"),
    ("electric-call", "leadgen", "Электрик Вызов", "Проводка, розетки, щиты", "электрика", "standard"),
    ("furniture-make", "leadgen", "Мебель на Заказ", "Кухни и шкафы по размерам", "мебель на заказ", "premium"),
    ("window-fit", "leadgen", "Окна Установка", "Замер, монтаж, гарантия", "остекление", "premium"),
    ("garden-care", "leadgen", "Уход за Участком", "Газон, обрезка, сезонные работы", "уход за участком", "standard"),
    ("pet-care", "leadgen", "Передержка Питомцев", "Догситтер и выгул", "уход за питомцами", "budget"),
    ("kids-party", "leadgen", "Детский Праздник", "Аниматоры и программа", "детские праздники", "standard"),
    ("photo-book", "leadgen", "Фотограф Запись", "Съёмка и обработка", "фотосъёмка", "standard"),
    ("wedding-plan", "consult", "Свадебный Организатор", "Свадьба без нервов", "организация свадеб", "elite"),
    ("tutor-find", "leadgen", "Подбор Репетитора", "Преподаватель под задачу", "репетиторы", "standard"),
    ("laundry-pick", "leadgen", "Химчистка Доставка", "Забираем и привозим", "химчистка", "budget"),
    ("locksmith-24", "leadgen", "Вскрытие Замков", "Аварийная служба 24/7", "вскрытие замков", "standard"),
    ("appliance-fix", "leadgen", "Ремонт Техники", "Стиральные, холодильники, плиты", "ремонт бытовой техники", "standard"),

    # ---- Хобби и творчество (14) ----
    ("photo-school", "course", "Школа Фото", "Съёмка и обработка на телефон", "фотография", "standard"),
    ("video-edit", "course", "Монтаж Видео", "Reels и Shorts, которые смотрят", "видеомонтаж", "standard"),
    ("draw-basics", "course", "Рисование с Нуля", "Скетчи и портреты", "рисование", "budget"),
    ("pottery-club", "club", "Керамика Клуб", "Гончарное дело для начинающих", "керамика", "standard"),
    ("knit-patterns", "shop", "Вязание Схемы", "Авторские схемы и описания", "вязание", "budget"),
    ("cook-school", "club", "Кулинарная Школа", "Новое блюдо каждую неделю", "кулинария", "budget"),
    ("bake-pro", "course", "Кондитер Про", "Торты на заказ как бизнес", "кондитерское дело", "premium"),
    ("wine-club", "club", "Винный Клуб", "Дегустации и подбор вин", "вино", "standard"),
    ("garden-home", "club", "Домашний Сад", "Растения, которые не гибнут", "комнатные растения", "budget"),
    ("fish-spots", "club", "Рыбные Места", "Клёв, снасти, точки", "рыбалка", "budget"),
    ("hunt-gear", "shop", "Охота Снаряжение", "Гайды по экипировке и сезонам", "охота", "standard"),
    ("model-craft", "shop", "Моделизм", "Схемы и наборы для сборки", "моделизм", "standard"),
    ("music-prod", "course", "Продюсирование Музыки", "Свой трек от идеи до релиза", "музыкальное продюсирование", "premium"),
    ("dance-home", "club", "Танцы Дома", "Хореография по видеоурокам", "танцы", "budget"),

    # ---- Путешествия (8) ----
    ("cheap-flights", "signals", "Дешёвые Билеты", "Ошибочные тарифы и распродажи", "авиабилеты", "budget"),
    ("visa-help", "service", "Виза Помощь", "Documents и запись в консульство", "визы", "premium"),
    ("tour-select", "leadgen", "Подбор Тура", "Отдых под бюджет и даты", "туры", "standard"),
    ("road-trip", "shop", "Автопутешествия", "Маршруты по России с точками", "автопутешествия", "budget"),
    ("hotel-deals", "signals", "Отели Выгодно", "Скидки и ошибки бронирования", "отели", "budget"),
    ("relocate-help", "consult", "Релокация Консультация", "Переезд: страна, статус, налоги", "релокация", "elite"),
    ("camp-gear", "shop", "Походное Снаряжение", "Списки и обзоры для походов", "походы", "budget"),
    ("city-guides", "shop", "Гиды по Городам", "Маршруты на 2-3 дня", "городские гиды", "budget"),

    # ---- Авто (8) ----
    ("car-select", "consult", "Подбор Авто", "Проверка и выбор машины", "подбор автомобиля", "premium"),
    ("car-diag", "leadgen", "Автодиагностика", "Выездная проверка перед покупкой", "диагностика авто", "standard"),
    ("car-parts", "shop", "Автозапчасти Гид", "Каталоги и подбор по VIN", "автозапчасти", "standard"),
    ("driving-exam", "course", "Экзамен ГИБДД", "Теория и площадка с первого раза", "экзамен в ГИБДД", "budget"),
    ("car-tuning", "club", "Тюнинг Клуб", "Доработки и разборы проектов", "тюнинг", "standard"),
    ("truck-work", "club", "Дальнобой Работа", "Рейсы, ставки, документы", "грузоперевозки", "standard"),
    ("moto-school", "course", "Мотошкола", "Первый сезон без падений", "мотоциклы", "standard"),
    ("evcar-guide", "course", "Электромобиль Гид", "Покупка и эксплуатация в России", "электромобили", "standard"),

    # ---- Недвижимость (8) ----
    ("mortgage-calc", "consult", "Ипотека Консультант", "Одобрение и снижение ставки", "ипотека", "premium"),
    ("flat-buy", "leadgen", "Покупка Квартиры", "Подбор и сопровождение сделки", "покупка квартиры", "elite"),
    ("rent-flow", "saas", "Аренда Поток", "Учёт арендаторов и платежей", "управление арендой", "standard"),
    ("newbuild-scan", "signals", "Новостройки Скан", "Старты продаж и скидки", "новостройки", "standard"),
    ("dacha-build", "course", "Дом Построить", "Каркасник своими силами", "строительство дома", "premium"),
    ("interior-design", "service", "Дизайн Интерьера", "Планировка и визуализация", "дизайн интерьера", "elite"),
    ("realtor-school", "course", "Школа Риелтора", "Профессия с нуля до сделок", "работа риелтором", "premium"),
    ("land-check", "consult", "Проверка Участка", "Юридическая чистота земли", "земельные участки", "premium"),

    # ---- Юридические и бухгалтерские услуги (8) ----
    ("law-consult", "consult", "Юрист Онлайн", "Консультация по вашему вопросу", "юридические консультации", "premium"),
    ("bankrupt-help", "service", "Банкротство Физлиц", "Списание долгов законно", "банкротство", "elite"),
    ("ip-register", "service", "Регистрация ИП", "ИП и ООО под ключ", "регистрация бизнеса", "standard"),
    ("accounting-out", "service", "Бухгалтерия Аутсорс", "Отчётность и зарплата", "бухгалтерия", "premium"),
    ("labor-rights", "consult", "Трудовые Споры", "Увольнение, зарплата, суд", "трудовое право", "premium"),
    ("family-law", "consult", "Семейный Юрист", "Развод, алименты, раздел", "семейное право", "premium"),
    ("auto-law", "consult", "Автоюрист", "ДТП, страховая, лишение прав", "автоправо", "premium"),
    ("contract-check", "service", "Проверка Договора", "Правки и риски за 24 часа", "проверка договоров", "standard"),

    # ---- Психология и отношения (10) ----
    ("psy-online", "consult", "Психолог Онлайн", "Сессии в удобное время", "психотерапия", "premium"),
    ("anxiety-help", "course", "Тревога Под Контроль", "Протокол работы с тревогой", "тревожность", "standard"),
    ("burnout-fix", "course", "Выгорание Стоп", "Восстановление ресурса за 6 недель", "выгорание", "standard"),
    ("relations-club", "club", "Отношения Клуб", "Практики для пар", "отношения", "standard"),
    ("dating-guide", "course", "Знакомства Гид", "Онлайн-дейтинг без иллюзий", "знакомства", "budget"),
    ("parent-school", "club", "Школа Родителей", "Возрастные кризисы без криков", "воспитание детей", "standard"),
    ("self-esteem", "course", "Самооценка", "Опора на себя за 30 дней", "самооценка", "standard"),
    ("habits-lab", "saas", "Лаборатория Привычек", "Трекер и разборы срывов", "привычки", "budget"),
    ("meditation", "club", "Медитация Каждый День", "Практики осознанности", "медитация", "budget"),
    ("career-coach", "consult", "Карьерный Коуч", "Рост, оффер, переговоры о зарплате", "карьерный коучинг", "elite"),

    # ---- Игры и киберспорт (12) ----
    ("cs2-boost", "service", "CS2 Прокачка", "Апгрейд ранга с тренером", "CS2", "standard"),
    ("dota-coach", "consult", "Dota Тренер", "Разбор реплеев и стратегия", "Dota 2", "standard"),
    ("wot-guide", "club", "Танки Гайды", "Билды и тактика World of Tanks", "World of Tanks", "budget"),
    ("mobile-legends", "club", "Мобильные Легенды", "Мета, герои, тактика", "мобильные MOBA", "budget"),
    ("game-keys", "shop", "Ключи Игр", "Активации и подписки", "ключи для игр", "standard"),
    ("steam-skins", "signals", "Скины Сигналы", "Движение цен и выгодные лоты", "скины CS2", "premium"),
    ("streamer-start", "course", "Стример Старт", "Первая тысяча зрителей", "стриминг", "standard"),
    ("minecraft-serv", "saas", "Майнкрафт Сервер", "Свой сервер за пять минут", "серверы Minecraft", "budget"),
    ("fifa-trade", "course", "FIFA Трейд", "Заработок на трансферном рынке", "FIFA Ultimate Team", "standard"),
    ("poker-school", "course", "Покерная Школа", "Матанализ вместо интуиции", "покер", "premium"),
    ("esports-bets", "signals", "Киберспорт Аналитика", "Разборы матчей и статистика", "киберспортивная аналитика", "premium"),
    ("retro-games", "shop", "Ретро Игры", "Эмуляторы, ромы, настройка", "ретро-гейминг", "budget"),
]


# --------------------------------------------------------------------------
# EU/US segment — 100 bots, priced in EUR/USD, Stripe + crypto + Stars.
# --------------------------------------------------------------------------

EU: list[tuple[str, str, str, str, str, str, str]] = [
    # (slug, archetype, name, tagline, topic, tier, lang)
    # ---- Finance & investing (12) ----
    ("index-investing", "course", "Index Investing 101", "Build a lazy portfolio that beats most funds", "index investing", "standard", "en"),
    ("dividend-income", "club", "Dividend Income Club", "Monthly dividend picks and payout tracking", "dividend investing", "premium", "en"),
    ("fire-plan", "course", "FIRE Blueprint", "Retire two decades early on a normal salary", "financial independence", "premium", "en"),
    ("options-income", "signals", "Options Income Desk", "Weekly premium-selling setups", "options trading", "premium", "en"),
    ("debt-payoff", "course", "Debt Payoff Plan", "Escape consumer debt in 18 months", "debt payoff", "budget", "en"),
    ("budget-app", "saas", "Zero-Based Budget", "Every euro assigned, every month", "budgeting", "budget", "en"),
    ("tax-eu", "consult", "EU Tax Advisor", "Cross-border tax planning for freelancers", "EU taxation", "elite", "en"),
    ("pension-eu", "course", "Private Pension EU", "Second and third pillar, explained", "pension planning", "standard", "de"),
    ("etf-sparplan", "course", "ETF Sparplan", "Vermögensaufbau mit ETF-Sparplänen", "ETF-Sparpläne", "standard", "de"),
    ("swing-trader", "signals", "Swing Trader Pro", "Daily swing setups on US equities", "swing trading", "premium", "en"),
    ("real-estate-eu", "course", "EU Property Investing", "Buy-to-let across the eurozone", "property investing", "premium", "en"),
    ("side-income", "club", "Side Income Lab", "A tested income experiment every month", "side income", "standard", "en"),

    # ---- Crypto & web3 (10) ----
    ("crypto-101-eu", "course", "Crypto Foundations", "Self-custody, exchanges, and risk", "cryptocurrency", "standard", "en"),
    ("defi-yield-eu", "club", "DeFi Yield Room", "Audited yield strategies, weekly", "DeFi yield", "premium", "en"),
    ("onchain-signals", "signals", "On-Chain Signals", "Whale flows and exchange reserves", "on-chain analysis", "premium", "en"),
    ("nft-alpha-eu", "signals", "NFT Alpha", "Mints and floor moves before the crowd", "NFT trading", "standard", "en"),
    ("crypto-tax-eu", "service", "Crypto Tax Report", "Compliant reports for EU jurisdictions", "crypto taxation", "premium", "en"),
    ("solidity-dev", "course", "Solidity Developer", "Ship audited smart contracts", "Solidity", "elite", "en"),
    ("airdrop-eu", "club", "Airdrop Farming", "Testnet checklists and wallet hygiene", "airdrop farming", "standard", "en"),
    ("mining-eu", "saas", "Mining Profit Tracker", "Live ROI for your rigs", "crypto mining", "standard", "en"),
    ("stablecoin-yield", "club", "Stablecoin Yield", "Low-volatility crypto income", "stablecoin yield", "standard", "en"),
    ("web3-careers", "club", "Web3 Careers", "Vetted roles and grant deadlines", "web3 jobs", "standard", "en"),

    # ---- SaaS & developer tools (12) ----
    ("api-monitor", "saas", "API Uptime Monitor", "Know before your customers do", "API monitoring", "standard", "en"),
    ("code-mentor", "consult", "Code Mentor", "Senior review of your architecture", "code mentoring", "premium", "en"),
    ("saas-launch", "course", "SaaS Launch Kit", "Idea to first paying customer", "SaaS launch", "premium", "en"),
    ("indie-hacker", "club", "Indie Hacker Club", "Build in public with a real cohort", "indie hacking", "standard", "en"),
    ("aws-cost", "service", "Cloud Cost Audit", "Cut your AWS bill by 30%", "cloud cost optimisation", "elite", "en"),
    ("devops-eu", "course", "DevOps Pipeline", "Docker, CI/CD, and IaC in practice", "DevOps", "elite", "en"),
    ("python-eu", "course", "Python for Work", "Automate the boring parts of your job", "Python automation", "standard", "en"),
    ("data-eng", "course", "Data Engineering", "Pipelines that survive production", "data engineering", "elite", "en"),
    ("ai-prompts", "shop", "Prompt Library", "Battle-tested prompts by profession", "AI prompting", "budget", "en"),
    ("no-code-eu", "course", "No-Code Founder", "Ship a product without engineers", "no-code", "standard", "en"),
    ("security-audit", "service", "Security Audit", "Pen-test report for your web app", "security auditing", "elite", "en"),
    ("open-source", "club", "Open Source Path", "Land your first maintainer role", "open source", "standard", "en"),

    # ---- Health & fitness (12) ----
    ("home-hiit", "club", "Home HIIT", "20-minute sessions, no equipment", "home workouts", "budget", "en"),
    ("strength-plan", "course", "Strength Programme", "12 weeks to a real deadlift", "strength training", "standard", "en"),
    ("macro-coach", "service", "Macro Coaching", "Your numbers, recalculated weekly", "nutrition coaching", "premium", "en"),
    ("marathon-eu", "course", "Marathon Sub-4", "16-week plan with pacing charts", "marathon training", "premium", "en"),
    ("yoga-eu", "club", "Daily Yoga", "Fifteen minutes, every morning", "yoga", "budget", "en"),
    ("sleep-eu", "course", "Sleep Protocol", "Fix your sleep in three weeks", "sleep improvement", "budget", "en"),
    ("mobility-eu", "course", "Desk Worker Mobility", "Undo eight hours of sitting", "mobility training", "standard", "en"),
    ("ernaehrung", "course", "Ernährungsplan", "Individueller Plan für Ihr Ziel", "Ernährung", "standard", "de"),
    ("fitness-de", "club", "Fitness Zuhause", "Training ohne Studio, täglich", "Heimtraining", "budget", "de"),
    ("mental-fit", "club", "Mental Fitness", "Evidence-based habits for a calmer mind", "mental fitness", "standard", "en"),
    ("longevity", "consult", "Longevity Review", "Blood panel analysis and protocol", "longevity", "elite", "en"),
    ("nutricion-es", "course", "Nutrición Práctica", "Come bien sin dietas imposibles", "nutrición", "standard", "es"),

    # ---- Career & education (12) ----
    ("cv-rewrite", "service", "CV Rewrite", "ATS-proof CV and LinkedIn profile", "CV writing", "standard", "en"),
    ("interview-prep", "consult", "Interview Coaching", "Mock interviews with real feedback", "interview preparation", "premium", "en"),
    ("salary-nego", "course", "Salary Negotiation", "Add five figures to your offer", "salary negotiation", "standard", "en"),
    ("german-b1", "course", "German B1 Sprint", "Pass B1 in four months", "German language", "standard", "de"),
    ("english-biz", "club", "Business English", "Meetings, emails, presentations", "business English", "standard", "en"),
    ("spanish-es", "club", "Español Conversación", "Práctica diaria con correcciones", "español", "budget", "es"),
    ("pmp-prep", "course", "PMP Exam Prep", "Pass on the first attempt", "PMP certification", "premium", "en"),
    ("study-abroad", "consult", "Study Abroad EU", "Applications, visas, and funding", "studying abroad", "elite", "en"),
    ("freelance-start", "course", "Freelance Launch", "First five clients in 90 days", "freelancing", "standard", "en"),
    ("remote-jobs", "signals", "Remote Job Feed", "Vetted remote roles, daily", "remote work", "budget", "en"),
    ("public-speaking-eu", "course", "Speak with Impact", "Presentations people remember", "public speaking", "premium", "en"),
    ("notion-systems", "shop", "Notion Systems", "Templates that run your work", "Notion templates", "budget", "en"),

    # ---- Marketing & agency (12) ----
    ("meta-ads", "course", "Meta Ads Mastery", "Profitable campaigns, not vanity metrics", "Meta advertising", "premium", "en"),
    ("google-ads", "service", "Google Ads Management", "Managed search campaigns", "Google Ads", "elite", "en"),
    ("seo-eu", "service", "SEO Growth", "Rankings that convert", "SEO", "elite", "en"),
    ("email-eu", "course", "Email Revenue", "Flows that print money on autopilot", "email marketing", "standard", "en"),
    ("content-eu", "saas", "Content Calendar", "Plan a quarter in an afternoon", "content marketing", "standard", "en"),
    ("shopify-store", "service", "Shopify Store Build", "Launch-ready store in 10 days", "Shopify", "premium", "en"),
    ("amazon-fba", "course", "Amazon FBA EU", "Source, list, and scale across the EU", "Amazon FBA", "premium", "en"),
    ("copywriting-eu", "course", "Conversion Copywriting", "Words that sell without hype", "copywriting", "premium", "en"),
    ("branding-eu", "service", "Brand Identity", "Logo, system, and guidelines", "branding", "premium", "en"),
    ("tiktok-growth", "course", "Short-Form Growth", "Reels and TikTok that compound", "short-form video", "standard", "en"),
    ("agency-scale", "consult", "Agency Scaling", "From freelancer to a team of ten", "agency growth", "elite", "en"),
    ("marketing-de", "course", "Online Marketing DE", "Kunden gewinnen im DACH-Raum", "Online-Marketing", "premium", "de"),

    # ---- E-commerce & retail (10) ----
    ("dropship-eu", "course", "Dropshipping EU", "Suppliers, VAT, and fulfilment", "dropshipping", "premium", "en"),
    ("print-demand", "course", "Print on Demand", "Designs that actually sell", "print on demand", "standard", "en"),
    ("etsy-shop", "course", "Etsy Shop Growth", "From first listing to full-time", "Etsy", "standard", "en"),
    ("product-source", "service", "Product Sourcing", "Vetted suppliers and samples", "product sourcing", "premium", "en"),
    ("ecom-analytics", "saas", "E-com Analytics", "Real margins per product", "e-commerce analytics", "premium", "en"),
    ("vat-oss", "consult", "EU VAT & OSS", "Sell across borders, compliantly", "EU VAT", "premium", "en"),
    ("packaging-design", "service", "Packaging Design", "Shelf-ready packaging artwork", "packaging design", "premium", "en"),
    ("subscription-box", "course", "Subscription Box", "Recurring revenue from physical goods", "subscription boxes", "standard", "en"),
    ("wholesale-eu", "club", "Wholesale Deals", "Verified B2B lots, weekly", "wholesale", "standard", "en"),
    ("returns-fix", "consult", "Returns Reduction", "Cut return rates by a third", "returns management", "premium", "en"),

    # ---- Lifestyle & hobby (10) ----
    ("photo-eu", "course", "Photography Craft", "Manual mode to paid shoots", "photography", "standard", "en"),
    ("video-eu", "course", "Video Editing", "Edit like a professional", "video editing", "standard", "en"),
    ("cooking-eu", "club", "Cooking Club", "A new technique every week", "cooking", "budget", "en"),
    ("wine-eu", "club", "Wine Discovery", "Tastings and bottles worth buying", "wine", "standard", "en"),
    ("guitar-eu", "course", "Guitar in 30 Days", "Your first songs, fast", "guitar", "budget", "en"),
    ("chess-eu", "club", "Chess Improvement", "Openings, tactics, and game reviews", "chess", "standard", "en"),
    ("garden-eu", "club", "Urban Gardening", "Grow food on a balcony", "urban gardening", "budget", "en"),
    ("travel-hack", "signals", "Flight Deal Alerts", "Error fares and award sweet spots", "flight deals", "budget", "en"),
    ("van-life", "shop", "Van Conversion Plans", "Build plans and part lists", "van conversion", "standard", "en"),
    ("running-eu", "club", "Running Club", "Structured plans for every distance", "running", "budget", "en"),

    # ---- Property, legal, relocation (10) ----
    ("relocate-eu", "consult", "Relocation to Europe", "Visa route, taxes, and settling in", "relocation", "elite", "en"),
    ("digital-nomad", "course", "Digital Nomad Setup", "Residency, banking, and taxes", "digital nomad life", "premium", "en"),
    ("mortgage-eu", "consult", "EU Mortgage Advice", "Financing as a non-resident", "mortgages", "elite", "en"),
    ("rental-mgmt", "saas", "Rental Manager", "Tenants, rent, and paperwork", "rental management", "standard", "en"),
    ("gmbh-setup", "service", "Company Formation", "GmbH, LTD, or estonian OÜ", "company formation", "elite", "en"),
    ("contract-eu", "service", "Contract Review", "Legal review within 24 hours", "contract review", "premium", "en"),
    ("gdpr-comply", "service", "GDPR Compliance", "Policies and records that hold up", "GDPR compliance", "premium", "en"),
    ("interior-eu", "service", "Interior Design", "Floor plans and 3D visuals", "interior design", "elite", "en"),
    ("inmobiliaria-es", "leadgen", "Inmobiliaria Directa", "Encuentra tu piso sin comisiones", "inmobiliaria", "premium", "es"),
    ("umzug-de", "leadgen", "Umzugsservice", "Umzug planen und buchen", "Umzüge", "standard", "de"),
]


def ru_entries() -> list[dict]:
    return [
        {
            "slug": slug,
            "archetype": archetype,
            "name": name,
            "tagline": tagline,
            "topic": topic,
            "tier": tier,
            "region": "ru",
            "lang": "ru",
            "currency": "RUB",
        }
        for slug, archetype, name, tagline, topic, tier in RU
    ]


def eu_entries() -> list[dict]:
    return [
        {
            "slug": slug,
            "archetype": archetype,
            "name": name,
            "tagline": tagline,
            "topic": topic,
            "tier": tier,
            "region": "eu",
            "lang": lang,
            "currency": "EUR",
        }
        for slug, archetype, name, tagline, topic, tier, lang in EU
    ]


def all_entries() -> list[dict]:
    return ru_entries() + eu_entries()


if __name__ == "__main__":  # pragma: no cover - sanity check
    ru, eu = ru_entries(), eu_entries()
    slugs = [e["slug"] for e in ru + eu]
    assert len(slugs) == len(set(slugs)), "duplicate slugs"
    print(f"RU: {len(ru)}  EU: {len(eu)}  total: {len(slugs)}")
