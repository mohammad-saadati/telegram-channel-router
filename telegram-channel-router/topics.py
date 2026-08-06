"""Ensure forum topics exist in the destination group and cache their IDs."""

from __future__ import annotations

import logging
import random
from datetime import datetime
from typing import Dict, Optional

from telethon import TelegramClient
from telethon.tl.functions.channels import GetForumTopicsRequest
from telethon.tl.functions.messages import CreateForumTopicRequest

from categorizer import CATEGORIES

log = logging.getLogger(__name__)


def _random_id() -> int:
    return random.randrange(-(2**63), 2**63)


async def _list_topics(client: TelegramClient, group) -> Dict[str, int]:
    """Return {topic_title: topic_id} for an existing forum."""
    result: Dict[str, int] = {}
    offset_date: datetime | int = 0
    offset_id = 0
    offset_topic = 0

    while True:
        resp = await client(
            GetForumTopicsRequest(
                peer=group,
                offset_date=offset_date,
                offset_id=offset_id,
                offset_topic=offset_topic,
                limit=100,
            )
        )
        if not resp.topics:
            break

        for topic in resp.topics:
            title = getattr(topic, "title", None)
            topic_id = getattr(topic, "id", None)
            if title and topic_id is not None:
                result[title] = topic_id

        if len(resp.topics) < 100:
            break

        last = resp.topics[-1]
        offset_topic = last.id
        offset_id = getattr(last, "top_message", 0) or 0
        # Prefer message date from messages payload when available
        offset_date = 0
        for msg in getattr(resp, "messages", []) or []:
            if getattr(msg, "id", None) == offset_id and getattr(msg, "date", None):
                offset_date = msg.date
                break

    return result


async def ensure_topics(
    client: TelegramClient,
    group,
    dry_run: bool = False,
) -> Dict[str, int]:
    """
    Make sure every category has a matching forum topic.
    Returns mapping: category_key -> message_thread_id (topic id).
    """
    existing = await _list_topics(client, group)
    log.info("Found %d existing forum topics", len(existing))

    key_to_topic_id: Dict[str, int] = {}

    for cat in CATEGORIES:
        if cat.topic_title in existing:
            key_to_topic_id[cat.key] = existing[cat.topic_title]
            log.info(
                "Topic '%s' already exists (id=%s)",
                cat.topic_title,
                existing[cat.topic_title],
            )
            continue

        if dry_run:
            log.info("[DRY RUN] Would create topic '%s'", cat.topic_title)
            key_to_topic_id[cat.key] = -1
            continue

        created = await client(
            CreateForumTopicRequest(
                peer=group,
                title=cat.topic_title,
                random_id=_random_id(),
            )
        )
        topic_id = _extract_created_topic_id(created)
        if topic_id is None:
            existing = await _list_topics(client, group)
            topic_id = existing.get(cat.topic_title)
        if topic_id is None:
            raise RuntimeError(f"Failed to create or resolve topic '{cat.topic_title}'")

        key_to_topic_id[cat.key] = topic_id
        existing[cat.topic_title] = topic_id
        log.info("Created topic '%s' (id=%s)", cat.topic_title, topic_id)

    return key_to_topic_id


def _extract_created_topic_id(updates) -> Optional[int]:
    """Best-effort parse of CreateForumTopicRequest response."""
    for upd in getattr(updates, "updates", []) or []:
        msg = getattr(upd, "message", None)
        if msg is None:
            continue
        # Topic id == id of the topic-creation service message
        if getattr(msg, "action", None) is not None and getattr(msg, "id", None):
            return msg.id
        reply = getattr(msg, "reply_to", None)
        if reply is not None and getattr(reply, "reply_to_top_id", None):
            return reply.reply_to_top_id
        if reply is not None and getattr(reply, "reply_to_msg_id", None):
            return reply.reply_to_msg_id
        if getattr(msg, "id", None):
            return msg.id
    return None
