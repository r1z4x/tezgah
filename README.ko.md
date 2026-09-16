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

<h3 align="center">실행 중인 모든 AI 코딩 어시스턴트를 위한 단 하나의 작업 계약.</h3>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/github/license/r1z4x/tezgah?style=flat-square"></a>
  <a href="https://github.com/r1z4x/tezgah/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/r1z4x/tezgah/ci.yml?style=flat-square&label=ci"></a>
  <a href="https://github.com/r1z4x/tezgah/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/r1z4x/tezgah?style=flat-square"></a>
</p>

<p align="center">
  <a href="#what-it-enforces">강제 사항</a> &bull;
  <a href="#supported-hosts">지원하는 호스트</a> &bull;
  <a href="#install">설치</a> &bull;
  <a href="#day-to-day">일상적인 사용</a> &bull;
  <a href="#configuration">설정</a> &bull;
  <a href="#cost">비용</a> &bull;
  <a href="#development">개발</a> &bull;
  <a href="#contributing">기여하기</a> &bull;
  <a href="#security">보안</a> &bull;
  <a href="#license">라이선스</a>
</p>

<p align="center"><sub>영어 원문이 기준이며, 번역은 원문보다 지연될 수 있습니다.</sub></p>

---

설정된 리포지토리 루트 내에서 실행하는 모든 AI 코딩 어시스턴트(Claude Code,
opencode, Codex, Cursor, DeepSeek의 dsh 하네스)를 위한 단 하나의 작업 계약입니다.

그대로 두면 각 어시스턴트는 고유한 습관을 가집니다. 어떤 것은 튀르키예어로, 다른 것은
영어로 대답합니다. 어떤 것은 모든 것을 grep으로 찾고, 다른 것은 코드 그래프를 쿼리합니다.
어떤 것은 테스트를 실행하지도 않고 "완료"라고 말합니다. tezgah는 이러한 편차를 제거합니다.
어떤 호스트를 열든 동일한 언어, 동일한 규율, 동일한 증거 기준을 얻게 됩니다.

설계는 두 개의 계층으로 이루어져 있습니다. 규칙은 공유 코어에 한 번만 존재하며, 각 호스트는
해당 코어를 자신이 이해할 수 있는 형태로 변환하는 얇은 어댑터를 갖습니다.
한 곳에서 규칙을 변경하면 5개의 호스트 모두에 적용됩니다. 동일한 텍스트를
5번 복사할 필요가 없습니다.

<a id="what-it-enforces"></a>

## 강제 사항

- **결과 우선의 튀르키예어 보고.** 모든 답변은 튀르키예어로 작성되며 결과나 결정(BLUF)을 먼저
  제시한 다음, 영향도 순으로 요점을 나열합니다. 코드, 커밋, 문서, 하위 에이전트 프롬프트는
  영어로 유지됩니다. 이름, CLI 명령어, 오류 문자열은 절대 번역되지 않습니다.
- **최소한의 코드 (ponytail).** 실제로 작동하는 가장 게으른 변경: YAGNI 원칙을 따르고,
  기존 헬퍼를 재사용하며, 그 다음 표준 라이브러리, 네이티브 플랫폼 기능, 설치된 종속성,
  마지막으로 한 줄 코드를 사용합니다. 요청하지 않은 추상화는 금지됩니다.
  유효성 검사, 오류 처리, 보안은 절대 단순화하여 생략하지 않습니다.
- **코드 그래프 우선 탐색.** "X는 어디에 있나", "누가 Y를 호출하나", "Z가 변경되면 무엇이
  망가지나"와 같은 질문은 grep이 아닌 `codebase-memory-mcp` 그래프(`search_graph`,
  `trace_path`, `search_code`)로 향합니다. 리터럴 텍스트, 설정, 코드가 아닌 파일에 대해서는
  grep을 사용하는 것이 맞습니다.
