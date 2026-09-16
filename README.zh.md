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

<h3 align="center">为你运行的每一个 AI 编程助手提供统一的工作契约。</h3>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/github/license/r1z4x/tezgah?style=flat-square"></a>
  <a href="https://github.com/r1z4x/tezgah/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/r1z4x/tezgah/ci.yml?style=flat-square&label=ci"></a>
</p>

<p align="center">
  <a href="#what-it-enforces">强制执行的规则</a> &bull;
  <a href="#supported-hosts">支持的宿主</a> &bull;
  <a href="#install">安装</a> &bull;
  <a href="#day-to-day">日常使用</a> &bull;
  <a href="#configuration">配置</a> &bull;
  <a href="#cost">开销</a> &bull;
  <a href="#development">开发</a> &bull;
  <a href="#contributing">贡献</a> &bull;
  <a href="#security">安全</a> &bull;
  <a href="#license">许可证</a>
</p>

<p align="center"><sub>英文版本为准；翻译版本可能存在滞后。</sub></p>

---

为你运行的每一个 AI 编程助手——Claude Code、opencode、Codex、Cursor 以及 DeepSeek 的 dsh 框架——在一组配置好的代码库根目录下，提供统一的工作契约。

如果不加干预，每个助手都有自己的习惯：一个用土耳其语回答，另一个用英语；一个对所有东西都用 grep，另一个则查询代码图谱；一个没跑测试就说“完成了”。tezgah 消除了这种偏差。打开任何宿主，你都会得到相同的语言、相同的纪律以及相同的证据标准。

其设计分为两层。规则在共享核心中只存在一份；每个宿主都有一个轻量级适配器，将该核心转换为宿主能理解的形式。在一个地方修改规则，所有五个宿主都会生效——不需要将同一段文本复制五份。

<a id="what-it-enforces"></a>

## 强制执行的规则

- **结果优先的土耳其语报告。** 每次回复均使用土耳其语，并以结果或决定开头（BLUF，结论先行），然后按影响程度对要点进行排序。代码、提交信息、文档和子代理提示词保持英语；名称、CLI 命令和错误字符串绝不翻译。
- **极简代码 (ponytail)。** 真正有效的最懒惰的更改：YAGNI（你不需要它），然后重用现有的辅助函数，接着是标准库，再是原生平台功能，然后是已安装的依赖，最后是一行代码。不提供未要求的抽象。验证、错误处理和安全性绝不能被简化掉。
- **代码图谱优先的发现机制。** “X 在哪里”、“谁调用了 Y”、“如果 Z 改变会破坏什么”等问题会交给 `codebase-memory-mcp` 图谱（`search_graph`、`trace_path`、`search_code`），而不是使用 grep。grep 仅适用于字面文本、配置文件和非代码文件。
- **无障碍优先的应用分析。** 运行中的 Web 或移动应用通过其无障碍 / DOM / 原生视图树进行读取，而不是每步截取一张屏幕截图。`analyze-app` 涵盖浏览器（Playwright MCP）、iOS 模拟器或 Android 模拟器（Mobile MCP），以及可选的 Web 诊断（Chrome DevTools MCP）；屏幕截图是针对视图树无法回答的问题而采取的明确的、按需执行的操作。
- **外部第二意见。** 在进行非平凡或难以撤销的调用之前，`~/.config/tezgah/bin/consult` 会通过 OpenRouter（或使用 `--provider deepseek` 的 DeepSeek API）并行询问独立的模型，然后代理会报告它们达成一致或存在分歧的地方。
- **通过 OpenResearch 进行研究。** 当路由器判断一项任务属于研究时——文献综述、形成和测试假设、运行实验、研究产物——它会通过 alphaXiv 的 OpenResearch (`orx`) 驱动工作，并首先加载 `orx` 手册，而不是临时拼凑协议。纯代码发现仍保留在代码图谱上。当缺少 `orx` 时，路由器会说明情况并回退到宿主子代理。
- **验证下的诚实。** 除非看到了输出结果，否则绝不报告已完成、已测试或已修复。失败的测试会如实报告为失败并附上确切的错误信息，跳过的检查也会被清楚地说明。
- **任何地方都没有 AI 署名。** 任何持久化或发布的内容——提交、合并和标签信息、PR 和 issue 文本、代码注释、文件头、文档——都不得归功于助手、模型、供应商或“AI”。使用工具没问题；把它的名字签在你的工作成果上则不行。
- **双层编排。** 主线程负责决策和验证；一个廉价模型（`~/.config/tezgah/bin/codegen`，默认为 OpenRouter 或 `--provider deepseek`）向临时目录起草有边界的、规范明确的编辑。除了通过路由器，任何内容都无法进入代码库，失败的草稿会自动回退到主模型。
- **每个代码库的子代理。** 在会话开始时，所在的代码库会获得一小组受能力限制的代理（`tezgah-explorer`、`tezgah-reviewer`、`tezgah-researcher`、`tezgah-verifier`）加上一个 `tezgah-orchestrator`，它们被渲染到每个已安装宿主的原生界面中（Claude/Cursor 的 `.claude/agents/`，opencode 的 `.opencode/agents/` 加上实时配置注入，Codex 的 `.codex/agents/`），并通过一个受管的 `.gitignore` 块被忽略。在 Claude 上，orchestrator 的 `Agent(tezgah-*)` 允许列表仅在它作为主线程运行（`claude --agent tezgah-orchestrator`）时生效；作为子代理时，该列表会被忽略。dsh 没有按角色的界面，因此契约的路由器规则涵盖了它。

