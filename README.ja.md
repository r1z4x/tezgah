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

<h3 align="center">実行するすべてのAIコーディングアシスタントに、1つの共通規約を。</h3>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/github/license/r1z4x/tezgah?style=flat-square"></a>
  <a href="https://github.com/r1z4x/tezgah/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/r1z4x/tezgah/ci.yml?style=flat-square&label=ci"></a>
  <a href="https://github.com/r1z4x/tezgah/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/r1z4x/tezgah?style=flat-square"></a>
</p>

<p align="center">
  <a href="#what-it-enforces">強制されるルール</a> &bull;
  <a href="#supported-hosts">対応ホスト</a> &bull;
  <a href="#install">インストール</a> &bull;
  <a href="#day-to-day">日常的な使用</a> &bull;
  <a href="#configuration">設定</a> &bull;
  <a href="#benchmark">Benchmark</a> &bull;
  <a href="#cost">コスト</a> &bull;
  <a href="#development">開発</a> &bull;
  <a href="#contributing">コントリビューション</a> &bull;
  <a href="#security">セキュリティ</a> &bull;
  <a href="#license">ライセンス</a>
</p>

<p align="center"><sub>英語が信頼できる情報源（source of truth）です。翻訳は遅れる場合があります。</sub></p>

---

設定されたリポジトリルート内で実行するすべてのAIコーディングアシスタント（Claude Code、opencode、Codex、Cursor、およびDeepSeekのdshハーネス）に対して、1つの共通規約を適用します。

そのままでは、各アシスタントには独自の癖があります。あるものはトルコ語で答え、別のものは英語で答えます。あるものはすべてをgrepし、別のものはコードグラフをクエリします。あるものはテストを実行せずに「完了」と言います。tezgahはこのブレを排除します。どのホストを開いても、同じ言語、同じ規律、同じ証拠基準が得られます。

設計は2層構造です。ルールは共有コアに1つだけ存在し、各ホストにはそのコアをホストが理解できる形に変換する薄いアダプターが用意されます。1箇所でルールを変更すれば、5つのホストすべてに反映されます。同じテキストを5つコピーする必要はありません。

<a id="what-it-enforces"></a>

## 強制されるルール

