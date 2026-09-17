<p align="center">
  <a href="README.md">English</a> |
  <a href="README.zh.md">简体中文</a> |
  <a href="README.de.md">Deutsch</a> |
  <a href="README.es.md">Español</a> |
  <a href="README.fr.md">Français</a> |
  <a href="README.ja.md">日本語</a> |
  <a href="README.br.md">Português (Brasil)</a> |
  <a href="README.tr.md">Türkçe</a>
</p>

# Tezgah

<p align="center">
  <img src="assets/logo/tezgah-logo.svg" alt="tezgah logo" width="220">
</p>

<h3 align="center">为你运行的每一个 AI 编程助手提供统一的工作契约。</h3>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/github/license/r1z4x/tezgah?style=flat-square"></a>
  <a href="https://github.com/r1z4x/tezgah/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/r1z4x/tezgah/ci.yml?style=flat-square&label=ci"></a>
  <a href="https://github.com/r1z4x/tezgah/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/r1z4x/tezgah?style=flat-square"></a>
</p>

<p align="center">
  <a href="#what-it-enforces">强制执行的规则</a> &bull;
  <a href="#supported-hosts">支持的宿主</a> &bull;
  <a href="#install">安装</a> &bull;
  <a href="#day-to-day">日常使用</a> &bull;
  <a href="#configuration">配置</a> &bull;
  <a href="#benchmark">Benchmark</a> &bull;
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
  实验所需的领域知识也一并提供：仓库内置的 `AI-research-SKILLs` 库（98 个技能、23 个分类、MIT）作为 `ai-research`
  技能随附，按阶段索引逐条读取。
- **验证下的诚实。** 除非看到了输出结果，否则绝不报告已完成、已测试或已修复。失败的测试会如实报告为失败并附上确切的错误信息，跳过的检查也会被清楚地说明。
- **任何地方都没有 AI 署名。** 任何持久化或发布的内容——提交、合并和标签信息、PR 和 issue 文本、代码注释、文件头、文档——都不得归功于助手、模型、供应商或“AI”。使用工具没问题；把它的名字签在你的工作成果上则不行。
- **双层编排。** 主线程负责决策和验证；一个廉价模型（`~/.config/tezgah/bin/codegen`，默认为 OpenRouter 或 `--provider deepseek`）向临时目录起草有边界的、规范明确的编辑。除了通过路由器，任何内容都无法进入代码库，失败的草稿会自动回退到主模型。
- **每个代码库的子代理。** 在会话开始时，所在的代码库会获得一小组受能力限制的代理（`tezgah-explorer`、`tezgah-reviewer`、`tezgah-researcher`、`tezgah-verifier`）加上一个 `tezgah-orchestrator`，它们被渲染到每个已安装宿主的原生界面中（Claude/Cursor 的 `.claude/agents/`，opencode 的 `.opencode/agents/` 加上实时配置注入，Codex 的 `.codex/agents/`），并通过一个受管的 `.gitignore` 块被忽略。在 Claude 上，orchestrator 的 `Agent(tezgah-*)` 允许列表仅在它作为主线程运行（`claude --agent tezgah-orchestrator`）时生效；作为子代理时，该列表会被忽略。dsh 没有按角色的界面，因此契约的路由器规则涵盖了它。

<a id="supported-hosts"></a>

## 支持的宿主

| 宿主 | 接入方式 |
|---|---|
| **omp** (oh-my-pi) — 主要 | `~/.omp/agent`：受管的 `RULES.md` 常开区块、技能、生成的子代理、`mcp.json`，以及一个扩展（`hooks/pre/tezgah-hook.ts`），它武装每个提示词的规则、对工具进行门控、记录证据并运行 Stop 规则；该接线由 `tezgah-setup` 检查 |
| **Claude Code** | 本地插件市场：钩子、命令、两个只读代理、输出样式 |
| **opencode** | 插件 + 指令 + MCP + 生成的技能路由器（拒绝原生技能列表），首条消息时代码库自动索引 |
| **Codex** | `hooks.json` + 技能 + MCP，包含一个 `PreToolUse` 门控 |
| **Cursor** | `hooks.json` + 技能 + MCP |
| **dsh** | Claude Code 钩子桥接 + 受管补丁块（钩子、MCP、LLM 路由、一个树外的 Web 状态栏） |

Codex 门控将 Bash、`exec_command`、`apply_patch`、Edit/Write、MCP 工具和子代理调用通过与其他宿主相同的检查运行。在 Claude 上，署名禁令也是机械强制执行的：`attribution` 设置被清空（`commit`、`pr`、`sessionUrl`），因此提交和 PR 的归属在源头就被关闭了。

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

