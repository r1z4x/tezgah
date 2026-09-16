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

<h3 align="center">Én fungerende kontrakt for hver AI-kodningsassistent, du kører.</h3>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/github/license/r1z4x/tezgah?style=flat-square"></a>
  <a href="https://github.com/r1z4x/tezgah/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/r1z4x/tezgah/ci.yml?style=flat-square&label=ci"></a>
</p>

<p align="center">
  <a href="#what-it-enforces">Hvad den håndhæver</a> &bull;
  <a href="#supported-hosts">Understøttede værter</a> &bull;
  <a href="#install">Installation</a> &bull;
  <a href="#day-to-day">Daglig brug</a> &bull;
  <a href="#configuration">Konfiguration</a> &bull;
  <a href="#cost">Omkostninger</a> &bull;
  <a href="#development">Udvikling</a> &bull;
  <a href="#contributing">Bidrag</a> &bull;
  <a href="#security">Sikkerhed</a> &bull;
  <a href="#license">Licens</a>
</p>

<p align="center"><sub>Engelsk er kilden til sandhed; oversættelser kan være bagefter.</sub></p>

---

Én fungerende kontrakt for hver AI-kodningsassistent, du kører — Claude Code,
opencode, Codex, Cursor og DeepSeeks dsh-harness — inden for et sæt
konfigurerede repository-rødder.

Overladt til sig selv har hver assistent sine egne vaner: én svarer på tyrkisk, en anden
på engelsk; én grepper efter alt, en anden forespørger i en kodegraf; én siger
"færdig" uden at køre en test. Tezgah fjerner denne afvigelse. Åbn en hvilken som helst vært, og
du får det samme sprog, den samme disciplin og den samme bevisstandard.

Designet består af to lag. Reglerne findes én gang i en delt kerne; hver vært får
en tynd adapter, der oversætter denne kerne til det format, værten forstår.
Ændr en regel ét sted, og alle fem værter ser det — ingen femdobbelt kopi af
den samme tekst.

<a id="what-it-enforces"></a>

## Hvad den håndhæver

- **Resultat-først tyrkisk rapportering.** Hvert svar er på tyrkisk og starter med
  resultatet eller beslutningen (BLUF), derefter punkter ordnet efter indvirkning. Kode, commits,
  dokumentation og underagent-prompter forbliver på engelsk; navne, CLI-kommandoer og fejltekster
  oversættes aldrig.
- **Minimal kode (ponytail).** Den mest dovne ændring, der rent faktisk virker: YAGNI,
  genbrug derefter en eksisterende hjælper, derefter stdlib, derefter en indbygget platformsfunktion,
  derefter en installeret afhængighed, derefter én linje. Ingen uanmodede abstraktioner.
  Validering, fejlhåndtering og sikkerhed bliver aldrig forsimplet væk.
- **Kodegraf-først opdagelse.** "Hvor er X", "hvem kalder Y", "hvad går i stykker, hvis
  Z ændres" går til `codebase-memory-mcp`-grafen (`search_graph`,
  `trace_path`, `search_code`), ikke til grep. Grep forbliver det rigtige valg til bogstavelig tekst,
  konfigurationer og ikke-kodefiler.
- **Tilgængelighed-først app-analyse.** En kørende web- eller mobilapp læses
  gennem dens tilgængeligheds- / DOM- / native view-træ, ikke et skærmbillede pr. trin.
  `analyze-app` dækker en browser (Playwright MCP), en iOS Simulator eller Android-emulator
  (Mobile MCP) og valgfri webdiagnostik (Chrome DevTools MCP); et
  skærmbillede er en eksplicit handling på anmodning for det, træet ikke kan besvare.
- **Ekstern second opinion.** Før en ikke-triviel eller svær-at-omgøre beslutning,
  spørger `~/.config/tezgah/bin/consult` uafhængige modeller gennem OpenRouter (eller DeepSeek API
  med `--provider deepseek`) parallelt, og agenten rapporterer, hvor de var
  enige eller uenige.
- **Forskning via OpenResearch.** Når routeren vurderer, at en opgave er forskning — en
  litteraturgennemgang, opstilling og test af hypoteser, kørsel af eksperimenter, en
  forskningsartefakt — driver den arbejdet gennem alphaXivs OpenResearch (`orx`)
  og indlæser `orx`-manualen først, i stedet for at improvisere protokollen. Almindelig
  kodeopdagelse forbliver på kodegrafen. Når `orx` mangler, siger routeren det
  og falder tilbage til en værtsunderagent.
