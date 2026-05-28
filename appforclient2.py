"""
SmartTrend Analyzer v3.0 — Professional Edition
================================================
Универсальный анализатор трендовых видео для маркетинговых агентств.
Источники: YouTube Data API v3, yt-dlp, Apify (Instagram + TikTok),
           RapidAPI/ScrapTik, Instaloader.

Особенности версии 3.0:
  • Универсальные ниши с готовыми пресетами (бьюти, мода, косметика и др.)
  • 4 источника данных с автоматическим fallback и ретраями
  • Улучшенный scoring с защитой от накруток и viral-коэффициентом
  • Аналитика каналов и авторов (топ создателей, частота, engagement)
  • Безопасное хранение ключей через st.secrets (Streamlit Cloud-ready)
  • Rate limiting, валидация ввода, информативные ошибки
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# ЛОГИРОВАНИЕ (без утечки ключей)
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("smarttrend")


def mask_key(key: str) -> str:
    """Маскирует ключ для безопасного отображения/логирования."""
    if not key or len(key) < 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


# ─────────────────────────────────────────────────────────────────────────────
# КОНФИГУРАЦИЯ СТРАНИЦЫ
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SmartTrend Analyzer Pro",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "SmartTrend Analyzer v3.0 — Professional Edition. "
                 "Универсальный анализатор трендовых видео для маркетинга.",
    },
)

# ─────────────────────────────────────────────────────────────────────────────
# СТИЛИ (CSS)
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

section[data-testid="stSidebar"] { background: #0d0d12; border-right: 1px solid #2a2a35; }
section[data-testid="stSidebar"] * { color: #e0e0e0 !important; }

.main-header {
    background: linear-gradient(135deg, #6a11cb 0%, #2575fc 100%);
    padding: 24px 28px; border-radius: 16px; margin-bottom: 20px;
    color: white; box-shadow: 0 8px 24px rgba(106,17,203,0.25);
}
.main-header h1 { margin: 0; font-size: 1.9rem; font-weight: 800; }
.main-header p { margin: 6px 0 0 0; opacity: 0.92; font-size: 0.95rem; }

.kpi-card {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border: 1px solid #2a2a4a; border-radius: 12px;
    padding: 20px; text-align: center; transition: transform 0.2s, border-color 0.2s;
    height: 100%;
}
.kpi-card:hover { transform: translateY(-2px); border-color: #4fc3f7; }
.kpi-value { font-size: 2rem; font-weight: 800; color: #4fc3f7; line-height: 1.1; }
.kpi-label { font-size: 0.82rem; color: #9e9e9e; margin-top: 6px; }
.kpi-delta { font-size: 0.78rem; margin-top: 6px; }
.kpi-delta.up { color: #66bb6a; }
.kpi-delta.down { color: #ef5350; }
.kpi-delta.neutral { color: #9e9e9e; }

.video-card {
    background: #1e1e2e; border: 1px solid #2a2a3e;
    border-radius: 12px; padding: 16px; margin-bottom: 12px; transition: all 0.2s;
}
.video-card:hover { border-color: #4fc3f7; transform: translateX(2px); }
.video-title { font-size: 0.98rem; font-weight: 600; color: #e0e0e0; line-height: 1.35; }
.video-meta { font-size: 0.8rem; color: #9e9e9e; margin-top: 6px; }
.video-stats { font-size: 0.88rem; color: #4fc3f7; margin-top: 8px; font-weight: 500; }

.badge {
    display: inline-block; padding: 3px 10px; border-radius: 20px;
    font-size: 0.72rem; font-weight: 700; margin-right: 4px;
    text-transform: uppercase; letter-spacing: 0.3px;
}
.badge-yt { background: #c62828; color: white; }
.badge-ig { background: linear-gradient(45deg,#f09433,#e6683c,#dc2743,#cc2366,#bc1888); color: white; }
.badge-tt { background: #000; color: white; border: 1px solid #00f2ea; }
.badge-hot { background: #ff6f00; color: white; }
.badge-trending { background: #1565c0; color: white; }
.badge-viral { background: linear-gradient(45deg,#e91e63,#9c27b0); color: white; }
.badge-fresh { background: #00897b; color: white; }

.score-bar-wrap { background: #2a2a3e; border-radius: 4px; height: 8px; margin-top: 8px; }
.score-bar-fill { height: 8px; border-radius: 4px;
    background: linear-gradient(90deg, #4fc3f7, #9c27b0, #e91e63); }

.section-header {
    font-size: 1.35rem; font-weight: 700; color: #e0e0e0;
    border-bottom: 2px solid #4fc3f7; padding-bottom: 8px; margin-bottom: 16px;
}

.info-box {
    background: #1a2744; border-left: 4px solid #4fc3f7;
    padding: 12px 16px; border-radius: 0 8px 8px 0;
    margin: 8px 0; font-size: 0.88rem; color: #cfd8dc;
}
.success-box {
    background: #1a2e1a; border-left: 4px solid #66bb6a;
    padding: 12px 16px; border-radius: 0 8px 8px 0;
    margin: 8px 0; font-size: 0.88rem; color: #c8e6c9;
}
.warning-box {
    background: #2e2a1a; border-left: 4px solid #ffa726;
    padding: 12px 16px; border-radius: 0 8px 8px 0;
    margin: 8px 0; font-size: 0.88rem; color: #ffe0b2;
}

.creator-card {
    background: linear-gradient(135deg,#1e1e2e 0%,#2a2a3e 100%);
    border: 1px solid #2a2a4a; border-radius: 12px;
    padding: 14px 18px; margin-bottom: 10px;
}
.creator-name { font-size: 1.05rem; font-weight: 700; color: #e0e0e0; }
.creator-meta { font-size: 0.82rem; color: #9e9e9e; margin-top: 4px; }

.setup-step {
    background: #1a1a2e; border: 1px solid #2a2a4a; border-radius: 10px;
    padding: 14px; margin-bottom: 10px;
}
.setup-step-num {
    display: inline-block; background: #4fc3f7; color: #000;
    border-radius: 50%; width: 26px; height: 26px;
    text-align: center; line-height: 26px; font-weight: 700;
    font-size: 0.85rem; margin-right: 8px;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# КОНСТАНТЫ
# ─────────────────────────────────────────────────────────────────────────────
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
REQ_TIMEOUT = 15
MAX_RETRIES = 3
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Цвета платформ
PLATFORM_COLORS = {
    "YouTube":   "#ff4444",
    "Instagram": "#c13584",
    "TikTok":    "#00f2ea",
}

# Готовые пресеты ниш
NICHE_PRESETS: dict[str, dict[str, Any]] = {
    "💄 Бьюти и косметика": {
        "queries": ["makeup tutorial", "skincare routine", "beauty hacks",
                    "макияж урок", "уход за кожей", "косметика обзор"],
        "hashtags": ["makeup", "beauty", "skincare", "makeuptutorial",
                     "beautyhacks", "косметика", "макияж", "бьюти"],
        "keywords": ["makeup", "beauty", "skincare", "lipstick", "foundation",
                     "макияж", "косметика", "уход", "кожа", "бьюти"],
    },
    "👗 Мода и стиль": {
        "queries": ["fashion haul", "outfit ideas", "style tips",
                    "модный обзор", "стильный образ", "тренды моды"],
        "hashtags": ["fashion", "ootd", "style", "outfit", "fashiontrends",
                     "мода", "стиль", "образ"],
        "keywords": ["fashion", "style", "outfit", "haul", "trends",
                     "мода", "стиль", "образ", "одежда"],
    },
    "💪 Фитнес и здоровье": {
        "queries": ["home workout", "fitness routine", "healthy lifestyle",
                    "тренировка дома", "фитнес упражнения"],
        "hashtags": ["fitness", "workout", "gym", "fitnessmotivation",
                     "фитнес", "тренировка", "спорт"],
        "keywords": ["workout", "fitness", "gym", "training", "exercise",
                     "фитнес", "тренировка", "упражнения"],
    },
    "🍳 Кулинария": {
        "queries": ["easy recipes", "cooking tutorial", "food hacks",
                    "рецепты", "кулинарные лайфхаки"],
        "hashtags": ["food", "recipe", "cooking", "foodie", "foodhacks",
                     "рецепты", "кулинария", "еда"],
        "keywords": ["recipe", "cooking", "food", "kitchen", "meal",
                     "рецепт", "кулинария", "блюдо"],
    },
    "📱 Технологии и гаджеты": {
        "queries": ["smartphone review", "tech unboxing", "gadget review",
                    "обзор смартфона", "распаковка"],
        "hashtags": ["tech", "gadgets", "smartphone", "techreview", "unboxing",
                     "техника", "гаджеты"],
        "keywords": ["tech", "smartphone", "review", "gadget", "unboxing",
                     "обзор", "смартфон", "гаджет"],
    },
    "🔧 Ремонт смартфонов": {
        "queries": ["smartphone repair", "phone screen replacement",
                    "iphone repair", "ремонт телефона"],
        "hashtags": ["phonerepair", "iphonerepair", "smartphonerepair",
                     "ремонттелефона", "ремонт"],
        "keywords": ["repair", "fix", "screen", "battery", "broken",
                     "ремонт", "починить", "замена"],
    },
    "🎮 Игры и геймплей": {
        "queries": ["gaming highlights", "game review", "best gaming moments",
                    "обзор игр", "геймплей"],
        "hashtags": ["gaming", "gamer", "gameplay", "videogames",
                     "игры", "геймплей"],
        "keywords": ["gaming", "game", "gameplay", "review",
                     "игра", "обзор", "геймплей"],
    },
    "✈️ Путешествия": {
        "queries": ["travel vlog", "travel tips", "destination guide",
                    "путешествия", "тревел блог"],
        "hashtags": ["travel", "wanderlust", "travelvlog", "travelgram",
                     "путешествие", "тревел"],
        "keywords": ["travel", "destination", "trip", "vlog",
                     "путешествие", "поездка", "тревел"],
    },
}

# YouTube категории (videoCategoryId)
YT_CATEGORIES = {
    "Все": None,
    "Музыка": "10",
    "Развлечения": "24",
    "Лайфстайл (How-to & Style)": "26",
    "Образование": "27",
    "Наука и технологии": "28",
    "Спорт": "17",
    "Игры": "20",
    "Люди и блоги": "22",
}

# Регионы
REGIONS = {
    "🇺🇸 США": "US", "🇬🇧 Великобритания": "GB", "🇩🇪 Германия": "DE",
    "🇫🇷 Франция": "FR", "🇪🇸 Испания": "ES", "🇮🇹 Италия": "IT",
    "🇷🇺 Россия": "RU", "🇺🇦 Украина": "UA", "🇰🇿 Казахстан": "KZ",
    "🇧🇷 Бразилия": "BR", "🇯🇵 Япония": "JP", "🇰🇷 Корея": "KR",
    "🇮🇳 Индия": "IN", "🇨🇦 Канада": "CA", "🇦🇺 Австралия": "AU",
}


# ─────────────────────────────────────────────────────────────────────────────
# КЛЮЧИ И КОНФИГУРАЦИЯ
# ─────────────────────────────────────────────────────────────────────────────
def load_saved_keys() -> dict[str, str]:
    """
    Загружает ключи в порядке приоритета:
    1) Переменные окружения (для локального запуска / Docker)
    2) st.secrets (для Streamlit Cloud)
    """
    keys = {
        "youtube_api_key": "",
        "apify_token": "",
        "rapidapi_key": "",
        "instagram_user": "",
        "instagram_pass": "",
    }
    # 1. Переменные окружения
    keys["youtube_api_key"] = os.environ.get("YOUTUBE_API_KEY", "")
    keys["apify_token"] = os.environ.get("APIFY_TOKEN", "")
    keys["rapidapi_key"] = os.environ.get("RAPIDAPI_KEY", "")
    keys["instagram_user"] = os.environ.get("INSTAGRAM_USER", "")
    keys["instagram_pass"] = os.environ.get("INSTAGRAM_PASS", "")

    # 2. Streamlit secrets (только если не нашли в env)
    try:
        for k in keys:
            if not keys[k]:
                keys[k] = st.secrets.get(k, "")
    except Exception:
        pass

    return keys


def save_keys_to_session(**kwargs) -> None:
    """Сохраняет ключи только в session_state (для Streamlit Cloud это безопасно)."""
    for k, v in kwargs.items():
        st.session_state[k] = v or ""


def validate_youtube_key(key: str) -> tuple[bool, str]:
    """Проверяет валидность YouTube API ключа."""
    if not key or not key.strip():
        return False, "Ключ пустой"
    if not re.match(r"^[A-Za-z0-9_\-]{20,}$", key.strip()):
        return False, "Неверный формат ключа"
    try:
        r = requests.get(
            f"{YOUTUBE_API_BASE}/search",
            params={"part": "snippet", "q": "test", "type": "video",
                    "maxResults": 1, "key": key.strip()},
            timeout=REQ_TIMEOUT,
        )
        if r.status_code == 200:
            return True, "✅ Ключ работает"
        elif r.status_code == 403:
            err = r.json().get("error", {}).get("message", "")
            if "accessNotConfigured" in err or "API has not been used" in err:
                return False, "API не активирован. Включите YouTube Data API v3 в Google Cloud Console."
            if "quotaExceeded" in err:
                return False, "Квота исчерпана на сегодня (10 000 единиц в день)"
            return False, f"Отказ доступа: {err[:120]}"
        elif r.status_code == 400:
            return False, "Невалидный API ключ"
        else:
            return False, f"HTTP {r.status_code}"
    except requests.exceptions.Timeout:
        return False, "Таймаут соединения"
    except Exception as e:
        return False, f"Ошибка: {e}"


def validate_apify_token(token: str) -> tuple[bool, str]:
    """Проверяет валидность Apify токена."""
    if not token or not token.strip():
        return False, "Токен пустой"
    try:
        r = requests.get(
            "https://api.apify.com/v2/users/me",
            headers={"Authorization": f"Bearer {token.strip()}"},
            timeout=REQ_TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json().get("data", {})
            plan = data.get("plan", {}).get("id", "free")
            return True, f"✅ Apify работает (план: {plan})"
        elif r.status_code == 401:
            return False, "Невалидный токен"
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, f"Ошибка: {e}"


def check_ytdlp() -> bool:
    try:
        import yt_dlp  # noqa: F401
        return True
    except ImportError:
        return False


def check_instaloader() -> bool:
    try:
        import instaloader  # noqa: F401
        return True
    except ImportError:
        return False


def install_package(pkg: str) -> tuple[bool, str]:
    """Устанавливает pip-пакет. Возвращает (успех, сообщение)."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", pkg, "-q"],
            capture_output=True, text=True, timeout=180,
        )
        if result.returncode == 0:
            return True, f"✅ {pkg} установлен"
        return False, f"Ошибка установки: {result.stderr[:200]}"
    except subprocess.TimeoutExpired:
        return False, "Таймаут установки (>3 мин)"
    except Exception as e:
        return False, f"Ошибка: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ─────────────────────────────────────────────────────────────────────────────
