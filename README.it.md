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

<h3 align="center">Un unico contratto di lavoro per ogni assistente alla programmazione IA che esegui.</h3>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/github/license/r1z4x/tezgah?style=flat-square"></a>
  <a href="https://github.com/r1z4x/tezgah/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/r1z4x/tezgah/ci.yml?style=flat-square&label=ci"></a>
  <a href="https://github.com/r1z4x/tezgah/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/r1z4x/tezgah?style=flat-square"></a>
</p>

<p align="center">
  <a href="#what-it-enforces">Cosa impone</a> &bull;
  <a href="#supported-hosts">Host supportati</a> &bull;
  <a href="#install">Installazione</a> &bull;
  <a href="#day-to-day">Uso quotidiano</a> &bull;
  <a href="#configuration">Configurazione</a> &bull;
  <a href="#benchmark">Benchmark</a> &bull;
  <a href="#cost">Costi</a> &bull;
  <a href="#development">Sviluppo</a> &bull;
  <a href="#contributing">Contribuire</a> &bull;
  <a href="#security">Sicurezza</a> &bull;
  <a href="#license">Licenza</a>
</p>

<p align="center"><sub>L'inglese è la fonte di verità; le traduzioni potrebbero non essere aggiornate.</sub></p>

---

Un unico contratto di lavoro per ogni assistente alla programmazione IA che esegui — Claude Code,
opencode, Codex, Cursor e l'harness dsh di DeepSeek — all'interno di un insieme di
root di repository configurate.

Lasciato a sé stesso, ogni assistente ha le proprie abitudini: uno risponde in turco, un altro
in inglese; uno usa grep per tutto, un altro interroga un grafo del codice; uno dice
"fatto" senza eseguire un test. Tezgah elimina questa deriva. Apri qualsiasi host e
otterrai la stessa lingua, la stessa disciplina e lo stesso standard di prova.

Il design è a due livelli. Le regole risiedono una sola volta in un nucleo condiviso; ogni host riceve
un sottile adattatore che traduce quel nucleo nel formato che l'host comprende.
Modifica una regola in un punto e tutti e cinque gli host la vedranno — nessuna
copia quintupla dello stesso testo.

<a id="what-it-enforces"></a>

## Cosa impone

- **Report in turco orientati al risultato.** Ogni risposta è in turco e inizia con
  il risultato o la decisione (BLUF), seguiti dai punti ordinati per impatto. Codice, commit,
  documentazione e prompt dei subagenti rimangono in inglese; nomi, comandi CLI e
  stringhe di errore non vengono mai tradotti.
- **Codice minimo (ponytail).** La modifica più pigra che funziona davvero: YAGNI,
  poi riutilizzo di un helper esistente, poi stdlib, poi una funzionalità nativa della piattaforma,
  poi una dipendenza installata, poi una singola riga. Nessuna astrazione non richiesta.
  La convalida, la gestione degli errori e la sicurezza non vengono mai semplificate o rimosse.
- **Scoperta basata prima sul grafo del codice.** "Dov'è X", "chi chiama Y", "cosa si rompe se
  Z cambia" passano per il grafo `codebase-memory-mcp` (`search_graph`,
  `trace_path`, `search_code`), non per grep. Grep rimane appropriato per testo letterale,
  configurazioni e file non di codice.
- **Analisi dell'app basata prima sull'accessibilità.** Un'app web o mobile in esecuzione viene letta
  attraverso il suo albero di accessibilità / DOM / viste native, non con uno screenshot per ogni passaggio.
  `analyze-app` copre un browser (Playwright MCP), un simulatore iOS o un emulatore Android
  (Mobile MCP) e la diagnostica web opzionale (Chrome DevTools MCP); uno
  screenshot è un'azione esplicita e su richiesta per ciò a cui l'albero non può rispondere.
- **Seconda opinione esterna.** Prima di una decisione non banale o difficile da annullare,
  `~/.config/tezgah/bin/consult` interroga modelli indipendenti tramite OpenRouter (o l'API DeepSeek
  con `--provider deepseek`) in parallelo, e l'agente riporta dove sono
  d'accordo o in disaccordo.
