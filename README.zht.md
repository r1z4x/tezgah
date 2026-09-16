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

| 主機 | 串接方式 | 狀態列 |
|---|---|---|
| **Claude Code** | 本機外掛程式市集：掛鉤 (hooks)、指令、兩個唯讀代理、輸出樣式 | 原生 `statusLine` |
| **opencode** | 外掛程式 + 指示 + MCP + 產生的技能路由器（拒絕原生技能清單），在第一則訊息時自動索引儲存庫 | TUI 外掛程式（無指令 statusLine） |
| **Codex** | `hooks.json` + 技能 + MCP，包含一個 `PreToolUse` 閘道 | 掛鉤 `systemMessage`（頁尾項目清單已關閉） |
| **Cursor** | `hooks.json` + 技能 + MCP | `cli-config.json` 中的 `statusLine` |
| **dsh** | Claude Code 掛鉤橋接器 + 受管理的修補區塊（掛鉤、MCP、LLM 路由、樹外的 Web 狀態列） | Web UI 外掛程式：工作階段標頭中的 `tezgah-dsh-statusline` |

Codex 閘道會將 Bash、`exec_command`、`apply_patch`、編輯/寫入、MCP 工具和子代理呼叫，透過與其他主機相同的檢查來執行。在 Claude 上，歸屬禁止也是機械性強制執行的：`attribution` 設定會被清空（`commit`、`pr`、`sessionUrl`），因此提交和 PR 的歸屬標註在來源處就被關閉了。

### 狀態列

每個主機都會從 `tezgah-status` 渲染相同的單行檢查清單，因此它們不會產生分歧。狀態是關鍵：當規則已武裝並在本次工作階段生效時，標記為**綠色**；當規則已武裝但按需使用（尚未被使用）時，標記為**黃色**；當被終止開關 (kill switch) 關閉時，標記為**紅色**。`idx` 會獨立報告圖的就緒狀態（`✓` 已索引，`↻` 過期，`✗` 未索引，`–` 不適用），而 `plans N (M blk)` 報告開啟的計畫。`tezgah-status --legend` 會印出圖例，`--json` 為 UI 提供相同的區段，而 `--no-color`（或 `NO_COLOR`）會強制使用純文字。Claude Code 和 Cursor 會為原生狀態列上色；opencode TUI 會為其自身元件上色並在主機事件匯流排上重新整理；dsh Web UI 會為其標頭元件上色，且僅在其分頁可見時重新整理；Codex 在 `systemMessage` 中顯示純文字字串。

dsh 透過其 `dsh-hooks-claude-code` 橋接器執行相同的 Claude 掛鉤檔案，因此工作階段啟動契約、歸屬閘道和首次 grep 提示都適用於該處。dsh 僅暴露單一的 `subagent` 工具，因此拒絕僅限 grep 的探索器 (grep-only-explorer) 是無效的——因為沒有探索器子代理可供它拒絕。dsh 預設的 `workspace-write` 沙盒將掛鉤子處理程序限制在工作區和平台暫存目錄中，因此 tezgah 會將其掛鉤狀態（提示標記、索引戳記）寫入該處的可寫入備用位置，而不是在寫入被拒絕時失敗。圖索引工作程式無法從該沙盒內部寫入 `codebase-memory-mcp` 快取，因此 `dsh` 啟動器在啟動 dsh 之前，會在使用者未受限的 shell 中預熱索引——新儲存庫的索引方式與其他主機完全相同，並帶有 HEAD 戳記。未使用啟動器啟動的工作階段仍會收到清晰的報告，指出未沙盒化的 MCP 伺服器提供圖服務，且需要對尚未索引的儲存庫執行 `index_repository`，而不是直接回傳原始的 `EPERM`。受管理的修補區塊還在基礎組合掛載的 pi-ai 轉接器上宣告了兩個相容於 OpenAI 的 LLM 路由：`openrouter` (`OPENROUTER_API_KEY`) 和 `deepseek` (`DEEPSEEK_API_KEY`)，可與原生的 `deepseek-official` 預設值一起選擇。金鑰從啟動環境或測試框架憑證儲存區解析；這兩個金鑰都不會進入設定檔。tezgah-setup 還會在 PATH (`~/.local/bin/dsh`) 上放置一個 `dsh` 啟動器，它會在 `$DSH_HOME` 下尋找已安裝的 CLI，因此 `dsh --profile web` 可以在任何目錄中運作。

dsh 沒有指令狀態列，因此 tezgah 以 Web UI 外掛程式的形式提供了一個：`tezgah-dsh-statusline`。它的主機端透過經過驗證的 `/api/tezgah.status` 路由（使用 `?format=json` 取得彩色視圖）為工作階段的工作區提供 `tezgah-status` 字串；它的瀏覽器端將其渲染在工作階段標頭中，根據狀態上色並帶有懸停/點擊圖例，且僅在分頁可見時重新整理。`tezgah-setup` 將外掛程式連結到 web 設定檔中，並透過 `profiles/web/cordis.patch.yml` 中受管理的資料列來啟用它（僅限 web，因為主機端會注入僅限 web 的 `connection` 服務）；從未啟動過 `web` 的設定檔會被跳過並給予提示，而不是寫入一半。在 `headless` 模式下，掛鉤橋接器會將 SessionStart 契約作為其自身的尾隨輪次注入（其 `agent/session-start` 會在單次任務已經是第一則訊息之後，分離地呼叫 `agent.inject()`），因此 `dsh --profile headless "<task>"` 會多花費一個輪次，並且對於字面回答的提示詞，會印出模型對契約的反應，而不是任務的答案；互動式 web 工作階段則不受影響。