- **접근성 우선 앱 분석.** 실행 중인 웹이나 모바일 앱은 단계별 스크린샷이 아닌
  접근성 / DOM / 네이티브 뷰 트리를 통해 읽습니다.
  `analyze-app`은 브라우저(Playwright MCP), iOS 시뮬레이터 또는 Android 에뮬레이터(Mobile MCP),
  그리고 선택적인 웹 진단(Chrome DevTools MCP)을 다룹니다. 스크린샷은 트리가 대답할 수 없는
  항목에 대해 명시적으로 요청할 때만 수행하는 작업입니다.
- **외부의 두 번째 의견.** 사소하지 않거나 되돌리기 어려운 결정을 내리기 전에,
  `~/.config/tezgah/bin/consult`는 OpenRouter(또는 `--provider deepseek`를 사용한 DeepSeek API)를
  통해 독립적인 모델들에게 병렬로 질문하며, 에이전트는 그들이 동의하거나 동의하지 않은 부분을 보고합니다.
- **OpenResearch를 통한 연구.** 라우터가 작업을 연구(문헌 검토, 가설 설정 및 테스트, 실험 실행,
  연구 결과물)로 판단하면, 프로토콜을 즉흥적으로 만드는 대신 alphaXiv의 OpenResearch(`orx`)를
  통해 작업을 주도하고 `orx` 매뉴얼을 먼저 로드합니다. 단순한 코드 탐색은 코드 그래프에 남습니다.
  `orx`가 없는 경우, 라우터는 이를 알리고 호스트 하위 에이전트로 폴백합니다.
- **검증 하의 정직성.** 출력을 확인하지 않은 상태에서는 완료, 테스트, 수정되었다고
  보고하지 않습니다. 실패한 테스트는 정확한 오류와 함께 실패로 보고되며, 건너뛴 검사는 명확하게 명시됩니다.
- **어디에도 AI 출처 표기 금지.** 커밋, 병합, 태그 메시지, PR 및 이슈 텍스트, 코드 주석,
  파일 헤더, 문서 등 지속되거나 게시되는 어떤 것에도 어시스턴트, 모델, 공급업체 또는 "AI"의
  공로를 표기해서는 안 됩니다. 도구를 사용하는 것은 괜찮지만, 작업물에 도구의 이름을 서명하는 것은 안 됩니다.
- **2계층 오케스트레이션.** 메인 스레드가 결정하고 검증합니다. 저렴한 모델(`~/.config/tezgah/bin/codegen`,
  기본값 OpenRouter 또는 `--provider deepseek`)은 스크래치 디렉토리에 제한적이고 잘 명시된 편집 초안을
  작성합니다. 라우터를 통하지 않고는 리포지토리에 도달할 수 없으며, 실패한 초안은 자동으로 메인 모델로 폴백됩니다.
- **리포지토리별 하위 에이전트.** 세션 시작 시 포함된 리포지토리는 기능이 제한된 소규모
  에이전트 세트(`tezgah-explorer`, `tezgah-reviewer`,
  `tezgah-researcher`, `tezgah-verifier`)와 `tezgah-orchestrator`를 얻게 되며,
  이는 설치된 각 호스트의 네이티브 표면(Claude/Cursor `.claude/agents/`,
  opencode `.opencode/agents/` 및 실시간 설정 주입, Codex
  `.codex/agents/`)에 렌더링되고 관리되는 하나의 `.gitignore` 블록으로 무시됩니다. Claude에서
  오케스트레이터의 `Agent(tezgah-*)` 허용 목록은 메인 스레드(`claude --agent tezgah-orchestrator`)로
  실행될 때만 적용되며, 하위 에이전트로서 이 목록은 무시됩니다. dsh는 역할별 표면이 없으므로 계약의 라우터 규칙이 이를 다룹니다.

<a id="supported-hosts"></a>

## 지원하는 호스트