<a id="supported-hosts"></a>

## 支持的宿主

| 宿主 | 接入方式 | 状态栏 |
|---|---|---|
| **Claude Code** | 本地插件市场：钩子、命令、两个只读代理、输出样式 | 原生 `statusLine` |
| **opencode** | 插件 + 指令 + MCP + 生成的技能路由器（拒绝原生技能列表），首条消息时代码库自动索引 | TUI 插件（无命令 statusLine） |
| **Codex** | `hooks.json` + 技能 + MCP，包含一个 `PreToolUse` 门控 | 钩子 `systemMessage`（底部项目列表已关闭） |
| **Cursor** | `hooks.json` + 技能 + MCP | `cli-config.json` 中的 `statusLine` |
| **dsh** | Claude Code 钩子桥接 + 受管补丁块（钩子、MCP、LLM 路由、一个树外的 Web 状态栏） | Web UI 插件：会话头部中的 `tezgah-dsh-statusline` |

Codex 门控将 Bash、`exec_command`、`apply_patch`、Edit/Write、MCP 工具和子代理调用通过与其他宿主相同的检查运行。在 Claude 上，署名禁令也是机械强制执行的：`attribution` 设置被清空（`commit`、`pr`、`sessionUrl`），因此提交和 PR 的归属在源头就被关闭了。

### 状态栏

每个宿主都渲染来自 `tezgah-status` 的相同的单行检查列表，因此它们不会产生偏差。状态是关键：当规则被武装并在本次会话中生效时，标记为**绿色**；当规则被武装但按需使用（尚未使用）时，标记为**黄色**；当终止开关将其关闭时，标记为**红色**。`idx` 单独报告图谱的就绪状态（`✓` 已索引，`↻` 过期，`✗` 未索引，`–` 不适用），`plans N (M blk)` 报告开放的计划。`tezgah-status --legend` 打印图例，`--json` 为 UI 提供相同的片段，`--no-color`（或 `NO_COLOR`）强制使用纯文本。Claude Code 和 Cursor 为原生状态栏着色；opencode TUI 为其自身组件着色并在宿主事件总线上刷新；dsh Web UI 为其头部组件着色，且仅在其选项卡可见时刷新；Codex 在 `systemMessage` 中显示纯字符串。