- **Ricerca tramite OpenResearch.** Quando il router giudica che un'attività è di ricerca — una
  revisione della letteratura, la formulazione e il test di ipotesi, l'esecuzione di esperimenti, un
  artefatto di ricerca — guida il lavoro attraverso OpenResearch di alphaXiv (`orx`)
  e carica prima il manuale di `orx`, invece di improvvisare il protocollo. La semplice
  scoperta del codice rimane sul grafo del codice. Quando `orx` è assente, il router lo comunica
  e ripiega su un subagente dell'host.
- **Onestà sotto verifica.** Nulla viene segnalato come fatto, testato o risolto
  a meno che l'output non sia stato visto. Un test fallito viene segnalato come fallito con il suo
  errore esatto, e un controllo saltato viene dichiarato chiaramente.
- **Nessuna attribuzione all'IA, da nessuna parte.** Nulla di ciò che viene persistito o pubblicato — messaggi di commit,
  merge e tag, testo di PR e issue, commenti nel codice, intestazioni di file, documentazione
  — può accreditare l'assistente, il modello, il fornitore o l' "IA". Usare uno strumento va bene;
  firmare il tuo lavoro con il suo nome no.
- **Orchestrazione a due livelli.** Il thread principale decide e verifica; un modello economico
  (`~/.config/tezgah/bin/codegen`, OpenRouter per impostazione predefinita o `--provider deepseek`) abbozza
  modifiche limitate e ben specificate in una directory temporanea. Nulla raggiunge la repository
  se non attraverso il router, e una bozza fallita ripiega sul modello principale
  automaticamente.
- **Subagenti per repository.** All'avvio della sessione, la repository contenitore riceve un piccolo set di
  agenti con capacità limitate (`tezgah-explorer`, `tezgah-reviewer`,
  `tezgah-researcher`, `tezgah-verifier`) più un `tezgah-orchestrator`, renderizzati
  nella superficie nativa di ciascun host installato (Claude/Cursor `.claude/agents/`,
  opencode `.opencode/agents/` più un'iniezione di configurazione live, Codex
  `.codex/agents/`) e ignorati con un blocco `.gitignore` gestito. Su Claude la
  allowlist `Agent(tezgah-*)` dell'orchestratore ha effetto solo quando viene eseguito come
  thread principale (`claude --agent tezgah-orchestrator`); come subagente la lista viene
  ignorata. dsh non ha una superficie per ruolo, quindi la regola del router del contratto lo copre.

<a id="supported-hosts"></a>

## Host supportati

| Host | Collegato tramite |
|---|---|
| **omp** (oh-my-pi) — primario | `~/.omp/agent`: blocco sempre attivo `RULES.md` gestito, skill, subagenti generati, `mcp.json`, e un'estensione (`hooks/pre/tezgah-hook.ts`) che arma le regole per prompt, controlla gli strumenti, registra le prove ed esegue la regola Stop; il cablaggio è verificato da `tezgah-setup` |
| **Claude Code** | marketplace dei plugin locale: hook, comandi, due agenti in sola lettura, stile di output |
| **opencode** | plugin + istruzioni + MCP + router di skill generato (lista di skill nativa negata), auto-indicizzazione della repo al primo messaggio |
| **Codex** | `hooks.json` + skill + MCP, incluso un gate `PreToolUse` |
| **Cursor** | `hooks.json` + skill + MCP |
| **dsh** | bridge per hook di Claude Code + blocco patch gestito (hook, MCP, rotte LLM, una riga di stato Web out-of-tree) |

Il gate di Codex esegue Bash, `exec_command`, `apply_patch`, Edit/Write, strumenti MCP,
e chiamate ai subagenti attraverso lo stesso controllo degli altri host. Su Claude, il
divieto di attribuzione viene applicato anche meccanicamente: l'impostazione `attribution` viene
svuotata (`commit`, `pr`, `sessionUrl`) in modo che i crediti per commit e PR siano disattivati alla
fonte.

### Analisi dell'app

