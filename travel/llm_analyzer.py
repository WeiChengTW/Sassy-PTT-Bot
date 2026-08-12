"""批次 LLM 訊息分析（主題 / 情緒 / 實體 / 摘要）。

每月由 APScheduler 觸發，分析尚未標記的訊息，回填 SQLite。
"""
import json
import os
import time
from typing import Any

from openai import AsyncOpenAI

from travel.db import get_conn

PRIMARY_BASE = os.getenv("CLI_PROXY_BASE_URL", "http://localhost:8317/v1")
PRIMARY_KEY = os.getenv("CLI_PROXY_API_KEY", "")
PRIMARY_MODEL = os.getenv("PRIMARY_MODEL", "gemini-3.6-flash-high")
FALLBACK_BASE = os.getenv("CGU_LLM_BASE_URL", "https://air.cgu.edu.tw/cgullmapi/v1")
FALLBACK_KEY = os.getenv("CGU_LLM_API_KEY", "")
FALLBACK_MODEL = os.getenv("CGU_LLM_MODEL", "gpt-5-mini")
BATCH_SIZE = 50

PROMPT_TEMPLATE = """分析以下 LINE 群組訊息（多則），每則輸出 JSON。
欄位：
- id（訊息 id，必須保留）
- is_travel_related（0/1，是否跟旅行 / 旅遊 / 行程相關）
- topics（陣列，從這幾個選：travel/food/work/chat/joke/other）
- sentiment（-1 ~ 1，-1 極負面、0 中性、1 極正面）
- locations（地點陣列，可空陣列）
- summary（一句話中文摘要，可空字串）

只輸出合法 JSON 陣列，不要 ```json 包裹。

訊息：
{messages}

JSON："""


def build_prompt(messages: list[dict]) -> str:
    """組 LLM prompt：多則訊息一次分析。"""
    lines = []
    for m in messages:
        ts = time.strftime("%Y-%m-%d", time.localtime(m["timestamp"] / 1000))
        content = m.get("content") or "(non-text)"
        lines.append(f"id={m['id']} [{ts}] {m.get('user_name', '?')}: {content}")
    return PROMPT_TEMPLATE.format(messages="\n".join(lines))


def parse_llm_response(raw: str) -> list[dict[str, Any]]:
    """解析 LLM 回傳為 JSON 陣列。處理 ```json ... ``` 包裹。"""
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1]
        if s.startswith("json"):
            s = s[4:]
        s = s.strip().rstrip("`").strip()
    try:
        data = json.loads(s)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM 回傳非 JSON：{e}") from e
    if not isinstance(data, list):
        raise ValueError(f"預期 JSON 陣列，收到 {type(data).__name__}")
    return data


async def analyze_batch(messages: list[dict]) -> list[dict]:
    """呼叫 LLM 分析一批訊息，回傳結構化結果。"""
    prompt = build_prompt(messages)
    last_err = None

    try:
        client = AsyncOpenAI(base_url=PRIMARY_BASE, api_key=PRIMARY_KEY)
        resp = await client.chat.completions.create(
            model=PRIMARY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_completion_tokens=2000,
        )
        return parse_llm_response(resp.choices[0].message.content)
    except Exception as e:
        last_err = e

    if FALLBACK_KEY:
        client = AsyncOpenAI(base_url=FALLBACK_BASE, api_key=FALLBACK_KEY)
        resp = await client.chat.completions.create(
            model=FALLBACK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_completion_tokens=2000,
        )
        return parse_llm_response(resp.choices[0].message.content)

    raise RuntimeError(f"LLM 全部失敗: {last_err}")


def run_monthly_analysis():
    """主流程：撈未分析訊息 → 批次分析 → 回填 DB。"""
    import asyncio

    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, user_name, content, timestamp
               FROM messages
               WHERE analyzed_at IS NULL
                 AND content IS NOT NULL
                 AND type = 'text'
                 AND length(content) > 1
               ORDER BY timestamp ASC
               LIMIT ?""",
            (BATCH_SIZE,),
        ).fetchall()

    if not rows:
        print("[ANALYZER] 沒有未分析的訊息")
        return 0

    messages = [dict(r) for r in rows]
    try:
        results = asyncio.run(analyze_batch(messages))
    except Exception as e:
        print(f"[ANALYZER] LLM 失敗：{e}")
        return 0

    now = int(time.time())
    updated = 0
    with get_conn() as conn:
        for r in results:
            if "id" not in r:
                continue
            conn.execute(
                """UPDATE messages
                   SET is_travel_related=?, topics=?, sentiment=?,
                       locations=?, summary=?, analyzed_at=?
                   WHERE id=?""",
                (
                    r.get("is_travel_related", 0),
                    json.dumps(r.get("topics", []), ensure_ascii=False),
                    r.get("sentiment", 0.0),
                    json.dumps(r.get("locations", []), ensure_ascii=False),
                    r.get("summary", ""),
                    now,
                    r["id"],
                ),
            )
            updated += 1
    print(f"[ANALYZER] 完成 {updated} 則分析（輸入 {len(messages)} 則）")
    return updated


if __name__ == "__main__":
    run_monthly_analysis()