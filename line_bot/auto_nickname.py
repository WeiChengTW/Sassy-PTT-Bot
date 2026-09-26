"""自動取綽號：每週讓 LLM 看每位成員最近的發言，取一個暫時稱號寫進 aliases.json。

- 寫在各成員的 `auto_aliases`（與手寫的 `aliases` 分開），每人最多 MAX_AUTO_ALIASES 個，新的擠掉最舊的
- 只給機器人稱呼人時用（見 SassyBrain._nickname_map），不參與群組回憶檢索
- 不在群組公布，可在 LIFF「稱號」頁查看

用法：
    python -m line_bot.auto_nickname --dry-run   # 只印結果不寫檔
    python -m line_bot.auto_nickname             # 實際寫入 aliases.json
"""
import argparse
import asyncio
import json
import logging
import os
import re
import shutil
import time
from datetime import date

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


MAX_AUTO_ALIASES = 3
MIN_MSGS = 30            # 區間內發言少於此數就換更長的區間，再不夠就跳過
SAMPLE_SIZE = 150        # 每人送進 LLM 的最近發言數
MAX_NAME_CHARS = 10
MAX_REASON_CHARS = 50
_DAY_MS = 86400 * 1000


def choose_window(count_7d: int, count_30d: int) -> int | None:
    """回傳要看的天數：7 天夠多就看 7 天，否則 30 天，都不夠回 None（跳過）。"""
    if count_7d >= MIN_MSGS:
        return 7
    if count_30d >= MIN_MSGS:
        return 30
    return None


def push_auto_alias(entry: dict, alias: dict, max_n: int = MAX_AUTO_ALIASES) -> bool:
    """把新稱號加到 entry['auto_aliases'] 尾端，超過上限就丟掉最舊的。重複的名字不加，回傳是否有加。"""
    existing = set(entry.get("aliases", [])) | {a["name"] for a in entry.get("auto_aliases", [])}
    if alias["name"] in existing:
        return False
    autos = entry.setdefault("auto_aliases", [])
    autos.append(alias)
    del autos[:-max_n]
    return True


def parse_nickname_response(raw: str | None) -> dict | None:
    """從 LLM 輸出抽出 {"name", "reason"}，格式不對回 None。"""
    if not raw:
        return None
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    name = str(data.get("name", "")).strip()
    reason = str(data.get("reason", "")).strip()
    if not name or len(name) > MAX_NAME_CHARS or not reason:
        return None
    return {"name": name, "reason": reason}


def build_prompt(member: str, entry: dict, lines: list[str], days: int) -> str:
    taken = entry.get("aliases", []) + [a["name"] for a in entry.get("auto_aliases", [])]
    return (
        f"你是一個嘴很賤的 PTT 鄉民，要幫 LINE 群組成員「{member}」取一個本週的暫時稱號。\n"
        f"他已經有的外號（不要重複）：{'、'.join(taken) or '（無）'}\n\n"
        f"以下是他最近 {days} 天在群組的發言：\n" + "\n".join(lines) + "\n\n"
        "要求：\n"
        f"1. 稱號 2～{MAX_NAME_CHARS} 個字，只能從上面這段期間的發言裡具體的事、口頭禪或行為發想，"
        "不要拿以前的舊梗；好笑、有梗，可以酸但不要人身攻擊外貌或家人。\n"
        f"2. reason 用第三人稱、一句話（{MAX_REASON_CHARS} 字內）說明由來，引用他這段期間說過的話或做過的事。\n"
        '3. 只輸出 JSON：{"name": "稱號", "reason": "由來"}'
    )


def _fetch_counts(conn, group_id: str, now_ms: int) -> dict[str, tuple[int, int]]:
    rows = conn.execute(
        """SELECT user_name,
                  SUM(CASE WHEN timestamp >= ? THEN 1 ELSE 0 END),
                  COUNT(*)
           FROM messages
           WHERE group_id = ? AND type = 'text' AND is_deleted = 0 AND timestamp >= ?
           GROUP BY user_name""",
        (now_ms - 7 * _DAY_MS, group_id, now_ms - 30 * _DAY_MS),
    ).fetchall()
    return {r[0]: (r[1], r[2]) for r in rows}