| 호스트 | 연결 방식 | 상태 표시줄 |
|---|---|---|
| **Claude Code** | 로컬 플러그인 마켓플레이스: 훅, 명령어, 두 개의 읽기 전용 에이전트, 출력 스타일 | 네이티브 `statusLine` |
| **opencode** | 플러그인 + 지침 + MCP + 생성된 스킬 라우터 (네이티브 스킬 목록 거부됨), 첫 메시지 시 리포지토리 자동 인덱싱 | TUI 플러그인 (명령어 statusLine 없음) |
| **Codex** | `hooks.json` + 스킬 + MCP, `PreToolUse` 게이트 포함 | 훅 `systemMessage` (푸터 항목 목록은 닫혀 있음) |
| **Cursor** | `hooks.json` + 스킬 + MCP | `cli-config.json`의 `statusLine` |
| **dsh** | Claude Code 훅 브리지 + 관리형 패치 블록 (훅, MCP, LLM 라우트, 트리 외부 웹 상태 표시줄) | 웹 UI 플러그인: 세션 헤더의 `tezgah-dsh-statusline` |

Codex 게이트는 Bash, `exec_command`, `apply_patch`, Edit/Write, MCP 도구 및
하위 에이전트 호출을 다른 호스트와 동일한 검사를 통해 실행합니다. Claude에서는
출처 표기 금지도 기계적으로 강제됩니다. `attribution` 설정이 비워져(`commit`, `pr`, `sessionUrl`)
커밋 및 PR 크레딧이 소스에서 꺼집니다.

### 상태 표시줄

모든 호스트는 `tezgah-status`의 동일한 한 줄 체크리스트를 렌더링하므로 편차가 발생할 수 없습니다.
상태가 핵심입니다. 규칙이 준비되어 이번 세션에서 적용 중이면 마크가 **녹색**,
준비되었지만 온디맨드 상태(아직 사용되지 않음)이면 **노란색**, 킬 스위치로 꺼져 있으면 **빨간색**입니다.
`idx`는 그래프 준비 상태를 별도로 보고하며(`✓` 인덱싱됨, `↻` 오래됨, `✗` 인덱싱 안 됨, `–` 해당 없음),
`plans N (M blk)`는 열려 있는 계획을 나타냅니다. `tezgah-status --legend`는 범례를 출력하고,
`--json`은 UI용으로 동일한 세그먼트를 제공하며, `--no-color`(또는 `NO_COLOR`)는 일반 텍스트를 강제합니다.
Claude Code와 Cursor는 네이티브 상태 표시줄에 색상을 지정합니다. opencode TUI는 자체 컴포넌트에
색상을 지정하고 호스트 이벤트 버스에서 새로 고칩니다. dsh 웹 UI는 헤더 컴포넌트에 색상을 지정하고
탭이 표시되는 동안에만 새로 고칩니다. Codex는 `systemMessage`에 일반 문자열을 표시합니다.

dsh는 `dsh-hooks-claude-code` 브리지를 통해 동일한 Claude 훅 파일을 실행하므로,
세션 시작 계약, 출처 표기 게이트, 첫 번째 grep 넛지가 모두 여기에 적용됩니다.
dsh는 단일 `subagent` 도구를 노출하므로 grep 전용 탐색기 거부는 비활성 상태입니다.
거부할 탐색기 하위 에이전트가 없기 때문입니다. dsh의 기본 `workspace-write` 샌드박스는
훅 하위 프로세스를 작업 공간과 플랫폼 임시 디렉토리로 제한하므로, tezgah는 쓰기 거부로
실패하는 대신 쓰기 가능한 폴백에 훅 상태(넛지 마크, 인덱스 스탬프)를 기록합니다.
그래프 인덱스 워커는 해당 샌드박스 내부에서 `codebase-memory-mcp` 캐시를 쓸 수 없으므로,
`dsh` 런처는 dsh를 부팅하기 전에 사용자의 제한 없는 셸에서 인덱스를 웜업합니다.
새 리포지토리는 다른 호스트와 정확히 동일하게 HEAD 스탬프가 찍혀 인덱싱됩니다.
런처 없이 부팅된 세션은 원시 `EPERM` 대신, 샌드박스 처리되지 않은 MCP 서버가 그래프를 제공하며
인덱싱하지 않은 리포지토리에 대해 `index_repository`가 필요하다는 명확한 보고를 받게 됩니다.
관리형 패치 블록은 또한 기본 구성이 마운트하는 pi-ai 어댑터에 두 개의 OpenAI 호환 LLM 라우트를 선언합니다.
네이티브 `deepseek-official` 기본값과 함께 선택할 수 있는 `openrouter`(`OPENROUTER_API_KEY`) 및
`deepseek`(`DEEPSEEK_API_KEY`)입니다. 키는 실행 환경이나 하네스 자격 증명 저장소에서 확인되며,
두 키 모두 설정 파일에 들어가지 않습니다. tezgah-setup은 또한 `$DSH_HOME` 아래에 설치된 CLI를 찾는
`dsh` 런처를 PATH(`~/.local/bin/dsh`)에 배치하므로, 어느 디렉토리에서나 `dsh --profile web`이 작동합니다.

