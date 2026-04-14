

import os
import requests
import feedparser
from datetime import datetime
import pytz
from apscheduler.schedulers.blocking import BlockingScheduler
from googleapiclient.discovery import build



TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID")
YOUTUBE_API_KEY    = os.environ.get("YOUTUBE_API_KEY")
RAPIDAPI_KEY       = os.environ.get("RAPIDAPI_KEY")
TEAMS_WEBHOOK_URL = os.environ.get("TEAMS_WEBHOOK_URL")

YOUTUBE_CHANNEL_IDS = [
    "UCbmNph6atAoGfqLoCL_duAg",   # Andrej Karpathy
    "UCWX3yGbODI3HLa1J4M5L1_w",   # Two Minute Papers
    "UCnUYZLuoy1rq1aVMwx4aTzw",   # AI Explained
    "UCBcRF18a7Qf58cCRy5xuWwQ",   # Matt Wolfe
    "UCCwH3J7J5pJEKXa2vm2BHIQ",   # Wes Roth
]

# ── Subreddits to scan ──
SUBREDDITS = [
    "artificial",
    "AItools",
    "MachineLearning",
    "ChatGPT",
    "singularity",
]

# ── Google News search queries ──
GOOGLE_NEWS_QUERIES = [
    "AI business growth",
    "artificial intelligence enterprise 2025",
    "AI productivity tools",
]




def fetch_reddit_news(limit=5):
    print("  Fetching Reddit...")
    posts = []
    for sub in SUBREDDITS:
        try:
            url  = f"https://www.reddit.com/r/{sub}/hot/.rss"
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                title = entry.title.strip()
                if len(title) > 20:
                    posts.append({
                        "title":  title,
                        "url":    entry.link,
                        "source": f"Reddit · r/{sub}",
                    })
        except Exception as e:
            print(f"    Reddit r/{sub} error: {e}")
    return posts[:limit]




def fetch_google_news(limit=5):
    print("  Fetching Google News...")
    articles = []
    for query in GOOGLE_NEWS_QUERIES:
        try:
            q    = query.replace(" ", "+")
            url  = f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                articles.append({
                    "title":  entry.title.strip(),
                    "url":    entry.link,
                    "source": "Google News",
                })
        except Exception as e:
            print(f"    Google News error: {e}")
    return articles[:limit]


# ══════════════════════════════════════════════════════
#  SOURCE 3 — YOUTUBE (needs YouTube API key)
# ══════════════════════════════════════════════════════

def fetch_youtube_news(limit=3):
    print("  Fetching YouTube...")
    if YOUTUBE_API_KEY == "PASTE_YOUR_YOUTUBE_API_KEY_HERE":
        print("    Skipping YouTube — API key not set.")
        return []
    videos = []
    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        for channel_id in YOUTUBE_CHANNEL_IDS:
            res = youtube.search().list(
                part="snippet",
                channelId=channel_id,
                maxResults=2,
                order="date",
                type="video"
            ).execute()
            for item in res.get("items", []):
                snippet = item["snippet"]
                videos.append({
                    "title":     snippet["title"].strip(),
                    "url":       f"https://youtube.com/watch?v={item['id']['videoId']}",
                    "source":    f"YouTube · {snippet['channelTitle']}",
                    "published": snippet["publishedAt"],
                })
        videos.sort(key=lambda x: x["published"], reverse=True)
    except Exception as e:
        print(f"    YouTube error: {e}")
    return videos[:limit]


# ══════════════════════════════════════════════════════
#  SOURCE 4 — LINKEDIN (via RapidAPI free tier)
# ══════════════════════════════════════════════════════

