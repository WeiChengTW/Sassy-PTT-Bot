# Sassy-Bot 對話感知增強

**日期**：2026-08-07
**狀態**：Approved → Implementing
**範圍**：僅 `telegram_bot/bot.py`，不動 `.env` / 架構 / LLM 切換邏輯

## 背景

目前 `generate_response` 的 prompt 雖然堆了 few-shot 範例 + RAG 語料 + 對話歷史，但實際生成出來常常有以下問題：

1. **回應跟訊息本身無關**：bot 丟出通用罐頭（"問這幹嘛，沒意義"），沒有引用 user 訊息裡的具體字詞
2. **不記得上下文**：群組前一句別人說「他壞掉了」，下一句被觸發時 bot 完全沒接上
3. **缺少發話者**：歷史注入把不同人的 user 訊息混在一起，LLM 誤判為同一個人
4. **歷史太窄**：只存「觸發的 5 輪」，常常 3 輪裡都是同一個人

目標：放大利 1（針對性）與 2（脈絡），同時保留多樣性。

## 設計

### 1. SYSTEM_PROMPT 加規範

```python
SYSTEM_PROMPT = (
    "你是 PTT 八卦板資深鄉民。"
    "說話風格極簡短、犀利、帶有台灣網路黑話和鄉民幽默感。"
    "回應必須呼應或引用 user 訊息裡的具體字詞/主題，不可產生通用罐頭回應。"
    "不要重複前幾輪已用過的句型或起手式。"
    "只輸出角色的一句話回應，不加解釋、不加標籤、不加引導文字。"
    "風格參考：直接點評事情本質，用輕描淡寫的方式諷刺，像是在 PTT 留言串底下的神回覆。"
)
```

（最後兩句「回應必須呼應... / 不要重複...」為本次新增。）

### 2. Few-shot 半語意選擇

新函式 `_select_examples(user_text, k_top=2, k_random=3)`：

- 評分：以 `_bigram_overlap(user_text, q)` 算 user_text 跟每個 Q 的 2-gram 重疊數
- 取 top 2（語意相近）+ 從剩下 random 抽 3（保留多樣性）
- 混合後再 `random.shuffle`
- 取代原先 `_sample_examples()` 全部 random 取 5 的行為

bigram 為什麼：人名/專有名詞的 2-3 字片段在 example Q 裡若重複就視為相關；對短句如「三小」會自動 fallback 到 random（無 overlap），不卡死。

### 3. Sender 標記 + 對話 window 拓寬

`_chat_histories` 結構改為：

```python
self._chat_histories: dict[str, list[dict]] = {}  # chat_id → [{"sender", "text", "role"}, ...]
```

新增 helpers：

- `_get_sender_label(user_id)`：lazy fetch LINE profile 拿 `display_name`，cache 到 `self._user_names`；抓不到 fallback `路人{user_id[-6:]}`
- `_record_turn(chat_id, sender, text, role)`：append + cap 10
- `_format_history_for_prompt(chat_id)`：回傳 list of `{"role": "user"/"assistant", "content": "..."}`，user 訊息前綴 `f'{sender} 說：「{text}」'`

caller 端（`handle_line_event`、`handle_telegram_message`）改為：

1. 在 trigger 判斷**之前**就 `_record_turn(chat_id, sender, clean_text, "user")` — **不再只記觸發的，全部都記**
2. 觸發成功後 `_record_turn(chat_id, "鍵盤俠", response, "bot")`
3. `generate_response` 只負責讀 history 組 LLM messages，不再自己寫 history

window 上限 10 則（佔約 200-500 tokens）。

### 4. RAG 真實推文範例

`get_relevant_snippets(query, n_results=3)` 改回傳 `(top1, rest)`：

- chromadb query 本身已按相似度排序，`docs[0]` 是最相關
- top 1 進 prompt 當「真實推文範例」
- `docs[1:n_results]` 進 prompt 當「其他相關語料」

prompt 結構：

```
以下是 PTT 鄉民的發言風格範例：
[2 語意相近 + 3 random 的 Q&A]

真實推文範例：
「{top1 推文}」

其他相關 PTT 語料（風格參考）：
「{rest[0]}」
「{rest[1]}」

[optional news hint]

[對話歷史帶 sender標記]

網友說：「{user_text}」
PTT 酸民的回應（一句話，不要解釋）：
```

### 5. 影響預期

- Prompt 多 ~200-400 tokens（多 sender 標記 + 拓寬 history）
- P50 latency 預期 +0.5-1s（從 ~6s → ~6.5-7s，PRIMARY 仍可承受）
- 隨機性：few-shot 半 random + 系統層禁止句型重複
- 針對性：few-shot 語意相似 + 系統層強制引用 user_text 字詞
- 脈絡：10 則 window + sender 標記，前後文與角色清楚

### 6. 測試

- 重啟 bot 後，用 5 則 bot.log 真實訊息（"我去找他拔"、"三小"、"100塊而已"、"輸入boy666 免費拔門牙"、"他壞掉了 長庚怎麼了"）跑測試
- 觀察：
  - 回應是否引用 user_text 裡的具體字（如「三小」「拔」）
  - 回應 latency 與之前 PRIMARY 對比
  - 是否觸發 fallback
- 對照組：前次用同樣 5 則的 PRIMARY 輸出

### 7. 回滾

全部變更壓在一個 feature commit（`feat: enhance conversation awareness`），`git revert` 即可還原。

### 8. 不做的事（YAGNI）

- ❌ 持久化對話歷史（重啟歸零 OK）
- ❌ 多 persona 切換（先讓「針對性」達標）
- ❌ Anti-generic post-processing regenerate（先讓 prompt 規矩跑看看）
- ❌ 改 LINE webhook payload 想辦法拿到 display_name（lazy fetch 已經夠）
- ❌ 改 `_chat_histories` 結構做 migration（in-memory，重啟就清空）