`analyze-app` guida un'applicazione in esecuzione dal suo albero di accessibilità. Il
ciclo predefinito è aprire, leggere l'albero, agire, osservare console/rete/log e
rileggere l'albero — uno screenshot è un'azione esplicita per ciò a cui l'albero non può
rispondere (canvas, giochi, animazioni, regressioni visive a livello di pixel). La skill è
un unico percorso per tutti gli host; i server sottostanti sono una singola specifica condivisa in
`hooks/tezgah_apps.py`:

| Server | Target | Collegato tramite |
|---|---|---|
| `playwright` (`@playwright/mcp`) | pagine web, strumenti `browser_*` | opencode, Codex, Cursor, Claude (plugin `.mcp.json`) |
| `mobile-mcp` (`@mobilenext/mobile-mcp`) | Simulatore iOS / emulatore Android, strumenti `mobile_*` | idem |
| `chrome-devtools` (opt-in, `--devtools`) | tracce delle prestazioni web, rete profonda, console con source-map | idem |

Il browser esegue un profilo **isolato** per impostazione predefinita, quindi un'esecuzione non tocca mai
il tuo vero stato di Chrome; analizzare un flusso con accesso effettuato è un collegamento deliberato
(`--cdp-endpoint` o l'estensione Playwright), non un'impostazione predefinita. Screenshot,
tracce e dump dell'albero finiscono in `~/.cache/tezgah/apps` (sovrascrivibile con
`TEZGAH_ARTIFACTS`) e l'agente riceve indietro un percorso, mai byte di immagini inline.
I server vengono eseguiti tramite `npx`, quindi necessitano di node ma di nessuna installazione propria;
`tezgah-setup --install --devtools` aggiunge il server opzionale di diagnostica web.
dsh collega gli stessi due server attraverso il suo bridge `dsh-mcp-client`
(`serverName` / `command` / `args` / `env`, confermati rispetto allo schema di configurazione pubblicato),
e Claude li ottiene dal `.mcp.json` del plugin
(`claude plugin details tezgah` elenca 2 server MCP ed entrambi si connettono).
`mobile-mcp` è la metà con maggiore attrito: macOS potrebbe richiedere i permessi di Accessibilità /
Registrazione Schermo e l'albero delle viste può cadere sotto carico, quindi la skill
riprova l'albero prima di ripiegare su uno screenshot.

La CI esegue un handshake deterministico per entrambi i server (nessun browser, nessun dispositivo):
`TEZGAH_E2E_STRICT=1 python3 tests/e2e_analyze_wiring.py`. Due smoke test locali opt-in si spingono oltre:
`TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_web.py` avvia Playwright MCP,
naviga e legge lo snapshot senza screenshot;
`TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_mobile.py` avvia Mobile MCP, controlla
gli strumenti dell'albero delle viste ed elenca un dispositivo. Stampano `SKIP: ...` quando node, una
build del browser o un dispositivo mancano.

<a id="install"></a>

## Installazione

Richiede Python 3.8+. node + npm sono necessari per l'host dsh e, con `pnpm`,
per la sua riga di stato web. Le integrazioni opzionali degradano in modo elegante:
`codebase-memory-mcp` nel PATH alimenta il grafo; una chiave del modello alimenta `consult`
e `codegen` — OpenRouter per impostazione predefinita (`OPENROUTER_API_KEY` o
`~/.config/openrouter/key`), o l'API DeepSeek con `--provider deepseek`
(`DEEPSEEK_API_KEY` o `~/.config/deepseek/key`); e `orx` di OpenResearch
nel PATH dà alla regola di ricerca qualcosa da guidare. Quando la chiave del provider scelto
manca, tezgah lo comunica invece di fingere.

Clona, quindi arma ogni host rilevato in un solo passaggio:

```bash
git clone https://github.com/r1z4x/tezgah.git ~/Projects/tezgah
cd ~/Projects/tezgah
bin/tezgah-setup --install
```

