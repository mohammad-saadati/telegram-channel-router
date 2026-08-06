"""
Telegram Channel → Forum Topic Router

Reads posts from a source channel, categorizes them
(YouTube, LinkedIn, Repost, Liked, …), and copies each
post into the matching topic of a destination forum group.

Uses Telethon (user account), because bots cannot read
full channel history or manage forum topics reliably.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from telethon.tl.custom.message import Message

from categorizer import categorize
from topics import ensure_topics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("router")

STATE_FILE = Path("state.json")


def _load_env() -> None:
    load_dotenv()
    missing = [k for k in ("API_ID", "API_HASH", "SOURCE_CHANNEL", "DEST_GROUP") if not os.getenv(k)]
    if missing:
        log.error("Missing env vars: %s — copy .env.example to .env and fill them in", ", ".join(missing))
        sys.exit(1)


def _parse_since() -> datetime | None:
    raw = os.getenv("SINCE_DATE", "").strip()
    if not raw:
        return None
    # Accept YYYY-MM-DD or full ISO
    try:
        if len(raw) == 10:
            return datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SystemExit(f"Invalid SINCE_DATE: {raw}") from exc


def _bool_env(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _load_last_id() -> int:
    if not STATE_FILE.exists():
        return 0
    try:
        import json

        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return int(data.get("last_message_id", 0))
    except Exception:
        return 0


def _save_last_id(msg_id: int) -> None:
    import json

    STATE_FILE.write_text(
        json.dumps({"last_message_id": msg_id}, indent=2),
        encoding="utf-8",
    )


async def _safe_sleep(seconds: float) -> None:
    if seconds > 0:
        await asyncio.sleep(seconds)


async def _copy_to_topic(
    client: TelegramClient,
    message: Message,
    dest,
    topic_id: int,
) -> None:
    """Copy a message into a forum topic (reply_to = topic root id)."""
    text = message.message or ""
    entities = message.entities

    if message.media:
        await client.send_file(
            dest,
            message.media,
            caption=text or None,
            formatting_entities=entities,
            reply_to=topic_id,
        )
    else:
        await client.send_message(
            dest,
            text or "(empty)",
            formatting_entities=entities,
            reply_to=topic_id,
        )


async def forward_one(
    client: TelegramClient,
    message: Message,
    dest,
    topic_id: int,
    dry_run: bool,
) -> None:
    cat = categorize(message)
    preview = (message.message or "")[:80].replace("\n", " ")
    log.info(
        "msg #%s → [%s] topic=%s | %s",
        message.id,
        cat.key,
        topic_id,
        preview or "(media/no text)",
    )

    if dry_run or topic_id < 0:
        return

    try:
        await _copy_to_topic(client, message, dest, topic_id)
    except FloodWaitError as e:
        log.warning("Flood wait %ss — sleeping", e.seconds)
        await asyncio.sleep(e.seconds + 1)
        await _copy_to_topic(client, message, dest, topic_id)
    except Exception as exc:
        log.warning("Copy failed (%s); trying forward…", exc)
        try:
            await client.forward_messages(dest, message, top_msg_id=topic_id)
        except TypeError:
            # Older Telethon: top_msg_id may be unsupported
            try:
                await client.forward_messages(dest, message)
            except Exception as exc2:
                log.error("Failed to deliver msg #%s: %s", message.id, exc2)
        except Exception as exc2:
            log.error("Failed to deliver msg #%s: %s", message.id, exc2)


async def sync_history(
    client: TelegramClient,
    source,
    dest,
    topic_map: dict[str, int],
    *,
    since: datetime | None,
    min_id: int,
    send_delay: float,
    dry_run: bool,
    limit: int | None,
) -> int:
    """Copy historical posts. Returns highest processed message id."""
    processed = 0
    highest = min_id

    kwargs: dict = {"reverse": True}  # oldest → newest
    if min_id:
        kwargs["min_id"] = min_id
    if limit:
        kwargs["limit"] = limit

    async for message in client.iter_messages(source, **kwargs):
        if not isinstance(message, Message) or message.action:
            continue  # skip service messages
        if since and message.date and message.date.replace(tzinfo=timezone.utc) < since:
            continue

        cat = categorize(message)
        topic_id = topic_map[cat.key]
        await forward_one(client, message, dest, topic_id, dry_run)

        highest = max(highest, message.id)
        processed += 1
        if not dry_run:
            _save_last_id(highest)
        await _safe_sleep(send_delay)

    log.info("History sync done — processed %d messages (last id=%s)", processed, highest)
    return highest


async def listen_live(
    client: TelegramClient,
    source,
    dest,
    topic_map: dict[str, int],
    *,
    send_delay: float,
    dry_run: bool,
) -> None:
    """Keep running and route new channel posts as they arrive."""
    source_id = (await client.get_entity(source)).id

    @client.on(events.NewMessage(chats=source))
    async def handler(event: events.NewMessage.Event) -> None:
        message = event.message
        if message.action:
            return
        # Double-check chat (channels sometimes share updates oddly)
        if event.chat_id and abs(event.chat_id) != abs(source_id) and event.chat_id != source_id:
            # Telethon channel ids are fine via chats= filter; keep simple
            pass

        cat = categorize(message)
        topic_id = topic_map[cat.key]
        await forward_one(client, message, dest, topic_id, dry_run)
        if not dry_run:
            _save_last_id(message.id)
        await _safe_sleep(send_delay)

    log.info("Listening for new posts… (Ctrl+C to stop)")
    await client.run_until_disconnected()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Route channel posts into forum topics")
    parser.add_argument(
        "--mode",
        choices=("sync", "live", "both"),
        default="both",
        help="sync=history only, live=new posts only, both=history then listen (default)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max messages to sync from history (default: all)",
    )
    parser.add_argument(
        "--reset-state",
        action="store_true",
        help="Ignore saved last_message_id and reprocess from start/SINCE_DATE",
    )
    args = parser.parse_args()

    _load_env()

    api_id = int(os.environ["API_ID"])
    api_hash = os.environ["API_HASH"]
    session = os.getenv("SESSION_NAME", "channel_router")
    source = os.environ["SOURCE_CHANNEL"]
    dest_ref = os.environ["DEST_GROUP"]
    send_delay = float(os.getenv("SEND_DELAY", "1.0"))
    dry_run = _bool_env("DRY_RUN")
    since = _parse_since()

    if args.reset_state and STATE_FILE.exists():
        STATE_FILE.unlink()
        log.info("Cleared state file")

    min_id = 0 if args.reset_state else _load_last_id()

    client = TelegramClient(session, api_id, api_hash)
    await client.start()
    log.info("Logged in as %s", (await client.get_me()).username)

    source_entity = await client.get_entity(source)
    dest_entity = await client.get_entity(dest_ref)

    # Destination must be a forum (Topics enabled)
    if not getattr(dest_entity, "forum", False):
        log.error(
            "Destination group is not a forum. Open group settings → Topics → Enable topics."
        )
        await client.disconnect()
        sys.exit(1)

    topic_map = await ensure_topics(client, dest_entity, dry_run=dry_run)

    if args.mode in ("sync", "both"):
        await sync_history(
            client,
            source_entity,
            dest_entity,
            topic_map,
            since=since,
            min_id=min_id,
            send_delay=send_delay,
            dry_run=dry_run,
            limit=args.limit,
        )

    if args.mode in ("live", "both"):
        await listen_live(
            client,
            source_entity,
            dest_entity,
            topic_map,
            send_delay=send_delay,
            dry_run=dry_run,
        )
    else:
        await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Stopped")