- **Ærlighed under verifikation.** Intet rapporteres som færdigt, testet eller rettet,
  medmindre outputtet blev set. En fejlende test rapporteres som fejlende med dens
  nøjagtige fejl, og et sprunget tjek angives tydeligt.
- **Ingen AI-tilskrivning, nogen steder.** Intet, der gemmes eller udgives — commit-,
  merge- og tag-beskeder, PR- og issue-tekst, kodekommentarer, filhoveder, dokumentation
  — må kreditere assistenten, modellen, leverandøren eller "AI". Det er fint at bruge et værktøj;
  at sætte dets navn på dit arbejde er ikke.
- **To-lags orkestrering.** Hovedtråden beslutter og verificerer; en billig
  model (`~/.config/tezgah/bin/codegen`, OpenRouter som standard eller `--provider deepseek`) udarbejder
  afgrænsede, veldefinerede ændringer til en midlertidig mappe. Intet når repositoryet
  undtagen gennem routeren, og et mislykket udkast falder automatisk tilbage til hovedmodellen.
- **Underagenter pr. repo.** Ved sessionsstart får det omsluttende repo et lille sæt af
  kapacitetsbegrænsede agenter (`tezgah-explorer`, `tezgah-reviewer`,
  `tezgah-researcher`, `tezgah-verifier`) plus en `tezgah-orchestrator`, gengivet
  i hver installeret værts native overflade (Claude/Cursor `.claude/agents/`,
  opencode `.opencode/agents/` plus en live konfigurationsindsættelse, Codex
  `.codex/agents/`) og ignoreret med én administreret `.gitignore`-blok. På Claude træder
  orkestratorens `Agent(tezgah-*)`-tilladelsesliste kun i kraft, når den kører som
  hovedtråd (`claude --agent tezgah-orchestrator`); som underagent ignoreres listen.
  dsh har ingen overflade pr. rolle, så kontraktens routerregel dækker den.

<a id="supported-hosts"></a>

## Understøttede værter

| Vært | Forbundet via | Statuslinje |
|---|---|---|
| **Claude Code** | lokal plugin-markedsplads: hooks, kommandoer, to skrivebeskyttede agenter, output-stil | indbygget `statusLine` |
| **opencode** | plugin + instruktioner + MCP + genereret skill-router (indbygget skill-liste afvist), repo auto-indeksering ved første besked | TUI-plugin (ingen kommando-statusLine) |
| **Codex** | `hooks.json` + skills + MCP, inklusive en `PreToolUse`-port | hook `systemMessage` (sidefodens elementliste er lukket) |
| **Cursor** | `hooks.json` + skills + MCP | `statusLine` i `cli-config.json` |
| **dsh** | Claude Code hook-bro + administreret patch-blok (hooks, MCP, LLM-ruter, en out-of-tree Web-statuslinje) | Web UI-plugin: `tezgah-dsh-statusline` i sessionshovedet |

Codex-porten kører Bash, `exec_command`, `apply_patch`, Edit/Write, MCP-værktøjer,
og underagentkald gennem det samme tjek som de andre værter. På Claude håndhæves
tilskrivningsforbuddet også mekanisk: `attribution`-indstillingen tømmes
(`commit`, `pr`, `sessionUrl`), så commit- og PR-krediteringer er slået fra ved kilden.

### Statuslinje

Hver vært gengiver den samme én-linjes tjekliste fra `tezgah-status`, så de
ikke kan afvige. Tilstanden er pointen: et mærke er **grønt**, når reglen er aktiveret
og gældende i denne session, **gult**, når den er aktiveret men på anmodning (endnu ikke brugt),
og **rødt**, når en kill switch har slået den fra. `idx` rapporterer graf-parathed
separat (`✓` indekseret, `↻` forældet, `✗` ikke indekseret, `–` ikke relevant) og
`plans N (M blk)` de åbne planer. `tezgah-status --legend` udskriver nøglen,
`--json` giver de samme segmenter til en brugergrænseflade, og `--no-color` (eller `NO_COLOR`)
gennemtvinger almindelig tekst. Claude Code og Cursor farvelægger den indbyggede statuslinje;
opencode TUI farvelægger sin egen komponent og opdaterer på værtens hændelsesbus;
dsh Web UI farvelægger sin header-komponent og opdaterer kun, mens dens fane er
synlig; Codex viser den rene streng i `systemMessage`.

