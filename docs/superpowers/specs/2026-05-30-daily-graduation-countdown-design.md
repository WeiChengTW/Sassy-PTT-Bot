# Daily Graduation Countdown Message — Design Spec

**Date:** 2026-05-30  
**Status:** Approved

---

## Context

Sassy-PTT-Bot currently responds only to incoming events (LINE webhook, Telegram polling). There is no proactive scheduled messaging. The goal is to add a daily push at 09:00 that sends a PTT-鄉民-style countdown to graduation to a specific LINE group, keeping the same cynical persona the bot uses in all other replies.

---

## Requirements

| # | Requirement |
|---|-------------|
| 1 | Trigger exactly once per day at 09:00 (local server time) |
| 2 | Target: a single LINE group identified by `LINE_GROUP_ID` |
| 3 | Message content: LLM-generated, PTT 鄉民 tone, includes exact days remaining to graduation |
| 4 | Graduation date configurable via `GRADUATION_DATE` env var (default: `2027-05-30`) |
| 5 | If `LINE_GROUP_ID` is unset, skip silently and log a warning — do not crash |
| 6 | Group ID helper: log each incoming group event's `group_id` so operator can identify the target group |

---

## Architecture

### Scheduler

Use **APScheduler** `BackgroundScheduler` (threaded). Started inside `SassyBrain.__init__()` alongside the existing threading model. Job added with `trigger='cron', hour=9, minute=0`.

No new threads, no new processes — APScheduler manages its own daemon thread internally.

### New Method: `send_daily_graduation_message()`

```
SassyBrain.send_daily_graduation_message()
  ├── Calculate days_remaining = (GRADUATION_DATE - today).days
  ├── If days_remaining <= 0: send "已畢業" variant
  ├── Build LLM prompt (PTT persona system prompt + countdown user prompt)
  ├── Call LLM (same AsyncOpenAI client, run via asyncio.run())
  ├── Sanitize via _sanitize_response()
  └── line_api.push_message(LINE_GROUP_ID, TextMessage(text=...))
```

### LLM Prompt

**System prompt:** reuse the existing PTT 鄉民 persona system prompt already defined in the codebase.

**User prompt:**
```
今天距離畢業還有 {N} 天。用一句話 PTT 鄉民語氣講這件事，要酸、要簡短、不要超過兩句。
```

Result passes through existing `_sanitize_response()` for consistency.

### Group ID Helper

In `handle_line_event()`, add one log line in the group-message branch:
```python
logger.info(f"[GROUP_ID] source group_id={group_id}")
```
Operator reads `bot.log` after the bot receives any group message to get the ID, then sets `LINE_GROUP_ID` in `.env`.

---

## Configuration Changes

Add to `.env`:

```env
LINE_GROUP_ID=C...           # Target group's LINE group ID
GRADUATION_DATE=2027-05-30   # ISO date; defaults to 2027-05-30 if unset
```

---

## Code Changes

**Only file modified:** `telegram_bot/bot.py`

1. **Imports** — add `from apscheduler.schedulers.background import BackgroundScheduler` and `from datetime import date`
2. **Constants** — add `GRADUATION_DATE` parsed from env (fallback `2027-05-30`), `LINE_GROUP_ID` from env
3. **`SassyBrain.__init__()`** — instantiate and start `BackgroundScheduler`; add cron job pointing to `send_daily_graduation_message`; only start if `LINE_GROUP_ID` is set
4. **New method `send_daily_graduation_message()`** — countdown calc, LLM call, push message
5. **`handle_line_event()`** — add one `logger.info` line for group ID logging

**New dependency:** `apscheduler` (install via `pip install apscheduler`)

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| `LINE_GROUP_ID` not set | Log warning at startup; scheduler not started |
| LLM call fails | Retry 3× (same pattern as existing response generation); on total failure, send hardcoded fallback: `"還有 {N} 天，繼續撐啊廢物"` |
| `days_remaining <= 0` | Send `"已畢業了幹，還在這邊傳訊息"` |
| Scheduler exception | APScheduler logs internally; bot continues running |

---

## Verification

1. Install `apscheduler`: `pip install apscheduler`
2. Set `LINE_GROUP_ID` and `GRADUATION_DATE` in `.env`
3. Temporarily change the cron trigger to fire 1 minute in the future and restart the bot; confirm push message arrives in the LINE group
4. Check `bot.log` for `[GRADUATION]` log lines confirming LLM generation and push
5. Restore trigger to `hour=9, minute=0`
6. Confirm bot still handles incoming LINE and Telegram messages normally (scheduler runs in background)
