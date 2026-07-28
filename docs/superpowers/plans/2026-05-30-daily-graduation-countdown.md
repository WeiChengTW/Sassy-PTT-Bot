# Daily Graduation Countdown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 每天 09:00 自動推送 PTT 鄉民風倒數畢業訊息到指定 LINE 群組。

**Architecture:** 在 `SassyBrain.__init__()` 加入 APScheduler `BackgroundScheduler`，每天 09:00 呼叫新方法 `send_daily_graduation_message()`，該方法計算距畢業天數、呼叫 LLM 生成鄉民語氣訊息、透過 LINE Push Message API 推送。

**Tech Stack:** Python 3.11、apscheduler 3.x、linebot.v3、AsyncOpenAI（現有）

---

## File Map

| 動作 | 路徑 | 說明 |
|------|------|------|
| Modify | `telegram_bot/bot.py` | 唯一需要改的檔案：加 import、常數、scheduler init、新方法、group_id log |
| Modify | `.env` | 加兩個新 key：`LINE_GROUP_ID`、`GRADUATION_DATE` |

---

### Task 1：安裝 apscheduler

**Files:**
- Run in: `/home/william/projects/Sassy-PTT-Bot/`

- [ ] **Step 1: 啟動 venv 並安裝**

```bash
cd /home/william/projects/Sassy-PTT-Bot
source venv/bin/activate
pip install apscheduler
```

預期輸出包含 `Successfully installed apscheduler-3.x.x`

- [ ] **Step 2: 確認可以 import**

```bash
python -c "from apscheduler.schedulers.background import BackgroundScheduler; print('OK')"
```

預期輸出：`OK`

---

### Task 2：加入環境變數設定

**Files:**
- Modify: `.env`

- [ ] **Step 1: 在 `.env` 末尾加入兩個新變數**

打開 `/home/william/projects/Sassy-PTT-Bot/.env`，在最後加上：

```env
LINE_GROUP_ID=
GRADUATION_DATE=2027-05-30
```

`LINE_GROUP_ID` 先留空，等 Task 5（group_id helper）跑起來後再填入。

---

### Task 3：加入 import 與常數

**Files:**
- Modify: `telegram_bot/bot.py`（imports 區段第 1–11 行；配置區段第 50–73 行附近）

- [ ] **Step 1: 在 bot.py 頂部 import 區加入新 import**

在 `import threading` 那行（第 7 行）之後，加入：

```python
from datetime import date
from apscheduler.schedulers.background import BackgroundScheduler
```

- [ ] **Step 2: 在配置區（LINE_WEBHOOK_PORT 那行之後，TRIGGER_KEYWORDS 之前）加入新常數**

在第 61 行 `LINE_WEBHOOK_PORT = ...` 之後加：

```python
LINE_GROUP_ID = os.getenv("LINE_GROUP_ID", "")
_grad_date_str = os.getenv("GRADUATION_DATE", "2027-05-30")
GRADUATION_DATE = date.fromisoformat(_grad_date_str)
```

---

### Task 4：加入 `send_daily_graduation_message()` 方法

**Files:**
- Modify: `telegram_bot/bot.py`（在 `_sanitize_response()` 方法之後，`run_line_server()` 函數之前）

- [ ] **Step 1: 在 `SassyBrain` class 內，`_sanitize_response` 結束後加入新方法**

在第 323 行（`return first` 那行）之後，於 class 內插入：

```python
    def send_daily_graduation_message(self):
        """每天 09:00 推送鄉民風倒數畢業訊息到 LINE 群組。"""
        if not self.line_api or not LINE_GROUP_ID:
            logger.warning("[GRADUATION] LINE API 未初始化或 LINE_GROUP_ID 未設定，跳過推送")
            return

        today = date.today()
        days_remaining = (GRADUATION_DATE - today).days

        if days_remaining <= 0:
            message_text = "已畢業了幹，還在這邊傳訊息"
            logger.info(f"[GRADUATION] 已畢業，推送固定訊息")
        else:
            user_prompt = (
                f"今天距離畢業還有 {days_remaining} 天。"
                "用一句話 PTT 鄉民語氣講這件事，要酸、要簡短、不要超過兩句。"
            )
            try:
                async def _call_llm():
                    for attempt in range(3):
                        try:
                            resp = await self.llm.chat.completions.create(
                                model=GENERATION_MODEL_NAME,
                                messages=[
                                    {"role": "system", "content": SYSTEM_PROMPT},
                                    {"role": "user", "content": user_prompt},
                                ],
                                temperature=1.0,
                                max_completion_tokens=100,
                            )
                            return resp.choices[0].message.content or ""
                        except Exception as e:
                            if "429" in str(e) and attempt < 2:
                                logger.warning(f"[GRADUATION] 429 rate limit，5s 後重試 (attempt {attempt+1})")
                                await asyncio.sleep(5)
                            else:
                                raise

                raw = asyncio.run(_call_llm())
                message_text = self._sanitize_response(raw)
                logger.info(f"[GRADUATION] LLM 生成: {repr(message_text)}")
            except Exception as e:
                logger.error(f"[GRADUATION] LLM 失敗，使用 fallback: {e}")
                message_text = f"還有 {days_remaining} 天，繼續撐啊廢物"

        try:
            self.line_api.push_message(
                PushMessageRequest(
                    to=LINE_GROUP_ID,
                    messages=[LineTextMessage(text=message_text)],
                )
            )
            logger.info(f"[GRADUATION] 推送成功: {repr(message_text)}")
        except Exception as e:
            logger.error(f"[GRADUATION] 推送失敗: {e}")
```

