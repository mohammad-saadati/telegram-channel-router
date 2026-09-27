# Telegram Channel → Forum Topic Router

Reads posts from a Telegram **channel**, categorizes them (YouTube, LinkedIn, Repost, Liked, …), and copies each post into the matching **topic** of a destination **forum group**.

## Why Telethon (user account), not a Bot?

| Need | Bot API | Telethon (this app) |
|------|---------|---------------------|
| Read full channel history | No | Yes |
| Create forum topics | Limited | Yes |
| Post into a specific topic | Yes | Yes |
| Live new-post routing | Yes (if bot is channel admin) | Yes |

A pure bot cannot scrape past posts, so this project uses your Telegram user account via [Telethon](https://docs.telethon.dev/).

## Categories → Topics

| Category | How it is detected | Forum topic title |
|----------|--------------------|-------------------|
| `youtube` | youtube.com / youtu.be links | YouTube |
| `linkedin` | linkedin.com links | LinkedIn |
| `instagram` | instagram.com links | Instagram |
| `twitter` | twitter.com / x.com links | Twitter / X |
| `tiktok` | tiktok.com links | TikTok |
| `repost` | Forwarded message | Reposts |
| `liked` | ≥ 5 reactions | Liked |
| `media` | Photo / video / document (no link match) | Media |
| `other` | Everything else | Other |

If a post matches several link types, the highest-priority platform wins (YouTube first, then LinkedIn, …).

Edit rules in `categorizer.py` (URL patterns, liked threshold, topic titles).

## Setup

### 1. Create a forum destination group

1. Create a Telegram group (or use an existing one).
2. Group settings → **Topics** → enable.
3. Add the Telegram account you will log in with as a member (admin recommended).

### 2. Join / access the source channel

Your account must be able to read the source channel (public channel, or private channel you belong to).

### 3. Get API credentials

1. Open https://my.telegram.org/apps  
2. Create an application  
3. Copy `api_id` and `api_hash`

### 4. Install & configure

```bash
cd telegram-channel-router
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # Windows
# cp .env.example .env   # macOS / Linux
```

Edit `.env`:

```env
API_ID=12345678
API_HASH=your_api_hash_here
SESSION_NAME=channel_router
SOURCE_CHANNEL=@your_source_channel
DEST_GROUP=@your_destination_group
SEND_DELAY=1.0
DRY_RUN=true
```

Use numeric ids if there is no username, e.g. `-1001234567890`.

### 5. First run (dry run)

```bash
# Preview only — does not post
python main.py --mode sync --limit 20
```

On first launch Telethon asks for your phone number and login code (and 2FA password if enabled). A `channel_router.session` file is created; keep it private.

Set `DRY_RUN=false` in `.env` when the categorization looks right.

## Usage

```bash
# Sync all history, then keep listening for new posts (default)
python main.py

# History only
python main.py --mode sync

# New posts only (no history)
python main.py --mode live

# Cap how many history messages to process
python main.py --mode sync --limit 100

# Ignore saved progress and start over
python main.py --mode sync --reset-state
```

Progress is stored in `state.json` (`last_message_id`) so re-runs skip already processed posts.

Optional: set `SINCE_DATE=2024-06-01` in `.env` to skip older messages.

## Notes

- **Flood limits**: keep `SEND_DELAY` ≥ `1.0` for large syncs.
- **Private channels / groups**: your logged-in account must already be a member.
- **“Same topic”**: topics are created by category name in the destination forum. They are not copied from a source forum; enable Topics on the destination and this app creates YouTube / LinkedIn / … topics automatically.
- **Session security**: treat `*.session` like a password; do not commit it.

## Project layout

```
telegram-channel-router/
├── main.py            # CLI entry — sync + live listener
├── categorizer.py     # Category detection rules
├── topics.py          # Create / resolve forum topics
├── requirements.txt
├── .env.example
└── README.md
```

---

# Agent platform (`app/`)

A FastAPI + CLI platform for agentic workflows on Telegram. See [CLAUDE.md](CLAUDE.md) for the architecture and how to add agents and workflows.

**First agent: `greeter`.** It posts a hello message to the channel.

1. `pip install -r requirements.txt`
2. Set `TELEGRAM_BOT_TOKEN` in `.env` (see `.env.example`).
3. Add the bot to the channel as an **admin** with "Post messages", then post any message in the channel.
4. `python -m app.cli discover-chats` and put the `-100…` id into `TELEGRAM_CHANNEL_ID`.
5. `python -m app.cli run-workflow channel_hello`

API: `uvicorn app.main:app --reload`, then open http://127.0.0.1:8000/docs.