dsh에는 명령어 상태 표시줄이 없으므로, tezgah는 이를 웹 UI 플러그인인 `tezgah-dsh-statusline`으로 제공합니다.
호스트 측은 인증된 `/api/tezgah.status` 라우트를 통해 세션의 작업 공간에 대한 `tezgah-status` 문자열을
제공하며(색상 보기를 위해 `?format=json` 사용), 브라우저 측은 이를 세션 헤더에 렌더링하고 상태에 따라
색상을 지정하며 호버/클릭 범례를 제공하고 탭이 표시되는 동안에만 새로 고칩니다. `tezgah-setup`은
플러그인을 웹 프로필에 연결하고 `profiles/web/cordis.patch.yml`의 관리형 행으로 활성화합니다(호스트 측이
웹 전용 `connection` 서비스를 주입하기 때문에 웹 전용임). `web`을 부팅한 적이 없는 프로필은 절반만
작성되는 대신 힌트와 함께 건너뜁니다. `headless` 모드에서 훅 브리지는 SessionStart 계약을 자체 후행 턴으로
주입하므로(원샷 작업이 이미 첫 번째 메시지인 후 `agent/session-start`가 분리된 상태로 `agent.inject()`를 호출함),
`dsh --profile headless "<task>"`는 턴을 하나 더 소비하고 리터럴 답변 프롬프트의 경우 작업의 답변 대신
계약에 대한 모델의 반응을 출력합니다. 대화형 웹 세션은 영향을 받지 않습니다.

`bin/tezgah-setup --install`은 `orx`가 PATH에 있을 때 Claude, Codex, opencode, Cursor에 대해
`orx install-skills`도 트리거하므로 연구 규칙이 로드할 매뉴얼을 갖게 됩니다. 심(shim) 파일은 orx에 속하므로,
tezgah는 해당 설치 프로그램만 실행하며 제거 목록에 절대 포함하지 않습니다. dsh에는 orx 하네스가 없으므로,
그곳의 연구 규칙은 셸의 `orx skill`로 폴백합니다.

Claude 플러그인은 또한 두 개의 읽기 전용 에이전트를 제공합니다. `agents/tezgah-explorer.md`는
그래프에서 코드 탐색을 수행하고 `file:line` 증거를 반환합니다.
`agents/tezgah-reviewer.md`는 `detect_changes`를 사용하여 diff를 영향 세트로 변환한 다음
실제 결함을 찾습니다. 둘 다 쓰기 및 명령어 도구가 비활성화되어 있으며, 그 출력은 권고용입니다.

### 앱 분석

`analyze-app`은 접근성 트리에서 실행 중인 애플리케이션을 구동합니다. 기본 루프는 열기,
트리 읽기, 작업 수행, 콘솔/네트워크/로그 관찰, 트리 다시 읽기입니다. 스크린샷은 트리가
대답할 수 없는 항목(캔버스, 게임, 애니메이션, 픽셀 수준의 시각적 회귀)에 대한 명시적인 작업입니다.
이 스킬은 모든 호스트를 위한 하나의 경로이며, 그 아래의 서버들은 `hooks/tezgah_apps.py`에 있는
하나의 공유 사양입니다:

