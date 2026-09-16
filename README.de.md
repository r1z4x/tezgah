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

<h3 align="center">Ein funktionierender Vertrag für jeden KI-Programmierassistenten, den Sie ausführen.</h3>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/github/license/r1z4x/tezgah?style=flat-square"></a>
  <a href="https://github.com/r1z4x/tezgah/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/r1z4x/tezgah/ci.yml?style=flat-square&label=ci"></a>
  <a href="https://github.com/r1z4x/tezgah/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/r1z4x/tezgah?style=flat-square"></a>
</p>

<p align="center">
  <a href="#what-it-enforces">Was es durchsetzt</a> &bull;
  <a href="#supported-hosts">Unterstützte Hosts</a> &bull;
  <a href="#install">Installation</a> &bull;
  <a href="#day-to-day">Alltag</a> &bull;
  <a href="#configuration">Konfiguration</a> &bull;
  <a href="#benchmark">Benchmark</a> &bull;
  <a href="#cost">Kosten</a> &bull;
  <a href="#development">Entwicklung</a> &bull;
  <a href="#contributing">Mitwirken</a> &bull;
  <a href="#security">Sicherheit</a> &bull;
  <a href="#license">Lizenz</a>
</p>

<p align="center"><sub>Englisch ist die maßgebliche Quelle; Übersetzungen können hinterherhinken.</sub></p>

---

Ein funktionierender Vertrag für jeden KI-Programmierassistenten, den Sie ausführen – Claude Code,
opencode, Codex, Cursor und DeepSeeks dsh-Harness – innerhalb einer Reihe von
konfigurierten Repository-Stammverzeichnissen.

Sich selbst überlassen, hat jeder Assistent seine eigenen Gewohnheiten: Einer antwortet auf Türkisch, ein anderer
auf Englisch; einer durchsucht alles mit Grep, ein anderer fragt einen Code-Graphen ab; einer sagt
„fertig“, ohne einen Test auszuführen. Tezgah beseitigt diese Abweichungen. Öffnen Sie einen beliebigen Host und Sie
erhalten dieselbe Sprache, dieselbe Disziplin und denselben Beweisstandard.

Das Design besteht aus zwei Schichten. Die Regeln existieren einmal in einem gemeinsamen Kern; jeder Host erhält
einen dünnen Adapter, der diesen Kern in die Form übersetzt, die der Host versteht.
Ändern Sie eine Regel an einer Stelle und alle fünf Hosts sehen sie – keine fünffache Kopie
desselben Textes.

<a id="what-it-enforces"></a>

## Was es durchsetzt

- **Ergebnisorientierte türkische Berichterstattung.** Jede Antwort ist auf Türkisch und beginnt mit
  dem Ergebnis oder der Entscheidung (BLUF), gefolgt von nach Auswirkungen geordneten Punkten. Code, Commits,
  Dokumentation und Subagent-Prompts bleiben Englisch; Namen, CLI-Befehle und Fehlerzeichenfolgen
  werden niemals übersetzt.
- **Minimaler Code (ponytail).** Die faulste Änderung, die tatsächlich funktioniert: YAGNI,
  dann Wiederverwendung eines vorhandenen Helfers, dann stdlib, dann eine native Plattformfunktion,
  dann eine installierte Abhängigkeit, dann ein Einzeiler. Keine ungefragten Abstraktionen.
  Validierung, Fehlerbehandlung und Sicherheit werden niemals wegvereinfacht.
- **Code-Graphen-basierte Entdeckung zuerst.** „Wo ist X“, „wer ruft Y auf“, „was geht kaputt, wenn
  sich Z ändert“ gehen an den `codebase-memory-mcp`-Graphen (`search_graph`,
  `trace_path`, `search_code`), nicht an Grep. Grep bleibt richtig für wörtlichen Text,
  Konfigurationen und Nicht-Code-Dateien.
