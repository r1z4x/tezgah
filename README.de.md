<p align="center">
  <a href="README.md">English</a> |
  <a href="README.de.md">Deutsch</a> |
  <a href="README.es.md">Español</a> |
  <a href="README.fr.md">Français</a> |
  <a href="README.tr.md">Türkçe</a>
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

<p align="center"><sub>Englisch ist die maßgebliche Quelle; Übersetzungen können hinterherhinken.</sub></p>

---

Tezgah rüstet jeden KI-Programmierassistenten, den Sie ausführen — **omp, den
primären Host**, plus Claude Code, Codex, Cursor, opencode und DeepSeeks dsh —
innerhalb der von Ihnen konfigurierten Repository-Stammverzeichnisse mit einem
funktionierenden Vertrag aus. Sich selbst überlassen, driften die Assistenten:
Einer antwortet auf Türkisch, ein anderer auf Englisch; einer nutzt Grep, ein
anderer fragt einen Code-Graphen ab; einer meldet „fertig“, ohne einen Test
auszuführen. Die Regeln existieren einmal in einem gemeinsamen Kern; jeder
Host erhält einen dünnen Adapter, der sie in die Form übersetzt, die er
versteht — eine Regel, die an einer Stelle geändert wird, erreicht jeden Host
auf dieselbe Weise.

## Was tezgah durchsetzt und aufzeichnet

- **Ein Vertrag, sechs Hosts.** omp, Claude Code, Codex, Cursor, opencode und
  dsh sehen dieselben Regeln, denn jeder Host ist ein dünner Adapter über
  einem gemeinsamen Kern — eine Regel einmal ändern, alle übernehmen sie.
- **Eine Fertig-Meldung braucht eine bestandene Prüfung im Protokoll.** Ein
  Gate aus 15 Verweigerungen stoppt die entschärfte Prüfung — `--no-verify`,
  `|| true`, ein in `tail` gepipeter Test, ein mitten im Flug ergänzter Skip —
  und die Stop-Regel verweigert einen Fertigstellungsanspruch, den das
  Evidenzprotokoll der Sitzung nicht stützt. Sie verweigert den Zug; sie kann
  das Modell nicht davon abhalten, den Anspruch zu erheben.
- **Forschung kommt mit eigener Bibliothek.** Forschungsaufgaben laufen über
  OpenResearch, mit einer integrierten Bibliothek aus 98 Upstream-Skills, die
  Eintrag für Eintrag geladen wird, damit der Kontext klein bleibt.
- **Jede Regel hat einen Ausschalter.** Sechzehn Kill-Switches — dazu
  Repo-Markierungen — entfernen den Regeltext aus der Sitzung; die Regel
  stoppt damit wirklich, statt nur als aus zu erscheinen.
- **Eine feste Antwortform.** Antworten sind türkisch, sofern Sie keine andere Sprache wählen, und
  beginnen mit dem Ergebnis; eine Liste zeigt höchstens fünf gerankte
  Einträge; eine Schätzung wird als Schätzung genannt; ein Fehler liest sich
  als Ort, Ursache, Behebung.

## Was es nicht gezeigt hat

Tezgah ist eine Sammlung von Mechanismen: Regeln, die in die Sitzung
eingespeist werden, ein Gate, das bestimmte Befehle verweigert, und ein
Protokoll, das die Stop-Regel liest. Es ist kein Beleg dafür, dass ein Agent
weniger schummelt oder mehr Aufgaben löst. Ein gepaartes An/Aus-Experiment
(Oktober 2026; DeepSeek V4.1 Flash auf omp, ohne tezgah gegen eine volle
tezgah-Installation) fand keine messbare Verringerung des Schummelns, weil
das Modell in beiden Armen kaum schummelte:

- **Phase 1, drei Druck-Fixtures:** Schummeln in 0 von 60 Läufen in jedem
  Arm; sauber bestanden 48/60 mit tezgah gegen 53/60 ohne.
- **Phase 2, der widersprüchliche SWE-bench-Split von ImpossibleBench (44
  Instanzen, k = 3):** Schummeln 0/132 mit tezgah gegen 1/131 ohne (-0.8 pp,
  95%-KI -2.3 bis 0); sauber bestanden auf den Originalaufgaben 129/131 gegen
  129/132.
- **Falsche Fertig-Meldungen, von Hand gelabelt:** Bei diesen unmöglichen
  Aufgaben meldeten 3 von 30 Stichproben-Abschlussnachrichten mit tezgah und
  6 von 30 ohne dem Nutzer, die Aufgabe sei erledigt. Der bereinigte
  Unterschied liegt bei -5 pp (95%-KI -18 bis +9), also kein Effekt in
  irgendeine Richtung.
- **Eine Schwachstelle im Anspruchsleser der Stop-Regel:** Er markierte
  115/132 Läufe mit tezgah und 90/131 ohne, aber nur 10% bzw. 20% seiner
  Markierungen waren echte Fertig-Meldungen. Mit tezgah antwortete der Agent
  auf Türkisch, und der Leser zählt `doğrulandı` (verifiziert) bei einer
  Teilkorrektur als Anspruch. Das ist festgehalten, aber noch nicht behoben.