dsh kører de samme Claude hook-filer gennem sin `dsh-hooks-claude-code`-bro,
så sessionsstart-kontrakten, tilskrivningsporten og first-grep-nudget gælder alle der.
dsh eksponerer et enkelt `subagent`-værktøj, så grep-only-explorer-afvisningen er
inaktiv — der er ingen explorer-underagent, den kan afvise. dsh's standard
`workspace-write`-sandbox begrænser hook-underprocesser til arbejdsområdet og
platformens midlertidige mappe, så tezgah skriver sin hook-tilstand (nudge-mærker, indeksstempel) til
en skrivbar fallback der i stedet for at fejle på en afvist skrivning. Graf-indeks-arbejderen
kan ikke skrive til `codebase-memory-mcp`-cachen indefra den sandbox, så
`dsh`-launcheren varmer indekset op i brugerens ubegrænsede shell, før dsh startes —
et nyt repo indekseres nøjagtigt som på de andre værter, HEAD-stemplet. En
session startet uden launcheren får stadig en klar rapport om, at den
ikke-sandboxede MCP-server betjener grafen og har brug for `index_repository` til et repo,
den ikke har indekseret, i stedet for en rå `EPERM`. Den administrerede
patch-blok erklærer også to OpenAI-kompatible LLM-ruter på pi-ai-adapteren,
som basiskompositionen monterer: `openrouter` (`OPENROUTER_API_KEY`) og `deepseek`
(`DEEPSEEK_API_KEY`), som kan vælges sammen med den indbyggede `deepseek-official`-standard.
Nøgler løses fra startmiljøet eller harness-legitimationslageret; ingen af nøglerne
indgår i konfigurationsfilen. tezgah-setup placerer også en `dsh`-launcher i PATH (`~/.local/bin/dsh`),
der finder det installerede CLI under `$DSH_HOME`, så `dsh --profile web` fungerer fra enhver mappe.

dsh har ingen kommando-statuslinje, så tezgah leverer en som et Web UI-plugin:
`tezgah-dsh-statusline`. Dets værtshalvdel serverer `tezgah-status`-strengen for
sessionens arbejdsområde over en godkendt `/api/tezgah.status`-rute (med
`?format=json` for den farvelagte visning); dets browserhalvdel gengiver den i sessionshovedet,
farvelagt efter tilstand med en hover/klik-forklaring, og opdaterer kun, mens fanen er synlig. `tezgah-setup`
linker pluginet ind i web-profilen og aktiverer det med en administreret række i
`profiles/web/cordis.patch.yml` (kun web, fordi værtshalvdelen injicerer den
web-specifikke `connection`-tjeneste); en profil, der aldrig har startet `web`, springes over
med et tip i stedet for at blive halvt skrevet. I `headless`-tilstand injicerer hooks-broen
SessionStart-kontrakten som sin egen afsluttende tur (dens `agent/session-start`
kalder `agent.inject()` frakoblet, efter at engangsopgaven allerede er den første
besked), så `dsh --profile headless "<task>"` bruger én ekstra tur og, for en
bogstavelig-svar-prompt, udskriver modellens reaktion på kontrakten i stedet for
opgavens svar; interaktive web-sessioner påvirkes ikke.

`bin/tezgah-setup --install` udløser også `orx install-skills` for Claude,
Codex, opencode og Cursor, når `orx` er i PATH, så forskningsreglen har en
manual at indlæse. Shim-filerne tilhører orx, så tezgah kører kun det installationsprogram
og lister dem aldrig til afinstallation. dsh har intet orx-harness; forskningsreglen
der falder tilbage til `orx skill` i shellen.

Claude-pluginet leverer også to skrivebeskyttede agenter. `agents/tezgah-explorer.md`
udfører kodeopdagelse fra grafen og returnerer `file:line`-beviser;
`agents/tezgah-reviewer.md` omdanner en diff til dens indvirkningssæt med
`detect_changes` og leder derefter efter reelle fejl. Begge har skrive- og kommandoværktøjer
deaktiveret; deres output er vejledende.

### App-analyse

`analyze-app` driver en kørende applikation fra dens tilgængelighedstræ. Den
standardløkken er åbn, læs træet, handl, observer konsol/netværk/logs, og
genlæs træet — et skærmbillede er en eksplicit handling for det, træet ikke kan
besvare (canvas, spil, animation, visuel regression på pixelniveau). Skillen er
én sti for alle værter; serverne under den er én delt specifikation i
`hooks/tezgah_apps.py`:

