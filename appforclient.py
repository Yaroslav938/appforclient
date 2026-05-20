"""
📱 SmartTrend Analyzer v2
Анализ трендовых видео по теме ремонта и продажи смартфонов
YouTube | Instagram | TikTok
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import re
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

st.set_page_config(
    page_title="SmartTrend Analyzer",
    page_icon="📱",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
section[data-testid="stSidebar"] { background: #0f0f0f; border-right: 1px solid #2a2a2a; }
section[data-testid="stSidebar"] * { color: #e0e0e0 !important; }
.kpi-card { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border: 1px solid #2a2a4a; border-radius: 12px; padding: 20px; text-align: center;
    transition: transform 0.2s; }
.kpi-card:hover { transform: translateY(-2px); }
.kpi-value { font-size: 2rem; font-weight: 700; color: #4fc3f7; }
.kpi-label { font-size: 0.85rem; color: #9e9e9e; margin-top: 4px; }
.kpi-delta { font-size: 0.8rem; margin-top: 6px; }
.kpi-delta.up { color: #66bb6a; }
.kpi-delta.down { color: #ef5350; }
.video-card { background: #1e1e2e; border: 1px solid #2a2a3e; border-radius: 10px;
    padding: 14px; margin-bottom: 12px; transition: border-color 0.2s; }
.video-card:hover { border-color: #4fc3f7; }
.video-title { font-size: 0.95rem; font-weight: 600; color: #e0e0e0; }
.video-meta { font-size: 0.8rem; color: #9e9e9e; margin-top: 6px; }
.video-stats { font-size: 0.85rem; color: #4fc3f7; margin-top: 8px; }
.badge { display: inline-block; padding: 2px 10px; border-radius: 20px;
    font-size: 0.72rem; font-weight: 600; margin-right: 4px; }
.badge-yt { background: #c62828; color: white; }
.badge-ig { background: #6a1b9a; color: white; }
.badge-tt { background: #00796b; color: white; }
.badge-hot { background: #e65100; color: white; }
.badge-trending { background: #1565c0; color: white; }
.score-bar-wrap { background: #2a2a3e; border-radius: 4px; height: 6px; margin-top: 8px; }
.score-bar-fill { height: 6px; border-radius: 4px;
    background: linear-gradient(90deg, #4fc3f7, #9c27b0); }
.section-header { font-size: 1.3rem; font-weight: 700; color: #e0e0e0;
    border-bottom: 2px solid #4fc3f7; padding-bottom: 8px; margin-bottom: 16px; }
.api-info { background: #1a2744; border-left: 4px solid #4fc3f7;
    padding: 12px 16px; border-radius: 0 8px 8px 0; margin: 8px 0;
    font-size: 0.85rem; color: #cfd8dc; }
.free-info { background: #1a2e1a; border-left: 4px solid #66bb6a;
    padding: 12px 16px; border-radius: 0 8px 8px 0; margin: 8px 0;
    font-size: 0.85rem; color: #c8e6c9; }
.demo-banner { background: linear-gradient(90deg, #1a237e, #4a148c);
    color: #e8eaf6; padding: 10px 16px; border-radius: 8px;
    font-size: 0.88rem; margin-bottom: 12px; border: 1px solid #3949ab; }
.setup-step { background: #1a1a2e; border: 1px solid #2a2a4a;
    border-radius: 10px; padding: 16px; margin-bottom: 12px; }
.setup-step-num { display: inline-block; background: #4fc3f7; color: #000;
    border-radius: 50%; width: 28px; height: 28px; text-align: center;
    line-height: 28px; font-weight: 700; font-size: 0.9rem; margin-right: 8px; }
</style>
""", unsafe_allow_html=True)

# ── КЛЮЧИ ────────────────────────────────────────────────────────────────────
def load_saved_keys():
    keys = {"youtube_api_key": "", "apify_token": ""}
    try:
        keys["youtube_api_key"] = st.secrets.get("youtube_api_key", "")
        keys["apify_token"]     = st.secrets.get("apify_token", "")
    except Exception:
        pass
    if not keys["youtube_api_key"]:
        keys["youtube_api_key"] = os.environ.get("YOUTUBE_API_KEY", "")
    if not keys["apify_token"]:
        keys["apify_token"] = os.environ.get("APIFY_TOKEN", "")
    return keys

def save_keys(yt_key, apify_key):
    st.session_state.yt_key    = yt_key
    st.session_state.apify_key = apify_key
    try:
        sd = Path(".streamlit"); sd.mkdir(exist_ok=True)
        (sd / "secrets.toml").write_text(
            f'youtube_api_key = "{yt_key}"\napify_token = "{apify_key}"\n'
        )
    except OSError:
        pass

def check_ytdlp():
    try:
        import yt_dlp  # noqa
        return True
    except ImportError:
        return False

def install_ytdlp():
    subprocess.check_call([sys.executable, "-m", "pip", "install", "yt-dlp", "-q"])

# ── УТИЛИТЫ ──────────────────────────────────────────────────────────────────
def fmt_number(n):
    if n >= 1_000_000: return f"{n/1_000_000:.1f}М"
    if n >= 1_000:     return f"{n/1_000:.1f}К"
    return str(int(n))

def score_video(views, likes, comments, days_ago):
    er       = (likes + comments * 3) / max(views, 1)
    recency  = max(0, 1 - days_ago / 90)
    velocity = views / max(days_ago, 1)
    return min(round(
        min(views / 5_000_000 * 30, 30) +
        min(er * 2000, 30) +
        recency * 20 +
        min(velocity / 50_000 * 20, 20)
    ), 100)

def parse_duration(iso):
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso or "")
    if not m: return 0
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s

def duration_fmt(secs):
    secs = int(secs or 0)
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

