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

| Host | Eingebunden durch | Statuszeile |
|---|---|---|
| **Claude Code** | lokaler Plugin-Marktplatz: Hooks, Befehle, zwei schreibgeschützte Agenten, Ausgabestil | native `statusLine` |
| **opencode** | Plugin + Anweisungen + MCP + generierter Skill-Router (native Skill-Liste verweigert), Repo-Auto-Index bei der ersten Nachricht | TUI-Plugin (keine Befehls-`statusLine`) |
| **Codex** | `hooks.json` + Skills + MCP, einschließlich eines `PreToolUse`-Gates | Hook `systemMessage` (Fußzeilen-Elementliste ist geschlossen) |
| **Cursor** | `hooks.json` + Skills + MCP | `statusLine` in `cli-config.json` |
| **dsh** | Claude Code Hook-Brücke + verwalteter Patch-Block (Hooks, MCP, LLM-Routen, eine Out-of-Tree-Web-Statuszeile) | Web-UI-Plugin: `tezgah-dsh-statusline` im Sitzungs-Header |

Das Codex-Gate führt Bash, `exec_command`, `apply_patch`, Edit/Write, MCP-Tools,
und Subagent-Aufrufe durch dieselbe Prüfung wie die anderen Hosts. Bei Claude wird das
Zuschreibungsverbot auch mechanisch durchgesetzt: Die `attribution`-Einstellung wird
geleert (`commit`, `pr`, `sessionUrl`), sodass Commit- und PR-Credits an der
Quelle deaktiviert sind.

### Statuszeile

Jeder Host rendert dieselbe einzeilige Checkliste von `tezgah-status`, sodass sie
nicht abweichen können. Der Zustand ist der entscheidende Punkt: Eine Markierung ist
**grün**, wenn die Regel scharfgeschaltet und in dieser Sitzung in Kraft ist, **gelb**,
wenn sie scharfgeschaltet, aber auf Abruf ist (noch nicht verwendet), und **rot**, wenn
ein Kill-Switch sie ausgeschaltet hat. `idx` meldet die Graphen-Bereitschaft
separat (`✓` indiziert, `↻` veraltet, `✗` nicht indiziert, `–` nicht zutreffend) und
`plans N (M blk)` die offenen Pläne. `tezgah-status --legend` druckt die Legende,
`--json` liefert dieselben Segmente für eine UI, und `--no-color` (oder `NO_COLOR`)
erzwingt reinen Text. Claude Code und Cursor färben die native Statuszeile; die
opencode-TUI färbt ihre eigene Komponente und aktualisiert sich über den Host-Event-Bus; die
dsh-Web-UI färbt ihre Header-Komponente und aktualisiert sich nur, solange ihr Tab
sichtbar ist; Codex zeigt die einfache Zeichenfolge in `systemMessage`.

dsh führt dieselben Claude-Hook-Dateien über seine `dsh-hooks-claude-code`-Brücke aus,
sodass der Sitzungsstart-Vertrag, das Zuschreibungs-Gate und der First-Grep-Nudge
dort alle gelten. dsh stellt ein einziges `subagent`-Tool zur Verfügung, sodass die Grep-Only-Explorer-Verweigerung
wirkungslos ist – es gibt keinen Explorer-Subagenten, den es ablehnen könnte. Die standardmäßige
`workspace-write`-Sandbox von dsh beschränkt Hook-Unterprozesse auf den Workspace und das
temporäre Verzeichnis der Plattform, sodass tezgah seinen Hook-Status (Nudge-Markierungen, Index-Stempel) in
ein beschreibbares Fallback dort schreibt, anstatt bei einem verweigerten Schreibvorgang fehlzuschlagen. Der Graphen-Index-Worker
kann den `codebase-memory-mcp`-Cache nicht aus dem Inneren dieser Sandbox schreiben, daher
wärmt der `dsh`-Launcher den Index in der unbeschränkten Shell des Benutzers auf, bevor
dsh gebootet wird – ein neues Repo wird genau wie auf den anderen Hosts indiziert, mit HEAD-Stempel. Eine
ohne den Launcher gebootete Sitzung erhält dennoch einen klaren Bericht, dass der
nicht in einer Sandbox ausgeführte MCP-Server den Graphen bedient und `index_repository` für ein Repo
benötigt, das er nicht indiziert hat, anstelle eines rohen `EPERM`. Der verwaltete
Patch-Block deklariert außerdem zwei OpenAI-kompatible LLM-Routen auf dem pi-ai-Adapter,
den die Basiskomposition einhängt: `openrouter` (`OPENROUTER_API_KEY`) und `deepseek`
(`DEEPSEEK_API_KEY`), auswählbar neben dem nativen `deepseek-official`-Standard.
Schlüssel werden aus der Startumgebung oder dem Harness-Anmeldeinformationsspeicher
aufgelöst; keiner der Schlüssel gelangt in die Konfigurationsdatei. tezgah-setup legt außerdem einen `dsh`-Launcher
in den PATH (`~/.local/bin/dsh`), der die installierte CLI unter
`$DSH_HOME` findet, sodass `dsh --profile web` aus jedem Verzeichnis funktioniert.