- **Barrierefreiheitsbasierte App-Analyse zuerst.** Eine laufende Web- oder Mobile-App wird über
  ihren Barrierefreiheits- / DOM- / nativen Ansichtsbaum gelesen, nicht über einen Screenshot pro Schritt.
  `analyze-app` deckt einen Browser (Playwright MCP), einen iOS-Simulator oder Android-Emulator
  (Mobile MCP) und optionale Web-Diagnosen (Chrome DevTools MCP) ab;
  ein Screenshot ist eine explizite On-Demand-Aktion für das, was der Baum nicht beantworten kann.
- **Externe Zweitmeinung.** Vor einer nicht-trivialen oder schwer rückgängig zu machenden Entscheidung
  fragt `~/.config/tezgah/bin/consult` unabhängige Modelle über OpenRouter (oder die DeepSeek-API
  mit `--provider deepseek`) parallel an, und der Agent berichtet, wo sie
  übereinstimmten oder nicht.
- **Forschung via OpenResearch.** Wenn der Router eine Aufgabe als Forschung einstuft – eine
  Literaturrecherche, das Aufstellen und Testen von Hypothesen, das Durchführen von Experimenten, ein
  Forschungsartefakt –, steuert er die Arbeit über alphaXivs OpenResearch (`orx`)
  und lädt zuerst das `orx`-Handbuch, anstatt das Protokoll zu improvisieren. Reine
  Code-Entdeckung bleibt auf dem Code-Graphen. Wenn `orx` fehlt, teilt der Router dies
  mit und greift auf einen Host-Subagenten zurück.
- **Ehrlichkeit bei der Überprüfung.** Nichts wird als erledigt, getestet oder behoben
  gemeldet, es sei denn, die Ausgabe wurde gesehen. Ein fehlschlagender Test wird mit seinem
  genauen Fehler als fehlschlagend gemeldet, und eine übersprungene Prüfung wird klar benannt.
- **Keine KI-Zuschreibung, nirgendwo.** Nichts, was persistiert oder veröffentlicht wird – Commit-,
  Merge- und Tag-Nachrichten, PR- und Issue-Texte, Code-Kommentare, Datei-Header, Dokumentationen
  –, darf den Assistenten, das Modell, den Anbieter oder „KI“ erwähnen. Ein Werkzeug zu benutzen ist in Ordnung;
  seinen Namen unter Ihre Arbeit zu setzen, ist es nicht.
- **Zweistufige Orchestrierung.** Der Haupt-Thread entscheidet und verifiziert; ein günstiges
  Modell (`~/.config/tezgah/bin/codegen`, standardmäßig OpenRouter oder `--provider deepseek`) entwirft
  begrenzte, gut spezifizierte Bearbeitungen in einem Scratch-Verzeichnis. Nichts gelangt in das Repo
  außer über den Router, und ein fehlgeschlagener Entwurf fällt automatisch auf das Hauptmodell zurück.
- **Pro-Repo-Subagenten.** Beim Sitzungsstart erhält das umschließende Repo eine kleine Gruppe von
  fähigkeitsbeschränkten Agenten (`tezgah-explorer`, `tezgah-reviewer`,
  `tezgah-researcher`, `tezgah-verifier`) plus einen `tezgah-orchestrator`, die
  in die native Oberfläche jedes installierten Hosts gerendert (Claude/Cursor `.claude/agents/`,
  opencode `.opencode/agents/` plus eine Live-Konfigurationsinjektion, Codex
  `.codex/agents/`) und mit einem verwalteten `.gitignore`-Block ignoriert werden. Bei Claude wird die
  `Agent(tezgah-*)`-Allowlist des Orchestrators nur wirksam, wenn er als
  Haupt-Thread ausgeführt wird (`claude --agent tezgah-orchestrator`); als Subagent wird die Liste
  ignoriert. dsh hat keine rollenspezifische Oberfläche, daher deckt die Router-Regel des Vertrags dies ab.

<a id="supported-hosts"></a>

## Unterstützte Hosts