In un terminale, quel comando senza argomenti è invece la procedura guidata di
installazione: chiede quali host armare, le directory radice, se installare gli strumenti
opzionali mancanti e se collegare il DevTools MCP opzionale, stampa il piano e scrive solo
dopo un sì. I flag sono i valori predefiniti della procedura guidata, quindi `--wizard
--hosts omp` chiede solo il resto. Un'esecuzione in pipe, da un agente o in CI non riceve
mai una richiesta — stampa il report, esattamente come prima.

`--install` installa anche gli strumenti opzionali mancanti eseguendo l'installer di ciascun
fornitore **tramite rete**: `orx` (`openresearch.sh/install.sh`), `cursor-agent`
(`cursor.com/install`), `dsh` (il suo profilo home tramite `npx`) e `pnpm` quando dsh ne ha
bisogno (tramite `npm`) — `curl ... | sh` incluso. Nessuno richiede sudo; l'esecuzione viene
registrata in `~/.config/tezgah/install.log`. Visualizza un'anteprima con `--dry-run`,
saltalo con `--no-deps` (utile in CI), o installa solo gli strumenti con `--deps`. Gli
strumenti finiscono in `~/.local/bin` o `~/.cargo/bin`, quindi potrebbe essere necessaria
una nuova shell prima che siano nel PATH; i controlli di tezgah cercano comunque in quelle
directory, quindi una shell non interattiva
li segnala comunque come presenti.

Se è già presente una configurazione precedente, importala prima — viene spostata,
non eliminata:

```bash
bin/tezgah-setup --adopt
```

Claude Code si installa attraverso il proprio canale dei plugin:

```bash
claude plugin marketplace add ~/Projects/tezgah
claude plugin install tezgah@rizacan-local
```

Limita l'installazione esplicitamente quando necessario:

```bash
bin/tezgah-setup --install --hosts omp
bin/tezgah-setup --install --hosts claude,codex,cursor,opencode,dsh
bin/tezgah-setup --roots ~/work:~/oss --install
```

<a id="day-to-day"></a>

## Uso quotidiano

Niente da eseguire: le regole si caricano all'avvio di un host. Vale la pena conoscere alcuni comandi:

| Comando | Scopo |
|---|---|
| `bin/tezgah-setup` | In un terminale: la procedura guidata di installazione; in una pipe o in CI: riporta cosa è armato, per host |
| `bin/tezgah-setup --wizard` | Forza la procedura guidata di installazione ovunque; `--report` forza il report |
| `bin/tezgah-status [PATH]` | Mostra se le regole sono attive in quella repo |
| `bin/tezgah-setup --status [PATH]` | Stampa la checklist armata/usata |
| `bin/tezgah-setup --deps [--dry-run]` | Installa gli strumenti opzionali mancanti (orx, cursor-agent, dsh) |
| `bin/tezgah-research init\|check\|status` | Crea e verifica una linea di ricerca: stato, findings, claim e la regola protocollo-prima-dei-risultati |
| `bin/tezgah-doctor [--clean] [--prune-sessions DAYS]` | Riporta l'uso del disco dell'harness; `--clean` elimina i vecchi log dell'indice ed esegue il vacuum del DB di opencode; `--prune-sessions` elimina le sessioni inattive (l'unica azione che riduce effettivamente il DB) |
| `/tezgah:plan-add` | Trasforma un lavoro in un piano tracciato |
| `/tezgah:plan-status` | Riepiloga i piani aperti e sceglie il successivo |
| `/tezgah:plan-sync` | Chiude i piani completati |
| `bin/tezgah-setup --version` | Stampa la versione del plugin |
| `bin/tezgah-setup --uninstall` | Rimuove solo i link simbolici di tezgah, le voci degli hook dell'host e il blocco gestito di dsh |

<a id="configuration"></a>

## Configurazione

Tezgah è armato solo sotto le sue root configurate; ovunque altrove è silenzioso.

- Root predefinita: `~/Projects`.
- `~/.config/tezgah/config.json`: `{"roots": ["~/Projects", "~/work"]}`.
- `TEZGAH_ROOTS` (lista separata dal separatore di percorso) sovrascrive il file per esecuzioni una tantum e CI.