# ── ИСТОЧНИК 1: yt-dlp (бесплатно) ──────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def search_ytdlp(query, max_results=20):
    try:
        import yt_dlp
    except ImportError:
        return []
    rows = []
    try:
        opts = {"quiet": True, "no_warnings": True, "extract_flat": True,
                "playlist_items": f"1:{max_results}"}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info    = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            entries = info.get("entries", []) if info else []
        for e in entries:
            if not e: continue
            vid_id = e.get("id", "")
            try:
                pub_dt  = datetime.strptime(e.get("upload_date", ""), "%Y%m%d")
                days_ago = (datetime.now() - pub_dt).days
                published = pub_dt.strftime("%Y-%m-%d")
            except Exception:
                days_ago, published = 30, ""
            v, l, c = (int(e.get(k) or 0) for k in ("view_count", "like_count", "comment_count"))
            dur = int(e.get("duration") or 0)
            rows.append({
                "platform": "YouTube", "id": vid_id,
                "title":       (e.get("title") or "")[:80],
                "channel":     e.get("uploader") or e.get("channel") or "",
                "published":   published, "days_ago": days_ago,
                "views": v, "likes": l, "comments": c,
                "duration_sec": dur, "duration": duration_fmt(dur),
                "thumbnail":   e.get("thumbnail") or f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg",
                "url":         f"https://www.youtube.com/watch?v={vid_id}",
                "description": (e.get("description") or "")[:200],
                "tags":        ", ".join((e.get("tags") or [])[:8]),
                "score":       score_video(v, l, c, days_ago),
            })
    except Exception as exc:
        st.warning(f"yt-dlp: {exc}")
    return rows

# ── ИСТОЧНИК 2: YouTube Data API v3 ─────────────────────────────────────────
YT_BASE = "https://www.googleapis.com/youtube/v3"

@st.cache_data(ttl=300, show_spinner=False)
def search_yt_api(api_key, query, max_results=25, region="US", days=90):
    pub_after = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        r = requests.get(f"{YT_BASE}/search", params={
            "part": "snippet", "q": query, "type": "video",
            "maxResults": max_results, "order": "viewCount",
            "regionCode": region, "publishedAfter": pub_after, "key": api_key,
        }, timeout=10)
        r.raise_for_status()
        items = r.json().get("items", [])
    except Exception as exc:
        st.error(f"YouTube API: {exc}")
        return []
    ids = [i["id"]["videoId"] for i in items if i.get("id", {}).get("videoId")]
    if not ids:
        return []
    stats_map = {s["id"]: s for s in requests.get(f"{YT_BASE}/videos", params={
        "part": "statistics,contentDetails,snippet",
        "id": ",".join(ids), "key": api_key,
    }, timeout=10).json().get("items", [])}
    rows = []
    for item in items:
        vid_id = item.get("id", {}).get("videoId")
        if not vid_id: continue
        snip = item.get("snippet", {})
        stat = stats_map.get(vid_id, {})
        sd   = stat.get("statistics", {})
        cd   = stat.get("contentDetails", {})
        pub  = snip.get("publishedAt", "")
        try:
            pd_  = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            da   = (datetime.now(pd_.tzinfo) - pd_).days
        except Exception:
            da = 30
        v, l, c = int(sd.get("viewCount", 0)), int(sd.get("likeCount", 0)), int(sd.get("commentCount", 0))
        dur = parse_duration(cd.get("duration", ""))
        rows.append({
            "platform": "YouTube", "id": vid_id,
            "title":       snip.get("title", "")[:80],
            "channel":     snip.get("channelTitle", ""),
            "published":   pub[:10], "days_ago": da,
            "views": v, "likes": l, "comments": c,
            "duration_sec": dur, "duration": duration_fmt(dur),
            "thumbnail":   snip.get("thumbnails", {}).get("high", {}).get("url", ""),
            "url":         f"https://www.youtube.com/watch?v={vid_id}",
            "description": snip.get("description", "")[:200],
            "tags":        ", ".join(stat.get("snippet", {}).get("tags", [])[:8]),
            "score":       score_video(v, l, c, da),
        })
    return rows

# ── ИСТОЧНИК 3: Instagram через Apify ────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def search_instagram_apify(token, hashtag, max_results=30):
    try:
        from apify_client import ApifyClient
    except ImportError:
        st.warning("pip install apify-client")
        return []
    try:
        client = ApifyClient(token)
        run    = client.actor("apify/instagram-hashtag-scraper").call(
            run_input={"hashtags": [hashtag.lstrip("#")], "resultsLimit": max_results}
        )
        rows = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            pub = (item.get("timestamp") or "")[:10]
            try: da = (datetime.now() - datetime.fromisoformat(pub)).days
            except Exception: da = 30
            v = item.get("videoViewCount") or item.get("likesCount") or 0
            l = item.get("likesCount") or 0
            c = item.get("commentsCount") or 0
            rows.append({
                "platform": "Instagram", "id": item.get("id", ""),
                "title":       (item.get("caption") or "")[:80],
                "channel":     "@" + (item.get("ownerUsername") or ""),
                "published":   pub, "days_ago": da,
                "views": v, "likes": l, "comments": c,
                "duration_sec": 0, "duration": "",
                "thumbnail":   item.get("displayUrl", ""),
                "url":         item.get("url", ""),
                "description": (item.get("caption") or "")[:200],
                "tags":        "",
                "score":       score_video(v, l, c, da),
            })
        return rows
    except Exception as exc:
        st.warning(f"Instagram Apify: {exc}")
        return []