dsh 通过其 `dsh-hooks-claude-code` 桥接运行相同的 Claude 钩子文件，因此会话启动契约、署名门控和首次 grep 提示都在那里适用。dsh 暴露了一个单一的 `subagent` 工具，因此仅限 grep 的 explorer 拒绝规则是无效的——没有 explorer 子代理可供它拒绝。dsh 默认的 `workspace-write` 沙箱将钩子子进程限制在工作区和平台临时目录中，因此 tezgah 将其钩子状态（提示标记、索引戳）写入那里的可写后备位置，而不是因拒绝写入而失败。图谱索引工作进程无法从该沙箱内部写入 `codebase-memory-mcp` 缓存，因此 `dsh` 启动器在启动 dsh 之前，会在用户不受限制的 shell 中预热索引——新代码库的索引方式与其他宿主完全相同，并带有 HEAD 戳。未使用启动器启动的会话仍然会得到清晰的报告，说明未沙箱化的 MCP 服务器提供图谱服务，并且需要对尚未索引的代码库执行 `index_repository`，而不是直接返回原始的 `EPERM`。受管补丁块还在基础组合挂载的 pi-ai 适配器上声明了两个兼容 OpenAI 的 LLM 路由：`openrouter`（`OPENROUTER_API_KEY`）和 `deepseek`（`DEEPSEEK_API_KEY`），可与原生的 `deepseek-official` 默认选项一起选择。密钥从启动环境或框架凭据存储中解析；这两个密钥都不会进入配置文件。tezgah-setup 还在 PATH（`~/.local/bin/dsh`）上放置了一个 `dsh` 启动器，它会在 `$DSH_HOME` 下找到已安装的 CLI，因此 `dsh --profile web` 可以在任何目录下工作。

dsh 没有命令状态栏，因此 tezgah 将其作为一个 Web UI 插件提供：`tezgah-dsh-statusline`。它的宿主部分通过经过身份验证的 `/api/tezgah.status` 路由（使用 `?format=json` 获取彩色视图）为会话的工作区提供 `tezgah-status` 字符串；它的浏览器部分在会话头部渲染它，按状态着色并带有悬停/点击图例，且仅在选项卡可见时刷新。`tezgah-setup` 将插件链接到 web 配置文件中，并通过 `profiles/web/cordis.patch.yml` 中的受管行启用它（仅限 web，因为宿主部分注入了仅限 web 的 `connection` 服务）；从未启动过 `web` 的配置文件会被跳过并给出提示，而不是写入一半。在 `headless` 模式下，钩子桥接将 SessionStart 契约作为其自身的尾部轮次注入（其 `agent/session-start` 在一次性任务已经是第一条消息之后，分离地调用 `agent.inject()`），因此 `dsh --profile headless "<task>"` 会额外消耗一轮，并且对于字面回答提示，会打印模型对契约的反应而不是任务的答案；交互式 web 会话不受影响。

当 `orx` 在 PATH 上时，`bin/tezgah-setup --install` 还会为 Claude、Codex、opencode 和 Cursor 触发 `orx install-skills`，以便研究规则有手册可加载。垫片文件属于 orx，因此 tezgah 仅运行该安装程序，绝不会将它们列入卸载列表。dsh 没有 orx 框架；那里的研究规则会回退到 shell 上的 `orx skill`。

Claude 插件还附带了两个只读代理。`agents/tezgah-explorer.md` 从图谱中进行代码发现并返回 `file:line` 证据；`agents/tezgah-reviewer.md` 使用 `detect_changes` 将差异转换为其影响集，然后寻找真正的缺陷。两者都禁用了写入和命令工具；它们的输出仅供参考。

### 应用分析

`analyze-app` 从其无障碍树驱动运行中的应用程序。默认循环是打开、读取树、执行操作、观察控制台/网络/日志，然后重新读取树——屏幕截图是针对树无法回答的问题（画布、游戏、动画、像素级视觉回归）的明确操作。该技能是所有宿主的统一路径；其下的服务器是 `hooks/tezgah_apps.py` 中的一个共享规范：