- **結論優先のトルコ語レポート。** すべての返答はトルコ語で行われ、結果や決定（BLUF：結論から述べること）から始まり、影響度の高い順にポイントが続きます。コード、コミット、ドキュメント、およびサブエージェントのプロンプトは英語のままです。名前、CLIコマンド、エラー文字列は決して翻訳されません。
- **最小限のコード（ponytail）。** 実際に機能する最も怠惰な変更：YAGNI（You Aren't Gonna Need It）を前提とし、既存のヘルパーの再利用、標準ライブラリ、ネイティブプラットフォーム機能、インストール済みの依存関係、そして1行のコードの順に優先します。要求されていない抽象化は行いません。バリデーション、エラーハンドリング、セキュリティが簡略化されて省略されることは決してありません。
- **コードグラフ優先の探索。** 「Xはどこにあるか」「誰がYを呼び出しているか」「Zを変更すると何が壊れるか」といった問いは、grepではなく `codebase-memory-mcp` グラフ（`search_graph`、`trace_path`、`search_code`）に向けられます。リテラルテキスト、設定ファイル、非コードファイルに対しては、引き続きgrepが適しています。
- **アクセシビリティ優先のアプリ分析。** 実行中のWebまたはモバイルアプリは、ステップごとのスクリーンショットではなく、アクセシビリティ / DOM / ネイティブビューツリーを通じて読み取られます。`analyze-app` はブラウザ（Playwright MCP）、iOS SimulatorまたはAndroidエミュレータ（Mobile MCP）、およびオプションのWeb診断（Chrome DevTools MCP）をカバーします。スクリーンショットは、ツリーでは答えられないものに対する明示的でオンデマンドなアクションです。
- **外部のセカンドオピニオン。** 些細ではない、または取り返しのつかない判断を下す前に、`~/.config/tezgah/bin/consult` はOpenRouter（または `--provider deepseek` を使用したDeepSeek API）を通じて独立したモデルに並行して問い合わせを行い、エージェントはそれらが同意した点や意見が分かれた点を報告します。
- **OpenResearch経由のリサーチ。** ルーターがタスクをリサーチ（文献レビュー、仮説の構築と検証、実験の実行、リサーチ成果物）と判断した場合、プロトコルを即興で作るのではなく、alphaXivのOpenResearch（`orx`）を通じて作業を進め、最初に `orx` のマニュアルを読み込みます。純粋なコード探索はコードグラフ上にとどまります。`orx` が存在しない場合、ルーターはその旨を伝え、ホストのサブエージェントにフォールバックします。
- **検証に基づく誠実さ。** 出力が確認されない限り、完了した、テストした、修正したと報告されることはありません。失敗したテストは正確なエラーとともに失敗として報告され、スキップされたチェックは明確に述べられます。
- **AIのクレジット表記の完全排除。** 永続化または公開されるもの（コミット、マージ、タグのメッセージ、PRやIssueのテキスト、コードコメント、ファイルヘッダー、ドキュメント）において、アシスタント、モデル、ベンダー、または「AI」のクレジットを表記してはなりません。ツールを使用するのは問題ありませんが、自分の成果物にその名前を署名することは許可されません。
- **2層のオーケストレーション。** メインスレッドが決定と検証を行います。安価なモデル（`~/.config/tezgah/bin/codegen`、デフォルトはOpenRouter、または `--provider deepseek`）が、スクラッチディレクトリに対して境界が明確で仕様の定まった編集のドラフトを作成します。ルーターを経由しない限りリポジトリには何も到達せず、失敗したドラフトは自動的にメインモデルにフォールバックします。
- **リポジトリごとのサブエージェント。** セッション開始時に、対象リポジトリには機能制限された少数のエージェント（`tezgah-explorer`、`tezgah-reviewer`、`tezgah-researcher`、`tezgah-verifier`）と `tezgah-orchestrator` が提供され、インストールされている各ホストのネイティブな領域（Claude/Cursorの `.claude/agents/`、opencodeの `.opencode/agents/` とライブ設定の注入、Codexの `.codex/agents/`）にレンダリングされ、管理された1つの `.gitignore` ブロックで無視されます。Claudeでは、オーケストレーターの `Agent(tezgah-*)` 許可リストは、メインスレッドとして実行された場合（`claude --agent tezgah-orchestrator`）にのみ有効になります。サブエージェントとして実行された場合、このリストは無視されます。dshには役割ごとの領域がないため、規約のルータールールがこれをカバーします。

<a id="supported-hosts"></a>

## 対応ホスト

| ホスト | 接続方法 |
|---|---|
| **omp** (oh-my-pi) — プライマリ | `~/.omp/agent`：管理された `RULES.md` の常時オンブロック、スキル、生成されたサブエージェント、`mcp.json`、およびプロンプトごとのルールを武装させ、ツールをゲートし、証拠を記録し、Stop ルールを実行する拡張機能（`hooks/pre/tezgah-hook.ts`）。この配線は `tezgah-setup` によって検査されます |
| **Claude Code** | ローカルプラグインマーケットプレイス: フック、コマンド、2つの読み取り専用エージェント、出力スタイル |
| **opencode** | プラグイン + instructions + MCP + 生成されたスキルルーター（ネイティブのスキルリストは拒否）、最初のメッセージでのリポジトリ自動インデックス |
| **Codex** | `hooks.json` + スキル + MCP（`PreToolUse` ゲートを含む） |
| **Cursor** | `hooks.json` + スキル + MCP |
| **dsh** | Claude Codeフックブリッジ + 管理されたパッチブロック（フック、MCP、LLMルート、ツリー外のWebステータスライン） |

Codexのゲートは、Bash、`exec_command`、`apply_patch`、Edit/Write、MCPツール、およびサブエージェントの呼び出しを、他のホストと同じチェックを通して実行します。Claudeでは、クレジット表記の禁止も機械的に強制されます。`attribution` 設定が空にされる（`commit`、`pr`、`sessionUrl`）ため、コミットやPRのクレジットはソースレベルでオフになります。