I kill switch risiedono in `~/.config/tezgah/`. Ognuno rimuove la propria regola dal
testo iniettato nella sessione, in modo che la regola si fermi effettivamente:

| Switch | Disattiva |
|---|---|
| `exec-mode.off` | Report in turco, orientati al risultato |
| `ponytail-auto.off` | la regola del codice minimo |
| `spec-off` | la regola delle specifiche prima della costruzione |
| `consult-off` | la regola della seconda opinione esterna |
| `research-off` | l'instradamento delle attività di ricerca verso OpenResearch |
| `orchestrate-off` | la delega ai subagenti (aggiunge una riga di non delega) |
| `reminder-off` | il testo di promemoria per ogni turno |
| `pretooluse-off` | il gate PreToolUse stesso (attribuzione, explorer, nudge per grep) |

Per ogni repo, `.no-ponytail`, `.no-cbm` e `.no-lessons` disattivano rispettivamente la regola del codice minimo,
la regola del grafo del codice (e la sua auto-indicizzazione) e il registro delle lezioni.

Quando l'utente segnala un errore, l'agente aggiunge una lezione di una riga a `.tezgah/lessons.md` della repo;
le righe più recenti vengono iniettate all'avvio della sessione in modo che lo
stesso errore non possa ripetersi silenziosamente.

<a id="benchmark"></a>

## Benchmark

Questo contratto migliora il lavoro, o fa solo finta di doverlo fare? Lo si misura in
`benchmarks/arm-bench/`, non lo si afferma: controlli nascosti di cui l'agente non vede mai
il test, costo dal registro d'uso dell'host stesso, e modifiche collaterali conteggiate come
fallimenti. `PREREGISTRATION.md` fissa gli endpoint prima di una esecuzione e `python3
bench.py report` li stampa; lo studio completo, con gli id di esecuzione, è
`docs/research/2026-09-16-tezgah-quality.md`. Ogni cifra qui sotto è un registro di
esecuzione.

| Blocco | Esecuzioni | Cosa ha stabilito |
|---|---|---|
| due host, 28 attività, k=3 | 336 | `omp+tezgah` 0.95 e `opencode+tezgah` 0.96 hanno intervalli sovrapposti e lo stesso costo per attività risolta; sui bracci nudi omp costa meno ($0.0047 contro $0.0074 CPS), quindi il driver quotidiano è omp senza alcun costo in qualità |
| famiglia difficile, 5 attività, k=5, due famiglie di modelli | 200 | in pool, tre dei quattro bracci finiscono su 40/50: nessun effetto dell'harness a quella dimensione, e l'unico segnale prodotto dal primo modello si è invertito sul secondo |
| famiglia del gate, gate armato | 36 | nessun braccio ha preso la via della scorciatoia; il meccanismo del gate è verificato direttamente (una modifica di skip viene rifiutata), il suo effetto sul lavoro non è ancora misurato |
| ablazione di clausola, le due regole che separano, k=8 | 160 | i bracci con contratto passano 23/32 (0.72) contro 12/32 (0.38) dell'ancora nuda |

**Aiuta esattamente dove il default del modello è sbagliato.** `c04` (un prompt in inglese
dove solo il contratto rende la risposta in turco) legge 9/16 con un contratto e 0/16 senza;
`h02` (un contratto sul denaro la cui suite visibile è verde in entrambi i casi) legge 14/16
contro 12/16. Dove non c'è alcun divario da colmare - 22 delle 25 attività pilota sono
passate sotto ogni braccio a ogni ripetizione - un benchmark può solo riportare un nullo.

**Sono due clausole a portarlo.** Rimuovere la clausola 1 porta `c04` a 0/8, il punteggio
dell'ancora nuda stessa, muovendo appena `h02`. Rimuovere la clausola 3 porta `h02` a 2/8 -
sotto il 6/8 dell'ancora nuda - perché la clausola 3 vieta di fermarsi al percorso più breve
che sembra fatto, e su quell'attività il percorso più breve è il one-liner che passa la
suite visibile violando la regola documentata. Le clausole 2 e 4 non muovono nulla di
misurabile.

