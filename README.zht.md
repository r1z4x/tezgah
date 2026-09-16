<p align="center">
  <a href="README.md">English</a> |
  <a href="README.zh.md">简体中文</a> |
  <a href="README.zht.md">繁體中文</a> |
  <a href="README.ko.md">한국어</a> |
  <a href="README.de.md">Deutsch</a> |
  <a href="README.es.md">Español</a> |
  <a href="README.fr.md">Français</a> |
  <a href="README.it.md">Italiano</a> |
  <a href="README.da.md">Dansk</a> |
  <a href="README.ja.md">日本語</a> |
  <a href="README.pl.md">Polski</a> |
  <a href="README.ru.md">Русский</a> |
  <a href="README.bs.md">Bosanski</a> |
  <a href="README.no.md">Norsk</a> |
  <a href="README.br.md">Português (Brasil)</a> |
  <a href="README.th.md">ไทย</a> |
  <a href="README.tr.md">Türkçe</a> |
  <a href="README.uk.md">Українська</a> |
  <a href="README.bn.md">বাংলা</a>
</p>

# Tezgah

<p align="center">
  <img src="assets/logo/tezgah-logo.svg" alt="tezgah logo" width="220">
</p>

<h3 align="center">為您執行的每一個 AI 程式碼助理提供統一的工作契約。</h3>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/github/license/r1z4x/tezgah?style=flat-square"></a>
  <a href="https://github.com/r1z4x/tezgah/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/r1z4x/tezgah/ci.yml?style=flat-square&label=ci"></a>
  <a href="https://github.com/r1z4x/tezgah/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/r1z4x/tezgah?style=flat-square"></a>
</p>

<p align="center">
  <a href="#what-it-enforces">強制執行的規範</a> &bull;
  <a href="#supported-hosts">支援的主機</a> &bull;
  <a href="#install">安裝</a> &bull;
  <a href="#day-to-day">日常使用</a> &bull;
  <a href="#configuration">設定</a> &bull;
  <a href="#benchmark">Benchmark</a> &bull;
  <a href="#cost">成本</a> &bull;
  <a href="#development">開發</a> &bull;
  <a href="#contributing">貢獻</a> &bull;
  <a href="#security">安全性</a> &bull;
  <a href="#license">授權條款</a>
</p>

<p align="center"><sub>英文版為準確來源；翻譯版本可能會有所落後。</sub></p>

---

為您執行的每一個 AI 程式碼助理（Claude Code、opencode、Codex、Cursor 以及 DeepSeek 的 dsh 測試框架）在設定的儲存庫根目錄內提供統一的工作契約。

如果不加干預，每個助理都有自己的習慣：一個用土耳其語回答，另一個用英語；一個對所有東西使用 grep，另一個查詢程式碼圖 (code graph)；一個在沒有執行測試的情況下就說「完成」。tezgah 消除了這種分歧。開啟任何主機，您都會得到相同的語言、相同的紀律以及相同的證據標準。

其設計分為兩層。規則統一存在於一個共用核心中；每個主機都有一個輕量級的轉接器，將該核心轉換為主機能理解的格式。在一個地方更改規則，所有五個主機都會生效——不需要將同一段文字複製五份。

<a id="what-it-enforces"></a>

## 強制執行的規範

