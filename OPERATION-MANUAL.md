# 專注亞洲籃球觀察：網站與 SQLite 操作手冊

維護者：凸肚男 · tzesmann@gmail.com。版本日期：2026-10-08。適用目前網站資料夾與 SQLite 結構版本 2。

## 1. 先了解目前狀態

網站、資料庫、資料更新程式及 GitHub Pages 工作流程已完成本機建置。尚未建立 GitHub 儲存庫，因此雲端排程與公開網址尚未啟用。本機預覽在電腦關機或預覽伺服器停止後不能開啟；單純開啟網站不會抓取新資料。

資料流程：官方網站 → Python 擷取與驗證 → SQLite 保存 → JSON 匯出與日報 → 網頁顯示。GitHub Pages 顯示靜態檔案；讀者瀏覽器不會直接查詢或寫入 SQLite。

| 操作目的 | 使用方式 |
| --- | --- |
| 看比賽、分析、下載規則 | 開啟網站 |
| 更新官方資料與日報 | 執行 `scripts/update.py`，上線後由 Actions 排程執行 |
| 找歷史比賽、球員、組合 | 用 SQLite SQL 查詢 |
| 把資料拿去研究或 Excel | 匯出 CSV |
| 保存可復原副本 | 備份 SQLite，再備份整個網站資料夾 |
| 修改研究文章／個人介紹 | 編輯 `index.html`；目前沒有文章後台 |

## 2. 檔案儲存與分類

目前專案位置：`C:\Users\Tyson Tzeng\Documents\Codex\2026-10-06\ji3\outputs\basketball-site`。以下命令以這個資料夾為工作目錄；搬到其他位置時替換路徑，整個資料夾一起搬移。

| 位置 | 分類與用途 | 保存方式 |
| --- | --- | --- |
| `index.html`、`style.css`、`reading.css` | 網站內容與外觀 | 編輯前備份 |
| `app.js`、`reports.js`、`advanced.js` | 賽程、報告與進階卡片顯示 | 隨網站發布 |
| `a11y.js`、`speech.js` | 閱讀設定與朗讀 | 隨網站發布 |
| `data/basketball.sqlite3` | 主要歷史資料庫 | 優先備份，更新時自動寫入 |
| `data/site.json` | 目前頁面資料快照 | 從資料庫匯出，勿人工修改 |
| `data/archive.json` | 已保存詳細比賽的相容歷史匯出 | 從資料庫匯出；未包含所有賽程列 |
| `data/reports/YYYY-MM-DD.json` | 每日網站／分析快照 | 同日期重跑會覆蓋該日期檔；不是每次更新的獨立版本 |
| `downloads/` | 使用者提供的規則 PDF | 保留來源原檔與版本日期 |
| `scripts/` | 擷取、分析、匯出與管理程式 | 隨專案保存 |
| `scripts/schema.sql` | 完整資料表定義 | 結構版本變更時需一起更新 |
| `scripts/adapters/` | 原始聯盟轉換器 | 隨專案保存 |
| `tests/` | 數據與資料庫測試 | 發布變更前使用 |
| `.github/workflows/` | GitHub 排程與發布設定 | 上傳儲存庫時不可遺漏 |
| `.cache/http/` | 本機 HTTP 暫存，有效期 30 分鐘 | 可重新取得，通常不備份／不上傳 |
| `backups/`、`exports/` | 建議的備份與研究 CSV 目錄 | 管理工具首次使用時建立，預設不加入 Git |

分類主軸為「聯盟 → 比賽 → 球員／組合／回合」，不必替每隊建立一個資料庫。使用一個 SQLite 檔案，依欄位查詢即可。

日報檔清理程式在寫入當日日報前刪除超過 90 個既有日期檔的舊檔，因此寫完當日後可能暫有 91 個檔案；SQLite 的 `report:日期` 快照與歷史資料目前沒有自動保留期限。這兩種保留方式不同，資料庫會逐漸增加。建議每月查看檔案大小並保存月度備份。