| Host | Eingebunden durch |
|---|---|
| **omp** (oh-my-pi) — primär | `~/.omp/agent`: verwalteter `RULES.md`-Always-on-Block, Skills, generierte Subagenten, `mcp.json` und eine Erweiterung (`hooks/pre/tezgah-hook.ts`), die die Regeln pro Prompt scharf schaltet, Tools durch ein Gate führt, Evidenz aufzeichnet und die Stop-Regel ausführt; die Verdrahtung wird von `tezgah-setup` geprüft |
| **Claude Code** | lokaler Plugin-Marktplatz: Hooks, Befehle, zwei schreibgeschützte Agenten, Ausgabestil |
| **opencode** | Plugin + Anweisungen + MCP + generierter Skill-Router (native Skill-Liste verweigert), Repo-Auto-Index bei der ersten Nachricht |
| **Codex** | `hooks.json` + Skills + MCP, einschließlich eines `PreToolUse`-Gates |
| **Cursor** | `hooks.json` + Skills + MCP |
| **dsh** | Claude Code Hook-Brücke + verwalteter Patch-Block (Hooks, MCP, LLM-Routen, eine Out-of-Tree-Web-Statuszeile) |

Das Codex-Gate führt Bash, `exec_command`, `apply_patch`, Edit/Write, MCP-Tools,
und Subagent-Aufrufe durch dieselbe Prüfung wie die anderen Hosts. Bei Claude wird das
Zuschreibungsverbot auch mechanisch durchgesetzt: Die `attribution`-Einstellung wird
geleert (`commit`, `pr`, `sessionUrl`), sodass Commit- und PR-Credits an der
Quelle deaktiviert sind.

### App-Analyse

`analyze-app` steuert eine laufende Anwendung über ihren Barrierefreiheitsbaum. Die
Standard-Schleife ist: öffnen, den Baum lesen, handeln, Konsole/Netzwerk/Logs beobachten und
den Baum erneut lesen – ein Screenshot ist eine explizite Aktion für das, was der Baum nicht
beantworten kann (Canvas, Spiel, Animation, visuelle Regression auf Pixelebene). Der Skill ist
ein Pfad für alle Hosts; die Server darunter sind eine gemeinsame Spezifikation in
`hooks/tezgah_apps.py`:

| Server | Ziel | Eingebunden durch |
|---|---|---|
| `playwright` (`@playwright/mcp`) | Webseiten, `browser_*`-Tools | opencode, Codex, Cursor, Claude (Plugin `.mcp.json`) |
| `mobile-mcp` (`@mobilenext/mobile-mcp`) | iOS-Simulator / Android-Emulator, `mobile_*`-Tools | selbe |
| `chrome-devtools` (Opt-in, `--devtools`) | Web-Perf-Traces, tiefes Netzwerk, Source-Mapped-Konsole | selbe |

Der Browser führt standardmäßig ein **isoliertes** Profil aus, sodass ein Durchlauf niemals Ihren
echten Chrome-Status berührt; die Analyse eines eingeloggten Flows ist ein bewusstes Anhängen
(`--cdp-endpoint` oder die Playwright-Erweiterung), kein Standard. Screenshots,
Traces und Baum-Dumps landen in `~/.cache/tezgah/apps` (überschreiben mit
`TEZGAH_ARTIFACTS`) und der Agent erhält einen Pfad zurück, niemals Inline-Bildbytes.
Die Server laufen über `npx`, benötigen also Node, aber keine eigene Installation;
`tezgah-setup --install --devtools` fügt den optionalen Web-Diagnoseserver hinzu.
dsh bindet dieselben zwei Server über seine `dsh-mcp-client`-Brücke ein
(`serverName` / `command` / `args` / `env`, bestätigt gegen das veröffentlichte
Konfigurationsschema), und Claude bezieht sie aus der `.mcp.json` des Plugins
(`claude plugin details tezgah` listet 2 MCP-Server auf und beide verbinden sich).
`mobile-mcp` ist die reibungsintensivere Hälfte: macOS fragt möglicherweise nach Berechtigungen für Barrierefreiheit /
Bildschirmaufnahme und der Ansichtsbaum kann unter Last abbrechen, sodass der Skill
den Baum erneut versucht, bevor er auf einen Screenshot zurückgreift.