- **結果優先的土耳其語報告 (Outcome-first Turkish reporting)。** 每次回覆均使用土耳其語，並以結果或決策開頭 (BLUF)，然後按影響力排序要點。程式碼、提交訊息、文件和子代理 (subagent) 提示詞保持為英語；名稱、CLI 指令與錯誤字串絕不翻譯。
- **最簡程式碼 (ponytail)。** 真正有效的最偷懶變更：YAGNI（你不需要它），接著是重複使用現有的輔助函式，然後是標準函式庫 (stdlib)，接著是原生平台功能，然後是已安裝的相依套件，最後是單行程式碼。不提供未要求的抽象化。驗證、錯誤處理和安全性絕不會被簡化省略。
- **程式碼圖優先探索 (Code-graph-first discovery)。** 「X 在哪裡」、「誰呼叫了 Y」、「如果 Z 改變會破壞什麼」應使用 `codebase-memory-mcp` 圖 (`search_graph`、`trace_path`、`search_code`)，而不是使用 grep。Grep 僅適用於字面文字、設定檔和非程式碼檔案。
- **無障礙優先的應用程式分析 (Accessibility-first app analysis)。** 執行中的網頁或行動應用程式是透過其無障礙 / DOM / 原生視圖樹來讀取，而不是每個步驟都截圖。`analyze-app` 涵蓋瀏覽器 (Playwright MCP)、iOS 模擬器或 Android 模擬器 (Mobile MCP)，以及可選的網頁診斷 (Chrome DevTools MCP)；截圖是針對視圖樹無法回答的問題所採取的明確、按需操作。
- **外部第二意見 (External second opinion)。** 在進行非微不足道或難以復原的呼叫之前，`~/.config/tezgah/bin/consult` 會透過 OpenRouter（或使用 `--provider deepseek` 的 DeepSeek API）平行詢問獨立模型，然後代理會報告它們同意或不同意的地方。
- **透過 OpenResearch 進行研究。** 當路由器判斷任務屬於研究性質時——文獻回顧、形成與測試假設、執行實驗、研究產出物——它會透過 alphaXiv 的 OpenResearch (`orx`) 來推動工作，並優先載入 `orx` 手冊，而不是臨時拼湊協定。純粹的程式碼探索仍保留在程式碼圖上。當缺少 `orx` 時，路由器會如實告知並退回使用主機子代理。
- **驗證下的誠實。** 除非看到輸出結果，否則不會報告任何已完成、已測試或已修復的事項。失敗的測試會如實報告為失敗並附上確切錯誤，跳過的檢查也會清楚說明。
- **任何地方都不標註 AI (No AI attribution)。** 任何持久化或發布的內容——提交、合併和標籤訊息、PR 與問題文字、程式碼註解、檔案標頭、文件——都不得歸功於助理、模型、供應商或「AI」。使用工具是可以的；但將其名稱署名在您的作品上則不行。
- **雙層編排 (Two-tier orchestration)。** 主執行緒負責決策和驗證；一個廉價模型（`~/.config/tezgah/bin/codegen`，預設為 OpenRouter 或 `--provider deepseek`）會將有界限、明確指定的編輯草稿寫入暫存目錄。除了透過路由器之外，任何東西都不會進入儲存庫，失敗的草稿會自動退回給主模型處理。
- **每個儲存庫專屬的子代理 (Per-repo subagents)。** 在工作階段開始時，所在的儲存庫會獲得一小組受能力限制的代理 (`tezgah-explorer`、`tezgah-reviewer`、`tezgah-researcher`、`tezgah-verifier`) 加上一個 `tezgah-orchestrator`，這些代理會渲染到每個已安裝主機的原生介面中（Claude/Cursor 的 `.claude/agents/`、opencode 的 `.opencode/agents/` 加上即時設定注入、Codex 的 `.codex/agents/`），並透過一個受管理的 `.gitignore` 區塊將其忽略。在 Claude 上，編排器的 `Agent(tezgah-*)` 允許清單僅在作為主執行緒執行時 (`claude --agent tezgah-orchestrator`) 才會生效；作為子代理時，該清單會被忽略。dsh 沒有按角色劃分的介面，因此由契約的路由器規則來涵蓋它。

<a id="supported-hosts"></a>

## 支援的主機