| 服务器 | 目标 | 接入方式 |
|---|---|---|
| `playwright` (`@playwright/mcp`) | 网页，`browser_*` 工具 | opencode, Codex, Cursor, Claude (插件 `.mcp.json`) |
| `mobile-mcp` (`@mobilenext/mobile-mcp`) | iOS 模拟器 / Android 模拟器，`mobile_*` 工具 | 同上 |
| `chrome-devtools` (选择性加入，`--devtools`) | Web 性能追踪，深度网络，源码映射控制台 | 同上 |

浏览器默认运行一个**隔离的**配置文件，因此运行绝不会触及你真实的 Chrome 状态；分析已登录的流程是一种刻意的附加操作（`--cdp-endpoint` 或 Playwright 扩展），而不是默认行为。屏幕截图、追踪和树转储会落在 `~/.cache/tezgah/apps`（可通过 `TEZGAH_ARTIFACTS` 覆盖），代理会获得返回的路径，绝不会是内联图像字节。服务器通过 `npx` 运行，因此它们需要 node 但不需要自行安装；`tezgah-setup --install --devtools` 会添加可选的 Web 诊断服务器。dsh 通过其 `dsh-mcp-client` 桥接接入相同的两个服务器（`serverName` / `command` / `args` / `env`，已根据发布的配置架构确认），而 Claude 从插件的 `.mcp.json` 中获取它们（`claude plugin details tezgah` 列出 MCP 服务器为 2 且均已连接）。`mobile-mcp` 是阻力较大的一半：macOS 可能会提示需要无障碍 / 屏幕录制权限，并且视图树在负载下可能会丢失，因此该技能会在回退到屏幕截图之前重试获取视图树。

CI 为两个服务器运行确定性的握手（无浏览器，无设备）：`TEZGAH_E2E_STRICT=1 python3 tests/e2e_analyze_wiring.py`。两个选择性加入的本地冒烟测试走得更远：`TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_web.py` 启动 Playwright MCP，导航并读取快照而不截图；`TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_mobile.py` 启动 Mobile MCP，检查视图树工具并列出设备。当缺少 node、浏览器构建或设备时，它们会打印 `SKIP: ...`。

<a id="install"></a>

## 安装

需要 Python 3.8+。dsh 宿主需要 node + npm，并且其 Web 状态栏需要 `pnpm`。可选的集成会优雅降级：PATH 上的 `codebase-memory-mcp` 为图谱提供支持；模型密钥为 `consult` 和 `codegen` 提供支持——默认为 OpenRouter（`OPENROUTER_API_KEY` 或 `~/.config/openrouter/key`），或使用 `--provider deepseek` 的 DeepSeek API（`DEEPSEEK_API_KEY` 或 `~/.config/deepseek/key`）；PATH 上的 OpenResearch 的 `orx` 为研究规则提供了驱动对象。当缺少所选提供商的密钥时，tezgah 会如实说明而不是假装正常。

克隆，然后一次性武装每个检测到的宿主：

```bash
git clone https://github.com/r1z4x/tezgah.git ~/Projects/tezgah
cd ~/Projects/tezgah
bin/tezgah-setup --install
```

`--install` 还会通过**网络**运行每个供应商自己的安装程序来安装缺失的可选工具：`orx` (`openresearch.sh/install.sh`)、`cursor-agent` (`cursor.com/install`)、`dsh`（通过 `npx` 安装其主配置文件），以及当 dsh 需要时安装 `pnpm`（通过 `npm`）——包括 `curl ... | sh`。都不需要 sudo；运行记录在 `~/.config/tezgah/install.log` 中。使用 `--dry-run` 预览，使用 `--no-deps` 跳过它（在 CI 中很有用），或使用 `--deps` 单独安装工具。工具会落在 `~/.local/bin` 或 `~/.cargo/bin` 中，因此在它们进入 PATH 之前可能需要一个新的 shell；无论如何，tezgah 自己的检查都会在这些目录中查找，因此非交互式 shell 仍会报告它们已存在。

如果已经存在前置设置，请先导入它——它会被移到一边，而不是被删除：

```bash
bin/tezgah-setup --adopt
```