CI führt einen deterministischen Handshake für beide Server aus (kein Browser, kein Gerät):
`TEZGAH_E2E_STRICT=1 python3 tests/e2e_analyze_wiring.py`. Zwei optionale lokale
Smoke-Tests gehen weiter: `TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_web.py` startet
Playwright MCP, navigiert und liest den Snapshot ohne Screenshot;
`TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_mobile.py` startet Mobile MCP, prüft
die Ansichtsbaum-Tools und listet ein Gerät auf. Sie geben `SKIP: ...` aus, wenn Node, ein
Browser-Build oder ein Gerät fehlt.

<a id="install"></a>

## Installation

Erfordert Python 3.8+. Node + npm werden für den dsh-Host und, mit `pnpm`,
für seine Web-Statuszeile benötigt. Die optionalen Integrationen degradieren gracefully (fallen elegant zurück):
`codebase-memory-mcp` im PATH treibt den Graphen an; ein Modellschlüssel treibt `consult`
und `codegen` an – standardmäßig OpenRouter (`OPENROUTER_API_KEY` oder
`~/.config/openrouter/key`) oder die DeepSeek-API mit `--provider deepseek`
(`DEEPSEEK_API_KEY` oder `~/.config/deepseek/key`); und OpenResearchs `orx` im
PATH gibt der Forschungsregel etwas zum Steuern. Wenn der Schlüssel des gewählten Anbieters
fehlt, teilt tezgah dies mit, anstatt etwas vorzutäuschen.

Klonen Sie das Repository und schalten Sie dann jeden erkannten Host in einem Durchgang scharf:

```bash
git clone https://github.com/r1z4x/tezgah.git ~/Projects/tezgah
cd ~/Projects/tezgah
bin/tezgah-setup --install
```

In einem Terminal ist dieses Kommando ohne Argumente stattdessen der Installationsassistent:
Es fragt, welche Hosts scharf geschaltet werden, die Wurzelverzeichnisse, ob die fehlenden
optionalen Tools installiert werden und ob das optionale DevTools MCP verdrahtet wird,
druckt den Plan und schreibt erst nach einem Ja. Die Flags sind die Voreinstellungen des
Assistenten, daher fragt `--wizard --hosts omp` nur den Rest. Ein gepipter, Agent- oder
CI-Lauf wird nie bepromptet — er druckt den Bericht, genau wie zuvor.

`--install` installiert auch die fehlenden optionalen Tools, indem das eigene
Installationsprogramm jedes Anbieters **über das Netzwerk** ausgeführt wird: `orx`
(`openresearch.sh/install.sh`), `cursor-agent` (`cursor.com/install`), `dsh` (sein
Home-Profil über `npx`) und `pnpm`, wenn dsh es benötigt (via `npm`) –
`curl ... | sh` inklusive. Keines benötigt sudo; der Durchlauf wird in
`~/.config/tezgah/install.log` aufgezeichnet. Vorschau mit `--dry-run`, überspringen mit
`--no-deps` (nützlich in CI) oder nur die Tools installieren mit `--deps`. Tools landen
in `~/.local/bin` oder `~/.cargo/bin`, sodass möglicherweise eine neue Shell erforderlich ist, bevor
sie im PATH sind; tezgahs eigene Prüfungen suchen unabhängig davon in diesen Verzeichnissen, sodass eine nicht-interaktive
Shell sie dennoch als vorhanden meldet.

Wenn bereits ein Vorgänger-Setup vorhanden ist, importieren Sie es zuerst – es wird beiseite geschoben,
nicht gelöscht:

```bash
bin/tezgah-setup --adopt
```

Claude Code wird über seinen eigenen Plugin-Kanal installiert:

```bash
claude plugin marketplace add ~/Projects/tezgah
claude plugin install tezgah@rizacan-local
```

Beschränken Sie die Installation bei Bedarf explizit:

```bash
bin/tezgah-setup --install --hosts omp
bin/tezgah-setup --install --hosts claude,codex,cursor,opencode,dsh
bin/tezgah-setup --roots ~/work:~/oss --install
```

<a id="day-to-day"></a>

## Alltag

