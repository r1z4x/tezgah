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

| ホスト | 接続方法 | ステータスライン |
|---|---|---|
| **Claude Code** | ローカルプラグインマーケットプレイス: フック、コマンド、2つの読み取り専用エージェント、出力スタイル | ネイティブの `statusLine` |
| **opencode** | プラグイン + instructions + MCP + 生成されたスキルルーター（ネイティブのスキルリストは拒否）、最初のメッセージでのリポジトリ自動インデックス | TUIプラグイン（コマンドの statusLine はなし） |
| **Codex** | `hooks.json` + スキル + MCP（`PreToolUse` ゲートを含む） | フックの `systemMessage`（フッターアイテムリストはクローズド） |
| **Cursor** | `hooks.json` + スキル + MCP | `cli-config.json` 内の `statusLine` |
| **dsh** | Claude Codeフックブリッジ + 管理されたパッチブロック（フック、MCP、LLMルート、ツリー外のWebステータスライン） | Web UIプラグイン: セッションヘッダー内の `tezgah-dsh-statusline` |

Codexのゲートは、Bash、`exec_command`、`apply_patch`、Edit/Write、MCPツール、およびサブエージェントの呼び出しを、他のホストと同じチェックを通して実行します。Claudeでは、クレジット表記の禁止も機械的に強制されます。`attribution` 設定が空にされる（`commit`、`pr`、`sessionUrl`）ため、コミットやPRのクレジットはソースレベルでオフになります。

### ステータスライン

すべてのホストは `tezgah-status` から同じ1行のチェックリストをレンダリングするため、ブレが生じることはありません。状態が重要です。マークは、ルールが有効化されこのセッションで適用されている場合は**緑色**、有効化されているがオンデマンド（まだ使用されていない）の場合は**黄色**、キルスイッチによってオフにされている場合は**赤色**になります。`idx` はグラフの準備状態を個別に報告し（`✓` インデックス済み、`↻` 古い、`✗` 未インデックス、`–` 適用外）、`plans N (M blk)` はオープンなプランを報告します。`tezgah-status --legend` はキーを出力し、`--json` はUI用に同じセグメントを提供し、`--no-color`（または `NO_COLOR`）はプレーンテキストを強制します。Claude CodeとCursorはネイティブのステータスラインを色付けします。opencodeのTUIは独自のコンポーネントを色付けし、ホストのイベントバスで更新します。dshのWeb UIはヘッダーコンポーネントを色付けし、タブが表示されている間のみ更新します。Codexは `systemMessage` にプレーンな文字列を表示します。

dshは `dsh-hooks-claude-code` ブリッジを通じて同じClaudeフックファイルを実行するため、セッション開始時の規約、クレジット表記ゲート、および最初のgrepのナッジ（注意喚起）はすべてそこに適用されます。dshは単一の `subagent` ツールを公開しているため、grep専用エクスプローラーの拒否は機能しません（拒否すべきエクスプローラーサブエージェントが存在しないため）。dshのデフォルトの `workspace-write` サンドボックスは、フックのサブプロセスをワークスペースとプラットフォームの一時ディレクトリに制限するため、tezgahは書き込み拒否で失敗するのではなく、書き込み可能なフォールバック先にフックの状態（ナッジマーク、インデックススタンプ）を書き込みます。グラフインデックスワーカーはそのサンドボックス内から `codebase-memory-mcp` キャッシュを書き込むことができないため、`dsh` ランチャーはdshを起動する前に、ユーザーの制限のないシェルでインデックスをウォームアップします。新しいリポジトリは他のホストとまったく同じようにインデックスされ、HEADスタンプが押されます。ランチャーなしで起動されたセッションでも、生の `EPERM` ではなく、サンドボックス化されていないMCPサーバーがグラフを提供しており、インデックスされていないリポジトリに対して `index_repository` が必要であるという明確なレポートを受け取ります。管理されたパッチブロックは、ベース構成がマウントするpi-aiアダプター上に2つのOpenAI互換LLMルートも宣言します。`openrouter`（`OPENROUTER_API_KEY`）と `deepseek`（`DEEPSEEK_API_KEY`）であり、ネイティブの `deepseek-official` デフォルトと並んで選択可能です。キーは起動環境またはハーネスの認証情報ストアから解決され、どちらのキーも設定ファイルには入りません。tezgah-setupはまた、`$DSH_HOME` の下にあるインストール済みCLIを見つける `dsh` ランチャーをPATH（`~/.local/bin/dsh`）に配置するため、どのディレクトリからでも `dsh --profile web` が機能します。

dshにはコマンドのステータスラインがないため、tezgahはWeb UIプラグインとして `tezgah-dsh-statusline` を同梱しています。そのホスト側は、認証された `/api/tezgah.status` ルート（色付き表示の場合は `?format=json`）を介して、セッションのワークスペース用の `tezgah-status` 文字列を提供します。ブラウザ側はそれをセッションヘッダーにレンダリングし、状態に応じて色付けし、ホバー/クリックで凡例を表示し、タブが表示されている間のみ更新します。`tezgah-setup` はプラグインをWebプロファイルにリンクし、`profiles/web/cordis.patch.yml` の管理された行で有効にします（ホスト側がWeb専用の `connection` サービスを注入するため、Web専用です）。`web` を一度も起動したことがないプロファイルは、中途半端に書き込まれるのではなく、ヒントとともにスキップされます。`headless` モードでは、フックブリッジがSessionStart規約を独自の末尾のターンとして注入します（ワンショットタスクがすでに最初のメッセージになった後、その `agent/session-start` が分離された状態で `agent.inject()` を呼び出します）。そのため、`dsh --profile headless "<task>"` は1ターン余分に消費し、リテラルな回答を求めるプロンプトの場合、タスクの回答ではなく規約に対するモデルの反応を出力します。インタラクティブなWebセッションには影響しません。

