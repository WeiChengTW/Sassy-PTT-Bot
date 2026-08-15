# 運維手冊 / Operations Runbook

本專案由 **兩個 systemd `--user` 服務** + **一個手動 ngrok** 組成。
重開機或搬機器時照本文件操作即可，不會漏東西。

> 最後更新：2026-08-15

---

## 服務總覽

| 元件 | 管理方式 | 埠 | 說明 |
|---|---|---|---|
| 後端 bot | systemd `sassy-bot.service` | **5000** | Flask（LINE webhook `/line/callback` + LIFF API `/liff/*`）＋所有排程 |
| LIFF 前端 | systemd `sassy-liff-frontend.service` | **5174** | Vite dev server（`--host --port 5174 --strictPort`），HMR 即時服務原始碼 |
| 對外通道 | **ngrok（手動，非 systemd）** | — | `sassy_liff` tunnel → 5174；`nlp_final_project` tunnel → 5000 |

- 兩個 systemd 服務都 `enabled` 且開了 user linger → **重開機/登出會自動起來**。
- **ngrok 不會自動起來**，重開機後要手動啟動（見下方檢查清單）。
- ⚠️ **埠 5173 的 vite 是另一個專案（MovieAnimeKdrama）**，不要動它。

---

## 常用指令

```bash
# 狀態
systemctl --user status sassy-bot.service
systemctl --user status sassy-liff-frontend.service

# 重啟（改完後端程式碼後必做；前端 HMR 通常免重啟）
systemctl --user restart sassy-bot.service
systemctl --user restart sassy-liff-frontend.service

# 看日誌
journalctl --user -u sassy-bot.service -f          # 也會寫入專案根目錄 bot.log
journalctl --user -u sassy-liff-frontend.service -f

# 開機自啟（已設定，僅供參考）
systemctl --user enable sassy-bot.service sassy-liff-frontend.service
loginctl enable-linger william     # 讓 --user 服務在未登入時也運行
```

> **不要**用 `./run_bot.sh &` / `nohup` / 背景方式手動跑 bot——那會變成當前 shell/session 的子程序，session 結束就被殺，還會跟 systemd 版本搶 5000 埠。一律用 `systemctl --user`。

---

## ngrok（對外網址）

```bash
# 啟動 LIFF 對外通道（重開機後必做）
ngrok start sassy_liff --config /home/william/projects/Sassy-PTT-Bot/ngrok.yml

# 查目前公開網址
curl -s http://127.0.0.1:4040/api/tunnels | python3 -c "import sys,json;[print(t['name'],'=>',t['public_url']) for t in json.load(sys.stdin)['tunnels']]"
```

⚠️ **重點坑**：`ngrok.yml` 沒有設固定網域，所以**每次啟動 ngrok 都會拿到隨機的 `*.ngrok-free.app` 網址**。網址一變，就必須到 **LINE Developers 後台 → LIFF → Endpoint URL** 更新成新網址，否則 LIFF 開不起來。

**根治方式**（有空再做）：到 ngrok 儀表板領一個免費 static domain，寫進 `ngrok.yml` 的 `sassy_liff`（加 `domain: xxx.ngrok-free.app`），LINE 後台只需改這一次，之後就能把 ngrok 也做成 systemd 常駐服務。

---

## 重開機後檢查清單

1. `systemctl --user status sassy-bot sassy-liff-frontend` → 兩個都 `active (running)`（應自動起來）。
2. `ss -tln | grep -E ':5000|:5174'` → 兩個埠都在聽。
3. **手動啟動 ngrok**：`ngrok start sassy_liff --config .../ngrok.yml`。
4. 用上面的 `curl .../api/tunnels` 拿到新公開網址。
5. **若網址跟 LINE 後台登記的不同 → 到 LINE Developers 後台更新 LIFF Endpoint URL。**
6. 在 LINE 群組內開一次 LIFF 驗證。

---

## 排程（都在 `sassy-bot.service` 內，APScheduler，時區 Asia/Taipei）

| 排程 | 時間 | 內容 |
|---|---|---|
| 畢業倒數 | 每日 **09:00**（watchdog 09:05） | 推播畢業倒數訊息到 `LINE_GROUP_ID` |
| 每月 LLM 分析 | 每月 1 號 03:00 | `run_monthly_analysis` |
| 每日聚合 | 每日 04:00 | `run_daily_aggregation` |
| 徽章發放 | 每小時 :05 | `process_ended_trips` |
| 旅行週年提醒 | 每日 10:00 | `_send_anniversary_reminders` |
| 每週 PTT 爬取 | 週日 03:00 | `_run_weekly_crawl_and_index` |

- 畢業倒數的最後發送狀態記在 `data/graduation_state.json`（同日不會重複發）。
- **排程只有在 bot 該時刻正在運行時才會觸發**（misfire grace 10~60 分）。bot 若在 09:00 沒跑，當天倒數就會漏掉——這正是改用 systemd 常駐的原因。

---

## 關鍵設定檔

| 檔案 | 內容 |
|---|---|
| `.env` | LINE 金鑰、`LINE_GROUP_ID`、`GRADUATION_DATE`、`ADMIN_USER_IDS`、`LIFF_ID`、LLM proxy 等 |
| `liff/.env.local` | `VITE_LIFF_ID`（前端 LIFF 初始化用） |
| `ngrok.yml` | ngrok tunnel 設定（`sassy_liff`→5174、`nlp_final_project`→5000） |
| `data/chat.db` | SQLite 主資料庫（WAL 模式） |
| `data/graduation_state.json` | 畢業倒數最後發送狀態 |

---

## systemd unit 檔位置

- `~/.config/systemd/user/sassy-bot.service`
- `~/.config/systemd/user/sassy-liff-frontend.service`

改完 unit 檔後：`systemctl --user daemon-reload && systemctl --user restart <service>`。