Nichts auszuführen: Die Regeln werden geladen, wenn ein Host startet. Ein paar Befehle sind wissenswert:

| Befehl | Zweck |
|---|---|
| `bin/tezgah-setup` | Im Terminal: der Installationsassistent; in einer Pipe oder in CI: meldet, was pro Host scharfgeschaltet ist |
| `bin/tezgah-setup --wizard` | Erzwingt den Installationsassistenten überall; `--report` erzwingt den Bericht |
| `bin/tezgah-status [PATH]` | Zeigt an, ob die Regeln in diesem Repo aktiv sind |
| `bin/tezgah-setup --status [PATH]` | Druckt die Checkliste der scharfgeschalteten/verwendeten Regeln |
| `bin/tezgah-setup --deps [--dry-run]` | Installiert fehlende optionale Tools (orx, cursor-agent, dsh) |
| `bin/tezgah-research init\|check\|status` | Legt eine Research-Linie an und prüft sie: Zustand, Findings, Claims und die Protokoll-vor-Ergebnis-Regel |
| `bin/tezgah-doctor [--clean] [--prune-sessions DAYS]` | Meldet die Festplattennutzung des Harness; `--clean` löscht alte Index-Logs und bereinigt (vacuum) die opencode-DB; `--prune-sessions` löscht inaktive Sitzungen (die einzige Aktion, die die DB tatsächlich verkleinert) |
| `/plan-add` | Verwandelt ein Stück Arbeit in einen verfolgten Plan |
| `/plan-status` | Fasst offene Pläne zusammen und wählt den nächsten aus |
| `/plan-sync` | Schließt abgeschlossene Pläne ab |
| `bin/tezgah-setup --version` | Druckt die Plugin-Version |
| `bin/tezgah-setup --uninstall` | Entfernt nur die Symlinks von tezgah, Host-Hook-Einträge und den von dsh verwalteten Block |

<a id="configuration"></a>

## Konfiguration

Tezgah ist nur unter seinen konfigurierten Stammverzeichnissen scharfgeschaltet; überall sonst ist es still.

- Standard-Stammverzeichnis: `~/Projects`.
- `~/.config/tezgah/config.json`: `{"roots": ["~/Projects", "~/work"]}`.
- `TEZGAH_ROOTS` (durch Pfadtrennzeichen getrennte Liste) überschreibt die Datei für einmalige Aktionen und CI.

Kill-Switches befinden sich in `~/.config/tezgah/`. Jeder entfernt seine Regel aus dem
in die Sitzung injizierten Text, sodass die Regel tatsächlich stoppt:

| Switch | Schaltet aus |
|---|---|
| `exec-mode.off` | Türkische, ergebnisorientierte Berichterstattung |
| `ponytail-auto.off` | die Minimal-Code-Regel |
| `spec-off` | die Spezifikation-vor-dem-Bauen-Regel |
| `consult-off` | die Externe-Zweitmeinung-Regel |
| `research-off` | das Weiterleiten von Forschungsaufgaben an OpenResearch |
| `orchestrate-off` | Subagenten-Delegation (fügt eine Nicht-Delegieren-Zeile hinzu) |
| `reminder-off` | den Erinnerungstext pro Zug |
| `pretooluse-off` | das PreToolUse-Gate selbst (Zuschreibung, Explorer, Grep-Nudge) |

Pro Repo schalten `.no-ponytail`, `.no-cbm` und `.no-lessons` die Minimal-Code-Regel,
die Code-Graphen-Regel (und ihren Auto-Index) bzw. das Lektionen-Ledger aus.

Wenn der Benutzer einen Fehler markiert, hängt der Agent eine einzeilige Lektion an die
`.tezgah/lessons.md` des Repos an; die neuesten Zeilen werden beim Sitzungsstart injiziert, sodass
sich derselbe Fehler nicht stillschweigend wiederholen kann.

<a id="benchmark"></a>

## Benchmark