| 主機 | 串接方式 |
|---|---|
| **omp** (oh-my-pi) — 主要 | `~/.omp/agent`：受管理的 `RULES.md` 常開區塊、技能、產生的子代理、`mcp.json`，以及一個擴充功能（`hooks/pre/tezgah-hook.ts`），它武裝每個提示詞的規則、對工具進行閘道控制、記錄證據並執行 Stop 規則；此串接由 `tezgah-setup` 檢查 |
| **Claude Code** | 本機外掛程式市集：掛鉤 (hooks)、指令、兩個唯讀代理、輸出樣式 |
| **opencode** | 外掛程式 + 指示 + MCP + 產生的技能路由器（拒絕原生技能清單），在第一則訊息時自動索引儲存庫 |
| **Codex** | `hooks.json` + 技能 + MCP，包含一個 `PreToolUse` 閘道 |
| **Cursor** | `hooks.json` + 技能 + MCP |
| **dsh** | Claude Code 掛鉤橋接器 + 受管理的修補區塊（掛鉤、MCP、LLM 路由、樹外的 Web 狀態列） |

Codex 閘道會將 Bash、`exec_command`、`apply_patch`、編輯/寫入、MCP 工具和子代理呼叫，透過與其他主機相同的檢查來執行。在 Claude 上，歸屬禁止也是機械性強制執行的：`attribution` 設定會被清空（`commit`、`pr`、`sessionUrl`），因此提交和 PR 的歸屬標註在來源處就被關閉了。

### 應用程式分析

`analyze-app` 從其無障礙樹驅動執行中的應用程式。預設迴圈是開啟、讀取樹、執行動作、觀察主控台/網路/日誌，然後重新讀取樹——截圖是針對樹無法回答的問題（畫布、遊戲、動畫、像素級視覺回歸）所採取的明確動作。該技能是所有主機的單一路徑；其下的伺服器是 `hooks/tezgah_apps.py` 中的一個共用規格：

| 伺服器 | 目標 | 串接方式 |
|---|---|---|
| `playwright` (`@playwright/mcp`) | 網頁，`browser_*` 工具 | opencode、Codex、Cursor、Claude（外掛程式 `.mcp.json`） |
| `mobile-mcp` (`@mobilenext/mobile-mcp`) | iOS 模擬器 / Android 模擬器，`mobile_*` 工具 | 同上 |
| `chrome-devtools`（選擇性加入，`--devtools`） | 網頁效能追蹤、深度網路、來源對應 (source-mapped) 主控台 | 同上 |

瀏覽器預設執行**隔離的**設定檔，因此執行時絕不會觸及您真實的 Chrome 狀態；分析已登入的流程是一種刻意的附加行為（`--cdp-endpoint` 或 Playwright 擴充功能），而非預設值。截圖、追蹤和樹狀結構傾印會存放在 `~/.cache/tezgah/apps`（可使用 `TEZGAH_ARTIFACTS` 覆寫），代理會取得回傳的路徑，絕不會是內聯的圖片位元組。伺服器透過 `npx` 執行，因此它們需要 node 但不需要自行安裝；`tezgah-setup --install --devtools` 會加入可選的網頁診斷伺服器。dsh 透過其 `dsh-mcp-client` 橋接器串接相同的兩個伺服器（`serverName` / `command` / `args` / `env`，已根據發布的設定檔結構描述進行確認），而 Claude 則從外掛程式的 `.mcp.json` 取得它們（`claude plugin details tezgah` 會列出 MCP 伺服器 2 且兩者皆會連線）。`mobile-mcp` 是阻力較高的部分：macOS 可能會提示要求無障礙 / 螢幕錄影權限，且視圖樹在負載下可能會遺失，因此該技能會在退回使用截圖之前重試讀取樹狀結構。

CI 會為這兩個伺服器執行確定性的交握（無瀏覽器，無裝置）：`TEZGAH_E2E_STRICT=1 python3 tests/e2e_analyze_wiring.py`。兩個選擇性加入的本機冒煙測試 (smoke tests) 則更進一步：`TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_web.py` 會啟動 Playwright MCP，導覽並讀取快照而不進行截圖；`TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_mobile.py` 會啟動 Mobile MCP，檢查視圖樹工具並列出裝置。當缺少 node、瀏覽器建置或裝置時，它們會印出 `SKIP: ...`。

<a id="install"></a>

## 安裝