# ── ИСТОЧНИК 4: TikTok через Apify ───────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def search_tiktok_apify(token, hashtag, max_results=30):
    try:
        from apify_client import ApifyClient
    except ImportError:
        st.warning("pip install apify-client")
        return []
    try:
        client = ApifyClient(token)
        run    = client.actor("clockworks/tiktok-hashtag-scraper").call(
            run_input={"hashtags": [hashtag.lstrip("#")], "resultsPerPage": max_results}
        )
        rows = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            author = (item.get("authorMeta") or {}).get("name", "")
            vid_id = item.get("id", "")
            try:
                pd_  = datetime.fromtimestamp(item.get("createTime", 0))
                da   = (datetime.now() - pd_).days
                pub  = pd_.strftime("%Y-%m-%d")
            except Exception:
                da, pub = 30, ""
            v  = item.get("playCount") or 0
            l  = item.get("diggCount") or 0
            c  = item.get("commentCount") or 0
            dur= (item.get("videoMeta") or {}).get("duration", 0) or 0
            rows.append({
                "platform": "TikTok", "id": vid_id,
                "title":       (item.get("text") or "")[:80],
                "channel":     f"@{author}",
                "published":   pub, "days_ago": da,
                "views": v, "likes": l, "comments": c,
                "duration_sec": dur, "duration": duration_fmt(dur),
                "thumbnail":   ((item.get("covers") or [None])[0]) or "",
                "url":         f"https://www.tiktok.com/@{author}/video/{vid_id}",
                "description": (item.get("text") or "")[:200],
                "tags":        ", ".join(
                    [x.get("name","") for x in (item.get("challenges") or [])[:8]]
                ),
                "score":       score_video(v, l, c, da),
            })
        return rows
    except Exception as exc:
        st.warning(f"TikTok Apify: {exc}")
        return []