Verbessert dieser Vertrag die Arbeit, oder sieht es nur so aus, als sollte er? Das wird in
`benchmarks/arm-bench/` gemessen, nicht behauptet: versteckte Prüfungen, für die der Agent
die Prüfung nie sieht, Kosten aus dem eigenen Nutzungsprotokoll des Hosts, und
Kollateral-Edits, die als Fehler gewertet werden. `PREREGISTRATION.md` legt die Endpunkte
vor einem Lauf fest und `python3 bench.py report` druckt sie; die vollständige Studie mit
den Lauf-IDs ist `docs/research/2026-09-16-tezgah-quality.md`. Jede Zahl unten ist ein
Laufprotokoll.

| Block | Läufe | Was er geklärt hat |
|---|---|---|
| Zwei-Host, 28 Aufgaben, k=3 | 336 | `omp+tezgah` 0.95 und `opencode+tezgah` 0.96 haben überlappende Intervalle und dieselben Kosten pro gelöster Aufgabe; auf den nackten Armen ist omp billiger ($0.0047 gegen $0.0074 CPS), also ist der Daily Driver omp bei keinen Kosten in der Qualität |
| harte Familie, 5 Aufgaben, k=5, zwei Modellfamilien | 200 | gepoolt landen drei der vier Arme bei 40/50: kein Harness-Effekt bei dieser Größe, und das eine Signal, das das erste Modell erzeugte, kehrte sich beim zweiten um |
| Gate-Familie, Gate scharf | 36 | kein Arm nahm die Abkürzungsroute; der Gate-Mechanismus ist direkt verifiziert (ein Skip-Edit wird verweigert), seine Wirkung auf die Arbeit ist noch nicht gemessen |
| Klausel-Ablation, die beiden trennenden Regeln, k=8 | 160 | die Vertragsarme bestehen 23/32 (0.72) gegen 12/32 (0.38) des nackten Ankers |

**Es hilft genau dort, wo die Standardeinstellung des Modells falsch ist.** `c04` (ein
englischer Prompt, bei dem nur der Vertrag die Antwort türkisch macht) liest sich 9/16 mit
einem Vertrag und 0/16 ohne einen; `h02` (ein Geld-Vertrag, dessen sichtbare Suite so oder
so grün ist) liest sich 14/16 gegen 12/16. Wo es keine Lücke zu schließen gibt - 22 der 25
Pilotaufgaben bestanden unter jedem Arm bei jeder Wiederholung - kann ein Benchmark nur eine
Null berichten.

**Zwei Klauseln tragen es.** Das Entfernen von Klausel 1 bringt `c04` auf 0/8, den eigenen
Wert des nackten Ankers, während `h02` sich kaum bewegt. Das Entfernen von Klausel 3 bringt
`h02` auf 2/8 - unter den 6/8 des nackten Ankers -, weil Klausel 3 verbietet, am kürzesten
fertig aussehenden Pfad zu stoppen, und bei jener Aufgabe ist der kürzeste Pfad der
Einzeiler, der die sichtbare Suite besteht und die dokumentierte Regel bricht. Klauseln 2
und 4 bewegen nichts Messbares.

**Kosten folgen der Qualität.** Pro gelöster Aufgabe: $0.0078 gegen $0.0097 auf dem
Vollvertrags-Knoten, $0.0043 gegen $0.0087 auf dem Minus-Ponytail-Knoten. Die Vertragsarme
lösen mehr Aufgaben, also kostet jede gelöste Aufgabe weniger; die Gesamtausgabe ist höher,
und der Benchmark zeichnet sie pro Zeile auf, statt sie zu verrechnen.

Was dies nicht zeigt: Codequalität, Review-Aufwand oder Wartbarkeit, nichts davon wird hier
gemessen; die Wirkung des Gates auf die Entscheidungen eines Arms, da kein Arm in 36
scharfen Läufen nach der Abkürzung griff; oder eine Klausel-*Reihenfolge* - `k=8` legt eine
Richtung fest, bei 8 Läufen pro Zelle. Ein Anbieter und ein Fixture-Paket durchgehend, und
die Ablationsrunden laufen auf einer einzigen Modellfamilie. Eine zweite Modellfamilie
reproduziert die 28-Aufgaben-Null exakt (51/56 gegen 51/56), was zeigt, dass die erste
Lesung kein Modell-Artefakt war.