`bin/tezgah-setup --install` は、`orx` がPATHにある場合、Claude、Codex、opencode、およびCursorに対して `orx install-skills` もトリガーするため、リサーチルールには読み込むべきマニュアルが用意されます。シムファイルはorxに属しているため、tezgahはそのインストーラーを実行するだけで、アンインストール対象としてリストすることはありません。dshにはorxハーネスがありません。そこでのリサーチルールはシェル上の `orx skill` にフォールバックします。

Claudeプラグインには、2つの読み取り専用エージェントも同梱されています。`agents/tezgah-explorer.md` はグラフからコード探索を行い、`file:line` の証拠を返します。`agents/tezgah-reviewer.md` は `detect_changes` を使用してdiffをその影響セットに変換し、実際の欠陥を探します。どちらも書き込みおよびコマンドツールが無効になっており、その出力はアドバイスとしての位置付けです。

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

`--install` は、各ベンダー独自のインストーラーを**ネットワーク経由で**実行することにより、不足しているオプションツールもインストールします。`orx`（`openresearch.sh/install.sh`）、`cursor-agent`（`cursor.com/install`）、`dsh`（`npx` 経由のホームプロファイル）、およびdshが必要とする場合の `pnpm`（`npm` 経由）が含まれ、`curl ... | sh` も含まれます。sudoはどれも必要ありません。実行は `~/.config/tezgah/install.log` に記録されます。`--dry-run` でプレビューしたり、`--no-deps` でスキップしたり（CIで便利です）、`--deps` でツールのみをインストールしたりできます。ツールは `~/.local/bin` または `~/.cargo/bin` に配置されるため、PATHに通すために新しいシェルが必要になる場合があります。tezgah独自のチェックはそれに関係なくこれらのディレクトリを検索するため、非対話型シェルでもそれらが存在すると報告されます。

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
| `bin/tezgah-setup` | ホストごとに有効化されているものを報告する |
| `bin/tezgah-status [PATH]` | そのリポジトリでルールがアクティブかどうかを表示する |
| `bin/tezgah-setup --status [PATH]` | 有効化/使用済みのチェックリストを出力する |
| `bin/tezgah-setup --deps [--dry-run]` | 不足しているオプションツール（orx、cursor-agent、dsh）をインストールする |
| `bin/tezgah-doctor [--clean] [--prune-sessions DAYS]` | ハーネスのディスク使用量を報告する。`--clean` は古いインデックスログを削除し、opencodeのDBをバキュームする。`--prune-sessions` はアイドル状態のセッションを削除する（実際にDBを縮小する唯一のアクション） |
| `/plan-add` | 作業の一部を追跡対象のプランに変換する |
| `/plan-status` | オープンなプランを要約し、次のプランを選択する |
| `/plan-sync` | 完了したプランをクローズする |
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

<a id="cost"></a>

## コスト

推測ではなく、このマシン（macOS、Python 3.10）で測定された値です：

- **コンテキスト。** セッション開始時に約5.4 KB（約1.3kトークン）の規約テキストが注入されます。Codexではターンごとに954バイトのリマインダーが追加されます。Claudeや他のホストにはターンごとのフックがないため、ターンごとのコストはゼロです。完全な `tezgah-contract` スキル（約25k文字）は、タスクがそれを読み込んだ場合にのみコストが発生します。opencodeでは、規約は約5.8 KBのinstructionsファイルとして提供されます。opencodeは通常、すべてのセッションのシステムプロンプトにスキル名/説明/場所のテキストを注入しますが、tezgahはそのリストを拒否し（`permission.skill = deny`）、代わりに生成されたスキルルーターを提供します。そのため、スキルはルーターからその `SKILL.md` パスを読み取ることで見つけられます。
- **レイテンシ。** フックは個別のPythonプロセスであるため、約19ミリ秒のインタープリター起動時間が支配的です。それに加えて、セッション開始に約25ミリ秒、ゲートされたツール呼び出し（Bash/Grep/Task）に約9ミリ秒、CodexのStopセグメントにターンあたり約15ミリ秒が追加されます。
- **ディスク。** インストールには約58ミリ秒かかり、tezgahが書き換えるすべてのファイルは `<file>.tezgah-bak` として1回保持されます。

その効果は呼び出し元の質問に対する回答に表れます。ある実際のリポジトリでは、デフォルトの `grep` は関連するフォルダーを無視して何も見つけられませんでした。無視を無効にすると3.95秒かかり、それでも定義と呼び出し元が混在していました。コードグラフは同じ質問に16ミリ秒で答え、8つの真の呼び出し元のみをリストしました。

opencodeは、長時間のセッションにおけるコンテキストの衛生管理のためにも有効化されています。`tezgah-setup --install` は `compaction.prune` を設定し、古いツールの結果がステップごとに再送信されるのではなくプロンプトからクリアされるようにします。また、`watcher.ignore` リストにより、ファイルウォッチャーが `.git`、`node_modules`、およびビルドディレクトリを監視しないようにします。どちらもマージされ、ユーザーの明示的な値が優先されます。これが重要なのは、opencodeはモデルのコンテキスト制限（1Mトークンのモデルの場合、約980k）の近くでのみ自動コンパクションを行うため、プルーニングを行わないとワーキングセットが数十万トークンにまで膨れ上がるからです。`bin/tezgah-doctor` は結果としてのディスクフットプリントを報告します。`--prune-sessions DAYS` はopencode CLIを通じてアイドル状態のセッションを削除します。これはデータベースを実際に縮小する唯一のアクションです（ページがすべてアクティブであるため、VACUUMだけでは縮小できません）。

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