**Il costo segue la qualità.** Per attività risolta: $0.0078 contro $0.0097 sul nodo
contratto completo, $0.0043 contro $0.0087 sul nodo senza ponytail. I bracci con contratto
risolvono più attività, quindi ogni attività risolta costa meno; la spesa totale è più alta,
e il benchmark la registra riga per riga invece di compensarla.

Cosa questo non mostra: la qualità del codice, lo sforzo di revisione o la manutenibilità,
nulla dei quali è misurato qui; l'effetto del gate sulle scelte di un braccio, poiché nessun
braccio ha cercato la scorciatoia in 36 esecuzioni armate; né un *ordine* delle clausole -
`k=8` fissa una direzione, a 8 esecuzioni per cella. Un solo fornitore e un solo pacchetto
di fixture per tutto il tempo, e i giri di ablazione girano su una sola famiglia di modelli.
Una seconda famiglia di modelli riproduce esattamente il nullo delle 28 attività (51/56
contro 51/56), ed è questo che mostra che la prima lettura non era un artefatto del modello.

<a id="cost"></a>

## Costi

Misurati su questa macchina (macOS, Python 3.10), non stimati. `tezgah-setup` stampa il
budget in tempo reale - leggilo lì invece di fidarti di una cifra copiata qui, cosa che ha
portato una revisione precedente a citare una banda core più piccola di quella che installa.

| Banda | Quanto costa |
|---|---|
| Avvio della sessione | il contratto sempre attivo (gli invarianti più un puntatore di una riga per ogni regola on-demand): su questa macchina e con questo set di skill, ~1.3k token di testo del contratto e ~1.3k di metadati delle skill, con le regole condizionali (spec, consult, research, graph) che aggiungono ~0.6k solo sul turno il cui prompt corrisponde |
| Per turno | un breve promemoria (~0.2k token) più la regola armata quando corrisponde; gli hook sono processi Python separati, quindi l'avvio dell'interprete di ~19 ms è la base - un turno aggiunge ~31 ms, l'avvio della sessione aggiunge ~50-81 ms, una chiamata a uno strumento con gate (Bash/Grep/Task) ~24-25 ms. opencode non ha hook al momento del prompt, quindi paga zero |
| On demand | la skill completa `tezgah-contract` (~6.0k token), pagata solo quando un'attività la carica |
| Schemi MCP | la banda più grande, e quella che nessun report statico vede: il solo server del grafo dichiara 15 strumenti / 24,508 byte (~6.1k token), presenti in ogni richiesta a meno che l'host non recuperi gli schemi on demand. `tezgah-setup --mcp-schemas` lo misura |
| Disco | l'installazione richiede ~58 ms, e ogni file che tezgah riscrive viene conservato una volta come `<file>.tezgah-bak` |

