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
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue?style=flat-square"></a>
  <a href="https://github.com/r1z4x/tezgah/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/badge/ci-GitHub%20Actions-informational?style=flat-square"></a>
</p>

<p align="center">
  <a href="#what-it-enforces">Cosa impone</a> &bull;
  <a href="#supported-hosts">Host supportati</a> &bull;
  <a href="#install">Installazione</a> &bull;
  <a href="#day-to-day">Uso quotidiano</a> &bull;
  <a href="#configuration">Configurazione</a> &bull;
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

| Host | Collegato tramite | Riga di stato |
|---|---|---|
| **Claude Code** | marketplace dei plugin locale: hook, comandi, due agenti in sola lettura, stile di output | `statusLine` nativa |
| **opencode** | plugin + istruzioni + MCP + router di skill generato (lista di skill nativa negata), auto-indicizzazione della repo al primo messaggio | plugin TUI (nessuna statusLine per i comandi) |
| **Codex** | `hooks.json` + skill + MCP, incluso un gate `PreToolUse` | hook `systemMessage` (la lista degli elementi nel footer è chiusa) |
| **Cursor** | `hooks.json` + skill + MCP | `statusLine` in `cli-config.json` |
| **dsh** | bridge per hook di Claude Code + blocco patch gestito (hook, MCP, rotte LLM, una riga di stato Web out-of-tree) | plugin Web UI: `tezgah-dsh-statusline` nell'intestazione della sessione |

Il gate di Codex esegue Bash, `exec_command`, `apply_patch`, Edit/Write, strumenti MCP,
e chiamate ai subagenti attraverso lo stesso controllo degli altri host. Su Claude, il
divieto di attribuzione viene applicato anche meccanicamente: l'impostazione `attribution` viene
svuotata (`commit`, `pr`, `sessionUrl`) in modo che i crediti per commit e PR siano disattivati alla
fonte.

### Riga di stato

Ogni host renderizza la stessa checklist su una riga da `tezgah-status`, in modo che
non possano divergere. Lo stato è il punto focale: un segno è **verde** quando la regola è armata
e in vigore in questa sessione, **giallo** quando è armata ma su richiesta (non ancora usata),
e **rosso** quando un kill switch l'ha disattivata. `idx` riporta la prontezza del grafo
separatamente (`✓` indicizzato, `↻` obsoleto, `✗` non indicizzato, `–` non applicabile) e
`plans N (M blk)` i piani aperti. `tezgah-status --legend` stampa la legenda,
`--json` fornisce gli stessi segmenti per una UI, e `--no-color` (o `NO_COLOR`)
forza il testo normale. Claude Code e Cursor colorano la riga di stato nativa; la
TUI di opencode colora il proprio componente e si aggiorna sul bus degli eventi dell'host; la
Web UI di dsh colora il suo componente di intestazione e si aggiorna solo mentre la sua scheda è
visibile; Codex mostra la stringa semplice in `systemMessage`.

