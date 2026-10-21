# TASTE 改版與 NBL 接入驗證

日期：2026-10-21（Asia/Taipei）。

## 完成範圍

- 依 [TASTE Skill](https://github.com/Leonxlnx/taste-skill/blob/6010f91a9935f1c167dfc500fb1a475681892e6b/skills/taste-skill/SKILL.md) 的報表方向調整既有網站；固定版本 `6010f91a9935f1c167dfc500fb1a475681892e6b`，方向 `achromatic-ledger`，種子 `20261021`。
- 保留原有 HTML／CSS／JavaScript、系統中文字型、品牌名稱、閱讀與朗讀設定、研究文章、規則下載、個人圖片及郵箱。縮短引言、統一層級、對齊比分，桌機並排顯示近期賽程與賽果，手機改為上下排列；表格需要時可水平捲動。
- 尊重使用者簡潔、視障友善、少照片與特效的要求，不套用技能偏向展示網站的多照片、動態場景及大型標題建議。
- NBL 加入既有官方更新、SQLite、歷史篩選、單場分析、每日戰報及網站查詢工具。保持每日臺北時間 23:00 的排程（UTC `0 15 * * *`）；GitHub 排程可能延後執行，不是即時比分服務。

## NBL 資料驗證與處理

一手來源及三場獨立查核見 [NBL-OFFICIAL-RESEARCH-2026-10-21.md](NBL-OFFICIAL-RESEARCH-2026-10-21.md)。

- 賽程：`https://schedule.nbl.com.au/api/calendar/schedule?league=NBL&year=2026`。
- 單場：`https://schedule.nbl.com.au/api/calendar/match?match=<官方賽事ID>&league=NBL`。
- 排除測試、季前賽及 Blitz；目前收取 regular、playoffs、postseason 類型。未辨識類型先略過。時間依官方 UTC epoch 轉臺北時間。
- 只用 `period=0` 作全場統計，核對賽程／單場比分、球員得分合計及隊伍得分。USG 分母採官方隊伍失誤，包含球員個人失誤合計之外的團隊失誤。
- 官方事件陣列順序不可靠，依 action_id 保存官方事件次序，仍可偵測到補登與時間倒退；不依時鐘靜默重排來宣稱戰術或陣容有效。時間、比分、換人等驗證不足時，受影響的 ATO、最後五分鐘與五人組合停止判定；USG、EFF 等獨立 box score 指標仍可顯示。
- 初次更新保存 165 場 NBL 賽程，其中最近 5 場有詳細統計，未來七天 7 場；全部來源更新未回報抓取錯誤。近三場歷史樣本不足時，球員變化提示保持「資料不足」。

## 實際測試

| 檢查 | 結果 |
|---|---|
| Python 單元與整合測試 | 43 項通過，含新增 6 項 NBL 測試 |
| WebMCP 查詢測試 | 4 項通過 |
| 瀏覽器回歸 | 通過；749 場歷史、單一比賽日 13 場不截斷、NBL 篩選與單場頁、14 篇研究與 6 項方法、零 JavaScript 例外 |
| SQLite | integrity／foreign keys／比分檢查通過；公開輸出排除 SQLite 原檔 |
| axe-core 4.10.3 | 6 頁 × 標準／高對比／深色，共 18 次；WCAG 2 A／AA、2.1 AA、2.2 AA 規則零違規 |
| 放大與鍵盤 | 6 頁於 320px、200% 字級無頁面整體水平溢出；跳至主要內容焦點通過 |
| TASTE inspect | 修改前 2 FAIL／5 WARN；最終 0 FAIL／2 WARN |

自動檢測不能證明全面符合 WCAG。真人螢幕閱讀器、原始規則 PDF 標籤與閱讀順序仍待人工驗收。朗讀語音由裝置與瀏覽器提供。

本機 Windows 曾鎖定大型 archive.json 的重新命名；SQLite 交易已成功，改從相同資料庫匯出至暫存目錄後覆寫 JSON，完成一致性檢查。正式 Linux 更新程式保留原有原子匯出流程，發布後以 Actions 實際執行結果確認。

## 視覺檢視與保留事項

已實看桌機、平板、手機截圖及整頁分段。頁面以官方紀錄、數字及來源連結為主，沒有新增裝飾圖、動畫或付費服務。兩項 TASTE 提醒：不同資訊長度造成欄位底部不齊；首頁包含多聯盟、研究與規則，仍需捲動。保留自然高度及既有資訊順序，避免強制高度造成空白或隱藏內容。

依 TASTE 視覺 rubric 的人工自評：設計 6.5、易用性 8、創意 6、內容 8；加權 7.0，但依其照片／展示型評分上限保守記 6.5。此為單次主觀設計評估，不是外部評審成績或 WCAG 認證。

## 重跑方式

- 原有排程直接執行 `python scripts/update.py`、`python scripts/validate.py`、`python scripts/build_public.py`；不需增加 NBL 密鑰、額外排程或付費資料庫。
- `python -m unittest discover -s tests -v`。
- `node --test tests/test_webmcp.cjs`。
- `node tests/check_pages.cjs` 需 Playwright 與 Chrome，環境變數 `BASKETBALL_TEST_BROWSER=chrome`。
- `node tests/check_accessibility.cjs` 需 Playwright、Chrome、已安裝的 axe-core；將 `BASKETBALL_AXE_PATH` 指向其 axe.min.js，網站預設 `http://127.0.0.1:8770/`，可用 `BASKETBALL_TEST_URL` 覆寫。

技能下載與方向／截圖保存在本機 `.taste-skill/`，已加入忽略清單，不作網站執行依賴。