Claude Code 通过其自己的插件通道安装：

```bash
claude plugin marketplace add ~/Projects/tezgah
claude plugin install tezgah@rizacan-local
```

需要时显式限制安装：

```bash
bin/tezgah-setup --install --hosts claude,codex,opencode,cursor,dsh
bin/tezgah-setup --roots ~/work:~/oss --install
```

<a id="day-to-day"></a>

## 日常使用

无需运行任何内容：规则在宿主启动时加载。有几个命令值得了解：

| 命令 | 用途 |
|---|---|
| `bin/tezgah-setup` | 报告每个宿主已武装的内容 |
| `bin/tezgah-status [PATH]` | 显示规则在该代码库中是否处于活动状态 |
| `bin/tezgah-setup --status [PATH]` | 打印已武装/已使用的检查列表 |
| `bin/tezgah-setup --deps [--dry-run]` | 安装缺失的可选工具（orx、cursor-agent、dsh） |
| `bin/tezgah-doctor [--clean] [--prune-sessions DAYS]` | 报告框架磁盘使用情况；`--clean` 删除旧的索引日志并清理 opencode 数据库；`--prune-sessions` 删除空闲会话（唯一真正缩小数据库的操作） |
| `/plan-add` | 将一项工作转化为受跟踪的计划 |
| `/plan-status` | 总结开放的计划并选择下一个 |
| `/plan-sync` | 完结已完成的计划 |
| `bin/tezgah-setup --version` | 打印插件版本 |
| `bin/tezgah-setup --uninstall` | 仅移除 tezgah 的符号链接、宿主钩子条目以及 dsh 受管块 |

<a id="configuration"></a>

## 配置

tezgah 仅在其配置的根目录下武装；在其他任何地方它都保持静默。

- 默认根目录：`~/Projects`。
- `~/.config/tezgah/config.json`：`{"roots": ["~/Projects", "~/work"]}`。
- `TEZGAH_ROOTS`（路径分隔符列表）可覆盖文件，用于一次性任务和 CI。

终止开关位于 `~/.config/tezgah/` 中。每一个都会将其规则从注入到会话的文本中移除，因此规则会真正停止：

| 开关 | 关闭功能 |
|---|---|
| `exec-mode.off` | 土耳其语，结果优先的报告 |
| `ponytail-auto.off` | 极简代码规则 |
| `spec-off` | 构建前规范规则 |
| `consult-off` | 外部第二意见规则 |
| `research-off` | 将研究任务路由到 OpenResearch |
| `orchestrate-off` | 子代理委派（添加一行不委派的指令） |
| `reminder-off` | 每轮提示文本 |
| `pretooluse-off` | PreToolUse 门控本身（署名、explorer、grep 提示） |

在每个代码库中，`.no-ponytail`、`.no-cbm` 和 `.no-lessons` 分别关闭极简代码规则、代码图谱规则（及其自动索引）以及经验教训账本。

当用户标记一个错误时，代理会在代码库的 `.tezgah/lessons.md` 中追加一行经验教训；最近的行会在会话开始时注入，因此同样的错误不会悄无声息地重复发生。

<a id="cost"></a>

## 开销

在本机（macOS，Python 3.10）上测量，而非估算：

- **上下文。** 会话启动会注入约 4.8 KB（约 1.2k tokens）的契约文本。在 Codex 上，每轮都会附带一个 480 字节的提示；Claude 和其他宿主没有每轮钩子，因此它们的每轮开销为零。完整的 `tezgah-contract` 技能（约 19.9k 字符）仅在任务加载它时才产生开销。在 opencode 上，契约作为一个约 5.5 KB 的指令文件提供。否则，opencode 会将约 53 KB 的技能名称/描述/位置文本注入到每个会话的系统提示词中；tezgah 拒绝了该列表（`permission.skill = deny`），并提供了一个生成的约 16 KB 的技能路由器，因此通过从路由器读取其 `SKILL.md` 路径来找到技能。
- **延迟。** 钩子是独立的 Python 进程，因此约 19 毫秒的解释器启动时间占主导地位。在此之上，会话启动增加约 25 毫秒，受门控的工具调用（Bash/Grep/Task）增加约 9 毫秒，而 Codex 的 Stop 片段每轮增加约 15 毫秒。
- **磁盘。** 安装耗时约 58 毫秒，tezgah 重写的每个文件都会保留一份 `<file>.tezgah-bak` 备份。

