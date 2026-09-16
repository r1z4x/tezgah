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

<h3 align="center">Jeden działający kontrakt dla każdego asystenta kodowania AI, którego uruchamiasz.</h3>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/github/license/r1z4x/tezgah?style=flat-square"></a>
  <a href="https://github.com/r1z4x/tezgah/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/r1z4x/tezgah/ci.yml?style=flat-square&label=ci"></a>
  <a href="https://github.com/r1z4x/tezgah/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/r1z4x/tezgah?style=flat-square"></a>
</p>

<p align="center">
  <a href="#what-it-enforces">Co egzekwuje</a> &bull;
  <a href="#supported-hosts">Obsługiwane hosty</a> &bull;
  <a href="#install">Instalacja</a> &bull;
  <a href="#day-to-day">Codzienne użytkowanie</a> &bull;
  <a href="#configuration">Konfiguracja</a> &bull;
  <a href="#cost">Koszty</a> &bull;
  <a href="#development">Rozwój</a> &bull;
  <a href="#contributing">Współpraca</a> &bull;
  <a href="#security">Bezpieczeństwo</a> &bull;
  <a href="#license">Licencja</a>
</p>

<p align="center"><sub>Język angielski jest głównym źródłem prawdy; tłumaczenia mogą być opóźnione.</sub></p>

---

Jeden działający kontrakt dla każdego asystenta kodowania AI, którego uruchamiasz — Claude Code,
opencode, Codex, Cursor i środowiska dsh od DeepSeek — w ramach skonfigurowanych
katalogów głównych repozytoriów.

Pozostawiony sam sobie, każdy asystent ma własne nawyki: jeden odpowiada po turecku, inny
po angielsku; jeden używa grepa do wszystkiego, inny odpytuje graf kodu; jeden mówi
„gotowe” bez uruchomienia testu. Tezgah eliminuje te rozbieżności. Otwórz dowolnego hosta, a
otrzymasz ten sam język, tę samą dyscyplinę i ten sam standard dowodowy.

Projekt składa się z dwóch warstw. Reguły istnieją w jednym, współdzielonym rdzeniu; każdy host otrzymuje
cienki adapter, który tłumaczy ten rdzeń na format zrozumiały dla hosta.
Zmień regułę w jednym miejscu, a wszystkie pięć hostów to zobaczy — bez pięciokrotnego kopiowania
tego samego tekstu.

<a id="what-it-enforces"></a>

## Co egzekwuje

- **Raportowanie po turecku zorientowane na wynik.** Każda odpowiedź jest w języku tureckim i zaczyna się
  od wyniku lub decyzji (BLUF), a następnie punktów uporządkowanych według wpływu. Kod, commity,
  dokumentacja i prompty subagentów pozostają w języku angielskim; nazwy, polecenia CLI i komunikaty
  o błędach nigdy nie są tłumaczone.
- **Minimalny kod (ponytail).** Najbardziej leniwa zmiana, która faktycznie działa: YAGNI,
  następnie ponowne użycie istniejącej funkcji pomocniczej, potem biblioteka standardowa (stdlib), natywna funkcja platformy,
  zainstalowana zależność, a na końcu jedna linijka. Żadnych nieproszonych abstrakcji.
  Walidacja, obsługa błędów i bezpieczeństwo nigdy nie są upraszczane.
- **Odkrywanie oparte w pierwszej kolejności na grafie kodu.** Pytania „gdzie jest X”, „kto wywołuje Y”, „co się zepsuje, jeśli
  Z się zmieni” trafiają do grafu `codebase-memory-mcp` (`search_graph`,
  `trace_path`, `search_code`), a nie do grepa. Grep pozostaje właściwym narzędziem dla dosłownego tekstu,
  konfiguracji i plików niebędących kodem.
- **Analiza aplikacji oparta w pierwszej kolejności na dostępności.** Działająca aplikacja internetowa lub mobilna jest odczytywana
  poprzez jej drzewo dostępności / DOM / natywne drzewo widoków, a nie zrzut ekranu na każdym kroku.
  `analyze-app` obejmuje przeglądarkę (Playwright MCP), symulator iOS lub emulator Androida (Mobile MCP)
  oraz opcjonalną diagnostykę webową (Chrome DevTools MCP); zrzut ekranu jest jawną,
  akcją na żądanie dla tego, na co drzewo nie potrafi odpowiedzieć.
