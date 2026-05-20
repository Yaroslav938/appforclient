"""
📱 SmartTrend Analyzer v2.2
Анализ трендовых видео по теме ремонта и продажи смартфонов
YouTube | Instagram | TikTok
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import json
import time
import re
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ─────────────────────────────────────────────
# КОНФИГУРАЦИЯ СТРАНИЦЫ
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="SmartTrend Analyzer",
    page_icon="📱",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# СТИЛИ
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

section[data-testid="stSidebar"] { background: #0f0f0f; border-right: 1px solid #2a2a2a; }
section[data-testid="stSidebar"] * { color: #e0e0e0 !important; }

.kpi-card {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border: 1px solid #2a2a4a; border-radius: 12px;
    padding: 20px; text-align: center; transition: transform 0.2s;
}
.kpi-card:hover { transform: translateY(-2px); }
.kpi-value { font-size: 2rem; font-weight: 700; color: #4fc3f7; }
.kpi-label { font-size: 0.85rem; color: #9e9e9e; margin-top: 4px; }
.kpi-delta { font-size: 0.8rem; margin-top: 6px; }
.kpi-delta.up { color: #66bb6a; }
.kpi-delta.down { color: #ef5350; }

.video-card {
    background: #1e1e2e; border: 1px solid #2a2a3e;
    border-radius: 10px; padding: 14px; margin-bottom: 12px; transition: border-color 0.2s;
}
.video-card:hover { border-color: #4fc3f7; }
.video-title { font-size: 0.95rem; font-weight: 600; color: #e0e0e0; }
.video-meta { font-size: 0.8rem; color: #9e9e9e; margin-top: 6px; }
.video-stats { font-size: 0.85rem; color: #4fc3f7; margin-top: 8px; }

.badge {
    display: inline-block; padding: 2px 10px; border-radius: 20px;
    font-size: 0.72rem; font-weight: 600; margin-right: 4px;
}
.badge-yt { background: #c62828; color: white; }
.badge-ig { background: #6a1b9a; color: white; }
.badge-tt { background: #00796b; color: white; }
.badge-hot { background: #e65100; color: white; }
.badge-trending { background: #1565c0; color: white; }
.badge-free { background: #2e7d32; color: white; }

.score-bar-wrap { background: #2a2a3e; border-radius: 4px; height: 6px; margin-top: 8px; }
.score-bar-fill { height: 6px; border-radius: 4px; background: linear-gradient(90deg, #4fc3f7, #9c27b0); }

.section-header {
    font-size: 1.3rem; font-weight: 700; color: #e0e0e0;
    border-bottom: 2px solid #4fc3f7; padding-bottom: 8px; margin-bottom: 16px;
}

.api-info {
    background: #1a2744; border-left: 4px solid #4fc3f7;
    padding: 12px 16px; border-radius: 0 8px 8px 0;
    margin: 8px 0; font-size: 0.85rem; color: #cfd8dc;
}
.free-info {
    background: #1a2e1a; border-left: 4px solid #66bb6a;
    padding: 12px 16px; border-radius: 0 8px 8px 0;
    margin: 8px 0; font-size: 0.85rem; color: #c8e6c9;
}

.demo-banner {
    background: linear-gradient(90deg, #1a237e, #4a148c);
    color: #e8eaf6; padding: 10px 16px; border-radius: 8px;
    font-size: 0.88rem; margin-bottom: 12px; border: 1px solid #3949ab;
}
.setup-step {
    background: #1a1a2e; border: 1px solid #2a2a4a; border-radius: 10px;
    padding: 16px; margin-bottom: 12px;
}
.setup-step-num {
    display: inline-block; background: #4fc3f7; color: #000;
    border-radius: 50%; width: 28px; height: 28px;
    text-align: center; line-height: 28px; font-weight: 700;
    font-size: 0.9rem; margin-right: 8px;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# УПРАВЛЕНИЕ КЛЮЧАМИ — совместимо со Streamlit Cloud
# ─────────────────────────────────────────────

def load_saved_keys():
    """Загружает ключи: сначала из st.secrets (Streamlit Cloud), потом из session_state"""
    keys = {"youtube_api_key": "", "apify_token": ""}
    # Streamlit Cloud: ключи задаются через Manage app → Secrets
    try:
        keys["youtube_api_key"] = st.secrets.get("youtube_api_key", "")
        keys["apify_token"] = st.secrets.get("apify_token", "")
    except Exception:
        pass
    # Локальный запуск: берём из переменных окружения
    if not keys["youtube_api_key"]:
        keys["youtube_api_key"] = os.environ.get("YOUTUBE_API_KEY", "")
    if not keys["apify_token"]:
        keys["apify_token"] = os.environ.get("APIFY_TOKEN", "")
    return keys

def save_keys(yt_key, apify_key):
    """На Cloud — только session_state. Локально — пробуем записать secrets.toml."""
    st.session_state.yt_key = yt_key
    st.session_state.apify_key = apify_key
    # Пробуем записать файл только локально
    try:
        from pathlib import Path
        secrets_dir = Path(".streamlit")
        secrets_file = secrets_dir / "secrets.toml"
        secrets_dir.mkdir(exist_ok=True)
        secrets_file.write_text(
            f'youtube_api_key = "{yt_key}"\napify_token = "{apify_key}"\n'
        )
    except OSError:
        pass  # Streamlit Cloud — файловая система read-only, это нормально

def check_ytdlp():
    """Проверить наличие yt-dlp"""
    try:
        import yt_dlp
        return True
    except ImportError:
        return False

def install_ytdlp():
    """Установить yt-dlp"""
    subprocess.check_call([sys.executable, "-m", "pip", "install", "yt-dlp", "-q"])


# ─────────────────────────────────────────────
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ─────────────────────────────────────────────
def fmt_number(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}М"
    elif n >= 1_000:
        return f"{n/1_000:.1f}К"
    return str(int(n))

def score_video(views, likes, comments, days_ago):
    # Добавлена защита от накрутки Engagement Rate на свежих/пустых видео
    if views < 100:
        return 0
        
    engagement_rate = (likes + comments * 3) / max(views, 1)
    recency = max(0, 1 - days_ago / 90)
    velocity = views / max(days_ago, 1)
    score = (
        min(views / 5_000_000 * 30, 30) +
        min(engagement_rate * 2000, 30) +
        recency * 20 +
        min(velocity / 50_000 * 20, 20)
    )
    return min(round(score), 100)

def parse_duration(iso):
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso or "")
    if not m:
        return 0
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s

def duration_fmt(secs):
    secs = int(secs or 0)
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


# ─────────────────────────────────────────────
# ИСТОЧНИК 1: yt-dlp (БЕСПЛАТНО, без API-ключа)
# ─────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def search_ytdlp(query, fetch_limit=50):
    """Поиск YouTube через yt-dlp — парсим больше, чтобы потом отфильтровать лучшие"""
    try:
        import yt_dlp
    except ImportError:
        return []

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "playlist_items": f"1:{fetch_limit}",
    }
    search_url = f"ytsearch{fetch_limit}:{query}"
    rows = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_url, download=False)
            entries = info.get("entries", []) if info else []
            for e in entries:
                if not e:
                    continue
                vid_id = e.get("id", "")
                upload_date = e.get("upload_date", "")
                try:
                    pub_dt = datetime.strptime(upload_date, "%Y%m%d")
                    days_ago = (datetime.now() - pub_dt).days
                    published = pub_dt.strftime("%Y-%m-%d")
                except:
                    days_ago = 30
                    published = ""

                views = int(e.get("view_count") or 0)
                likes = int(e.get("like_count") or 0)
                comments = int(e.get("comment_count") or 0)
                duration_sec = int(e.get("duration") or 0)

                rows.append({
                    "platform": "YouTube",
                    "id": vid_id,
                    "title": (e.get("title") or "")[:80],
                    "channel": e.get("uploader") or e.get("channel") or "",
                    "published": published,
                    "days_ago": days_ago,
                    "views": views,
                    "likes": likes,
                    "comments": comments,
                    "duration_sec": duration_sec,
                    "duration": duration_fmt(duration_sec),
                    "thumbnail": e.get("thumbnail") or f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg",
                    "url": f"https://www.youtube.com/watch?v={vid_id}",
                    "description": (e.get("description") or "")[:200],
                    "tags": ", ".join((e.get("tags") or [])[:8]),
                    "score": score_video(views, likes, comments, days_ago),
                })
    except Exception as e:
        st.warning(f"yt-dlp: {e}")
    return rows


# ─────────────────────────────────────────────
# ИСТОЧНИК 2: YouTube Data API v3
# ─────────────────────────────────────────────
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"

@st.cache_data(ttl=300, show_spinner=False)
def search_yt_api(api_key, query, fetch_limit=50, region="US", days=90):
    published_after = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    actual_limit = min(fetch_limit, 50)
    params = {
        "part": "snippet", "q": query, "type": "video",
        "maxResults": actual_limit, "order": "viewCount",
        "regionCode": region, "publishedAfter": published_after,
        "key": api_key,
    }
    try:
        r = requests.get(f"{YOUTUBE_API_BASE}/search", params=params, timeout=10)
        r.raise_for_status()
        items = r.json().get("items", [])
    except Exception as e:
        st.error(f"YouTube API: {e}")
        return []

    video_ids = [i.get("id", {}).get("videoId") for i in items if i.get("id", {}).get("videoId")]
    if not video_ids:
        return []

    stats_resp = requests.get(f"{YOUTUBE_API_BASE}/videos", params={
        "part": "statistics,contentDetails,snippet",
        "id": ",".join(video_ids), "key": api_key,
    }, timeout=10).json()
    stats_dict = {s["id"]: s for s in stats_resp.get("items", [])}

    rows = []
    for item in items:
        vid_id = item.get("id", {}).get("videoId")
        if not vid_id:
            continue
        snip = item.get("snippet", {})
        stat = stats_dict.get(vid_id, {})
        sd = stat.get("statistics", {})
        cd = stat.get("contentDetails", {})
        published = snip.get("publishedAt", "")
        try:
            pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
            days_ago = (datetime.now(pub_dt.tzinfo) - pub_dt).days
        except:
            days_ago = 30
        views = int(sd.get("viewCount", 0))
        likes = int(sd.get("likeCount", 0))
        comments = int(sd.get("commentCount", 0))
        dur_sec = parse_duration(cd.get("duration", ""))
        rows.append({
            "platform": "YouTube",
            "id": vid_id,
            "title": snip.get("title", "")[:80],
            "channel": snip.get("channelTitle", ""),
            "published": published[:10],
            "days_ago": days_ago,
            "views": views, "likes": likes, "comments": comments,
            "duration_sec": dur_sec, "duration": duration_fmt(dur_sec),
            "thumbnail": snip.get("thumbnails", {}).get("high", {}).get("url", ""),
            "url": f"https://www.youtube.com/watch?v={vid_id}",
            "description": snip.get("description", "")[:200],
            "tags": ", ".join(stat.get("snippet", {}).get("tags", [])[:8]),
            "score": score_video(views, likes, comments, days_ago),
        })
    return rows


# ─────────────────────────────────────────────
# ДЕМО-ДАННЫЕ
# ─────────────────────────────────────────────
DEMO_VIDEOS = [
    {"platform":"YouTube","id":"dQw4w9WgXcQ","title":"Замена экрана iPhone 15 Pro Max — полное руководство 2024","channel":"PhoneFixer Pro","published":"2024-11-05","days_ago":14,"views":4_823_000,"likes":95_400,"comments":3_200,"duration":"18:42","score":91,"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","thumbnail":"https://picsum.photos/seed/iphone15/320/180","tags":"iphone,ремонт,замена экрана","description":"Полное руководство по замене экрана iPhone 15 Pro Max дома."},
    {"platform":"YouTube","id":"abc12345","title":"Замена аккумулятора Samsung Galaxy S24 за 10 минут","channel":"QuickFix Mobile","published":"2024-11-10","days_ago":9,"views":2_190_000,"likes":58_700,"comments":1_890,"duration":"9:55","score":87,"url":"https://www.youtube.com/watch?v=abc12345","thumbnail":"https://picsum.photos/seed/samsung24/320/180","tags":"samsung,аккумулятор,ремонт","description":"Быстрая замена аккумулятора Samsung S24."},
    {"platform":"YouTube","id":"def67890","title":"ХВАТИТ платить за ремонт телефона! Сделай это сам","channel":"ЭкономТех","published":"2024-10-28","days_ago":22,"views":7_540_000,"likes":212_000,"comments":9_800,"duration":"14:20","score":96,"url":"https://www.youtube.com/watch?v=def67890","thumbnail":"https://picsum.photos/seed/stoprepairing/320/180","tags":"самостоятельный ремонт,смартфон","description":"Топ-5 ремонтов смартфона, которые ты можешь сделать сам."},
    {"platform":"Instagram","id":"ig_001","title":"Лайфхак по ремонту телефона — экономит 15 000 руб 💸","channel":"@mobilefixmaster","published":"2024-11-14","days_ago":5,"views":8_200_000,"likes":430_000,"comments":12_400,"duration":"0:55","score":98,"url":"https://www.instagram.com/p/ig_001/","thumbnail":"https://picsum.photos/seed/ighack/320/180","tags":"#ремонттелефона,#лайфхак","description":"Этот ОДИН трюк сэкономит тебе 15 000 рублей в сервисном центре."},
    {"platform":"TikTok","id":"tt_001","title":"Уронил iPhone и ПОЧИНИЛ его за 800 рублей 🤯","channel":"@techsaverz","published":"2024-11-13","days_ago":6,"views":15_700_000,"likes":1_200_000,"comments":28_000,"duration":"0:45","score":99,"url":"https://www.tiktok.com/@techsaverz/video/tt_001","thumbnail":"https://picsum.photos/seed/ttiphone/320/180","tags":"#iphone,#ремонттелефона,#лайфхак","description":"Разбил экран и починил всего за 800 рублей."},
    {"platform":"TikTok","id":"tt_002","title":"День из жизни мастера по ремонту телефонов 📱","channel":"@fixitfast_phones","published":"2024-11-08","days_ago":11,"views":6_340_000,"likes":485_000,"comments":14_200,"duration":"1:05","score":93,"url":"https://www.tiktok.com/@fixitfast_phones/video/tt_002","thumbnail":"https://picsum.photos/seed/dayinlife/320/180","tags":"#ремонттелефонов,#деньизжизни","description":"За кулисами моего сервисного центра."},
    {"platform":"YouTube","id":"ghi11122","title":"Лучшие бюджетные смартфоны 2024 — топ-10 до 25 000 рублей","channel":"ТехОбзор","published":"2024-11-01","days_ago":18,"views":3_280_000,"likes":87_600,"comments":4_200,"duration":"22:15","score":89,"url":"https://www.youtube.com/watch?v=ghi11122","thumbnail":"https://picsum.photos/seed/budget2024/320/180","tags":"бюджетный телефон,обзор,до 25000","description":"Лучшие бюджетные телефоны прямо сейчас."},
    {"platform":"Instagram","id":"ig_002","title":"До и После восстановления телефона 😮 #реставрация","channel":"@restore_tech","published":"2024-11-12","days_ago":7,"views":4_100_000,"likes":310_000,"comments":7_800,"duration":"0:38","score":94,"url":"https://www.instagram.com/p/ig_002/","thumbnail":"https://picsum.photos/seed/beforeafter/320/180","tags":"#реставрация,#ремонт","description":"Превращаем уничтоженный Samsung в состояние «как новый»."},
    {"platform":"YouTube","id":"jkl33344","title":"iPhone vs Samsung — что ломается быстрее? Тест на падение 2024","channel":"ТехДроп","published":"2024-10-25","days_ago":25,"views":9_150_000,"likes":198_000,"comments":15_600,"duration":"11:08","score":95,"url":"https://www.youtube.com/watch?v=jkl33344","thumbnail":"https://picsum.photos/seed/droptest/320/180","tags":"тест на падение,iphone vs samsung","description":"100 тестов на падение iPhone 15 Pro и Samsung S24 Ultra."},
    {"platform":"TikTok","id":"tt_003","title":"POV: клиент принёс iPhone с водой 💧","channel":"@phonerepairking","published":"2024-11-11","days_ago":8,"views":11_200_000,"likes":890_000,"comments":22_000,"duration":"0:52","score":97,"url":"https://www.tiktok.com/@phonerepairking/video/tt_003","thumbnail":"https://picsum.photos/seed/waterdamage/320/180","tags":"#ремонттелефона,#водяноеповреждение","description":"POV-серия — самые удовлетворяющие ремонты."},
    {"platform":"YouTube","id":"mno55566","title":"Xiaomi 14 Ultra — полный обзор. Лучшая камера 2024?","channel":"МобильныйГид","published":"2024-10-30","days_ago":20,"views":5_670_000,"likes":143_000,"comments":8_900,"duration":"19:44","score":90,"url":"https://www.youtube.com/watch?v=mno55566","thumbnail":"https://picsum.photos/seed/xiaomi14/320/180","tags":"xiaomi,обзор,камера","description":"Xiaomi 14 Ultra — лучший камерофон?"},
    {"platform":"Instagram","id":"ig_003","title":"5 признаков, что телефон нужно нести в ремонт ⚠️","channel":"@phone_expert_ru","published":"2024-11-06","days_ago":13,"views":3_750_000,"likes":195_000,"comments":5_600,"duration":"1:10","score":88,"url":"https://www.instagram.com/p/ig_003/","thumbnail":"https://picsum.photos/seed/phonewarning/320/180","tags":"#советы,#ремонттелефона","description":"Когда точно пора в сервис? 5 чётких признаков."},
]

DEMO_TRENDS = [
    {"tag":"#ремонттелефона","platform":"Instagram","videos":4200,"growth":"+187%"},
    {"tag":"#iphonerepair","platform":"YouTube","videos":8900,"growth":"+143%"},
    {"tag":"#phonerestoration","platform":"TikTok","videos":6700,"growth":"+221%"},
    {"tag":"#самостоятельный ремонт","platform":"YouTube","videos":3100,"growth":"+98%"},
    {"tag":"#до и после реставрация","platform":"Instagram","videos":5500,"growth":"+312%"},
    {"tag":"#POV сервисный центр","platform":"TikTok","videos":9200,"growth":"+276%"},
    {"tag":"#замена экрана","platform":"YouTube","videos":2800,"growth":"+67%"},
    {"tag":"#waterdamage repair","platform":"TikTok","videos":7100,"growth":"+189%"},
    {"tag":"#бюджетный смартфон","platform":"YouTube","videos":4600,"growth":"+134%"},
    {"tag":"#satisfying repair","platform":"TikTok","videos":12300,"growth":"+345%"},
]


# ─────────────────────────────────────────────
# ЗАГРУЗКА СОХРАНЁННЫХ КЛЮЧЕЙ
# ─────────────────────────────────────────────
saved = load_saved_keys()

# Инициализируем session state
if "yt_key" not in st.session_state:
    st.session_state.yt_key = saved.get("youtube_api_key", "")
if "apify_key" not in st.session_state:
    st.session_state.apify_key = saved.get("apify_token", "")
if "setup_done" not in st.session_state:
    st.session_state.setup_done = bool(saved.get("youtube_api_key") or saved.get("apify_token"))
if "ytdlp_installed" not in st.session_state:
    st.session_state.ytdlp_installed = check_ytdlp()


# ─────────────────────────────────────────────
# МАСТЕР ПЕРВОГО ЗАПУСКА
# ─────────────────────────────────────────────
def show_setup_wizard():
    st.markdown("# 📱 SmartTrend Analyzer")
    st.markdown("## 🚀 Мастер первого запуска")
    st.markdown("Настрой приложение за 2 минуты и начни анализировать тренды. Выбери один из режимов:")

    mode = st.radio(
        "Выбери режим работы:",
        [
            "🆓 Полностью бесплатно — через yt-dlp (YouTube без API-ключа)",
            "🔑 Расширенный — YouTube API + yt-dlp (больше данных)",
            "⚡ Полный — YouTube API + Instagram + TikTok через Apify",
            "🎮 Демо-режим — посмотреть на примерах без настройки",
        ],
        index=0,
    )

    if "бесплатно" in mode:
        st.markdown("""
        <div class='free-info'>
        ✅ <b>Не нужен ни один API-ключ</b> — yt-dlp напрямую обходит YouTube<br>
        ✅ Полностью бесплатно, без лимитов запросов<br>
        ✅ Получает: заголовок, просмотры, лайки, длину, дату, обложку<br>
        ⚠️ Только YouTube. Без Instagram и TikTok.
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("📦 Установить yt-dlp и начать", type="primary", use_container_width=True):
                with st.spinner("Устанавливаем yt-dlp..."):
                    try:
                        install_ytdlp()
                        st.session_state.ytdlp_installed = True
                        st.session_state.setup_done = True
                        save_keys("", "")
                        st.success("✅ yt-dlp установлен! Перезагружаем...")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Ошибка установки: {e}\n\nЗапусти вручную: pip install yt-dlp")
        with col2:
            if check_ytdlp():
                st.info("✅ yt-dlp уже установлен")
                if st.button("Начать работу →", use_container_width=True):
                    st.session_state.setup_done = True
                    st.rerun()
            else:
                st.code("pip install yt-dlp", language="bash")

    elif "Расширенный" in mode:
        st.markdown("""
        <div class='api-info'>
        🔑 <b>YouTube Data API v3</b> — даёт точную статистику (комментарии, теги, разрешение обложки)<br>
        ✅ 10 000 запросов/день бесплатно — этого хватает на ~100 поисков<br>
        ✅ Регистрация займёт 5 минут, карта не нужна
        </div>
        """, unsafe_allow_html=True)

        st.markdown("### Шаг 1 — Получи YouTube API ключ")

        with st.expander("📋 Пошаговая инструкция (нажми чтобы раскрыть)", expanded=True):
            st.markdown("""
            <div class='setup-step'>
            <span class='setup-step-num'>1</span> Перейди по ссылке ниже → войди в Google-аккаунт
            </div>
            <div class='setup-step'>
            <span class='setup-step-num'>2</span> Нажми <b>"Select a project"</b> вверху → <b>"New Project"</b> → придумай название → <b>Create</b>
            </div>
            <div class='setup-step'>
            <span class='setup-step-num'>3</span> В строке поиска вверху введи <code>YouTube Data API v3</code> → кликни на результат → нажми <b>Enable</b>
            </div>
            <div class='setup-step'>
            <span class='setup-step-num'>4</span> Слева: <b>APIs & Services → Credentials → + CREATE CREDENTIALS → API key</b>
            </div>
            <div class='setup-step'>
            <span class='setup-step-num'>5</span> Скопируй ключ вида <code>AIzaSy...</code> и вставь ниже
            </div>
            """, unsafe_allow_html=True)

            st.link_button("🌐 Открыть Google Cloud Console →", "https://console.cloud.google.com", use_container_width=True)

        yt_key_input = st.text_input(
            "Вставь YouTube API ключ:",
            value=st.session_state.yt_key,
            type="password",
            placeholder="AIzaSy...",
        )

        if yt_key_input:
            if st.button("✅ Проверить и сохранить ключ", type="primary", use_container_width=True):
                with st.spinner("Проверяем ключ..."):
                    params = {"part":"snippet","q":"test","type":"video","maxResults":1,"key":yt_key_input}
                    try:
                        r = requests.get(f"{YOUTUBE_API_BASE}/search", params=params, timeout=8)
                        if r.status_code == 200:
                            st.success("✅ Ключ работает!")
                            st.session_state.yt_key = yt_key_input
                            save_keys(yt_key_input, st.session_state.apify_key)
                            st.session_state.setup_done = True
                            if not check_ytdlp():
                                install_ytdlp()
                                st.session_state.ytdlp_installed = True
                            st.rerun()
                        elif r.status_code == 403:
                            err = r.json().get("error", {}).get("message", "")
                            if "accessNotConfigured" in err:
                                st.error("❌ YouTube Data API v3 не включён. Вернись к шагу 3.")
                            else:
                                st.error(f"❌ Отказ доступа: {err}")
                        else:
                            st.error(f"❌ Ошибка {r.status_code}")
                    except Exception as e:
                        st.error(f"❌ Ошибка соединения: {e}")

    elif "Полный" in mode:
        st.markdown("""
        <div class='api-info'>
        🔑 <b>YouTube API</b> + <b>Apify</b> (Instagram + TikTok) — максимальный охват всех платформ<br>
        💰 Apify: бесплатный стартовый кредит $5, затем ~$1.90 за 1000 постов
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**YouTube API ключ**")
            st.link_button("Открыть Google Cloud →", "https://console.cloud.google.com")
            yt_key_input = st.text_input("YouTube API ключ:", value=st.session_state.yt_key, type="password", placeholder="AIzaSy...", key="wiz_yt")
        with col2:
            st.markdown("**Apify Token (Instagram + TikTok)**")
            st.link_button("Открыть Apify →", "https://console.apify.com/account/integrations")
            apify_key_input = st.text_input("Apify Token:", value=st.session_state.apify_key, type="password", placeholder="apify_api_...", key="wiz_ap")

        if st.button("💾 Сохранить оба ключа и начать", type="primary", use_container_width=True):
            save_keys(yt_key_input or "", apify_key_input or "")
            st.session_state.yt_key = yt_key_input or ""
            st.session_state.apify_key = apify_key_input or ""
            st.session_state.setup_done = True
            st.success("✅ Ключи сохранены!")
            st.rerun()

    else:  # Демо
        st.info("🎮 Демо-режим: показываем примеры трендовых видео без реального поиска")
        if st.button("Войти в демо-режим →", type="primary", use_container_width=True):
            st.session_state.setup_done = True
            st.rerun()

    st.markdown("---")
    st.markdown("*Ключи сохраняются в `.streamlit/secrets.toml` — не нужно вводить каждый раз при запуске.*")


# ─────────────────────────────────────────────
# ПОКАЗЫВАЕМ МАСТЕР ПРИ ПЕРВОМ ЗАПУСКЕ
# ─────────────────────────────────────────────
if not st.session_state.setup_done:
    show_setup_wizard()
    st.stop()


# ─────────────────────────────────────────────
# БОКОВАЯ ПАНЕЛЬ (после настройки)
# ─────────────────────────────────────────────
yt_api_key = st.session_state.yt_key
apify_token = st.session_state.apify_key
ytdlp_ok = st.session_state.ytdlp_installed or check_ytdlp()

# Определяем доступные режимы
has_yt_api = bool(yt_api_key)
has_apify = bool(apify_token)
has_ytdlp = ytdlp_ok

with st.sidebar:
    st.markdown("## 📱 SmartTrend Analyzer")
    st.markdown("*Анализ трендовых видео*")
    st.markdown("---")

    # Статус подключений
    st.markdown("### 📡 Источники данных")
    if has_ytdlp:
        st.markdown("🟢 **yt-dlp** (YouTube, бесплатно)")
    else:
        st.markdown("⚪ yt-dlp (не установлен)")
    if has_yt_api:
        st.markdown("🟢 **YouTube API** (с ключом)")
    else:
        st.markdown("⚪ YouTube API (без ключа)")
    if has_apify:
        st.markdown("🟢 **Apify** (Instagram + TikTok)")
    else:
        st.markdown("⚪ Apify (не подключён)")

    use_demo = not has_ytdlp and not has_yt_api

    if use_demo:
        st.markdown("""
        <div style='background:#1a2a1a;border-left:3px solid #66bb6a;padding:10px;
        border-radius:0 6px 6px 0;font-size:0.82rem;color:#a5d6a7;margin-top:8px;'>
        🟡 <b>Демо-режим</b> — данные примерные.<br>
        Перейди в <b>⚙️ Настройки</b> для подключения.
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 🔍 Параметры поиска")

    query_preset = st.selectbox("Тематика", [
        "smartphone repair", "phone screen replacement", "iphone repair tutorial",
        "samsung repair", "phone battery replacement", "used phone buying guide",
        "phone restoration", "cracked screen fix", "📝 Свой запрос...",
    ], format_func=lambda x: {
        "smartphone repair": "Ремонт смартфонов",
        "phone screen replacement": "Замена экрана",
        "iphone repair tutorial": "Ремонт iPhone",
        "samsung repair": "Ремонт Samsung",
        "phone battery replacement": "Замена аккумулятора",
        "used phone buying guide": "Покупка б/у телефона",
        "phone restoration": "Реставрация телефона",
        "cracked screen fix": "Ремонт разбитого экрана",
        "📝 Свой запрос...": "📝 Свой запрос...",
    }.get(x, x))

    if query_preset == "📝 Свой запрос...":
        search_query = st.text_input("Введите запрос:", "phone repair shop")
    else:
        search_query = query_preset

    available_platforms = ["YouTube"]
    if has_apify:
        available_platforms += ["Instagram", "TikTok"]

    platforms = st.multiselect(
        "Платформы",
        available_platforms,
        default=available_platforms,
    )

    st.markdown("---")
    st.markdown("### 🎯 Фильтры качества")
    min_views = st.number_input(
        "Минимум просмотров (отсев мусора)", 
        min_value=0, value=10000, step=5000,
        help="Instagram и TikTok часто выдают новые видео с 0 просмотрами. Этот фильтр их отсечет."
    )

    col1, col2 = st.columns(2)
    with col1:
        max_results = st.selectbox("Топ видео (показать)", [10, 25, 50], index=1)
    with col2:
        region = st.selectbox("Регион", ["US", "GB", "DE", "AU", "CA", "RU"], index=0)

    date_range = st.slider("Опубликованы (дней назад)", 1, 365, 90)

    sort_by = st.selectbox("Сортировка", [
        "score", "views", "likes", "comments", "days_ago"
    ], format_func=lambda x: {
        "score": "🔥 Рейтинг залётности", "views": "👁 Просмотры",
        "likes": "👍 Лайки", "comments": "💬 Комментарии", "days_ago": "📅 Дата (новее)",
    }.get(x, x))

    st.markdown("---")
    run_btn = st.button("🚀 Запустить анализ", use_container_width=True, type="primary")

    st.markdown("---")
    if st.button("⚙️ Изменить настройки API", use_container_width=True):
        st.session_state.setup_done = False
        st.rerun()

    st.markdown("""
    <div style='font-size:0.75rem;color:#666;'>
    <b>Метрика «залётности»</b> учитывает:<br>
    просмотры, вовлечённость,<br>
    свежесть и скорость роста
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# ОСНОВНОЙ КОНТЕНТ
# ─────────────────────────────────────────────
st.markdown("# 📱 SmartTrend Analyzer")
st.markdown("**Анализ трендовых видео** по теме ремонта и продажи смартфонов")

if use_demo:
    st.markdown("""
    <div class='demo-banner'>
    ℹ️ <b>Демо-режим:</b> отображаются образцовые данные.
    Нажми <b>"⚙️ Изменить настройки API"</b> в боковой панели для подключения реальных данных.
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# ЗАГРУЗКА ДАННЫХ
# ─────────────────────────────────────────────
if run_btn or "df_videos" not in st.session_state:
    with st.spinner("⏳ Загрузка данных..."):
        if use_demo:
            df = pd.DataFrame(DEMO_VIDEOS)
            df = df[df["platform"].isin(platforms)] if platforms else df
        else:
            frames = []
            
            # OVER-FETCHING: Запрашиваем из API значительно больше видео (с запасом),
            # чтобы потом отфильтровать мелочь и оставить только сливки.
            fetch_limit = max(100, max_results * 4)
            
            if "YouTube" in platforms:
                if has_yt_api:
                    st.toast("🔑 Использую YouTube Data API...")
                    yt_rows = search_yt_api(yt_api_key, search_query, fetch_limit, region, date_range)
                    if yt_rows:
                        frames.append(pd.DataFrame(yt_rows))
                elif has_ytdlp:
                    st.toast("🆓 Использую yt-dlp (бесплатно)...")
                    yt_rows = search_ytdlp(search_query, fetch_limit)
                    if yt_rows:
                        frames.append(pd.DataFrame(yt_rows))

            if ("Instagram" in platforms or "TikTok" in platforms) and has_apify:
                # ── Instagram via Apify ──────────────────────────
                if "Instagram" in platforms:
                    try:
                        from apify_client import ApifyClient
                        ig_client = ApifyClient(apify_token)
                        ig_hashtag = search_query.replace(" ", "").lower()
                        st.toast(f"📸 Instagram: ищем #{ig_hashtag}...")
                        ig_run = ig_client.actor("apify/instagram-hashtag-scraper").call(
                            run_input={"hashtags": [ig_hashtag], "resultsLimit": fetch_limit}
                        )
                        ig_items = list(ig_client.dataset(ig_run["defaultDatasetId"]).iterate_items())
                        ig_rows = []
                        for item in ig_items:
                            pub = (item.get("timestamp") or "")[:10]
                            try:
                                days_ago = (datetime.now() - datetime.fromisoformat(pub)).days
                            except Exception:
                                days_ago = 30
                            views = item.get("videoViewCount", 0) or item.get("likesCount", 0) or 0
                            likes = item.get("likesCount", 0) or 0
                            comments_n = item.get("commentsCount", 0) or 0
                            ig_rows.append({
                                "platform": "Instagram",
                                "id": item.get("id", ""),
                                "title": (item.get("caption") or "")[:80],
                                "channel": "@" + (item.get("ownerUsername") or ""),
                                "published": pub,
                                "days_ago": days_ago,
                                "views": views,
                                "likes": likes,
                                "comments": comments_n,
                                "duration_sec": 0,
                                "duration": "",
                                "thumbnail": item.get("displayUrl", ""),
                                "url": item.get("url", ""),
                                "description": (item.get("caption") or "")[:200],
                                "tags": "",
                                "score": score_video(views, likes, comments_n, days_ago),
                            })
                        if ig_rows:
                            frames.append(pd.DataFrame(ig_rows))
                    except ImportError:
                        st.warning("Установи apify-client: pip install apify-client")
                    except Exception as e:
                        st.warning(f"Instagram Apify: {e}")

                # ── TikTok via Apify ─────────────────────────────
                if "TikTok" in platforms:
                    try:
                        from apify_client import ApifyClient
                        tt_client = ApifyClient(apify_token)
                        tt_hashtag = search_query.replace(" ", "").lower()
                        st.toast(f"🎵 TikTok: ищем #{tt_hashtag}...")
                        tt_run = tt_client.actor("clockworks/tiktok-hashtag-scraper").call(
                            run_input={"hashtags": [tt_hashtag], "resultsPerPage": fetch_limit}
                        )
                        tt_items = list(tt_client.dataset(tt_run["defaultDatasetId"]).iterate_items())
                        tt_rows = []
                        for item in tt_items:
                            author = (item.get("authorMeta") or {}).get("name", "")
                            vid_id = item.get("id", "")
                            try:
                                ts = item.get("createTime", 0) or 0
                                pub_dt = datetime.fromtimestamp(ts)
                                days_ago = (datetime.now() - pub_dt).days
                                published = pub_dt.strftime("%Y-%m-%d") if ts else ""
                            except Exception:
                                days_ago = 30
                                published = ""
                            views = item.get("playCount", 0) or 0
                            likes = item.get("diggCount", 0) or 0
                            comments_n = item.get("commentCount", 0) or 0
                            duration_sec = (item.get("videoMeta") or {}).get("duration", 0) or 0
                            tt_rows.append({
                                "platform": "TikTok",
                                "id": vid_id,
                                "title": (item.get("text") or "")[:80],
                                "channel": f"@{author}",
                                "published": published,
                                "days_ago": days_ago,
                                "views": views,
                                "likes": likes,
                                "comments": comments_n,
                                "duration_sec": duration_sec,
                                "duration": duration_fmt(duration_sec),
                                "thumbnail": ((item.get("covers") or [None])[0]) or "",
                                "url": f"https://www.tiktok.com/@{author}/video/{vid_id}",
                                "description": (item.get("text") or "")[:200],
                                "tags": ", ".join([c.get("name", "") for c in (item.get("challenges") or [])[:8]]),
                                "score": score_video(views, likes, comments_n, days_ago),
                            })
                        if tt_rows:
                            frames.append(pd.DataFrame(tt_rows))
                    except ImportError:
                        st.warning("Установи apify-client: pip install apify-client")
                    except Exception as e:
                        st.warning(f"TikTok Apify: {e}")

            if frames:
                df = pd.concat(frames, ignore_index=True)
                
                # --- ГЛАВНАЯ МАГИЯ ФИЛЬТРАЦИИ ---
                # 1. Отсекаем весь мусор (меньше min_views)
                df = df[df["views"] >= min_views]
                
                # 2. Предварительно сортируем то, что осталось
                if sort_by == "days_ago":
                    df = df.sort_values("days_ago")
                else:
                    df = df.sort_values(sort_by, ascending=False)
                    
                # 3. Берем только топ-N (max_results) лучших видео ДЛЯ КАЖДОЙ платформы
                df = df.groupby("platform").head(max_results).reset_index(drop=True)
            else:
                st.warning("Нет данных. Показываем демо.")
                df = pd.DataFrame(DEMO_VIDEOS)

        # Финальная сортировка общего результата для отображения
        if sort_by == "days_ago":
            df = df.sort_values("days_ago")
        else:
            df = df.sort_values(sort_by, ascending=False)

        st.session_state["df_videos"] = df
        st.session_state["trends"] = DEMO_TRENDS

df = st.session_state.get("df_videos", pd.DataFrame(DEMO_VIDEOS))
trends = st.session_state.get("trends", DEMO_TRENDS)

if df.empty:
    st.warning(f"🤷‍♂️ Нет видео, подходящих под критерии. Попробуйте снизить 'Минимум просмотров' (сейчас стоит {min_views}) или изменить поисковый запрос.")
    st.stop()


# ─────────────────────────────────────────────
# ВКЛАДКИ
# ─────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🔥 Топ видео", "📊 Аналитика", "📈 Тренды", "🎬 Референсы", "⚙️ Настройки",
])