---

### Task 5：在 `handle_line_event()` 加入 Group ID 日誌

**Files:**
- Modify: `telegram_bot/bot.py`（`handle_line_event()` 方法，第 171 行附近）

- [ ] **Step 1: 在 `handle_line_event()` 裡，取出 group_id 並 log**

找到第 208 行：
```python
        logger.info(f"LINE clean_text: {repr(clean_text)}, is_mentioned={is_mentioned}")
```

在這行**之前**加入：

```python
        if event.source.type == "group":
            group_id = getattr(event.source, 'group_id', 'unknown')
            logger.info(f"[GROUP_ID] source group_id={group_id}")
```

---

### Task 6：在 `__init__()` 啟動 BackgroundScheduler

**Files:**
- Modify: `telegram_bot/bot.py`（`SassyBrain.__init__()` 方法，LINE setup 結束後）

- [ ] **Step 1: 在 `__init__()` 末尾的 `logger.info("LINE Bot 已啟用")` 區塊之後加入 scheduler 初始化**

找到第 145 行：
```python
        else:
            logger.info("LINE Bot 未啟用（缺少 LINE_CHANNEL_SECRET 或 LINE_CHANNEL_ACCESS_TOKEN）")
```

在這段**之後**（仍在 `__init__` 內）加入：

```python
        # 每日倒數畢業排程
        if LINE_GROUP_ID:
            self._scheduler = BackgroundScheduler()
            self._scheduler.add_job(
                self.send_daily_graduation_message,
                trigger='cron',
                hour=9,
                minute=0,
                id='graduation_countdown',
            )
            self._scheduler.start()
            logger.info(f"[GRADUATION] 排程已啟動，目標群組: {LINE_GROUP_ID}，畢業日: {GRADUATION_DATE}")
        else:
            logger.warning("[GRADUATION] LINE_GROUP_ID 未設定，倒數排程不啟動")
```

---

### Task 7：確認 `PushMessageRequest` import 已存在

**Files:**
- Read: `telegram_bot/bot.py`（第 18–21 行的 linebot import 區）

- [ ] **Step 1: 確認 `PushMessageRequest` 已在現有 import 中**

查看第 19–21 行：
```python
    from linebot.v3.messaging import (
        Configuration, ApiClient, MessagingApi,
        ReplyMessageRequest, PushMessageRequest, TextMessage as LineTextMessage,
    )
```

`PushMessageRequest` 已經在現有 import 中 ✓。如果不在，加入它。

---

### Task 8：手動驗證（測試觸發）

**Files:**
- Modify: `telegram_bot/bot.py`（暫時改 cron trigger）

- [ ] **Step 1: 將 cron trigger 改成 1 分鐘後觸發（測試用）**

找到 Task 6 加入的 `add_job` 呼叫，把 `trigger='cron', hour=9, minute=0` 改成：

```python
from datetime import datetime, timedelta
run_at = datetime.now() + timedelta(minutes=1)
self._scheduler.add_job(
    self.send_daily_graduation_message,
    trigger='date',
    run_date=run_at,
    id='graduation_countdown',
)
```

- [ ] **Step 2: 先在 `.env` 填入真實的 `LINE_GROUP_ID`**

到 LINE 群組傳一則訊息，重啟 bot，從 `bot.log` 看：
```
[GROUP_ID] source group_id=C...
```
把這個 ID 填入 `.env` 的 `LINE_GROUP_ID=`。

- [ ] **Step 3: 重啟 bot 並等 1 分鐘**

```bash
cd /home/william/projects/Sassy-PTT-Bot
source venv/bin/activate
python telegram_bot/bot.py
```

確認 `bot.log` 出現：
```
[GRADUATION] 排程已啟動，目標群組: C...，畢業日: 2027-05-30
[GRADUATION] LLM 生成: '...'
[GRADUATION] 推送成功: '...'
```

LINE 群組應收到訊息。

- [ ] **Step 4: 恢復 cron trigger**

把 Task 8 Step 1 的測試改回正式 cron：

```python
            self._scheduler.add_job(
                self.send_daily_graduation_message,
                trigger='cron',
                hour=9,
                minute=0,
                id='graduation_countdown',
            )
```

移除 `from datetime import datetime, timedelta`（如果只為測試加的）。

- [ ] **Step 5: 重啟 bot，確認排程 log**

```bash
python telegram_bot/bot.py
```

`bot.log` 應出現：
```
[GRADUATION] 排程已啟動，目標群組: C...，畢業日: 2027-05-30
```

且 bot 仍正常響應 LINE / Telegram 訊息。