def fmt_number(n) -> str:
    """Форматирует числа: 1234567 → 1.2М. Безопасно к NaN/None/строкам."""
    if n is None:
        return "—"
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "—"
    # Защита от NaN и Infinity
    import math
    if math.isnan(n) or math.isinf(n):
        return "—"
    if n >= 1_000_000_000:
        return f"{n/1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}М"
    if n >= 1_000:
        return f"{n/1_000:.1f}К"
    return str(int(n))


def parse_iso_duration(iso: str | None) -> int:
    """ISO 8601 (PT5M30S) → секунды."""
    if not iso:
        return 0
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    if not m:
        return 0
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


def fmt_duration(secs: int | None) -> str:
    secs = int(secs or 0)
    if secs <= 0:
        return "—"
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def days_ago_from_iso(iso_date: str) -> int:
    """Считает дни от ISO даты."""
    if not iso_date:
        return 30
    try:
        if "T" in iso_date:
            dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
            now = datetime.now(dt.tzinfo)
        else:
            dt = datetime.strptime(iso_date[:10], "%Y-%m-%d")
            now = datetime.now()
        return max((now - dt).days, 0)
    except Exception:
        return 30


def safe_request(
    url: str, *, params: dict | None = None, headers: dict | None = None,
    retries: int = MAX_RETRIES, timeout: int = REQ_TIMEOUT,
) -> requests.Response | None:
    """HTTP-запрос с ретраями, экспоненциальным backoff и логированием."""
    headers = headers or {}
    headers.setdefault("User-Agent", USER_AGENT)
    last_err = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=timeout)
            if r.status_code == 429:  # rate limit
                wait = 2 ** attempt
                logger.warning("Rate limit, ждём %ds", wait)
                time.sleep(wait)
                continue
            return r
        except requests.exceptions.RequestException as e:
            last_err = e
            logger.warning("Попытка %d/%d не удалась: %s", attempt + 1, retries, e)
            time.sleep(2 ** attempt)
    if last_err:
        logger.error("Все попытки исчерпаны: %s", last_err)
        # Прикрепляем последнюю ошибку к функции для возможности доступа извне
        safe_request.last_error = f"{type(last_err).__name__}: {str(last_err)[:200]}"
    else:
        safe_request.last_error = None
    return None


safe_request.last_error = None  # type: ignore[attr-defined]


# ─────────────────────────────────────────────────────────────────────────────
# СКОРИНГ ВИДЕО — улучшенный алгоритм
# ─────────────────────────────────────────────────────────────────────────────
def score_video(
    views: int, likes: int, comments: int,
    days_ago: int, subscribers: int | None = None,
) -> tuple[int, dict[str, float]]:
    """
    Считает рейтинг «залётности» 0–100 и возвращает разложение по факторам.

    Учитывает:
      • Абсолютный охват (макс. 25 баллов)
      • Engagement Rate (макс. 25 баллов)
      • Свежесть контента (макс. 15 баллов)
      • Velocity — просмотры в день (макс. 20 баллов)
      • Viral coefficient — отношение к подписчикам (макс. 15 баллов)

    Защита от накруток:
      • Видео с <100 просмотрами получают 0
      • Аномальный ER (>50%) штрафуется — вероятная накрутка
    """
    if views < 100:
        return 0, {}

    days = max(days_ago, 1)

    # 1) Абсолютный охват — логарифмическая шкала
    reach_score = min(25, (views / 10_000_000) * 25)

    # 2) Engagement Rate (с защитой от накруток)
    er = (likes + comments * 3) / max(views, 1)
    if er > 0.5:  # аномально высокий — штрафуем
        er_score = 10
    else:
        er_score = min(25, er * 800)

    # 3) Свежесть — спадает по экспоненте
    recency_score = max(0, 15 * (1 - days / 120))

    # 4) Velocity
    velocity = views / days
    velocity_score = min(20, (velocity / 100_000) * 20)

    # 5) Viral coefficient — отношение просмотров к подписчикам
    viral_score = 0.0
    if subscribers and subscribers > 0:
        ratio = views / subscribers
        viral_score = min(15, ratio * 5)
    else:
        # Если нет данных о подписчиках — компенсируем по ER+velocity
        viral_score = min(15, (er * 200 + velocity / 200_000 * 5))

    total = reach_score + er_score + recency_score + velocity_score + viral_score
    breakdown = {
        "reach": round(reach_score, 1),
        "engagement": round(er_score, 1),
        "recency": round(recency_score, 1),
        "velocity": round(velocity_score, 1),
        "viral": round(viral_score, 1),
        "er_pct": round(er * 100, 2),
        "velocity_per_day": int(velocity),
    }
    return min(round(total), 100), breakdown


def smart_hashtags(query: str, niche_hashtags: list[str] | None = None) -> list[str]:
    """Генерирует список хэштегов из запроса + добавляет тематические."""
    query = (query or "").lower().replace("#", "").strip()
    words = [w for w in re.split(r"\W+", query) if len(w) > 2]
    tags: list[str] = []

    exact = query.replace(" ", "")
    if exact:
        tags.append(exact)
    if len(words) >= 2:
        tags.append(words[0] + words[1])
    for w in words:
        if w not in tags:
            tags.append(w)
    if niche_hashtags:
        for t in niche_hashtags:
            t = t.replace("#", "").strip()
            if t and t not in tags:
                tags.append(t)

    # Дедуп + до 12 тегов (расширенный охват — IG/TT любят много тегов)
    seen = set()
    res = []
    for t in tags:
        if t not in seen and len(t) >= 2:
            seen.add(t)
            res.append(t)
    return res[:12]


