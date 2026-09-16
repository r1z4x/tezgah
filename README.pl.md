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
  <a href="#benchmark">Benchmark</a> &bull;
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

| Host | Podłączony przez |
|---|---|
| **omp** (oh-my-pi) — główny | `~/.omp/agent`: zarządzany blok zawsze włączony `RULES.md`, umiejętności, wygenerowani subagenci, `mcp.json`, oraz rozszerzenie (`hooks/pre/tezgah-hook.ts`), które uzbraja reguły na poziomie promptu, bramkuje narzędzia, zapisuje dowody i uruchamia regułę Stop; połączenie jest sprawdzane przez `tezgah-setup` |
| **Claude Code** | lokalny rynek wtyczek (plugin marketplace): hooki, polecenia, dwóch agentów tylko do odczytu, styl wyjściowy |
| **opencode** | wtyczka + instrukcje + MCP + wygenerowany router umiejętności (natywna lista umiejętności odrzucona), auto-indeksowanie repozytorium przy pierwszej wiadomości |
| **Codex** | `hooks.json` + umiejętności + MCP, w tym bramka `PreToolUse` |
| **Cursor** | `hooks.json` + umiejętności + MCP |
| **dsh** | mostek hooków Claude Code + zarządzany blok łatek (hooki, MCP, trasy LLM, linia statusu Web poza drzewem) |

Bramka Codex przepuszcza Bash, `exec_command`, `apply_patch`, Edit/Write, narzędzia MCP,
i wywołania subagentów przez to samo sprawdzenie co inne hosty. W Claude, zakaz
przypisywania autorstwa jest również egzekwowany mechanicznie: ustawienie `attribution` jest
opróżniane (`commit`, `pr`, `sessionUrl`), więc podziękowania w commitach i PR są wyłączone u źródła.

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

W terminalu to polecenie bez argumentów jest zamiast tego kreatorem instalacji: pyta, które
hosty uzbroić, o katalogi główne, czy zainstalować brakujące opcjonalne narzędzia i czy
podłączyć opcjonalny DevTools MCP, wypisuje plan i zapisuje dopiero po potwierdzeniu. Flagi
są wartościami domyślnymi kreatora, więc `--wizard --hosts omp` pyta tylko o resztę.
Uruchomienie przez potok, przez agenta lub w CI nigdy nie dostaje pytania — wypisuje raport,
dokładnie tak jak wcześniej.