### アプリ分析

`analyze-app` は、実行中のアプリケーションをそのアクセシビリティツリーから操作します。デフォルトのループは、開く、ツリーを読み取る、アクションを実行する、コンソール/ネットワーク/ログを観察する、そしてツリーを再読み込みする、というものです。スクリーンショットは、ツリーでは答えられないもの（キャンバス、ゲーム、アニメーション、ピクセルレベルの視覚的リグレッション）に対する明示的なアクションです。このスキルはすべてのホストで共通のパスであり、その下にあるサーバーは `hooks/tezgah_apps.py` 内の1つの共有仕様です：

| サーバー | ターゲット | 接続方法 |
|---|---|---|
| `playwright` (`@playwright/mcp`) | Webページ、`browser_*` ツール | opencode、Codex、Cursor、Claude（プラグイン `.mcp.json`） |
| `mobile-mcp` (`@mobilenext/mobile-mcp`) | iOS Simulator / Androidエミュレータ、`mobile_*` ツール | 同上 |
| `chrome-devtools` (オプトイン、`--devtools`) | Webパフォーマンストレース、ディープネットワーク、ソースマップされたコンソール | 同上 |

ブラウザはデフォルトで**分離された**プロファイルを実行するため、実行によって実際のChromeの状態が影響を受けることはありません。ログイン済みのフローを分析する場合は、デフォルトではなく意図的なアタッチ（`--cdp-endpoint` またはPlaywright拡張機能）となります。スクリーンショット、トレース、およびツリーダンプは `~/.cache/tezgah/apps` に保存され（`TEZGAH_ARTIFACTS` で上書き可能）、エージェントにはインラインの画像バイトではなくパスが返されます。サーバーは `npx` を通じて実行されるため、nodeは必要ですが独自のインストールは不要です。`tezgah-setup --install --devtools` はオプションのWeb診断サーバーを追加します。dshは `dsh-mcp-client` ブリッジ（公開されている設定スキーマに対して確認された `serverName` / `command` / `args` / `env`）を通じて同じ2つのサーバーを接続し、Claudeはプラグインの `.mcp.json` からそれらを取得します（`claude plugin details tezgah` はMCPサーバーを2つリストし、両方とも接続します）。`mobile-mcp` は摩擦が大きい方です。macOSはアクセシビリティ / 画面収録の許可を求める場合があり、負荷がかかるとビューツリーが欠落する可能性があるため、スキルはスクリーンショットにフォールバックする前にツリーを再試行します。

CIは両方のサーバーに対して決定論的なハンドシェイクを実行します（ブラウザなし、デバイスなし）：`TEZGAH_E2E_STRICT=1 python3 tests/e2e_analyze_wiring.py`。2つのオプトインのローカルスモークテストはさらに踏み込みます。`TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_web.py` はPlaywright MCPを起動し、ナビゲートしてスクリーンショットなしでスナップショットを読み取ります。`TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_mobile.py` はMobile MCPを起動し、ビューツリーツールをチェックしてデバイスをリストします。node、ブラウザビルド、またはデバイスが見つからない場合は `SKIP: ...` と出力します。

<a id="install"></a>

## インストール

Python 3.8以上が必要です。dshホスト、および `pnpm` を使用したそのWebステータスラインには、node + npmが必要です。オプションの統合はグレースフルに縮退します。PATH上の `codebase-memory-mcp` はグラフを駆動し、モデルキーは `consult` と `codegen` を駆動します（デフォルトはOpenRouter（`OPENROUTER_API_KEY` または `~/.config/openrouter/key`）、または `--provider deepseek` を使用したDeepSeek API（`DEEPSEEK_API_KEY` または `~/.config/deepseek/key`））。また、PATH上のOpenResearchの `orx` はリサーチルールに駆動対象を提供します。選択したプロバイダーのキーが欠落している場合、tezgahはごまかすことなくその旨を伝えます。

クローンを作成し、検出されたすべてのホストを1回のパスで有効化します：

```bash
git clone https://github.com/r1z4x/tezgah.git ~/Projects/tezgah
cd ~/Projects/tezgah
bin/tezgah-setup --install
```