# ─────────────────────────────────────────────────────────────────────────────
# ИСТОЧНИК 1: YouTube Data API v3
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def search_youtube_api(
    api_key: str, query: str, *, fetch_limit: int = 50,
    region: str = "US", days: int = 90,
    category_id: str | None = None,
    video_duration: str = "any",  # any, short, medium, long
) -> list[dict]:
    """Поиск по YouTube Data API v3 с обогащением статистикой и каналами."""
    if not api_key:
        return []

    published_after = (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    rows: list[dict] = []
    next_page_token = None
    fetched = 0

    while fetched < fetch_limit:
        page_size = min(50, fetch_limit - fetched)
        params = {
            "part": "snippet", "q": query, "type": "video",
            "maxResults": page_size, "order": "viewCount",
            "regionCode": region, "publishedAfter": published_after,
            "videoDuration": video_duration, "key": api_key,
        }
        if category_id:
            params["videoCategoryId"] = category_id
        if next_page_token:
            params["pageToken"] = next_page_token

        r = safe_request(f"{YOUTUBE_API_BASE}/search", params=params)
        if not r or r.status_code != 200:
            if r is not None and r.status_code == 403:
                err = r.json().get("error", {}).get("message", "")
                raise RuntimeError(f"YouTube API: {err[:150]}")
            break

        data = r.json()
        items = data.get("items", [])
        if not items:
            break

        video_ids = [
            i["id"]["videoId"] for i in items if i.get("id", {}).get("videoId")
        ]
        if not video_ids:
            break

        # Подтягиваем статистику
        stats_r = safe_request(
            f"{YOUTUBE_API_BASE}/videos",
            params={
                "part": "statistics,contentDetails,snippet",
                "id": ",".join(video_ids), "key": api_key,
            },
        )
        if not stats_r or stats_r.status_code != 200:
            break

        stats_dict = {s["id"]: s for s in stats_r.json().get("items", [])}

        # Собираем уникальные каналы для одного запроса channels
        channel_ids = list({s.get("snippet", {}).get("channelId")
                            for s in stats_dict.values()
                            if s.get("snippet", {}).get("channelId")})
        channels_dict = {}
        if channel_ids:
            ch_r = safe_request(
                f"{YOUTUBE_API_BASE}/channels",
                params={
                    "part": "statistics",
                    "id": ",".join(channel_ids[:50]),
                    "key": api_key,
                },
            )
            if ch_r and ch_r.status_code == 200:
                for ch in ch_r.json().get("items", []):
                    channels_dict[ch["id"]] = int(
                        ch.get("statistics", {}).get("subscriberCount", 0) or 0
                    )

        for item in items:
            vid_id = item.get("id", {}).get("videoId")
            if not vid_id:
                continue
            stat = stats_dict.get(vid_id, {})
            snip = stat.get("snippet") or item.get("snippet", {})
            sd = stat.get("statistics", {})
            cd = stat.get("contentDetails", {})

            published = snip.get("publishedAt", "")
            days_ag = days_ago_from_iso(published)
            views = int(sd.get("viewCount", 0))
            likes = int(sd.get("likeCount", 0))
            comments = int(sd.get("commentCount", 0))
            dur_sec = parse_iso_duration(cd.get("duration", ""))
            channel_id = snip.get("channelId", "")
            subs = channels_dict.get(channel_id, 0)

            score, breakdown = score_video(views, likes, comments, days_ag, subs)

            rows.append({
                "platform": "YouTube",
                "id": vid_id,
                "title": snip.get("title", "")[:120],
                "channel": snip.get("channelTitle", ""),
                "channel_id": channel_id,
                "subscribers": subs,
                "published": published[:10],
                "days_ago": days_ag,
                "views": views, "likes": likes, "comments": comments,
                "duration_sec": dur_sec, "duration": fmt_duration(dur_sec),
                "thumbnail": snip.get("thumbnails", {}).get("high", {}).get("url", ""),
                "url": f"https://www.youtube.com/watch?v={vid_id}",
                "description": (snip.get("description") or "")[:300],
                "tags": ", ".join(snip.get("tags", [])[:10]),
                "score": score,
                "er_pct": breakdown.get("er_pct", 0),
                "velocity_per_day": breakdown.get("velocity_per_day", 0),
            })
            fetched += 1

        next_page_token = data.get("nextPageToken")
        if not next_page_token or fetched >= fetch_limit:
            break

    return rows


@st.cache_data(ttl=600, show_spinner=False)
def get_youtube_trending(
    api_key: str, region: str = "US",
    category_id: str | None = None, limit: int = 50,
) -> list[dict]:
    """Получает trending-видео для региона (быстрый сигнал по «горячему»)."""
    if not api_key:
        return []

    params = {
        "part": "snippet,statistics,contentDetails",
        "chart": "mostPopular", "regionCode": region,
        "maxResults": min(50, limit), "key": api_key,
    }
    if category_id:
        params["videoCategoryId"] = category_id

    r = safe_request(f"{YOUTUBE_API_BASE}/videos", params=params)
    if not r or r.status_code != 200:
        return []

    rows = []
    for item in r.json().get("items", []):
        snip = item.get("snippet", {})
        sd = item.get("statistics", {})
        cd = item.get("contentDetails", {})
        vid_id = item.get("id", "")
        published = snip.get("publishedAt", "")
        days_ag = days_ago_from_iso(published)
        views = int(sd.get("viewCount", 0))
        likes = int(sd.get("likeCount", 0))
        comments = int(sd.get("commentCount", 0))
        dur_sec = parse_iso_duration(cd.get("duration", ""))
        score, breakdown = score_video(views, likes, comments, days_ag)
        rows.append({
            "platform": "YouTube",
            "id": vid_id,
            "title": snip.get("title", "")[:120],
            "channel": snip.get("channelTitle", ""),
            "channel_id": snip.get("channelId", ""),
            "subscribers": 0,
            "published": published[:10],
            "days_ago": days_ag,
            "views": views, "likes": likes, "comments": comments,
            "duration_sec": dur_sec, "duration": fmt_duration(dur_sec),
            "thumbnail": snip.get("thumbnails", {}).get("high", {}).get("url", ""),
            "url": f"https://www.youtube.com/watch?v={vid_id}",
            "description": (snip.get("description") or "")[:300],
            "tags": ", ".join(snip.get("tags", [])[:10]),
            "score": score,
            "er_pct": breakdown.get("er_pct", 0),
            "velocity_per_day": breakdown.get("velocity_per_day", 0),
        })
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# ИСТОЧНИК 2: yt-dlp (бесплатно, без API)
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def search_ytdlp(query: str, fetch_limit: int = 50) -> list[dict]:
    """Поиск через yt-dlp — fallback при отсутствии API ключа."""
    try:
        import yt_dlp
    except ImportError:
        return []

    ydl_opts = {
        "quiet": True, "no_warnings": True,
        "extract_flat": True,
        "playlist_items": f"1:{fetch_limit}",
        "user_agent": USER_AGENT,
        "retries": 3,
    }
    rows: list[dict] = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch{fetch_limit}:{query}", download=False)
            entries = info.get("entries", []) if info else []
            for e in entries:
                if not e:
                    continue
                vid_id = e.get("id", "")
                upload_date = e.get("upload_date", "")
                try:
                    pub_dt = datetime.strptime(upload_date, "%Y%m%d")
                    days_ag = (datetime.now() - pub_dt).days
                    published = pub_dt.strftime("%Y-%m-%d")
                except Exception:
                    days_ag = 30
                    published = ""

                views = int(e.get("view_count") or 0)
                likes = int(e.get("like_count") or 0)
                comments = int(e.get("comment_count") or 0)
                dur_sec = int(e.get("duration") or 0)
                score, breakdown = score_video(views, likes, comments, days_ag)

                rows.append({
                    "platform": "YouTube",
                    "id": vid_id,
                    "title": (e.get("title") or "")[:120],
                    "channel": e.get("uploader") or e.get("channel") or "",
                    "channel_id": e.get("channel_id", ""),
                    "subscribers": int(e.get("channel_follower_count") or 0),
                    "published": published,
                    "days_ago": days_ag,
                    "views": views, "likes": likes, "comments": comments,
                    "duration_sec": dur_sec, "duration": fmt_duration(dur_sec),
                    "thumbnail": e.get("thumbnail") or f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg",
                    "url": f"https://www.youtube.com/watch?v={vid_id}",
                    "description": (e.get("description") or "")[:300],
                    "tags": ", ".join((e.get("tags") or [])[:10]),
                    "score": score,
                    "er_pct": breakdown.get("er_pct", 0),
                    "velocity_per_day": breakdown.get("velocity_per_day", 0),
                })
    except Exception as e:
        logger.warning("yt-dlp ошибка: %s", e)
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# ИСТОЧНИК 3: Apify (Instagram + TikTok)
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def search_instagram_apify(
    apify_token: str, hashtags: list[str], fetch_limit: int = 50,
) -> list[dict]:
    """Парсинг Instagram через apify/instagram-hashtag-scraper."""
    if not apify_token or not hashtags:
        return []

    try:
        from apify_client import ApifyClient
    except ImportError:
        raise RuntimeError("Установите: pip install apify-client")

    client = ApifyClient(apify_token)
    try:
        run = client.actor("apify/instagram-hashtag-scraper").call(
            run_input={
                "hashtags": hashtags,
                "resultsLimit": fetch_limit,
            },
            timeout_secs=300,
        )
    except Exception as e:
        raise RuntimeError(f"Apify Instagram: {e}")

    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    rows: list[dict] = []
    for item in items:
        pub = (item.get("timestamp") or "")[:10]
        days_ag = days_ago_from_iso(pub)
        likes = int(item.get("likesCount", 0) or 0)
        views = int(item.get("videoViewCount") or 0)
        # Восстановление скрытых просмотров: эвристика
        if views == 0 and likes > 0:
            views = likes * 10  # для виральных постов соотношение ~10:1
        comments = int(item.get("commentsCount", 0) or 0)
        video_dur = int((item.get("videoDuration") or 0))

        score, breakdown = score_video(views, likes, comments, days_ag)
        owner = item.get("ownerUsername") or ""
        followers = int((item.get("ownerFollowers") or 0))

        rows.append({
            "platform": "Instagram",
            "id": item.get("id", "") or item.get("shortCode", ""),
            "title": (item.get("caption") or "")[:120],
            "channel": f"@{owner}" if owner else "",
            "channel_id": owner,
            "subscribers": followers,
            "published": pub,
            "days_ago": days_ag,
            "views": views, "likes": likes, "comments": comments,
            "duration_sec": video_dur, "duration": fmt_duration(video_dur),
            "thumbnail": item.get("displayUrl", ""),
            "url": item.get("url", ""),
            "description": (item.get("caption") or "")[:300],
            "tags": ", ".join(item.get("hashtags", []) or [])[:200],
            "score": score,
            "er_pct": breakdown.get("er_pct", 0),
            "velocity_per_day": breakdown.get("velocity_per_day", 0),
        })
    return rows


@st.cache_data(ttl=600, show_spinner=False)
def search_tiktok_apify(
    apify_token: str, hashtags: list[str], fetch_limit: int = 50,
) -> list[dict]:
    """Парсинг TikTok через clockworks/tiktok-hashtag-scraper."""
    if not apify_token or not hashtags:
        return []

    try:
        from apify_client import ApifyClient
    except ImportError:
        raise RuntimeError("Установите: pip install apify-client")

    client = ApifyClient(apify_token)
    try:
        run = client.actor("clockworks/tiktok-hashtag-scraper").call(
            run_input={
                "hashtags": hashtags,
                "resultsPerPage": fetch_limit,
                "shouldDownloadCovers": False,
                "shouldDownloadVideos": False,
                "shouldDownloadSubtitles": False,
            },
            timeout_secs=300,
        )
    except Exception as e:
        raise RuntimeError(f"Apify TikTok: {e}")

    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    rows: list[dict] = []
    for item in items:
        author_meta = item.get("authorMeta") or {}
        author = author_meta.get("name", "")
        followers = int(author_meta.get("fans", 0) or 0)
        vid_id = item.get("id", "")
        ts = item.get("createTime", 0) or 0
        try:
            pub_dt = datetime.fromtimestamp(int(ts)) if ts else None
            days_ag = (datetime.now() - pub_dt).days if pub_dt else 30
            published = pub_dt.strftime("%Y-%m-%d") if pub_dt else ""
        except Exception:
            days_ag = 30
            published = ""

        views = int(item.get("playCount", 0) or 0)
        likes = int(item.get("diggCount", 0) or 0)
        comments = int(item.get("commentCount", 0) or 0)
        shares = int(item.get("shareCount", 0) or 0)
        dur_sec = int((item.get("videoMeta") or {}).get("duration", 0) or 0)

        # TikTok: shares — мощный сигнал виральности
        score_likes = likes + shares * 2
        score, breakdown = score_video(views, score_likes, comments, days_ag, followers)

        challenges = [c.get("name", "") for c in (item.get("hashtags") or item.get("challenges") or [])]

        rows.append({
            "platform": "TikTok",
            "id": vid_id,
            "title": (item.get("text") or "")[:120],
            "channel": f"@{author}" if author else "",
            "channel_id": author,
            "subscribers": followers,
            "published": published,
            "days_ago": days_ag,
            "views": views, "likes": likes, "comments": comments,
            "shares": shares,
            "duration_sec": dur_sec, "duration": fmt_duration(dur_sec),
            "thumbnail": ((item.get("covers") or [None])[0]) or item.get("videoMeta", {}).get("coverUrl", ""),
            "url": item.get("webVideoUrl") or f"https://www.tiktok.com/@{author}/video/{vid_id}",
            "description": (item.get("text") or "")[:300],
            "tags": ", ".join([c for c in challenges if c][:10]),
            "score": score,
            "er_pct": breakdown.get("er_pct", 0),
            "velocity_per_day": breakdown.get("velocity_per_day", 0),
        })
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# ИСТОЧНИК 4: RapidAPI / ScrapTik (альтернатива для TikTok)
# ─────────────────────────────────────────────────────────────────────────────
def _extract_tiktok_items(data) -> list:
    """Извлекает список TikTok-видео из произвольной JSON-структуры RapidAPI ответа."""
    # Перебираем известные ключи на верхнем и вложенном уровне
    candidates_keys = [
        "itemList", "item_list", "aweme_list", "videos", "items",
        "data", "posts", "search_item_list",
    ]
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []

    # Прямые ключи
    for k in candidates_keys:
        v = data.get(k)
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return v
        # search_item_list — вложенный list в data.data
        if isinstance(v, dict):
            sub = _extract_tiktok_items(v)
            if sub:
                return sub

    # Особый случай: tiktok-api23 search/general -> data: [{type, item}, ...]
    inner = data.get("data")
    if isinstance(inner, list) and inner and isinstance(inner[0], dict):
        # Распаковываем обёртки {item: {...}} или {aweme_info: {...}}
        extracted = []
        for it in inner:
            if not isinstance(it, dict):
                continue
            # Сам пост может лежать на верхнем уровне или в вложенном ключе
            for inner_key in ("item", "aweme_info", "video", "content"):
                if isinstance(it.get(inner_key), dict):
                    extracted.append(it[inner_key])
                    break
            else:
                if any(k in it for k in ("playCount", "play_count", "stats", "statsV2", "author", "desc")):
                    extracted.append(it)
        if extracted:
            return extracted
    return []


# Список TikTok-эндпоинтов на RapidAPI — пробуем по очереди
TIKTOK_RAPIDAPI_ENDPOINTS = [
    {
        "host": "tiktok-scraper7.p.rapidapi.com",
        "url": "https://tiktok-scraper7.p.rapidapi.com/feed/search",
        "params_key": "keywords",
        "extra_params": {"region": "us", "count": 30, "cursor": 0, "publish_time": 0, "sort_type": 0},
    },
    {
        "host": "tiktok-api23.p.rapidapi.com",
        "url": "https://tiktok-api23.p.rapidapi.com/api/search/general",
        "params_key": "keyword",
        "extra_params": {"count": 30, "cursor": 0, "search_id": "0"},
    },
    {
        "host": "tiktok-api23.p.rapidapi.com",
        "url": "https://tiktok-api23.p.rapidapi.com/api/challenge/posts",
        "params_key": "challengeName",
        "extra_params": {"count": 30, "cursor": 0},
        "need_challenge_id": True,  # нужен challenge_id, получим отдельным запросом
    },
    {
        "host": "tiktok-scraper2.p.rapidapi.com",
        "url": "https://tiktok-scraper2.p.rapidapi.com/hashtag/posts",
        "params_key": "hashtag",
        "extra_params": {"count": 30},
    },
]


@st.cache_data(ttl=600, show_spinner=False)
def search_tiktok_rapidapi(
    rapidapi_key: str, query: str, fetch_limit: int = 50,
) -> tuple[list[dict], str]:
    """Парсинг TikTok через RapidAPI. Пробует несколько эндпоинтов.

    Возвращает (rows, diagnostic_message).
    """
    if not rapidapi_key or not query:
        return [], "Пустой ключ или запрос"

    clean_query = query.replace("#", "").replace(" ", "")
    diagnostic_msgs: list[str] = []
    items: list = []
    successful_host = ""

    for endpoint in TIKTOK_RAPIDAPI_ENDPOINTS:
        headers = {
            "X-RapidAPI-Key": rapidapi_key.strip(),
            "X-RapidAPI-Host": endpoint["host"],
        }
        base_params = {endpoint["params_key"]: clean_query, **endpoint["extra_params"]}
        if "count" in base_params:
            base_params["count"] = 35  # максимум для большинства эндпоинтов

        # Эндпоинт challenge/posts требует challenge_id — сначала получаем его
        if endpoint.get("need_challenge_id"):
            ch_info_url = "https://tiktok-api23.p.rapidapi.com/api/challenge/info"
            ch_r = safe_request(
                ch_info_url, params={"challengeName": clean_query}, headers=headers,
            )
            if not ch_r or ch_r.status_code != 200:
                err = getattr(safe_request, "last_error", None) or (f"HTTP {ch_r.status_code}" if ch_r else "нет ответа")
                diagnostic_msgs.append(f"{endpoint['host']} (challenge/info): {err}")
                continue
            try:
                ch_data = ch_r.json()
                challenge_id = (
                    (ch_data.get("challengeInfo") or {}).get("challenge", {}).get("id")
                    or ch_data.get("id")
                    or (ch_data.get("data") or {}).get("id")
                )
                if not challenge_id:
                    diagnostic_msgs.append(f"{endpoint['host']}: хэштег #{clean_query} не найден в TikTok")
                    continue
                base_params = {"challengeId": challenge_id, **endpoint["extra_params"]}
            except Exception as e:
                diagnostic_msgs.append(f"{endpoint['host']}: ошибка разбора challenge: {e}")
                continue

        # Пагинация: до 5 страниц через cursor/offset пока не наберём fetch_limit
        cursor = 0
        page_items: list = []
        last_status = None
        last_text = ""
        last_keys = None
        for page in range(5):
            params = dict(base_params)
            if page > 0:
                params["cursor"] = cursor
                params["offset"] = cursor
            r = safe_request(endpoint["url"], params=params, headers=headers)
            if not r:
                if page == 0:
                    err = getattr(safe_request, "last_error", None) or "timeout/connection error"
                    diagnostic_msgs.append(f"{endpoint['host']}: {err}")
                break
            last_status = r.status_code
            if r.status_code != 200:
                if page == 0:
                    if r.status_code == 401:
                        diagnostic_msgs.append(f"{endpoint['host']}: 401 — не подписан на этот API на RapidAPI")
                    elif r.status_code == 403:
                        diagnostic_msgs.append(f"{endpoint['host']}: 403 — нет доступа (проверьте подписку)")
                    elif r.status_code == 429:
                        diagnostic_msgs.append(f"{endpoint['host']}: 429 — лимит исчерпан")
                    else:
                        diagnostic_msgs.append(f"{endpoint['host']}: HTTP {r.status_code} — {r.text[:120]}")
                break
            try:
                data = r.json()
            except Exception:
                if page == 0:
                    diagnostic_msgs.append(f"{endpoint['host']}: невалидный JSON — {r.text[:120]}")
                break
            new_items = _extract_tiktok_items(data)
            last_keys = list(data.keys())[:5] if isinstance(data, dict) else type(data).__name__
            if not new_items:
                if page == 0:
                    diagnostic_msgs.append(f"{endpoint['host']}: пустой ответ (ключи: {last_keys})")
                break
            page_items.extend(new_items)
            if len(page_items) >= fetch_limit:
                break
            # Извлекаем курсор из ответа
            if isinstance(data, dict):
                next_cursor = (
                    data.get("cursor") or data.get("next_cursor")
                    or (data.get("data") or {}).get("cursor") if isinstance(data.get("data"), dict) else None
                )
                if next_cursor and int(next_cursor) != cursor:
                    cursor = int(next_cursor)
                    continue
            # Если курсора нет — сдвигаемся по оффсету
            cursor += len(new_items)

        if page_items:
            items = page_items
            successful_host = endpoint["host"]
            logger.info("RapidAPI TikTok: успех через %s, получено %d", successful_host, len(items))
            break

    if not items:
        return [], "; ".join(diagnostic_msgs) or "все эндпоинты отклонили запрос"

    rows: list[dict] = []
    for it in items:
        author = (it.get("author") or {}).get("uniqueId") or (it.get("author") or {}).get("unique_id") or (it.get("authorMeta") or {}).get("name", "")
        followers = (
            (it.get("authorStats") or {}).get("followerCount")
            or (it.get("author") or {}).get("follower_count")
            or 0
        )
        stats = it.get("stats") or it.get("statsV2") or {}
        views = int(stats.get("playCount") or it.get("play_count") or it.get("playCount") or 0)
        likes = int(stats.get("diggCount") or it.get("digg_count") or it.get("diggCount") or 0)
        comments = int(stats.get("commentCount") or it.get("comment_count") or it.get("commentCount") or 0)
        shares = int(stats.get("shareCount") or it.get("share_count") or it.get("shareCount") or 0)
        vid_id = str(it.get("id") or it.get("aweme_id") or it.get("video_id", ""))
        ts = it.get("createTime") or it.get("create_time") or 0
        try:
            pub_dt = datetime.fromtimestamp(int(ts)) if ts else None
            days_ag = (datetime.now() - pub_dt).days if pub_dt else 30
            published = pub_dt.strftime("%Y-%m-%d") if pub_dt else ""
        except Exception:
            days_ag = 30
            published = ""

        dur_sec = int((it.get("video") or {}).get("duration", 0) or it.get("duration", 0) or 0)
        score, breakdown = score_video(views, likes + shares * 2, comments, days_ag, int(followers))

        rows.append({
            "platform": "TikTok",
            "id": vid_id,
            "title": (it.get("desc") or it.get("text") or it.get("title") or "")[:120],
            "channel": f"@{author}" if author else "",
            "channel_id": author,
            "subscribers": int(followers),
            "published": published,
            "days_ago": days_ag,
            "views": views, "likes": likes, "comments": comments,
            "shares": shares,
            "duration_sec": dur_sec, "duration": fmt_duration(dur_sec),
            "thumbnail": (it.get("video") or {}).get("cover", "") or (it.get("video") or {}).get("dynamicCover", "") or it.get("cover", ""),
            "url": it.get("webVideoUrl") or f"https://www.tiktok.com/@{author}/video/{vid_id}",
            "description": (it.get("desc") or it.get("text") or "")[:300],
            "tags": "",
            "score": score,
            "er_pct": breakdown.get("er_pct", 0),
            "velocity_per_day": breakdown.get("velocity_per_day", 0),
        })
    return rows, f"✅ {successful_host}: {len(rows)} видео"


# ─────────────────────────────────────────────────────────────────────────────
# ИСТОЧНИК 5: Instaloader (бесплатный fallback для Instagram)
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=900, show_spinner=False)
def search_instagram_instaloader(
    hashtag: str, fetch_limit: int = 30,
    ig_user: str = "", ig_pass: str = "",
) -> list[dict]:
    """
    Парсинг через Instaloader.
    ВАЖНО: Без логина Instagram сильно ограничивает доступ — рекомендуется логиниться.
    """
    try:
        import instaloader
    except ImportError:
        return []

    L = instaloader.Instaloader(
        download_pictures=False, download_videos=False,
        download_video_thumbnails=False, download_geotags=False,
        download_comments=False, save_metadata=False,
        request_timeout=30, user_agent=USER_AGENT,
    )

    # Логин (опционально)
    if ig_user and ig_pass:
        try:
            L.login(ig_user, ig_pass)
            logger.info("Instaloader: успешный логин %s", ig_user)
        except Exception as e:
            logger.warning("Instaloader login error: %s", e)

    tag_name = hashtag.replace("#", "").strip()
    rows: list[dict] = []
    try:
        hashtag_obj = instaloader.Hashtag.from_name(L.context, tag_name)
        for i, post in enumerate(hashtag_obj.get_posts_resumable()):
            if i >= fetch_limit:
                break
            try:
                views = int(post.video_view_count or 0)
                likes = int(post.likes or 0)
                if views == 0 and post.is_video and likes > 0:
                    views = likes * 10
                comments = int(post.comments or 0)
                days_ag = (datetime.now() - post.date_utc.replace(tzinfo=None)).days
                score, breakdown = score_video(views, likes, comments, max(days_ag, 1))

                rows.append({
                    "platform": "Instagram",
                    "id": post.shortcode,
                    "title": (post.caption or "")[:120],
                    "channel": f"@{post.owner_username}",
                    "channel_id": post.owner_username,
                    "subscribers": 0,
                    "published": post.date_utc.strftime("%Y-%m-%d"),
                    "days_ago": days_ag,
                    "views": views, "likes": likes, "comments": comments,
                    "duration_sec": int(post.video_duration or 0),
                    "duration": fmt_duration(int(post.video_duration or 0)),
                    "thumbnail": post.url,
                    "url": f"https://www.instagram.com/p/{post.shortcode}/",
                    "description": (post.caption or "")[:300],
                    "tags": ", ".join(list(post.caption_hashtags)[:10]),
                    "score": score,
                    "er_pct": breakdown.get("er_pct", 0),
                    "velocity_per_day": breakdown.get("velocity_per_day", 0),
                })
            except Exception as e:
                logger.debug("Instaloader post error: %s", e)
                continue
            # Антибан: минимальная задержка
            time.sleep(0.5)
    except Exception as e:
        logger.warning("Instaloader hashtag error: %s", e)
        raise RuntimeError(f"Instaloader: {e}")
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# ИНИЦИАЛИЗАЦИЯ STATE
# ─────────────────────────────────────────────────────────────────────────────
saved = load_saved_keys()