`--install` instaluje również brakujące opcjonalne narzędzia, uruchamiając własny instalator
każdego dostawcy **przez sieć**: `orx` (`openresearch.sh/install.sh`), `cursor-agent`
(`cursor.com/install`), `dsh` (jego profil domowy przez `npx`) oraz `pnpm`, gdy dsh go
potrzebuje (przez `npm`) — włączając w to `curl ... | sh`. Żadne z nich nie wymaga sudo;
przebieg jest zapisywany w `~/.config/tezgah/install.log`. Podgląd za pomocą `--dry-run`,
pominięcie za pomocą `--no-deps` (przydatne w CI) lub instalacja samych narzędzi za pomocą
`--deps`. Narzędzia lądują w `~/.local/bin` lub `~/.cargo/bin`, więc przed ich pojawieniem
się w PATH może być potrzebna nowa powłoka; własne testy tezgah i tak sprawdzają te
katalogi, więc nieinteraktywna
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
bin/tezgah-setup --install --hosts omp
bin/tezgah-setup --install --hosts claude,codex,cursor,opencode,dsh
bin/tezgah-setup --roots ~/work:~/oss --install
```

<a id="day-to-day"></a>

## Codzienne użytkowanie

Nie ma nic do uruchamiania: reguły ładują się podczas startu hosta. Warto znać kilka poleceń:

| Polecenie | Cel |
|---|---|
| `bin/tezgah-setup` | W terminalu: kreator instalacji; w potoku lub w CI: raportuje, co jest uzbrojone, dla każdego hosta |
| `bin/tezgah-setup --wizard` | Wymusza kreatora instalacji wszędzie; `--report` wymusza raport |
| `bin/tezgah-status [PATH]` | Pokazuje, czy reguły są aktywne w danym repozytorium |
| `bin/tezgah-setup --status [PATH]` | Wypisuje listę kontrolną uzbrojonych/używanych reguł |
| `bin/tezgah-setup --deps [--dry-run]` | Instaluje brakujące opcjonalne narzędzia (orx, cursor-agent, dsh) |
| `bin/tezgah-research init\|check\|status` | Tworzy i sprawdza linię badawczą: stan, ustalenia, twierdzenia i reguła protokół-przed-wynikami |
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

<a id="benchmark"></a>

## Benchmark

Czy ten kontrakt poprawia pracę, czy tylko sprawia takie wrażenie? To jest mierzone w
`benchmarks/arm-bench/`, a nie twierdzone: ukryte kontrole, których testu agent nigdy nie
widzi, koszt z własnego rejestru użycia hosta, a edycje poboczne punktowane jako porażki.
`PREREGISTRATION.md` ustala punkty końcowe przed uruchomieniem, a `python3 bench.py report`
je wypisuje; pełne badanie, wraz z identyfikatorami uruchomień, to
`docs/research/2026-09-16-tezgah-quality.md`. Każda liczba poniżej to dziennik uruchomienia.

| Blok | Uruchomienia | Co ustalił |
|---|---|---|
| dwa hosty, 28 zadań, k=3 | 336 | `omp+tezgah` 0.95 i `opencode+tezgah` 0.96 mają nakładające się przedziały i ten sam koszt na rozwiązane zadanie; na gołych ramionach omp jest tańszy ($0.0047 wobec $0.0074 CPS), więc codziennym narzędziem jest omp, bez kosztu w jakości |
| rodzina trudna, 5 zadań, k=5, dwie rodziny modeli | 200 | łącznie trzy z czterech ramion lądują na 40/50: brak efektu harnessu przy tej wielkości, a jedyny sygnał wygenerowany przez pierwszy model odwrócił się przy drugim |
| rodzina bramki, bramka uzbrojona | 36 | żadne ramię nie wybrało drogi na skróty; mechanizm bramki jest zweryfikowany bezpośrednio (edycja skip zostaje odrzucona), jej wpływ na pracę nie jest jeszcze zmierzony |
| ablacja klauzul, dwie reguły, które dzielą, k=8 | 160 | ramiona z kontraktem przechodzą 23/32 (0.72) wobec 12/32 (0.38) gołej kotwicy |

**Pomaga dokładnie tam, gdzie domyślne zachowanie modelu jest błędne.** `c04` (angielski
prompt, w którym tylko kontrakt czyni odpowiedź turecką) czyta 9/16 z kontraktem i 0/16 bez;
`h02` (kontrakt pieniężny, którego widoczny zestaw testów jest zielony tak czy inaczej)
czyta 14/16 wobec 12/16. Tam, gdzie nie ma luki do zamknięcia - 22 z 25 zadań pilotażowych
przeszły pod każdym ramieniem przy każdej powtórce - benchmark może zaraportować jedynie
null.

**Niosą go dwie klauzule.** Usunięcie klauzuli 1 sprowadza `c04` do 0/8, wyniku samej gołej
kotwicy, ledwie ruszając `h02`. Usunięcie klauzuli 3 sprowadza `h02` do 2/8 - poniżej 6/8
gołej kotwicy - ponieważ klauzula 3 zabrania zatrzymywania się na najkrótszej pozornie
gotowej ścieżce, a w tym zadaniu najkrótszą ścieżką jest jednolinijkowiec, który przechodzi
widoczny zestaw testów, łamiąc udokumentowaną regułę. Klauzule 2 i 4 nie ruszają niczego
mierzalnego.

**Koszt idzie za jakością.** Na rozwiązane zadanie: $0.0078 wobec $0.0097 na węźle pełnego
kontraktu, $0.0043 wobec $0.0087 na węźle bez ponytail. Ramiona z kontraktem rozwiązują
więcej zadań, więc każde rozwiązane zadanie kosztuje mniej; całkowity wydatek jest wyższy, a
benchmark rejestruje go wiersz po wierszu, zamiast go kompensować.

Czego to nie pokazuje: jakości kodu, nakładu na przegląd ani utrzymywalności - nic z tego
nie jest tu mierzone; wpływu bramki na wybory ramienia, bo żadne ramię nie sięgnęło po skrót
w 36 uzbrojonych uruchomieniach; ani *kolejności* klauzul - `k=8` ustala kierunek, przy 8
uruchomieniach na komórkę. Jeden dostawca i jeden pakiet fixtures przez cały czas, a rundy
ablacji działają na jednej rodzinie modeli. Druga rodzina modeli odtwarza null dla 28 zadań
dokładnie (51/56 wobec 51/56), co pokazuje, że pierwszy odczyt nie był artefaktem modelu.

<a id="cost"></a>

## Koszty

Zmierzone na tej maszynie (macOS, Python 3.10), a nie oszacowane. `tezgah-setup` wypisuje
bieżący budżet - czytaj go tam, zamiast ufać liczbie skopiowanej tutaj, co sprawiło, że
wcześniejsza wersja podawała pasmo rdzenia mniejsze od tego, które faktycznie instaluje.

| Pasmo | Ile kosztuje |
|---|---|
| Start sesji | kontrakt zawsze włączony (niezmienniki plus jednolinijkowy wskaźnik na każdą regułę na żądanie): na tej maszynie i w tym zestawie umiejętności ~1.3k tokenów tekstu kontraktu i ~1.3k metadanych umiejętności, przy czym reguły warunkowe (spec, consult, research, graph) dodają ~0.6k tylko w turze, której prompt pasuje |
| Na turę | krótkie przypomnienie (~0.2k tokenów) plus uzbrojona reguła, gdy pasuje; hooki to osobne procesy Pythona, więc dominuje start interpretera ~19 ms - start sesji dodaje ~25 ms, wywołanie narzędzia z bramką (Bash/Grep/Task) ~9 ms. opencode nie ma hooka w momencie promptu, więc płaci zero |
| Na żądanie | pełna umiejętność `tezgah-contract` (~6.0k tokenów), opłacana tylko wtedy, gdy zadanie ją załaduje |
| Schematy MCP | największe pasmo i to, którego nie widzi żaden statyczny raport: sam serwer grafu deklaruje 15 narzędzi / 24,508 bajtów (~6.1k tokenów), jadąc przy każdym żądaniu, chyba że host pobiera schematy na żądanie. `tezgah-setup --mcp-schemas` to mierzy |
| Dysk | instalacja zajmuje ~58 ms, a każdy plik, który tezgah nadpisuje, jest zachowywany jednorazowo jako `<file>.tezgah-bak` |

**Podłoga uzbrojenia.** Niezmienniki są zawsze włączone - tryb wykonania, ponytail,
deliver-the-whole-ask, integralność, dyscyplina pętli, rejestr lekcji i zakaz przypisywania
autorstwa - a reguła bezpieczeństwa („działania nieodwracalne lub skierowane na zewnątrz
wymagają najpierw wyraźnej prośby”) jest jedną z nich, więc nigdy nie zależy od
klasyfikatora. Każda reguła doradcza utrzymuje zawsze włączony jednolinijkowy, wykonalny
wskaźnik, więc pominięte dopasowanie kosztuje szczegół, nigdy samą regułę, a hook hosta,
który zawiedzie, cofa się do wskaźników plus umiejętności na żądanie, a nie do braku
kontraktu. Fałszywe negatywy są audytowalne: każdy prompt dopisuje `armed=<rules|none>
chars=<n>` - bez tekstu promptu - do `~/.cache/tezgah/classify.log` (przycinanego do
ostatnich 200 wierszy powyżej 64 KB), a wszystkie pięć hostów z hookami uzbraja ten sam
zestaw dla tego samego promptu (`tests/test_context.py::ArmingConformance`).

**opencode jest uzbrojony inaczej.** Nie ma punktu wstrzykiwania w momencie promptu, więc
kontrakt jest dostarczany jako wygenerowany plik instrukcji, a jego zawsze włączony router
wymienia tylko kubełki, po które sięga sesja kodowania, sprowadzając resztę do wskaźnika na
`~/.config/tezgah/opencode-skills.full.md` czytanego na żądanie; `permission.skill = deny`
powstrzymuje opencode przed wstrzykiwaniem zamiast tego metadanych każdej umiejętności.
`--install` ustawia też `compaction.prune` i `watcher.ignore`, usuwając stare wyniki
narzędzi z promptu zamiast wysyłać je ponownie na każdym kroku - bez tego zestaw roboczy
rośnie do setek tysięcy tokenów, zanim opencode automatycznie skompaktuje się blisko limitu
modelu (około 980k dla modelu 1M tokenów). `bin/tezgah-doctor` raportuje ślad na dysku, a
`--prune-sessions DAYS` usuwa bezczynne sesje przez CLI opencode - jedyna akcja, która
faktycznie zmniejsza bazę danych, bo samo VACUUM tego nie potrafi.

**Dlaczego się opłaca.** W jednym rzeczywistym repozytorium domyślny `grep` zignorował
odpowiedni folder i nic nie znalazł; z wyłączonym ignorowaniem zajęło to 3.95 s i nadal
mieszało definicje z miejscami wywołań, podczas gdy graf kodu odpowiedział na to samo
pytanie w 16 ms, podając 8 prawdziwych miejsc wywołań.

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