目前沒有獨立的 `season_id`、聯盟跨季球員身分對照表或隊伍更名對照表。要做跨季研究，先按聯盟與日期篩選；不要把姓名相同當成同一人，也不要只憑隊名合併更名前後資料。

## 3. Windows 第一次設定與啟動

需要可執行的 Python 3.12 或以上，以及網路。SQLite 由本程式使用 Python 的 `sqlite3` 模組存取，不需另架資料庫伺服器、註冊帳號或設定資料庫密碼。先確認環境：

```powershell
Set-Location -LiteralPath 'C:\Users\Tyson Tzeng\Documents\Codex\2026-10-06\ji3\outputs\basketball-site'
python --version
python -c "import sqlite3; print(sqlite3.sqlite_version)"
```

如果只有 `py` 指令可用，以下所有 `python` 可改成 `py -3.12`；若兩者都找不到，需先安裝 Python 並重新開啟 PowerShell。

建議建立專案專用環境，不必變更 PowerShell 的執行政策：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

以下範例使用 `python`；若採用專用環境，換成 `.\.venv\Scripts\python.exe`。三個外部依賴版本以 `requirements.txt` 為準，SQLite 無須用 pip 安裝。

先檢查，再開啟網站：

```powershell
python scripts/db_tools.py status
python scripts/validate.py
python -m http.server 8765 --bind 127.0.0.1
```

瀏覽器開啟 `http://127.0.0.1:8765/`。保持這個 PowerShell 視窗開啟；按 Ctrl+C 停止預覽。不要直接雙擊 `index.html`，否則 JSON 讀取可能失敗。若 8765 已使用，可改成 8766 並改用該網址。

本機 HTTP 伺服器會提供整個專案內的檔案，包含資料庫；綁定 `127.0.0.1` 供本機預覽。正式發布使用工作流程挑選的前端檔案，不以整個專案目錄作為公開網站。

## 4. 網站閱讀與日常操作

上方導覽包括賽程與戰報、進階賽後數據分析、聯盟簡介、推動籃球數據研究、籃球規則與字彙集、關於我。TPBL、P+、日本 B.LEAGUE 依序顯示未來七天與最近五場，分析顯示各聯盟最近三場。EASL、CBA、FIBA 目前主要是官方新聞／戰報連結，不代表已有完整球員統計。

閱讀列可設定 100–200% 字級、標準／黑字白底／白字黑底配色，設定儲存在該瀏覽器的 localStorage，不寫入 SQLite。手機或字體放大時左右捲動設定列，也可用 Tab 移動到按鈕。

朗讀：先在主內容選取文字，或先點導覽指定區塊，再按「朗讀」。可暫停、繼續、停止；切換導覽會停止。收合的詳細內容不朗讀。語音依裝置與瀏覽器提供，沒有支援或無法發聲會顯示提示。朗讀不會自動播放。

分析七項依序是末節最後五分鐘、五人組合、球員變化、ATO、USG、傳球與組織、VORP。組合近三場表格可收合；每場底部有官方引用與資料品質說明。看到「資料不足」時先閱讀該說明，不把缺值視為零。

## 5. SQLite 的實際設定

| 設定 | 目前值／行為 |
| --- | --- |
| 預設檔案 | 程式依自身位置尋找 `data/basketball.sqlite3`，不是依 PowerShell 當下路徑猜測 |
| 結構版本 | `PRAGMA user_version = 2` |
| 外鍵 | 更新程式每次連線執行 `PRAGMA foreign_keys = ON` |
| 鎖定等待 | 更新程式設定 `PRAGMA busy_timeout = 5000`，等待 5 秒 |
| 交易 | 一批入庫資料在交易內提交；驗證失敗會回復該批資料庫寫入 |
| Journal | 程式未設定 WAL；以該資料庫實際 `PRAGMA journal_mode` 查詢結果為準 |
| 缺值 | 未提供的進階追蹤資料使用 SQL `NULL`；真實零值保存為 0 |
| ID | 比賽／球員 ID 與 `league_id` 合成鍵；不跨聯盟假定 ID 相同 |
| 球隊鍵 | 以官方隊名產生本機鍵，不是官方隊伍 ID |

