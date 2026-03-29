"""
News Filter — suspends trading around high-impact economic events.
Uses a free economic calendar API (marketaux / forexfactory-compatible scraper).
"""
import httpx
from datetime import datetime, timedelta
from loguru import logger
from typing import List
import pytz


# High-impact events relevant to XAUUSD
XAUUSD_KEYWORDS = [
    "Non-Farm", "NFP", "CPI", "Inflation",
    "Interest Rate", "Fed", "FOMC", "Powell",
    "GDP", "Unemployment", "PCE", "ISM",
    "PPI", "Retail Sales",
]

WIB = pytz.timezone("Asia/Jakarta")
UTC = pytz.utc


class NewsFilter:
    """
    Checks if current time is within a news blackout window.
    Falls back to 'clear' if API is unavailable (fail-safe).
    """

    def __init__(
        self,
        suspend_before_min: int = 30,
        suspend_after_min: int = 30,
    ):
        self._suspend_before = timedelta(minutes=suspend_before_min)
        self._suspend_after  = timedelta(minutes=suspend_after_min)
        self._cached_events: List[dict] = []
        self._cache_date: datetime | None = None

    def is_news_window(self) -> bool:
        """Return True if current time is inside a news blackout window."""
        try:
            events = self._get_today_events()
            now_utc = datetime.now(UTC)

            for event in events:
                event_time = event.get("event_time")
                if event_time is None:
                    continue
                window_start = event_time - self._suspend_before
                window_end   = event_time + self._suspend_after

                if window_start <= now_utc <= window_end:
                    logger.warning(
                        f"NEWS BLACKOUT: '{event['title']}' @ "
                        f"{event_time.strftime('%H:%M UTC')} — Trading suspended"
                    )
                    return True

            return False

        except Exception as e:
            logger.warning(f"News filter error (fail-safe: clear): {e}")
            return False  # Fail-safe: allow trading if API unreachable

    def _get_today_events(self) -> List[dict]:
        """Fetch high-impact USD/XAU events for today. Cached per day."""
        today = datetime.now(UTC).date()
        if self._cache_date == today and self._cached_events is not None:
            return self._cached_events

        self._cached_events = self._fetch_from_fcsapi()
        self._cache_date = today
        return self._cached_events

    def _fetch_from_fcsapi(self) -> List[dict]:
        """
        Fetch from fcsapi.com (free tier) economic calendar.
        Falls back to empty list if unavailable.
        """
        try:
            today_str = datetime.now(UTC).strftime("%Y-%m-%d")
            # Using a lightweight public endpoint — replace with your API key
            url = (
                f"https://fcsapi.com/api-v3/forex/economy_cal"
                f"?country=US&from={today_str}&to={today_str}&access_key=demo"
            )
            with httpx.Client(timeout=5.0) as client:
                response = client.get(url)
                data = response.json()

            events = []
            for item in data.get("response", []):
                impact = item.get("impact", "").upper()
                title  = item.get("event", "")
                if impact != "HIGH":
                    continue
                if not any(kw.lower() in title.lower() for kw in XAUUSD_KEYWORDS):
                    continue

                time_str = item.get("date", "")
                try:
                    event_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
                    events.append({"title": title, "event_time": event_time})
                except ValueError:
                    continue

            logger.info(f"News filter: {len(events)} high-impact events today")
            return events

        except Exception as e:
            logger.warning(f"News API fetch failed: {e}")
            return []

    def next_clear_time(self) -> str:
        """Return ETA until next clear window (human readable)."""
        try:
            events = self._get_today_events()
            now_utc = datetime.now(UTC)
            for event in sorted(events, key=lambda x: x["event_time"]):
                window_end = event["event_time"] + self._suspend_after
                if window_end > now_utc:
                    delta = int((window_end - now_utc).total_seconds() // 60)
                    return f"{delta} min"
        except Exception:
            pass
        return "Unknown"