| 서버 | 대상 | 연결 방식 |
|---|---|---|
| `playwright` (`@playwright/mcp`) | 웹 페이지, `browser_*` 도구 | opencode, Codex, Cursor, Claude (플러그인 `.mcp.json`) |
| `mobile-mcp` (`@mobilenext/mobile-mcp`) | iOS 시뮬레이터 / Android 에뮬레이터, `mobile_*` 도구 | 동일 |
| `chrome-devtools` (선택 사항, `--devtools`) | 웹 성능 추적, 심층 네트워크, 소스 매핑된 콘솔 | 동일 |

브라우저는 기본적으로 **격리된** 프로필을 실행하므로, 실행 시 실제 Chrome 상태를 절대 건드리지 않습니다.
로그인된 흐름을 분석하는 것은 의도적인 연결(`--cdp-endpoint` 또는 Playwright 확장 프로그램)이며
기본값이 아닙니다. 스크린샷, 추적 및 트리 덤프는 `~/.cache/tezgah/apps`에 저장되며(`TEZGAH_ARTIFACTS`로 재정의 가능),
에이전트는 인라인 이미지 바이트가 아닌 경로를 반환받습니다. 서버는 `npx`를 통해 실행되므로 node가 필요하지만
자체 설치는 필요하지 않습니다. `tezgah-setup --install --devtools`는 선택적인 웹 진단 서버를 추가합니다.
dsh는 `dsh-mcp-client` 브리지(`serverName` / `command` / `args` / `env`, 게시된 설정 스키마에 대해 확인됨)를 통해
동일한 두 서버를 연결하고, Claude는 플러그인의 `.mcp.json`에서 이를 가져옵니다(`claude plugin details tezgah`는
MCP 서버 2개를 나열하고 둘 다 연결됨). `mobile-mcp`는 마찰이 더 큰 부분입니다. macOS는 접근성 / 화면 녹화 권한을
요청할 수 있으며 부하가 걸리면 뷰 트리가 누락될 수 있으므로, 스킬은 스크린샷으로 폴백하기 전에 트리를 재시도합니다.

CI는 두 서버 모두에 대해 결정론적 핸드셰이크(브라우저 없음, 기기 없음)를 실행합니다:
`TEZGAH_E2E_STRICT=1 python3 tests/e2e_analyze_wiring.py`. 두 가지 선택적 로컬 스모크 테스트는 더 나아갑니다.
`TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_web.py`는 Playwright MCP를 시작하고 탐색하여 스크린샷 없이 스냅샷을 읽습니다.
`TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_mobile.py`는 Mobile MCP를 시작하고 뷰 트리 도구를 확인하며 기기를 나열합니다.
node, 브라우저 빌드 또는 기기가 누락된 경우 `SKIP: ...`을 출력합니다.

<a id="install"></a>

## 설치

Python 3.8 이상이 필요합니다. dsh 호스트와 해당 웹 상태 표시줄(`pnpm` 포함)을 위해 node + npm이 필요합니다.
선택적 통합은 우아하게 저하(degrade gracefully)됩니다. `codebase-memory-mcp`가 PATH에 있으면 그래프를 구동하고,
모델 키는 `consult` 및 `codegen`을 구동합니다. 기본적으로 OpenRouter(`OPENROUTER_API_KEY` 또는 `~/.config/openrouter/key`)이거나
`--provider deepseek`를 사용한 DeepSeek API(`DEEPSEEK_API_KEY` 또는 `~/.config/deepseek/key`)입니다.
PATH에 있는 OpenResearch의 `orx`는 연구 규칙이 주도할 무언가를 제공합니다. 선택한 제공자의 키가 누락된 경우,
tezgah는 있는 척하지 않고 누락되었다고 알립니다.