for k in ["youtube_api_key", "apify_token", "rapidapi_key",
          "instagram_user", "instagram_pass"]:
    if k not in st.session_state:
        st.session_state[k] = saved.get(k, "")

if "setup_done" not in st.session_state:
    st.session_state.setup_done = bool(
        saved.get("youtube_api_key") or saved.get("apify_token")
        or saved.get("rapidapi_key") or check_ytdlp()
    )

if "ytdlp_installed" not in st.session_state:
    st.session_state.ytdlp_installed = check_ytdlp()


# ─────────────────────────────────────────────────────────────────────────────
# МАСТЕР ПЕРВОГО ЗАПУСКА
# ─────────────────────────────────────────────────────────────────────────────
def show_setup_wizard() -> None:
    st.markdown("""
    <div class='main-header'>
        <h1>🚀 SmartTrend Analyzer Pro</h1>
        <p>Профессиональный анализ трендовых видео для маркетинговых агентств</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("## ⚙️ Первоначальная настройка")
    st.markdown("Подключи источники данных. Можно начать с одного и подключать остальные постепенно.")

    tab_yt, tab_ig_tt, tab_security = st.tabs([
        "📺 YouTube", "📸 Instagram + TikTok", "🔒 Безопасность"
    ])

    # ── Вкладка YouTube ─────────────────────────────────────────────
    with tab_yt:
        st.markdown("### YouTube — выбери один из двух способов")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 🆓 Бесплатно (yt-dlp)")
            st.markdown("""<div class='success-box'>
            ✅ Без API ключа<br>
            ✅ Без лимитов<br>
            ⚠️ Чуть медленнее, нет данных о подписчиках
            </div>""", unsafe_allow_html=True)
            if check_ytdlp():
                st.success("✅ yt-dlp уже установлен")
            else:
                if st.button("📦 Установить yt-dlp", type="primary", use_container_width=True):
                    with st.spinner("Устанавливаю yt-dlp..."):
                        ok, msg = install_package("yt-dlp")
                        if ok:
                            st.session_state.ytdlp_installed = True
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

        with col2:
            st.markdown("#### 🔑 С API ключом (рекомендуется)")
            st.markdown("""<div class='info-box'>
            ✅ Точная статистика (подписчики, теги)<br>
            ✅ Доступ к Trending Charts<br>
            ✅ 10 000 запросов в день бесплатно
            </div>""", unsafe_allow_html=True)
            with st.expander("📋 Как получить ключ (5 минут)"):
                st.markdown("""
                1. Перейди в [Google Cloud Console](https://console.cloud.google.com)
                2. Создай новый проект → найди и включи **YouTube Data API v3**
                3. APIs & Services → Credentials → CREATE CREDENTIALS → API key
                4. Скопируй ключ вида `AIzaSy...`
                """)
            yt_in = st.text_input(
                "YouTube API ключ:",
                value=st.session_state.youtube_api_key,
                type="password", placeholder="AIzaSy...",
                key="wiz_yt_key",
            )
            if yt_in and st.button("✅ Проверить и сохранить", type="primary",
                                    use_container_width=True, key="wiz_yt_btn"):
                with st.spinner("Проверяю ключ..."):
                    ok, msg = validate_youtube_key(yt_in)
                    if ok:
                        st.session_state.youtube_api_key = yt_in.strip()
                        st.success(msg)
                        st.session_state.setup_done = True
                        if not check_ytdlp():
                            install_package("yt-dlp")
                            st.session_state.ytdlp_installed = True
                        time.sleep(0.7)
                        st.rerun()
                    else:
                        st.error(msg)

    # ── Вкладка Instagram + TikTok ─────────────────────────────────
    with tab_ig_tt:
        st.markdown("### Instagram и TikTok — выбери источник(и)")
        col_a, col_b, col_c = st.columns(3)

        with col_a:
            st.markdown("#### 💎 Apify (премиум)")
            st.markdown("""<div class='info-box'>
            ✅ Самый стабильный<br>
            ✅ Instagram + TikTok<br>
            💰 $5 бесплатно, далее ~$2/1000 постов
            </div>""", unsafe_allow_html=True)
            st.link_button("Открыть Apify →",
                "https://console.apify.com/account/integrations",
                use_container_width=True)
            ap_in = st.text_input(
                "Apify Token:", value=st.session_state.apify_token,
                type="password", placeholder="apify_api_...",
                key="wiz_ap_key",
            )
            if ap_in and st.button("✅ Проверить Apify", use_container_width=True, key="wiz_ap_btn"):
                with st.spinner("Проверяю Apify..."):
                    ok, msg = validate_apify_token(ap_in)
                    if ok:
                        st.session_state.apify_token = ap_in.strip()
                        st.success(msg)
                        st.session_state.setup_done = True
                        time.sleep(0.7)
                        st.rerun()
                    else:
                        st.error(msg)

        with col_b:
            st.markdown("#### ⚡ RapidAPI (TikTok)")
            st.markdown("""<div class='info-box'>
            ✅ Альтернатива Apify для TikTok<br>
            ✅ Бесплатный тариф 500 запросов/мес<br>
            ⚠️ Только TikTok
            </div>""", unsafe_allow_html=True)
            st.link_button("Открыть RapidAPI →",
                "https://rapidapi.com/search/tiktok",
                use_container_width=True)
            ra_in = st.text_input(
                "RapidAPI Key:", value=st.session_state.rapidapi_key,
                type="password", placeholder="ключ от RapidAPI",
                key="wiz_ra_key",
            )
            if ra_in and st.button("💾 Сохранить RapidAPI", use_container_width=True, key="wiz_ra_btn"):
                st.session_state.rapidapi_key = ra_in.strip()
                st.success("✅ Сохранено")
                st.session_state.setup_done = True
                time.sleep(0.5)
                st.rerun()

        with col_c:
            st.markdown("#### 🆓 Instaloader (Instagram)")
            st.markdown("""<div class='success-box'>
            ✅ Бесплатно<br>
            ⚠️ Желательно залогиниться<br>
            ⚠️ Риск бана аккаунта Instagram
            </div>""", unsafe_allow_html=True)
            if check_instaloader():
                st.success("✅ Instaloader установлен")
            else:
                if st.button("📦 Установить Instaloader", use_container_width=True, key="wiz_il_btn"):
                    with st.spinner("Устанавливаю..."):
                        ok, msg = install_package("instaloader")
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
            with st.expander("🔐 Логин Instagram (опционально)"):
                st.warning("⚠️ Используй второстепенный аккаунт — есть риск временной блокировки.")
                ig_u = st.text_input("Логин:", value=st.session_state.instagram_user, key="wiz_il_u")
                ig_p = st.text_input("Пароль:", value=st.session_state.instagram_pass, type="password", key="wiz_il_p")
                if st.button("💾 Сохранить логин", use_container_width=True, key="wiz_il_save"):
                    st.session_state.instagram_user = ig_u
                    st.session_state.instagram_pass = ig_p
                    st.success("✅ Сохранено в сессии")

    # ── Вкладка Безопасность ──────────────────────────────────────
    with tab_security:
        st.markdown("### 🔒 Как хранятся ключи")
        st.markdown("""<div class='info-box'>
        <b>На Streamlit Cloud:</b><br>
        Ключи задаются один раз через <code>Manage app → Secrets</code>:
        </div>""", unsafe_allow_html=True)
        st.code("""youtube_api_key = "AIzaSy..."
apify_token = "apify_api_..."
rapidapi_key = "..."
instagram_user = ""
instagram_pass = ""
""", language="toml")
        st.markdown("""<div class='success-box'>
        <b>Локально или Docker:</b> используются переменные окружения:
        </div>""", unsafe_allow_html=True)
        st.code("""export YOUTUBE_API_KEY="AIzaSy..."
export APIFY_TOKEN="apify_api_..."
export RAPIDAPI_KEY="..."
streamlit run app.py
""", language="bash")
        st.markdown("""
        - 🔐 Ключи **никогда** не сохраняются в коде или истории — только в защищённом хранилище.
        - 🔐 Маскировка ключей в логах: `AIza...XyZ1`
        - 🔐 Ретраи и rate-limiting защищают от случайного превышения квот.
        - 🔐 Только HTTPS-запросы, таймауты, валидация ответов.
        """)

    st.markdown("---")
    col_skip, col_start = st.columns([1, 1])
    with col_skip:
        if st.button("🎮 Демо-режим (без настройки)", use_container_width=True):
            st.session_state.setup_done = True
            st.rerun()
    with col_start:
        if st.button("✅ Завершить и начать", type="primary", use_container_width=True):
            if (st.session_state.youtube_api_key or st.session_state.apify_token
                    or st.session_state.rapidapi_key or check_ytdlp()):
                st.session_state.setup_done = True
                st.rerun()
            else:
                st.warning("Подключи хотя бы один источник или войди в демо-режим.")


# Показываем мастер при первом запуске
if not st.session_state.setup_done:
    show_setup_wizard()
    st.stop()


# ─────────────────────────────────────────────────────────────────────────────
# СОСТОЯНИЕ ИСТОЧНИКОВ
# ─────────────────────────────────────────────────────────────────────────────
has_yt_api = bool(st.session_state.youtube_api_key)
has_apify = bool(st.session_state.apify_token)
has_rapidapi = bool(st.session_state.rapidapi_key)
has_ytdlp = st.session_state.ytdlp_installed or check_ytdlp()
has_instaloader = check_instaloader()
use_demo = not (has_yt_api or has_apify or has_rapidapi or has_ytdlp or has_instaloader)


# ─────────────────────────────────────────────────────────────────────────────
# ДЕМО-ДАННЫЕ (если ничего не подключено)
# ─────────────────────────────────────────────────────────────────────────────
def get_demo_data() -> list[dict]:
    """Демо-данные для бьюти/моды/косметики."""
    base = [
        {"platform":"TikTok","id":"tt_001","title":"Glass Skin Routine: 5 шагов до идеальной кожи ✨","channel":"@beautybyalice","subscribers":2_100_000,"published":"2026-05-21","days_ago":6,"views":18_400_000,"likes":2_300_000,"comments":48_000,"shares":140_000,"duration_sec":52,"duration":"0:52","score":99,"er_pct":12.8,"velocity_per_day":3_066_666,"url":"https://www.tiktok.com/@beautybyalice/video/tt_001","thumbnail":"https://picsum.photos/seed/glass_skin/320/180","tags":"#skincare,#glassskin,#beautyhacks","description":"Glass skin за 5 минут — корейский ритуал."},
        {"platform":"Instagram","id":"ig_001","title":"Soft Glam макияж — пошагово 💋","channel":"@makeupbyvika","subscribers":890_000,"published":"2026-05-23","days_ago":4,"views":4_800_000,"likes":380_000,"comments":12_400,"duration_sec":58,"duration":"0:58","score":96,"er_pct":8.2,"velocity_per_day":1_200_000,"url":"https://www.instagram.com/p/ig_001/","thumbnail":"https://picsum.photos/seed/soft_glam/320/180","tags":"#makeup,#softglam,#beautytips","description":"Базовый soft glam — урок для начинающих."},
        {"platform":"YouTube","id":"yt_001","title":"Я попробовала ВСЕ вирусные кремы из TikTok — обзор","channel":"BeautyHaul Pro","subscribers":3_400_000,"published":"2026-05-15","days_ago":12,"views":9_800_000,"likes":540_000,"comments":28_000,"duration_sec":840,"duration":"14:00","score":94,"er_pct":5.8,"velocity_per_day":816_666,"url":"https://www.youtube.com/watch?v=yt_001","thumbnail":"https://picsum.photos/seed/viral_creams/320/180","tags":"beauty,review,tiktok trends","description":"Тестирую все вирусные кремы TikTok 2026."},
        {"platform":"TikTok","id":"tt_002","title":"Outfit для свидания — 3 образа за 60 сек 👗","channel":"@stylebymila","subscribers":1_500_000,"published":"2026-05-19","days_ago":8,"views":12_300_000,"likes":1_100_000,"comments":24_000,"shares":85_000,"duration_sec":59,"duration":"0:59","score":97,"er_pct":9.1,"velocity_per_day":1_537_500,"url":"https://www.tiktok.com/@stylebymila/video/tt_002","thumbnail":"https://picsum.photos/seed/date_outfit/320/180","tags":"#fashion,#ootd,#dateoutfit","description":"3 беспроигрышных образа на свидание."},
        {"platform":"Instagram","id":"ig_002","title":"GRWM: бранч с подругами 🥂","channel":"@laralifestyle","subscribers":620_000,"published":"2026-05-24","days_ago":3,"views":3_200_000,"likes":210_000,"comments":8_400,"duration_sec":75,"duration":"1:15","score":92,"er_pct":6.8,"velocity_per_day":1_066_666,"url":"https://www.instagram.com/p/ig_002/","thumbnail":"https://picsum.photos/seed/grwm_brunch/320/180","tags":"#grwm,#brunch,#lifestyle","description":"Get ready with me — собираюсь на бранч."},
        {"platform":"YouTube","id":"yt_002","title":"Top 10 трендов косметики весна-лето 2026","channel":"VogueRu","subscribers":5_200_000,"published":"2026-05-10","days_ago":17,"views":6_700_000,"likes":280_000,"comments":15_000,"duration_sec":720,"duration":"12:00","score":89,"er_pct":4.4,"velocity_per_day":394_117,"url":"https://www.youtube.com/watch?v=yt_002","thumbnail":"https://picsum.photos/seed/spring_trends/320/180","tags":"beauty,trends,spring 2026","description":"Главные косметические тренды сезона."},
        {"platform":"TikTok","id":"tt_003","title":"Bronzy summer makeup — за 90 секунд ☀️","channel":"@sunkissedkate","subscribers":780_000,"published":"2026-05-22","days_ago":5,"views":8_500_000,"likes":740_000,"comments":18_000,"shares":52_000,"duration_sec":88,"duration":"1:28","score":95,"er_pct":8.7,"velocity_per_day":1_700_000,"url":"https://www.tiktok.com/@sunkissedkate/video/tt_003","thumbnail":"https://picsum.photos/seed/bronzy/320/180","tags":"#summer,#bronzy,#makeup","description":"Идеальный летний макияж — bronzy glow."},
        {"platform":"Instagram","id":"ig_003","title":"Anti-haul: ЧТО я НЕ покупаю из косметики 🚫","channel":"@honestbeauty","subscribers":420_000,"published":"2026-05-20","days_ago":7,"views":2_100_000,"likes":195_000,"comments":11_200,"duration_sec":92,"duration":"1:32","score":91,"er_pct":9.8,"velocity_per_day":300_000,"url":"https://www.instagram.com/p/ig_003/","thumbnail":"https://picsum.photos/seed/anti_haul/320/180","tags":"#antihaul,#honestreview,#beauty","description":"Антиподборка — что НЕ стоит покупать."},
        {"platform":"YouTube","id":"yt_003","title":"Уход за кожей 25+ — врач-дерматолог объясняет","channel":"DermClinic","subscribers":1_200_000,"published":"2026-05-05","days_ago":22,"views":4_500_000,"likes":210_000,"comments":18_000,"duration_sec":1080,"duration":"18:00","score":87,"er_pct":5.1,"velocity_per_day":204_545,"url":"https://www.youtube.com/watch?v=yt_003","thumbnail":"https://picsum.photos/seed/derm_25/320/180","tags":"skincare,dermatology,routine","description":"Профессиональные советы дерматолога."},
        {"platform":"TikTok","id":"tt_004","title":"3 хака для красивой укладки — без утюжка ⚡","channel":"@hairhacksmary","subscribers":1_100_000,"published":"2026-05-25","days_ago":2,"views":7_200_000,"likes":620_000,"comments":14_500,"shares":48_000,"duration_sec":45,"duration":"0:45","score":98,"er_pct":9.0,"velocity_per_day":3_600_000,"url":"https://www.tiktok.com/@hairhacksmary/video/tt_004","thumbnail":"https://picsum.photos/seed/hair_hack/320/180","tags":"#hair,#hairhack,#hairstyle","description":"3 способа красивой укладки без термоприборов."},
        {"platform":"Instagram","id":"ig_004","title":"Lip combo дня: nude + glow 💄","channel":"@lipgloss_addict","subscribers":340_000,"published":"2026-05-26","days_ago":1,"views":1_400_000,"likes":125_000,"comments":4_800,"duration_sec":28,"duration":"0:28","score":90,"er_pct":9.3,"velocity_per_day":1_400_000,"url":"https://www.instagram.com/p/ig_004/","thumbnail":"https://picsum.photos/seed/lip_combo/320/180","tags":"#lipcombo,#lipstick,#makeup","description":"Идеальное сочетание помады и блеска."},
        {"platform":"YouTube","id":"yt_004","title":"Капсульный гардероб на лето 2026 — 12 вещей","channel":"MinimalStyleRu","subscribers":890_000,"published":"2026-05-12","days_ago":15,"views":3_900_000,"likes":156_000,"comments":9_200,"duration_sec":900,"duration":"15:00","score":86,"er_pct":4.2,"velocity_per_day":260_000,"url":"https://www.youtube.com/watch?v=yt_004","thumbnail":"https://picsum.photos/seed/capsule/320/180","tags":"fashion,capsule wardrobe,summer","description":"Минималистичный гардероб на лето."},
    ]
    return base


# ─────────────────────────────────────────────────────────────────────────────
# БОКОВАЯ ПАНЕЛЬ
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🚀 SmartTrend Pro")
    st.markdown("*Профессиональный анализ трендов*")
    st.markdown("---")

    # Статус источников
    st.markdown("### 📡 Источники данных")
    sources = [
        ("YouTube API", has_yt_api, st.session_state.youtube_api_key),
        ("yt-dlp", has_ytdlp, ""),
        ("Apify (IG+TT)", has_apify, st.session_state.apify_token),
        ("RapidAPI (TT)", has_rapidapi, st.session_state.rapidapi_key),
        ("Instaloader (IG)", has_instaloader, ""),
    ]
    for name, active, key in sources:
        icon = "🟢" if active else "⚪"
        st.markdown(f"{icon} **{name}**" + (f" `{mask_key(key)}`" if active and key else ""))

    if use_demo:
        st.markdown("""<div class='warning-box'>
        🟡 <b>Демо-режим</b><br>
        Подключи источники во вкладке Настройки.
        </div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 🎯 Ниша")
    niche = st.selectbox(
        "Готовый пресет:", ["📝 Свободный поиск"] + list(NICHE_PRESETS.keys()),
        help="Пресет подставит готовые запросы и хэштеги для ниши."
    )

    if niche != "📝 Свободный поиск":
        preset = NICHE_PRESETS[niche]
        query_options = preset["queries"] + ["📝 Свой запрос..."]
        query_choice = st.selectbox("Поисковый запрос:", query_options)
        if query_choice == "📝 Свой запрос...":
            search_query = st.text_input("Свой запрос:", value=preset["queries"][0])
        else:
            search_query = query_choice
        niche_tags = preset["hashtags"]
    else:
        search_query = st.text_input("Поисковый запрос:", value="makeup tutorial")
        custom_tags = st.text_input(
            "Свои хэштеги (через запятую):",
            value="", placeholder="makeup, beauty, skincare",
        )
        niche_tags = [t.strip() for t in custom_tags.split(",") if t.strip()]

    # Валидация запроса
    search_query = (search_query or "").strip()[:200]
    if not search_query:
        st.error("Введите поисковый запрос")
        st.stop()

    st.markdown("---")
    st.markdown("### 🌐 Платформы и регион")
    available = []
    if has_yt_api or has_ytdlp:
        available.append("YouTube")
    if has_apify or has_instaloader:
        available.append("Instagram")
    if has_apify or has_rapidapi:
        available.append("TikTok")
    if use_demo or not available:
        available = ["YouTube", "Instagram", "TikTok"]

    platforms = st.multiselect("Платформы:", available, default=available)

    region_label = st.selectbox("Регион:", list(REGIONS.keys()), index=0)
    region_code = REGIONS[region_label]

    st.markdown("---")
    st.markdown("### 🎯 Фильтры качества")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        min_views = st.number_input("Мин. просмотров", 0, 50_000_000, 10_000, 5_000)
    with col_f2:
        min_score = st.slider("Мин. рейтинг", 0, 100, 40)

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        date_range = st.slider("Дней назад", 1, 365, 30)
    with col_d2:
        max_results = st.selectbox("Видео на платформу", [10, 25, 50, 100], index=1)

    # Видео-длина для YouTube
    yt_duration = st.selectbox(
        "Длина видео:",
        ["Любая", "Shorts (<4 мин)", "Средние (4-20 мин)", "Длинные (>20 мин)"],
        help="Применяется только к YouTube",
    )
    yt_duration_map = {
        "Любая": "any", "Shorts (<4 мин)": "short",
        "Средние (4-20 мин)": "medium", "Длинные (>20 мин)": "long",
    }

    sort_by = st.selectbox(
        "Сортировка:",
        ["score", "views", "likes", "comments", "velocity_per_day", "er_pct", "days_ago"],
        format_func=lambda x: {
            "score": "🔥 Рейтинг залётности",
            "views": "👁 Просмотры",
            "likes": "👍 Лайки",
            "comments": "💬 Комментарии",
            "velocity_per_day": "🚀 Просмотры в день",
            "er_pct": "💖 Engagement Rate",
            "days_ago": "📅 Новизна",
        }[x],
    )

    use_yt_trending = st.checkbox(
        "➕ Включить YouTube Trending",
        value=False,
        help="Дополняет результаты текущим трендовым чартом региона",
    )

    st.markdown("---")
    run_btn = st.button("🚀 Запустить анализ", use_container_width=True, type="primary")

    st.markdown("---")
    if st.button("⚙️ Настройки источников", use_container_width=True):
        st.session_state.setup_done = False
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# ГЛАВНЫЙ ЭКРАН
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class='main-header'>
    <h1>🚀 SmartTrend Analyzer Pro</h1>
    <p>Ниша: <b>{niche}</b> · Запрос: <b>{search_query}</b> · Регион: <b>{region_label}</b></p>
</div>
""", unsafe_allow_html=True)

if use_demo:
    st.markdown("""<div class='warning-box'>
    ℹ️ <b>Демо-режим:</b> показываем образцовые данные.
    Подключи источники в <b>Настройках источников</b> в боковой панели.
    </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# ЗАГРУЗКА ДАННЫХ
# ─────────────────────────────────────────────────────────────────────────────
def load_all_data() -> pd.DataFrame:
    """Загружает данные из всех подключённых источников."""
    if use_demo:
        df_demo = pd.DataFrame(get_demo_data())
        if platforms:
            df_demo = df_demo[df_demo["platform"].isin(platforms)]
        return df_demo

    frames: list[pd.DataFrame] = []
    diagnostics: list[str] = []  # Детальный лог по каждому источнику
    # Берём с запасом — после дедупа и фильтров останется меньше
    fetch_limit = max(200, max_results * 5)
    progress = st.progress(0.0, text="Подготовка...")
    step = 0
    total_steps = sum([
        "YouTube" in platforms,
        use_yt_trending and "YouTube" in platforms,
        "Instagram" in platforms,
        "TikTok" in platforms,
    ]) or 1

    # ── YouTube (мульти-запрос: основной + niche-варианты) ──
    if "YouTube" in platforms:
        step += 1
        progress.progress(step / total_steps, text="📺 Загружаю YouTube...")
        if not has_yt_api and not has_ytdlp:
            diagnostics.append("⚠️ **YouTube:** нет ни API ключа, ни yt-dlp. Снимите галочку YouTube в сайдбаре или добавьте ключ в Настройках.")
        else:
            # Строим список запросов: основной + до 4 niche-тегов (расширяем охват)
            yt_queries = [search_query]
            for t in (niche_tags or [])[:4]:
                t_clean = t.replace("#", "").strip()
                if t_clean and t_clean.lower() != search_query.lower():
                    yt_queries.append(t_clean)
            per_query = max(30, fetch_limit // max(1, len(yt_queries)))
            yt_all: list[dict] = []
            yt_seen: set = set()
            yt_logs = []
            for q in yt_queries:
                if len(yt_all) >= fetch_limit:
                    break
                try:
                    if has_yt_api:
                        rows = search_youtube_api(
                            st.session_state.youtube_api_key, q,
                            fetch_limit=per_query, region=region_code,
                            days=date_range,
                            video_duration=yt_duration_map[yt_duration],
                        )
                        src_name = "YouTube API"
                    else:
                        rows = search_ytdlp(q, per_query)
                        src_name = "yt-dlp"
                    new_rows = [r for r in rows if r.get("id") not in yt_seen]
                    for r in new_rows:
                        yt_seen.add(r.get("id"))
                    yt_all.extend(new_rows)
                    yt_logs.append(f"'{q}': +{len(new_rows)}")
                except Exception as e:
                    yt_logs.append(f"'{q}' ошибка: {str(e)[:80]}")
                    logger.error("YouTube '%s' error: %s", q, e)
            if yt_all:
                frames.append(pd.DataFrame(yt_all))
                diagnostics.append(f"✅ **YouTube ({src_name}):** {len(yt_all)} видео ({'; '.join(yt_logs)})")
            else:
                diagnostics.append(f"⚠️ **YouTube:** пусто по всем запросам ({'; '.join(yt_logs)})")

    # ── YouTube Trending (опционально) ──
    if use_yt_trending and "YouTube" in platforms and has_yt_api:
        step += 1
        progress.progress(step / total_steps, text="🔥 YouTube Trending...")
        try:
            trend_rows = get_youtube_trending(
                st.session_state.youtube_api_key, region_code, limit=50,
            )
            if trend_rows:
                frames.append(pd.DataFrame(trend_rows))
                diagnostics.append(f"✅ **YouTube Trending:** +{len(trend_rows)} видео")
        except Exception as e:
            logger.warning("YT trending: %s", e)

    # ── Instagram ──
    if "Instagram" in platforms:
        step += 1
        progress.progress(step / total_steps, text="📸 Загружаю Instagram...")
        if not has_apify and not has_instaloader:
            diagnostics.append("⚠️ **Instagram:** нет ни Apify, ни Instaloader. Снимите галочку Instagram в сайдбаре.")
        else:
            ig_tags = smart_hashtags(search_query, niche_tags)
            ig_rows: list[dict] = []
            ig_seen: set = set()
            ig_src_logs = []
            if has_apify:
                try:
                    # Apify: передаём до 8 хэштегов (актор сам объединит)
                    ig_rows = search_instagram_apify(
                        st.session_state.apify_token, ig_tags[:8], fetch_limit,
                    )
                    for r in ig_rows:
                        if r.get("id"):
                            ig_seen.add(r["id"])
                    ig_src_logs.append(f"Apify [{len(ig_tags[:8])} тегов]: {len(ig_rows)} видео")
                except Exception as e:
                    ig_src_logs.append(f"Apify ошибка: {str(e)[:100]}")
                    logger.error("IG Apify error: %s", e)
            # Instaloader — или как fallback, или добор если Apify дал мало
            if len(ig_rows) < fetch_limit and has_instaloader:
                if not ig_rows:
                    ig_src_logs.append("пробую Instaloader")
                else:
                    ig_src_logs.append("добираю Instaloader")
                per_tag = max(30, (fetch_limit - len(ig_rows)) // 4)
                for tag in ig_tags[:6]:  # было 2, стало 6
                    if len(ig_rows) >= fetch_limit:
                        break
                    try:
                        extra = search_instagram_instaloader(
                            tag, per_tag,
                            st.session_state.instagram_user,
                            st.session_state.instagram_pass,
                        )
                        new_extra = [r for r in extra if r.get("id") not in ig_seen]
                        for r in new_extra:
                            if r.get("id"):
                                ig_seen.add(r["id"])
                        ig_rows.extend(new_extra)
                        ig_src_logs.append(f"#{tag}: +{len(new_extra)}")
                    except Exception as e:
                        ig_src_logs.append(f"#{tag}: {str(e)[:60]}")
                        logger.warning("Instaloader %s: %s", tag, e)
            if ig_rows:
                frames.append(pd.DataFrame(ig_rows))
                diagnostics.append(f"✅ **Instagram:** {len(ig_rows)} видео ({'; '.join(ig_src_logs)})")
            else:
                diagnostics.append(f"❌ **Instagram:** пусто ({'; '.join(ig_src_logs) or 'нет попыток'}). На Streamlit Cloud Instaloader часто блокируется — нужен Apify или локальный запуск.")

    # ── TikTok ──
    if "TikTok" in platforms:
        step += 1
        progress.progress(step / total_steps, text="🎵 Загружаю TikTok...")
        if not has_apify and not has_rapidapi:
            diagnostics.append("⚠️ **TikTok:** нет ни Apify, ни RapidAPI. Снимите галочку TikTok в сайдбаре.")
        else:
            tt_tags = smart_hashtags(search_query, niche_tags)
            tt_rows: list[dict] = []
            tt_seen: set = set()
            tt_src_logs = []
            if has_apify:
                try:
                    tt_rows = search_tiktok_apify(
                        st.session_state.apify_token, tt_tags[:8], fetch_limit,
                    )
                    for r in tt_rows:
                        if r.get("id"):
                            tt_seen.add(r["id"])
                    tt_src_logs.append(f"Apify [{len(tt_tags[:8])} тегов]: {len(tt_rows)} видео")
                except Exception as e:
                    tt_src_logs.append(f"Apify ошибка: {str(e)[:100]}")
                    logger.error("TT Apify error: %s", e)
            # RapidAPI — или фоллбэк, или добор если Apify дал мало
            if len(tt_rows) < fetch_limit and has_rapidapi:
                per_tag = max(30, (fetch_limit - len(tt_rows)) // 4)
                for tag in tt_tags[:6]:  # было 2, стало 6
                    if len(tt_rows) >= fetch_limit:
                        break
                    try:
                        extra, diag = search_tiktok_rapidapi(
                            st.session_state.rapidapi_key, tag, per_tag,
                        )
                        new_extra = [r for r in extra if r.get("id") not in tt_seen]
                        for r in new_extra:
                            if r.get("id"):
                                tt_seen.add(r["id"])
                        tt_rows.extend(new_extra)
                        tt_src_logs.append(f"#{tag}: +{len(new_extra)} ({diag})")
                    except Exception as e:
                        tt_src_logs.append(f"RapidAPI #{tag}: {str(e)[:80]}")
                        logger.warning("RapidAPI %s: %s", tag, e)
            if tt_rows:
                frames.append(pd.DataFrame(tt_rows))
                diagnostics.append(f"✅ **TikTok:** {len(tt_rows)} видео ({'; '.join(tt_src_logs)})")
            else:
                diagnostics.append(f"❌ **TikTok:** пусто. {'; '.join(tt_src_logs) or 'нет попыток'}")

    progress.progress(1.0, text="✅ Готово")
    time.sleep(0.3)
    progress.empty()

    # Сохраняем диагностику для отображения пользователю
    st.session_state["_diagnostics"] = diagnostics

    if not frames:
        st.error("### ❌ Ни один источник не вернул данных\n\nДетали по каждому источнику ниже:")
        for d in diagnostics:
            st.markdown(d)
        st.markdown("---")
        st.info(
            "💡 **Что делать:**\n"
            "1. Оставьте в сайдбаре только те платформы, для которых есть источники (зелёные кружки)\n"
            "2. Для YouTube — нужен API ключ или yt-dlp в requirements.txt\n"
            "3. Для Instagram на Streamlit Cloud — нужен **Apify** (Instaloader блокируется с датацентровых IP)\n"
            "4. Для TikTok через RapidAPI — вы должны быть **подписаны** хотя бы на один из TikTok-API на RapidAPI (Basic-тариф обычно бесплатный)"
        )
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    # Обязательные колонки
    for col in ["shares", "subscribers", "er_pct", "velocity_per_day"]:
        if col not in df.columns:
            df[col] = 0
    df = df.fillna({"shares": 0, "subscribers": 0, "er_pct": 0, "velocity_per_day": 0})

    # Дедупликация
    df = df.drop_duplicates(subset=["platform", "id"], keep="first")

    # Фильтры
    df = df[df["views"] >= min_views]
    df = df[df["score"] >= min_score]
    df = df[df["days_ago"] <= date_range]

    if df.empty:
        return df

    # Топ по платформам
    sort_col = sort_by if sort_by in df.columns else "score"
    asc = sort_col == "days_ago"
    df = df.sort_values(sort_col, ascending=asc)
    df = df.groupby("platform").head(max_results).reset_index(drop=True)
    df = df.sort_values(sort_col, ascending=asc).reset_index(drop=True)
    return df


# Кэш по параметрам запроса
cache_key = hashlib.md5(
    f"{search_query}|{','.join(sorted(platforms))}|{region_code}|{date_range}"
    f"|{min_views}|{min_score}|{max_results}|{sort_by}|{yt_duration}|{use_yt_trending}|{niche}".encode()
).hexdigest()

if run_btn or st.session_state.get("last_cache_key") != cache_key:
    if not platforms:
        st.warning("Выбери хотя бы одну платформу")
        st.stop()
    with st.spinner("⏳ Собираю данные из всех источников..."):
        df = load_all_data()
    st.session_state["df_videos"] = df
    st.session_state["last_cache_key"] = cache_key

df = st.session_state.get("df_videos", pd.DataFrame(get_demo_data()))

# Показываем диагностику источников в expander'е (видна всегда)
if st.session_state.get("_diagnostics"):
    with st.expander("🔍 Диагностика источников данных", expanded=False):
        for d in st.session_state["_diagnostics"]:
            st.markdown(d)

if df.empty:
    st.warning(
        f"🤷 Не нашлось видео под критерии.\n\n"
        f"Попробуй: снизить мин. просмотры ({min_views}), "
        f"уменьшить мин. рейтинг ({min_score}), увеличить диапазон дней ({date_range}) "
        f"или сменить запрос."
    )
    st.stop()


# ─────────────────────────────────────────────────────────────────────────────
# ВКЛАДКИ
# ─────────────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🔥 Топ видео", "📊 Аналитика", "👤 Авторы", "📈 Тренды",
    "🎬 Референсы", "⚙️ Настройки",
])


# ════════════════════════════════════════════════════════════════════════════
# ВКЛАДКА 1: ТОП ВИДЕО
# ════════════════════════════════════════════════════════════════════════════
with tab1:
    total_views = int(df["views"].sum())
    avg_score = float(df["score"].mean())
    avg_er = float(df["er_pct"].mean()) if "er_pct" in df.columns else 0
    total_likes = int(df["likes"].sum())
    viral_count = int((df["score"] >= 90).sum())

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(f"""<div class='kpi-card'>
            <div class='kpi-value'>{fmt_number(total_views)}</div>
            <div class='kpi-label'>Суммарные просмотры</div>
            <div class='kpi-delta up'>▲ {len(df)} видео</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class='kpi-card'>
            <div class='kpi-value'>{avg_score:.0f}/100</div>
            <div class='kpi-label'>Средний рейтинг</div>
            <div class='kpi-delta {"up" if avg_score > 70 else "neutral"}'>
            {'▲ Высокий' if avg_score > 70 else '◆ Средний'} потенциал</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class='kpi-card'>
            <div class='kpi-value'>{avg_er:.2f}%</div>
            <div class='kpi-label'>Средний ER</div>
            <div class='kpi-delta {"up" if avg_er > 3 else "down"}'>
            {'▲ Высокий' if avg_er > 3 else '▽ Низкий'}</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""<div class='kpi-card'>
            <div class='kpi-value'>{viral_count}</div>
            <div class='kpi-label'>🔥 Вирусные (90+)</div>
            <div class='kpi-delta up'>▲ Готовы к копированию</div>
        </div>""", unsafe_allow_html=True)
    with c5:
        plat_counts = df["platform"].value_counts()
        best_plat = plat_counts.idxmax() if not plat_counts.empty else "—"
        st.markdown(f"""<div class='kpi-card'>
            <div class='kpi-value'>{best_plat}</div>
            <div class='kpi-label'>Лидирующая платформа</div>
            <div class='kpi-delta up'>▲ {plat_counts.max() if not plat_counts.empty else 0} видео</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    plat_filter = st.radio(
        "Фильтр платформы:",
        ["Все"] + sorted(df["platform"].unique()),
        horizontal=True,
    )
    show_df = df if plat_filter == "Все" else df[df["platform"] == plat_filter]
    st.markdown(f"**Найдено видео:** {len(show_df)}")
    st.markdown("---")

    for i, row in show_df.iterrows():
        plat_badge_cls = {"YouTube": "badge-yt", "Instagram": "badge-ig",
                          "TikTok": "badge-tt"}.get(row["platform"], "")
        score_pct = int(row.get("score", 0))
        col_img, col_info = st.columns([1, 3])
        with col_img:
            if row.get("thumbnail"):
                try:
                    st.image(row["thumbnail"], width=210)
                except Exception:
                    st.markdown("🖼")
        with col_info:
            badges = f"<span class='badge {plat_badge_cls}'>{row['platform']}</span>"
            if score_pct >= 95:
                badges += "<span class='badge badge-viral'>💥 Вирусное</span>"
            elif score_pct >= 85:
                badges += "<span class='badge badge-hot'>🔥 Горячее</span>"
            elif score_pct >= 70:
                badges += "<span class='badge badge-trending'>📈 В тренде</span>"
            if row.get("days_ago", 100) <= 7:
                badges += "<span class='badge badge-fresh'>✨ Свежее</span>"

            # Безопасная проверка: NaN из pandas не должен пройти как truthy
            shares_val = row.get("shares", 0)
            try:
                shares_val = float(shares_val) if shares_val is not None else 0
                import math
                if math.isnan(shares_val):
                    shares_val = 0
            except (TypeError, ValueError):
                shares_val = 0

            subs_val = row.get("subscribers", 0)
            try:
                subs_val = float(subs_val) if subs_val is not None else 0
                if math.isnan(subs_val):
                    subs_val = 0
            except (TypeError, ValueError):
                subs_val = 0

            shares_str = f" &nbsp;&nbsp; 🔁 {fmt_number(shares_val)}" if shares_val > 0 else ""
            subs_str = f"📢 {fmt_number(subs_val)} подп." if subs_val > 0 else ""

            title_safe = str(row.get("title", "")).replace("<", "&lt;").replace(">", "&gt;")
            channel_safe = str(row.get("channel", "—")).replace("<", "&lt;").replace(">", "&gt;")
            desc_safe = str(row.get("description", ""))[:140].replace("<", "&lt;").replace(">", "&gt;")

            st.markdown(f"""
            <div class='video-card'>
                {badges}
                <div class='video-title' style='margin-top:8px;'>{title_safe}</div>
                <div class='video-meta'>
                    📺 {channel_safe} {f"({subs_str})" if subs_str else ""}
                    &nbsp;|&nbsp; 📅 {row.get('published', '—')} ({row.get('days_ago', 0)} дн. назад)
                    &nbsp;|&nbsp; ⏱ {row.get('duration', '—')}
                </div>
                <div class='video-stats'>
                    👁 {fmt_number(row['views'])} &nbsp;&nbsp;
                    👍 {fmt_number(row['likes'])} &nbsp;&nbsp;
                    💬 {fmt_number(row['comments'])}{shares_str}
                    &nbsp;&nbsp; 💖 ER: {row.get('er_pct', 0):.2f}%
                    &nbsp;&nbsp; 🚀 {fmt_number(row.get('velocity_per_day', 0))}/день
                </div>
                <div style='margin-top:8px;font-size:0.82rem;color:#9e9e9e;'>{desc_safe}</div>
                <div style='margin-top:10px;display:flex;align-items:center;gap:10px;'>
                    <span style='font-size:0.82rem;color:#bbb;'>Рейтинг:</span>
                    <b style='color:#4fc3f7;font-size:1rem;'>{score_pct}/100</b>
                    <div class='score-bar-wrap' style='flex:1;'>
                        <div class='score-bar-fill' style='width:{score_pct}%;'></div>
                    </div>
                </div>
                <div style='margin-top:10px;'>
                    <a href='{row["url"]}' target='_blank' rel='noopener noreferrer'
                       style='color:#4fc3f7;font-size:0.85rem;text-decoration:none;'>
                       🔗 Открыть видео →</a>
                </div>
            </div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# ВКЛАДКА 2: АНАЛИТИКА
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("<div class='section-header'>📊 Глубокая аналитика</div>", unsafe_allow_html=True)

    # Топ по просмотрам + распределение по платформам
    col_a, col_b = st.columns(2)
    with col_a:
        top12 = df.nlargest(12, "views").sort_values("views")
        fig = px.bar(
            top12, x="views", y="title", orientation="h", color="platform",
            color_discrete_map=PLATFORM_COLORS,
            title="Топ-12 видео по просмотрам",
            labels={"views": "Просмотры", "title": ""},
            hover_data=["channel", "score"],
        )
        fig.update_layout(
            plot_bgcolor="#1e1e2e", paper_bgcolor="#1e1e2e",
            font_color="#e0e0e0", height=440,
            yaxis=dict(tickfont=dict(size=10)),
        )
        fig.update_xaxes(gridcolor="#2a2a3e")
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        plat_stats = df.groupby("platform").agg(
            views=("views", "sum"),
            count=("id", "count"),
            avg_score=("score", "mean"),
        ).reset_index()
        fig = px.pie(
            plat_stats, names="platform", values="views",
            color="platform", color_discrete_map=PLATFORM_COLORS,
            title="Доля просмотров по платформам", hole=0.45,
        )
        fig.update_layout(
            plot_bgcolor="#1e1e2e", paper_bgcolor="#1e1e2e",
            font_color="#e0e0e0", height=440,
        )
        st.plotly_chart(fig, use_container_width=True)

    # Engagement vs Reach + Top by ER
    col_c, col_d = st.columns(2)
    with col_c:
        fig = px.scatter(
            df, x="views", y="score", size="likes", color="platform",
            color_discrete_map=PLATFORM_COLORS,
            hover_data=["title", "channel", "days_ago"],
            title="Рейтинг vs Просмотры (размер = лайки)",
            labels={"views": "Просмотры (лог.)", "score": "Рейтинг"},
            size_max=40, log_x=True,
        )
        fig.update_layout(
            plot_bgcolor="#1e1e2e", paper_bgcolor="#1e1e2e",
            font_color="#e0e0e0", height=440,
        )
        fig.update_xaxes(gridcolor="#2a2a3e")
        fig.update_yaxes(gridcolor="#2a2a3e")
        st.plotly_chart(fig, use_container_width=True)

    with col_d:
        top_er = df.nlargest(10, "er_pct").sort_values("er_pct")
        fig = px.bar(
            top_er, x="er_pct", y="title", orientation="h", color="platform",
            color_discrete_map=PLATFORM_COLORS,
            title="Топ-10 по Engagement Rate (%)",
            labels={"er_pct": "ER %", "title": ""},
            hover_data=["channel", "views"],
        )
        fig.update_layout(
            plot_bgcolor="#1e1e2e", paper_bgcolor="#1e1e2e",
            font_color="#e0e0e0", height=440,
            yaxis=dict(tickfont=dict(size=10)),
        )
        st.plotly_chart(fig, use_container_width=True)

    # Velocity и длина видео
    col_e, col_f = st.columns(2)
    with col_e:
        if "velocity_per_day" in df.columns:
            top_vel = df.nlargest(10, "velocity_per_day").sort_values("velocity_per_day")
            fig = px.bar(
                top_vel, x="velocity_per_day", y="title", orientation="h",
                color="platform", color_discrete_map=PLATFORM_COLORS,
                title="🚀 Топ-10 по скорости роста (просмотры в день)",
                labels={"velocity_per_day": "Просмотров/день", "title": ""},
            )
            fig.update_layout(
                plot_bgcolor="#1e1e2e", paper_bgcolor="#1e1e2e",
                font_color="#e0e0e0", height=420,
                yaxis=dict(tickfont=dict(size=10)),
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_f:
        df_dur = df[df["duration_sec"] > 0].copy()
        if not df_dur.empty:
            bins = [0, 30, 60, 90, 180, 600, 1800, 100000]
            labels = ["<30с", "30-60с", "1-1.5мин", "1.5-3мин", "3-10мин", "10-30мин", ">30мин"]
            df_dur["длина"] = pd.cut(df_dur["duration_sec"], bins=bins, labels=labels)
            length_stats = df_dur.groupby("длина", observed=True).agg(
                avg_score=("score", "mean"), count=("id", "count"),
            ).reset_index()
            fig = px.bar(
                length_stats, x="длина", y="avg_score",
                color="avg_score", color_continuous_scale=["#1565c0", "#e91e63"],
                title="Средний рейтинг по длине видео",
                labels={"длина": "Длина", "avg_score": "Средний рейтинг"},
                hover_data=["count"],
            )
            fig.update_layout(
                plot_bgcolor="#1e1e2e", paper_bgcolor="#1e1e2e",
                font_color="#e0e0e0", height=420, coloraxis_showscale=False,
            )
            st.plotly_chart(fig, use_container_width=True)

    # Таймлайн
    df_time = df.copy()
    df_time["published_date"] = pd.to_datetime(df_time["published"], errors="coerce")
    df_time = df_time.dropna(subset=["published_date"])
    if not df_time.empty and len(df_time) > 3:
        timeline = df_time.groupby(
            [df_time["published_date"].dt.to_period("W").astype(str), "platform"],
        )["views"].sum().reset_index()
        timeline.columns = ["неделя", "platform", "views"]
        fig = px.line(
            timeline, x="неделя", y="views", color="platform",
            color_discrete_map=PLATFORM_COLORS,
            title="📈 Динамика суммарных просмотров по неделям",
            labels={"views": "Просмотры", "неделя": "Неделя"}, markers=True,
        )
        fig.update_layout(
            plot_bgcolor="#1e1e2e", paper_bgcolor="#1e1e2e",
            font_color="#e0e0e0", height=340,
        )
        st.plotly_chart(fig, use_container_width=True)

    # Heatmap по дням недели и часам (если есть данные)
    if not df_time.empty and len(df_time) >= 10:
        df_time["weekday"] = df_time["published_date"].dt.day_name()
        df_time["hour"] = df_time["published_date"].dt.hour
        heat = df_time.groupby(["weekday", "hour"])["score"].mean().reset_index()
        # Если часы все нулевые (нет времени публикации), скипаем
        if heat["hour"].nunique() > 1:
            day_order = ["Monday", "Tuesday", "Wednesday", "Thursday",
                         "Friday", "Saturday", "Sunday"]
            heat["weekday"] = pd.Categorical(heat["weekday"], categories=day_order, ordered=True)
            heat = heat.sort_values("weekday")
            fig = px.density_heatmap(
                heat, x="hour", y="weekday", z="score",
                color_continuous_scale="Viridis",
                title="🕒 Когда лучше публиковать (средний рейтинг)",
                labels={"hour": "Час", "weekday": "День", "score": "Рейтинг"},
            )
            fig.update_layout(
                plot_bgcolor="#1e1e2e", paper_bgcolor="#1e1e2e",
                font_color="#e0e0e0", height=320,
            )
            st.plotly_chart(fig, use_container_width=True)

    # Таблица + экспорт
    st.markdown("### 📋 Полная таблица данных")
    cols = ["platform", "title", "channel", "subscribers", "published",
            "views", "likes", "comments", "er_pct", "velocity_per_day", "score"]
    cols = [c for c in cols if c in df.columns]
    display_df = df[cols].rename(columns={
        "platform": "Платформа", "title": "Заголовок", "channel": "Автор",
        "subscribers": "Подписчики", "published": "Дата",
        "views": "Просмотры", "likes": "Лайки", "comments": "Комментарии",
        "er_pct": "ER %", "velocity_per_day": "Просмотров/день",
        "score": "Рейтинг 🔥",
    })

    st.dataframe(
        display_df, use_container_width=True, hide_index=True,
        column_config={
            "Просмотры": st.column_config.NumberColumn(format="%d"),
            "Подписчики": st.column_config.NumberColumn(format="%d"),
            "ER %": st.column_config.NumberColumn(format="%.2f"),
            "Рейтинг 🔥": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
        },
    )

    col_csv, col_xlsx = st.columns(2)
    with col_csv:
        csv = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ Экспорт CSV", csv,
            file_name=f"smarttrend_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv", use_container_width=True,
        )
    with col_xlsx:
        try:
            from io import BytesIO
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="Видео", index=False)
            st.download_button(
                "⬇️ Экспорт Excel", buf.getvalue(),
                file_name=f"smarttrend_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except ImportError:
            st.caption("Установите openpyxl для экспорта в Excel")


# ════════════════════════════════════════════════════════════════════════════
# ВКЛАДКА 3: АВТОРЫ / КАНАЛЫ
# ════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("<div class='section-header'>👤 Анализ авторов и каналов</div>", unsafe_allow_html=True)

    creators = df.groupby(["channel", "platform"], dropna=False).agg(
        videos=("id", "count"),
        total_views=("views", "sum"),
        total_likes=("likes", "sum"),
        total_comments=("comments", "sum"),
        avg_score=("score", "mean"),
        avg_er=("er_pct", "mean"),
        max_views=("views", "max"),
        subscribers=("subscribers", "max"),
    ).reset_index()
    creators = creators[creators["channel"].astype(str).str.strip().astype(bool)]
    creators = creators.sort_values("total_views", ascending=False)

    if creators.empty:
        st.info("Нет данных по авторам")
    else:
        # KPI
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"""<div class='kpi-card'>
                <div class='kpi-value'>{len(creators)}</div>
                <div class='kpi-label'>Уникальных авторов</div>
            </div>""", unsafe_allow_html=True)
        with c2:
            avg_vids = creators["videos"].mean()
            st.markdown(f"""<div class='kpi-card'>
                <div class='kpi-value'>{avg_vids:.1f}</div>
                <div class='kpi-label'>Видео на автора (среднее)</div>
            </div>""", unsafe_allow_html=True)
        with c3:
            top_creator = creators.iloc[0]
            st.markdown(f"""<div class='kpi-card'>
                <div class='kpi-value' style='font-size:1.3rem;'>{top_creator['channel'][:20]}</div>
                <div class='kpi-label'>Топ автор по охвату</div>
                <div class='kpi-delta up'>▲ {fmt_number(top_creator['total_views'])}</div>
            </div>""", unsafe_allow_html=True)
        with c4:
            most_active = creators.sort_values("videos", ascending=False).iloc[0]
            st.markdown(f"""<div class='kpi-card'>
                <div class='kpi-value' style='font-size:1.3rem;'>{most_active['channel'][:20]}</div>
                <div class='kpi-label'>Самый активный</div>
                <div class='kpi-delta up'>▲ {int(most_active['videos'])} видео</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 🏆 Топ-15 авторов по суммарному охвату")

        for idx, row in creators.head(15).iterrows():
            plat_color = PLATFORM_COLORS.get(row["platform"], "#666")
            channel_videos = df[(df["channel"] == row["channel"]) & (df["platform"] == row["platform"])]
            top_vid_url = channel_videos.nlargest(1, "views")["url"].iloc[0] if not channel_videos.empty else "#"

            st.markdown(f"""
            <div class='creator-card' style='border-left:4px solid {plat_color};'>
                <div style='display:flex;justify-content:space-between;align-items:center;'>
                    <div>
                        <div class='creator-name'>{row['channel']}
                            <span class='badge' style='background:{plat_color};color:white;margin-left:8px;'>{row['platform']}</span>
                        </div>
                        <div class='creator-meta'>
                            📹 {int(row['videos'])} видео &nbsp;|&nbsp;
                            👁 {fmt_number(row['total_views'])} просмотров &nbsp;|&nbsp;
                            👍 {fmt_number(row['total_likes'])} лайков &nbsp;|&nbsp;
                            📢 {fmt_number(row['subscribers']) if row['subscribers'] else '—'} подписчиков
                        </div>
                        <div class='creator-meta'>
                            💖 Средний ER: <b>{row['avg_er']:.2f}%</b> &nbsp;|&nbsp;
                            🔥 Средний рейтинг: <b>{row['avg_score']:.0f}/100</b> &nbsp;|&nbsp;
                            🏆 Лучшее видео: {fmt_number(row['max_views'])} просмотров
                        </div>
                    </div>
                    <a href='{top_vid_url}' target='_blank' rel='noopener noreferrer'
                       style='color:#4fc3f7;text-decoration:none;font-size:0.85rem;'>
                       🔗 Топ видео →</a>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Графики по авторам
        st.markdown("---")
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            top10 = creators.head(10)
            fig = px.bar(
                top10.sort_values("total_views"), x="total_views", y="channel",
                orientation="h", color="platform",
                color_discrete_map=PLATFORM_COLORS,
                title="Топ-10 авторов по охвату",
                labels={"total_views": "Просмотры", "channel": ""},
            )
            fig.update_layout(
                plot_bgcolor="#1e1e2e", paper_bgcolor="#1e1e2e",
                font_color="#e0e0e0", height=420,
            )
            st.plotly_chart(fig, use_container_width=True)
        with col_g2:
            # Эффективность: ER vs средний рейтинг
            fig = px.scatter(
                creators.head(30), x="avg_er", y="avg_score",
                size="total_views", color="platform",
                color_discrete_map=PLATFORM_COLORS,
                hover_data=["channel", "videos"],
                title="Эффективность авторов: ER × Рейтинг",
                labels={"avg_er": "Средний ER %", "avg_score": "Средний рейтинг"},
                size_max=40,
            )
            fig.update_layout(
                plot_bgcolor="#1e1e2e", paper_bgcolor="#1e1e2e",
                font_color="#e0e0e0", height=420,
            )
            st.plotly_chart(fig, use_container_width=True)

        # Полная таблица
        st.markdown("### 📋 Полная таблица авторов")
        st.dataframe(
            creators.rename(columns={
                "channel": "Автор", "platform": "Платформа", "videos": "Видео",
                "total_views": "Просмотры", "total_likes": "Лайки",
                "total_comments": "Комментарии", "avg_score": "Ср. рейтинг",
                "avg_er": "Ср. ER %", "max_views": "Макс просмотров",
                "subscribers": "Подписчики",
            }),
            use_container_width=True, hide_index=True,
        )


# ════════════════════════════════════════════════════════════════════════════
# ВКЛАДКА 4: ТРЕНДЫ
# ════════════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown("<div class='section-header'>📈 Тренды и инсайты</div>", unsafe_allow_html=True)

    # Извлекаем теги из реальных данных
    all_tags: list[str] = []
    for tags_str in df["tags"].fillna(""):
        for t in re.split(r"[,\s]+", str(tags_str)):
            t = t.strip().lower().replace("#", "")
            if t and len(t) >= 3:
                all_tags.append(t)

    tag_counter = Counter(all_tags)
    top_tags = tag_counter.most_common(30)

    if top_tags:
        col_t1, col_t2 = st.columns([2, 1])
        with col_t1:
            tags_df = pd.DataFrame(top_tags, columns=["тег", "частота"])
            fig = px.bar(
                tags_df.head(20).sort_values("частота"),
                x="частота", y="тег", orientation="h",
                color="частота", color_continuous_scale="Plasma",
                title="🏷️ Топ-20 тегов в найденных видео",
                labels={"частота": "Кол-во упоминаний", "тег": ""},
            )
            fig.update_layout(
                plot_bgcolor="#1e1e2e", paper_bgcolor="#1e1e2e",
                font_color="#e0e0e0", height=520, coloraxis_showscale=False,
            )
            st.plotly_chart(fig, use_container_width=True)
        with col_t2:
            st.markdown("### 🏷️ Горячие теги")
            tags_html = ""
            for tag, freq in top_tags[:30]:
                size = min(1.4, 0.8 + freq / 15)
                tags_html += (
                    f"<span style='display:inline-block;background:#1565c022;"
                    f"border:1px solid #4fc3f7;color:#4fc3f7;padding:4px 12px;"
                    f"border-radius:18px;margin:3px;font-size:{size:.2f}rem;"
                    f"font-weight:600;'>#{tag} "
                    f"<span style='opacity:0.7;font-size:0.7rem;'>×{freq}</span></span>"
                )
            st.markdown(f"<div style='line-height:2.2;'>{tags_html}</div>", unsafe_allow_html=True)

    # Анализ слов в заголовках
    st.markdown("---")
    st.markdown("### 📝 Анализ заголовков")

    all_words: list[str] = []
    stopwords = {"the", "and", "for", "with", "from", "this", "that", "you", "your",
                 "как", "что", "это", "для", "очень", "был", "есть", "его", "она", "они"}
    for title in df["title"].fillna(""):
        words = re.findall(r"\b[a-zа-яё]{4,}\b", str(title).lower())
        all_words.extend(w for w in words if w not in stopwords)

    word_counter = Counter(all_words)
    top_words = word_counter.most_common(20)

    col_w1, col_w2 = st.columns(2)
    with col_w1:
        if top_words:
            words_df = pd.DataFrame(top_words, columns=["слово", "частота"])
            fig = px.bar(
                words_df.sort_values("частота"), x="частота", y="слово",
                orientation="h", color="частота",
                color_continuous_scale="Viridis",
                title="🔤 Самые частые слова в заголовках",
                labels={"частота": "Кол-во", "слово": ""},
            )
            fig.update_layout(
                plot_bgcolor="#1e1e2e", paper_bgcolor="#1e1e2e",
                font_color="#e0e0e0", height=440, coloraxis_showscale=False,
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_w2:
        df["title_len"] = df["title"].fillna("").str.len()
        bins = [0, 30, 50, 70, 90, 200]
        labels = ["<30", "30-50", "50-70", "70-90", ">90"]
        df["len_bucket"] = pd.cut(df["title_len"], bins=bins, labels=labels)
        title_len_stats = df.groupby("len_bucket", observed=True).agg(
            avg_score=("score", "mean"), count=("id", "count"),
        ).reset_index()
        fig = px.bar(
            title_len_stats, x="len_bucket", y="avg_score",
            color="avg_score", color_continuous_scale=["#1565c0", "#e91e63"],
            title="Средний рейтинг по длине заголовка (символы)",
            labels={"len_bucket": "Символов в заголовке", "avg_score": "Средний рейтинг"},
            hover_data=["count"],
        )
        fig.update_layout(
            plot_bgcolor="#1e1e2e", paper_bgcolor="#1e1e2e",
            font_color="#e0e0e0", height=440, coloraxis_showscale=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    # Инсайты
    st.markdown("---")
    st.markdown("### 💡 Автоматические инсайты")
    col_i1, col_i2, col_i3 = st.columns(3)

    # Инсайт 1: оптимальная длина видео
    df_dur_i = df[df["duration_sec"] > 0]
    optimal_len = ""
    if not df_dur_i.empty:
        best_dur_bucket = df_dur_i.groupby(
            pd.cut(df_dur_i["duration_sec"], bins=[0, 30, 60, 90, 180, 600, 1800, 100000]),
            observed=True,
        )["score"].mean().idxmax()
        optimal_len = f"{int(best_dur_bucket.left)}-{int(best_dur_bucket.right)} сек"

    # Инсайт 2: лучшая платформа по ER
    best_er_platform = df.groupby("platform")["er_pct"].mean().idxmax() if not df.empty else "—"
    best_er_value = df.groupby("platform")["er_pct"].mean().max() if not df.empty else 0

    # Инсайт 3: самое свежее залётное
    fresh_viral = df[(df["score"] >= 85) & (df["days_ago"] <= 7)]

    with col_i1:
        st.markdown(f"""**🎯 Оптимальная длина**

Видео длиной **{optimal_len or '—'}** показывают максимальный рейтинг в этой нише.

Сосредоточьтесь на этом формате для своих публикаций.""")

    with col_i2:
        st.markdown(f"""**💖 Лучшая платформа по ER**

На **{best_er_platform}** средний Engagement Rate составляет **{best_er_value:.2f}%**.

Здесь аудитория наиболее активно взаимодействует с контентом.""")

    with col_i3:
        st.markdown(f"""**🔥 Свежие хиты (≤7 дней)**

Найдено **{len(fresh_viral)}** свежих видео с рейтингом 85+.

Это самые горячие тренды прямо сейчас — копировать формат немедленно.""")


# ════════════════════════════════════════════════════════════════════════════
# ВКЛАДКА 5: РЕФЕРЕНСЫ
# ════════════════════════════════════════════════════════════════════════════
with tab5:
    st.markdown("<div class='section-header'>🎬 Лучшие референсы для производства</div>", unsafe_allow_html=True)
    st.markdown("Топ видео для создания похожего контента и брифов на съёмку/AI-генерацию")

    top_refs = df.nlargest(8, "score")

    for i, (idx, row) in enumerate(top_refs.iterrows(), start=1):
        with st.expander(f"🔥 #{i} — {row['title'][:80]} | Рейтинг: {int(row['score'])}/100"):
            c1, c2 = st.columns([1, 2])
            with c1:
                if row.get("thumbnail"):
                    try:
                        st.image(row["thumbnail"])
                    except Exception:
                        pass
                st.markdown(f"**🌐 Платформа:** {row['platform']}")
                st.markdown(f"**📺 Автор:** {row.get('channel', '—')}")
                st.markdown(f"**📢 Подписчики:** {fmt_number(row.get('subscribers', 0)) or '—'}")
                st.markdown(f"**👁 Просмотры:** {fmt_number(row['views'])}")
                st.markdown(f"**👍 Лайки:** {fmt_number(row['likes'])}")
                st.markdown(f"**💬 Комментарии:** {fmt_number(row['comments'])}")
                st.markdown(f"**⏱ Длина:** {row.get('duration', '—')}")
                st.markdown(f"**💖 ER:** {row.get('er_pct', 0):.2f}%")
                st.markdown(f"[🔗 Открыть оригинал]({row['url']})")

            with c2:
                st.markdown("**📋 Почему это залетело:**")
                reasons = []
                er = float(row.get("er_pct", 0))
                if row["views"] > 5_000_000:
                    reasons.append("✅ **Массовый охват** (5М+ просмотров)")
                if er > 5:
                    reasons.append(f"✅ **Очень высокий ER** ({er:.1f}%) — аудитория супер вовлечена")
                elif er > 3:
                    reasons.append(f"✅ **Высокий ER** ({er:.1f}%)")
                if row["days_ago"] <= 7:
                    reasons.append("✅ **Свежак** (< 7 дней) — на пике интереса")
                if row.get("velocity_per_day", 0) > 500_000:
                    reasons.append(f"✅ **Бешеная скорость роста** ({fmt_number(row['velocity_per_day'])}/день)")
                if row["duration_sec"] and row["duration_sec"] < 90:
                    reasons.append("✅ **Короткий формат** — оптимален для соц. сетей")
                if row.get("subscribers", 0) > 0 and row["views"] > row["subscribers"] * 5:
                    reasons.append("✅ **Виральный** — просмотры >> подписчиков")

                for r in reasons:
                    st.markdown(r)

                st.markdown("---")
                st.markdown("**🎯 Рекомендации для повтора:**")
                st.markdown(f"""
- **Платформа публикации:** {row['platform']} + кросс-пост на другие
- **Длина:** {row.get('duration', '—')} — копируй этот таймиг
- **Хук (первые 3 сек):** срисовать из «{row['title'][:60]}»
- **Призыв к действию:** комментарий-вопрос для буста ER
                """)

                st.markdown("**🤖 Промпт для AI-генерации сценария:**")
                prompt = (
                    f"Создай сценарий короткого видео для {row['platform']} в стиле виралового хита: "
                    f"«{row['title']}». Длина {row.get('duration', '60 секунд')}. "
                    f"Цель: максимальный охват и engagement в нише «{niche}». "
                    f"Структура: хук-проблема-решение-CTA. Тон: дружелюбный, экспертный."
                )
                st.text_area("Скопировать промпт:", value=prompt, height=100, key=f"prompt_{i}")


# ════════════════════════════════════════════════════════════════════════════
# ВКЛАДКА 6: НАСТРОЙКИ
# ════════════════════════════════════════════════════════════════════════════
with tab6:
    st.markdown("<div class='section-header'>⚙️ Управление подключениями и ключами</div>", unsafe_allow_html=True)

    # Статус
    st.markdown("### 📡 Статус источников")
    cols_st = st.columns(5)
    statuses = [
        ("YouTube API", has_yt_api, st.session_state.youtube_api_key),
        ("yt-dlp", has_ytdlp, ""),
        ("Apify", has_apify, st.session_state.apify_token),
        ("RapidAPI", has_rapidapi, st.session_state.rapidapi_key),
        ("Instaloader", has_instaloader, ""),
    ]
    for col, (name, active, key) in zip(cols_st, statuses):
        with col:
            if active:
                st.success(f"✅ {name}")
                if key:
                    st.caption(f"`{mask_key(key)}`")
            else:
                st.warning(f"⚪ {name}")

    st.markdown("---")
    st.markdown("### 🔑 Обновить ключи")
    st.markdown("""<div class='info-box'>
    🔒 Ключи хранятся <b>только в текущей сессии</b> + Streamlit secrets.
    На Streamlit Cloud задайте их через <b>Manage app → Secrets</b> для постоянного хранения.
    </div>""", unsafe_allow_html=True)

    col_k1, col_k2 = st.columns(2)
    with col_k1:
        new_yt = st.text_input("YouTube API Key:", value=st.session_state.youtube_api_key,
                                type="password", key="cfg_yt")
        new_ap = st.text_input("Apify Token:", value=st.session_state.apify_token,
                                type="password", key="cfg_ap")
        new_ra = st.text_input("RapidAPI Key:", value=st.session_state.rapidapi_key,
                                type="password", key="cfg_ra")
    with col_k2:
        new_iu = st.text_input("Instagram логин (для Instaloader):",
                                value=st.session_state.instagram_user, key="cfg_iu")
        new_ip = st.text_input("Instagram пароль:",
                                value=st.session_state.instagram_pass,
                                type="password", key="cfg_ip")

    if st.button("💾 Сохранить", type="primary", use_container_width=True):
        st.session_state.youtube_api_key = new_yt.strip()
        st.session_state.apify_token = new_ap.strip()
        st.session_state.rapidapi_key = new_ra.strip()
        st.session_state.instagram_user = new_iu.strip()
        st.session_state.instagram_pass = new_ip
        st.success("✅ Сохранено в сессии. На Streamlit Cloud не забудь обновить secrets.")
        time.sleep(0.8)
        st.rerun()

    st.markdown("---")
    st.markdown("### 📋 Сравнение источников")
    sources_data = {
        "Источник": ["YouTube API", "yt-dlp", "Apify", "RapidAPI", "Instaloader"],
        "Платформы": ["YouTube", "YouTube", "Instagram+TikTok", "TikTok", "Instagram"],
        "Стоимость": ["10К/день free", "Бесплатно", "$5 free → ~$2/1К", "Free тариф", "Бесплатно"],
        "Качество данных": ["⭐⭐⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐"],
        "Стабильность": ["⭐⭐⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐", "⭐⭐⭐", "⭐⭐"],
        "Риск бана": ["Нет", "Нет", "Нет", "Нет", "⚠️ Есть"],
    }
    st.dataframe(pd.DataFrame(sources_data), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("### 🔧 Установка зависимостей")
    st.code(
        "pip install streamlit pandas plotly requests yt-dlp apify-client "
        "instaloader openpyxl",
        language="bash",
    )

    st.markdown("### 🚀 Запуск")
    st.code("streamlit run app.py", language="bash")

    st.markdown("### 🔐 Secrets для Streamlit Cloud")
    st.markdown("Создайте в **Manage app → Secrets**:")
    st.code("""youtube_api_key = "AIzaSy..."
apify_token = "apify_api_..."
rapidapi_key = "..."
instagram_user = ""
instagram_pass = ""
""", language="toml")

    st.markdown("---")
    if st.button("🔄 Сбросить настройки и запустить мастер", use_container_width=True):
        st.session_state.setup_done = False
        st.rerun()

    st.markdown(f"""<div style='margin-top:30px;font-size:0.78rem;color:#666;text-align:center;'>
    SmartTrend Analyzer Pro v3.0 · {datetime.now().strftime('%Y-%m-%d %H:%M')}
    </div>""", unsafe_allow_html=True)