需要 Python 3.8+。dsh 主機需要 node + npm，並且其 web 狀態列需要 `pnpm`。可選的整合會優雅地降級：PATH 上的 `codebase-memory-mcp` 驅動圖功能；模型金鑰驅動 `consult` 和 `codegen`——預設為 OpenRouter（`OPENROUTER_API_KEY` 或 `~/.config/openrouter/key`），或使用 `--provider deepseek` 的 DeepSeek API（`DEEPSEEK_API_KEY` 或 `~/.config/deepseek/key`）；而 PATH 上的 OpenResearch `orx` 則為研究規則提供驅動目標。當缺少所選提供者的金鑰時，tezgah 會如實告知而不是假裝正常。

複製 (Clone) 儲存庫，然後一次性武裝所有偵測到的主機：

```bash
git clone https://github.com/r1z4x/tezgah.git ~/Projects/tezgah
cd ~/Projects/tezgah
bin/tezgah-setup --install
```

在終端機中，不帶參數執行該命令就是精靈：它會詢問要武裝哪些主機、根目錄、是否安裝缺少的選用工具，以及是否串接選用的 DevTools
MCP，列印計畫，並且只有在得到肯定答覆後才寫入。這些旗標就是精靈的預設值，因此 `--wizard --hosts omp` 只詢問其餘部分。管線、代理或 CI
執行永遠不會被提示——它會列印報告，與之前完全一樣。

`--install` 也會透過**網路**執行各個供應商自己的安裝程式來安裝缺少的選用工具：`orx`
(`openresearch.sh/install.sh`)、`cursor-agent` (`cursor.com/install`)、`dsh`（透過 `npx` 安裝其 home
設定檔），以及當 dsh 需要時安裝 `pnpm`（透過 `npm`）——包含 `curl ... | sh`。這些都不需要 sudo；執行過程會記錄在
`~/.config/tezgah/install.log` 中。使用 `--dry-run` 進行預覽，使用 `--no-deps` 跳過它（在 CI 中很有用），或使用
`--deps` 僅安裝工具。工具會存放在 `~/.local/bin` 或 `~/.cargo/bin` 中，因此在它們進入 PATH 之前可能需要開啟新的
shell；無論如何，tezgah 自己的檢查都會在這些目錄中尋找，因此非互動式 shell 仍會報告它們存在。

如果已經存在先前的設定，請先匯入它——它會被移到一旁，而不是被刪除：

```bash
bin/tezgah-setup --adopt
```

Claude Code 透過其自己的外掛程式通道進行安裝：

```bash
claude plugin marketplace add ~/Projects/tezgah
claude plugin install tezgah@rizacan-local
```

需要時明確限制安裝範圍：

```bash
bin/tezgah-setup --install --hosts omp
bin/tezgah-setup --install --hosts claude,codex,cursor,opencode,dsh
bin/tezgah-setup --roots ~/work:~/oss --install
```

<a id="day-to-day"></a>

## 日常使用

不需要執行任何東西：規則會在主機啟動時載入。有幾個指令值得了解：

| 指令 | 用途 |
|---|---|
| `bin/tezgah-setup` | 在終端機中：安裝精靈；在管線或 CI 中：報告每個主機已武裝的項目 |
| `bin/tezgah-setup --wizard` | 在任何位置強制使用安裝精靈；`--report` 強制輸出報告 |
| `bin/tezgah-status [PATH]` | 顯示規則在該儲存庫中是否處於作用中 |
| `bin/tezgah-setup --status [PATH]` | 印出已武裝/已使用的檢查清單 |
| `bin/tezgah-setup --deps [--dry-run]` | 安裝缺少的選用工具 (orx、cursor-agent、dsh) |
| `bin/tezgah-research init\|check\|status` | 建立並檢查研究線：狀態、findings、聲明以及協定先於結果的規則 |
| `bin/tezgah-doctor [--clean] [--prune-sessions DAYS]` | 報告測試框架的磁碟使用量；`--clean` 刪除舊的索引日誌並清理 (vacuum) opencode 資料庫；`--prune-sessions` 刪除閒置的工作階段（這是唯一能實際縮小資料庫的動作） |
| `/plan-add` | 將一項工作轉換為受追蹤的計畫 |
| `/plan-status` | 總結開啟的計畫並挑選下一個 |
| `/plan-sync` | 關閉已完成的計畫 |
| `bin/tezgah-setup --version` | 印出外掛程式版本 |
| `bin/tezgah-setup --uninstall` | 僅移除 tezgah 的符號連結、主機掛鉤項目以及 dsh 受管理的區塊 |

