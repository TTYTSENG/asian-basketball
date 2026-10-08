# 籃球網站資料庫

檔案：`data/basketball.sqlite3`。使用 SQLite 與 Python 標準庫，不需帳號、伺服器、API 金鑰或額外資料庫費用。

## 運作方式

官方網站 → 更新程式 → SQLite → 網頁 JSON → GitHub Pages。

資料庫是歷史統計與頁面快照的主要儲存來源；現有 `archive.json`、`site.json` 是相容匯出檔。初次啟用時從既有 JSON 匯入。之後每次自動更新使用同一個資料庫，以聯盟＋官方比賽／球員 ID 更新資料，不重複新增同一場統計。

GitHub Actions 已會將 `data/` 存回儲存庫，因此 SQLite 能跨次執行保留。Pages 仍只發布前端、`site.json` 與日報，SQLite 不會被複製到網站發布目錄。公開儲存庫中的檔案本身仍可被讀取，因此只能存放公開籃球資料。

資料庫沒有對外寫入介面，也不需要讀者登入。`insights` 是未來文章的預留表，目前零筆；還沒有文章後台或自動發布文章功能。

## 資料表

| 表 | 保存的資料 |
| --- | --- |
| `leagues` | 六個聯盟／賽事與官網入口 |
| `teams` | 已取得比賽中的球隊名稱；本機名稱鍵不是官方隊伍 ID |
| `players` | 官方球員 ID、聯盟與姓名 |
| `games` | 完整已取得賽程、比分、日期、隊伍及原始標準化紀錄 |
| `player_game_stats` | 個人單場得分、命中／出手、失誤、上場秒數，含 DNP |
| `game_sources` | 官方賽事、正式統計、逐球引用網址 |
| `lineup_stats`、`lineup_members` | 通過分析條件的最佳／最差組合、球員與共同時間 |
| `game_analyses` | 三點分析與資料品質說明 |
| `news_articles` | 官方戰報標題、連結與已知發布日期 |
| `snapshots` | 網站與每日分析資料快照 |
| `update_runs` | 更新批次與來源錯誤記錄 |
| `insights` | 未來個人文章預留，尚未有內容 |
| `player_advanced_stats` | 罰球與組織基本數據、USG、EFF、AST/TO；追蹤指標及 VORP 尚缺的值保存 NULL |
| `ato_sequences` | ATO 回合結果、終結者、樣本是否可用與排除原因；未知發球／接球者保存 NULL |

比分／個人數據有非負與合理出手數限制，相關表有外鍵約束。單次匯入以交易提交；資料格式失敗時整次資料庫寫入回復，保留之前成功資料。網站原有的逐球對帳與來源失敗提示繼續保留。

`imported_at` 表示入庫時間，`generated_at` 表示報告產生時間；它們不代表每條歷史數據都在該時刻從官網重新抓取。官網 ID 以聯盟區隔，沒有假定同一個人在不同聯盟使用相同 ID。若球隊更名，本機名稱鍵會視為不同名稱，未来可再加入官方隊伍 ID 與名稱別名映射。

## 管理與查詢

可用支援 SQLite 的桌面工具開啟檔案，或用 Python 標準庫查詢。操作前先複製檔案備份；不要在更新程式寫入期間覆蓋檔案。

檢查資料庫與重新匯出網站資料：

```powershell
python scripts/database.py --export
python scripts/validate.py
```

例：查看某聯盟最近的完賽紀錄：

```sql
SELECT game_date, game_id, home_score, away_score, official_url
FROM games
WHERE league_id = 'tpbl' AND completed = 1
ORDER BY game_date DESC, game_time DESC
LIMIT 5;
```

例：查看某球員最近三場實際出賽（把 `7` 換成官方球員 ID）：

```sql
SELECT g.game_date, p.name, s.points, s.turnovers, s.fgm, s.fga, s.seconds
FROM player_game_stats s
JOIN games g USING (league_id, game_id)
JOIN players p USING (league_id, player_id)
WHERE s.league_id = 'tpbl' AND s.player_id = '7' AND s.seconds > 0
ORDER BY g.game_date DESC, g.game_time DESC
LIMIT 3;
```

## 驗證

已測試：重複匯入不重複資料、官方更正更新既有紀錄、錯誤交易回復、賽程不覆蓋正式統計、不同聯盟可有相同官方 ID、JSON 匯出與資料庫一致。另檢查 SQLite 完整性、外鍵、個人得分合計與官方比分。

GitHub 尚未建立儲存庫，因此目前已驗證本機資料庫與完整更新流程；雲端排程與部署待儲存庫建立後驗證。
