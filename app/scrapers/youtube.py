from datetime import datetime, timedelta, timezone
from typing import List, Optional
import os
import time
import feedparser
from pydantic import BaseModel
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound


# -------------------- MODELS --------------------

class Transcript(BaseModel):
    text: str


class ChannelVideo(BaseModel):
    title: str
    url: str
    video_id: str
    published_at: datetime
    description: str
    transcript: Optional[str] = None


# -------------------- SCRAPER --------------------

class YouTubeScraper:
    def __init__(self):
        self.proxies = None  # keep simple for now

    def _get_rss_url(self, channel_id: str) -> str:
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

    def _extract_video_id(self, video_url: str) -> str:
        if "youtube.com/watch?v=" in video_url:
            return video_url.split("v=")[1].split("&")[0]
        if "youtube.com/shorts/" in video_url:
            return video_url.split("shorts/")[1].split("?")[0]
        if "youtu.be/" in video_url:
            return video_url.split("youtu.be/")[1].split("?")[0]
        return video_url

    # -------------------- TRANSCRIPT --------------------

    def get_transcript(self, video_id: str) -> Optional[Transcript]:
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            # 🔥 Try multiple languages
            try:
                transcript = transcript_list.find_transcript(['en'])
            except:
                try:
                    transcript = transcript_list.find_transcript(['hi'])
                except:
                    try:
                        transcript = transcript_list.find_generated_transcript(['en'])
                    except:
                        # fallback: pick ANY available transcript
                        transcript = next(iter(transcript_list))

            fetched = transcript.fetch()
            text = " ".join([snippet['text'] for snippet in fetched])

            return Transcript(text=text)

        except (TranscriptsDisabled, NoTranscriptFound):
            print(f"❌ No transcript for video: {video_id}")
            return None
        except Exception as e:
            print(f"⚠️ Error fetching transcript for {video_id}: {e}")
            return None

    # -------------------- FETCH VIDEOS --------------------

    def get_latest_videos(self, channel_id: str, hours: int = 24) -> List[ChannelVideo]:
        feed = feedparser.parse(self._get_rss_url(channel_id))

        print("📡 Total entries in feed:", len(feed.entries))  # DEBUG

        if not feed.entries:
            return []

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        videos = []

        for entry in feed.entries:
            if "/shorts/" in entry.link:
                continue

            published_time = datetime.fromtimestamp(
                time.mktime(entry.published_parsed),
                tz=timezone.utc
            )

            # 🔥 IMPORTANT: keep filter but adjustable
            if published_time >= cutoff_time:
                video_id = self._extract_video_id(entry.link)

                videos.append(ChannelVideo(
                    title=entry.title,
                    url=entry.link,
                    video_id=video_id,
                    published_at=published_time,
                    description=entry.get("summary", "")
                ))

        return videos

    # -------------------- MAIN SCRAPER --------------------

    def scrape_channel(self, channel_id: str, hours: int = 1000) -> List[ChannelVideo]:
        videos = self.get_latest_videos(channel_id, hours)

        print(f"🎥 Videos found: {len(videos)}")  # DEBUG

        result = []

        for video in videos:
            print(f"➡️ Processing: {video.title}")

            transcript = self.get_transcript(video.video_id)

            result.append(
                video.model_copy(
                    update={
                        "transcript": transcript.text if transcript else None
                    }
                )
            )

        return result


# -------------------- TEST RUN --------------------

if __name__ == "__main__":
    scraper = YouTubeScraper()

    # 🔥 TEST 1: transcript
    print("\n=== TEST TRANSCRIPT ===")
    transcript = scraper.get_transcript("dQw4w9WgXcQ")

    if transcript:
        print("✅ Transcript fetched:\n", transcript.text[:300])
    else:
        print("❌ No transcript available")

    # 🔥 TEST 2: channel scraping
    print("\n=== TEST CHANNEL ===")

    channel_videos = scraper.scrape_channel(
        "UCn8ujwUInbJkBhffxqAPBVQ",
        hours=1000
    )

    print(f"\n✅ Total videos fetched: {len(channel_videos)}\n")

    for video in channel_videos:
        print("Title:", video.title)
        print("Transcript available:", video.transcript is not None)
        print("-" * 50)