<a id="cost"></a>

## Kosten

Gemessen auf dieser Maschine (macOS, Python 3.10), nicht geschätzt. `tezgah-setup` druckt
das Live-Budget - lies es dort, statt einer hier kopierten Zahl zu trauen, was dazu führte,
dass eine frühere Revision ein Kernband zitierte, das kleiner war als das, was sie
installiert.

| Band | Was es kostet |
|---|---|
| Sitzungsstart | der Always-on-Vertrag (die Invarianten plus ein einzeiliger Zeiger pro On-Demand-Regel): auf dieser Maschine und Skill-Menge ~1.3k Token Vertragstext und ~1.3k an Skill-Metadaten, wobei die bedingten Regeln (spec, consult, research, graph) nur in dem Zug, dessen Prompt passt, ~0.6k hinzufügen |
| Pro Zug | eine kurze Erinnerung (~0.2k Token) plus die scharf geschaltete Regel, wenn sie passt; Hooks sind separate Python-Prozesse, daher ist der ~19 ms Interpreter-Start die Basis - ein Zug fügt ~31 ms hinzu, Sitzungsstart fügt ~50-81 ms hinzu, ein durch ein Gate geschützter Tool-Aufruf (Bash/Grep/Task) ~24-25 ms. opencode hat keinen Prompt-Zeit-Hook, zahlt also null |
| On Demand | der vollständige `tezgah-contract`-Skill (~6.0k Token), nur bezahlt, wenn eine Aufgabe ihn lädt |
| MCP-Schemas | das größte Band und das, das kein statischer Bericht sieht: allein der Graph-Server deklariert 15 Tools / 24,508 Bytes (~6.1k Token) und reitet auf jeder Anfrage mit, es sei denn, der Host holt Schemas auf Anfrage. `tezgah-setup --mcp-schemas` misst es |
| Festplatte | die Installation dauert ~58 ms, und jede Datei, die tezgah neu schreibt, wird einmal als `<file>.tezgah-bak` aufbewahrt |