ターミナルでは、引数なしのそのコマンドは代わりにインストールウィザードになります。どのホストを武装させるか、ルートディレクトリ、不足しているオプションツールをインストールするか、オプションの
DevTools MCP を接続するかを尋ね、計画を表示し、はいと言った後にだけ書き込みます。フラグはウィザードのデフォルトであるため、`--wizard --hosts omp`
は残りだけを尋ねます。パイプ、エージェント、または CI での実行は決してプロンプトを出されません — 以前とまったく同じようにレポートを表示します。

`--install`
は、各ベンダー独自のインストーラーを**ネットワーク経由で**実行することにより、不足しているオプションツールもインストールします。`orx`（`openresearch.sh/install.sh`）、`cursor-agent`（`cursor.com/install`）、`dsh`（`npx`
経由のホームプロファイル）、およびdshが必要とする場合の `pnpm`（`npm` 経由）が含まれ、`curl ... | sh`
も含まれます。sudoはどれも必要ありません。実行は `~/.config/tezgah/install.log` に記録されます。`--dry-run`
でプレビューしたり、`--no-deps` でスキップしたり（CIで便利です）、`--deps` でツールのみをインストールしたりできます。ツールは `~/.local/bin`
または `~/.cargo/bin`
に配置されるため、PATHに通すために新しいシェルが必要になる場合があります。tezgah独自のチェックはそれに関係なくこれらのディレクトリを検索するため、非対話型シェルでもそれらが存在すると報告されます。

以前のセットアップがすでに存在する場合は、まずそれをインポートします。削除されるのではなく、別の場所に移動されます：

```bash
bin/tezgah-setup --adopt
```

Claude Codeは独自のプラグインチャネルを通じてインストールされます：

```bash
claude plugin marketplace add ~/Projects/tezgah
claude plugin install tezgah@rizacan-local
```

必要に応じてインストールを明示的に制限します：

```bash
bin/tezgah-setup --install --hosts omp
bin/tezgah-setup --install --hosts claude,codex,cursor,opencode,dsh
bin/tezgah-setup --roots ~/work:~/oss --install
```

<a id="day-to-day"></a>

## 日常的な使用

実行するものはありません。ルールはホストの起動時に読み込まれます。知っておくべきコマンドがいくつかあります：

| コマンド | 目的 |
|---|---|
| `bin/tezgah-setup` | ターミナルではインストールウィザード、パイプや CI ではホストごとに有効化されているものを報告する |
| `bin/tezgah-setup --wizard` | どこでもインストールウィザードを強制する。`--report` はレポートを強制する |
| `bin/tezgah-status [PATH]` | そのリポジトリでルールがアクティブかどうかを表示する |
| `bin/tezgah-setup --status [PATH]` | 有効化/使用済みのチェックリストを出力する |
| `bin/tezgah-setup --deps [--dry-run]` | 不足しているオプションツール（orx、cursor-agent、dsh）をインストールする |
| `bin/tezgah-research init\|check\|status` | 研究ラインを作成・検査する: 状態、findings、クレーム、プロトコル先行のルール |
| `bin/tezgah-doctor [--clean] [--prune-sessions DAYS]` | ハーネスのディスク使用量を報告する。`--clean` は古いインデックスログを削除し、opencodeのDBをバキュームする。`--prune-sessions` はアイドル状態のセッションを削除する（実際にDBを縮小する唯一のアクション） |
| `/tezgah:plan-add` | 作業の一部を追跡対象のプランに変換する |
| `/tezgah:plan-status` | オープンなプランを要約し、次のプランを選択する |
| `/tezgah:plan-sync` | 完了したプランをクローズする |
| `bin/tezgah-setup --version` | プラグインのバージョンを出力する |
| `bin/tezgah-setup --uninstall` | tezgahのシンボリックリンク、ホストフックエントリ、およびdshの管理されたブロックのみを削除する |

<a id="configuration"></a>

## 設定

tezgahは設定されたルートの下でのみ有効化されます。それ以外の場所では沈黙します。