def _fetch_lines(conn, group_id: str, user_name: str, since_ms: int) -> list[str]:
    rows = conn.execute(
        """SELECT content FROM messages
           WHERE group_id = ? AND user_name = ? AND type = 'text' AND is_deleted = 0
             AND timestamp >= ? AND LENGTH(content) > 1 AND content NOT LIKE '[%'
           ORDER BY timestamp DESC LIMIT ?""",
        (group_id, user_name, since_ms, SAMPLE_SIZE),
    ).fetchall()
    return [r[0].replace("\n", " ")[:150] for r in reversed(rows)]


async def _generate(prompt: str) -> str | None:
    messages = [{"role": "user", "content": prompt}]
    # 呼叫時才讀 env：以 script 執行時 .env 在 import 之後才載入
    providers = (
        (os.getenv("CLI_PROXY_BASE_URL", "http://localhost:8317/v1"), os.getenv("CLI_PROXY_API_KEY", ""),
         os.getenv("NICKNAME_MODEL", "gemini-3.1-pro-low")),
        (os.getenv("CGU_LLM_BASE_URL", "https://air.cgu.edu.tw/cgullmapi/v1"), os.getenv("CGU_LLM_API_KEY", ""),
         os.getenv("CGU_LLM_MODEL", "gpt-5-mini")),
    )
    for base, key, model in providers:
        if not key:
            continue
        try:
            async with AsyncOpenAI(base_url=base, api_key=key) as client:
                resp = await client.chat.completions.create(
                    model=model, messages=messages, temperature=1.0,
                    max_completion_tokens=4000, timeout=90,
                )
            return resp.choices[0].message.content
        except Exception as e:
            logger.warning(f"[NICKNAME] {model} 失敗: {e}")
    return None


def _save_aliases(data: dict) -> None:
    """先備份再以暫存檔 + rename 寫入，避免 bot 讀到寫一半的 JSON。"""
    from corpus_config import ALIASES_FILE_PATH
    shutil.copy2(ALIASES_FILE_PATH, ALIASES_FILE_PATH.with_suffix(".json.bak"))
    tmp = ALIASES_FILE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, ALIASES_FILE_PATH)


def run_weekly_nicknames(dry_run: bool = False) -> list[dict]:
    """主流程：挑有足夠發言的成員 → 逐一取稱號 → 寫回 aliases.json。回傳新稱號清單。"""
    from corpus_config import load_aliases
    from travel.db import get_conn

    group_id = os.getenv("MAIN_LINE_GROUP_ID", "")
    if not group_id:
        logger.warning("[NICKNAME] MAIN_LINE_GROUP_ID 未設定，跳過")
        return []

    aliases = load_aliases()
    now_ms = int(time.time() * 1000)
    results = []
    with get_conn() as conn:
        counts = _fetch_counts(conn, group_id, now_ms)
        for member, (c7, c30) in counts.items():
            if member not in aliases:
                continue
            days = choose_window(c7, c30)
            if days is None:
                continue
            lines = _fetch_lines(conn, group_id, member, now_ms - days * _DAY_MS)
            raw = asyncio.run(_generate(build_prompt(member, aliases[member], lines, days)))
            parsed = parse_nickname_response(raw)
            if not parsed:
                logger.warning(f"[NICKNAME] {member} 解析失敗: {raw!r:.200}")
                continue
            parsed.update({"created": date.today().isoformat(), "window_days": days})
            results.append({"member": member, **parsed})
            logger.info(f"[NICKNAME] {member} → {parsed['name']}（{parsed['reason']}）")

    if dry_run or not results:
        return results

    # 寫入前重讀，避免蓋掉跑 LLM 期間手動改過的內容
    latest = load_aliases()
    for r in results:
        if r["member"] in latest:
            alias = {k: r[k] for k in ("name", "reason", "created", "window_days")}
            push_auto_alias(latest[r["member"]], alias)
    _save_aliases(latest)
    return results


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只印結果，不寫入 aliases.json")
    args = ap.parse_args()
    for r in run_weekly_nicknames(dry_run=args.dry_run):
        print(f"{r['member']}（{r['window_days']} 天）→ {r['name']}：{r['reason']}")