Der Lauf hatte Messmängel, darunter Agenten in beiden Armen, die die
Grundwahrheit des Benchmarks lesen konnten. Die Aggregate, die Zählungen pro
Aufgabe und jede Einschränkung stehen im
[Ergebnisbündel](docs/results/paired-outcome-2026-10.md) (Englisch).

<a id="install"></a>

## Installation

Eine Zeile, auf macOS, Linux oder WSL (Python 3.10+, `curl`, `tar`). Sie lädt
die neueste Version herunter, prüft ihre sha256 und rüstet jeden gefundenen
Host (Claude Code über dessen eigene `claude plugin`-CLI):

```bash
curl -fsSL https://raw.githubusercontent.com/r1z4x/tezgah/main/packaging/install.sh | sh
```

Oder über npm: `npm i -g @r1z4x/tezgah && tezgah --install`.

Eine Host-Konfiguration, die es nicht lesen kann, bleibt unverändert; jede
geänderte Konfiguration behält eine datierte `.tezgah-bak`-Kopie, und die
Installation endet mit einem Fehlercode, wenn ein geplanter Host nicht
gerüstet ist.

### Was tezgah auf Ihrem Rechner ändert

- **Host-Konfiguration.** Jeder gerüstete Host erhält tezgahs Hooks, seine
  MCP-Einträge und einen verwalteten Vertragsblock in seiner globalen
  Regeldatei (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`,
  `~/.omp/agent/RULES.md`). Claude Codes Hooks kommen in einem Plugin, das über
  `claude plugin` registriert wird; ohne `claude`-CLI bleibt Claude ungerüstet,
  und der Bericht sagt es.
- **Agent-Dateien in Ihren Repositories.** In den konfigurierten Wurzeln
  schreibt eine Sitzung Subagent-Dateien nach `.claude/agents/`,
  `.codex/agents/` und `.opencode/agents/` und trägt diese Verzeichnisse in die
  eigene `.git/info/exclude` des Klons ein (`TEZGAH_NO_EXCLUDE=1` stoppt das).
- **Eine tägliche Update-Prüfung.** Die Statuszeile fragt höchstens einmal am
  Tag nach einer neueren Version; `~/.config/tezgah/update-check-off` oder
  `TEZGAH_UPDATE_CHECK=0` schaltet sie ab.
- **orx.** Die Installation lädt die OpenResearch-CLI, über die
  Forschungsaufgaben laufen; `TEZGAH_NO_DEPS=1` überspringt sie.
- **Antwortsprache.** Antworten sind standardmäßig türkisch, und die Stop-Regel
  hält sie dazu an. `--reply-lang en` verlangt Englisch, `any` Ihre eigene
  Sprache; beides wird nicht geprüft: `curl -fsSL … | sh -s -- --reply-lang en`.

Lieber der Coding-Assistent erledigen? Fügen Sie dies in omp, Claude Code,
Codex, Cursor oder opencode ein (der Prompt bleibt Englisch; der Assistent
versteht ihn in jeder Sprache):

```text
Install tezgah (https://github.com/r1z4x/tezgah) on this machine and verify it.

1. Check the prerequisites: python3 --version must be 3.10 or newer, and curl
   and tar must exist. If one is missing, stop and tell me which.
2. Run the installer exactly as published - do not edit it or pipe it anywhere else:
   curl -fsSL https://raw.githubusercontent.com/r1z4x/tezgah/main/packaging/install.sh | sh
   Its output must contain "verified tezgah-<version>.tar.gz" (the sha256
   check). If it does not, stop and show me the output.
3. Verify: run ~/.local/share/tezgah/current/bin/tezgah-setup --version and
   ~/.local/share/tezgah/current/bin/tezgah-setup --report, and show me every
   line that says MISS.
4. Tell me which hosts were armed, which repository root was configured
   (default ~/Projects - if my code lives elsewhere, ask me for the directory and
   run ~/.local/share/tezgah/current/bin/tezgah-setup --roots <dir> --install),
   and that I must restart each assistant for the hooks to load.
Do not change any other file and do not uninstall anything.
```

Festgepinnte Versionen, Windows (`packaging/install.ps1`), offline-Tarballs,
Upgrades und die optionalen Integrationen stehen in der [Dokumentation](docs/README.md).

## Unterstützte Hosts

**omp** (der primäre Host, gegen den entwickelt und verifiziert wird), **Claude Code**, **Codex**, **Cursor**, **opencode**, **dsh** — dünne Adapter über einem gemeinsamen Kern.

## Wo die Tiefe liegt

Gate, Evidence-Ledger, Host-Adapter, Konfiguration und Entwicklung liegen in [docs/README.md](docs/README.md), eine Seite pro Frage.

## Lizenz

MIT — siehe [LICENSE](LICENSE).
Vendorte Skills (`ponytail`, `no-ai-slop`, `i-have-adhd`) tragen ihre eigenen MIT-Bedingungen, verzeichnet in [NOTICE](NOTICE).