# ════════════════════════════════════════════
# ВКЛАДКА 1: ТОП ВИДЕО
# ════════════════════════════════════════════
with tab1:
    total_views = df["views"].sum()
    avg_score = df["score"].mean()
    avg_engagement = ((df["likes"] + df["comments"]) / df["views"].replace(0, 1)).mean() * 100

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div class='kpi-card'>
            <div class='kpi-value'>{fmt_number(total_views)}</div>
            <div class='kpi-label'>Суммарные просмотры</div>
            <div class='kpi-delta up'>▲ {len(df)} видео проанализировано</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class='kpi-card'>
            <div class='kpi-value'>{avg_score:.0f}/100</div>
            <div class='kpi-label'>Средний рейтинг «залётности»</div>
            <div class='kpi-delta up'>{'▲ Высокий' if avg_score > 75 else '▽ Средний'} потенциал</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class='kpi-card'>
            <div class='kpi-value'>{avg_engagement:.2f}%</div>
            <div class='kpi-label'>Средний Engagement Rate</div>
            <div class='kpi-delta {"up" if avg_engagement > 3 else "down"}'>
            {'▲ Выше среднего' if avg_engagement > 3 else '▽ Ниже среднего'}</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        plat_counts = df["platform"].value_counts()
        best_plat = plat_counts.idxmax() if not plat_counts.empty else "—"
        st.markdown(f"""<div class='kpi-card'>
            <div class='kpi-value'>{best_plat}</div>
            <div class='kpi-label'>Самая активная платформа</div>
            <div class='kpi-delta up'>▲ {plat_counts.max() if not plat_counts.empty else 0} видео</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    plat_filter = st.radio("Фильтр платформы:", ["Все"] + list(df["platform"].unique()), horizontal=True)
    show_df = df if plat_filter == "Все" else df[df["platform"] == plat_filter]
    min_score = st.slider("Минимальный рейтинг залётности:", 0, 100, 50)
    show_df = show_df[show_df["score"] >= min_score]
    st.markdown(f"**Найдено видео:** {len(show_df)}")
    st.markdown("---")

    for i, row in show_df.iterrows():
        plat_badge_cls = {"YouTube":"badge-yt","Instagram":"badge-ig","TikTok":"badge-tt"}.get(row["platform"],"")
        score_pct = row["score"]
        col_img, col_info = st.columns([1, 3])
        with col_img:
            if row.get("thumbnail"):
                st.image(row["thumbnail"], width=200)
        with col_info:
            st.markdown(f"""
            <div class='video-card'>
                <span class='badge {plat_badge_cls}'>{row['platform']}</span>
                {'<span class="badge badge-hot">🔥 Горячее</span>' if score_pct >= 90 else ''}
                {'<span class="badge badge-trending">📈 Тренд</span>' if score_pct >= 80 else ''}
                <div class='video-title' style='margin-top:8px;'>{'🔥 ' if score_pct>=90 else ''}{row['title']}</div>
                <div class='video-meta'>📺 {row.get('channel','—')} &nbsp;|&nbsp; 📅 {row.get('published','—')} ({row.get('days_ago',0)} дн. назад) &nbsp;|&nbsp; ⏱ {row.get('duration','—')}</div>
                <div class='video-stats'>👁 {fmt_number(row['views'])} &nbsp;&nbsp; 👍 {fmt_number(row['likes'])} &nbsp;&nbsp; 💬 {fmt_number(row['comments'])}</div>
                <div style='margin-top:8px;font-size:0.8rem;color:#9e9e9e;'>{str(row.get('description',''))[:120]}...</div>
                <div style='margin-top:10px;display:flex;align-items:center;gap:10px;'>
                    <span style='font-size:0.8rem;color:#bbb;'>Рейтинг залётности:</span>
                    <b style='color:#4fc3f7;'>{score_pct}/100</b>
                    <div class='score-bar-wrap' style='flex:1;'>
                        <div class='score-bar-fill' style='width:{score_pct}%;'></div>
                    </div>
                </div>
                <div style='margin-top:8px;'><a href='{row["url"]}' target='_blank' style='color:#4fc3f7;font-size:0.83rem;'>🔗 Открыть видео →</a></div>
            </div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════
# ВКЛАДКА 2: АНАЛИТИКА
# ════════════════════════════════════════════
with tab2:
    st.markdown("<div class='section-header'>📊 Аналитика видео</div>", unsafe_allow_html=True)
    col_a, col_b = st.columns(2)
    with col_a:
        fig_views = px.bar(df.head(12).sort_values("views"), x="views", y="title", orientation="h",
            color="platform", color_discrete_map={"YouTube":"#ff4444","Instagram":"#c13584","TikTok":"#00f2ea"},
            title="Топ видео по просмотрам", labels={"views":"Просмотры","title":""})
        fig_views.update_layout(plot_bgcolor="#1e1e2e",paper_bgcolor="#1e1e2e",font_color="#e0e0e0",height=400,yaxis=dict(tickfont=dict(size=10)))
        fig_views.update_xaxes(gridcolor="#2a2a3e")
        st.plotly_chart(fig_views, use_container_width=True)
    with col_b:
        plat_stats = df.groupby("platform").agg(total_views=("views","sum"),avg_score=("score","mean"),count=("id","count")).reset_index()
        fig_pie = px.pie(plat_stats, names="platform", values="total_views",
            color="platform", color_discrete_map={"YouTube":"#ff4444","Instagram":"#c13584","TikTok":"#00f2ea"},
            title="Доля просмотров по платформам", hole=0.4)
        fig_pie.update_layout(plot_bgcolor="#1e1e2e",paper_bgcolor="#1e1e2e",font_color="#e0e0e0",height=400)
        st.plotly_chart(fig_pie, use_container_width=True)

    col_c, col_d = st.columns(2)
    with col_c:
        fig_scatter = px.scatter(df, x="views", y="score", size="likes",
            color="platform", color_discrete_map={"YouTube":"#ff4444","Instagram":"#c13584","TikTok":"#00f2ea"},
            hover_data=["title","channel","days_ago"], title="Рейтинг залётности vs Просмотры",
            labels={"views":"Просмотры","score":"Рейтинг залётности"}, size_max=30)
        fig_scatter.update_layout(plot_bgcolor="#1e1e2e",paper_bgcolor="#1e1e2e",font_color="#e0e0e0",height=400)
        fig_scatter.update_xaxes(gridcolor="#2a2a3e"); fig_scatter.update_yaxes(gridcolor="#2a2a3e")
        st.plotly_chart(fig_scatter, use_container_width=True)
    with col_d:
        df["engagement"] = (df["likes"] + df["comments"]*3) / df["views"].replace(0,1) * 100
        top_eng = df.nlargest(10,"engagement")[["title","platform","engagement","views"]]
        fig_eng = px.bar(top_eng.sort_values("engagement"), x="engagement", y="title", orientation="h",
            color="platform", color_discrete_map={"YouTube":"#ff4444","Instagram":"#c13584","TikTok":"#00f2ea"},
            title="Топ по Engagement Rate (%)", labels={"engagement":"Вовлечённость %","title":""})
        fig_eng.update_layout(plot_bgcolor="#1e1e2e",paper_bgcolor="#1e1e2e",font_color="#e0e0e0",height=400,yaxis=dict(tickfont=dict(size=10)))
        st.plotly_chart(fig_eng, use_container_width=True)

    df_time = df.copy()
    df_time["published_date"] = pd.to_datetime(df_time["published"], errors="coerce")
    df_time = df_time.dropna(subset=["published_date"])
    if not df_time.empty:
        timeline = df_time.groupby([df_time["published_date"].dt.to_period("W").astype(str),"platform"])["views"].sum().reset_index()
        timeline.columns = ["неделя","platform","views"]
        fig_timeline = px.line(timeline, x="неделя", y="views", color="platform",
            color_discrete_map={"YouTube":"#ff4444","Instagram":"#c13584","TikTok":"#00f2ea"},
            title="Динамика просмотров по неделям", labels={"views":"Просмотры","неделя":"Неделя"}, markers=True)
        fig_timeline.update_layout(plot_bgcolor="#1e1e2e",paper_bgcolor="#1e1e2e",font_color="#e0e0e0",height=320,xaxis=dict(gridcolor="#2a2a3e"),yaxis=dict(gridcolor="#2a2a3e"))
        st.plotly_chart(fig_timeline, use_container_width=True)

    st.markdown("### 📋 Таблица данных")
    display_cols = ["platform","title","channel","published","views","likes","comments","score"]
    st.dataframe(df[display_cols].rename(columns={"platform":"Платформа","title":"Заголовок","channel":"Канал","published":"Дата","views":"Просмотры","likes":"Лайки","comments":"Комментарии","score":"Рейтинг 🔥"}),
        use_container_width=True, hide_index=True,
        column_config={"Просмотры":st.column_config.NumberColumn(format="%d"),
                       "Рейтинг 🔥":st.column_config.ProgressColumn(min_value=0,max_value=100,format="%d")})
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Экспортировать CSV", data=csv,
        file_name=f"smarttrend_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", mime="text/csv")