- **Zewnętrzna druga opinia.** Przed podjęciem nietrywialnej lub trudnej do cofnięcia decyzji,
  `~/.config/tezgah/bin/consult` równolegle pyta niezależne modele przez OpenRouter (lub API DeepSeek
  z `--provider deepseek`), a agent raportuje, w czym były zgodne, a w czym nie.
- **Badania przez OpenResearch.** Gdy router uzna, że zadanie ma charakter badawczy —
  przegląd literatury, formułowanie i testowanie hipotez, przeprowadzanie eksperymentów,
  artefakt badawczy — kieruje pracą za pośrednictwem OpenResearch (`orx`) od alphaXiv
  i najpierw ładuje podręcznik `orx`, zamiast improwizować protokół. Zwykłe
  odkrywanie kodu pozostaje na grafie kodu. Gdy brakuje `orx`, router o tym informuje
  i przechodzi na subagenta hosta.
- **Uczciwość podczas weryfikacji.** Nic nie jest zgłaszane jako zrobione, przetestowane lub naprawione,
  dopóki nie zostanie zobaczony wynik. Nieudany test jest zgłaszany jako nieudany z jego
  dokładnym błędem, a pominięte sprawdzenie jest jasno komunikowane.
- **Brak przypisywania autorstwa AI, gdziekolwiek.** Nic, co jest utrwalane lub publikowane — wiadomości commitów,
  merge'y i tagów, teksty PR i zgłoszeń (issues), komentarze w kodzie, nagłówki plików, dokumentacja
  — nie może przypisywać zasług asystentowi, modelowi, dostawcy ani „AI”. Używanie narzędzia jest w porządku;
  podpisywanie jego nazwy pod twoją pracą już nie.
- **Dwupoziomowa orkiestracja.** Główny wątek decyduje i weryfikuje; tani
  model (`~/.config/tezgah/bin/codegen`, domyślnie OpenRouter lub `--provider deepseek`) szkicuje
  ograniczone, dobrze określone edycje do katalogu roboczego (scratch directory). Nic nie trafia do repozytorium
  inaczej niż przez router, a nieudany szkic automatycznie wraca do głównego modelu.
- **Subagenci per-repozytorium.** Na początku sesji repozytorium nadrzędne otrzymuje mały zestaw
  agentów z ograniczonymi uprawnieniami (`tezgah-explorer`, `tezgah-reviewer`,
  `tezgah-researcher`, `tezgah-verifier`) plus `tezgah-orchestrator`, renderowanych
  do natywnej powierzchni każdego zainstalowanego hosta (Claude/Cursor `.claude/agents/`,
  opencode `.opencode/agents/` plus wstrzyknięcie konfiguracji na żywo, Codex
  `.codex/agents/`) i ignorowanych za pomocą jednego zarządzanego bloku `.gitignore`. W Claude
  lista dozwolonych `Agent(tezgah-*)` orkiestratora działa tylko wtedy, gdy działa on jako
  główny wątek (`claude --agent tezgah-orchestrator`); jako subagent lista jest
  ignorowana. dsh nie ma powierzchni dla poszczególnych ról, więc obejmuje go reguła routera kontraktu.

<a id="supported-hosts"></a>

## Obsługiwane hosty

| Host | Podłączony przez | Linia statusu |
|---|---|---|
| **Claude Code** | lokalny rynek wtyczek (plugin marketplace): hooki, polecenia, dwóch agentów tylko do odczytu, styl wyjściowy | natywna `statusLine` |
| **opencode** | wtyczka + instrukcje + MCP + wygenerowany router umiejętności (natywna lista umiejętności odrzucona), auto-indeksowanie repozytorium przy pierwszej wiadomości | wtyczka TUI (brak polecenia statusLine) |
| **Codex** | `hooks.json` + umiejętności + MCP, w tym bramka `PreToolUse` | hook `systemMessage` (lista elementów stopki jest zamknięta) |
| **Cursor** | `hooks.json` + umiejętności + MCP | `statusLine` w `cli-config.json` |
| **dsh** | mostek hooków Claude Code + zarządzany blok łatek (hooki, MCP, trasy LLM, linia statusu Web poza drzewem) | wtyczka Web UI: `tezgah-dsh-statusline` w nagłówku sesji |