`bin/tezgah-setup --install` 也會在 `orx` 位於 PATH 上時，為 Claude、Codex、opencode 和 Cursor 觸發 `orx install-skills`，以便研究規則有手冊可以載入。shim 檔案屬於 orx，因此 tezgah 僅執行該安裝程式，絕不會將它們列入解除安裝清單。dsh 沒有 orx 測試框架；那裡的研究規則會退回使用 shell 上的 `orx skill`。

Claude 外掛程式還附帶兩個唯讀代理。`agents/tezgah-explorer.md` 從圖中進行程式碼探索並回傳 `file:line` 證據；`agents/tezgah-reviewer.md` 使用 `detect_changes` 將差異 (diff) 轉換為其影響集，然後尋找真正的缺陷。兩者都停用了寫入和指令工具；它們的輸出僅供參考。

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

`--install` 也會透過**網路**執行各個供應商自己的安裝程式來安裝缺少的選用工具：`orx` (`openresearch.sh/install.sh`)、`cursor-agent` (`cursor.com/install`)、`dsh`（透過 `npx` 安裝其 home 設定檔），以及當 dsh 需要時安裝 `pnpm`（透過 `npm`）——包含 `curl ... | sh`。這些都不需要 sudo；執行過程會記錄在 `~/.config/tezgah/install.log` 中。使用 `--dry-run` 進行預覽，使用 `--no-deps` 跳過它（在 CI 中很有用），或使用 `--deps` 僅安裝工具。工具會存放在 `~/.local/bin` 或 `~/.cargo/bin` 中，因此在它們進入 PATH 之前可能需要開啟新的 shell；無論如何，tezgah 自己的檢查都會在這些目錄中尋找，因此非互動式 shell 仍會報告它們存在。

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

<a id="cost"></a>

## 成本

在本機 (macOS, Python 3.10) 上實際測量，而非估算：

- **上下文 (Context)。** 工作階段啟動時會注入約 5.4 KB（約 1.3k 個 token）的契約文字。在 Codex 上，每個輪次會附帶 954 位元組的提醒；Claude 和其他主機沒有每輪次的掛鉤，因此它們的每輪次成本為零。完整的 `tezgah-contract` 技能（約 25k 個字元）僅在任務載入它時才需要付出成本。在 opencode 上，契約作為約 5.8 KB 的指示檔案提供。否則，opencode 會將技能名稱/描述/位置文字注入到每個工作階段的系統提示詞中；tezgah 拒絕該清單 (`permission.skill = deny`)，並改為提供一個產生的技能路由器，因此可以透過從路由器讀取其 `SKILL.md` 路徑來找到技能。
- **延遲 (Latency)。** 掛鉤是獨立的 Python 處理程序，因此約 19 毫秒的直譯器啟動時間佔了主導地位。除此之外，工作階段啟動增加約 25 毫秒，受閘道控制的工具呼叫 (Bash/Grep/Task) 增加約 9 毫秒，而 Codex 的 Stop 區段每輪次增加約 15 毫秒。
- **磁碟 (Disk)。** 安裝大約需要 58 毫秒，且 tezgah 覆寫的每個檔案都會保留一次為 `<file>.tezgah-bak`。

回報體現在呼叫者的問題上。在一個真實的儲存庫中，預設的 `grep` 忽略了相關資料夾且什麼也沒找到；在停用忽略的情況下，它花費了 3.95 秒，而且仍然將定義與呼叫位置混在一起。程式碼圖在 16 毫秒內回答了相同的問題，僅列出了 8 個真正的呼叫位置。

opencode 也為長工作階段的上下文衛生進行了武裝：`tezgah-setup --install` 設定了 `compaction.prune`，因此舊的工具結果會從提示詞中清除，而不是在每個步驟中重新傳送，並且 `watcher.ignore` 清單會讓檔案監控器避開 `.git`、`node_modules` 和建置目錄。兩者都會合併——明確的使用者設定值優先。這很重要，因為 opencode 僅在接近模型的上下文限制時（對於 1M token 的模型，大約是 980k）才會自動壓縮，因此如果不進行修剪，工作集會增長到數十萬個 token。`bin/tezgah-doctor` 會報告產生的磁碟佔用空間；`--prune-sessions DAYS` 透過 opencode CLI 刪除閒置的工作階段，這是唯一能實際縮小資料庫的動作——單靠 VACUUM 是無法做到的，因為它的分頁都是活躍的。

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