# ════════════════════════════════════════════
# ВКЛАДКА 3: ТРЕНДЫ
# ════════════════════════════════════════════
with tab3:
    st.markdown("<div class='section-header'>📈 Трендовые хэштеги и запросы</div>", unsafe_allow_html=True)
    trends_df = pd.DataFrame(trends)
    col_e, col_f = st.columns(2)
    with col_e:
        fig_trends = px.bar(trends_df.sort_values("videos",ascending=True), x="videos", y="tag", orientation="h",
            color="platform", color_discrete_map={"YouTube":"#ff4444","Instagram":"#c13584","TikTok":"#00f2ea"},
            title="Трендовые теги по количеству видео", labels={"videos":"Кол-во видео","tag":""})
        fig_trends.update_layout(plot_bgcolor="#1e1e2e",paper_bgcolor="#1e1e2e",font_color="#e0e0e0",height=420)
        st.plotly_chart(fig_trends, use_container_width=True)
    with col_f:
        trends_df["growth_val"] = trends_df["growth"].str.replace("%","").str.replace("+","").astype(float)
        fig_growth = px.bar(trends_df.sort_values("growth_val",ascending=True), x="growth_val", y="tag", orientation="h",
            color="growth_val", color_continuous_scale=["#1565c0","#00e676"],
            title="Рост за 30 дней (%)", labels={"growth_val":"Рост %","tag":""})
        fig_growth.update_layout(plot_bgcolor="#1e1e2e",paper_bgcolor="#1e1e2e",font_color="#e0e0e0",height=420,coloraxis_showscale=False)
        st.plotly_chart(fig_growth, use_container_width=True)

    st.markdown("### 🏷️ Горячие теги прямо сейчас")
    tags_html = ""
    for _, tr in trends_df.sort_values("growth_val",ascending=False).iterrows():
        color = "#c13584" if tr["platform"]=="Instagram" else ("#00796b" if tr["platform"]=="TikTok" else "#c62828")
        tags_html += f"""<span style='display:inline-block;background:{color}22;border:1px solid {color};color:{color};padding:5px 14px;border-radius:20px;margin:4px;font-size:0.85rem;font-weight:600;'>{tr['tag']} <span style='opacity:0.8;font-size:0.75rem;'>{tr['growth']} ↑</span></span>"""
    st.markdown(f"<div style='line-height:2.5;'>{tags_html}</div>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📰 Ключевые инсайты по трендам")
    col_i1, col_i2, col_i3 = st.columns(3)
    with col_i1:
        st.markdown("""**🔥 Форматы, которые «залетают»**
- POV-видео из ремонтного цеха
- До/После восстановление
- «Починил за N рублей» хуки
- Быстрые (до 60 сек) ремонты
- Тесты на прочность/падение""")
    with col_i2:
        st.markdown("""**📅 Оптимальная длина видео**
- TikTok/Reels: 30–90 сек
- YouTube Shorts: 15–60 сек
- YouTube длинный формат: 8–20 мин
- Наивысший ER у 45–75 сек""")
    with col_i3:
        st.markdown("""**💡 Успешные сценарии**
- Клиент принёс убитый телефон
- Ремонт в реальном времени
- «Не неси в сервис — сделай сам»
- Цена в сервисе vs реальная
- Восстановление редких моделей""")