Bramka Codex przepuszcza Bash, `exec_command`, `apply_patch`, Edit/Write, narzędzia MCP,
i wywołania subagentów przez to samo sprawdzenie co inne hosty. W Claude, zakaz
przypisywania autorstwa jest również egzekwowany mechanicznie: ustawienie `attribution` jest
opróżniane (`commit`, `pr`, `sessionUrl`), więc podziękowania w commitach i PR są wyłączone u źródła.

### Linia statusu

Każdy host renderuje tę samą jednowierszową listę kontrolną z `tezgah-status`, więc
nie mogą się one rozbiegać. Stan jest kluczowy: znacznik jest **zielony**, gdy reguła jest uzbrojona
i obowiązuje w tej sesji, **żółty**, gdy jest uzbrojona, ale na żądanie (jeszcze nieużyta),
i **czerwony**, gdy wyłącznik awaryjny (kill switch) ją wyłączył. `idx` osobno raportuje gotowość grafu
(`✓` zindeksowany, `↻` nieaktualny, `✗` niezindeksowany, `–` nie dotyczy), a
`plans N (M blk)` otwarte plany. `tezgah-status --legend` wypisuje legendę,
`--json` podaje te same segmenty dla interfejsu użytkownika, a `--no-color` (lub `NO_COLOR`)
wymusza zwykły tekst. Claude Code i Cursor kolorują natywną linię statusu;
TUI opencode koloruje własny komponent i odświeża się na szynie zdarzeń hosta;
Web UI dsh koloruje swój komponent nagłówka i odświeża się tylko wtedy, gdy jego karta
jest widoczna; Codex pokazuje zwykły ciąg znaków w `systemMessage`.

dsh uruchamia te same pliki hooków Claude przez swój mostek `dsh-hooks-claude-code`,
więc kontrakt startu sesji, bramka atrybucji i zachęta do pierwszego grepa mają tam zastosowanie.
dsh udostępnia pojedyncze narzędzie `subagent`, więc odmowa dla eksploratora używającego tylko grepa
jest nieaktywna — nie ma subagenta eksploratora, któremu można by odmówić. Domyślna
piaskownica (sandbox) `workspace-write` w dsh ogranicza podprocesy hooków do obszaru roboczego
i katalogu tymczasowego platformy, więc tezgah zapisuje swój stan hooka (znaczniki zachęty, stempel indeksu) do
zapisywalnego rozwiązania awaryjnego w tym miejscu, zamiast kończyć się błędem z powodu odmowy zapisu. Worker
indeksu grafu nie może zapisać pamięci podręcznej `codebase-memory-mcp` z wnętrza tej piaskownicy, więc
launcher `dsh` rozgrzewa indeks w nieograniczonej powłoce użytkownika przed uruchomieniem
dsh — nowe repozytorium jest indeksowane dokładnie tak samo jak na innych hostach, z oznaczeniem HEAD.
Sesja uruchomiona bez launchera nadal otrzymuje jasny raport, że
serwer MCP bez piaskownicy obsługuje graf i potrzebuje `index_repository` dla repozytorium,
którego nie zindeksował, zamiast surowego błędu `EPERM`. Zarządzany
blok łatek deklaruje również dwie trasy LLM kompatybilne z OpenAI na adapterze pi-ai,
który montuje bazowa kompozycja: `openrouter` (`OPENROUTER_API_KEY`) i `deepseek`
(`DEEPSEEK_API_KEY`), możliwe do wyboru obok natywnego domyślnego `deepseek-official`.
Klucze są rozwiązywane ze środowiska uruchomieniowego lub magazynu poświadczeń środowiska;
żaden klucz nie trafia do pliku konfiguracyjnego. tezgah-setup umieszcza również launcher `dsh`
w PATH (`~/.local/bin/dsh`), który znajduje zainstalowane CLI pod
`$DSH_HOME`, więc `dsh --profile web` działa z dowolnego katalogu.