- デフォルトルート: `~/Projects`。
- `~/.config/tezgah/config.json`: `{"roots": ["~/Projects", "~/work"]}`。
- `TEZGAH_ROOTS`（パス区切りリスト）は、単発の実行やCI用にファイルを上書きします。

キルスイッチは `~/.config/tezgah/` に配置されます。それぞれがセッションに注入されるテキストからそのルールを削除するため、ルールは実際に停止します：

| スイッチ | オフにする機能 |
|---|---|
| `exec-mode.off` | トルコ語、結論優先のレポート |
| `ponytail-auto.off` | 最小限のコードルール |
| `spec-off` | 構築前の仕様確認ルール |
| `consult-off` | 外部のセカンドオピニオンルール |
| `research-off` | リサーチタスクのOpenResearchへのルーティング |
| `orchestrate-off` | サブエージェントへの委譲（委譲しない旨の行を追加） |
| `reminder-off` | ターンごとのリマインダーテキスト |
| `pretooluse-off` | PreToolUseゲート自体（クレジット表記、エクスプローラー、grepナッジ） |

リポジトリごとに、`.no-ponytail`、`.no-cbm`、および `.no-lessons` は、それぞれ最小限のコードルール、コードグラフルール（およびその自動インデックス）、およびレッスンの台帳をオフにします。

ユーザーが間違いを指摘すると、エージェントはリポジトリの `.tezgah/lessons.md` に1行の教訓（レッスン）を追記します。最新の行はセッション開始時に注入されるため、同じ間違いが暗黙のうちに繰り返されることはありません。

<a id="benchmark"></a>

## Benchmark

この契約は仕事を改善するのか、それとも改善するように見えるだけなのか？ それは `benchmarks/arm-bench/`
で測定されるのであって、主張されるものではありません。エージェントが そのテストを決して見ない隠しチェック、ホスト自身の利用記録からのコスト、そして副次的な
編集を失敗として採点します。`PREREGISTRATION.md` が実行前にエンドポイントを固定し、 `python3 bench.py report` がそれを出力します。実行
id を含む完全な研究は `docs/research/2026-09-16-tezgah-quality.md` にあります。以下のすべての数値は実 行ログです。

| ブロック | 実行数 | 確定したこと |
|---|---|---|
| 2 ホスト、28 タスク、k=3 | 336 | `omp+tezgah` 0.95 と `opencode+tezgah` 0.96 は区間が重なり、解決済みタスクあたりのコストも同じ；ベアアームでは omp の方が安く（CPS で $0.0047 対 $0.0074）、したがって日常のドライバーは品質にコストをかけずに omp となる |
| ハード系、5 タスク、k=5、2 つのモデル系 | 200 | プールすると 4 つのアームのうち 3 つが 40/50 に着地：そのサイズではハーネス効果はなく、最初のモデルが生んだ唯一のシグナルは 2 つ目で反転した |
| ゲート系、ゲート武装 | 36 | どのアームも近道の経路を取らなかった；ゲートの仕組みは直接検証されており（skip 編集は拒否される）、仕事への効果はまだ測定されていない |
| 条項アブレーション、分離する 2 つのルール、k=8 | 160 | 契約アームは 23/32（0.72）を通過し、ベアアンカーの 12/32（0.38）を上回る |

**それはモデルのデフォルトが間違っているまさにそこで効く。** `c04`（契約だけが 応答をトルコ語にする英語プロンプト）は契約ありで 9/16、なしで 0/16
を読む；`h02` （可視スイートがどちらでも緑になる金銭契約）は 14/16 対 12/16 を読む。埋めるべき ギャップがない場合 - 25 のパイロットタスクのうち 22
はすべてのアームで毎回通過 した - ベンチマークはヌルを報告することしかできません。

**それを担うのは 2 つの条項。** 条項 1 を除くと `c04` は 0/8、ベアアンカー自身の スコアになり、`h02` はほとんど動きません。条項 3 を除くと `h02`
は 2/8 - ベアアン カーの 6/8 を下回る - になります。なぜなら条項 3 は、最短の「できたように見える」
経路で止まることを禁じており、そのタスクでは最短経路が、可視スイートは通すが文 書化されたルールを破るワンライナーだからです。条項 2 と 4 は測定可能なものを何 も動かしません。