# ════════════════════════════════════════════
# ВКЛАДКА 4: РЕФЕРЕНСЫ
# ════════════════════════════════════════════
with tab4:
    st.markdown("<div class='section-header'>🎬 Лучшие референсы для AI-генерации</div>", unsafe_allow_html=True)
    st.markdown("Топ видео для создания похожего контента с помощью нейросетей")
    top_refs = df.nlargest(6, "score")
    for i, row in top_refs.iterrows():
        with st.expander(f"🔥 #{list(top_refs.index).index(i)+1} — {row['title'][:70]}... | Рейтинг: {row['score']}/100"):
            c1, c2 = st.columns([1, 2])
            with c1:
                if row.get("thumbnail"):
                    st.image(row["thumbnail"])
                st.markdown(f"**Платформа:** {row['platform']}")
                st.markdown(f"**Канал:** {row.get('channel','—')}")
                st.markdown(f"**Просмотры:** {fmt_number(row['views'])}")
                st.markdown(f"**Лайки:** {fmt_number(row['likes'])}")
                st.markdown(f"**Длина:** {row.get('duration','—')}")
                st.markdown(f"[🔗 Открыть видео]({row['url']})")
            with c2:
                st.markdown("**📋 Почему это залетает:**")
                er = (row["likes"] + row["comments"]*3) / max(row["views"],1) * 100
                reasons = []
                if row["views"] > 5_000_000: reasons.append("✅ Массовый охват (5М+ просмотров)")
                if er > 3: reasons.append(f"✅ Высокая вовлечённость ({er:.1f}%)")
                if row["days_ago"] <= 14: reasons.append("✅ Актуальный контент (< 2 нед.)")
                if any(w in row["title"].lower() for w in ["iphone","айфон"]): reasons.append("✅ iPhone — самая популярная тема")
                if any(w in row["title"].lower() for w in ["ремонт","замена","починил","repair","fix","replace"]): reasons.append("✅ Практическая ценность (DIY)")
                if any(w in row["title"].lower() for w in ["руб","экономия","платить","$","save","stop"]): reasons.append("✅ Денежный триггер (экономия)")
                for r in reasons:
                    st.markdown(r)
                st.markdown("**🤖 Идеи для AI-генерации:**")
                st.markdown(f"""
- **Хук (первые 3 сек):** похожий на «{row['title'][:50]}»
- **Длина:** {row.get('duration','—')} — копируй этот формат
- **CTA:** попроси зрителей поделиться своим опытом ремонта
- **Платформы для публикации:** {row['platform']} + кросс-пост
                """)
                st.text_area("📝 Скопируй промпт для AI:", value=f"Создай видео в стиле: «{row['title']}». Платформа: {row['platform']}. Длина: {row.get('duration','—')}. Фокус: практическая польза для владельцев смартфонов, тема ремонта.", height=80, key=f"prompt_{i}")


