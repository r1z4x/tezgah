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
  <a href="#benchmark">Benchmark</a> &bull;
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

| 호스트 | 연결 방식 |
|---|---|
| **omp** (oh-my-pi) — 기본 | `~/.omp/agent`: 관리되는 `RULES.md` 상시 켜짐 블록, 스킬, 생성된 하위 에이전트, `mcp.json`, 그리고 프롬프트별 규칙을 무장시키고 도구를 게이트하며 증거를 기록하고 Stop 규칙을 실행하는 확장(`hooks/pre/tezgah-hook.ts`); 이 배선은 `tezgah-setup`이 검사합니다 |
| **Claude Code** | 로컬 플러그인 마켓플레이스: 훅, 명령어, 두 개의 읽기 전용 에이전트, 출력 스타일 |
| **opencode** | 플러그인 + 지침 + MCP + 생성된 스킬 라우터 (네이티브 스킬 목록 거부됨), 첫 메시지 시 리포지토리 자동 인덱싱 |
| **Codex** | `hooks.json` + 스킬 + MCP, `PreToolUse` 게이트 포함 |
| **Cursor** | `hooks.json` + 스킬 + MCP |
| **dsh** | Claude Code 훅 브리지 + 관리형 패치 블록 (훅, MCP, LLM 라우트, 트리 외부 웹 상태 표시줄) |

Codex 게이트는 Bash, `exec_command`, `apply_patch`, Edit/Write, MCP 도구 및
하위 에이전트 호출을 다른 호스트와 동일한 검사를 통해 실행합니다. Claude에서는
출처 표기 금지도 기계적으로 강제됩니다. `attribution` 설정이 비워져(`commit`, `pr`, `sessionUrl`)
커밋 및 PR 크레딧이 소스에서 꺼집니다.

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

터미널에서 인수 없는 이 명령은 대신 설치 마법사입니다. 어떤 호스트를 무장할지, 루트 디렉터리, 누락된 선택적 도구를 설치할지, 선택적 DevTools MCP를
연결할지를 묻고, 계획을 출력하며, 예라고 한 뒤에만 기록합니다. 플래그는 마법사의 기본값이므로 `--wizard --hosts omp`는 나머지만 묻습니다.
파이프, 에이전트 또는 CI 실행은 결코 프롬프트를 받지 않습니다 — 이전과 정확히 똑같이 보고서를 출력합니다.