**コストは品質に従う。** 解決済みタスクあたり：フル契約ノードで $0.0078 対 $0.0097、ponytail 抜きノードで $0.0043 対
$0.0087。契約アームはより多くのタスクを 解決するので、解決済みタスクあたりのコストは下がります。総支出は増え、ベンチマ ークはそれを相殺せず行ごとに記録します。

これが示さないもの：コード品質、レビュー労力、保守性（ここではいずれも測定されて いません）；アームの選択に対するゲートの効果（36 回の武装実行でどのアームも近道
に手を伸ばさなかったため）；条項の*順序*（`k=8` は方向を固定するもので、セルあた り 8 回の実行です）。全体を通じて 1 つのプロバイダーと 1 つのフィクスチャパッケ
ージ、そしてアブレーションのラウンドは単一のモデル系で実行されます。2 つ目のモ デル系は 28 タスクのヌルを正確に再現し（51/56 対 51/56）、これが最初の読みがモデ
ルのアーティファクトではなかったことを示しています。

<a id="cost"></a>

## コスト

このマシン（macOS、Python 3.10）で測定されたもので、推定ではありません。 `tezgah-setup` はライブの予算を出力します -
ここにコピーされた数値を信じるのでは なくそこで読んでください。以前のリビジョンが、実際にインストールするものより小さ いコア帯を引用するに至ったのはそのためです。

| 帯 | かかるコスト |
|---|---|
| セッション開始 | 常時オンの契約（不変条件に加え、オンデマンドの各ルールごとに 1 行のポインタ）：このマシンとスキルセットでは、契約テキストが約 1.3k トークン、スキルメタデータが約 1.3k トークンで、条件付きルール（spec、consult、research、graph）はプロンプトが一致するターンにのみ約 0.6k を追加します |
| ターンごと | 短いリマインダー（約 0.2k トークン）に加え、一致する場合の武装されたルール；フックは別個の Python プロセスなので、約 19 ms のインタープリター起動が土台です - ターンごとに約 31 ms、セッション開始で約 50-81 ms、ゲートされたツール呼び出し（Bash/Grep/Task）で約 24-25 ms が加わります。opencode にはプロンプト時のフックがないため、ゼロです |
| オンデマンド | 完全な `tezgah-contract` スキル（約 6.0k トークン）。タスクがそれをロードしたときにのみコストが発生します |
| MCP スキーマ | 最大の帯であり、静的なレポートには見えないものです：グラフサーバーだけで 15 ツール / 24,508 バイト（約 6.1k トークン）を宣言し、ホストがオンデマンドでスキーマを取得しない限りすべてのリクエストに同乗します。`tezgah-setup --mcp-schemas` がそれを測定します |
| ディスク | インストールには約 58 ms かかり、tezgah が書き換えるすべてのファイルは `<file>.tezgah-bak` として 1 回保持されます |

**武装の下限。** 不変条件は常時オンです - 実行モード、ponytail、 deliver-the-whole-ask、誠実性、ループ規律、教訓台帳、帰属の禁止 -
そして安全ルー ル（「不可逆的または外向きの行為には先に明示的な依頼が必要」）もその一つなので、 分類器に依存することは決してありません。各勧告ルールは実行可能な 1 行のポインタ
を常時オンに保つため、一致を逃しても失うのは詳細だけでルールではありません。ま た失敗したホストフックは、契約なしにではなく、ポインタとオンデマンドのスキルに
フォールバックします。偽陰性は監査可能です：すべてのプロンプトが `armed=<rules|none> chars=<n>` - プロンプトテキストは含まない - を
`~/.cache/tezgah/classify.log` に追記し（64 KB を超えると最後の 200 行に切り詰 め）、5
つすべてのフックホストが同じプロンプトに対して同じセットを武装させます （`tests/test_context.py::ArmingConformance`）。