| Server | Mål | Forbundet via |
|---|---|---|
| `playwright` (`@playwright/mcp`) | websider, `browser_*`-værktøjer | opencode, Codex, Cursor, Claude (plugin `.mcp.json`) |
| `mobile-mcp` (`@mobilenext/mobile-mcp`) | iOS Simulator / Android-emulator, `mobile_*`-værktøjer | samme |
| `chrome-devtools` (tilvalg, `--devtools`) | web-ydeevnespor, dybt netværk, source-mapped konsol | samme |

Browseren kører en **isoleret** profil som standard, så en kørsel rører aldrig
din rigtige Chrome-tilstand; at analysere et indlogget flow er en bevidst tilslutning
(`--cdp-endpoint` eller Playwright-udvidelsen), ikke en standard. Skærmbilleder,
spor og træ-dumps lander i `~/.cache/tezgah/apps` (overskriv med
`TEZGAH_ARTIFACTS`), og agenten får en sti tilbage, aldrig indlejrede billedbytes.
Serverne kører gennem `npx`, så de kræver node, men ingen egen installation;
`tezgah-setup --install --devtools` tilføjer den valgfrie webdiagnostik-server.
dsh forbinder de samme to servere gennem sin `dsh-mcp-client`-bro
(`serverName` / `command` / `args` / `env`, bekræftet mod det offentliggjorte
konfigurationsskema), og Claude får dem fra pluginets `.mcp.json`
(`claude plugin details tezgah` lister MCP-servere 2 og begge forbinder).
`mobile-mcp` er halvdelen med højere friktion: macOS kan anmode om tilladelse til Tilgængelighed /
Skærmoptagelse, og view-træet kan falde ud under belastning, så skillen
prøver træet igen, før den falder tilbage til et skærmbillede.

CI kører et deterministisk håndtryk for begge servere (ingen browser, ingen enhed):
`TEZGAH_E2E_STRICT=1 python3 tests/e2e_analyze_wiring.py`. To valgfrie lokale
røgtest går videre: `TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_web.py` starter
Playwright MCP, navigerer og læser øjebliksbilledet uden skærmbillede;
`TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_mobile.py` starter Mobile MCP, tjekker
view-træ-værktøjerne og lister en enhed. De udskriver `SKIP: ...`, når node, et
browser-build eller en enhed mangler.

<a id="install"></a>

## Installation

Kræver Python 3.8+. node + npm er nødvendige for dsh-værten og, med `pnpm`,
for dens web-statuslinje. De valgfrie integrationer nedgraderes yndefuldt:
`codebase-memory-mcp` i PATH driver grafen; en modelnøgle driver `consult`
og `codegen` — OpenRouter som standard (`OPENROUTER_API_KEY` eller
`~/.config/openrouter/key`), eller DeepSeek API med `--provider deepseek`
(`DEEPSEEK_API_KEY` eller `~/.config/deepseek/key`); og OpenResearchs `orx` i
PATH giver forskningsreglen noget at drive. Når den valgte udbyders nøgle
mangler, siger tezgah det i stedet for at lade som om.

Klon, og aktiver derefter hver registreret vært i én arbejdsgang:

```bash
git clone https://github.com/r1z4x/tezgah.git ~/Projects/tezgah
cd ~/Projects/tezgah
bin/tezgah-setup --install
```

`--install` installerer også de valgfrie værktøjer, der mangler, ved at køre hver
leverandørs eget installationsprogram **over netværket**: `orx`
(`openresearch.sh/install.sh`), `cursor-agent` (`cursor.com/install`), `dsh`
(dens hjemmeprofil gennem `npx`), og `pnpm` når dsh har brug for det (via `npm`) —
`curl ... | sh` inkluderet. Ingen kræver sudo; kørslen registreres i
`~/.config/tezgah/install.log`. Få en forhåndsvisning med `--dry-run`, spring det over med
`--no-deps` (nyttigt i CI), eller installer værktøjerne alene med `--deps`. Værktøjer lander
i `~/.local/bin` eller `~/.cargo/bin`, så en ny shell kan være nødvendig, før de
er i PATH; tezgahs egne tjek kigger i disse mapper uanset hvad, så en ikke-interaktiv
shell rapporterer dem stadig som tilstedeværende.

Hvis en tidligere opsætning allerede er til stede, skal du importere den først — den flyttes til side,
ikke slettes:

```bash
bin/tezgah-setup --adopt
```

