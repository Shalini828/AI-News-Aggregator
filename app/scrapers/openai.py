from datetime import datetime, timedelta, timezone
from typing import List, Optional
import os
import feedparser
from pydantic import BaseModel
from openai import OpenAI


# -------------------- MODEL --------------------

class OpenAIArticle(BaseModel):
    title: str
    description: str
    url: str
    guid: str
    published_at: datetime
    category: Optional[str] = None
    summary: Optional[str] = None


# -------------------- SCRAPER --------------------

class OpenAIScraper:
    def __init__(self):
        self.rss_url = "https://openai.com/news/rss.xml"
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # -------------------- FETCH ARTICLES --------------------

    def get_articles(self, hours: int = 24) -> List[OpenAIArticle]:
        feed = feedparser.parse(self.rss_url)

        if not feed.entries:
            return []

        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(hours=hours)
        articles = []

        for entry in feed.entries:
            published_parsed = getattr(entry, "published_parsed", None)
            if not published_parsed:
                continue

            published_time = datetime(*published_parsed[:6], tzinfo=timezone.utc)

            if published_time >= cutoff_time:
                articles.append(OpenAIArticle(
                    title=entry.get("title", ""),
                    description=entry.get("description", ""),
                    url=entry.get("link", ""),
                    guid=entry.get("id", entry.get("link", "")),
                    published_at=published_time,
                    category=entry.get("tags", [{}])[0].get("term") if entry.get("tags") else None
                ))

        return articles

    # -------------------- AI SUMMARY --------------------

    def summarize(self, text: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an AI news summarizer. Give short and clear summaries."
                    },
                    {
                        "role": "user",
                        "content": f"Summarize this:\n{text}"
                    }
                ],
                max_tokens=150
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            print("⚠️ OpenAI Error:", e)
            return "Summary not available"

    # -------------------- MAIN PIPELINE --------------------

    def get_articles_with_summary(self, hours: int = 24) -> List[OpenAIArticle]:
        articles = self.get_articles(hours)
        result = []

        for article in articles:
            print(f"🧠 Summarizing: {article.title}")

            content = article.description or article.title
            summary = self.summarize(content)

            result.append(
                article.model_copy(update={"summary": summary})
            )

        return result


# -------------------- TEST --------------------

if __name__ == "__main__":
    scraper = OpenAIScraper()

    articles = scraper.get_articles_with_summary(hours=50)

    for article in articles:
        print("\n📰", article.title)
        print("🔗", article.url)
        print("🧠 Summary:", article.summary)
        print("-" * 50)