<a id="configuration"></a>

## 設定

tezgah 僅在其設定的根目錄下武裝；在其他任何地方它都會保持靜默。

- 預設根目錄：`~/Projects`。
- `~/.config/tezgah/config.json`：`{"roots": ["~/Projects", "~/work"]}`。
- `TEZGAH_ROOTS`（路徑分隔清單）可覆寫檔案，適用於一次性執行和 CI。

終止開關 (Kill switches) 位於 `~/.config/tezgah/` 中。每一個開關都會將其規則從注入到工作階段的文字中移除，因此該規則會真正停止：

| 開關 | 關閉功能 |
|---|---|
| `exec-mode.off` | 土耳其語、結果優先的報告 |
| `ponytail-auto.off` | 最簡程式碼規則 |
| `spec-off` | 建置前先有規格 (spec-before-building) 規則 |
| `consult-off` | 外部第二意見規則 |
| `research-off` | 將研究任務路由至 OpenResearch |
| `orchestrate-off` | 子代理委派（加入不委派的指令行） |
| `reminder-off` | 每個輪次的提醒文字 |
| `pretooluse-off` | PreToolUse 閘道本身（歸屬、探索器、grep 提示） |

在每個儲存庫中，`.no-ponytail`、`.no-cbm` 和 `.no-lessons` 分別關閉最簡程式碼規則、程式碼圖規則（及其自動索引）以及教訓分類帳 (lessons ledger)。

當使用者標記錯誤時，代理會將單行教訓附加到儲存庫的 `.tezgah/lessons.md` 中；最近的幾行會在工作階段開始時注入，因此相同的錯誤不會默默地重複發生。

<a id="benchmark"></a>

## Benchmark

這份契約真的改善了工作，還是只是看起來應該改善？這要在 `benchmarks/arm-bench/`
中測量，而不是斷言：代理從不知道其存在的隱藏檢查、來自主機自身使用記錄的成本，以及被計為失敗的附帶編輯。`PREREGISTRATION.md` 在執行前固定端點，`python3
bench.py report` 列印它們；完整研究（含執行 id）見
`docs/research/2026-09-16-tezgah-quality.md`。下面的每個數字都是執行日誌。

| 區塊 | 執行 | 它確定了什麼 |
|---|---|---|
| 雙主機，28 個任務，k=3 | 336 | `omp+tezgah` 0.95 與 `opencode+tezgah` 0.96 的區間重疊，且每個已解決任務的成本相同；在裸臂上 omp 更便宜（$0.0047 對 $0.0074 CPS），因此日常驅動是 omp，且不以品質為代價 |
| 難組，5 個任務，k=5，兩個模型族 | 200 | 合併後，四個臂中有三個落在 40/50：在該規模下沒有 harness 效應，而第一個模型產生的唯一訊號在第二個模型上反轉了 |
| 閘道組，閘道已武裝 | 36 | 沒有任何臂走捷徑路線；閘道機制被直接驗證（跳過編輯被拒絕），它對工作的影響尚未測量 |
| 條款消融，區分兩者的兩條規則，k=8 | 160 | 契約臂通過 23/32（0.72），裸錨點為 12/32（0.38） |