Claude Code installeres gennem sin egen plugin-kanal:

```bash
claude plugin marketplace add ~/Projects/tezgah
claude plugin install tezgah@rizacan-local
```

Begræns installationen eksplicit, når det er nødvendigt:

```bash
bin/tezgah-setup --install --hosts claude,codex,opencode,cursor,dsh
bin/tezgah-setup --roots ~/work:~/oss --install
```

<a id="day-to-day"></a>

## Daglig brug

Intet at køre: reglerne indlæses, når en vært starter. Et par kommandoer er værd at
kende:

| Kommando | Formål |
|---|---|
| `bin/tezgah-setup` | Rapporter, hvad der er aktiveret, pr. vært |
| `bin/tezgah-status [PATH]` | Vis, om reglerne er aktive i det repo |
| `bin/tezgah-setup --status [PATH]` | Udskriv den aktiverede/brugte tjekliste |
| `bin/tezgah-setup --deps [--dry-run]` | Installer manglende valgfrie værktøjer (orx, cursor-agent, dsh) |
| `bin/tezgah-doctor [--clean] [--prune-sessions DAYS]` | Rapporter harness-diskforbrug; `--clean` sletter gamle indekslogs og støvsuger opencode-databasen; `--prune-sessions` sletter inaktive sessioner (den eneste handling, der rent faktisk krymper databasen) |
| `/plan-add` | Gør et stykke arbejde til en sporet plan |
| `/plan-status` | Opsummer åbne planer og vælg den næste |
| `/plan-sync` | Afslut færdige planer |
| `bin/tezgah-setup --version` | Udskriv plugin-versionen |
| `bin/tezgah-setup --uninstall` | Fjern kun tezgahs symlinks, værtens hook-poster og den dsh-administrerede blok |

<a id="configuration"></a>

## Konfiguration

Tezgah er kun aktiveret under sine konfigurerede rødder; alle andre steder er den tavs.

- Standardrod: `~/Projects`.
- `~/.config/tezgah/config.json`: `{"roots": ["~/Projects", "~/work"]}`.
- `TEZGAH_ROOTS` (sti-separator-liste) overskriver filen for engangstilfælde og CI.

Kill switches findes i `~/.config/tezgah/`. Hver af dem fjerner sin regel fra den
tekst, der injiceres i sessionen, så reglen rent faktisk stopper:

| Switch | Slår fra |
|---|---|
| `exec-mode.off` | Tyrkisk, resultat-først rapportering |
| `ponytail-auto.off` | reglen om minimal kode |
| `spec-off` | reglen om specifikation-før-bygning |
| `consult-off` | reglen om ekstern second opinion |
| `research-off` | dirigering af forskningsopgaver til OpenResearch |
| `orchestrate-off` | underagent-delegering (tilføjer en deleger-ikke-linje) |
| `reminder-off` | påmindelsesteksten pr. tur |
| `pretooluse-off` | selve PreToolUse-porten (tilskrivning, explorer, grep-nudge) |

Pr. repo slår `.no-ponytail`, `.no-cbm` og `.no-lessons` henholdsvis reglen om minimal kode,
kodegraf-reglen (og dens auto-indeksering) og lektionsbogen fra.

Når brugeren markerer en fejl, tilføjer agenten en én-linjes lektion til repoets
`.tezgah/lessons.md`; de seneste linjer injiceres ved sessionsstart, så den
samme fejl ikke kan gentage sig i stilhed.

<a id="cost"></a>

## Omkostninger

Målt på denne maskine (macOS, Python 3.10), ikke estimeret:

- **Kontekst.** En sessionsstart injicerer ~4,8 KB (~1,2k tokens) kontrakttekst.
  På Codex følger en 480-byte påmindelse med hver tur; Claude og de andre værter har
  ingen hook pr. tur, så deres omkostning pr. tur er nul. Den fulde `tezgah-contract`-skill
  (~19,9k tegn) betales kun, når en opgave indlæser den. På opencode leveres
  kontrakten som en ~5,5 KB instruktionsfil. opencode ville ellers
  injicere ~53 KB tekst med skill-navn/beskrivelse/placering i hver sessions
  systemprompt; tezgah afviser den liste (`permission.skill = deny`) og leverer
  i stedet en genereret ~16 KB skill-router, så en skill findes ved at læse dens
  `SKILL.md`-sti fra routeren.