dsh nie ma linii statusu poleceń, więc tezgah dostarcza ją jako wtyczkę Web UI:
`tezgah-dsh-statusline`. Jej część hosta serwuje ciąg `tezgah-status` dla
obszaru roboczego sesji przez uwierzytelnioną trasę `/api/tezgah.status` (z
`?format=json` dla widoku kolorowego); jej część przeglądarkowa renderuje ją w nagłówku sesji,
pokolorowaną według stanu z legendą po najechaniu/kliknięciu, i odświeża się tylko wtedy, gdy
karta jest widoczna. `tezgah-setup`
linkuje wtyczkę do profilu webowego i włącza ją za pomocą zarządzanego wiersza w
`profiles/web/cordis.patch.yml` (tylko dla web, ponieważ część hosta wstrzykuje usługę
`connection` dostępną tylko dla web); profil, który nigdy nie uruchomił `web`, jest pomijany
z podpowiedzią zamiast być w połowie zapisany. W trybie `headless`, mostek hooków wstrzykuje
kontrakt SessionStart jako własną końcową turę (jego `agent/session-start`
wywołuje `agent.inject()` w trybie odłączonym, po tym jak jednorazowe zadanie jest już pierwszą wiadomością),
więc `dsh --profile headless "<task>"` zużywa jedną dodatkową turę i, dla
promptu wymagającego dosłownej odpowiedzi, wypisuje reakcję modelu na kontrakt zamiast
odpowiedzi na zadanie; interaktywne sesje webowe pozostają nienaruszone.

`bin/tezgah-setup --install` uruchamia również `orx install-skills` dla Claude,
Codex, opencode i Cursor, gdy `orx` znajduje się w PATH, dzięki czemu reguła badawcza ma
podręcznik do załadowania. Pliki shim należą do orx, więc tezgah uruchamia tylko ten instalator
i nigdy nie wymienia ich do odinstalowania. dsh nie ma środowiska orx; reguła badawcza
w tym przypadku przechodzi na `orx skill` w powłoce.

Wtyczka Claude dostarcza również dwóch agentów tylko do odczytu. `agents/tezgah-explorer.md`
zajmuje się odkrywaniem kodu z grafu i zwraca dowody w postaci `file:line`;
`agents/tezgah-reviewer.md` zamienia diff na jego zestaw wpływu za pomocą
`detect_changes`, a następnie szuka rzeczywistych defektów. Obaj mają wyłączone narzędzia zapisu i poleceń;
ich dane wyjściowe mają charakter doradczy.

### Analiza aplikacji

`analyze-app` steruje działającą aplikacją na podstawie jej drzewa dostępności.
Domyślna pętla to: otwórz, odczytaj drzewo, działaj, obserwuj konsolę/sieć/logi,
i ponownie odczytaj drzewo — zrzut ekranu to jawna akcja dla tego, na co drzewo nie
potrafi odpowiedzieć (canvas, gra, animacja, regresja wizualna na poziomie pikseli). Umiejętność to
jedna ścieżka dla wszystkich hostów; serwery pod nią to jedna współdzielona specyfikacja w
`hooks/tezgah_apps.py`:

| Serwer | Cel | Podłączony przez |
|---|---|---|
| `playwright` (`@playwright/mcp`) | strony internetowe, narzędzia `browser_*` | opencode, Codex, Cursor, Claude (wtyczka `.mcp.json`) |
| `mobile-mcp` (`@mobilenext/mobile-mcp`) | Symulator iOS / emulator Androida, narzędzia `mobile_*` | to samo |
| `chrome-devtools` (opcjonalnie, `--devtools`) | ślady wydajności webowej, głęboka sieć, konsola z mapowaniem źródeł | to samo |

Przeglądarka domyślnie uruchamia **izolowany** profil, więc uruchomienie nigdy nie narusza
twojego rzeczywistego stanu Chrome; analizowanie przepływu po zalogowaniu to celowe podłączenie
(`--cdp-endpoint` lub rozszerzenie Playwright), a nie domyślne zachowanie.
Zrzuty ekranu, ślady i zrzuty drzewa lądują w `~/.cache/tezgah/apps` (można nadpisać za pomocą
`TEZGAH_ARTIFACTS`), a agent otrzymuje z powrotem ścieżkę, nigdy bajty obrazu w linii (inline).
Serwery działają przez `npx`, więc potrzebują node, ale nie wymagają własnej instalacji;
`tezgah-setup --install --devtools` dodaje opcjonalny serwer diagnostyki webowej.
dsh podłącza te same dwa serwery przez swój mostek `dsh-mcp-client`
(`serverName` / `command` / `args` / `env`, potwierdzone ze schematem opublikowanej
konfiguracji), a Claude pobiera je z pliku `.mcp.json` wtyczki
(`claude plugin details tezgah` wyświetla serwery MCP 2 i oba się łączą).
`mobile-mcp` to połowa o wyższym stopniu trudności: macOS może poprosić o uprawnienia do Dostępności /
Nagrywania ekranu, a drzewo widoków może zostać przerwane pod obciążeniem, więc umiejętność
ponawia próbę pobrania drzewa przed przejściem na zrzut ekranu.