既有資料庫已隨專案提供。`database.py` 首次開啟沒有網站快照的資料庫時，會嘗試從現有 `site.json` 與 `archive.json` 匯入；不是任意空資料夾都能自動完成初始化。因此移機請複製整個專案，至少保留這兩個 JSON 與資料庫。

以下管理工具以唯讀模式開啟資料庫，不會因路徑拼錯而建立空資料庫。一般研究查詢不需自行改資料表或 Journal 模式。

```powershell
python scripts/db_tools.py status
python scripts/db_tools.py query --sql "PRAGMA journal_mode;"
python scripts/db_tools.py query --sql "PRAGMA table_info(player_advanced_stats);"
```

## 6. 資料表與欄位分類

聯盟代碼：`tpbl`＝TPBL；`plg`＝P+；`b`＝日本 B.LEAGUE；`easl`＝東超；`cba`＝CBA；`fiba`＝FIBA 亞洲賽事。

| 分類 | 資料表 | 主要欄位與用途 |
| --- | --- | --- |
| 基礎名單 | `leagues` | `id`、`name`、`official_url` |
| 基礎名單 | `teams` | `league_id`、`team_key`、`name` |
| 基礎名單 | `players` | `league_id`、`player_id`、`name` |
| 賽程／比賽 | `games` | `game_date`、`game_time`、主客隊鍵、主客比分、`completed`、`has_detail`、`payload_json` |
| 個人基礎統計 | `player_game_stats` | `points`、`fgm`、`fga`、`turnovers`、`seconds`、`side` |
| 個人進階統計 | `player_advanced_stats` | 罰球、助攻、籃板、抄截、阻攻、`usg`、`eff`、`ast_to`、傳球追蹤與 `vorp` |
| 五人組合 | `lineup_stats`、`lineup_members` | 組合標籤、淨得分、共同秒數與成員；僅保存通過條件的選定組合 |
| ATO 回合 | `ato_sequences` | 節次、暫停剩餘秒數、攻守方、結果、`eligible`、排除原因及可知參與者 |
| 分析文字 | `game_analyses` | 前三項分析、資料品質、產生時間；不是七項分析都存於此表 |
| 引用來源 | `game_sources` | `role`＝`game`、`statistics`、`play_by_play` 與官方 `url` |
| 官方新聞 | `news_articles` | 標題、URL、已知發布日期、首次／最近見到時間 |
| 保存快照 | `snapshots` | `site` 與 `report:YYYY-MM-DD` 的 JSON |
| 維護記錄 | `update_runs` | 更新時間、入庫時間、`source_errors_json` |
| 預留研究文章 | `insights` | 標題、內文、作者、草稿／發布狀態；目前未連動網頁 |

`game_date`／`game_time` 供目前賽程顯示，時間採臺北 UTC+8；`imported_at` 是 UTC 入庫時間，`generated_at` 有時區偏移，不能把所有時間字串都視為同一時區。`has_detail = 1` 表示保存詳細類型資料，仍可能有缺漏，需搭配個人統計列與品質說明。DNP 的 `seconds = 0`，實際出賽查詢使用 `seconds > 0`。

正規化事件與額外原始欄位在 `games.payload_json` 中，不是另有一張事件表。網站卡片中的 `keyPlayers`、`lineups`、`playerChanges` 保存在頁面／日報快照。引用網址在 `games.official_url` 與 `game_sources`；擷取成功時間可查 `site.json` 中各聯盟的 `lastSuccess`。入庫時間不代表每一筆歷史數據都重新抓取。

## 7. 查詢與研究 CSV 匯出

提供 `scripts/db_tools.py`，不用先安裝 SQLite CLI。它支援單一唯讀 SQL、SQL 檔、CSV 匯出與備份；預設拒絕覆蓋既有 CSV／備份。CSV 使用 UTF-8 BOM，便於 Excel 開啟；缺值以文字 `NULL` 標示，研究前要轉成缺值，而不是數字 0。

先查有哪些球員：

```powershell
python scripts/db_tools.py query --sql "SELECT league_id, player_id, name FROM players WHERE league_id='tpbl' ORDER BY name;"
```