- **Forsinkelse.** Hooks er separate Python-processer, så fortolkerens start på ~19 ms
  dominerer. Oven i det tilføjer sessionsstart ~25 ms, et portstyret værktøjskald
  (Bash/Grep/Task) tilføjer ~9 ms, og Codex's Stop-segment tilføjer ~15 ms pr. tur.
- **Disk.** Installation tager ~58 ms, og hver fil, tezgah overskriver, gemmes
  én gang som `<file>.tezgah-bak`.

Gevinsten viser sig ved opkalder-spørgsmål. I et virkeligt repo ignorerede en standard `grep`
den relevante mappe og fandt intet; med ignorering deaktiveret tog det
3,95 s og blandede stadig definitioner med kaldssteder. Kodegrafen besvarede det
samme spørgsmål på 16 ms og listede kun de 8 sande kaldssteder.

opencode er også aktiveret for konteksthygiejne i lange sessioner: `tezgah-setup --install`
indstiller `compaction.prune`, så gamle værktøjsresultater ryddes fra prompten i stedet for
at blive sendt igen ved hvert trin, og en `watcher.ignore`-liste holder filovervågeren
ude af `.git`, `node_modules` og build-mapper. Begge flettes — en eksplicit brugerværdi
vinder. Dette er vigtigt, fordi opencode kun auto-komprimerer nær modellens kontekstgrænse
(for en 1M-token model, omkring 980k), så uden beskæring vokser arbejdssættet
til hundredtusindvis af tokens. `bin/tezgah-doctor` rapporterer det
resulterende diskaftryk; `--prune-sessions DAYS` sletter inaktive sessioner gennem
opencode CLI, hvilket er den eneste handling, der rent faktisk krymper databasen —
VACUUM alene kan ikke, da dens sider alle er aktive.

<a id="development"></a>

## Udvikling

```bash
python3 -m unittest discover -s tests -v   # stdlib test suite
pip install -r requirements-dev.txt        # pinned ruff, the only dev dep
ruff check .                               # lint (config in pyproject.toml)
```

CI kører både på Python 3.10 og 3.12. For at opdatere en installeret Claude-kopi fra
dette checkout, brug `bin/tezgah-setup --sync`, og valider manifestet med
`claude plugin validate .claude-plugin/plugin.json`. Når versionen hæves, skal
`.claude-plugin/plugin.json` og `.claude-plugin/marketplace.json` opdateres
sammen — de skal stemme overens.

`codebase-memory-mcp` installeres af brugeren. Orcas hooks og filer er ikke
en del af dette projekt og efterlades urørte. Claude modtager den altid-aktive kerne
fra SessionStart-hooket; `output-styles/tezgah.md` er en dublet til builds,
der indlæser plugin-output-stile, så hooket er den autoritative sti.

<a id="contributing"></a>

## Bidrag

Små ændringer med et enkelt formål er de nemmeste at acceptere. En regel hører til i den
delte kerne (`hooks/`), medmindre den er ægte værtsspecifik; en værtsforskel
hører til i dens adapter under `hosts/<name>/`. Hold diff'en så kort som den kan
være, mens den stadig er korrekt — projektets egen regel om minimal kode gælder for
projektet.

Før du åbner en pull request, skal du køre de samme tre tjek, som CI kører:

```bash
python3 -m compileall -q hooks hosts bin statusline.py   # byte-compile every script
python3 -m unittest discover -s tests                     # stdlib test suite
ruff check .                                              # lint; config in pyproject.toml
```

`ruff` kommer fra `requirements-dev.txt` (`pip install -r requirements-dev.txt`),
som er den eneste udviklingsafhængighed.

<a id="security"></a>

## Sikkerhed

Rapporter sårbarheder privat gennem GitHubs sikkerhedsmeddelelser
(fanen **Security** → **Report a vulnerability**) i stedet for et offentligt issue.

tezgah kører shell-hooks, skriver værtskonfiguration og injicerer tekst i hver
session, så alt, der får et hook til at udføre angriberkontrolleret kode, lækker en
nøgle i en konfigurationsfil, udvider en sandbox eller lader repository-indhold eskalere
til instruktionstekst, er inden for rækkevidde. Inkluder værten, tezgah-versionen
(`bin/tezgah-setup --version`) og en minimal reproduktion.

<a id="license"></a>

## Licens

Rodfilen `LICENSE` (MIT) dækker tezgahs egne filer. `skills/ponytail` og
`skills/no-ai-slop` er leveret under deres egne MIT-vilkår, registreret i
`NOTICE`.