CI uruchamia deterministyczny handshake dla obu serwerów (bez przeglądarki, bez urządzenia):
`TEZGAH_E2E_STRICT=1 python3 tests/e2e_analyze_wiring.py`. Dwa opcjonalne lokalne
testy dymne (smoke tests) idą dalej: `TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_web.py` uruchamia
Playwright MCP, nawiguje i odczytuje migawkę bez zrzutu ekranu;
`TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_mobile.py` uruchamia Mobile MCP, sprawdza
narzędzia drzewa widoków i wyświetla listę urządzeń. Wypisują one `SKIP: ...`, gdy brakuje node,
kompilacji przeglądarki lub urządzenia.

<a id="install"></a>

## Instalacja

Wymaga Pythona 3.8+. node + npm są potrzebne dla hosta dsh oraz, wraz z `pnpm`,
dla jego webowej linii statusu. Opcjonalne integracje degradują się z gracją:
`codebase-memory-mcp` w PATH zasila graf; klucz modelu zasila `consult`
i `codegen` — domyślnie OpenRouter (`OPENROUTER_API_KEY` lub
`~/.config/openrouter/key`), lub API DeepSeek z `--provider deepseek`
(`DEEPSEEK_API_KEY` lub `~/.config/deepseek/key`); a `orx` od OpenResearch
w PATH daje regule badawczej coś do sterowania. Gdy brakuje klucza wybranego
dostawcy, tezgah o tym informuje, zamiast udawać.

Sklonuj, a następnie uzbrój każdy wykryty host w jednym przebiegu:

```bash
git clone https://github.com/r1z4x/tezgah.git ~/Projects/tezgah
cd ~/Projects/tezgah
bin/tezgah-setup --install
```

`--install` instaluje również brakujące opcjonalne narzędzia, uruchamiając
własny instalator każdego dostawcy **przez sieć**: `orx`
(`openresearch.sh/install.sh`), `cursor-agent` (`cursor.com/install`), `dsh`
(jego profil domowy przez `npx`) oraz `pnpm`, gdy dsh go potrzebuje (przez `npm`) —
włączając w to `curl ... | sh`. Żadne z nich nie wymaga sudo; przebieg jest zapisywany w
`~/.config/tezgah/install.log`. Podgląd za pomocą `--dry-run`, pominięcie za pomocą
`--no-deps` (przydatne w CI) lub instalacja samych narzędzi za pomocą `--deps`. Narzędzia lądują
w `~/.local/bin` lub `~/.cargo/bin`, więc przed ich pojawieniem się w PATH może być potrzebna nowa powłoka;
własne testy tezgah i tak sprawdzają te katalogi, więc nieinteraktywna
powłoka nadal zgłasza ich obecność.

Jeśli poprzednia konfiguracja jest już obecna, zaimportuj ją najpierw — zostanie ona przeniesiona na bok,
a nie usunięta:

```bash
bin/tezgah-setup --adopt
```

Claude Code instaluje się przez własny kanał wtyczek:

```bash
claude plugin marketplace add ~/Projects/tezgah
claude plugin install tezgah@rizacan-local
```

W razie potrzeby wyraźnie ogranicz instalację:

```bash
bin/tezgah-setup --install --hosts claude,codex,opencode,cursor,dsh
bin/tezgah-setup --roots ~/work:~/oss --install
```

<a id="day-to-day"></a>

## Codzienne użytkowanie

Nie ma nic do uruchamiania: reguły ładują się podczas startu hosta. Warto znać kilka poleceń:

| Polecenie | Cel |
|---|---|
| `bin/tezgah-setup` | Raportuje, co jest uzbrojone, dla każdego hosta |
| `bin/tezgah-status [PATH]` | Pokazuje, czy reguły są aktywne w danym repozytorium |
| `bin/tezgah-setup --status [PATH]` | Wypisuje listę kontrolną uzbrojonych/używanych reguł |
| `bin/tezgah-setup --deps [--dry-run]` | Instaluje brakujące opcjonalne narzędzia (orx, cursor-agent, dsh) |
| `bin/tezgah-doctor [--clean] [--prune-sessions DAYS]` | Raportuje zużycie dysku przez środowisko; `--clean` usuwa stare logi indeksu i czyści (vacuum) bazę danych opencode; `--prune-sessions` usuwa bezczynne sesje (jedyna akcja, która faktycznie zmniejsza bazę danych) |
| `/plan-add` | Zmienia fragment pracy w śledzony plan |
| `/plan-status` | Podsumowuje otwarte plany i wybiera następny |
| `/plan-sync` | Zamyka ukończone plany |
| `bin/tezgah-setup --version` | Wypisuje wersję wtyczki |
| `bin/tezgah-setup --uninstall` | Usuwa tylko dowiązania symboliczne tezgah, wpisy hooków hosta i zarządzany blok dsh |

