"""Detect post categories from Telegram message content."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from telethon.tl.custom.message import Message
from telethon.tl.types import (
    MessageEntityTextUrl,
    MessageEntityUrl,
    MessageMediaWebPage,
)


@dataclass(frozen=True)
class Category:
    key: str
    topic_title: str
    priority: int  # lower = checked / preferred first when multiple match


# Order matters for priority: first matching rule wins when priorities collide.
CATEGORIES: tuple[Category, ...] = (
    Category("youtube", "YouTube", 10),
    Category("linkedin", "LinkedIn", 20),
    Category("instagram", "Instagram", 30),
    Category("twitter", "Twitter / X", 40),
    Category("tiktok", "TikTok", 50),
    Category("repost", "Reposts", 60),
    Category("liked", "Liked", 70),
    Category("media", "Media", 80),
    Category("other", "Other", 100),
)

CATEGORY_BY_KEY = {c.key: c for c in CATEGORIES}

URL_PATTERNS: dict[str, re.Pattern[str]] = {
    "youtube": re.compile(
        r"(?:https?://)?(?:www\.)?(?:youtube\.com|youtu\.be|youtube-nocookie\.com)/",
        re.I,
    ),
    "linkedin": re.compile(
        r"(?:https?://)?(?:[\w-]+\.)?linkedin\.com/",
        re.I,
    ),
    "instagram": re.compile(
        r"(?:https?://)?(?:www\.)?instagram\.com/",
        re.I,
    ),
    "twitter": re.compile(
        r"(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/",
        re.I,
    ),
    "tiktok": re.compile(
        r"(?:https?://)?(?:www\.|vm\.)?tiktok\.com/",
        re.I,
    ),
}

# Minimum reaction count to treat a post as "liked"
LIKED_REACTION_THRESHOLD = 5


def _urls_from_message(message: Message) -> list[str]:
    urls: list[str] = []
    text = message.message or ""

    if message.entities:
        for ent in message.entities:
            if isinstance(ent, MessageEntityUrl):
                urls.append(text[ent.offset : ent.offset + ent.length])
            elif isinstance(ent, MessageEntityTextUrl):
                urls.append(ent.url)

    if isinstance(message.media, MessageMediaWebPage) and message.media.webpage:
        wp = message.media.webpage
        if getattr(wp, "url", None):
            urls.append(wp.url)

    # Fallback: raw http(s) links in text
    urls.extend(re.findall(r"https?://[^\s\]\)]+", text, flags=re.I))
    return urls


def _reaction_count(message: Message) -> int:
    reactions = getattr(message, "reactions", None)
    if not reactions or not getattr(reactions, "results", None):
        return 0
    return sum(int(r.count or 0) for r in reactions.results)


def categorize(message: Message) -> Category:
    """
    Pick a single category for a message.

    Priority:
      1. Known platform links (YouTube, LinkedIn, …)
      2. Repost / forwarded message
      3. High reaction count ("liked")
      4. Media-only posts
      5. Other
    """
    urls = _urls_from_message(message)
    matched: list[Category] = []

    for key, pattern in URL_PATTERNS.items():
        if any(pattern.search(u) for u in urls):
            matched.append(CATEGORY_BY_KEY[key])

    if matched:
        return min(matched, key=lambda c: c.priority)

    if message.fwd_from is not None:
        return CATEGORY_BY_KEY["repost"]

    if _reaction_count(message) >= LIKED_REACTION_THRESHOLD:
        return CATEGORY_BY_KEY["liked"]

    if message.media and not isinstance(message.media, MessageMediaWebPage):
        return CATEGORY_BY_KEY["media"]

    return CATEGORY_BY_KEY["other"]


def all_category_titles() -> Iterable[str]:
    return (c.topic_title for c in CATEGORIES)