dsh hat keine Befehls-Statuszeile, daher liefert tezgah eine als Web-UI-Plugin mit:
`tezgah-dsh-statusline`. Seine Host-Hälfte stellt die `tezgah-status`-Zeichenfolge für den
Workspace der Sitzung über eine authentifizierte `/api/tezgah.status`-Route bereit (mit
`?format=json` für die farbige Ansicht); seine Browser-Hälfte rendert sie im Sitzungs-Header,
farblich nach Status mit einer Hover/Klick-Legende, und aktualisiert sich nur, solange der
Tab sichtbar ist. `tezgah-setup`
verlinkt das Plugin in das Web-Profil und aktiviert es mit einer verwalteten Zeile in
`profiles/web/cordis.patch.yml` (nur Web, da die Host-Hälfte den nur im Web verfügbaren
`connection`-Dienst injiziert); ein Profil, das noch nie `web` gebootet hat, wird mit einem
Hinweis übersprungen, anstatt halb geschrieben zu werden. Im `headless`-Modus injiziert die Hooks-Brücke
den SessionStart-Vertrag als eigenen nachfolgenden Zug (ihr `agent/session-start`
ruft `agent.inject()` losgelöst auf, nachdem die One-Shot-Aufgabe bereits die erste Nachricht ist),
sodass `dsh --profile headless "<task>"` einen zusätzlichen Zug verbraucht und bei einem
Prompt für eine wörtliche Antwort die Reaktion des Modells auf den Vertrag anstelle der
Antwort auf die Aufgabe ausgibt; interaktive Web-Sitzungen sind davon nicht betroffen.

`bin/tezgah-setup --install` löst auch `orx install-skills` für Claude,
Codex, opencode und Cursor aus, wenn `orx` im PATH ist, sodass die Forschungsregel ein
Handbuch zum Laden hat. Die Shim-Dateien gehören zu orx, daher führt tezgah nur dieses Installationsprogramm
aus und listet sie niemals zur Deinstallation auf. dsh hat kein orx-Harness; die Forschungsregel
greift dort auf `orx skill` in der Shell zurück.

Das Claude-Plugin liefert außerdem zwei schreibgeschützte Agenten mit. `agents/tezgah-explorer.md`
führt Code-Entdeckung aus dem Graphen durch und gibt `file:line`-Beweise zurück;
`agents/tezgah-reviewer.md` wandelt ein Diff mit `detect_changes` in seine Auswirkungsmenge um
und sucht dann nach echten Fehlern. Bei beiden sind Schreib- und Befehls-Tools
deaktiviert; ihre Ausgabe hat beratenden Charakter.

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