<a id="configuration"></a>

## Konfiguracja

Tezgah jest uzbrojony tylko w ramach skonfigurowanych katalogów głównych; wszędzie indziej pozostaje bezgłośny.

- Domyślny katalog główny: `~/Projects`.
- `~/.config/tezgah/config.json`: `{"roots": ["~/Projects", "~/work"]}`.
- `TEZGAH_ROOTS` (lista oddzielona separatorami ścieżek) nadpisuje plik dla jednorazowych uruchomień i CI.

Wyłączniki awaryjne (kill switches) znajdują się w `~/.config/tezgah/`. Każdy z nich usuwa swoją regułę z
tekstu wstrzykiwanego do sesji, więc reguła faktycznie przestaje działać:

| Wyłącznik | Wyłącza |
|---|---|
| `exec-mode.off` | raportowanie po turecku zorientowane na wynik |
| `ponytail-auto.off` | regułę minimalnego kodu |
| `spec-off` | regułę specyfikacji przed budowaniem |
| `consult-off` | regułę zewnętrznej drugiej opinii |
| `research-off` | kierowanie zadań badawczych do OpenResearch |
| `orchestrate-off` | delegowanie do subagentów (dodaje linię zakazującą delegowania) |
| `reminder-off` | tekst przypomnienia na każdą turę |
| `pretooluse-off` | samą bramkę PreToolUse (atrybucja, eksplorator, zachęta do grepa) |

Dla każdego repozytorium, `.no-ponytail`, `.no-cbm` i `.no-lessons` wyłączają odpowiednio: regułę minimalnego kodu,
regułę grafu kodu (i jego auto-indeksowanie) oraz rejestr lekcji.

Gdy użytkownik zgłosi błąd, agent dopisuje jednowierszową lekcję do pliku repozytorium
`.tezgah/lessons.md`; najnowsze linie są wstrzykiwane na początku sesji, aby
ten sam błąd nie mógł się po cichu powtórzyć.

<a id="cost"></a>

## Koszty

Zmierzone na tej maszynie (macOS, Python 3.10), a nie oszacowane:

- **Kontekst.** Start sesji wstrzykuje ~4,8 KB (~1,2 tys. tokenów) tekstu kontraktu.
  W Codex przypomnienie o rozmiarze 480 bajtów towarzyszy każdej turze; Claude i inne hosty
  nie mają hooka na turę, więc ich koszt na turę wynosi zero. Pełna umiejętność `tezgah-contract`
  (~19,9 tys. znaków) jest opłacana tylko wtedy, gdy zadanie ją załaduje. W opencode
  kontrakt jest dostarczany jako plik instrukcji o rozmiarze ~5,5 KB. opencode w przeciwnym razie
  wstrzyknąłby ~53 KB tekstu z nazwą/opisem/lokalizacją umiejętności do systemowego promptu każdej sesji;
  tezgah odrzuca tę listę (`permission.skill = deny`) i dostarcza w zamian
  wygenerowany router umiejętności o rozmiarze ~16 KB, więc umiejętność jest znajdowana poprzez odczytanie jej
  ścieżki `SKILL.md` z routera.
- **Opóźnienie.** Hooki to oddzielne procesy Pythona, więc dominuje start interpretera
  zajmujący ~19 ms. Oprócz tego start sesji dodaje ~25 ms, wywołanie narzędzia z bramką
  (Bash/Grep/Task) dodaje ~9 ms, a segment Stop w Codex dodaje ~15 ms na turę.
- **Dysk.** Instalacja zajmuje ~58 ms, a każdy plik, który tezgah nadpisuje, jest zachowywany
  jednorazowo jako `<file>.tezgah-bak`.

Zwrot z inwestycji pojawia się przy pytaniach wywołującego. W jednym z rzeczywistych repozytoriów domyślny `grep`
zignorował odpowiedni folder i nic nie znalazł; z wyłączonym ignorowaniem zajęło to
3,95 s i nadal mieszało definicje z miejscami wywołań. Graf kodu odpowiedział na
to samo pytanie w 16 ms, wymieniając tylko 8 prawdziwych miejsc wywołań.