클론한 다음, 감지된 모든 호스트를 한 번에 준비시킵니다:

```bash
git clone https://github.com/r1z4x/tezgah.git ~/Projects/tezgah
cd ~/Projects/tezgah
bin/tezgah-setup --install
```

`--install`은 또한 각 공급업체의 자체 설치 프로그램을 **네트워크를 통해** 실행하여 누락된 선택적 도구를 설치합니다:
`orx` (`openresearch.sh/install.sh`), `cursor-agent` (`cursor.com/install`), `dsh`
(`npx`를 통한 홈 프로필), 그리고 dsh에 필요할 때 `pnpm`(`npm`을 통해)을 설치하며,
`curl ... | sh`도 포함됩니다. 어느 것도 sudo가 필요하지 않으며, 실행 기록은
`~/.config/tezgah/install.log`에 저장됩니다. `--dry-run`으로 미리 보거나, `--no-deps`로 건너뛰거나(CI에서 유용함),
`--deps`로 도구만 설치할 수 있습니다. 도구는 `~/.local/bin` 또는 `~/.cargo/bin`에 저장되므로
PATH에 적용하려면 새 셸이 필요할 수 있습니다. tezgah의 자체 검사는 이와 무관하게 해당 디렉토리를 확인하므로,
비대화형 셸에서도 도구가 존재한다고 보고합니다.

이전 설정이 이미 존재하는 경우 먼저 가져옵니다. 삭제되지 않고 옆으로 이동됩니다:

```bash
bin/tezgah-setup --adopt
```

Claude Code는 자체 플러그인 채널을 통해 설치됩니다:

```bash
claude plugin marketplace add ~/Projects/tezgah
claude plugin install tezgah@rizacan-local
```

필요할 때 설치를 명시적으로 제한합니다:

```bash
bin/tezgah-setup --install --hosts claude,codex,opencode,cursor,dsh
bin/tezgah-setup --roots ~/work:~/oss --install
```

<a id="day-to-day"></a>

## 일상적인 사용

실행할 것이 없습니다. 호스트가 시작될 때 규칙이 로드됩니다. 알아두면 좋은 몇 가지 명령어가 있습니다:

| 명령어 | 목적 |
|---|---|
| `bin/tezgah-setup` | 호스트별로 준비된 항목 보고 |
| `bin/tezgah-status [PATH]` | 해당 리포지토리에서 규칙이 활성화되어 있는지 표시 |
| `bin/tezgah-setup --status [PATH]` | 준비/사용된 체크리스트 출력 |
| `bin/tezgah-setup --deps [--dry-run]` | 누락된 선택적 도구(orx, cursor-agent, dsh) 설치 |
| `bin/tezgah-doctor [--clean] [--prune-sessions DAYS]` | 하네스 디스크 사용량 보고; `--clean`은 오래된 인덱스 로그를 삭제하고 opencode DB를 정리(vacuum)합니다; `--prune-sessions`는 유휴 세션을 삭제합니다(실제로 DB 크기를 줄이는 유일한 작업) |
| `/plan-add` | 작업을 추적되는 계획으로 변환 |
| `/plan-status` | 열려 있는 계획을 요약하고 다음 계획 선택 |
| `/plan-sync` | 완료된 계획 마감 |
| `bin/tezgah-setup --version` | 플러그인 버전 출력 |
| `bin/tezgah-setup --uninstall` | tezgah의 심볼릭 링크, 호스트 훅 항목, dsh 관리형 블록만 제거 |

<a id="configuration"></a>

## 설정

tezgah는 설정된 루트 아래에서만 준비되며, 그 외의 곳에서는 조용히 있습니다.

- 기본 루트: `~/Projects`.
- `~/.config/tezgah/config.json`: `{"roots": ["~/Projects", "~/work"]}`.
- `TEZGAH_ROOTS` (경로 구분자 목록)는 일회성 작업 및 CI를 위해 파일을 재정의합니다.