# ── ДЕМО-ДАННЫЕ ───────────────────────────────────────────────────────────────
DEMO_VIDEOS = [
    {"platform":"YouTube","id":"dQw4w9WgXcQ","title":"Замена экрана iPhone 15 Pro Max — полное руководство 2024","channel":"PhoneFixer Pro","published":"2024-11-05","days_ago":14,"views":4823000,"likes":95400,"comments":3200,"duration":"18:42","duration_sec":1122,"score":91,"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","thumbnail":"https://picsum.photos/seed/iphone15/320/180","tags":"iphone,ремонт","description":"Полное руководство по замене экрана iPhone 15 Pro Max."},
    {"platform":"YouTube","id":"abc12345","title":"Замена аккумулятора Samsung Galaxy S24 за 10 минут","channel":"QuickFix Mobile","published":"2024-11-10","days_ago":9,"views":2190000,"likes":58700,"comments":1890,"duration":"9:55","duration_sec":595,"score":87,"url":"https://www.youtube.com/watch?v=abc12345","thumbnail":"https://picsum.photos/seed/samsung24/320/180","tags":"samsung,аккумулятор","description":"Быстрая замена аккумулятора Samsung S24."},
    {"platform":"YouTube","id":"def67890","title":"ХВАТИТ платить за ремонт! Сделай это сам","channel":"ЭкономТех","published":"2024-10-28","days_ago":22,"views":7540000,"likes":212000,"comments":9800,"duration":"14:20","duration_sec":860,"score":96,"url":"https://www.youtube.com/watch?v=def67890","thumbnail":"https://picsum.photos/seed/stoprepairing/320/180","tags":"самостоятельный ремонт","description":"Топ-5 ремонтов смартфона, которые ты можешь сделать сам."},
    {"platform":"Instagram","id":"ig_001","title":"Лайфхак по ремонту телефона — экономит 15 000 руб 💸","channel":"@mobilefixmaster","published":"2024-11-14","days_ago":5,"views":8200000,"likes":430000,"comments":12400,"duration":"0:55","duration_sec":55,"score":98,"url":"https://www.instagram.com/p/ig_001/","thumbnail":"https://picsum.photos/seed/ighack/320/180","tags":"#ремонттелефона","description":"Один трюк сэкономит тебе 15 000 рублей."},
    {"platform":"TikTok","id":"tt_001","title":"Уронил iPhone и ПОЧИНИЛ его за 800 рублей 🤯","channel":"@techsaverz","published":"2024-11-13","days_ago":6,"views":15700000,"likes":1200000,"comments":28000,"duration":"0:45","duration_sec":45,"score":99,"url":"https://www.tiktok.com/@techsaverz/video/tt_001","thumbnail":"https://picsum.photos/seed/ttiphone/320/180","tags":"#iphone,#лайфхак","description":"Разбил экран и починил за 800 рублей."},
    {"platform":"TikTok","id":"tt_002","title":"День из жизни мастера по ремонту телефонов 📱","channel":"@fixitfast_phones","published":"2024-11-08","days_ago":11,"views":6340000,"likes":485000,"comments":14200,"duration":"1:05","duration_sec":65,"score":93,"url":"https://www.tiktok.com/@fixitfast_phones/video/tt_002","thumbnail":"https://picsum.photos/seed/dayinlife/320/180","tags":"#деньизжизни","description":"За кулисами сервисного центра."},
    {"platform":"YouTube","id":"ghi11122","title":"Лучшие бюджетные смартфоны 2024 — топ-10 до 25 000 рублей","channel":"ТехОбзор","published":"2024-11-01","days_ago":18,"views":3280000,"likes":87600,"comments":4200,"duration":"22:15","duration_sec":1335,"score":89,"url":"https://www.youtube.com/watch?v=ghi11122","thumbnail":"https://picsum.photos/seed/budget2024/320/180","tags":"бюджетный телефон","description":"Лучшие бюджетные телефоны прямо сейчас."},
    {"platform":"Instagram","id":"ig_002","title":"До и После восстановления телефона 😮","channel":"@restore_tech","published":"2024-11-12","days_ago":7,"views":4100000,"likes":310000,"comments":7800,"duration":"0:38","duration_sec":38,"score":94,"url":"https://www.instagram.com/p/ig_002/","thumbnail":"https://picsum.photos/seed/beforeafter/320/180","tags":"#реставрация","description":"Превращаем уничтоженный Samsung в «как новый»."},
    {"platform":"YouTube","id":"jkl33344","title":"iPhone vs Samsung — что ломается быстрее? Тест на падение 2024","channel":"ТехДроп","published":"2024-10-25","days_ago":25,"views":9150000,"likes":198000,"comments":15600,"duration":"11:08","duration_sec":668,"score":95,"url":"https://www.youtube.com/watch?v=jkl33344","thumbnail":"https://picsum.photos/seed/droptest/320/180","tags":"тест на падение","description":"100 тестов на падение iPhone 15 Pro и Samsung S24 Ultra."},
    {"platform":"TikTok","id":"tt_003","title":"POV: клиент принёс iPhone с водой 💧","channel":"@phonerepairking","published":"2024-11-11","days_ago":8,"views":11200000,"likes":890000,"comments":22000,"duration":"0:52","duration_sec":52,"score":97,"url":"https://www.tiktok.com/@phonerepairking/video/tt_003","thumbnail":"https://picsum.photos/seed/waterdamage/320/180","tags":"#ремонт","description":"POV-серия — самые удовлетворяющие ремонты."},
    {"platform":"YouTube","id":"mno55566","title":"Xiaomi 14 Ultra — полный обзор. Лучшая камера 2024?","channel":"МобильныйГид","published":"2024-10-30","days_ago":20,"views":5670000,"likes":143000,"comments":8900,"duration":"19:44","duration_sec":1184,"score":90,"url":"https://www.youtube.com/watch?v=mno55566","thumbnail":"https://picsum.photos/seed/xiaomi14/320/180","tags":"xiaomi,обзор","description":"Xiaomi 14 Ultra — лучший камерофон?"},
    {"platform":"Instagram","id":"ig_003","title":"5 признаков, что телефон нужно нести в ремонт ⚠️","channel":"@phone_expert_ru","published":"2024-11-06","days_ago":13,"views":3750000,"likes":195000,"comments":5600,"duration":"1:10","duration_sec":70,"score":88,"url":"https://www.instagram.com/p/ig_003/","thumbnail":"https://picsum.photos/seed/phonewarning/320/180","tags":"#советы","description":"Когда точно пора в сервис?"},
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

# ── SESSION STATE ─────────────────────────────────────────────────────────────
saved = load_saved_keys()
if "yt_key"          not in st.session_state: st.session_state.yt_key          = saved.get("youtube_api_key","")
if "apify_key"       not in st.session_state: st.session_state.apify_key       = saved.get("apify_token","")
if "setup_done"      not in st.session_state: st.session_state.setup_done      = bool(saved.get("youtube_api_key") or saved.get("apify_token"))
if "ytdlp_installed" not in st.session_state: st.session_state.ytdlp_installed = check_ytdlp()

# ── МАСТЕР НАСТРОЙКИ ──────────────────────────────────────────────────────────
def show_setup_wizard():
    st.markdown("# 📱 SmartTrend Analyzer")
    st.markdown("## 🚀 Мастер настройки")
    st.markdown("Настрой приложение за 2 минуты и сразу начни анализировать тренды.")

    mode = st.radio("Выбери режим:", [
        "🆓 Бесплатно — YouTube через yt-dlp (без API-ключей)",
        "🔑 YouTube API — точнее, 10 000 запросов/день бесплатно",
        "⚡ Полный — YouTube API + Instagram + TikTok через Apify",
        "🎮 Демо-режим — посмотреть без настройки",
    ], index=0)

    if "Бесплатно" in mode:
        st.markdown('<div class="free-info"><b>✅ Никаких API-ключей!</b> yt-dlp напрямую парсит YouTube.<br>'
                    'Нажми кнопку — и сразу начнёшь работу. Instagram/TikTok — только демо-данные.</div>',
                    unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("⬇️ Установить yt-dlp и начать", type="primary", use_container_width=True):
                with st.spinner("Устанавливаю yt-dlp..."):
                    try:
                        install_ytdlp()
                        st.session_state.ytdlp_installed = True
                        st.session_state.setup_done = True
                        save_keys("", "")
                        st.success("✅ Готово!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Ошибка: {e}\nПопробуй вручную: pip install yt-dlp")
        with c2:
            if check_ytdlp():
                st.info("✅ yt-dlp уже установлен")
                if st.button("▶️ Войти сейчас", use_container_width=True):
                    st.session_state.setup_done = True
                    st.rerun()
            else:
                st.code("pip install yt-dlp", language="bash")

    elif "YouTube API" in mode:
        st.markdown('<div class="api-info"><b>YouTube Data API v3</b> — бесплатно до 10 000 единиц/день.<br>'
                    'Регистрация на console.cloud.google.com — 5 минут.</div>', unsafe_allow_html=True)
        with st.expander("📋 Пошаговая инструкция (разверни)", expanded=True):
            st.markdown("""
<div class="setup-step"><span class="setup-step-num">1</span>
Открой <b>Google Cloud Console</b> → войди под своим Google-аккаунтом</div>
<div class="setup-step"><span class="setup-step-num">2</span>
Вверху → <b>"Select a project"</b> → <b>"New Project"</b> → введи имя → <b>"Create"</b></div>
<div class="setup-step"><span class="setup-step-num">3</span>
В поиске введи <code>YouTube Data API v3</code> → открой результат → нажми <b>"Enable"</b></div>
<div class="setup-step"><span class="setup-step-num">4</span>
Слева → <b>"APIs & Services" → "Credentials" → "+ CREATE CREDENTIALS" → "API key"</b></div>
<div class="setup-step"><span class="setup-step-num">5</span>
Скопируй ключ вида <code>AIzaSy...</code> → вставь ниже → нажми "Проверить"</div>
""", unsafe_allow_html=True)
        st.link_button("🔗 Открыть Google Cloud Console", "https://console.cloud.google.com",
                       use_container_width=True)
        yt_inp = st.text_input("YouTube API ключ", value=st.session_state.yt_key,
                               type="password", placeholder="AIzaSy...")
        if yt_inp and st.button("✅ Проверить и сохранить", type="primary", use_container_width=True):
            with st.spinner("Проверяю..."):
                try:
                    r = requests.get(f"{YT_BASE}/search",
                        params={"part":"snippet","q":"test","type":"video","maxResults":1,"key":yt_inp},
                        timeout=8)
                    if r.status_code == 200:
                        st.success("✅ Ключ работает!")
                        st.session_state.yt_key = yt_inp
                        save_keys(yt_inp, "")
                        st.session_state.setup_done = True
                        if not check_ytdlp(): install_ytdlp(); st.session_state.ytdlp_installed = True
                        st.rerun()
                    elif r.status_code == 403:
                        err = r.json().get("error",{}).get("message","")
                        if "accessNotConfigured" in err:
                            st.error("❌ YouTube Data API v3 не включён. Выполни шаг 3.")
                        else:
                            st.error(f"❌ {err}")
                    else:
                        st.error(f"❌ Ошибка {r.status_code}")
                except Exception as e:
                    st.error(f"❌ {e}")

    elif "Полный" in mode:
        st.markdown('<div class="api-info"><b>YouTube API</b> + <b>Apify</b> — Instagram и TikTok.<br>'
                    'Apify: <b>$5 бесплатных кредитов</b> при регистрации (~2600 постов).</div>',
                    unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**YouTube Data API v3**")
            st.link_button("🔗 Google Cloud Console", "https://console.cloud.google.com")
            yt_inp = st.text_input("YouTube API ключ", value=st.session_state.yt_key,
                                   type="password", placeholder="AIzaSy...", key="wiz_yt")
        with c2:
            st.markdown("**Apify Token** — Instagram + TikTok")
            st.link_button("🔗 Apify Console", "https://console.apify.com/account/integrations")
            ap_inp = st.text_input("Apify Token", value=st.session_state.apify_key,
                                   type="password", placeholder="apify_api_...", key="wiz_ap")
        if st.button("💾 Сохранить и войти", type="primary", use_container_width=True):
            save_keys(yt_inp or "", ap_inp or "")
            st.session_state.yt_key    = yt_inp or ""
            st.session_state.apify_key = ap_inp or ""
            st.session_state.setup_done = True
            st.success("✅ Настройки сохранены!")
            st.rerun()
    else:
        st.info("🎮 Демо-режим — работает с примерами данных без интернет-запросов.")
        if st.button("▶️ Войти в демо-режим", type="primary", use_container_width=True):
            st.session_state.setup_done = True
            st.rerun()

    st.markdown("---")
    st.markdown("<small>Настройки сохраняются в <code>.streamlit/secrets.toml</code> — "
                "при следующем запуске вводить не нужно.</small>", unsafe_allow_html=True)


if not st.session_state.setup_done:
    show_setup_wizard()
    st.stop()

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
yt_api_key  = st.session_state.yt_key
apify_token = st.session_state.apify_key
ytdlp_ok    = st.session_state.ytdlp_installed or check_ytdlp()
has_yt_api  = bool(yt_api_key)
has_apify   = bool(apify_token)
has_ytdlp   = ytdlp_ok
use_demo    = not has_ytdlp and not has_yt_api

with st.sidebar:
    st.markdown("## 📱 SmartTrend")
    st.markdown("---")
    st.markdown("**Источники:**")
    st.markdown("✅ yt-dlp (YouTube)" if has_ytdlp else "⚪ yt-dlp (не установлен)")
    st.markdown("✅ YouTube API"       if has_yt_api else "⚪ YouTube API")
    st.markdown("✅ Apify (IG+TT)"    if has_apify  else "⚪ Apify (Instagram/TikTok)")
    if use_demo:
        st.markdown('<div style="background:#1a2a1a;border-left:3px solid #66bb6a;padding:10px;'
                    'border-radius:0 6px 6px 0;font-size:0.82rem;color:#a5d6a7;margin-top:8px">'
                    '<b>🎮 Демо-режим</b></div>', unsafe_allow_html=True)
    st.markdown("---")

    query_preset = st.selectbox("Готовый запрос:", [
        "smartphone repair","phone screen replacement","iphone repair tutorial",
        "samsung repair","phone battery replacement","used phone buying guide",
        "phone restoration","cracked screen fix","...свой запрос",
    ], format_func=lambda x: {
        "smartphone repair":       "📱 Ремонт смартфонов",
        "phone screen replacement":"🖥️ Замена экрана",
        "iphone repair tutorial":  "🍎 Ремонт iPhone",
        "samsung repair":          "🤖 Ремонт Samsung",
        "phone battery replacement":"🔋 Замена аккумулятора",
        "used phone buying guide": "🛒 Покупка б/у телефона",
        "phone restoration":       "✨ Реставрация телефона",
        "cracked screen fix":      "💔 Разбитый экран",
        "...свой запрос":          "✏️ Свой запрос...",
    }.get(x, x))

    search_query = st.text_input("Введи запрос:", "phone repair shop") \
        if query_preset == "...свой запрос" else query_preset

    available_platforms = ["YouTube"] + (["Instagram","TikTok"] if has_apify else [])
    platforms   = st.multiselect("Платформы:", available_platforms, default=available_platforms)
    c1, c2      = st.columns(2)
    with c1:    max_results = st.selectbox("Кол-во:", [10, 25, 50], index=1)
    with c2:    region      = st.selectbox("Регион:", ["US","GB","DE","AU","CA","RU"], index=0)
    date_range  = st.slider("Период (дней):", 1, 365, 90)
    sort_by     = st.selectbox("Сортировка:", ["score","views","likes","comments","days_ago"],
        format_func=lambda x: {"score":"🏆 Рейтинг","views":"👁️ Просмотры","likes":"❤️ Лайки",
                               "comments":"💬 Комментарии","days_ago":"📅 Дата"}.get(x,x))
    st.markdown("---")
    run_btn = st.button("🚀 Запустить анализ", use_container_width=True, type="primary")
    st.markdown("---")
    if st.button("⚙️ Изменить настройки API", use_container_width=True):
        st.session_state.setup_done = False
        st.rerun()

# ── ЗАГОЛОВОК ─────────────────────────────────────────────────────────────────
st.markdown("# 📱 SmartTrend Analyzer")
if use_demo:
    st.markdown('<div class="demo-banner">🎮 <b>Демо-режим</b> — данные примерные. '
                'Добавь <b>API-ключи</b> для реальной аналитики.</div>', unsafe_allow_html=True)

# ── ЗАГРУЗКА ДАННЫХ ───────────────────────────────────────────────────────────
if run_btn or "df_videos" not in st.session_state:
    with st.spinner("⏳ Загружаю данные..."):
        if use_demo:
            df = pd.DataFrame(DEMO_VIDEOS)
            df = df[df["platform"].isin(platforms)] if platforms else df
        else:
            frames = []
            if "YouTube" in platforms:
                if has_yt_api:
                    st.toast("🔑 YouTube Data API...")
                    rows = search_yt_api(yt_api_key, search_query, max_results, region, date_range)
                    if rows: frames.append(pd.DataFrame(rows))
                elif has_ytdlp:
                    st.toast("🆓 yt-dlp...")
                    rows = search_ytdlp(search_query, max_results)
                    if rows: frames.append(pd.DataFrame(rows))
            if has_apify:
                htag = search_query.replace(" ", "").lower()
                if "Instagram" in platforms:
                    st.toast("📷 Instagram...")
                    rows = search_instagram_apify(apify_token, htag, max_results)
                    if rows: frames.append(pd.DataFrame(rows))
                if "TikTok" in platforms:
                    st.toast("🎵 TikTok...")
                    rows = search_tiktok_apify(apify_token, htag, max_results)
                    if rows: frames.append(pd.DataFrame(rows))
            if frames:
                df = pd.concat(frames, ignore_index=True)
            else:
                st.warning("Нет данных. Проверь настройки API.")
                df = pd.DataFrame(DEMO_VIDEOS)

        df = df.sort_values("days_ago") if sort_by == "days_ago" else df.sort_values(sort_by, ascending=False)
        st.session_state.df_videos = df
        st.session_state.trends    = DEMO_TRENDS

df     = st.session_state.get("df_videos", pd.DataFrame(DEMO_VIDEOS))
trends = st.session_state.get("trends",    DEMO_TRENDS)
if df.empty: st.warning("Нет данных."); st.stop()

COLORS = {"YouTube":"#ff4444","Instagram":"#c13584","TikTok":"#00f2ea"}

# ── ВКЛАДКИ ───────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["🔥 Топ видео","📊 Аналитика","📈 Тренды","🎬 Референсы для AI","⚙️ Настройки"]
)

# TAB 1
with tab1:
    tv  = df["views"].sum()
    avs = df["score"].mean()
    avg_er = ((df["likes"] + df["comments"]) / df["views"].replace(0,1) * 100).mean()
    pc  = df["platform"].value_counts()
    bp  = pc.idxmax() if not pc.empty else "—"
    c1,c2,c3,c4 = st.columns(4)
    for col, val, label, delta in [
        (c1, fmt_number(tv),    "Суммарный охват",  f"↑ {len(df)} видео"),
        (c2, f"{avs:.0f}/100",  "Средний рейтинг",  "🔥 Высокий" if avs>75 else "📊 Средний"),
        (c3, f"{avg_er:.2f}%",  "Engagement Rate",  "↑ Выше нормы" if avg_er>3 else "↓ Ниже нормы"),
        (c4, bp,                "Лучшая платформа", f"↑ {pc.max() if not pc.empty else 0} видео"),
    ]:
        col.markdown(f'<div class="kpi-card"><div class="kpi-value">{val}</div>'
                     f'<div class="kpi-label">{label}</div>'
                     f'<div class="kpi-delta up">{delta}</div></div>',
                     unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    plat_f    = st.radio("Фильтр:", ["Все"]+list(df["platform"].unique()), horizontal=True)
    min_score = st.slider("Мин. рейтинг:", 0, 100, 50)
    show_df   = (df if plat_f=="Все" else df[df["platform"]==plat_f])
    show_df   = show_df[show_df["score"] >= min_score]
    st.markdown(f"**Найдено: {len(show_df)} видео**")
    st.markdown("---")

    for _, row in show_df.iterrows():
        pcls  = {"YouTube":"badge-yt","Instagram":"badge-ig","TikTok":"badge-tt"}.get(row["platform"],"")
        sc    = row["score"]
        hot   = '<span class="badge badge-hot">🔥 ТОП</span>'     if sc>=90 else \
                '<span class="badge badge-trending">📈 Тренд</span>' if sc>=80 else ""
        ci, cf = st.columns([1,3])
        with ci:
            if row.get("thumbnail"): st.image(row["thumbnail"], width=200)
        with cf:
            st.markdown(
                f'<div class="video-card">'
                f'<span class="badge {pcls}">{row["platform"]}</span> {hot}'
                f'<div class="video-title" style="margin-top:8px">{"🔥 " if sc>=90 else ""}{row["title"]}</div>'
                f'<div class="video-meta">{row.get("channel","")} &nbsp;|&nbsp; '
                f'{row.get("published","")} ({row.get("days_ago",0):.0f} дн.) &nbsp;|&nbsp; ⏱ {row.get("duration","")}</div>'
                f'<div class="video-stats">👁 {fmt_number(row["views"])} &nbsp;❤️ {fmt_number(row["likes"])} &nbsp;💬 {fmt_number(row["comments"])}</div>'
                f'<div style="margin-top:8px;font-size:0.8rem;color:#9e9e9e">{str(row.get("description",""))[:120]}...</div>'
                f'<div style="margin-top:10px;display:flex;align-items:center;gap:10px">'
                f'<span style="font-size:0.8rem;color:#bbb">Рейтинг</span>'
                f'<b style="color:#4fc3f7">{sc}/100</b>'
                f'<div class="score-bar-wrap" style="flex:1"><div class="score-bar-fill" style="width:{sc}%"></div></div></div>'
                f'<div style="margin-top:8px"><a href="{row["url"]}" target="_blank" '
                f'style="color:#4fc3f7;font-size:0.83rem">🔗 Открыть видео</a></div>'
                f'</div>', unsafe_allow_html=True)

# TAB 2
with tab2:
    st.markdown('<div class="section-header">📊 Аналитика</div>', unsafe_allow_html=True)
    ca, cb = st.columns(2)
    with ca:
        fig = px.bar(df.head(12).sort_values("views"), x="views", y="title",
                     orientation="h", color="platform", color_discrete_map=COLORS,
                     title="Топ по просмотрам", labels={"views":"Просмотры","title":""})
        fig.update_layout(plot_bgcolor="#1e1e2e", paper_bgcolor="#1e1e2e",
                          font_color="#e0e0e0", height=400, yaxis=dict(tickfont=dict(size=10)))
        fig.update_xaxes(gridcolor="#2a2a3e")
        st.plotly_chart(fig, use_container_width=True)
    with cb:
        ps = df.groupby("platform").agg(total=("views","sum")).reset_index()
        fig2 = px.pie(ps, names="platform", values="total", color="platform",
                      color_discrete_map=COLORS, title="Охват по платформам", hole=0.4)
        fig2.update_layout(plot_bgcolor="#1e1e2e", paper_bgcolor="#1e1e2e",
                           font_color="#e0e0e0", height=400)
        st.plotly_chart(fig2, use_container_width=True)

    cc, cd = st.columns(2)
    with cc:
        fig3 = px.scatter(df, x="views", y="score", size="likes", color="platform",
                          color_discrete_map=COLORS, hover_data=["title","channel"],
                          title="Просмотры vs Рейтинг", labels={"views":"Просмотры","score":"Рейтинг"},
                          size_max=30)
        fig3.update_layout(plot_bgcolor="#1e1e2e", paper_bgcolor="#1e1e2e",
                           font_color="#e0e0e0", height=400)
        fig3.update_xaxes(gridcolor="#2a2a3e"); fig3.update_yaxes(gridcolor="#2a2a3e")
        st.plotly_chart(fig3, use_container_width=True)
    with cd:
        df_e = df.assign(er=(df["likes"]+df["comments"]*3)/df["views"].replace(0,1)*100)
        fig4 = px.bar(df_e.nlargest(10,"er").sort_values("er"),
                      x="er", y="title", orientation="h", color="platform",
                      color_discrete_map=COLORS, title="Топ по Engagement Rate",
                      labels={"er":"ER %","title":""})
        fig4.update_layout(plot_bgcolor="#1e1e2e", paper_bgcolor="#1e1e2e",
                           font_color="#e0e0e0", height=400, yaxis=dict(tickfont=dict(size=10)))
        st.plotly_chart(fig4, use_container_width=True)

    dt = df.copy()
    dt["pd"] = pd.to_datetime(dt["published"], errors="coerce")
    dt = dt.dropna(subset=["pd"])
    if not dt.empty:
        tl = dt.groupby([dt["pd"].dt.to_period("W").astype(str),"platform"])["views"].sum().reset_index()
        tl.columns = ["Неделя","platform","views"]
        fig5 = px.line(tl, x="Неделя", y="views", color="platform", color_discrete_map=COLORS,
                       title="Динамика просмотров по неделям", markers=True,
                       labels={"views":"Просмотры","Неделя":""})
        fig5.update_layout(plot_bgcolor="#1e1e2e", paper_bgcolor="#1e1e2e", font_color="#e0e0e0", height=320)
        st.plotly_chart(fig5, use_container_width=True)

    display_cols = ["platform","title","channel","published","views","likes","comments","score"]
    st.dataframe(df[display_cols].rename(columns={
        "platform":"Платформа","title":"Заголовок","channel":"Канал","published":"Дата",
        "views":"Просмотры","likes":"Лайки","comments":"Комментарии","score":"Рейтинг"
    }), use_container_width=True, hide_index=True,
    column_config={"Рейтинг": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d")})

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Скачать CSV", data=csv,
        file_name=f"smarttrend_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", mime="text/csv")

# TAB 3
with tab3:
    st.markdown('<div class="section-header">📈 Тренды</div>', unsafe_allow_html=True)
    tdf = pd.DataFrame(trends)
    ce, cf = st.columns(2)
    with ce:
        f1 = px.bar(tdf.sort_values("videos"), x="videos", y="tag", orientation="h",
                    color="platform", color_discrete_map=COLORS, title="Популярность хэштегов",
                    labels={"videos":"Видео","tag":""})
        f1.update_layout(plot_bgcolor="#1e1e2e", paper_bgcolor="#1e1e2e", font_color="#e0e0e0", height=420)
        st.plotly_chart(f1, use_container_width=True)
    with cf:
        tdf["gv"] = tdf["growth"].str.replace("+","").str.replace("%","").astype(float)
        f2 = px.bar(tdf.sort_values("gv"), x="gv", y="tag", orientation="h",
                    color="gv", color_continuous_scale=["#1565c0","#00e676"],
                    title="Рост за 30 дней (%)", labels={"gv":"Рост %","tag":""})
        f2.update_layout(plot_bgcolor="#1e1e2e", paper_bgcolor="#1e1e2e", font_color="#e0e0e0",
                         height=420, coloraxis_showscale=False)
        st.plotly_chart(f2, use_container_width=True)

    tags_html = ""
    for _, tr in tdf.sort_values("gv", ascending=False).iterrows():
        clr = "#c13584" if tr["platform"]=="Instagram" else "#00796b" if tr["platform"]=="TikTok" else "#c62828"
        tags_html += (f'<span style="display:inline-block;border:1px solid {clr};color:{clr};'
                      f'padding:5px 14px;border-radius:20px;margin:4px;font-size:0.85rem;font-weight:600">'
                      f'{tr["tag"]} <span style="opacity:0.8;font-size:0.75rem">{tr["growth"]}</span></span>')
    st.markdown(f'<div style="line-height:2.5">{tags_html}</div>', unsafe_allow_html=True)
    st.markdown("---")
    i1, i2, i3 = st.columns(3)
    with i1:
        st.markdown("**Структура сценария:**\n- 🎣 Крючок (боль/шок) — первые 3 сек\n- ✂️ POV-подача\n"
                    "- ✅ До/После трансформация\n- 🔢 Числа в заголовке\n- ⏱ Shorts до 60 сек")
    with i2:
        st.markdown("**Форматы по длине:**\n- TikTok/Reels: 30–90 сек\n- YouTube Shorts: 15–60 сек\n"
                    "- YouTube обзор: 8–20 мин\n- Engagement Rate: 4.5–7.5%")
    with i3:
        st.markdown("**Темы с макс. охватом:**\n- 💸 Экономия на ремонте\n- 😮 Шокирующая трансформация\n"
                    "- ⚡ Быстрый способ / Life hack\n- 🆚 Сравнения брендов\n- 🔑 Секреты мастера")

# TAB 4
with tab4:
    st.markdown('<div class="section-header">🎬 Топ референсы для AI-генерации</div>', unsafe_allow_html=True)
    st.markdown("Выбери видео с высоким рейтингом → используй анализ как промпт для AI-генерации")
    for i, (_, row) in enumerate(df.nlargest(6,"score").iterrows()):
        with st.expander(f"#{i+1} | {row['title'][:70]}... | ⭐ {row['score']}/100"):
            c1, c2 = st.columns([1,2])
            with c1:
                if row.get("thumbnail"): st.image(row["thumbnail"])
                st.markdown(f"**Платформа:** {row['platform']}")
                st.markdown(f"**Канал:** {row.get('channel','—')}")
                st.markdown(f"**Просмотры:** {fmt_number(row['views'])}")
                st.markdown(f"**Лайки:** {fmt_number(row['likes'])}")
                st.markdown(f"**Длина:** {row.get('duration','—')}")
                st.markdown(f"[🔗 Смотреть оригинал]({row['url']})")
            with c2:
                er = (row["likes"] + row["comments"]*3) / max(row["views"],1)*100
                reasons = []
                if row["views"]>5_000_000: reasons.append("🔥 Сверхвирусный — более 5М просмотров")
                if er>3:                   reasons.append(f"💬 Высокий ER: {er:.1f}%")
                if row["days_ago"]<14:     reasons.append("⚡ Свежий тренд — менее 2 недель")
                for w in ["iphone","айфон"]:
                    if w in row["title"].lower(): reasons.append("🍎 Тема iPhone — вечный магнит"); break
                for w in ["ремонт","repair","fix","замена","replace"]:
                    if w in row["title"].lower(): reasons.append("🔧 DIY-формат — люди хотят сами"); break
                for w in ["хватит","stop","экономия","save","бесплатно"]:
                    if w in row["title"].lower(): reasons.append("💸 Мотивация экономии — сильный триггер"); break
                for w in ["pov","день из жизни","за кулисами"]:
                    if w in row["title"].lower(): reasons.append("👁️ POV/закулисный — высокое доверие"); break
                st.markdown("**Почему это залетело:**")
                for r in reasons: st.markdown(f"- {r}")
                st.markdown("---")
                st.markdown("**📝 Готовый промпт для AI:**")
                prompt = (f"Создай видео в стиле: «{row['title'][:50]}». "
                          f"Платформа: {row['platform']}. Длина: {row.get('duration','до 60 сек')}. "
                          f"Стиль: вовлекающий, крючок в первые 3 секунды, POV-подача. "
                          f"Ключевые слова: ремонт телефона, сервисный центр, смартфон.")
                st.text_area("Промпт:", value=prompt, height=90, key=f"pr_{i}")

# TAB 5
with tab5:
    st.markdown('<div class="section-header">⚙️ Настройки API</div>', unsafe_allow_html=True)
    cs1, cs2, cs3 = st.columns(3)
    with cs1:
        if has_ytdlp:
            st.success("✅ yt-dlp установлен")
        else:
            st.error("❌ yt-dlp не найден")
            if st.button("⬇️ Установить yt-dlp", key="inst_yt"):
                with st.spinner("..."): install_ytdlp(); st.session_state.ytdlp_installed=True; st.rerun()
    with cs2:
        st.success("✅ YouTube API") if has_yt_api else st.warning("⚪ YouTube API не задан")
    with cs3:
        st.success("✅ Apify") if has_apify else st.warning("⚪ Apify не задан")
    st.markdown("---")
    ck1, ck2 = st.columns(2)
    with ck1:
        st.markdown("**YouTube Data API v3**")
        st.markdown('<div class="free-info">Бесплатно. Квота: 10 000 единиц/день.</div>',
                    unsafe_allow_html=True)
        st.link_button("🔗 Google Cloud Console", "https://console.cloud.google.com", use_container_width=True)
        new_yt = st.text_input("YouTube API ключ", value=st.session_state.yt_key,
                               type="password", placeholder="AIzaSy...", key="cfg_yt")
    with ck2:
        st.markdown("**Apify Token** — Instagram + TikTok")
        st.markdown('<div class="api-info">$5 бесплатных кредитов при регистрации.<br>'
                    '~$1.90 за 1000 постов Instagram/TikTok.</div>', unsafe_allow_html=True)
        st.link_button("🔗 Apify Console", "https://console.apify.com/account/integrations",
                       use_container_width=True)
        new_ap = st.text_input("Apify Token", value=st.session_state.apify_key,
                               type="password", placeholder="apify_api_...", key="cfg_ap")
    if st.button("💾 Сохранить", type="primary", use_container_width=True):
        save_keys(new_yt, new_ap)
        st.session_state.yt_key=new_yt; st.session_state.apify_key=new_ap
        st.success("✅ Сохранено в .streamlit/secrets.toml!")
        st.rerun()
    st.markdown("---")
    st.markdown("### 📦 Зависимости")
    st.code("pip install streamlit pandas plotly requests yt-dlp apify-client google-api-python-client",
            language="bash")
    st.markdown("### ▶️ Запуск")
    st.code("streamlit run app.py", language="bash")
    st.markdown("---")
    if st.button("🔄 Сбросить настройки (открыть мастер)", use_container_width=True):
        st.session_state.setup_done = False
        st.rerun()