回报体现在调用者的问题上。在一个真实的代码库中，默认的 `grep` 忽略了相关文件夹且什么也没找到；在禁用忽略的情况下，它花费了 3.95 秒，并且仍然将定义与调用点混在一起。代码图谱在 16 毫秒内回答了同样的问题，仅列出了 8 个真正的调用点。

opencode 还针对长会话上下文卫生进行了武装：`tezgah-setup --install` 设置了 `compaction.prune`，因此旧的工具结果会从提示词中清除，而不是在每一步都被重新发送，并且 `watcher.ignore` 列表使文件监视器避开 `.git`、`node_modules` 和构建目录。两者都会合并——显式的用户值优先。这很重要，因为 opencode 仅在接近模型上下文限制时（对于 1M token 的模型，大约在 980k）才自动压缩，因此如果不进行修剪，工作集会增长到数十万个 token。`bin/tezgah-doctor` 报告由此产生的磁盘占用；`--prune-sessions DAYS` 通过 opencode CLI 删除空闲会话，这是唯一真正缩小数据库的操作——单靠 VACUUM 无法做到，因为它的页面都是活跃的。

<a id="development"></a>

## 开发

```bash
python3 -m unittest discover -s tests -v   # stdlib test suite
pip install -r requirements-dev.txt        # pinned ruff, the only dev dep
ruff check .                               # lint (config in pyproject.toml)
```

CI 在 Python 3.10 和 3.12 上均会运行。要从当前检出刷新已安装的 Claude 副本，请使用 `bin/tezgah-setup --sync`，并使用 `claude plugin validate .claude-plugin/plugin.json` 验证清单。在提升版本时，请同时更新 `.claude-plugin/plugin.json` 和 `.claude-plugin/marketplace.json`——它们必须保持一致。

`codebase-memory-mcp` 由用户安装。Orca 的钩子和文件不属于本项目，保持原样。Claude 从 SessionStart 钩子接收始终在线的核心；`output-styles/tezgah.md` 是为加载插件输出样式的构建准备的副本，因此钩子才是权威路径。

<a id="contributing"></a>

## 贡献

小型的、单一用途的更改最容易被接受。规则属于共享核心（`hooks/`），除非它确实是特定于宿主的；宿主差异属于 `hosts/<name>/` 下的适配器。在保证正确的前提下，尽量保持 diff 简短——本项目自身的极简代码规则同样适用于本项目。

在提交 pull request 之前，请运行与 CI 相同的三个检查：

```bash
python3 -m compileall -q hooks hosts bin statusline.py   # byte-compile every script
python3 -m unittest discover -s tests                     # stdlib test suite
ruff check .                                              # lint; config in pyproject.toml
```

`ruff` 来自 `requirements-dev.txt`（`pip install -r requirements-dev.txt`），这是唯一的开发依赖项。

<a id="security"></a>

## 安全

请通过 GitHub 的安全公告（**Security** 选项卡 → **Report a vulnerability**）私下报告漏洞，而不是提交公开的 issue。

tezgah 运行 shell 钩子，写入宿主配置，并将文本注入到每个会话中，因此任何导致钩子执行攻击者控制的代码、将密钥泄漏到配置文件中、扩大沙箱范围或让代码库内容升级为指令文本的问题都在范围内。请包含宿主、tezgah 版本（`bin/tezgah-setup --version`）以及最小复现步骤。

<a id="license"></a>

## 许可证

根目录的 `LICENSE` (MIT) 涵盖了 tezgah 自己的文件。`skills/ponytail` 和 `skills/no-ai-slop` 在其自身的 MIT 条款下被引入，记录在 `NOTICE` 中。