**Die Arming-Untergrenze.** Die Invarianten sind immer aktiv - Ausführungsmodus, Ponytail,
Deliver-the-whole-ask, Integrität, Schleifendisziplin, das Lessons-Ledger und das
Attributionsverbot - und die Sicherheitsregel ("irreversible oder nach außen gerichtete
Aktionen brauchen zuerst eine ausdrückliche Nachfrage") ist eine davon, also hängt sie nie
von einem Klassifizierer ab. Jede beratende Regel behält einen umsetzbaren einzeiligen
Zeiger immer aktiv, sodass eine verpasste Übereinstimmung Detail kostet, nie die Regel, und
ein Host-Hook, der ausfällt, auf die Zeiger plus den On-Demand-Skill zurückfällt statt auf
keinen Vertrag. Falsch-Negative sind prüfbar: jeder Prompt hängt `armed=<rules|none>
chars=<n>` - keinen Prompt-Text - an `~/.cache/tezgah/classify.log` an (gekürzt auf die
letzten 200 Zeilen ab 64 KB), und alle fünf Hook-Hosts schalten für denselben Prompt
dieselbe Menge scharf (`tests/test_context.py::ArmingConformance`).

**opencode wird anders scharf geschaltet.** Es hat keinen Injektionspunkt zur Prompt-Zeit,
daher wird der Vertrag als generierte Anweisungsdatei ausgeliefert, und sein
Always-on-Router listet nur die Buckets, nach denen eine Codingsitzung greift, und reduziert
den Rest auf einen Zeiger auf `~/.config/tezgah/opencode-skills.full.md`, der auf Anfrage
gelesen wird; `permission.skill = deny` hindert opencode daran, stattdessen die Metadaten
jedes Skills zu injizieren. `--install` setzt außerdem `compaction.prune` und
`watcher.ignore` und löscht alte Tool-Ergebnisse aus dem Prompt, statt sie bei jedem Schritt
erneut zu senden - ohne das wächst das Working Set auf Hunderttausende von Token, bevor
opencode nahe dem Modelllimit (bei einem 1M-Token-Modell etwa 980k) automatisch kompaktiert.
`bin/tezgah-doctor` meldet den Festplattenbedarf und `--prune-sessions DAYS` löscht inaktive
Sitzungen durch die opencode-CLI, die einzige Aktion, die die Datenbank tatsächlich
verkleinert, da VACUUM allein das nicht kann.

**Warum es sich auszahlt.** In einem echten Repo ignorierte ein Standard-`grep` den
relevanten Ordner und fand nichts; mit deaktiviertem Ignore dauerte es 3.95 s und vermischte
immer noch Definitionen mit Aufrufstellen, während der Code-Graph dieselbe Frage in 16 ms
mit den 8 echten Aufrufstellen beantwortete.

<a id="development"></a>

## Entwicklung

```bash
python3 -m unittest discover -s tests -v   # stdlib test suite
pip install -r requirements-dev.txt        # pinned ruff, the only dev dep
ruff check .                               # lint (config in pyproject.toml)
```

CI läuft sowohl auf Python 3.10 als auch auf 3.12. Um eine installierte Claude-Kopie
aus diesem Checkout zu aktualisieren, verwenden Sie `bin/tezgah-setup --sync` und validieren Sie das Manifest mit
`claude plugin validate .claude-plugin/plugin.json`. Wenn Sie die Version erhöhen, aktualisieren Sie
`.claude-plugin/plugin.json` und `.claude-plugin/marketplace.json`
zusammen – sie müssen übereinstimmen.

`codebase-memory-mcp` wird vom Benutzer installiert. Orcas Hooks und Dateien sind nicht
Teil dieses Projekts und bleiben unangetastet. Claude erhält den Always-on-Kern
vom SessionStart-Hook; `output-styles/tezgah.md` ist ein Duplikat für Builds,
die Plugin-Ausgabestile laden, daher ist der Hook der maßgebliche Pfad.

<a id="contributing"></a>

## Mitwirken

Kleine, einzeckige Änderungen sind am einfachsten zu akzeptieren. Eine Regel gehört in den
gemeinsamen Kern (`hooks/`), es sei denn, sie ist wirklich hostspezifisch; ein Host-Unterschied
gehört in seinen Adapter unter `hosts/<name>/`. Halten Sie das Diff so kurz wie möglich,
während es noch korrekt ist – die projekteigene Minimal-Code-Regel gilt auch für das Projekt.

Bevor Sie einen Pull Request öffnen, führen Sie dieselben drei Prüfungen aus, die auch CI ausführt:

```bash
python3 -m compileall -q hooks hosts bin statusline.py   # byte-compile every script
python3 -m unittest discover -s tests                     # stdlib test suite
ruff check .                                              # lint; config in pyproject.toml
```

`ruff` stammt aus `requirements-dev.txt` (`pip install -r requirements-dev.txt`),
was die einzige Entwicklungsabhängigkeit ist.

<a id="security"></a>

## Sicherheit

Melden Sie Schwachstellen privat über die Security Advisories von GitHub
(Tab **Security** → **Report a vulnerability**) anstatt über ein öffentliches Issue.

tezgah führt Shell-Hooks aus, schreibt Host-Konfigurationen und injiziert Text in jede
Sitzung. Daher ist alles im Scope, was dazu führt, dass ein Hook von einem Angreifer kontrollierten Code ausführt,
einen Schlüssel in eine Konfigurationsdatei leakt, eine Sandbox erweitert oder zulässt, dass Repository-Inhalte
zu Anweisungstext eskalieren. Geben Sie den Host, die tezgah-Version
(`bin/tezgah-setup --version`) und eine minimale Reproduktion an.

<a id="license"></a>

## Lizenz

Die `LICENSE` (MIT) im Stammverzeichnis deckt die eigenen Dateien von tezgah ab. `skills/ponytail` und
`skills/no-ai-slop` werden unter ihren eigenen MIT-Bedingungen bereitgestellt (vendored), die in
`NOTICE` festgehalten sind.
