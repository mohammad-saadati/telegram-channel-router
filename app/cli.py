"""Command-line entry point: ``python -m app.cli <command>``."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from app.core.config import get_settings
from app.core.container import Container, build_container
from app.core.logging import configure_logging


async def _discover_chats(container: Container) -> int:
    """List chats the bot has seen, to find a private channel's numeric id."""
    # Pass allowed_updates explicitly: Telegram remembers the last filter, and a
    # filter of just ["message"] silently drops channel posts.
    update_types = ["channel_post", "message", "my_chat_member", "edited_channel_post"]
    updates = await container.telegram.get_updates(allowed_updates=update_types)
    chats: dict[int, dict] = {}
    for update in updates:
        for key in update_types:
            chat = (update.get(key) or {}).get("chat")
            if chat:
                chats[chat["id"]] = chat
    if not chats:
        print(
            "No chats found. Add the bot to the channel as an admin (with 'Post messages'),\n"
            "post any message in the channel, then run this again."
        )
        return 1
    for chat in chats.values():
        print(f"{chat['id']:>16}  {chat.get('type', ''):<10}  {chat.get('title') or chat.get('username', '')}")
    print("\nPut the channel id in .env as TELEGRAM_CHANNEL_ID.")
    return 0


async def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    run_agent = sub.add_parser("run-agent", help="Run one agent")
    run_agent.add_argument("name")
    run_agent.add_argument("--params", default="{}", help="JSON object of agent params")

    run_wf = sub.add_parser("run-workflow", help="Run a workflow")
    run_wf.add_argument("name")

    sub.add_parser("list", help="List agents and workflows")
    sub.add_parser("discover-chats", help="Show chat ids the bot has seen")

    args = parser.parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level)
    container = build_container(settings)
    try:
        if args.command == "run-agent":
            result = await container.agents.get(args.name).run(json.loads(args.params))
            print(result.model_dump_json(indent=2))
            return 0 if result.success else 1
        if args.command == "run-workflow":
            run = await container.workflows.run(args.name)
            print(run.model_dump_json(indent=2))
            return 0 if run.success else 1
        if args.command == "list":
            for agent in container.agents.all():
                print(f"agent     {agent.name:<20} {agent.description}")
            for wf in container.workflows.all():
                print(f"workflow  {wf.name:<20} {wf.description}")
            return 0
        return await _discover_chats(container)
    finally:
        await container.aclose()


def main() -> None:
    # Windows consoles default to cp1252, which can't print emoji in results.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(asyncio.run(_main(sys.argv[1:])))


if __name__ == "__main__":
    main()