킬 스위치는 `~/.config/tezgah/`에 있습니다. 각각은 세션에 주입되는 텍스트에서 해당 규칙을 제거하므로 규칙이 실제로 중지됩니다:

| 스위치 | 끄는 기능 |
|---|---|
| `exec-mode.off` | 튀르키예어, 결과 우선 보고 |
| `ponytail-auto.off` | 최소한의 코드 규칙 |
| `spec-off` | 빌드 전 사양 작성 규칙 |
| `consult-off` | 외부의 두 번째 의견 규칙 |
| `research-off` | 연구 작업을 OpenResearch로 라우팅 |
| `orchestrate-off` | 하위 에이전트 위임 (위임 금지 줄 추가) |
| `reminder-off` | 턴별 알림 텍스트 |
| `pretooluse-off` | PreToolUse 게이트 자체 (출처 표기, 탐색기, grep 넛지) |

리포지토리별로 `.no-ponytail`, `.no-cbm`, `.no-lessons`는 각각 최소한의 코드 규칙,
코드 그래프 규칙(및 자동 인덱싱), 교훈 원장을 끕니다.

사용자가 실수를 지적하면 에이전트는 리포지토리의 `.tezgah/lessons.md`에 한 줄짜리 교훈을 추가합니다.
가장 최근 줄이 세션 시작 시 주입되므로 동일한 실수가 조용히 반복될 수 없습니다.

<a id="cost"></a>

## 비용

추정치가 아닌 이 머신(macOS, Python 3.10)에서 측정된 값입니다:

- **컨텍스트.** 세션 시작 시 약 4.8KB(약 1.2k 토큰)의 계약 텍스트가 주입됩니다.
  Codex에서는 매 턴마다 480바이트의 알림이 함께 전달됩니다. Claude와 다른 호스트에는
  턴별 훅이 없으므로 턴별 비용은 0입니다. 전체 `tezgah-contract` 스킬(약 19.9k 문자)은
  작업이 이를 로드할 때만 비용이 발생합니다. opencode에서 계약은 약 5.5KB의 지침 파일로 제공됩니다.
  그렇지 않으면 opencode는 모든 세션의 시스템 프롬프트에 약 53KB의 스킬 이름/설명/위치 텍스트를 주입합니다.
  tezgah는 해당 목록을 거부(`permission.skill = deny`)하고 대신 생성된 약 16KB의 스킬 라우터를 제공하므로,
  라우터에서 `SKILL.md` 경로를 읽어 스킬을 찾습니다.
- **지연 시간.** 훅은 별도의 Python 프로세스이므로 약 19ms의 인터프리터 시작 시간이 지배적입니다.
  여기에 세션 시작이 약 25ms를 추가하고, 게이트된 도구 호출(Bash/Grep/Task)이 약 9ms를 추가하며,
  Codex의 Stop 세그먼트가 턴당 약 15ms를 추가합니다.
- **디스크.** 설치에는 약 58ms가 소요되며, tezgah가 다시 작성하는 모든 파일은
  `<file>.tezgah-bak`으로 한 번 보관됩니다.

그 효과는 호출자 질문에서 나타납니다. 실제 한 리포지토리에서 기본 `grep`은 관련 폴더를 무시하고
아무것도 찾지 못했습니다. 무시를 비활성화했을 때는 3.95초가 걸렸고 여전히 정의와 호출 위치가 섞여 있었습니다.
코드 그래프는 동일한 질문에 16ms 만에 대답하여 8개의 실제 호출 위치만 나열했습니다.

