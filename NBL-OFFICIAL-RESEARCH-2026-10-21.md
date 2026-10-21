# 澳洲 NBL 官方資料接入查核

查核日期：2026-10-21，臺北時間。用途：供現有亞洲籃球網站新增澳洲 NBL 的資料介面與分析限制使用。本文件只記錄實際查得的一手來源；沒有改動生產程式。

## 結論

官方公開 JSON 可在無登入、無 API key 的情況下以普通 HTTP GET 取得。已實抓最近三場例行賽，球員得分、FGA、FTA 加總皆與全隊統計及正式比分一致；球員上場時間可解析，雙方各有五位先發。USG%、EFF、助攻失誤比，以及累積足夠歷史後的球員變化提示，具備接入資料條件。

逐球回應含出手結果、暫停、換人及球員 ID；但三場依事件 ID 排序後仍有時鐘倒退與後補事件。不能因此宣稱關鍵時段、五人組合、ATO 已通過精確時序驗證。建議沿用現有 fail-closed：有對應品質問題時停止受影響指標，保留 box score 與限制說明。

這是單次跨三場的可用性查核，不是對官方端點永久可用性的保證；公開可讀也不等於已確認大量原始數據再散布授權。

## 官方來源

- [NBL 官方統計入口](https://www.nbl.com.au/stats/statistics)
- [NBL 官方 Stats Hub](https://www.nbl.com.au/pages/stats-hub)
- [官方賽程 JSON](https://schedule.nbl.com.au/api/calendar/schedule?league=NBL&year=2026)
- [官方 Game Centre 前端程式](https://schedule.nbl.com.au/match/match.js?v=362e21e)
- [官方賽程備援及 UTC 解析程式](https://schedule.nbl.com.au/schedule-shared/rosetta-schedule-fallback.js?v=362e21e)
- [官方單場 JSON 範例：Melbourne–Illawarra](https://schedule.nbl.com.au/api/calendar/match?match=371032f3-58ad-11f1-a72d-69c2b72ae0a9&league=NBL)
- [官方單場 JSON 範例：Tasmania–NZ](https://schedule.nbl.com.au/api/calendar/match?match=37085418-58ad-11f1-9e12-411a11259918&league=NBL)
- [官方單場 JSON 範例：Sydney–Perth](https://schedule.nbl.com.au/api/calendar/match?match=3707e960-58ad-11f1-a8d4-819ec06531e4&league=NBL)

## 端點與欄位

### 賽程

端點：`GET https://schedule.nbl.com.au/api/calendar/schedule?league=NBL&year=2026`。

此次 HTTP 200，回應包含 `matches`、`total=190`、`offset=0`、`limit=500`、`years`、`seasons_meta`、`fallback=false`。2026 年回應同時包含季前賽與不同賽季類型，應依 `season_type` 或 `season_id` 明確篩選；不可把所有列一律當例行賽。

每場使用：

| 目的 | 官方欄位 |
|---|---|
| 比賽 ID | `id` |
| 開賽時間 | `starts_at_ms`，UTC epoch 毫秒 |
| 已完賽 | `phase == "complete"` |
| 球隊 | `home/away.id`、`.name`、`.team_code` |
| 比分 | `home_score`、`away_score`，需接受數字或數字字串 |
| 賽季 | `season_id`、`season_type` |
| 輪次／場地 | `round_label`、`venue_name` |

`status_raw="CONFIRMED"` 不代表完賽，不能代替 `phase`。尚未完賽的資料不得進入賽後分析。

### 單場

端點：`GET https://schedule.nbl.com.au/api/calendar/match?match=<schedule id>&league=NBL`。

官方前端只需 `match` 與 `league`；另傳 `season`、`year` 也曾測得成功，但不是必要條件。回應根節點是 `match`，內有 `match_status`、`home_score`、`away_score`、`home_team`、`away_team`、`player_match_statistics`、`team_match_statistics`、`play_by_play`、`calculated_player_statistics`、`calculated_team_statistics` 等。此次三場 `data_source="lambda-cache"`。

基本分析優先用正式 `player_match_statistics` 及 `team_match_statistics`；兩者都要篩 `str(period)=="0"` 的全場列，避免把單節與全場重複加總。球員 ID 用 `player.id`，不是該筆統計列的 `id`。隊別以 `team.id` 對 `home_team.id`／`away_team.id`。

| 網站欄位 | 官方球員欄位 |
|---|---|
| 姓名 | `player.full_name` |
| 得分 | `points` |
| 投籃命中／出手 | `field_goals_made`／`field_goals_attempted` |
| 罰球命中／出手 | `free_throws_made`／`free_throws_attempted` |
| 失誤 | `turnovers` |
| 助攻、籃板、抄截、阻攻 | `assists`、`rebounds`、`steals`、`blocks` |
| 犯規 | `personal_fouls`／`fouls`，需保留各定義 |
| 上場時間 | `minutes="30:49"`，或 `minutes_string="PT30M49S"` |
| 是否先發／出賽 | `starter`／`participated`，布林 |

全隊 `minutes=200` 表示五位球員共 200 分鐘，而不是該比賽進行 200 分鐘；正常 40 分鐘比賽的團隊總秒數為 12000。USG 分母使用全隊正式 FGA、FTA、TOV，不能只把個人失誤相加：此次 Melbourne 18 次全隊失誤但個人合計 17，Tasmania 10 次但個人合計 9。

`boxscore_field_mapping` 直接提供 `points→PTS`、`field_goals_made→FGM`、`field_goals_attempted→FGA`、`free_throws_made→FTM`、`free_throws_attempted→FTA`、`turnovers→TOV`、`minutes→MIN` 等，與上述解讀相符。

## 時區

賽程 `starts_at_ms` 已是 UTC epoch，轉為 `Asia/Taipei` 顯示即可。單場 `start_time_datetime` 雖沒有 `Z`，官方 `parseKickoffMs` 明確將無時區 ISO 補 `Z` 後才解析，故應視為 UTC。`venue.timezone`（例如 `Australia/Perth`）是場地時區，不應再把單場 ISO 當該地本地時間轉一次。這可避開澳洲各州與紐西蘭日光節約時間差異。

## 三場實證

選取規則：2026 年官方賽程、`phase=complete`、開賽時間不晚於臺北 2026-10-21 日終，依 `starts_at_ms` 倒序取最近三場。

| UTC 時間 | 比賽 | 正式比分 | 球員列（兩隊） | 逐球筆數 | 暫停／換人 |
|---|---|---:|---:|---:|---:|
| 2026-10-18 06:00 | Melbourne United–Illawarra Hawks | 89:91 | 24 | 630 | 11／162 |
| 2026-10-18 04:00 | Tasmania JackJumpers–NZ Breakers | 98:92 | 24 | 560 | 6／106 |
| 2026-10-17 08:30 | Sydney Kings–Perth Wildcats | 102:81 | 24 | 570 | 6／140 |

三場都通過以下獨立核對：

- 球員得分加總等於全隊 `points` 及正式比分。
- 球員 FGA、FTA 加總等於全隊正式 FGA、FTA。
- `success=true` 的 2pt、3pt、freeThrow 加權得分等於正式比分。
- 每隊全場球員上場時間合計 12000 秒；各有五位 `starter=true`。
- 沒有出賽球員缺少可解析的 `minutes` 字串。

以上不是對逐球順序及每位球員事件統計全部一致的宣稱。

## 逐球映射與限制

`play_by_play` 原陣列並非可靠的事件順序。例如 9 月 24 日 PER–ADL 樣本中，第二節換人 `action_id=291` 出現在第一節出手 `action_id=11` 前。`action_id` 有助辨識原事件次序，但也存在官方後補更正事件，不能把它當成精確時鐘順序的保證。

| 網站事件 | 官方 `action_type`／判定 |
|---|---|
| 兩分／三分命中或未中 | `2pt`／`3pt`，配 `success` 布林 |
| 罰球命中或未中 | `freeThrow`，配 `success` 布林 |
| 助攻／失誤／抄截／阻攻 | `assist`／`turnover`／`steal`／`block` |
| 進攻／防守籃板 | `rebound`，配 `sub_type` 的 Offensive／Defensive |
| 暫停 | `timeOut`（注意大小寫） |
| 換上／換下 | `substitution`，`sub_type` 是 `In`／`Out` |
| 每節開始／結束 | `period`，`sub_type` 是 `Start`／`End` |

球員用 `player.id` 或 `personId`；隊別用 `team.id`。`period` 是該事件節次，`clock` 是剩餘 MM:SS。換人事件的 `display_period_key` 有時仍指向前一節，因此不可用它取代 `period`。一般節為 600 秒，延長賽應另以官方節型／節次處理。

依 `action_id` 排序後，三場分別發現 14、9、16 次同節 clock 倒退。例如 Melbourne–Illawarra：第一節結束 `id=320,00:00` 後有 `id=321,08:25` 的後補出手；另有 `00:35` 阻攻後出現 `00:38` 出手。這不能用靜默重排或插補後直接宣稱可靠的共同上場時間。若使用校正，必須揭露校正及受影響指標，並經獨立對帳。

## 接入建議

1. 第一層驗證通過即可發布正式比分、球隊主要數據、球員 box score、USG／EFF／助攻失誤比，並保留每場官方 Game Centre 連結與擷取時間。
2. 逐球資料可保存原始來源與品質資訊，但關鍵球員、五人組合、ATO 須分指標通過時序、比分、個人主要統計及陣容檢核；失敗時顯示資料不足。
3. 歷史比較按 NBL 聯盟＋官方球員 ID 累積，不得和中國 NBL、NBL1 或其他聯盟混用 ID。賽程中也有不同賽季類型，第一版建議先限定澳洲男子 NBL 的例行賽／季後賽。
4. 自動排程須在 GitHub Actions 環境另外實跑，保留上次成功資料，避免官方介面暫時失敗造成頁面清空。來源讀取成功不等於所有進階指標驗證成功。
