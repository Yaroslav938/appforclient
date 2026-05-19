"""
📱 SmartTrend Analyzer
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
from datetime import datetime, timedelta
from urllib.parse import quote_plus, urlparse, parse_qs
import os

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="SmartTrend Analyzer",
    page_icon="📱",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# CUSTOM CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Dark sidebar */
section[data-testid="stSidebar"] {
    background: #0f0f0f;
    border-right: 1px solid #2a2a2a;
}
section[data-testid="stSidebar"] * {
    color: #e0e0e0 !important;
}

/* KPI cards */
.kpi-card {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border: 1px solid #2a2a4a;
    border-radius: 12px;
    padding: 20px;
    text-align: center;
    transition: transform 0.2s;
}
.kpi-card:hover { transform: translateY(-2px); }
.kpi-value { font-size: 2rem; font-weight: 700; color: #4fc3f7; }
.kpi-label { font-size: 0.85rem; color: #9e9e9e; margin-top: 4px; }
.kpi-delta { font-size: 0.8rem; margin-top: 6px; }
.kpi-delta.up { color: #66bb6a; }
.kpi-delta.down { color: #ef5350; }

/* Video cards */
.video-card {
    background: #1e1e2e;
    border: 1px solid #2a2a3e;
    border-radius: 10px;
    padding: 14px;
    margin-bottom: 12px;
    transition: border-color 0.2s;
}
.video-card:hover { border-color: #4fc3f7; }
.video-title { font-size: 0.95rem; font-weight: 600; color: #e0e0e0; }
.video-meta { font-size: 0.8rem; color: #9e9e9e; margin-top: 6px; }
.video-stats { font-size: 0.85rem; color: #4fc3f7; margin-top: 8px; }
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    margin-right: 4px;
}
.badge-yt { background: #c62828; color: white; }
.badge-ig { background: #6a1b9a; color: white; }
.badge-tt { background: #00796b; color: white; }
.badge-hot { background: #e65100; color: white; }
.badge-trending { background: #1565c0; color: white; }

/* Score bar */
.score-bar-wrap { background: #2a2a3e; border-radius: 4px; height: 6px; margin-top: 8px; }
.score-bar-fill { height: 6px; border-radius: 4px; background: linear-gradient(90deg, #4fc3f7, #9c27b0); }

/* Section headers */
.section-header {
    font-size: 1.3rem; font-weight: 700;
    color: #e0e0e0; border-bottom: 2px solid #4fc3f7;
    padding-bottom: 8px; margin-bottom: 16px;
}

/* Trend tag */
.trend-tag {
    display: inline-block; background: #0d47a1;
    color: #90caf9; padding: 3px 10px; border-radius: 20px;
    font-size: 0.75rem; margin: 2px;
}

/* API setup info box */
.api-info {
    background: #1a2744;
    border-left: 4px solid #4fc3f7;
    padding: 12px 16px;
    border-radius: 0 8px 8px 0;
    margin: 8px 0;
    font-size: 0.85rem;
    color: #cfd8dc;
}

/* Demo banner */
.demo-banner {
    background: linear-gradient(90deg, #1a237e, #4a148c);
    color: #e8eaf6;
    padding: 10px 16px;
    border-radius: 8px;
    font-size: 0.88rem;
    margin-bottom: 12px;
    border: 1px solid #3949ab;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# HELPERS & FORMATTERS
# ─────────────────────────────────────────────
def fmt_number(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)

def score_video(views, likes, comments, days_ago):
    """Рейтинг «залётности» видео (0-100)"""
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
    """ISO 8601 duration → секунды"""
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso or "")
    if not m:
        return 0
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s

def duration_fmt(secs):
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


# ─────────────────────────────────────────────
# YOUTUBE DATA API
# ─────────────────────────────────────────────
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"

def yt_search(api_key, query, max_results=25, order="viewCount",
              published_after=None, region="US"):
    """Поиск видео на YouTube"""
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max_results,
        "order": order,
        "regionCode": region,
        "relevanceLanguage": "en",
        "key": api_key,
    }
    if published_after:
        params["publishedAfter"] = published_after
    try:
        r = requests.get(f"{YOUTUBE_API_BASE}/search", params=params, timeout=10)
        r.raise_for_status()
        return r.json().get("items", [])
    except Exception as e:
        st.error(f"YouTube API error: {e}")
        return []

def yt_video_stats(api_key, video_ids):
    """Статистика видео по ID"""
    ids = ",".join(video_ids)
    params = {
        "part": "statistics,contentDetails,snippet",
        "id": ids,
        "key": api_key,
    }
    try:
        r = requests.get(f"{YOUTUBE_API_BASE}/videos", params=params, timeout=10)
        r.raise_for_status()
        return {
            item["id"]: item
            for item in r.json().get("items", [])
        }
    except Exception as e:
        st.error(f"YouTube stats error: {e}")
        return {}

def yt_trending(api_key, category_id="0", region="US", max_results=25):
    """Трендовые видео YouTube по региону"""
    params = {
        "part": "snippet,statistics,contentDetails",
        "chart": "mostPopular",
        "regionCode": region,
        "videoCategoryId": category_id,
        "maxResults": max_results,
        "key": api_key,
    }
    try:
        r = requests.get(f"{YOUTUBE_API_BASE}/videos", params=params, timeout=10)
        r.raise_for_status()
        return r.json().get("items", [])
    except Exception as e:
        st.error(f"YouTube trending error: {e}")
        return []

def build_youtube_df(items_search, stats_dict):
    """Собрать DataFrame из результатов поиска и статистики"""
    rows = []
    for item in items_search:
        vid_id = item.get("id", {}).get("videoId") or item.get("id")
        if not vid_id:
            continue
        snip = item.get("snippet", {})
        stat = stats_dict.get(vid_id, {})
        stat_data = stat.get("statistics", {}) if stat else {}
        content = stat.get("contentDetails", {}) if stat else {}

        published = snip.get("publishedAt", "")
        try:
            pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
            days_ago = (datetime.now(pub_dt.tzinfo) - pub_dt).days
        except:
            days_ago = 30

        views = int(stat_data.get("viewCount", 0))
        likes = int(stat_data.get("likeCount", 0))
        comments = int(stat_data.get("commentCount", 0))
        dur_secs = parse_duration(content.get("duration", ""))

        rows.append({
            "platform": "YouTube",
            "id": vid_id,
            "title": snip.get("title", "")[:80],
            "channel": snip.get("channelTitle", ""),
            "published": published[:10],
            "days_ago": days_ago,
            "views": views,
            "likes": likes,
            "comments": comments,
            "duration_sec": dur_secs,
            "duration": duration_fmt(dur_secs),
            "thumbnail": snip.get("thumbnails", {}).get("high", {}).get("url", ""),
            "url": f"https://www.youtube.com/watch?v={vid_id}",
            "description": snip.get("description", "")[:200],
            "tags": ", ".join(snip.get("tags", [])[:8] if stat else []),
            "score": score_video(views, likes, comments, days_ago),
        })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────
# DEMO DATA (когда нет API-ключа)
# ─────────────────────────────────────────────
DEMO_VIDEOS = [
    {
        "platform": "YouTube", "id": "dQw4w9WgXcQ",
        "title": "iPhone 15 Pro Max Screen Replacement - Full Tutorial 2024",
        "channel": "PhoneFixer Pro", "published": "2024-11-05", "days_ago": 14,
        "views": 4_823_000, "likes": 95_400, "comments": 3_200, "duration": "18:42",
        "score": 91, "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "thumbnail": "https://picsum.photos/seed/iphone15/320/180",
        "tags": "iphone,repair,screen replacement,tutorial",
        "description": "Complete guide to replacing iPhone 15 Pro Max screen at home. Tools needed, step-by-step walkthrough."
    },
    {
        "platform": "YouTube", "id": "abc12345",
        "title": "Samsung Galaxy S24 Battery Replacement Under 10 Minutes",
        "channel": "QuickFix Mobile", "published": "2024-11-10", "days_ago": 9,
        "views": 2_190_000, "likes": 58_700, "comments": 1_890, "duration": "9:55",
        "score": 87, "url": "https://www.youtube.com/watch?v=abc12345",
        "thumbnail": "https://picsum.photos/seed/samsung24/320/180",
        "tags": "samsung,battery,repair,galaxy",
        "description": "Fast Samsung S24 battery swap. Watch before you go to a repair shop!"
    },
    {
        "platform": "YouTube", "id": "def67890",
        "title": "STOP Paying for Phone Repairs! Fix These Yourself",
        "channel": "HowToSaveMoney Tech", "published": "2024-10-28", "days_ago": 22,
        "views": 7_540_000, "likes": 212_000, "comments": 9_800, "duration": "14:20",
        "score": 96, "url": "https://www.youtube.com/watch?v=def67890",
        "thumbnail": "https://picsum.photos/seed/stoprepairing/320/180",
        "tags": "diy repair,smartphone,save money,cracked screen",
        "description": "Top 5 smartphone repairs you can do yourself. No experience needed!"
    },
    {
        "platform": "Instagram", "id": "ig_001",
        "title": "Phone repair hack that saves $300 💸 #phonerepair #diy",
        "channel": "@mobilefixmaster", "published": "2024-11-14", "days_ago": 5,
        "views": 8_200_000, "likes": 430_000, "comments": 12_400, "duration": "0:55",
        "score": 98, "url": "https://www.instagram.com/p/ig_001/",
        "thumbnail": "https://picsum.photos/seed/ighack/320/180",
        "tags": "#phonerepair,#diy,#moneysaving,#iphone",
        "description": "This ONE trick will save you $300 at the repair shop. Watch till end!"
    },
    {
        "platform": "TikTok", "id": "tt_001",
        "title": "Dropped my iPhone and FIXED it for $12 🤯",
        "channel": "@techsaverz", "published": "2024-11-13", "days_ago": 6,
        "views": 15_700_000, "likes": 1_200_000, "comments": 28_000, "duration": "0:45",
        "score": 99, "url": "https://www.tiktok.com/@techsaverz/video/tt_001",
        "thumbnail": "https://picsum.photos/seed/ttiphone/320/180",
        "tags": "#iphone,#phonerepair,#lifehack,#viral",
        "description": "Cracked screen fix for just $12. The repair shop wanted $300!"
    },
    {
        "platform": "TikTok", "id": "tt_002",
        "title": "Day in the life of a phone repair shop 📱",
        "channel": "@fixitfast_phones", "published": "2024-11-08", "days_ago": 11,
        "views": 6_340_000, "likes": 485_000, "comments": 14_200, "duration": "1:05",
        "score": 93, "url": "https://www.tiktok.com/@fixitfast_phones/video/tt_002",
        "thumbnail": "https://picsum.photos/seed/dayinlife/320/180",
        "tags": "#phonerepair,#dayinlife,#smallbusiness,#tech",
        "description": "Behind the scenes of my phone repair shop. We fix 50+ phones a day!"
    },
    {
        "platform": "YouTube", "id": "ghi11122",
        "title": "Best Budget Smartphones 2024 - Top 10 Under $300",
        "channel": "MrMobile [Michael Fisher]", "published": "2024-11-01", "days_ago": 18,
        "views": 3_280_000, "likes": 87_600, "comments": 4_200, "duration": "22:15",
        "score": 89, "url": "https://www.youtube.com/watch?v=ghi11122",
        "thumbnail": "https://picsum.photos/seed/budget2024/320/180",
        "tags": "budget phone,review,under 300,best smartphones 2024",
        "description": "The best budget phones you can buy right now. Tested for 30 days each."
    },
    {
        "platform": "Instagram", "id": "ig_002",
        "title": "Before vs After phone restoration 😮 #phonerestoration",
        "channel": "@restore_tech", "published": "2024-11-12", "days_ago": 7,
        "views": 4_100_000, "likes": 310_000, "comments": 7_800, "duration": "0:38",
        "score": 94, "url": "https://www.instagram.com/p/ig_002/",
        "thumbnail": "https://picsum.photos/seed/beforeafter/320/180",
        "tags": "#phonerestoration,#satisfying,#repair,#transformation",
        "description": "Transforming a destroyed Samsung into like-new condition. Satisfying!"
    },
    {
        "platform": "YouTube", "id": "jkl33344",
        "title": "iPhone vs Samsung - Which Breaks Easier? Drop Test 2024",
        "channel": "EverythingApplePro", "published": "2024-10-25", "days_ago": 25,
        "views": 9_150_000, "likes": 198_000, "comments": 15_600, "duration": "11:08",
        "score": 95, "url": "https://www.youtube.com/watch?v=jkl33344",
        "thumbnail": "https://picsum.photos/seed/droptest/320/180",
        "tags": "drop test,iphone vs samsung,durability,2024",
        "description": "100 drop tests between iPhone 15 Pro and Samsung S24 Ultra. Results will shock you!"
    },
    {
        "platform": "TikTok", "id": "tt_003",
        "title": "POV: Customer brings water-damaged iPhone 💧",
        "channel": "@phonerepairking", "published": "2024-11-11", "days_ago": 8,
        "views": 11_200_000, "likes": 890_000, "comments": 22_000, "duration": "0:52",
        "score": 97, "url": "https://www.tiktok.com/@phonerepairking/video/tt_003",
        "thumbnail": "https://picsum.photos/seed/waterdamage/320/180",
        "tags": "#phonerepair,#waterdamage,#iphone,#pov",
        "description": "POV series — most satisfying phone repairs. Water damage recovery."
    },
    {
        "platform": "YouTube", "id": "mno55566",
        "title": "Xiaomi 14 Ultra Full Review — Best Camera Phone 2024?",
        "channel": "MKBHD", "published": "2024-10-30", "days_ago": 20,
        "views": 5_670_000, "likes": 143_000, "comments": 8_900, "duration": "19:44",
        "score": 90, "url": "https://www.youtube.com/watch?v=mno55566",
        "thumbnail": "https://picsum.photos/seed/xiaomi14/320/180",
        "tags": "xiaomi,review,camera,flagship 2024",
        "description": "Is Xiaomi 14 Ultra the best camera phone? After 3 weeks of testing, here's my verdict."
    },
    {
        "platform": "Instagram", "id": "ig_003",
        "title": "5 signs your phone needs repair TODAY ⚠️",
        "channel": "@phonedoctor_official", "published": "2024-11-09", "days_ago": 10,
        "views": 2_800_000, "likes": 187_000, "comments": 5_600, "duration": "1:10",
        "score": 85, "url": "https://www.instagram.com/p/ig_003/",
        "thumbnail": "https://picsum.photos/seed/signrepair/320/180",
        "tags": "#phonerepair,#tips,#smartphone,#tech",
        "description": "Don't ignore these warning signs — your phone is trying to tell you something!"
    },
]

DEMO_TRENDS = [
    {"tag": "#phonerepair", "platform": "TikTok", "videos": 284000, "growth": "+42%"},
    {"tag": "screen replacement tutorial", "platform": "YouTube", "videos": 48000, "growth": "+28%"},
    {"tag": "#iphonerepair", "platform": "Instagram", "videos": 195000, "growth": "+35%"},
    {"tag": "battery replacement", "platform": "YouTube", "videos": 62000, "growth": "+19%"},
    {"tag": "#satisfying repair", "platform": "TikTok", "videos": 412000, "growth": "+67%"},
    {"tag": "phone restoration", "platform": "YouTube", "videos": 31000, "growth": "+55%"},
    {"tag": "#budgetphone2024", "platform": "TikTok", "videos": 88000, "growth": "+22%"},
    {"tag": "water damage fix", "platform": "Instagram", "videos": 74000, "growth": "+31%"},
    {"tag": "POV repair shop", "platform": "TikTok", "videos": 156000, "growth": "+89%"},
    {"tag": "before after restoration", "platform": "Instagram", "videos": 230000, "growth": "+44%"},
]


# ─────────────────────────────────────────────
# SIDEBAR SETTINGS
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📱 SmartTrend Analyzer")
    st.markdown("*Анализ трендовых видео*\n*для магазинов смартфонов*")
    st.markdown("---")

    st.markdown("### 🔑 API Ключи")
    yt_api_key = st.text_input(
        "YouTube Data API v3",
        type="password",
        help="Получить на console.cloud.google.com → YouTube Data API v3",
        placeholder="AIzaSy..."
    )
    apify_token = st.text_input(
        "Apify Token (Instagram/TikTok)",
        type="password",
        help="Получить на apify.com → Settings → Integrations",
        placeholder="apify_api_..."
    )

    use_demo = not bool(yt_api_key)
    if use_demo:
        st.markdown("""
        <div style='background:#1a2a1a;border-left:3px solid #66bb6a;padding:10px;
        border-radius:0 6px 6px 0;font-size:0.82rem;color:#a5d6a7;margin-top:8px;'>
        🟢 <b>Демо режим</b> — показаны реальные примеры трендовых видео.<br>
        Добавьте YouTube API ключ для живого поиска.
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 🔍 Параметры поиска")

    query_preset = st.selectbox("Тематика", [
        "smartphone repair",
        "phone screen replacement",
        "iphone repair tutorial",
        "samsung repair",
        "phone battery replacement",
        "used phone buying guide",
        "phone restoration",
        "cracked screen fix",
        "📝 Свой запрос...",
    ])
    if query_preset == "📝 Свой запрос...":
        search_query = st.text_input("Введите запрос:", "phone repair shop")
    else:
        search_query = query_preset

    platforms = st.multiselect(
        "Платформы",
        ["YouTube", "Instagram", "TikTok"],
        default=["YouTube", "Instagram", "TikTok"],
    )

    col1, col2 = st.columns(2)
    with col1:
        max_results = st.selectbox("Кол-во видео", [10, 25, 50], index=1)
    with col2:
        region = st.selectbox("Регион", ["US", "GB", "DE", "AU", "CA"], index=0)

    date_range = st.slider(
        "Опубликованы (дней назад)", 1, 365, 90
    )

    sort_by = st.selectbox("Сортировка", [
        "score", "views", "likes", "comments", "days_ago"
    ], format_func=lambda x: {
        "score": "🔥 Рейтинг залётности",
        "views": "👁 Просмотры",
        "likes": "👍 Лайки",
        "comments": "💬 Комментарии",
        "days_ago": "📅 Дата (новее)",
    }.get(x, x))

    st.markdown("---")
    run_btn = st.button("🚀 Запустить анализ", use_container_width=True, type="primary")
    st.markdown("---")
    st.markdown("""
    <div style='font-size:0.75rem;color:#666;'>
    <b>Источники данных:</b><br>
    • YouTube Data API v3<br>
    • Instagram via Apify<br>
    • TikTok via Apify<br><br>
    <b>Метрика «залётности»</b> учитывает:<br>
    просмотры, engagement rate,<br>
    свежесть и скорость набора просмотров
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# MAIN CONTENT
# ─────────────────────────────────────────────
st.markdown("# 📱 SmartTrend Analyzer")
st.markdown("**Анализ трендовых видео** по теме ремонта и продажи смартфонов")

if use_demo:
    st.markdown("""
    <div class='demo-banner'>
    ℹ️ <b>Демо-режим:</b> отображаются образцовые данные. 
    Добавьте <b>YouTube Data API v3</b> ключ в боковую панель для живого анализа.
    Для Instagram и TikTok требуется <b>Apify Token</b>.
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def load_youtube_data(api_key, query, max_results, region, days):
    published_after = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    items = yt_search(api_key, query, max_results, "viewCount", published_after, region)
    if not items:
        return pd.DataFrame()
    video_ids = [i.get("id", {}).get("videoId") for i in items if i.get("id", {}).get("videoId")]
    stats = yt_video_stats(api_key, video_ids) if video_ids else {}
    df = build_youtube_df(items, stats)
    return df

if run_btn or "df_videos" not in st.session_state:
    with st.spinner("Загрузка данных..."):
        if use_demo:
            # Фильтруем демо по платформам
            df = pd.DataFrame(DEMO_VIDEOS)
            df = df[df["platform"].isin(platforms)]
            if sort_by == "days_ago":
                df = df.sort_values("days_ago")
            else:
                df = df.sort_values(sort_by, ascending=False)
            st.session_state["df_videos"] = df
            st.session_state["trends"] = DEMO_TRENDS
        else:
            frames = []
            if "YouTube" in platforms and yt_api_key:
                yt_df = load_youtube_data(yt_api_key, search_query, max_results, region, date_range)
                if not yt_df.empty:
                    frames.append(yt_df)
            # Instagram / TikTok через Apify (заглушка с уведомлением)
            if ("Instagram" in platforms or "TikTok" in platforms) and not apify_token:
                st.info("💡 Для анализа Instagram и TikTok добавьте Apify Token. Данные YouTube загружены.")
            if frames:
                df = pd.concat(frames, ignore_index=True)
                if sort_by == "days_ago":
                    df = df.sort_values("days_ago")
                else:
                    df = df.sort_values(sort_by, ascending=False)
                st.session_state["df_videos"] = df
            else:
                st.warning("Нет данных. Проверьте API ключ или включите демо-режим.")
                st.session_state["df_videos"] = pd.DataFrame(DEMO_VIDEOS)
            st.session_state["trends"] = DEMO_TRENDS

df = st.session_state.get("df_videos", pd.DataFrame(DEMO_VIDEOS))
trends = st.session_state.get("trends", DEMO_TRENDS)

if df.empty:
    st.warning("Нет видео для отображения.")
    st.stop()


# ─────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🔥 Топ видео",
    "📊 Аналитика",
    "📈 Тренды",
    "🎬 Референсы",
    "⚙️ Настройка API",
])