**Il pavimento dell'armamento.** Gli invarianti sono sempre attivi - modalità di esecuzione,
ponytail, deliver-the-whole-ask, integrità, disciplina del ciclo, il registro delle lezioni
e il divieto di attribuzione - e la regola di sicurezza («le azioni irreversibili o rivolte
all'esterno richiedono una richiesta esplicita prima») è una di esse, quindi non dipende mai
da un classificatore. Ogni regola consultiva mantiene sempre attivo un puntatore di una riga
azionabile, quindi una corrispondenza mancata costa dettaglio, mai la regola, e un hook
dell'host che fallisce ripiega sui puntatori più la skill on demand invece che su nessun
contratto. I falsi negativi sono verificabili: ogni prompt accoda `armed=<rules|none>
chars=<n>` - nessun testo del prompt - a `~/.cache/tezgah/classify.log` (troncato alle
ultime 200 righe oltre i 64 KB), e tutti e cinque gli host con hook armano lo stesso set per
lo stesso prompt (`tests/test_context.py::ArmingConformance`).

**opencode è armato diversamente.** Non ha alcun punto di iniezione al momento del prompt,
quindi il contratto viene fornito come file di istruzioni generato, e il suo router sempre
attivo elenca solo i bucket a cui una sessione di codice fa ricorso, riducendo il resto a un
puntatore a `~/.config/tezgah/opencode-skills.full.md` letto on demand; `permission.skill =
deny` impedisce a opencode di iniettare invece i metadati di ogni skill. `--install` imposta
anche `compaction.prune` e `watcher.ignore`, cancellando i vecchi risultati degli strumenti
dal prompt invece di reinviarli a ogni passo - senza questo il working set cresce fino a
centinaia di migliaia di token prima che opencode si auto-compatti vicino al limite del
modello (circa 980k per un modello da 1M di token). `bin/tezgah-doctor` riporta l'impronta
su disco e `--prune-sessions DAYS` elimina le sessioni inattive tramite la CLI di opencode,
l'unica azione che riduce davvero il database, perché il solo VACUUM non può.

**Perché conviene.** In una repo reale un `grep` predefinito ha ignorato la cartella
rilevante e non ha trovato nulla; con l'ignore disabilitato ha impiegato 3.95 s e ha
comunque mescolato definizioni e siti di chiamata, mentre il grafo del codice ha risposto
alla stessa domanda in 16 ms con gli 8 veri siti di chiamata.

<a id="development"></a>

## Sviluppo

```bash
python3 -m unittest discover -s tests -v   # stdlib test suite
pip install -r requirements-dev.txt        # pinned ruff, the only dev dep
ruff check .                               # lint (config in pyproject.toml)
```

La CI viene eseguita sia su Python 3.10 che 3.12. Per aggiornare una copia installata di Claude da
questo checkout, usa `bin/tezgah-setup --sync`, e convalida il manifest con
`claude plugin validate .claude-plugin/plugin.json`. Quando si incrementa la versione,
aggiorna `.claude-plugin/plugin.json` e `.claude-plugin/marketplace.json`
insieme — devono corrispondere.

`codebase-memory-mcp` viene installato dall'utente. Gli hook e i file di Orca non
fanno parte di questo progetto e vengono lasciati intatti. Claude riceve il nucleo always-on
dall'hook SessionStart; `output-styles/tezgah.md` è un duplicato per le build
che caricano gli stili di output dei plugin, quindi l'hook è il percorso autorevole.

<a id="contributing"></a>

## Contribuire

Le modifiche piccole e con un unico scopo sono le più facili da accettare. Una regola appartiene al
nucleo condiviso (`hooks/`) a meno che non sia genuinamente specifica per un host; una differenza dell'host
appartiene al suo adattatore sotto `hosts/<name>/`. Mantieni il diff il più breve possibile
pur rimanendo corretto — la regola del codice minimo del progetto si applica al progetto stesso.

Prima di aprire una pull request, esegui gli stessi tre controlli che esegue la CI:

```bash
python3 -m compileall -q hooks hosts bin statusline.py   # byte-compile every script
python3 -m unittest discover -s tests                     # stdlib test suite
ruff check .                                              # lint; config in pyproject.toml
```

`ruff` proviene da `requirements-dev.txt` (`pip install -r requirements-dev.txt`),
che è l'unica dipendenza di sviluppo.

<a id="security"></a>

## Sicurezza

Segnala le vulnerabilità privatamente tramite gli avvisi di sicurezza di GitHub
(scheda **Security** → **Report a vulnerability**) piuttosto che con una issue pubblica.

tezgah esegue hook di shell, scrive la configurazione dell'host e inietta testo in ogni
sessione, quindi qualsiasi cosa che faccia eseguire a un hook codice controllato da un attaccante, faccia trapelare
una chiave in un file di configurazione, allarghi una sandbox o permetta al contenuto della repository di intensificarsi
in testo di istruzioni è in scope. Includi l'host, la versione di tezgah
(`bin/tezgah-setup --version`) e una riproduzione minima.

<a id="license"></a>

## Licenza

Il file `LICENSE` (MIT) nella root copre i file propri di tezgah. `skills/ponytail` e
`skills/no-ai-slop` sono forniti (vendored) sotto i propri termini MIT, registrati in
`NOTICE`.
