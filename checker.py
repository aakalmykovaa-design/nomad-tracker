import os
import json
import time
import logging
import urllib.parse
import feedparser
from groq import Groq

logger = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.3-70b-versatile"

TOPIC_LABELS = {
    "visa": "визы и въезд",
    "residency": "ВНЖ и переезд",
    "nomad_visa": "цифровая номадская виза",
    "tax": "налоги для иностранцев",
    "banking": "банки и счета для иностранцев",
}


def _search_google_news(query: str, max_results: int = 5) -> list[dict]:
    """Search via Google News RSS — free, no API key, no rate limits."""
    q = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={q}&hl=ru&gl=RU&ceid=RU:ru"
    try:
        feed = feedparser.parse(url)
        results = []
        for entry in feed.entries[:max_results]:
            results.append({
                "title": entry.get("title", ""),
                "summary": entry.get("summary", "")[:300],
            })
        return results
    except Exception as e:
        logger.warning(f"Google News RSS ошибка ({query}): {e}")
        return []


def _build_news_context(country_name: str, citizenship: str) -> str:
    """Collect news from Google News for the country."""
    queries = [
        f"{country_name} виза иммиграция {citizenship} 2025",
        f"{country_name} visa immigration Russian passport 2025",
        f"{country_name} ВНЖ цифровая виза 2025",
    ]

    articles = []
    for q in queries:
        articles.extend(_search_google_news(q, max_results=3))
        if len(articles) >= 6:
            break
        time.sleep(0.5)

    if not articles:
        return "Свежих новостей не найдено."

    seen = set()
    lines = []
    for a in articles:
        title = a["title"]
        if title not in seen:
            seen.add(title)
            lines.append(f"- {title}. {a['summary']}")

    return "\n".join(lines[:6])


def check_countries(countries: list[dict], profile: dict) -> list[dict]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY не задан в .env файле")

    client = Groq(api_key=api_key)
    citizenship = profile.get("citizenship_label", "Россия")
    topics = profile.get("topics", "visa,residency,nomad_visa,tax,banking").split(",")
    topic_str = ", ".join(TOPIC_LABELS.get(t, t) for t in topics)

    results = []

    for country in countries:
        name = country["name"]
        code = country["code"]
        logger.info(f"Проверяю: {name}")

        news_text = _build_news_context(name, citizenship)

        prompt = f"""Ты — эксперт по иммиграции и переезду. Анализируй условия для граждан {citizenship} в {name}.

Темы: {topic_str}

Последние новости:
{news_text}

Верни ТОЛЬКО валидный JSON без markdown-блоков:
{{
  "code": "{code}",
  "has_changes": false,
  "severity": "ok",
  "status_summary": "Краткий текущий статус на русском, 1-2 предложения.",
  "change_title": "",
  "change_detail": ""
}}

Правила severity:
- ok — ничего важного нет
- info — есть свежие новости, без срочности
- warning — важные изменения условий
- urgent — критически срочно, нужно действовать сейчас

has_changes=true и change_title заполни только при реальном новом событии."""

        try:
            resp = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=400,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content
            data = json.loads(raw)
            data["code"] = code
            results.append(data)
            logger.info(f"{name}: severity={data.get('severity')}, changes={data.get('has_changes')}")
        except Exception as e:
            logger.error(f"Ошибка Groq для {name}: {e}")
            results.append({
                "code": code,
                "has_changes": False,
                "severity": "unknown",
                "status_summary": "Ошибка при проверке. Попробуй снова позже.",
                "change_title": "",
                "change_detail": "",
            })

        time.sleep(1.0)

    return results