# ════════════════════════════════════════════
# ВКЛАДКА 5: НАСТРОЙКИ
# ════════════════════════════════════════════
with tab5:
    st.markdown("<div class='section-header'>⚙️ Управление подключениями</div>", unsafe_allow_html=True)

    # Текущий статус
    st.markdown("### 📡 Текущие подключения")
    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        if has_ytdlp:
            st.success("✅ yt-dlp установлен")
        else:
            st.error("❌ yt-dlp не установлен")
            if st.button("📦 Установить yt-dlp", key="install_ytdlp"):
                with st.spinner("Устанавливаем..."):
                    install_ytdlp()
                    st.session_state.ytdlp_installed = True
                    st.success("✅ Установлено!")
                    st.rerun()
    with col_s2:
        if has_yt_api:
            st.success("✅ YouTube API подключён")
        else:
            st.warning("⚪ YouTube API не настроен")
    with col_s3:
        if has_apify:
            st.success("✅ Apify подключён")
        else:
            st.warning("⚪ Apify не настроен")

    st.markdown("---")

    # Раздел обновления ключей
    st.markdown("### 🔑 Обновить API-ключи")

    col_k1, col_k2 = st.columns(2)
    with col_k1:
        st.markdown("**YouTube Data API v3**")
        st.markdown("""<div class='free-info'>
        Бесплатно. 10 000 единиц/день.<br>
        Регистрация: 5 минут, без карты.
        </div>""", unsafe_allow_html=True)
        st.link_button("🌐 Открыть Google Cloud Console →", "https://console.cloud.google.com", use_container_width=True)
        new_yt_key = st.text_input("YouTube API ключ:", value=st.session_state.yt_key, type="password", placeholder="AIzaSy...", key="cfg_yt")

    with col_k2:
        st.markdown("**Apify Token (Instagram + TikTok)**")
        st.markdown("""<div class='api-info'>
        $5 бесплатных кредитов при регистрации.<br>
        Затем ~$1.90 за 1000 постов Instagram/TikTok.
        </div>""", unsafe_allow_html=True)
        st.link_button("🌐 Открыть Apify Console →", "https://console.apify.com/account/integrations", use_container_width=True)
        new_apify_key = st.text_input("Apify Token:", value=st.session_state.apify_key, type="password", placeholder="apify_api_...", key="cfg_ap")

    if st.button("💾 Сохранить ключи", type="primary", use_container_width=True):
        save_keys(new_yt_key, new_apify_key)
        st.session_state.yt_key = new_yt_key
        st.session_state.apify_key = new_apify_key
        st.success("✅ Ключи сохранены в .streamlit/secrets.toml — не нужно вводить при следующем запуске!")
        st.rerun()

    st.markdown("---")
    st.markdown("### 📋 Сравнение режимов работы")
    modes_data = {
        "Режим": ["🆓 yt-dlp (бесплатно)", "🔑 YouTube API", "⚡ + Apify (полный)"],
        "Стоимость": ["Бесплатно", "Бесплатно", "~$2/1000 постов IG/TT"],
        "YouTube": ["✅ Да", "✅ Да (точнее)", "✅ Да"],
        "Instagram": ["❌ Нет", "❌ Нет", "✅ Да"],
        "TikTok": ["❌ Нет", "❌ Нет", "✅ Да"],
        "Лимиты": ["Нет", "10К ед./день", "По кредитам"],
        "Данные": ["Базовые", "Полные (теги, ER)", "Полные (все платформы)"],
    }
    st.dataframe(pd.DataFrame(modes_data), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("### 🔧 Установка зависимостей")
    st.code("pip install streamlit pandas plotly requests yt-dlp apify-client google-api-python-client", language="bash")

    st.markdown("### 🚀 Запуск")
    st.code("streamlit run app.py", language="bash")

    st.markdown("### 📁 Автосохранение ключей")
    st.markdown("""
    Ключи сохраняются в файл `.streamlit/secrets.toml` рядом с `app.py`.
    При следующем запуске приложение загрузит их автоматически.
    """)
    try:
        from pathlib import Path
        sf = Path(".streamlit/secrets.toml")
        if sf.exists():
            st.success("✅ Ключи сохранены локально в `.streamlit/secrets.toml`")
        else:
            st.info("ℹ️ Streamlit Cloud: ключи хранятся в разделе Manage app → Secrets")
    except Exception:
        st.info("ℹ️ Streamlit Cloud: ключи хранятся в разделе Manage app → Secrets")

    if st.button("🔄 Сбросить настройки и запустить мастер заново", use_container_width=True):
        st.session_state.setup_done = False
        st.rerun()