`--install` installiert auch die fehlenden optionalen Tools, indem das eigene Installationsprogramm jedes Anbieters **über das Netzwerk** ausgeführt wird: `orx`
(`openresearch.sh/install.sh`), `cursor-agent` (`cursor.com/install`), `dsh`
(sein Home-Profil über `npx`) und `pnpm`, wenn dsh es benötigt (via `npm`) –
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
bin/tezgah-setup --install --hosts claude,codex,opencode,cursor,dsh
bin/tezgah-setup --roots ~/work:~/oss --install
```

<a id="day-to-day"></a>

## Alltag

Nichts auszuführen: Die Regeln werden geladen, wenn ein Host startet. Ein paar Befehle sind wissenswert:

| Befehl | Zweck |
|---|---|
| `bin/tezgah-setup` | Meldet, was pro Host scharfgeschaltet ist |
| `bin/tezgah-status [PATH]` | Zeigt an, ob die Regeln in diesem Repo aktiv sind |
| `bin/tezgah-setup --status [PATH]` | Druckt die Checkliste der scharfgeschalteten/verwendeten Regeln |
| `bin/tezgah-setup --deps [--dry-run]` | Installiert fehlende optionale Tools (orx, cursor-agent, dsh) |
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

<a id="cost"></a>

## Kosten

Auf dieser Maschine gemessen (macOS, Python 3.10), nicht geschätzt:

- **Kontext.** Ein Sitzungsstart injiziert ~4,8 KB (~1,2k Token) Vertragstext.
  Bei Codex wird in jedem Zug eine 480-Byte-Erinnerung mitgeschickt; Claude und die anderen Hosts haben
  keinen Hook pro Zug, daher sind ihre Kosten pro Zug null. Der vollständige `tezgah-contract`-Skill
  (~19,9k Zeichen) wird nur bezahlt, wenn eine Aufgabe ihn lädt. Bei opencode wird der
  Vertrag als ~5,5 KB große Anweisungsdatei ausgeliefert. opencode würde andernfalls
  ~53 KB an Skill-Namen/Beschreibungen/Speicherort-Text in den System-Prompt jeder Sitzung injizieren;
  tezgah verweigert diese Liste (`permission.skill = deny`) und liefert
  stattdessen einen generierten ~16 KB großen Skill-Router aus, sodass ein Skill gefunden wird, indem sein
  `SKILL.md`-Pfad aus dem Router gelesen wird.
- **Latenz.** Hooks sind separate Python-Prozesse, daher dominiert der Interpreter-Start von ~19 ms.
  Zusätzlich fügt der Sitzungsstart ~25 ms hinzu, ein durch ein Gate geschützter Tool-Aufruf
  (Bash/Grep/Task) fügt ~9 ms hinzu, und das Stop-Segment von Codex fügt ~15 ms pro Zug hinzu.
- **Festplatte.** Die Installation dauert ~58 ms und jede Datei, die tezgah umschreibt, wird
  einmal als `<file>.tezgah-bak` aufbewahrt.

Die Auszahlung zeigt sich bei Fragen zu Aufrufern. In einem echten Repo ignorierte ein Standard-`grep`
den relevanten Ordner und fand nichts; mit deaktiviertem Ignore dauerte es
3,95 s und vermischte immer noch Definitionen mit Aufrufstellen. Der Code-Graph beantwortete
dieselbe Frage in 16 ms und listete nur die 8 echten Aufrufstellen auf.

opencode ist auch für die Kontext-Hygiene in langen Sitzungen gerüstet: `tezgah-setup --install`
setzt `compaction.prune`, sodass alte Tool-Ergebnisse aus dem Prompt gelöscht werden,
anstatt bei jedem Schritt erneut gesendet zu werden, und eine `watcher.ignore`-Liste hält den Datei-Watcher
aus `.git`, `node_modules` und Build-Verzeichnissen fern. Beide werden zusammengeführt – ein expliziter Benutzerwert
gewinnt. Dies ist wichtig, da opencode nur in der Nähe des Kontextlimits des Modells automatisch komprimiert
(bei einem 1M-Token-Modell etwa 980k), sodass das Working Set ohne Bereinigung auf
Hunderttausende von Token anwächst. `bin/tezgah-doctor` meldet den resultierenden Festplattenbedarf;
`--prune-sessions DAYS` löscht inaktive Sitzungen über die opencode-CLI, was die einzige Aktion ist,
die die Datenbank tatsächlich verkleinert – VACUUM allein kann das nicht, da alle seine Seiten live sind.

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