較長的 SQL 請在文字編輯器保存為 UTF-8 的 `.sql` 檔，例如 `queries/recent-games.sql`（自行建立 `queries` 資料夾）：

```sql
SELECT g.league_id, g.game_date, h.name AS home_team,
       a.name AS away_team, g.home_score, g.away_score,
       g.has_detail, g.official_url
FROM games g
JOIN teams h ON h.league_id=g.league_id AND h.team_key=g.home_team_key
JOIN teams a ON a.league_id=g.league_id AND a.team_key=g.away_team_key
WHERE g.league_id='tpbl' AND g.completed=1
ORDER BY g.game_date DESC, g.game_time DESC, g.game_id DESC
LIMIT 5;
```

執行或匯出（資料夾會自動建立）：

```powershell
python scripts/db_tools.py query --file queries/recent-games.sql
python scripts/db_tools.py query --file queries/recent-games.sql --csv exports/tpbl-recent-games-20261008.csv
```

球員近三場：把 `PLAYER_ID` 換成上一步查得的官方 ID。下列查詢含最近一場；研究某場賽前狀態時需增加比賽日期上限，避免使用未來資料。

```sql
SELECT g.game_date, p.name, s.points, s.turnovers,
       s.fgm, s.fga, ROUND(s.seconds/60.0,1) AS minutes,
       ROUND(100.0*s.fgm/NULLIF(s.fga,0),1) AS fg_percent,
       ROUND(v.usg,1) AS usg_percent, v.assists, v.ast_to
FROM player_game_stats s
JOIN games g USING(league_id,game_id)
JOIN players p USING(league_id,player_id)
LEFT JOIN player_advanced_stats v USING(league_id,game_id,player_id)
WHERE s.league_id='tpbl' AND s.player_id='PLAYER_ID' AND s.seconds>0
ORDER BY g.game_date DESC, g.game_time DESC, g.game_id DESC
LIMIT 3;
```

五人組合：結果每組一列，成員是集合，以下串接姓名順序沒有排序意義。

```sql
SELECT l.league_id, l.game_id, l.side, l.label,
       ROUND(l.seconds/60.0,1) AS minutes, l.net_points,
       GROUP_CONCAT(p.name,'、') AS members
FROM lineup_stats l
JOIN lineup_members m ON m.lineup_id=l.lineup_id
JOIN players p ON p.league_id=m.league_id AND p.player_id=m.player_id
WHERE l.league_id='tpbl'
GROUP BY l.lineup_id
ORDER BY l.game_id DESC, l.side, l.label;
```

ATO 進攻成功率：按球隊合併目前已保存樣本，不是整季完整母體。防守成功率可用 `defense` 分組並改成 `points=0`。

```sql
SELECT q.league_id,
       CASE q.offense WHEN 'home' THEN h.name ELSE a.name END AS offense_team,
       COUNT(*) AS possessions,
       ROUND(100.0*SUM(CASE WHEN q.points>0 THEN 1 ELSE 0 END)/COUNT(*),1) AS scoring_success_percent,
       SUM(q.points) AS points, SUM(q.turnovers) AS turnovers
FROM ato_sequences q
JOIN games g USING(league_id,game_id)
JOIN teams h ON h.league_id=g.league_id AND h.team_key=g.home_team_key
JOIN teams a ON a.league_id=g.league_id AND a.team_key=g.away_team_key
WHERE q.eligible=1 AND q.offense IN ('home','away')
GROUP BY q.league_id, offense_team;
```

找來源與更新問題：

```sql
SELECT league_id, game_id, role, url FROM game_sources
WHERE league_id='tpbl' ORDER BY game_id DESC;
```

```sql
SELECT run_id, generated_at, source_errors_json
FROM update_runs ORDER BY run_id DESC LIMIT 10;
```

單獨查看備份而不改主資料庫：`python scripts/db_tools.py --db backups/檔名.sqlite3 status`。`--db` 必須放在 `status`／`query`／`backup` 前面。

## 8. 更新、驗證與資料保存