opencode는 긴 세션의 컨텍스트 위생을 위해서도 준비되어 있습니다. `tezgah-setup --install`은
`compaction.prune`을 설정하여 오래된 도구 결과가 매 단계마다 다시 전송되는 대신 프롬프트에서 지워지도록 하며,
`watcher.ignore` 목록은 파일 감시자가 `.git`, `node_modules` 및 빌드 디렉토리를 벗어나게 합니다.
둘 다 병합되며 명시적인 사용자 값이 우선합니다. 이는 opencode가 모델의 컨텍스트 제한(1M 토큰 모델의 경우 약 980k)
근처에서만 자동 압축을 수행하기 때문에 중요합니다. 정리하지 않으면 작업 세트가 수십만 토큰으로 늘어납니다.
`bin/tezgah-doctor`는 결과적인 디스크 공간을 보고합니다. `--prune-sessions DAYS`는 opencode CLI를 통해
유휴 세션을 삭제하며, 이는 실제로 데이터베이스 크기를 줄이는 유일한 작업입니다. VACUUM만으로는 줄일 수 없습니다.
페이지가 모두 활성 상태이기 때문입니다.

<a id="development"></a>

## 개발

```bash
python3 -m unittest discover -s tests -v   # stdlib test suite
pip install -r requirements-dev.txt        # pinned ruff, the only dev dep
ruff check .                               # lint (config in pyproject.toml)
```

CI는 Python 3.10과 3.12 모두에서 실행됩니다. 이 체크아웃에서 설치된 Claude 복사본을 새로 고치려면
`bin/tezgah-setup --sync`를 사용하고, `claude plugin validate .claude-plugin/plugin.json`으로
매니페스트를 검증하세요. 버전을 올릴 때는 `.claude-plugin/plugin.json`과 `.claude-plugin/marketplace.json`을
함께 업데이트해야 합니다. 두 파일이 일치해야 합니다.

`codebase-memory-mcp`는 사용자가 설치합니다. Orca의 훅과 파일은 이 프로젝트의 일부가 아니며
건드리지 않고 그대로 둡니다. Claude는 SessionStart 훅에서 항상 켜져 있는 코어를 받습니다.
`output-styles/tezgah.md`는 플러그인 출력 스타일을 로드하는 빌드를 위한 복제본이므로,
훅이 권위 있는 경로입니다.

<a id="contributing"></a>

## 기여하기

작고 단일 목적의 변경 사항이 가장 수락되기 쉽습니다. 규칙이 진정으로 호스트에 특정되지 않는 한
공유 코어(`hooks/`)에 속합니다. 호스트 차이는 `hosts/<name>/` 아래의 해당 어댑터에 속합니다.
정확성을 유지하면서 diff를 최대한 짧게 유지하세요. 프로젝트 자체의 최소한의 코드 규칙이
이 프로젝트에도 적용됩니다.

풀 리퀘스트를 열기 전에 CI가 실행하는 것과 동일한 세 가지 검사를 실행하세요:

```bash
python3 -m compileall -q hooks hosts bin statusline.py   # byte-compile every script
python3 -m unittest discover -s tests                     # stdlib test suite
ruff check .                                              # lint; config in pyproject.toml
```

`ruff`는 유일한 개발 종속성인 `requirements-dev.txt`(`pip install -r requirements-dev.txt`)에서 제공됩니다.

<a id="security"></a>

## 보안

취약점은 공개 이슈가 아닌 GitHub의 보안 권고(**Security** 탭 → **Report a vulnerability**)를 통해 비공개로 보고해 주세요.

tezgah는 셸 훅을 실행하고, 호스트 설정을 작성하며, 모든 세션에 텍스트를 주입하므로,
훅이 공격자가 제어하는 코드를 실행하게 하거나, 키를 설정 파일로 유출하거나, 샌드박스를 넓히거나,
리포지토리 콘텐츠가 지침 텍스트로 에스컬레이션되도록 하는 모든 것이 범위에 포함됩니다.
호스트, tezgah 버전(`bin/tezgah-setup --version`), 그리고 최소한의 재현 방법을 포함해 주세요.

<a id="license"></a>

## 라이선스

루트 `LICENSE`(MIT)는 tezgah 자체 파일에 적용됩니다. `skills/ponytail` 및
`skills/no-ai-slop`은 `NOTICE`에 기록된 자체 MIT 조건에 따라 벤더링(vendored)되었습니다.