def fetch_linkedin_news(limit=2):
    print("  Fetching LinkedIn...")
    if RAPIDAPI_KEY == "PASTE_YOUR_RAPIDAPI_KEY_HERE":
        print("    Skipping LinkedIn — RapidAPI key not set.")
        return []
    try:
        url     = "https://linkedin-data-scraper.p.rapidapi.com/search_posts"
        headers = {
            "X-RapidAPI-Key":  RAPIDAPI_KEY,
            "X-RapidAPI-Host": "linkedin-data-scraper.p.rapidapi.com",
        }
        params  = {"keyword": "AI business growth", "count": 10}
        r       = requests.get(url, headers=headers, params=params, timeout=10)
        posts   = r.json().get("data", [])
        results = []
        for post in posts:
            text = post.get("text", "").strip()
            if len(text) > 30:
                results.append({
                    "title":  text[:100] + ("..." if len(text) > 100 else ""),
                    "url":    post.get("url", "https://linkedin.com"),
                    "source": "LinkedIn",
                })
        return results[:limit]
    except Exception as e:
        print(f"    LinkedIn error: {e}")
        return []


# ══════════════════════════════════════════════════════
#  BUILD THE TELEGRAM MESSAGE
# ══════════════════════════════════════════════════════

def build_message():
    print("Building message...")
    ist      = pytz.timezone("Asia/Kolkata")
    date_str = datetime.now(ist).strftime("%d %b %Y")

    gnews    = fetch_google_news(3)
    reddit   = fetch_reddit_news(3)
    linkedin = fetch_linkedin_news(2)
    youtube  = fetch_youtube_news(2)

    pool = gnews[:2] + reddit[:2] + linkedin[:1] + youtube[:1]
    top5 = pool[:5]

    if not top5:
        return "Could not fetch news today. Will retry tomorrow."

    lines = [
        f"*Top 5 AI News for Business*",
        f"Date: {date_str}  |  11:00 AM IST",
        f"--------------------\n",
    ]

    for i, item in enumerate(top5, 1):
        title  = item["title"]
        title  = title[:95] + "..." if len(title) > 95 else title
        source = item.get("source", "")
        url    = item.get("url", "")
        lines.append(f"*{i}.* [{title}]({url})")
        lines.append(f"   _{source}_\n")

    lines.append("--------------------")
    lines.append("_Stay ahead with AI - every morning at 11 AM IST_")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════
#  SEND TO TELEGRAM
# ══════════════════════════════════════════════════════

def send_to_telegram(message):
    print("Sending to Telegram...")
    url     = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id":                  TELEGRAM_CHAT_ID,
        "text":                     message,
        "parse_mode":               "Markdown",
        "disable_web_page_preview": False,
    }
    r = requests.post(url, json=payload, timeout=10)
    if r.ok:
        print(f"  Sent successfully at {datetime.now()}")
    else:
        print(f"  Failed: {r.status_code} - {r.text}")
    return r.ok


# ══════════════════════════════════════════════════════
#  DAILY JOB
# ══════════════════════════════════════════════════════

def send_to_teams(message):
    print("Sending to Teams...")
    if not TEAMS_WEBHOOK_URL:
        print("    Skipping Teams - webhook not set.")
        return
    clean = message.replace("*", "").replace("_", "")
    payload = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.2",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": "Top 5 AI News for Business",
                            "weight": "Bolder",
                            "size": "Medium"
                        },
                        {
                            "type": "TextBlock",
                            "text": clean,
                            "wrap": True
                        }
                    ]
                }
            }
        ]
    }
    try:
        r = requests.post(TEAMS_WEBHOOK_URL, json=payload, timeout=10)
        if r.ok:
            print("  Sent to Teams successfully!")
        else:
            print(f"  Teams failed: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"  Teams error: {e}")


def job():
    print(f"\n{'='*40}")
    print(f"Running job at {datetime.now()}")
    print(f"{'='*40}")
    try:
        msg = build_message()
        send_to_telegram(msg)
        send_to_teams(msg)
    except Exception as e:
        print(f"Job error: {e}")


# ══════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════

if __name__ == "__main__":

    print("AI News Bot - Starting up...")


    #job()

    # --------------------------------------------------
    # SCHEDULED MODE - runs every day at 11 AM IST
    # --------------------------------------------------
    scheduler = BlockingScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(job, "cron", hour=11, minute=0)
    print("Bot is running. Will post daily at 11:00 AM IST.")
    print("Press Ctrl+C to stop.")
    scheduler.start()