opencode jest również uzbrojony w higienę kontekstu dla długich sesji: `tezgah-setup --install`
ustawia `compaction.prune`, dzięki czemu stare wyniki narzędzi są usuwane z promptu
zamiast być ponownie wysyłane na każdym kroku, a lista `watcher.ignore` trzyma obserwatora plików (file watcher)
z dala od `.git`, `node_modules` i katalogów kompilacji. Oba się łączą — jawna wartość użytkownika
wygrywa. Ma to znaczenie, ponieważ opencode automatycznie kompaktuje tylko w pobliżu limitu kontekstu modelu
(dla modelu 1M tokenów, około 980k), więc bez przycinania zestaw roboczy
rośnie do setek tysięcy tokenów. `bin/tezgah-doctor` raportuje wynikowy ślad na dysku;
`--prune-sessions DAYS` usuwa bezczynne sesje przez CLI opencode, co jest jedyną akcją,
która faktycznie zmniejsza bazę danych — samo VACUUM nie może tego zrobić, ponieważ wszystkie jego strony są aktywne.

<a id="development"></a>

## Rozwój

```bash
python3 -m unittest discover -s tests -v   # stdlib test suite
pip install -r requirements-dev.txt        # pinned ruff, the only dev dep
ruff check .                               # lint (config in pyproject.toml)
```

CI działa zarówno na Pythonie 3.10, jak i 3.12. Aby odświeżyć zainstalowaną kopię Claude
z tego checkoutu, użyj `bin/tezgah-setup --sync` i zweryfikuj manifest za pomocą
`claude plugin validate .claude-plugin/plugin.json`. Podczas podnoszenia wersji zaktualizuj
razem `.claude-plugin/plugin.json` i `.claude-plugin/marketplace.json` — muszą być ze sobą zgodne.

`codebase-memory-mcp` jest instalowany przez użytkownika. Hooki i pliki Orca nie są
częścią tego projektu i pozostają nietknięte. Claude otrzymuje zawsze włączony rdzeń
z hooka SessionStart; `output-styles/tezgah.md` to duplikat dla kompilacji,
które ładują style wyjściowe wtyczek, więc hook jest autorytatywną ścieżką.

<a id="contributing"></a>

## Współpraca

Małe, jednocelowe zmiany są najłatwiejsze do zaakceptowania. Reguła należy do
współdzielonego rdzenia (`hooks/`), chyba że jest autentycznie specyficzna dla hosta; różnica dla hosta
należy do jego adaptera w `hosts/<name>/`. Utrzymuj diff tak krótki, jak to możliwe,
zachowując przy tym poprawność — własna reguła minimalnego kodu projektu ma zastosowanie do samego projektu.

Przed otwarciem pull requesta uruchom te same trzy testy, które uruchamia CI:

```bash
python3 -m compileall -q hooks hosts bin statusline.py   # byte-compile every script
python3 -m unittest discover -s tests                     # stdlib test suite
ruff check .                                              # lint; config in pyproject.toml
```

`ruff` pochodzi z `requirements-dev.txt` (`pip install -r requirements-dev.txt`),
co jest jedyną zależnością deweloperską.

<a id="security"></a>

## Bezpieczeństwo

Zgłaszaj luki w zabezpieczeniach prywatnie przez biuletyny bezpieczeństwa GitHub
(karta **Security** → **Report a vulnerability**), a nie jako publiczne zgłoszenie (issue).

tezgah uruchamia hooki powłoki, zapisuje konfigurację hosta i wstrzykuje tekst do każdej
sesji, więc wszystko, co sprawia, że hook wykonuje kod kontrolowany przez atakującego, wycieka
klucz do pliku konfiguracyjnego, rozszerza piaskownicę lub pozwala zawartości repozytorium na
eskalację do tekstu instrukcji, jest w zakresie. Dołącz hosta, wersję tezgah
(`bin/tezgah-setup --version`) oraz minimalną reprodukcję.

<a id="license"></a>

## Licencja

Główny plik `LICENSE` (MIT) obejmuje własne pliki tezgah. `skills/ponytail` i
`skills/no-ai-slop` są dostarczane (vendored) na ich własnych warunkach MIT, zapisanych w pliku
`NOTICE`.
