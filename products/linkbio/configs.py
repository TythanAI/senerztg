# -*- coding: utf-8 -*-
"""Content + themes for Link-in-Bio Kit. 10 personas x 5 themes = 50 pages.
Edit personas/themes here, then `python build.py`."""


def theme(bg, text, muted, accent, border, av, ring, soc, btn, btn_text, btn_border):
    return (f"--bg:{bg}; --text:{text}; --muted:{muted}; --accent:{accent}; "
            f"--border:{border}; --av:{av}; --ring:{ring}; --soc:{soc}; "
            f"--btn:{btn}; --btn-text:{btn_text}; --btn-border:{btn_border}; ")


THEMES = {
    "midnight": theme("radial-gradient(120% 120% at 50% 0%,#1b2340,#0a0e1a)", "#eaf0ff",
                      "#93a0c0", "#22d3ee", "rgba(255,255,255,.12)",
                      "linear-gradient(135deg,#22d3ee,#6366f1)", "rgba(255,255,255,.2)",
                      "rgba(255,255,255,.06)", "rgba(255,255,255,.07)", "#eaf0ff",
                      "1px solid rgba(255,255,255,.14)"),
    "sunset": theme("linear-gradient(160deg,#ff7e5f,#feb47b)", "#3a1e12", "#7a4a34",
                    "#c0392b", "rgba(0,0,0,.08)", "#fff", "rgba(255,255,255,.7)",
                    "rgba(255,255,255,.55)", "#ffffff", "#b3402a", "none"),
    "candy": theme("linear-gradient(160deg,#a18cd1,#fbc2eb)", "#3a2a4a", "#6b5a7a",
                   "#a21caf", "rgba(0,0,0,.06)", "#fff", "rgba(255,255,255,.8)",
                   "rgba(255,255,255,.6)", "#ffffff", "#7a2a9a", "none"),
    "forest": theme("radial-gradient(120% 120% at 50% 0%,#164a32,#0b1f16)", "#e7f5ec",
                    "#8fc0a6", "#34d399", "rgba(255,255,255,.1)",
                    "linear-gradient(135deg,#34d399,#059669)", "rgba(255,255,255,.18)",
                    "rgba(255,255,255,.06)", "rgba(255,255,255,.07)", "#e7f5ec",
                    "1px solid rgba(255,255,255,.12)"),
    "ocean": theme("linear-gradient(160deg,#2193b0,#6dd5ed)", "#04283a", "#2c5a70",
                   "#0369a1", "rgba(0,0,0,.08)", "#fff", "rgba(255,255,255,.75)",
                   "rgba(255,255,255,.55)", "#ffffff", "#0b5573", "none"),
    "mono": theme("#f4f4f5", "#111114", "#6b7280", "#111114", "rgba(0,0,0,.1)",
                  "#111114", "#111114", "#ffffff", "#111114", "#ffffff", "none"),
    "gold": theme("radial-gradient(120% 120% at 50% 0%,#161410,#0a0908)", "#f5e9c9",
                  "#b6a480", "#d4af37", "rgba(212,175,55,.25)",
                  "linear-gradient(135deg,#d4af37,#8a6d1f)", "rgba(212,175,55,.5)",
                  "rgba(212,175,55,.1)", "transparent", "#f5e9c9",
                  "1px solid rgba(212,175,55,.5)"),
    "neon": theme("radial-gradient(120% 120% at 50% 0%,#141026,#08060f)", "#f0e9ff",
                  "#a99fc9", "#e635ff", "rgba(230,53,255,.25)",
                  "linear-gradient(135deg,#e635ff,#6d28d9)", "rgba(230,53,255,.5)",
                  "rgba(230,53,255,.1)", "rgba(230,53,255,.12)", "#f7ecff",
                  "1px solid rgba(230,53,255,.4)"),
    "peach": theme("linear-gradient(160deg,#ffd9c0,#fff1e6)", "#4a2f22", "#8a6a56",
                   "#ff7a59", "rgba(0,0,0,.07)", "#fff", "#ffffff", "#ffffff",
                   "#ffffff", "#c2492e", "1px solid rgba(0,0,0,.06)"),
    "clean": theme("#ffffff", "#0f172a", "#64748b", "#6366f1", "#e5e7eb",
                   "linear-gradient(135deg,#6366f1,#8b5cf6)", "#eef2ff", "#f8fafc",
                   "#ffffff", "#0f172a", "1px solid #e5e7eb"),
}
THEME_ORDER = list(THEMES)

