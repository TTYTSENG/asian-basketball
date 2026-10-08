# 凸肚男的亞洲籃球觀察

完整操作步驟與 SQLite 設定見 [操作手冊](OPERATION-MANUAL.md)；亦提供可在瀏覽器閱讀／列印的 `OPERATION-MANUAL.html`。唯讀查詢、CSV 匯出與備份工具：`scripts/db_tools.py`。

目前頁首名稱為「專注亞洲籃球觀察」。頁首有可保存的 100–200% 字體大小與標準／高對比／深色配色控制。導覽包含「進階賽後數據分析」、「推動籃球數據研究」、「籃球規則與字彙集」與「關於我」。規則區提供使用者附件的原檔下載；進階指標口徑與限制見 [ADVANCED-METRICS.md](ADVANCED-METRICS.md)。

已完成的可部署網站，使用官方公開資料、Python 與 GitHub Pages。沒有付費 API、AI 日報費用、外部字型或圖片資源。前端讀取預先產生的 JSON；GitHub Actions 在雲端更新資料，所以電腦關機仍可運作。

## 一次性上線設定

1. 在 GitHub 建立 **Public** 儲存庫，例如 `asian-basketball`，預設分支使用 `main`。
2. 將本資料夾**內容**上傳到儲存庫根目錄，包含隱藏的 `.github/workflows/update-and-deploy.yml`。不要只上傳 ZIP 或多套一層資料夾。
3. 到 **Settings → Pages → Build and deployment → Source** 選擇 **GitHub Actions**。
4. 到 **Settings → Actions → General → Workflow permissions** 選 **Read and write permissions**。
5. 若初次上傳的工作流程已執行但 Pages 設定未完成，到 **Actions → Official data and GitHub Pages → Run workflow** 執行一次。
6. 部署成功後，網址為 `https://你的帳號.github.io/asian-basketball/`。往後依排程執行，無須每日手動更新。

目前尚未建立遠端儲存庫，因此 GitHub 雲端排程、Linux 網路存取與公開部署**尚未實機驗證**；本機已使用真實官方資料執行更新及瀏覽器測試。

## 更新時程與零成本條件

- 每日臺北時間 07:17 更新，09:47 再次更新／重試。工作流程中的 cron 使用 UTC。
- 排程每天也會更新預告賽程；比賽日之後抓取最新已完賽比賽，自動產生三點分析與日期日報。
- 不是秒級即時比分。GitHub 可能延遲排程，官方也可能晚公布統計；頁面提供擷取時間、來源錯誤與超過 48 小時的過期提示。
- 各聯盟獨立更新。單一來源失敗保留上次成功資料，其餘來源繼續更新。單場詳細資料失敗會重試。分析對帳限制與連線錯誤分開呈現。
- 公開儲存庫可使用 GitHub Free 的 Pages；標準 GitHub 託管執行器的公開儲存庫 Actions 不收執行分鐘費用。使用免費 `github.io` 網址，不購買網域。
- 公開儲存庫長期無活動可能停用排程。工作流程每日保存資料；若 GitHub 停用排程、官方更改格式或阻擋雲端連線，仍需修復。零成本不能保證永久免維護。