**opencode は別の方法で武装されます。** プロンプト時の注入ポイントがないため、 契約は生成された instructions
ファイルとして提供され、その常時オンルーターはコ ーディングセッションが手を伸ばすバケットだけを列挙し、残りはオンデマンドで読ま れる
`~/.config/tezgah/opencode-skills.full.md` へのポインタに集約されます； `permission.skill = deny` は
opencode が代わりに全スキルのメタデータを注入するの を止めます。`--install` は `compaction.prune` と `watcher.ignore`
も設定し、古い ツール結果を毎ステップ再送信するのではなくプロンプトから消去します - これがなけ れば、opencode がモデルの限界近く（1M トークンモデルで約
980k）で自動コンパクト する前に、ワーキングセットが数十万トークンに膨れ上がります。`bin/tezgah-doctor`
はディスクフットプリントを報告し、`--prune-sessions DAYS` は opencode CLI を通じ てアイドル状態のセッションを削除します。VACUUM
だけではできない、データベースを 実際に縮小する唯一のアクションです。

**なぜ元が取れるのか。** ある実際のリポジトリで、デフォルトの `grep` は関連する フォルダーを無視して何も見つけられませんでした。無視を無効にすると 3.95 秒かか
り、それでも定義と呼び出し場所が混在していましたが、コードグラフは同じ質問に 16 ms で答え、8 つの真の呼び出し場所を挙げました。

<a id="development"></a>

## 開発

```bash
python3 -m unittest discover -s tests -v   # stdlib test suite
pip install -r requirements-dev.txt        # pinned ruff, the only dev dep
ruff check .                               # lint (config in pyproject.toml)
```

CIはPython 3.10と3.12の両方で実行されます。このチェックアウトからインストール済みのClaudeのコピーを更新するには、`bin/tezgah-setup --sync` を使用し、`claude plugin validate .claude-plugin/plugin.json` でマニフェストを検証します。バージョンを上げる際は、`.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` を一緒に更新してください。これらは一致している必要があります。

`codebase-memory-mcp` はユーザーによってインストールされます。Orcaのフックとファイルはこのプロジェクトの一部ではなく、手付かずのまま残されます。ClaudeはSessionStartフックから常時稼働のコアを受け取ります。`output-styles/tezgah.md` はプラグインの出力スタイルを読み込むビルド用の複製であるため、フックが信頼できるパスとなります。

<a id="contributing"></a>

## コントリビューション

小さく、単一目的の変更が最も受け入れられやすいです。ルールは、純粋にホスト固有のものでない限り、共有コア（`hooks/`）に属します。ホストの違いは `hosts/<name>/` の下のアダプターに属します。正確さを保ちつつ、diffは可能な限り短くしてください。プロジェクト独自の最小限のコードルールは、このプロジェクト自体にも適用されます。

プルリクエストを開く前に、CIが実行するのと同じ3つのチェックを実行してください：

```bash
python3 -m compileall -q hooks hosts bin statusline.py   # byte-compile every script
python3 -m unittest discover -s tests                     # stdlib test suite
ruff check .                                              # lint; config in pyproject.toml
```

`ruff` は `requirements-dev.txt`（`pip install -r requirements-dev.txt`）から提供されます。これが唯一の開発依存関係です。

<a id="security"></a>

## セキュリティ

脆弱性は、公開のIssueではなく、GitHubのセキュリティアドバイザリ（**Security** タブ → **Report a vulnerability**）を通じて非公開で報告してください。

tezgahはシェルフックを実行し、ホスト設定を書き込み、すべてのセッションにテキストを注入します。そのため、フックに攻撃者が制御するコードを実行させるもの、設定ファイルにキーを漏洩させるもの、サンドボックスを広げるもの、またはリポジトリのコンテンツを指示テキストにエスカレーションさせるものはすべて対象となります。ホスト、tezgahのバージョン（`bin/tezgah-setup --version`）、および最小限の再現手順を含めてください。

<a id="license"></a>

## ライセンス

ルートの `LICENSE`（MIT）はtezgah自身のファイルをカバーします。`skills/ponytail` と `skills/no-ai-slop` は独自のMIT条件の下でベンダー化されており、`NOTICE` に記録されています。
