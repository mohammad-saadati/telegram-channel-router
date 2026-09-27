# CLAUDE.md

Guidance for working in this repo. Read before adding agents, workflows or integrations.

## What this is

An **agentic workflow platform** around Telegram. Small, single-purpose **agents** are
composed into **workflows**, exposed through a **FastAPI** service and a **CLI**.

The root-level `main.py`, `categorizer.py`, `topics.py` are a **legacy** Telethon
(user-account) channel router. They are independent of `app/`. Don't import them from `app/`.
If that logic becomes an agent, port it into `app/agents/<name>/` instead.

## Layout

```
app/
├── main.py                 # FastAPI app factory (uvicorn app.main:app)
├── cli.py                  # python -m app.cli run-agent|run-workflow|list|discover-chats
├── core/
│   ├── config.py           # pydantic-settings Settings (all env vars live here)
│   ├── container.py        # Composition root: builds clients, agents, workflows
│   └── logging.py
├── integrations/           # External services, one subpackage each
│   └── telegram/client.py  # Async Bot API client (httpx)
├── agents/
│   ├── base.py             # BaseAgent, AgentInput, AgentContext, AgentResult
│   ├── registry.py         # AgentRegistry (name -> instance)
│   └── greeter/            # One package per agent
├── workflows/
│   ├── engine.py           # Workflow, WorkflowStep, WorkflowEngine (sequential)
│   └── definitions.py      # Declarative WORKFLOWS list
└── api/
    ├── deps.py             # ContainerDep (FastAPI dependency)
    └── routes/             # health, agents, workflows
tests/                      # pytest; use fakes, never hit the real Telegram API
```

## Dependency direction

```
api / cli  ->  core.container  ->  workflows  ->  agents  ->  integrations
```

- Lower layers never import higher ones. Agents don't know about FastAPI. Integrations don't know about agents.
- `core/container.py` is the **only** place that creates concrete objects. Agents get their
  dependencies through `__init__`, never by reading settings or env vars themselves.
- API routes and CLI commands stay thin. Business logic belongs in agents.

## Adding an agent

1. Create `app/agents/<name>/agent.py`, subclass `BaseAgent`:
   - `name` (unique, snake_case), `description`
   - `Input`: an `AgentInput` pydantic model (validates params, feeds the API schema)
   - `async def execute(self, params, ctx) -> dict`: raise on failure. `BaseAgent.run`
     turns exceptions into `AgentResult(success=False)`.
2. Export it from `app/agents/<name>/__init__.py`.
3. Register it in `build_agents()` in `app/core/container.py`.
4. Add tests in `tests/` with a fake client.

It is then automatically available at `POST /agents/<name>/run` and `python -m app.cli run-agent <name>`.

## Adding a workflow

Add a `Workflow` to `app/workflows/definitions.py` and append it to `WORKFLOWS`.
Steps run in order and share one `AgentContext`. A step's output is stored in
`ctx.data[step.key or step.agent]`, so later agents can read earlier results.
The engine checks at startup that every step's agent exists.

## Adding an integration

Create `app/integrations/<service>/` with an async client class. Keep it thin: typed methods,
one error type, no business logic. Add settings to `Settings`, wire it in `build_container`,
and close it in `Container.aclose`.

## Conventions

- Python 3.11+, `from __future__ import annotations`, full type hints, async I/O only.
- Config: add fields to `Settings`, document them in `.env.example`. Use `SecretStr` for secrets.
- **Never log or return secrets.** Bot API URLs contain the token. That's why httpx logging
  is set to WARNING and `TelegramBotClient` strips URLs from errors.
- `.env` and `*.session` are git-ignored. Never commit them.

## Telegram notes

- The bot must be an **admin** of the channel with "Post messages" permission.
- Private channels can only be addressed by numeric id (`-100…`), not by name. Use
  `python -m app.cli discover-chats` after adding the bot and posting once in the channel.
  Set it as `TELEGRAM_CHANNEL_ID`.
- Bots cannot read channel history. Use the legacy Telethon code (user account) for that.

## Future direction (keep the design compatible)

- **LLM agents**: add `integrations/anthropic/` and agents that call Claude. The same
  `BaseAgent` contract applies.
- **Triggers**: a Telegram webhook route (`api/routes/telegram_webhook.py`) or scheduler
  that starts workflows. Keep triggers separate from agents.
- **Richer workflows**: branching and parallel steps belong in `workflows/engine.py`
  without changing the agent contract.
- **Long-running jobs**: move `WorkflowEngine.run` behind a task queue (arq/Celery) and
  persist `WorkflowRun` records. The API returns a run id instead of blocking.

## Commands

```bash
pip install -r requirements.txt
python -m pytest                              # tests
python -m app.cli list
python -m app.cli discover-chats              # find private channel id
python -m app.cli run-agent greeter --params '{"text": "Hello!"}'
python -m app.cli run-workflow channel_hello
uvicorn app.main:app --reload                 # API docs at http://127.0.0.1:8000/docs
```