# ════════════════════════════════════════════
# TAB 1: ТОП ВИДЕО
# ════════════════════════════════════════════
with tab1:
    # KPI Row
    total_views = df["views"].sum()
    avg_score = df["score"].mean()
    top_video = df.iloc[0] if not df.empty else None
    avg_engagement = ((df["likes"] + df["comments"]) / df["views"].replace(0, 1)).mean() * 100

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class='kpi-card'>
            <div class='kpi-value'>{fmt_number(total_views)}</div>
            <div class='kpi-label'>Суммарные просмотры</div>
            <div class='kpi-delta up'>▲ {len(df)} видео проанализировано</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class='kpi-card'>
            <div class='kpi-value'>{avg_score:.0f}/100</div>
            <div class='kpi-label'>Средний рейтинг «залётности»</div>
            <div class='kpi-delta up'>▲ {'Высокий' if avg_score > 75 else 'Средний'} потенциал</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class='kpi-card'>
            <div class='kpi-value'>{avg_engagement:.2f}%</div>
            <div class='kpi-label'>Средний Engagement Rate</div>
            <div class='kpi-delta {'up' if avg_engagement > 3 else 'down'}'>
            {'▲ Выше среднего' if avg_engagement > 3 else '▽ Ниже среднего'}</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        plat_counts = df["platform"].value_counts()
        best_plat = plat_counts.idxmax() if not plat_counts.empty else "—"
        st.markdown(f"""
        <div class='kpi-card'>
            <div class='kpi-value'>{best_plat}</div>
            <div class='kpi-label'>Самая активная платформа</div>
            <div class='kpi-delta up'>▲ {plat_counts.max() if not plat_counts.empty else 0} видео</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Platform filter
    plat_filter = st.radio("Фильтр платформы:", ["Все"] + list(df["platform"].unique()),
                            horizontal=True)
    show_df = df if plat_filter == "Все" else df[df["platform"] == plat_filter]

    # Score threshold
    min_score = st.slider("Минимальный рейтинг залётности:", 0, 100, 50)
    show_df = show_df[show_df["score"] >= min_score]

    st.markdown(f"**Показано видео:** {len(show_df)}")
    st.markdown("---")

    # Video cards
    for i, row in show_df.iterrows():
        plat_badge_cls = {"YouTube": "badge-yt", "Instagram": "badge-ig", "TikTok": "badge-tt"}.get(row["platform"], "")
        hot = "🔥" if row["score"] >= 90 else ""
        score_pct = row["score"]

        col_img, col_info = st.columns([1, 3])
        with col_img:
            if row.get("thumbnail"):
                st.image(row["thumbnail"], width=200)
        with col_info:
            st.markdown(f"""
            <div class='video-card'>
                <div>
                    <span class='badge {plat_badge_cls}'>{row['platform']}</span>
                    {'<span class="badge badge-hot">🔥 Горячее</span>' if score_pct >= 90 else ''}
                    {'<span class="badge badge-trending">📈 Тренд</span>' if score_pct >= 80 else ''}
                </div>
                <div class='video-title' style='margin-top:8px;'>{hot} {row['title']}</div>
                <div class='video-meta'>
                    📺 {row.get('channel','—')} &nbsp;|&nbsp;
                    📅 {row.get('published','—')} ({row.get('days_ago',0)} дн. назад) &nbsp;|&nbsp;
                    ⏱ {row.get('duration','—')}
                </div>
                <div class='video-stats'>
                    👁 {fmt_number(row['views'])} &nbsp;&nbsp;
                    👍 {fmt_number(row['likes'])} &nbsp;&nbsp;
                    💬 {fmt_number(row['comments'])}
                </div>
                <div style='margin-top:8px;font-size:0.8rem;color:#9e9e9e;'>{row.get('description','')[:120]}...</div>
                <div style='margin-top:10px;display:flex;align-items:center;gap:10px;'>
                    <span style='font-size:0.8rem;color:#bbb;'>Рейтинг залётности:</span>
                    <b style='color:#4fc3f7;'>{score_pct}/100</b>
                    <div class='score-bar-wrap' style='flex:1;'>
                        <div class='score-bar-fill' style='width:{score_pct}%;'></div>
                    </div>
                </div>
                <div style='margin-top:8px;'>
                    <a href='{row["url"]}' target='_blank' style='color:#4fc3f7;font-size:0.83rem;'>
                    🔗 Открыть видео →</a>
                </div>
            </div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════
# TAB 2: АНАЛИТИКА
# ════════════════════════════════════════════
with tab2:
    st.markdown("<div class='section-header'>📊 Аналитика видео</div>", unsafe_allow_html=True)

    # Row 1: Views distribution + Platform breakdown
    col_a, col_b = st.columns(2)

    with col_a:
        fig_views = px.bar(
            df.head(12).sort_values("views"),
            x="views", y="title",
            orientation="h",
            color="platform",
            color_discrete_map={"YouTube": "#ff4444", "Instagram": "#c13584", "TikTok": "#00f2ea"},
            title="Топ видео по просмотрам",
            labels={"views": "Просмотры", "title": ""},
        )
        fig_views.update_layout(
            plot_bgcolor="#1e1e2e", paper_bgcolor="#1e1e2e",
            font_color="#e0e0e0", height=400,
            yaxis=dict(tickfont=dict(size=10)),
            showlegend=True,
        )
        fig_views.update_xaxes(gridcolor="#2a2a3e")
        st.plotly_chart(fig_views, use_container_width=True)

    with col_b:
        plat_stats = df.groupby("platform").agg(
            total_views=("views", "sum"),
            avg_score=("score", "mean"),
            count=("id", "count"),
        ).reset_index()
        fig_pie = px.pie(
            plat_stats, names="platform", values="total_views",
            color="platform",
            color_discrete_map={"YouTube": "#ff4444", "Instagram": "#c13584", "TikTok": "#00f2ea"},
            title="Доля просмотров по платформам",
            hole=0.4,
        )
        fig_pie.update_layout(
            plot_bgcolor="#1e1e2e", paper_bgcolor="#1e1e2e",
            font_color="#e0e0e0", height=400,
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    # Row 2: Score vs Views scatter + Engagement
    col_c, col_d = st.columns(2)

    with col_c:
        fig_scatter = px.scatter(
            df, x="views", y="score", size="likes",
            color="platform",
            color_discrete_map={"YouTube": "#ff4444", "Instagram": "#c13584", "TikTok": "#00f2ea"},
            hover_data=["title", "channel", "days_ago"],
            title="Рейтинг залётности vs Просмотры",
            labels={"views": "Просмотры", "score": "Рейтинг залётности"},
            size_max=30,
        )
        fig_scatter.update_layout(
            plot_bgcolor="#1e1e2e", paper_bgcolor="#1e1e2e",
            font_color="#e0e0e0", height=400,
        )
        fig_scatter.update_xaxes(gridcolor="#2a2a3e")
        fig_scatter.update_yaxes(gridcolor="#2a2a3e")
        st.plotly_chart(fig_scatter, use_container_width=True)

    with col_d:
        df["engagement"] = (df["likes"] + df["comments"] * 3) / df["views"].replace(0, 1) * 100
        top_eng = df.nlargest(10, "engagement")[["title", "platform", "engagement", "views"]]
        fig_eng = px.bar(
            top_eng.sort_values("engagement"),
            x="engagement", y="title", orientation="h",
            color="platform",
            color_discrete_map={"YouTube": "#ff4444", "Instagram": "#c13584", "TikTok": "#00f2ea"},
            title="Топ по Engagement Rate (%)",
            labels={"engagement": "Engagement %", "title": ""},
        )
        fig_eng.update_layout(
            plot_bgcolor="#1e1e2e", paper_bgcolor="#1e1e2e",
            font_color="#e0e0e0", height=400,
            yaxis=dict(tickfont=dict(size=10)),
        )
        st.plotly_chart(fig_eng, use_container_width=True)

    # Row 3: Timeline
    df_time = df.copy()
    df_time["published_date"] = pd.to_datetime(df_time["published"], errors="coerce")
    df_time = df_time.dropna(subset=["published_date"])
    if not df_time.empty:
        timeline = df_time.groupby([df_time["published_date"].dt.to_period("W").astype(str), "platform"])["views"].sum().reset_index()
        timeline.columns = ["week", "platform", "views"]
        fig_timeline = px.line(
            timeline, x="week", y="views", color="platform",
            color_discrete_map={"YouTube": "#ff4444", "Instagram": "#c13584", "TikTok": "#00f2ea"},
            title="Динамика просмотров по неделям",
            markers=True,
        )
        fig_timeline.update_layout(
            plot_bgcolor="#1e1e2e", paper_bgcolor="#1e1e2e",
            font_color="#e0e0e0", height=320,
            xaxis=dict(gridcolor="#2a2a3e"),
            yaxis=dict(gridcolor="#2a2a3e"),
        )
        st.plotly_chart(fig_timeline, use_container_width=True)

    # Data table
    st.markdown("### 📋 Таблица данных")
    display_cols = ["platform", "title", "channel", "published", "views", "likes", "comments", "score"]
    st.dataframe(
        df[display_cols].rename(columns={
            "platform": "Платформа", "title": "Заголовок", "channel": "Канал",
            "published": "Дата", "views": "Просмотры", "likes": "Лайки",
            "comments": "Комментарии", "score": "Рейтинг 🔥",
        }),
        use_container_width=True, hide_index=True,
        column_config={
            "Просмотры": st.column_config.NumberColumn(format="%d"),
            "Рейтинг 🔥": st.column_config.ProgressColumn(
                min_value=0, max_value=100, format="%d",
            ),
        }
    )

    # Export
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Экспортировать CSV",
        data=csv,
        file_name=f"smarttrend_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
    )


# ════════════════════════════════════════════
# TAB 3: ТРЕНДЫ
# ════════════════════════════════════════════
with tab3:
    st.markdown("<div class='section-header'>📈 Трендовые хэштеги и запросы</div>", unsafe_allow_html=True)

    trends_df = pd.DataFrame(trends)

    col_e, col_f = st.columns(2)
    with col_e:
        fig_trends = px.bar(
            trends_df.sort_values("videos", ascending=True),
            x="videos", y="tag", orientation="h",
            color="platform",
            color_discrete_map={"YouTube": "#ff4444", "Instagram": "#c13584", "TikTok": "#00f2ea"},
            title="Трендовые теги по кол-ву видео",
            labels={"videos": "Кол-во видео", "tag": ""},
        )
        fig_trends.update_layout(
            plot_bgcolor="#1e1e2e", paper_bgcolor="#1e1e2e",
            font_color="#e0e0e0", height=420,
        )
        st.plotly_chart(fig_trends, use_container_width=True)

    with col_f:
        # Growth chart
        trends_df["growth_val"] = trends_df["growth"].str.replace("%", "").str.replace("+", "").astype(float)
        fig_growth = px.bar(
            trends_df.sort_values("growth_val", ascending=True),
            x="growth_val", y="tag", orientation="h",
            color="growth_val",
            color_continuous_scale=["#1565c0", "#00e676"],
            title="Рост за 30 дней (%)",
            labels={"growth_val": "Рост %", "tag": ""},
        )
        fig_growth.update_layout(
            plot_bgcolor="#1e1e2e", paper_bgcolor="#1e1e2e",
            font_color="#e0e0e0", height=420,
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig_growth, use_container_width=True)

    # Trending tags visual display
    st.markdown("### 🏷️ Горячие теги прямо сейчас")
    tags_html = ""
    for _, tr in trends_df.sort_values("growth_val", ascending=False).iterrows():
        color = "#c13584" if tr["platform"] == "Instagram" else (
            "#00796b" if tr["platform"] == "TikTok" else "#c62828"
        )
        tags_html += f"""<span style='display:inline-block;background:{color}22;
        border:1px solid {color};color:{color};padding:5px 14px;border-radius:20px;
        margin:4px;font-size:0.85rem;font-weight:600;'>
        {tr['tag']} <span style='opacity:0.8;font-size:0.75rem;'>{tr['growth']} ↑</span>
        </span>"""
    st.markdown(f"<div style='line-height:2.5;'>{tags_html}</div>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📰 Ключевые инсайты по трендам")
    col_i1, col_i2, col_i3 = st.columns(3)
    with col_i1:
        st.markdown("""
        **🔥 Форматы, которые «залетают»**
        - POV-видео из ремонтного цеха
        - Before/After восстановление
        - «Починил за N рублей» хуки
        - Быстрые (до 60 сек) ремонты
        - Drop-test сравнения
        """)
    with col_i2:
        st.markdown("""
        **📅 Оптимальная длина видео**
        - TikTok/Reels: 30-90 сек
        - YouTube Shorts: 15-60 сек
        - YouTube long-form: 8-20 мин
        - Самый высокий ER у 45-75 сек
        """)
    with col_i3:
        st.markdown("""
        **💡 Успешные сценарии видео**
        - Клиент принёс убитый телефон
        - Ремонт в реальном времени
        - «Не неси в сервис, сделай сам»
        - Сколько стоит vs сколько реально
        - Восстановление редких моделей
        """)


# ════════════════════════════════════════════
# TAB 4: РЕФЕРЕНСЫ
# ════════════════════════════════════════════
with tab4:
    st.markdown("<div class='section-header'>🎬 Лучшие референсы для AI-генерации</div>", unsafe_allow_html=True)
    st.markdown("Топ видео для создания похожего контента с помощью нейросетей")

    top_refs = df.nlargest(6, "score")

    for i, row in top_refs.iterrows():
        with st.expander(f"🔥 #{list(top_refs.index).index(i)+1} — {row['title'][:70]}... | Score: {row['score']}/100"):
            c1, c2 = st.columns([1, 2])
            with c1:
                if row.get("thumbnail"):
                    st.image(row["thumbnail"])
                st.markdown(f"**Платформа:** {row['platform']}")
                st.markdown(f"**Канал:** {row.get('channel','—')}")
                st.markdown(f"**Просмотры:** {fmt_number(row['views'])}")
                st.markdown(f"**Лайки:** {fmt_number(row['likes'])}")
                st.markdown(f"**Длина:** {row.get('duration','—')}")
                st.markdown(f"[🔗 Открыть]({row['url']})")
            with c2:
                st.markdown("**📋 Почему это залетает:**")
                score = row["score"]
                er = (row["likes"] + row["comments"] * 3) / max(row["views"], 1) * 100
                reasons = []
                if row["views"] > 5_000_000:
                    reasons.append("✅ Массовый охват (5M+ просмотров)")
                if er > 3:
                    reasons.append(f"✅ Высокий engagement rate ({er:.1f}%)")
                if row["days_ago"] <= 14:
                    reasons.append("✅ Актуальный контент (< 2 нед.)")
                if "iphone" in row["title"].lower():
                    reasons.append("✅ iPhone — самая ищемая тема")
                if any(w in row["title"].lower() for w in ["fix", "repair", "replace"]):
                    reasons.append("✅ Практическая ценность (DIY)")
                if any(w in row["title"].lower() for w in ["$", "save", "stop paying", "cheap"]):
                    reasons.append("✅ Денежный триггер (экономия)")
                if row.get("duration","") and ":" in row.get("duration",""):
                    secs = sum(int(x) * 60**i for i, x in enumerate(reversed(row["duration"].split(":"))))
                    if secs < 120:
                        reasons.append("✅ Короткий формат (<2 мин) = высокий досмотр")
                for r in reasons:
                    st.markdown(r)

                st.markdown("**🤖 Идеи для AI-генерации:**")
                st.markdown(f"""
                - **Хук:** Начни с крупного плана повреждения телефона + цифры экономии
                - **Формат:** Повтори структуру "{row['title'][:40]}..." для своего магазина
                - **Теги:** {row.get('tags','—')[:100]}
                - **CTA:** «Приходи в [название магазина] — починим как здесь»
                """)


# ════════════════════════════════════════════
# TAB 5: НАСТРОЙКА API
# ════════════════════════════════════════════
with tab5:
    st.markdown("<div class='section-header'>⚙️ Настройка источников данных</div>", unsafe_allow_html=True)

    st.markdown("### 🔴 YouTube Data API v3 (бесплатно)")
    st.markdown("""
    <div class='api-info'>
    <b>Квота:</b> 10,000 единиц/день бесплатно. Поиск — 100 ед./запрос, статистика — 1 ед./запрос.<br>
    <b>Что даёт:</b> Поиск по ключевым словам, просмотры, лайки, комментарии, длина видео, теги, обложки.
    </div>
    """, unsafe_allow_html=True)

    with st.expander("📖 Как получить YouTube API ключ (бесплатно)"):
        st.markdown("""
        1. Перейди на [console.cloud.google.com](https://console.cloud.google.com)
        2. Создай новый проект (кнопка вверху)
        3. Перейди в **APIs & Services → Library**
        4. Найди **YouTube Data API v3** → нажми **Enable**
        5. Перейди в **APIs & Services → Credentials**
        6. Нажми **+ CREATE CREDENTIALS → API key**
        7. Скопируй ключ в боковую панель приложения
        
        **💡 Совет:** Ограничь ключ только YouTube Data API для безопасности.
        """)

    st.markdown("---")
    st.markdown("### 🟣 Instagram Reels (через Apify)")
    st.markdown("""
    <div class='api-info'>
    <b>Стоимость:</b> $5/месяц (free trial доступен). Или использовать <code>reelscraper</code> Python-пакет напрямую.<br>
    <b>Что даёт:</b> Views, likes, комментарии, описание, хэштеги, обложки Reels по хэштегу/аккаунту.
    </div>
    """, unsafe_allow_html=True)

    with st.expander("📖 Как подключить Instagram через Apify"):
        st.markdown("""
        **Вариант 1: Apify (рекомендуется)**
        1. Зарегистрируйся на [apify.com](https://apify.com)
        2. Перейди в Settings → Integrations → API tokens
        3. Нажми **Create new token** → скопируй
        4. Используй актор `apify/instagram-hashtag-scraper`
        
        ```python
        import httpx
        
        APIFY_TOKEN = "твой_токен"
        actor_id = "apify/instagram-hashtag-scraper"
        
        # Запуск актора
        run = httpx.post(
            f"https://api.apify.com/v2/acts/{actor_id}/runs",
            json={"hashtags": ["phonerepair", "smartphonerepair"], "resultsLimit": 50},
            params={"token": APIFY_TOKEN}
        ).json()
        ```
        
        **Вариант 2: reelscraper (Python, бесплатно)**
        ```bash
        pip install reelscraper
        ```
        ```python
        from reelscraper import ReelScraper
        scraper = ReelScraper(timeout=30)
        reels = scraper.get_user_reels("mobilefixmaster", max_posts=20)
        ```
        """)

    st.markdown("---")
    st.markdown("### 🟢 TikTok (через Apify или TikTok API)")
    with st.expander("📖 Как получить данные TikTok"):
        st.markdown("""
        **Вариант 1: Apify TikTok Trending Scraper**
        - Актор: `apify/tiktok-hashtag-scraper`
        - Поддерживает поиск по хэштегам без авторизации
        
        **Вариант 2: TikTok Research API (официальный)**
        - Подача заявки на [developers.tiktok.com](https://developers.tiktok.com)
        - Бесплатно для исследователей
        - Ограничение: 1000 видео/день
        
        **Вариант 3: TikTok-Api (неофициальный Python)**
        ```bash
        pip install TikTokApi playwright
        playwright install
        ```
        ```python
        from TikTokApi import TikTokApi
        with TikTokApi() as api:
            tag = api.hashtag(name="phonerepair")
            for video in tag.videos(count=30):
                print(video.stats)
        ```
        """)

    st.markdown("---")
    st.markdown("### 🔧 requirements.txt для деплоя")
    st.code("""streamlit>=1.32
pandas>=2.0
plotly>=5.18
requests>=2.31
reelscraper>=1.1
httpx>=0.27
TikTokApi>=6.3
google-api-python-client>=2.100
""", language="text")

    st.markdown("### 🚀 Запуск приложения")
    st.code("""# Установка зависимостей
pip install -r requirements.txt

# Запуск
streamlit run app.py

# С переменными окружения (рекомендуется)
YOUTUBE_API_KEY=AIzaSy... APIFY_TOKEN=apify_api_... streamlit run app.py
""", language="bash")