在终端中，不带参数运行该命令就是向导：它会询问要武装哪些宿主、根目录、是否安装缺失的可选工具，以及是否接入可选的 DevTools
MCP，打印计划，并且只有在得到肯定答复后才写入。这些标志就是向导的默认值，因此 `--wizard --hosts omp` 只询问其余部分。管道、代理或 CI
运行永远不会被提示——它会打印报告，与之前完全一样。

`--install` 还会通过**网络**运行每个供应商自己的安装程序来安装缺失的可选工具：`orx`
(`openresearch.sh/install.sh`)、`cursor-agent` (`cursor.com/install`)、`dsh`（通过 `npx`
安装其主配置文件），以及当 dsh 需要时安装 `pnpm`（通过 `npm`）——包括 `curl ... | sh`。都不需要 sudo；运行记录在
`~/.config/tezgah/install.log` 中。使用 `--dry-run` 预览，使用 `--no-deps` 跳过它（在 CI 中很有用），或使用
`--deps` 单独安装工具。工具会落在 `~/.local/bin` 或 `~/.cargo/bin` 中，因此在它们进入 PATH 之前可能需要一个新的
shell；无论如何，tezgah 自己的检查都会在这些目录中查找，因此非交互式 shell 仍会报告它们已存在。

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
bin/tezgah-setup --install --hosts omp
bin/tezgah-setup --install --hosts claude,codex,cursor,opencode,dsh
bin/tezgah-setup --roots ~/work:~/oss --install
```

<a id="day-to-day"></a>

## 日常使用

无需运行任何内容：规则在宿主启动时加载。有几个命令值得了解：

| 命令 | 用途 |
|---|---|
| `bin/tezgah-setup` | 在终端中：安装向导；在管道或 CI 中：报告每个宿主已武装的内容 |
| `bin/tezgah-setup --wizard` | 在任何位置强制使用安装向导；`--report` 强制输出报告 |
| `bin/tezgah-status [PATH]` | 显示规则在该代码库中是否处于活动状态 |
| `bin/tezgah-setup --status [PATH]` | 打印已武装/已使用的检查列表 |
| `bin/tezgah-setup --deps [--dry-run]` | 安装缺失的可选工具（orx、cursor-agent、dsh） |
| `bin/tezgah-research init\|check\|status` | 创建并检查研究线：状态、findings、声明以及协议先于结果的规则 |
| `bin/tezgah-doctor [--clean] [--prune-sessions DAYS]` | 报告框架磁盘使用情况；`--clean` 删除旧的索引日志并清理 opencode 数据库；`--prune-sessions` 删除空闲会话（唯一真正缩小数据库的操作） |
| `/tezgah:plan-add` | 将一项工作转化为受跟踪的计划 |
| `/tezgah:plan-status` | 总结开放的计划并选择下一个 |
| `/tezgah:plan-sync` | 完结已完成的计划 |
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

<a id="benchmark"></a>

## Benchmark

这份契约真的改善了工作，还是只是看起来应该改善？这要在 `benchmarks/arm-bench/`
中测量，而不是断言：代理从不知道其存在的隐藏检查、来自宿主自身使用记录的成本，以及被计为失败的附带编辑。`PREREGISTRATION.md` 在运行前固定端点，`python3
bench.py report` 打印它们；完整研究（含运行 id）见
`docs/research/2026-09-16-tezgah-quality.md`。下面的每个数字都是运行日志。

| 区块 | 运行 | 它确定了什么 |
|---|---|---|
| 双宿主，28 个任务，k=3 | 336 | `omp+tezgah` 0.95 与 `opencode+tezgah` 0.96 的区间重叠，且每个已解决任务的成本相同；在裸臂上 omp 更便宜（$0.0047 对 $0.0074 CPS），因此日常驱动是 omp，且不以质量为代价 |
| 难组，5 个任务，k=5，两个模型族 | 200 | 合并后，四个臂中有三个落在 40/50：在该规模下没有 harness 效应，而第一个模型产生的唯一信号在第二个模型上反转了 |
| 门控组，门控已武装 | 36 | 没有任何臂走捷径路线；门控机制被直接验证（跳过编辑被拒绝），它对工作的影响尚未测量 |
| 条款消融，区分两者的两条规则，k=8 | 160 | 契约臂通过 23/32（0.72），裸锚点为 12/32（0.38） |

**它恰好在模型默认错误的地方起作用。** `c04`（一个只有契约才使回复为中文的英文提示词）在有契约时读出 9/16，无契约时
0/16；`h02`（一个可见测试套件两种情况都为绿的金钱契约）读出 14/16 对 12/16。在没有差距要弥补的地方——25 个试点任务中有 22
个在每个臂的每次重复下都通过——基准只能报告一个 null。

**两条条款支撑它。** 移除条款 1 使 `c04` 降到 0/8，即裸锚点自己的分数，而几乎不动 `h02`。移除条款 3 使 `h02` 降到 2/8——低于裸锚点的
6/8——因为条款 3 禁止停在看起来最短的已完成路径上，而在那个任务上，最短路径就是一行代码，它通过了可见套件却违反成文规则。条款 2 和 4 没有移动任何可测量的东西。

**成本跟随质量。** 每个已解决任务：在完整契约节点上 $0.0078 对 $0.0097，在减去 ponytail 的节点上 $0.0043 对
$0.0087。契约臂解决了更多任务，因此每个已解决任务成本更低；总支出更高，基准按行记录它而不是把它净掉。

这里没有展示的：代码质量、审查工作量或可维护性，这些都没有在此测量；门控对臂选择的影响，因为在 36 次已武装运行中没有任何臂去够捷径；或条款的顺序——`k=8` 在每个单元 8
次运行下固定一个方向。全程一个提供商和一个夹具包，消融轮次在单一模型族上运行。第二个模型族精确复现了 28 任务的 null（51/56 对
51/56），这正是表明第一次读数不是模型假象的证据。

<a id="cost"></a>

## 开销

在本机（macOS，Python 3.10）上测量，而非估算。`tezgah-setup`
打印实时预算——请在那里读取，而不要相信复制到这里的数字；早先的一个修订版正是这样引用了比它所安装的更小的核心区间。

| 区间 | 它的成本 |
|---|---|
| 会话启动 | 常开的契约（不变量加上每条按需规则的一行指针）：在本机和这套技能下，约 1.5k tokens 的契约文本和约 1.4k 的技能元数据，条件规则（spec、consult、research、graph）只在提示词匹配的那一轮增加约 0.7k |
| 每轮 | 一条简短提醒（约 0.2k tokens）加上匹配时武装的规则；钩子是独立的 Python 进程，因此约 19 毫秒的解释器启动是基础——每轮增加约 31 毫秒，会话启动增加约 50-81 毫秒，一次受门控的工具调用（Bash/Grep/Task）约 24-25 毫秒。opencode 没有提示词时钩子，因此付出零成本 |
| 按需 | 完整的 `tezgah-contract` 技能（约 6.6k tokens），只在任务加载它时才付出 |
| MCP schema | 最大的区间，也是没有任何静态报告能看到的区间：仅图谱服务器就声明 15 个工具 / 24,508 字节（约 6.1k tokens），除非宿主按需获取 schema，否则它搭乘每个请求。`tezgah-setup --mcp-schemas` 测量它 |
| 磁盘 | 安装耗时约 58 毫秒，tezgah 重写的每个文件都会保留一份 `<file>.tezgah-bak` |

**武装底线。**
不变量是常开的——执行模式、ponytail、交付完整请求、完整性、循环纪律、教训账本和署名禁令——而安全规则（"不可逆或外向的动作需要先明确提出"）就是其中之一，因此它从不依赖分类器。每条建议性规则都保留一个可操作的常开一行指针，因此一次漏配只损失细节，绝不损失规则本身，而失败的宿主钩子会回退到指针加上按需技能，而不是回退到没有契约。假阴性可审计：每个提示词都向
`~/.cache/tezgah/classify.log` 追加 `armed=<rules|none> chars=<n>`——没有提示词文本——（超过 64 KB 后截断为最后
200 行），并且所有五个有钩子的宿主对同一个提示词武装同一套规则（`tests/test_context.py::ArmingConformance`）。

**opencode 的武装方式不同。** 它没有提示词时的注入点，因此契约作为生成的指令文件提供，其常开路由器只列出编码会话会用到的那几个桶，将其余的折叠为按需读取的
`~/.config/tezgah/opencode-skills.full.md` 指针；`permission.skill = deny` 阻止 opencode
注入每个技能的元数据。`--install` 还设置 `compaction.prune` 和
`watcher.ignore`，从提示词中清除旧的工具结果而不是在每一步重新发送它们——没有这一点，工作集会增长到数十万个 token，然后 opencode
才会在接近模型限制（1M-token 模型约 980k）时自动压缩。`bin/tezgah-doctor` 报告磁盘占用，而 `--prune-sessions DAYS` 通过
opencode CLI 删除空闲会话，这是唯一真正缩小数据库的操作，因为单靠 VACUUM 做不到。

**为什么值得。** 在一个真实代码库中，默认的 `grep` 忽略了相关文件夹且什么也没找到；禁用忽略后它花了 3.95 秒，并且仍然把定义与调用点混在一起，而代码图谱在 16
毫秒内用 8 个真正的调用点回答了同一个问题。

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