dsh esegue gli stessi file hook di Claude attraverso il suo bridge `dsh-hooks-claude-code`,
quindi il contratto di inizio sessione, il gate di attribuzione e il nudge per il primo grep
si applicano tutti anche lì. dsh espone un singolo strumento `subagent`, quindi il rifiuto di
grep-only-explorer è inerte — non c'è alcun subagente explorer da rifiutare. La sandbox
predefinita `workspace-write` di dsh confina i sottoprocessi degli hook al workspace e
alla directory temporanea della piattaforma, quindi tezgah scrive il suo stato degli hook (segni di nudge, timbro dell'indice) in
un fallback scrivibile lì piuttosto che fallire su una scrittura negata. Il worker dell'indice del grafo
non può scrivere la cache di `codebase-memory-mcp` dall'interno di quella sandbox, quindi
il launcher `dsh` riscalda l'indice nella shell non confinata dell'utente prima di avviare
dsh — una nuova repo viene indicizzata esattamente come sugli altri host, con il timbro di HEAD. Una
sessione avviata senza il launcher riceve comunque un report chiaro che il
server MCP non in sandbox serve il grafo e necessita di `index_repository` per una repo
che non ha indicizzato, invece di un grezzo `EPERM`. Il blocco patch gestito
dichiara anche due rotte LLM compatibili con OpenAI sull'adattatore pi-ai montato dalla
composizione di base: `openrouter` (`OPENROUTER_API_KEY`) e `deepseek`
(`DEEPSEEK_API_KEY`), selezionabili insieme al predefinito nativo `deepseek-official`.
Le chiavi si risolvono dall'ambiente di avvio o dall'archivio credenziali dell'harness;
nessuna delle due chiavi entra nel file di configurazione. tezgah-setup inserisce anche un launcher `dsh`
nel PATH (`~/.local/bin/dsh`) che trova la CLI installata sotto
`$DSH_HOME`, in modo che `dsh --profile web` funzioni da qualsiasi directory.

dsh non ha una riga di stato per i comandi, quindi tezgah ne fornisce una come plugin per la Web UI:
`tezgah-dsh-statusline`. La sua metà host serve la stringa `tezgah-status` per il
workspace della sessione su una rotta autenticata `/api/tezgah.status` (con
`?format=json` per la vista colorata); la sua metà browser la renderizza nell'intestazione della sessione,
colorata in base allo stato con una legenda al passaggio del mouse/clic, e si aggiorna solo mentre la
scheda è visibile. `tezgah-setup`
collega il plugin nel profilo web e lo abilita con una riga gestita in
`profiles/web/cordis.patch.yml` (solo web, perché la metà host inietta il
servizio `connection` che è solo web); un profilo che non ha mai avviato `web` viene saltato
con un suggerimento invece di essere scritto a metà. In modalità `headless`, il bridge degli hook
inietta il contratto SessionStart come proprio turno finale (il suo `agent/session-start`
chiama `agent.inject()` in modo distaccato, dopo che l'attività one-shot è già il primo messaggio),
quindi `dsh --profile headless "<task>"` spende un turno extra e, per un
prompt a risposta letterale, stampa la reazione del modello al contratto piuttosto che
la risposta all'attività; le sessioni web interattive non ne sono influenzate.

`bin/tezgah-setup --install` attiva anche `orx install-skills` per Claude,
Codex, opencode e Cursor quando `orx` è nel PATH, in modo che la regola di ricerca abbia un
manuale da caricare. I file shim appartengono a orx, quindi tezgah esegue solo quell'installer
e non li elenca mai per la disinstallazione. dsh non ha un harness orx; la regola di ricerca
lì ripiega su `orx skill` nella shell.

Il plugin di Claude fornisce anche due agenti in sola lettura. `agents/tezgah-explorer.md`
esegue la scoperta del codice dal grafo e restituisce prove `file:line`;
`agents/tezgah-reviewer.md` trasforma un diff nel suo set di impatto con
`detect_changes` e poi cerca difetti reali. Entrambi hanno gli strumenti di scrittura e di comando
disabilitati; il loro output è consultivo.

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

`--install` installa anche gli strumenti opzionali mancanti eseguendo l'installer di
ciascun fornitore **tramite rete**: `orx`
(`openresearch.sh/install.sh`), `cursor-agent` (`cursor.com/install`), `dsh`
(il suo profilo home tramite `npx`) e `pnpm` quando dsh ne ha bisogno (tramite `npm`) —
`curl ... | sh` incluso. Nessuno richiede sudo; l'esecuzione viene registrata in
`~/.config/tezgah/install.log`. Visualizza un'anteprima con `--dry-run`, saltalo con
`--no-deps` (utile in CI), o installa solo gli strumenti con `--deps`. Gli strumenti finiscono
in `~/.local/bin` o `~/.cargo/bin`, quindi potrebbe essere necessaria una nuova shell prima
che siano nel PATH; i controlli di tezgah cercano comunque in quelle directory, quindi una shell non interattiva
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
bin/tezgah-setup --install --hosts claude,codex,opencode,cursor,dsh
bin/tezgah-setup --roots ~/work:~/oss --install
```

<a id="day-to-day"></a>

## Uso quotidiano

Niente da eseguire: le regole si caricano all'avvio di un host. Vale la pena conoscere alcuni comandi:

| Comando | Scopo |
|---|---|
| `bin/tezgah-setup` | Riporta cosa è armato, per host |
| `bin/tezgah-status [PATH]` | Mostra se le regole sono attive in quella repo |
| `bin/tezgah-setup --status [PATH]` | Stampa la checklist armata/usata |
| `bin/tezgah-setup --deps [--dry-run]` | Installa gli strumenti opzionali mancanti (orx, cursor-agent, dsh) |
| `bin/tezgah-doctor [--clean] [--prune-sessions DAYS]` | Riporta l'uso del disco dell'harness; `--clean` elimina i vecchi log dell'indice ed esegue il vacuum del DB di opencode; `--prune-sessions` elimina le sessioni inattive (l'unica azione che riduce effettivamente il DB) |
| `/plan-add` | Trasforma un lavoro in un piano tracciato |
| `/plan-status` | Riepiloga i piani aperti e sceglie il successivo |
| `/plan-sync` | Chiude i piani completati |
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

<a id="cost"></a>

## Costi

Misurati su questa macchina (macOS, Python 3.10), non stimati:

- **Contesto.** L'avvio di una sessione inietta ~4,8 KB (~1,2k token) di testo del contratto.
  Su Codex un promemoria di 480 byte accompagna ogni turno; Claude e gli altri host non
  hanno hook per turno, quindi il loro costo per turno è zero. La skill completa `tezgah-contract`
  (~19,9k caratteri) viene pagata solo quando un'attività la carica. Su opencode il
  contratto viene fornito come file di istruzioni di ~5,5 KB. opencode inietterebbe altrimenti
  ~53 KB di testo con nome/descrizione/posizione delle skill nel prompt di sistema di ogni sessione;
  tezgah nega quella lista (`permission.skill = deny`) e fornisce invece un router di skill generato
  di ~16 KB, in modo che una skill venga trovata leggendo il suo percorso `SKILL.md` dal router.
- **Latenza.** Gli hook sono processi Python separati, quindi l'avvio dell'interprete di ~19 ms
  domina. Oltre a questo, l'avvio della sessione aggiunge ~25 ms, una chiamata a uno strumento con gate
  (Bash/Grep/Task) aggiunge ~9 ms, e il segmento Stop di Codex aggiunge ~15 ms per turno.
- **Disco.** L'installazione richiede ~58 ms e ogni file che tezgah riscrive viene conservato
  una volta come `<file>.tezgah-bak`.

Il vantaggio si manifesta sulle domande del chiamante. In una repo reale, un `grep` predefinito
ha ignorato la cartella rilevante e non ha trovato nulla; con l'ignore disabilitato ha impiegato
3,95 s e ha comunque mescolato le definizioni con i siti di chiamata. Il grafo del codice ha risposto
alla stessa domanda in 16 ms, elencando solo gli 8 veri siti di chiamata.

opencode è armato anche per l'igiene del contesto nelle sessioni lunghe: `tezgah-setup --install`
imposta `compaction.prune` in modo che i vecchi risultati degli strumenti vengano cancellati dal prompt
invece di essere reinviati a ogni passaggio, e una lista `watcher.ignore` tiene il file watcher
fuori da `.git`, `node_modules` e dalle directory di build. Entrambi si uniscono — un valore esplicito dell'utente
vince. Questo è importante perché opencode esegue l'auto-compattazione solo vicino al limite di contesto del modello
(per un modello da 1M di token, circa 980k), quindi senza la potatura il working set
cresce fino a centinaia di migliaia di token. `bin/tezgah-doctor` riporta
l'impronta su disco risultante; `--prune-sessions DAYS` elimina le sessioni inattive
tramite la CLI di opencode, che è l'unica azione che riduce effettivamente il database —
VACUUM da solo non può farlo, poiché le sue pagine sono tutte attive.

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