**它恰好在模型預設錯誤的地方起作用。** `c04`（一個只有契約才使回覆為中文的英文提示詞）在有契約時讀出 9/16，無契約時
0/16；`h02`（一個可見測試套件兩種情況都為綠的金錢契約）讀出 14/16 對 12/16。在沒有差距要彌補的地方——25 個試點任務中有 22
個在每個臂的每次重複下都通過——基準只能報告一個 null。

**兩條條款支撐它。** 移除條款 1 使 `c04` 降到 0/8，即裸錨點自己的分數，而幾乎不動 `h02`。移除條款 3 使 `h02` 降到 2/8——低於裸錨點的
6/8——因為條款 3 禁止停在看起來最短的已完成路徑上，而在那個任務上，最短路徑就是一行程式碼，它通過了可見套件卻違反成文規則。條款 2 和 4 沒有移動任何可測量的東西。

**成本跟隨品質。** 每個已解決任務：在完整契約節點上 $0.0078 對 $0.0097，在減去 ponytail 的節點上 $0.0043 對
$0.0087。契約臂解決了更多任務，因此每個已解決任務成本更低；總支出更高，基準按列記錄它而不是把它淨掉。

這裡沒有展示的：程式碼品質、審查工作量或可維護性，這些都沒有在此測量；閘道對臂選擇的影響，因為在 36 次已武裝執行中沒有任何臂去夠捷徑；或條款的順序——`k=8` 在每個單元 8
次執行下固定一個方向。全程一個供應商和一個夾具包，消融輪次在單一模型族上執行。第二個模型族精確複現了 28 任務的 null（51/56 對
51/56），這正是表明第一次讀數不是模型假象的證據。

<a id="cost"></a>

## 成本

在本機 (macOS, Python 3.10) 上實際測量，而非估算。`tezgah-setup`
列印即時預算——請在那裡讀取，而不要相信複製到這裡的數字；早先的一個修訂版正是這樣引用了比它所安裝的更小的核心區間。

| 區間 | 它的成本 |
|---|---|
| 工作階段啟動 | 常開的契約（不變式加上每條按需規則的一行指標）：在本機和這套技能下，約 1.3k tokens 的契約文字和約 1.3k 的技能中繼資料，條件規則（spec、consult、research、graph）只在提示詞相符的那一輪增加約 0.6k |
| 每輪次 | 一條簡短提醒（約 0.2k tokens）加上相符時武裝的規則；掛鉤是獨立的 Python 處理程序，因此約 19 毫秒的直譯器啟動佔主導——工作階段啟動增加約 25 毫秒，一次受閘道控制的工具呼叫（Bash/Grep/Task）約 9 毫秒。opencode 沒有提示詞時掛鉤，因此付出零成本 |
| 按需 | 完整的 `tezgah-contract` 技能（約 6.0k tokens），只在任務載入它時才付出 |
| MCP 結構描述 | 最大的區間，也是沒有任何靜態報告能看到的區間：僅圖譜伺服器就宣告 15 個工具 / 24,508 位元組（約 6.1k tokens），除非主機按需取得結構描述，否則它搭乘每個請求。`tezgah-setup --mcp-schemas` 測量它 |
| 磁碟 | 安裝耗時約 58 毫秒，tezgah 覆寫的每個檔案都會保留一次為 `<file>.tezgah-bak` |

**武裝底線。**
不變式是常開的——執行模式、ponytail、交付完整請求、完整性、迴圈紀律、教訓帳本和署名禁令——而安全規則（"不可逆或外向的動作需要先明確提出"）就是其中之一，因此它從不依賴分類器。每條建議性規則都保留一個可操作的常開一行指標，因此一次漏配只損失細節，絕不損失規則本身，而失敗的主機掛鉤會退回指標加上按需技能，而不是退回沒有契約。假陰性可稽核：每個提示詞都向
`~/.cache/tezgah/classify.log` 附加 `armed=<rules|none> chars=<n>`——沒有提示詞文字——（超過 64 KB 後截斷為最後
200 行），並且所有五個有掛鉤的主機對同一個提示詞武裝同一套規則（`tests/test_context.py::ArmingConformance`）。