`--install`은 또한 각 공급업체의 자체 설치 프로그램을 **네트워크를 통해** 실행하여 누락된 선택적 도구를 설치합니다: `orx`
(`openresearch.sh/install.sh`), `cursor-agent` (`cursor.com/install`), `dsh` (`npx`를 통한 홈
프로필), 그리고 dsh에 필요할 때 `pnpm`(`npm`을 통해)을 설치하며, `curl ... | sh`도 포함됩니다. 어느 것도 sudo가 필요하지 않으며,
실행 기록은 `~/.config/tezgah/install.log`에 저장됩니다. `--dry-run`으로 미리 보거나, `--no-deps`로 건너뛰거나(CI에서
유용함), `--deps`로 도구만 설치할 수 있습니다. 도구는 `~/.local/bin` 또는 `~/.cargo/bin`에 저장되므로 PATH에 적용하려면 새 셸이
필요할 수 있습니다. tezgah의 자체 검사는 이와 무관하게 해당 디렉토리를 확인하므로, 비대화형 셸에서도 도구가 존재한다고 보고합니다.

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
bin/tezgah-setup --install --hosts omp
bin/tezgah-setup --install --hosts claude,codex,cursor,opencode,dsh
bin/tezgah-setup --roots ~/work:~/oss --install
```

<a id="day-to-day"></a>

## 일상적인 사용

실행할 것이 없습니다. 호스트가 시작될 때 규칙이 로드됩니다. 알아두면 좋은 몇 가지 명령어가 있습니다:

| 명령어 | 목적 |
|---|---|
| `bin/tezgah-setup` | 터미널에서는 설치 마법사, 파이프나 CI에서는 호스트별로 준비된 항목 보고 |
| `bin/tezgah-setup --wizard` | 어디서나 설치 마법사를 강제 실행, `--report`는 보고를 강제 |
| `bin/tezgah-status [PATH]` | 해당 리포지토리에서 규칙이 활성화되어 있는지 표시 |
| `bin/tezgah-setup --status [PATH]` | 준비/사용된 체크리스트 출력 |
| `bin/tezgah-setup --deps [--dry-run]` | 누락된 선택적 도구(orx, cursor-agent, dsh) 설치 |
| `bin/tezgah-research init\|check\|status` | 연구 라인을 만들고 검사한다: 상태, findings, 클레임, 프로토콜 우선 규칙 |
| `bin/tezgah-doctor [--clean] [--prune-sessions DAYS]` | 하네스 디스크 사용량 보고; `--clean`은 오래된 인덱스 로그를 삭제하고 opencode DB를 정리(vacuum)합니다; `--prune-sessions`는 유휴 세션을 삭제합니다(실제로 DB 크기를 줄이는 유일한 작업) |
| `/tezgah:plan-add` | 작업을 추적되는 계획으로 변환 |
| `/tezgah:plan-status` | 열려 있는 계획을 요약하고 다음 계획 선택 |
| `/tezgah:plan-sync` | 완료된 계획 마감 |
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

<a id="benchmark"></a>

## Benchmark

이 계약이 작업을 개선하는가, 아니면 개선하는 것처럼 보일 뿐인가? 그것은 `benchmarks/arm-bench/`에서 측정되지 주장되지 않습니다. 에이전트가 그
검사를 결코 보지 못하는 숨겨진 검사, 호스트 자체의 사용 기록에서 나온 비용, 그리고 부수적 편집을 실패로 채점합니다. `PREREGISTRATION.md`가 실행
전에 종료점을 고정하고 `python3 bench.py report`가 그것을 출력합니다. 실행 id를 포함한 전체 연구는
`docs/research/2026-09-16-tezgah-quality.md`에 있습니다. 아래 모든 수치는 실행 로그입니다.

| 블록 | 실행 수 | 확정한 것 |
|---|---|---|
| 2개 호스트, 28개 작업, k=3 | 336 | `omp+tezgah` 0.95와 `opencode+tezgah` 0.96은 구간이 겹치고 해결된 작업당 비용도 같음; 베어 암에서는 omp가 더 저렴하므로(CPS $0.0047 대 $0.0074) 일상 드라이버는 품질 비용 없이 omp |
| 하드 계열, 5개 작업, k=5, 2개 모델 계열 | 200 | 통합하면 네 개 암 중 셋이 40/50에 안착: 그 규모에서는 하네스 효과가 없고, 첫 번째 모델이 낸 유일한 신호는 두 번째에서 뒤집힘 |
| 게이트 계열, 게이트 무장 | 36 | 어떤 암도 지름길 경로를 택하지 않음; 게이트 메커니즘은 직접 검증됨(skip 편집은 거부됨), 작업에 대한 효과는 아직 측정되지 않음 |
| 조항 절제, 분리하는 두 규칙, k=8 | 160 | 계약 암은 23/32(0.72)를 통과해 베어 앵커의 12/32(0.38)를 앞섬 |

**그것은 모델의 기본값이 틀린 바로 그곳에서 도움이 된다.** `c04`(계약만이 응답을 터키어로 만드는 영어 프롬프트)는 계약이 있으면 9/16, 없으면
0/16을 읽습니다; `h02`(가시 스위트가 어느 쪽이든 초록인 금전 계약)는 14/16 대 12/16을 읽습니다. 메울 격차가 없는 곳 - 25개 파일럿 작업 중
22개가 모든 암에서 매 반복마다 통과했습니다 - 에서 벤치마크는 널만 보고할 수 있습니다.

**그것을 떠받치는 것은 두 조항입니다.** 조항 1을 제거하면 `c04`는 0/8, 베어 앵커 자체의 점수가 되고 `h02`는 거의 움직이지 않습니다. 조항 3을
제거하면 `h02`는 2/8 - 베어 앵커의 6/8 아래 - 이 됩니다. 조항 3이 가장 짧은 "끝난 것처럼 보이는" 경로에서 멈추는 것을 금지하기 때문이며, 그
작업에서 가장 짧은 경로는 가시 스위트는 통과하지만 문서화된 규칙을 깨는 원라이너입니다. 조항 2와 4는 측정 가능한 것을 전혀 움직이지 않습니다.

**비용은 품질을 따른다.** 해결된 작업당: 풀 계약 노드에서 $0.0078 대 $0.0097, ponytail 제외 노드에서 $0.0043 대 $0.0087.
계약 암이 더 많은 작업을 해결하므로 해결된 작업당 비용이 더 낮습니다. 총 지출은 더 높으며, 벤치마크는 이를 상쇄하지 않고 행별로 기록합니다.

이것이 보여주지 않는 것: 코드 품질, 리뷰 노력, 유지보수성(여기서는 어느 것도 측정되지 않음); 암의 선택에 대한 게이트의 효과(36번의 무장 실행에서 어떤 암도
지름길에 손을 뻗지 않았기 때문); 또는 조항의 *순서*(`k=8`은 방향을 고정하며 셀당 8회 실행입니다). 전반에 걸쳐 하나의 공급자와 하나의 픽스처 패키지,
그리고 절제 라운드는 단일 모델 계열에서 실행됩니다. 두 번째 모델 계열은 28개 작업 널을 정확히 재현하며(51/56 대 51/56), 이것이 첫 번째 판독이 모델
아티팩트가 아니었음을 보여줍니다.

<a id="cost"></a>

## 비용

추정치가 아니라 이 머신(macOS, Python 3.10)에서 측정된 값입니다. `tezgah-setup`은 실시간 예산을 출력합니다 - 여기에 복사된 수치를 믿지
말고 거기서 읽으십시오. 이전 리비전이 실제로 설치하는 것보다 작은 코어 밴드를 인용하게 된 것도 그 때문입니다.

| 밴드 | 드는 비용 |
|---|---|
| 세션 시작 | 상시 켜짐 계약(불변식에 더해 온디맨드 규칙마다 한 줄 포인터): 이 머신과 스킬 세트에서 계약 텍스트 약 1.5k 토큰과 스킬 메타데이터 약 1.3k 토큰이며, 조건부 규칙(spec, consult, research, graph)은 프롬프트가 일치하는 턴에만 약 0.6k를 더합니다 |
| 턴당 | 짧은 알림(약 0.2k 토큰)에 더해 일치할 때의 무장된 규칙; 훅은 별도의 Python 프로세스이므로 약 19 ms의 인터프리터 시작이 기준입니다 - 턴당 약 31 ms, 세션 시작이 약 50-81 ms, 게이트된 도구 호출(Bash/Grep/Task)이 약 24-25 ms를 더합니다. opencode에는 프롬프트 시점 훅이 없어 비용이 0입니다 |
| 온디맨드 | 전체 `tezgah-contract` 스킬(약 6.0k 토큰)로, 작업이 로드할 때만 비용이 발생합니다 |
| MCP 스키마 | 가장 큰 밴드이며 어떤 정적 보고서도 보지 못하는 것입니다: 그래프 서버만 15개 도구 / 24,508 바이트(약 6.1k 토큰)를 선언하고, 호스트가 온디맨드로 스키마를 가져오지 않는 한 모든 요청에 동승합니다. `tezgah-setup --mcp-schemas`가 이를 측정합니다 |
| 디스크 | 설치에 약 58 ms가 걸리며, tezgah가 다시 쓰는 모든 파일은 `<file>.tezgah-bak`으로 한 번 보관됩니다 |

**무장의 하한.** 불변식은 상시 켜짐입니다 - 실행 모드, ponytail, deliver-the-whole-ask, 무결성, 루프 규율, 교훈 원장, 그리고
출처 표기 금지 - 그 리고 안전 규칙("되돌릴 수 없거나 외부를 향하는 행위는 먼저 명시적인 요청이 필요하다")도 그중 하나이므로 결코 분류기에 의존하지 않습니다.
각 권고 규칙은 실행 가능한 한 줄 포인터를 상시 켜짐으로 유지하므로, 일치를 놓쳐도 잃는 것은 세부 사항일 뿐 규칙이 아니며, 실패한 호스트 훅은 계약 없음이
아니라 포인터와 온디맨드 스킬로 폴백합니다. 거짓 음성은 감사 가능합니다: 모든 프롬프트가 `armed=<rules|none> chars=<n>` - 프롬프트
텍스트는 없음 - 을 `~/.cache/tezgah/classify.log`에 추가하고(64 KB를 넘으면 마지막 200줄로 잘림), 다섯 훅 호스트 모두 같은
프롬프트에 대해 같은 세트를 무장합니다 (`tests/test_context.py::ArmingConformance`).

**opencode는 다르게 무장됩니다.** 프롬프트 시점 주입 지점이 없으므로 계약은 생성된 instructions 파일로 제공되고, 상시 켜짐 라우터는 코딩
세션이 손을 뻗는 버킷만 나열하여 나머지는 온디맨드로 읽히는 `~/.config/tezgah/opencode-skills.full.md`에 대한 포인터로 축약합니다;
`permission.skill = deny`는 opencode가 대신 모든 스킬의 메타데이터를 주입하는 것을 막습니다. `--install`은
`compaction.prune`과 `watcher.ignore`도 설정하여 오래된 도구 결과를 매 단계 다시 보내는 대신 프롬프트에서 지웁니다 - 이것이 없으면
opencode가 모델 한계(1M 토큰 모델의 경우 약 980k) 근처에서 자동 압축하기 전에 작업 세트가 수십만 토큰으로 커집니다.
`bin/tezgah-doctor`는 디스크 공간을 보고하고, `--prune-sessions DAYS`는 opencode CLI를 통해 유휴 세션을 삭제하며,
VACUUM만으로는 할 수 없는, 데이터베이스를 실제로 줄이는 유일한 작업입니다.

**왜 이득인가.** 실제 한 리포지토리에서 기본 `grep`은 관련 폴더를 무시하고 아무것도 찾지 못했습니다. 무시를 비활성화하자 3.95초가 걸렸고 여전히 정의와
호출 위치가 섞여 있었지만, 코드 그래프는 같은 질문에 16 ms 만에 답하여 8개의 진짜 호출 위치를 나열했습니다.

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