PERSONAS = [
    dict(key="musician", emoji="🎧", name="Alex Rivers", handle="@alexrivers", verified=True,
         bio="Продюсер и DJ. Новый трек уже вышел 🔥",
         socials=[("📸", "Instagram"), ("▶️", "YouTube"), ("🎵", "TikTok"), ("✈️", "Telegram")],
         links=[("🎵", "Слушать на всех площадках"), ("🆕", "Новый релиз"),
                ("🎫", "Билеты на концерт"), ("👕", "Мерч"), ("🎹", "Заказать бит")]),
    dict(key="photographer", emoji="📷", name="Мария Лес", handle="@mariales.photo", verified=False,
         bio="Фотограф. Портреты и свадьбы. Записывайтесь ✨",
         socials=[("📸", "Instagram"), ("✈️", "Telegram"), ("📌", "Pinterest")],
         links=[("🖼", "Портфолио"), ("📅", "Забронировать съёмку"),
                ("💰", "Прайс-лист"), ("⭐️", "Отзывы")]),
    dict(key="coach", emoji="💪", name="Ivan Strong", handle="@ivanstrong", verified=True,
         bio="Фитнес-тренер. Помогаю прийти в форму.",
         socials=[("📸", "Instagram"), ("▶️", "YouTube"), ("✈️", "Telegram")],
         links=[("🏋️", "Программы тренировок"), ("📝", "Персональный план"),
                ("📅", "Записаться"), ("📣", "Мой Telegram-канал"), ("⭐️", "Отзывы")]),
    dict(key="cafe", emoji="☕️", name="Aroma Coffee", handle="@aroma.coffee", verified=False,
         bio="Уютная кофейня в центре. Ждём вас!",
         socials=[("📸", "Instagram"), ("✈️", "Telegram"), ("🅥", "VK")],
         links=[("📖", "Меню"), ("🪑", "Забронировать столик"),
                ("🚚", "Доставка"), ("📍", "Мы на карте")]),
    dict(key="shop", emoji="🛍", name="NOVA Store", handle="@novastore", verified=True,
         bio="Онлайн-магазин аксессуаров. Доставка по РФ.",
         socials=[("📸", "Instagram"), ("✈️", "Telegram"), ("🟢", "WhatsApp")],
         links=[("🛒", "Каталог"), ("🔥", "Хиты продаж"),
                ("⭐️", "Отзывы"), ("💬", "Поддержка")]),
    dict(key="developer", emoji="💻", name="Dmitry Code", handle="@dmitrycode", verified=False,
         bio="Full-stack разработчик. Беру проекты.",
         socials=[("🐙", "GitHub"), ("✈️", "Telegram"), ("💼", "LinkedIn")],
         links=[("🗂", "Портфолио"), ("🐙", "GitHub"),
                ("🌐", "Заказать сайт"), ("📄", "Резюме"), ("✉️", "Написать мне")]),
    dict(key="streamer", emoji="🎮", name="PixelPlay", handle="@pixelplay", verified=True,
         bio="Стример. Онлайн каждый вечер!",
         socials=[("🟣", "Twitch"), ("▶️", "YouTube"), ("✈️", "Telegram"), ("💬", "Discord")],
         links=[("🔴", "Смотреть стрим"), ("💬", "Discord-сервер"),
                ("💜", "Донат"), ("🗓", "Расписание"), ("👕", "Мерч")]),
    dict(key="artist", emoji="🎨", name="Lera Art", handle="@lera.art", verified=False,
         bio="Иллюстратор. Принты и заказы открыты.",
         socials=[("📸", "Instagram"), ("🎭", "Behance"), ("✈️", "Telegram")],
         links=[("🖼", "Галерея"), ("🛒", "Купить принт"),
                ("✏️", "Заказать иллюстрацию"), ("🎥", "Процесс работы")]),
    dict(key="podcast", emoji="🎙", name="Разговоры", handle="@razgovory.pod", verified=False,
         bio="Подкаст о жизни и бизнесе. Новый выпуск!",
         socials=[("🎧", "Spotify"), ("▶️", "YouTube"), ("✈️", "Telegram")],
         links=[("🎧", "Слушать выпуск"), ("📡", "Все площадки"),
                ("🎤", "Стать гостем"), ("💜", "Поддержать проект")]),
    dict(key="creator", emoji="✨", name="Nina Vibe", handle="@ninavibe", verified=True,
         bio="Контент-креатор. Сотрудничество — в личку.",
         socials=[("📸", "Instagram"), ("🎵", "TikTok"), ("▶️", "YouTube"), ("✈️", "Telegram")],
         links=[("🎬", "Последнее видео"), ("🤝", "Сотрудничество"),
                ("🎓", "Мой курс"), ("🛍", "Магазин"), ("✈️", "Telegram")]),
]


CONFIGS = []
for _pi, _per in enumerate(PERSONAS):
    for _k in range(5):
        _tname = THEME_ORDER[(_pi * 3 + _k) % len(THEME_ORDER)]
        _cfg = dict(_per)
        _cfg["slug"] = f"{_per['key']}_{_tname}"
        _cfg["vars"] = THEMES[_tname]
        CONFIGS.append(_cfg)