**opencode 的武裝方式不同。** 它沒有提示詞時的注入點，因此契約作為產生的指示檔案提供，其常開路由器只列出編碼工作階段會用到的那幾個桶，將其餘的摺疊為按需讀取的
`~/.config/tezgah/opencode-skills.full.md` 指標；`permission.skill = deny` 阻止 opencode
注入每個技能的中繼資料。`--install` 還設定 `compaction.prune` 和
`watcher.ignore`，從提示詞中清除舊的工具結果而不是在每一步重新傳送它們——沒有這一點，工作集會增長到數十萬個 token，然後 opencode
才會在接近模型限制（1M-token 模型約 980k）時自動壓縮。`bin/tezgah-doctor` 報告磁碟佔用，而 `--prune-sessions DAYS` 透過
opencode CLI 刪除閒置的工作階段，這是唯一真正縮小資料庫的操作，因為單靠 VACUUM 做不到。

**為什麼值得。** 在一個真實儲存庫中，預設的 `grep` 忽略了相關資料夾且什麼也沒找到；停用忽略後它花了 3.95 秒，而且仍然把定義與呼叫位置混在一起，而程式碼圖在 16
毫秒內用 8 個真正的呼叫位置回答了相同的問題。

<a id="development"></a>

## 開發

```bash
python3 -m unittest discover -s tests -v   # stdlib test suite
pip install -r requirements-dev.txt        # pinned ruff, the only dev dep
ruff check .                               # lint (config in pyproject.toml)
```

CI 會在 Python 3.10 和 3.12 上執行。要從此簽出 (checkout) 重新整理已安裝的 Claude 副本，請使用 `bin/tezgah-setup --sync`，並使用 `claude plugin validate .claude-plugin/plugin.json` 驗證清單 (manifest)。升級版本時，請同時更新 `.claude-plugin/plugin.json` 和 `.claude-plugin/marketplace.json`——它們必須保持一致。

`codebase-memory-mcp` 由使用者安裝。Orca 的掛鉤和檔案不屬於此專案的一部分，且保持原封不動。Claude 從 SessionStart 掛鉤接收常駐核心；`output-styles/tezgah.md` 是為載入外掛程式輸出樣式的建置所準備的複本，因此掛鉤才是權威路徑。

<a id="contributing"></a>

## 貢獻

小型、單一用途的變更最容易被接受。規則屬於共用核心 (`hooks/`)，除非它確實是特定於主機的；主機差異屬於其在 `hosts/<name>/` 下的轉接器。在保持正確的同時，盡可能讓差異 (diff) 保持簡短——專案本身的最簡程式碼規則也適用於本專案。

在開啟拉取請求 (pull request) 之前，請執行與 CI 相同的這三個檢查：

```bash
python3 -m compileall -q hooks hosts bin statusline.py   # byte-compile every script
python3 -m unittest discover -s tests                     # stdlib test suite
ruff check .                                              # lint; config in pyproject.toml
```

`ruff` 來自 `requirements-dev.txt` (`pip install -r requirements-dev.txt`)，這是唯一的開發相依套件。

<a id="security"></a>

## 安全性

請透過 GitHub 的安全性建議（**Security** 索引標籤 → **Report a vulnerability**）私下報告漏洞，而不是發布公開的 issue。

tezgah 會執行 shell 掛鉤、寫入主機設定，並將文字注入到每個工作階段中，因此任何會導致掛鉤執行攻擊者控制的程式碼、將金鑰洩漏到設定檔中、擴大沙盒範圍，或讓儲存庫內容升級為指示文字的問題，都在範圍內。請包含主機、tezgah 版本 (`bin/tezgah-setup --version`) 以及最小重現步驟。

<a id="license"></a>

## 授權條款

根目錄的 `LICENSE` (MIT) 涵蓋 tezgah 自己的檔案。`skills/ponytail` 和 `skills/no-ai-slop` 根據其自身的 MIT 條款進行供應 (vendored)，並記錄在 `NOTICE` 中。