本機需要手動執行一次更新；正式排程啟用後由雲端自動執行。另開 PowerShell，切到專案目錄：

```powershell
python scripts/update.py
python scripts/validate.py
python scripts/db_tools.py status
```

更新會保存賽程、最近五場及為近三場分析補足相關隊伍的先前三場資料，逐步累積歷史；不代表一開始已下載各聯盟全季所有個人與逐球資料。已有較早詳細資料通常沿用存檔；近期比賽會重抓以接收官方更正。

同聯盟、同官方 ID 的比賽與球員更新原紀錄，避免重複；官方更正不會自動保留每一版個人統計。若研究需要版本追蹤，保存帶日期／時間的 SQLite 備份與研究 CSV。

來源失敗時保留之前資料並記錄問題。工作流程成功不等於所有來源成功，還需看 `source_errors_json`、Actions 的 Source health summary 與頁面提示。SQLite 入庫驗證失敗會回復交易；JSON 匯出與入庫不是整個系統的單一交易，若入庫成功但匯出中斷，修復方式是：

```powershell
python scripts/database.py --export
python scripts/validate.py
```

上述命令只把目前快照重新匯出，不重新抓官網，也不因修改個人統計就重新計算快照。一般使用者不要直接修改官方數據；計算或解析器變更後應執行完整更新，核對引用與品質。

## 9. 備份、還原與移機

建議每週、修改程式前及重要研究匯出前備份；至少保留最近四週與每月一份。建議將第二份存於其他磁碟。`archive.json` 無法取代完整 SQLite 備份，因為沒有全部賽程、批次記錄及各類資料表。

建立不覆蓋既有副本的備份（時間字串避免同名）：

```powershell
$backupStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
python scripts/db_tools.py backup "backups/basketball-$backupStamp.sqlite3"
```

工具使用 SQLite backup API 保存一致的資料庫副本並檢查完整性；若失敗，顯示錯誤，不要把未完成檔當成可用備份。再用 `--db` 指向該備份執行 `status` 確認。

還原會覆蓋目前資料，請依序操作：停止更新程式、關閉資料庫編輯工具；若修復雲端資料，先停用該工作流程。先備份現在資料庫，再檢查欲還原備份。以下範例將檔名改成你實際已有的副本：

```powershell
python scripts/db_tools.py --db backups/basketball-20261008-200000.sqlite3 status
Copy-Item -LiteralPath 'backups/basketball-20261008-200000.sqlite3' -Destination 'data/basketball.sqlite3' -Force
python scripts/database.py --export
python scripts/validate.py
```

還原既有 SQLite 結構版本 2 備份；不要把未知來源或不同結構的資料庫直接覆蓋。若看到 `-wal`、`-shm`、`-journal` 側檔，先確保所有寫入連線已關閉並釐清 Journal 模式，再還原，不要在活動交易中只複製主檔。

移機：複製整個專案、建立新的 Python 環境、安裝依賴、執行 `status` 與 `validate.py`，再啟動預覽。不要複製舊電腦的 `.venv`。目前資料庫路徑寫在 `scripts/database.py` 的 `DB` 常數；管理工具 `--db` 只切換這次管理操作，不會切換更新程式使用的資料庫。

## 10. GitHub Pages 與自動排程

1. 建立 GitHub 公開儲存庫，預設分支 `main`。
2. 將專案內容放在儲存庫根目錄，包含 `.github/workflows/update-and-deploy.yml`，避免多套一層資料夾。不要上傳 `.venv`、`.cache` 或私人備份／研究匯出。
3. Settings → Pages → Source 選 GitHub Actions。
4. Settings → Actions → General → Workflow permissions 設 Read and write permissions；若帳號／組織政策有限制，按該政策處理。
5. Actions → Official data and GitHub Pages → Run workflow，首次執行後核對來源摘要、驗證與 Deploy。
6. 成功後使用 Pages 提供的正式網址。維護修改時，先取得雲端最新版再上傳；不要以舊本機資料庫覆蓋已持續更新的雲端資料。