官方說明：[GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)、[Actions 使用計費](https://docs.github.com/en/billing/concepts/product-billing/github-actions)、[排程限制](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。

## 官方資料與引用

| 來源 | 資料 | 取得方式 |
| --- | --- | --- |
| [TPBL](https://tpbl.basketball/schedule) | 賽程、正式統計、逐球 | 官方 `api.tpbl.basketball/api/seasons`、`seasons/{id}/games`、`games/{id}/stats` 與 `broadcasts` |
| [P. LEAGUE+](https://pleagueofficial.com/schedule-regular-season) | 賽程、正式統計、逐球 | 官網賽程、公開 `api/boxscore.preciser.php` 與 `api/playbyplay.php` |
| [B.LEAGUE](https://www.bleague.jp/schedule/) | 最高級別賽程、正式統計、逐球 | 官方 `schedule/` 與 `game_detail/` 中的官方嵌入 JSON |
| [EASL](https://www.easl.basketball/news) | 官方新聞與戰報標題 | 官方新聞文章連結，戰報優先 |
| [CBA](https://www.cbaleague.com/#/news) | 官方戰報 | 官網使用的 `portal-server.cbaleague.com/news/list`，戰報優先 |
| [FIBA](https://www.fiba.basketball/en/events/fiba-basketball-world-cup-2027-asian-qualifiers/news) | 亞洲國際賽事官方戰報 | 世界盃亞洲資格賽新聞；亞洲盃另有官方資料庫連結 |

每場顯示官方賽事引用與逐球連結。API 是官網目前公開使用的介面，並非有穩定性承諾的開發者 API。讀取失敗會重試；不繞過登入或付費限制。

## 三點分析口徑

1. **第四節最後五分鐘**：剩餘時間 300 秒至 0 秒，包含邊界，不包含延長賽。不另外限制分差。得分優先，依序以助攻、抄截、阻攻與失誤比較；顯示前三名的可驗證貢獻。
2. **五人組合**：明確處理每次換人和節末。每隊比較共同上場至少四分鐘的組合，按淨得分選出最佳與最差；同分時先取共同時間長者。至少要有兩組才做比較。個人近三場是實際有出賽的紀錄、含本場，列出日期、得分、失誤與投籃命中／出手。啟用時只有有限歷史可抓，不足三場會明示，之後持續累積。
3. **特殊變化**：本場至少十分鐘，與之前三場實際出賽平均得分相差至少八分。顯示本場與前三場上場時間，避免把上場增加直接當作能力提升。不做健康、疲勞或戰術能力的診斷。

逐球與正式比分、球員得分、命中、出手與失誤對帳。得分／陣容有問題時，不產生組合結論；只有失誤不符時，可保留已通過驗證的得分與陣容分析，但省略末段失誤數。官方空值、DNP、`0`／`00` 背號差異均有處理。P+ 只有在官方名單中姓名唯一且完全相同時，才修正逐球背號或隊別，並顯示校正數。時間校正採原附件的非遞增序列方法，會披露校正數；組合上場時間屬重建值，不是官方發布的組合統計。

原始轉換器放在 `scripts/adapters/`，來自使用者提供的三個檔案；正式分析使用 `scripts/engine.py` 修正換人時間歸屬，不使用原附件的日報演算法。

## 無障礙與簡潔設計

- 繁體中文、語意化標題、主內容地標與跳至內容連結。
- 原生可用鍵盤操作的連結與展開區塊、明顯焦點、高對比文字。
- 表格有標題與欄位表頭；手機表格可在自身容器捲動，整頁不橫向溢出。
- 不只用顏色表達比分或狀態；無輪播、閃爍、動畫、圖片文字或第三方字型。
- `My Insight` 空白保留；社群名稱是未設定文字，沒有假的可點擊連結。
- axe 自動掃描只是部分驗證，不能代替實際螢幕閱讀器使用者測試。

## 本機使用

需要 Python 3.12 或以上：

```powershell
python -m pip install -r requirements.txt
python scripts/update.py
python -m unittest discover -s tests -v
python scripts/validate.py
python -m http.server 8765
```

瀏覽 `http://localhost:8765`。不要直接雙擊 HTML，因為瀏覽器對本機 `file:` JSON 讀取有限制。

`data/basketball.sqlite3` 是主要資料庫；`data/site.json` 是頁面匯出，`data/archive.json` 是歷史統計的相容匯出。`data/reports/YYYY-MM-DD.json` 保存日報，最多保留 90 天日期檔。部署只公開前端與日報，不將 SQLite 或完整歷史檔複製到發布目錄。公開儲存庫仍可讀取其檔案，因此資料庫只存公開資料。完整說明與 SQL 範例見 [DATABASE.md](DATABASE.md)。

未來個人文章可直接修改 `index.html` 的 `#insight`；社群連結設定也在同檔。需要改資料來源或新版賽事入口時，修改 `scripts/sources.py`／`scripts/update.py`。

## 單列閱讀設定與朗讀

閱讀設定包含字級、對比度、重設、朗讀、暫停／繼續及停止，維持單列；手機或放大字體時可左右捲動，鍵盤焦點也會帶出控制項。先在主要內容選取文字，或透過導覽選擇區塊，再按「朗讀」；未指定區塊時朗讀主要內容。收合的詳細資料不會朗讀。切換導覽區塊會停止朗讀，沒有自動播放。

語音使用瀏覽器內建 Web Speech API，優先選擇本機繁體中文語音，沒有該語音時由可用中文語音或瀏覽器預設處理。語音品質及是否可播放依裝置與瀏覽器提供；沒有語音或播放失敗會提示。不需付費語音 API。技術參考：[MDN SpeechSynthesis](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis)。

進階分析七項使用一致的編號、方法說明及卡片格式。前三項依使用者提供的模擬戰報參考外觀；數字仍來自官方資料，保留原有排序與變化門檻。組合個人近三場表格預設展開，可收合。資料更新會自動匯出 `keyPlayers`、`lineups` 與 `playerChanges` 結構供頁面呈現。