目前排程每天臺北時間 07:17 與 09:47，cron 寫 UTC；第二次重試延遲公布統計。電腦可關機。排程可能延遲，不能保證精準到分鐘，也不是比分直播。公開儲存庫長期無活動可能停用排程，需檢查 Actions 狀態。

Pages 僅發布前端、規則下載、`site.json` 與日報，不發布 SQLite／完整 archive；但公開儲存庫內被提交的 SQLite 仍可被下載，所以資料庫只存官方公開數據。備份、研究資料、信箱以外的個人資訊不要加入公開儲存庫。

## 11. 分析口徑與研究限制

| 指標 | 目前口徑／必要條件 |
| --- | --- |
| 最後五分鐘 | 第四節剩餘 300–0 秒，不含延長賽；得分優先，不是附件模擬影響分 |
| 最佳／最差五人 | 共同至少四分鐘、至少兩組可比較、通過換人及比分驗證；按淨得分，不是每百回合效率 |
| 球員變化 | 本場至少十分鐘、之前三場足夠、得分差至少八分；顯示變化最大者，不是統計顯著性檢定 |
| ATO | 首個可辨識完整回合；得分即進攻成功、未得分即防守成功；只計 `eligible=1` |
| USG | 傳統 box-score 估計，包含 0.44 罰球係數；不是效率指標 |
| 比較基準 | 本場 EFF 最佳者，具體資格與說明見報告；不是聯盟 MVP |
| 傳球追蹤 | 官方缺少完整傳球鏈時，潛在助攻、傳出／接球、次級助攻維持缺值 |
| VORP | 尚無適用聯盟模型／替補基準時維持缺值，不用單場正負值代替 |

疲勞、防守責任、戰術理解與執行目前沒有可驗證的標註資料，不能從失誤或得分變化直接推斷。詳細公式見 `ADVANCED-METRICS.md`。

## 12. 故障排查與維護

| 情況 | 處理 |
| --- | --- |
| `python` 找不到 | 檢查 Python 安裝／PATH，或改用 `py -3.12` |
| 套件匯入失敗 | 確認使用同一個 Python 執行 pip 安裝與更新；使用專案 `.venv` |
| 找不到資料庫 | 檢查專案 `data/` 路徑；別先建立空資料庫掩蓋檔案遺失 |
| `database is locked` | 關閉資料庫工具的未提交交易，不同時執行兩個更新，等待完成再重試 |
| 外鍵／完整性／比分檢查失敗 | 保留錯誤記錄，使用已驗證備份；不要任意刪列或補零 |
| 網頁資料讀取失敗 | 透過 HTTP 開啟、確認 `data/site.json` 存在，必要時重新匯出 |
| 官方資料超過 48 小時 | 查看更新記錄與官網；修復來源／網路後重跑，不能只改更新時間 |
| ATO／陣容不判定 | 看排除原因與品質；解析器／官方資料問題不一定是程式壞掉 |
| 朗讀沒聲音 | 確認瀏覽器支援、音量與裝置語音，按停止再重試；換可用瀏覽器核對 |
| GitHub 成功但資料舊 | 查看 Source health summary 與各聯盟最後成功時間，確認不是保留舊資料 |

每週：確認頁面最新時間、官方來源、來源錯誤與備份。每月：檢查 SQLite／儲存庫大小、備份保留、官方網站是否改版。修改解析器後：執行 `python -m unittest discover -s tests -v`、更新、`validate.py` 並抽查官方紀錄。完整測試與已知未驗證項目見 `TEST-REPORT.md`。

目前沒有資料庫查詢網頁、文章後台、完整全季歷史回補、自動賽季分類或多使用者寫入系統；查詢與研究使用本手冊 SQL 與管理工具。

## 13. 官方參考與相關文件

- [Python sqlite3：連線、唯讀 URI 與備份 API](https://docs.python.org/3/library/sqlite3.html)
- [GitHub Pages 自訂工作流程](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
- [GitHub Actions 排程事件與限制](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
- 專案文件：`README.md`、`DATABASE.md`、`ADVANCED-METRICS.md`、`TEST-REPORT.md`。

本手冊依本機程式核對；GitHub 介面與政策依官方文件及帳號實際狀態為準。
