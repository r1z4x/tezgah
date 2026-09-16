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

<h3 align="center">Én fungerende kontrakt for hver AI-kodeassistent du kjører.</h3>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/github/license/r1z4x/tezgah?style=flat-square"></a>
  <a href="https://github.com/r1z4x/tezgah/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/r1z4x/tezgah/ci.yml?style=flat-square&label=ci"></a>
  <a href="https://github.com/r1z4x/tezgah/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/r1z4x/tezgah?style=flat-square"></a>
</p>

<p align="center">
  <a href="#what-it-enforces">Hva den håndhever</a> &bull;
  <a href="#supported-hosts">Støttede verter</a> &bull;
  <a href="#install">Installasjon</a> &bull;
  <a href="#day-to-day">Daglig bruk</a> &bull;
  <a href="#configuration">Konfigurasjon</a> &bull;
  <a href="#cost">Kostnad</a> &bull;
  <a href="#development">Utvikling</a> &bull;
  <a href="#contributing">Bidra</a> &bull;
  <a href="#security">Sikkerhet</a> &bull;
  <a href="#license">Lisens</a>
</p>

<p align="center"><sub>Engelsk er kilden til sannhet; oversettelser kan henge etter.</sub></p>

---

Én fungerende kontrakt for hver AI-kodeassistent du kjører — Claude Code,
opencode, Codex, Cursor, og DeepSeeks dsh-rammeverk — innenfor et sett med
konfigurerte kodelagerrøtter.

Overlatt til seg selv har hver assistent sine egne vaner: én svarer på tyrkisk, en annen
på engelsk; én bruker grep for alt, en annen gjør oppslag i en kodegraf; én sier
"ferdig" uten å kjøre en test. Tezgah fjerner dette avviket. Åpne hvilken som helst vert, og
du får det samme språket, den samme disiplinen og den samme bevisstandarden.

Designet består av to lag. Reglene lever én gang i en delt kjerne; hver vert får
en tynn adapter som oversetter denne kjernen til det formatet verten forstår.
Endre en regel på ett sted, og alle fem verter ser det — ingen femdobbel kopi av
den samme teksten.

<a id="what-it-enforces"></a>

## Hva den håndhever

- **Resultat-først tyrkisk rapportering.** Hvert svar er på tyrkisk og starter med
  resultatet eller beslutningen (BLUF), deretter punkter sortert etter påvirkning. Kode, commits,
  dokumentasjon og underagent-prompter forblir på engelsk; navn, CLI-kommandoer og feilstrenger
  oversettes aldri.
- **Minimal kode (ponytail).** Den lateste endringen som faktisk fungerer: YAGNI,
  deretter gjenbruk av en eksisterende hjelpefunksjon, deretter stdlib, deretter en innebygd plattformfunksjon,
  deretter en installert avhengighet, deretter én linje. Ingen uønskede abstraksjoner.
  Validering, feilhåndtering og sikkerhet forenkles aldri bort.
- **Kodegraf-først oppdagelse.** "Hvor er X", "hvem kaller Y", "hva ødelegges hvis
  Z endres" går til `codebase-memory-mcp`-grafen (`search_graph`,
  `trace_path`, `search_code`), ikke til grep. Grep forblir riktig for bokstavelig tekst,
  konfigurasjoner og filer som ikke er kode.
- **Tilgjengelighet-først app-analyse.** En kjørende web- eller mobilapp leses
  gjennom dens tilgjengelighets- / DOM- / native visningstre, ikke et skjermbilde per trinn.
  `analyze-app` dekker en nettleser (Playwright MCP), en iOS-simulator eller Android-emulator
  (Mobile MCP), og valgfri webdiagnostikk (Chrome DevTools MCP); et skjermbilde er en
  eksplisitt, behovsstyrt handling for det treet ikke kan svare på.
- **Ekstern vurdering (second opinion).** Før en ikke-triviell eller vanskelig reverserbar beslutning,
  spør `~/.config/tezgah/bin/consult` uavhengige modeller gjennom OpenRouter (eller DeepSeek API
  med `--provider deepseek`) parallelt, og agenten rapporterer hvor de var
  enige eller uenige.
- **Forskning via OpenResearch.** Når ruteren vurderer at en oppgave er forskning — en
  litteraturgjennomgang, utforming og testing av hypoteser, kjøring av eksperimenter, en
  forskningsartefakt — driver den arbeidet gjennom alphaXivs OpenResearch (`orx`)
  og laster `orx`-manualen først, i stedet for å improvisere protokollen. Ren
  kodeoppdagelse forblir på kodegrafen. Når `orx` mangler, sier ruteren ifra om
  dette og faller tilbake til en vert-underagent.
- **Ærlighet under verifisering.** Ingenting rapporteres som ferdig, testet eller fikset
  med mindre utdataene ble sett. En feilende test rapporteres som feilende med sin
  nøyaktige feilmelding, og en hoppet over sjekk oppgis tydelig.
- **Ingen AI-kreditering, noe sted.** Ingenting som lagres eller publiseres — commit-,
  merge- og tag-meldinger, PR- og issue-tekst, kodekommentarer, filhoder, dokumentasjon
  — kan kreditere assistenten, modellen, leverandøren eller "AI". Å bruke et verktøy er greit;
  å signere dets navn på arbeidet ditt er ikke det.
- **To-lags orkestrering.** Hovedtråden beslutter og verifiserer; en billig
  modell (`~/.config/tezgah/bin/codegen`, OpenRouter som standard eller `--provider deepseek`) utformer
  begrensede, velspesifiserte endringer til en midlertidig mappe (scratch directory). Ingenting når kodelageret
  unntatt gjennom ruteren, og et mislykket utkast faller automatisk tilbake til hovedmodellen.
- **Underagenter per kodelager.** Ved oppstart av en økt får det omsluttende kodelageret et lite sett med
  evne-begrensede agenter (`tezgah-explorer`, `tezgah-reviewer`,
  `tezgah-researcher`, `tezgah-verifier`) pluss en `tezgah-orchestrator`, gjengitt
  i hver installerte verts opprinnelige overflate (Claude/Cursor `.claude/agents/`,
  opencode `.opencode/agents/` pluss en live konfigurasjonsinjeksjon, Codex
  `.codex/agents/`) og ignorert med én administrert `.gitignore`-blokk. På Claude trer
  orkestratorens `Agent(tezgah-*)`-hviteliste bare i kraft når den kjører som
  hovedtråd (`claude --agent tezgah-orchestrator`); som underagent ignoreres listen.
  dsh har ingen overflate per rolle, så kontraktens ruter-regel dekker den.

<a id="supported-hosts"></a>

## Støttede verter

| Vert | Koblet via | Statuslinje |
|---|---|---|
| **Claude Code** | lokal plugin-markedsplass: hooks, kommandoer, to skrivebeskyttede agenter, utdatastil | innebygd `statusLine` |
| **opencode** | plugin + instruksjoner + MCP + generert ferdighetsruter (innebygd ferdighetsliste nektet), repo auto-indeksering på første melding | TUI-plugin (ingen kommando-statusLine) |
| **Codex** | `hooks.json` + ferdigheter + MCP, inkludert en `PreToolUse`-port | hook `systemMessage` (bunntekstens elementliste er lukket) |
| **Cursor** | `hooks.json` + ferdigheter + MCP | `statusLine` i `cli-config.json` |
| **dsh** | Claude Code hook-bro + administrert patch-blokk (hooks, MCP, LLM-ruter, en out-of-tree Web-statuslinje) | Web UI-plugin: `tezgah-dsh-statusline` i økthodet |

Codex-porten kjører Bash, `exec_command`, `apply_patch`, Edit/Write, MCP-verktøy,
og underagent-kall gjennom den samme sjekken som de andre vertene. På Claude håndheves også
krediteringsforbudet mekanisk: `attribution`-innstillingen tømmes (`commit`, `pr`, `sessionUrl`)
slik at commit- og PR-krediteringer er slått av ved kilden.

### Statuslinje

Hver vert gjengir den samme én-linjes sjekklisten fra `tezgah-status`, slik at de
ikke kan avvike. Tilstanden er poenget: et merke er **grønt** når regelen er aktivert
og gjeldende i denne økten, **gult** når den er aktivert men på forespørsel (ikke brukt
ennå), og **rødt** når en nødstopp-bryter (kill switch) har slått den av. `idx` rapporterer graf-beredskap
separat (`✓` indeksert, `↻` utdatert, `✗` ikke indeksert, `–` ikke aktuelt)
og `plans N (M blk)` de åpne planene. `tezgah-status --legend` skriver ut nøkkelen,
`--json` gir de samme segmentene for et brukergrensesnitt, og `--no-color` (eller `NO_COLOR`)
tvinger frem ren tekst. Claude Code og Cursor fargelegger den innebygde statuslinjen;
opencode TUI fargelegger sin egen komponent og oppdateres på vertens hendelsesbuss;
dsh Web UI fargelegger sin overskriftskomponent og oppdateres bare mens fanen er
synlig; Codex viser den rene strengen i `systemMessage`.

dsh kjører de samme Claude hook-filene gjennom sin `dsh-hooks-claude-code`-bro,
så øktoppstart-kontrakten, krediteringsporten og første-grep-påminnelsen (nudge)
gjelder alle der. dsh eksponerer et enkelt `subagent`-verktøy, så avslaget for grep-only-explorer
er inaktivt — det er ingen explorer-underagent for den å avvise. dshs standard
`workspace-write`-sandkasse begrenser hook-underprosesser til arbeidsområdet og
plattformens midlertidige mappe, så tezgah skriver sin hook-tilstand (påminnelsesmerker, indeksstempel) til
en skrivbar reserve der i stedet for å feile på en nektet skriving. Graf-indeksarbeideren
kan ikke skrive til `codebase-memory-mcp`-hurtigbufferen fra innsiden av den sandkassen, så
`dsh`-oppstarteren varmer opp indeksen i brukerens ubegrensede skall før dsh startes
— et nytt kodelager indekseres nøyaktig som på de andre vertene, HEAD-stemplet. En
økt startet uten oppstarteren får fortsatt en tydelig rapport om at den
usandkassede MCP-serveren betjener grafen og trenger `index_repository` for et kodelager
den ikke har indeksert, i stedet for en rå `EPERM`. Den administrerte
patch-blokken deklarerer også to OpenAI-kompatible LLM-ruter på pi-ai-adapteren
som basiskomposisjonen monterer: `openrouter` (`OPENROUTER_API_KEY`) og `deepseek`
(`DEEPSEEK_API_KEY`), valgbare ved siden av den innebygde `deepseek-official`-standarden.
Nøkler løses fra oppstartsmiljøet eller rammeverkets legitimasjonslager;
ingen av nøklene legges inn i konfigurasjonsfilen. tezgah-setup legger også en `dsh`-oppstarter
på PATH (`~/.local/bin/dsh`) som finner det installerte CLI-et under
`$DSH_HOME`, slik at `dsh --profile web` fungerer fra hvilken som helst mappe.

dsh har ingen kommando-statuslinje, så tezgah leverer en som en Web UI-plugin:
`tezgah-dsh-statusline`. Dens vertshalvdel serverer `tezgah-status`-strengen for
øktens arbeidsområde over en autentisert `/api/tezgah.status`-rute (med
`?format=json` for den fargelagte visningen); dens nettleserhalvdel gjengir den i
økthodet, fargelagt etter tilstand med en hover/klikk-forklaring, og oppdateres bare mens
fanen er synlig. `tezgah-setup`
lenker pluginen inn i web-profilen og aktiverer den med en administrert rad i
`profiles/web/cordis.patch.yml` (kun for web, fordi vertshalvdelen injiserer den
web-eksklusive `connection`-tjenesten); en profil som aldri har startet `web` hoppes over
med et hint i stedet for å bli halvskrevet. I `headless`-modus injiserer hooks-broen
SessionStart-kontrakten som sin egen avsluttende tur (dens `agent/session-start`
kaller `agent.inject()` frakoblet, etter at engangsoppgaven allerede er den første
meldingen), så `dsh --profile headless "<task>"` bruker én ekstra tur og, for en
bokstavelig-svar-prompt, skriver ut modellens reaksjon på kontrakten i stedet for
oppgavens svar; interaktive web-økter påvirkes ikke.

`bin/tezgah-setup --install` utløser også `orx install-skills` for Claude,
Codex, opencode og Cursor når `orx` er på PATH, slik at forskningsregelen har en
manual å laste. Shim-filene tilhører orx, så tezgah kjører bare det installasjonsprogrammet
og lister dem aldri for avinstallasjon. dsh har ikke noe orx-rammeverk; forskningsregelen
der faller tilbake til `orx skill` i skallet.

Claude-pluginen leverer også to skrivebeskyttede agenter. `agents/tezgah-explorer.md`
utfører kodeoppdagelse fra grafen og returnerer `file:line`-bevis;
`agents/tezgah-reviewer.md` gjør en diff om til sitt påvirkningssett med
`detect_changes` og ser deretter etter reelle feil. Begge har skrive- og kommandoverktøy
deaktivert; deres utdata er rådgivende.

### App-analyse

`analyze-app` driver en kjørende applikasjon fra dens tilgjengelighetstre. Den
standardløkken er åpen, les treet, handle, observer konsoll/nettverk/logger, og
les treet på nytt — et skjermbilde er en eksplisitt handling for det treet ikke kan
svare på (canvas, spill, animasjon, visuell regresjon på pikselnivå). Ferdigheten er
én sti for alle verter; serverne under den er én delt spesifikasjon i
`hooks/tezgah_apps.py`:

| Server | Mål | Koblet via |
|---|---|---|
| `playwright` (`@playwright/mcp`) | nettsider, `browser_*`-verktøy | opencode, Codex, Cursor, Claude (plugin `.mcp.json`) |
| `mobile-mcp` (`@mobilenext/mobile-mcp`) | iOS-simulator / Android-emulator, `mobile_*`-verktøy | samme |
| `chrome-devtools` (valgfri, `--devtools`) | web-ytelsessporinger, dypt nettverk, kildekartlagt konsoll | samme |

Nettleseren kjører en **isolert** profil som standard, så en kjøring rører aldri din
virkelige Chrome-tilstand; å analysere en innlogget flyt er en bevisst tilkobling
(`--cdp-endpoint` eller Playwright-utvidelsen), ikke en standard. Skjermbilder,
sporinger og tre-dumper havner i `~/.cache/tezgah/apps` (overstyr med
`TEZGAH_ARTIFACTS`) og agenten får en sti tilbake, aldri innebygde bilde-bytes.
Serverne kjører gjennom `npx`, så de trenger node, men ingen egen installasjon;
`tezgah-setup --install --devtools` legger til den valgfrie webdiagnostikk-serveren.
dsh kobler de samme to serverne gjennom sin `dsh-mcp-client`-bro
(`serverName` / `command` / `args` / `env`, bekreftet mot det publiserte
konfigurasjonsskjemaet), og Claude får dem fra pluginens `.mcp.json`
(`claude plugin details tezgah` lister opp MCP-servere 2 og begge kobler til).
`mobile-mcp` er halvdelen med høyere friksjon: macOS kan be om tillatelse for Tilgjengelighet /
Skjermopptak, og visningstreet kan falle ut under belastning, så ferdigheten
prøver treet på nytt før den faller tilbake til et skjermbilde.

CI kjører et deterministisk håndtrykk for begge servere (ingen nettleser, ingen enhet):
`TEZGAH_E2E_STRICT=1 python3 tests/e2e_analyze_wiring.py`. To valgfrie lokale
røyk-tester (smoke tests) går lenger: `TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_web.py` starter
Playwright MCP, navigerer og leser øyeblikksbildet uten skjermbilde;
`TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_mobile.py` starter Mobile MCP, sjekker
visningstre-verktøyene og lister opp en enhet. De skriver ut `SKIP: ...` når node, en
nettleser-bygg eller en enhet mangler.

<a id="install"></a>

## Installasjon

Krever Python 3.8+. node + npm trengs for dsh-verten og, med `pnpm`,
for dens web-statuslinje. De valgfrie integrasjonene degraderes grasiøst:
`codebase-memory-mcp` på PATH driver grafen; en modellnøkkel driver `consult`
og `codegen` — OpenRouter som standard (`OPENROUTER_API_KEY` eller
`~/.config/openrouter/key`), eller DeepSeek API med `--provider deepseek`
(`DEEPSEEK_API_KEY` eller `~/.config/deepseek/key`); og OpenResearchs `orx` på
PATH gir forskningsregelen noe å drive. Når den valgte leverandørens nøkkel
mangler, sier tezgah ifra om dette i stedet for å late som.

Klon, og aktiver deretter hver oppdagede vert i én omgang:

```bash
git clone https://github.com/r1z4x/tezgah.git ~/Projects/tezgah
cd ~/Projects/tezgah
bin/tezgah-setup --install
```

`--install` installerer også de valgfrie verktøyene som mangler ved å kjøre hver
leverandørs eget installasjonsprogram **over nettverket**: `orx`
(`openresearch.sh/install.sh`), `cursor-agent` (`cursor.com/install`), `dsh`
(dens hjemmeprofil gjennom `npx`), og `pnpm` når dsh trenger det (via `npm`) —
`curl ... | sh` inkludert. Ingen trenger sudo; kjøringen registreres i
`~/.config/tezgah/install.log`. Forhåndsvis med `--dry-run`, hopp over det med
`--no-deps` (nyttig i CI), eller installer verktøyene alene med `--deps`. Verktøy lander
i `~/.local/bin` eller `~/.cargo/bin`, så et nytt skall kan være nødvendig før
de er på PATH; tezgahs egne sjekker leter i disse mappene uansett, så et ikke-interaktivt
skall rapporterer dem fortsatt som til stede.

Hvis et tidligere oppsett allerede er til stede, importer det først — det flyttes til side,
ikke slettes:

```bash
bin/tezgah-setup --adopt
```

Claude Code installeres gjennom sin egen plugin-kanal:

```bash
claude plugin marketplace add ~/Projects/tezgah
claude plugin install tezgah@rizacan-local
```

Begrens installasjonen eksplisitt når det er nødvendig:

```bash
bin/tezgah-setup --install --hosts omp
bin/tezgah-setup --install --hosts claude,codex,cursor,opencode,dsh
bin/tezgah-setup --roots ~/work:~/oss --install
```

<a id="day-to-day"></a>

## Daglig bruk

Ingenting å kjøre: reglene lastes når en vert starter. Noen få kommandoer er verdt å
kjenne til:

| Kommando | Formål |
|---|---|
| `bin/tezgah-setup` | Rapporter hva som er aktivert, per vert |
| `bin/tezgah-status [PATH]` | Vis om reglene er aktive i det kodelageret |
| `bin/tezgah-setup --status [PATH]` | Skriv ut sjekklisten for aktivert/brukt |
| `bin/tezgah-setup --deps [--dry-run]` | Installer manglende valgfrie verktøy (orx, cursor-agent, dsh) |
| `bin/tezgah-doctor [--clean] [--prune-sessions DAYS]` | Rapporter rammeverkets diskbruk; `--clean` sletter gamle indekslogger og støvsuger (vacuums) opencode-databasen; `--prune-sessions` sletter inaktive økter (den eneste handlingen som faktisk krymper databasen) |
| `/plan-add` | Gjør et stykke arbeid om til en sporet plan |
| `/plan-status` | Oppsummer åpne planer og velg den neste |
| `/plan-sync` | Lukk ferdige planer |
| `bin/tezgah-setup --version` | Skriv ut plugin-versjonen |
| `bin/tezgah-setup --uninstall` | Fjern kun tezgahs symbolske lenker, vertens hook-oppføringer og den administrerte dsh-blokken |

<a id="configuration"></a>

## Konfigurasjon

Tezgah er kun aktivert under sine konfigurerte røtter; alle andre steder er den stille.

- Standardrot: `~/Projects`.
- `~/.config/tezgah/config.json`: `{"roots": ["~/Projects", "~/work"]}`.
- `TEZGAH_ROOTS` (baneseparator-liste) overstyrer filen for engangstilfeller og CI.

Nødstopp-brytere (kill switches) ligger i `~/.config/tezgah/`. Hver av dem fjerner sin regel fra
teksten som injiseres i økten, slik at regelen faktisk stopper:

| Bryter | Slår av |
|---|---|
| `exec-mode.off` | tyrkisk, resultat-først rapportering |
| `ponytail-auto.off` | regelen for minimal kode |
| `spec-off` | regelen for spesifikasjon-før-bygging |
| `consult-off` | regelen for ekstern vurdering (second opinion) |
| `research-off` | ruting av forskningsoppgaver til OpenResearch |
| `orchestrate-off` | underagent-delegering (legger til en ikke-deleger-linje) |
| `reminder-off` | påminnelsesteksten per tur |
| `pretooluse-off` | selve PreToolUse-porten (kreditering, explorer, grep-påminnelse) |

Per kodelager slår `.no-ponytail`, `.no-cbm` og `.no-lessons` av henholdsvis regelen for minimal kode,
kodegraf-regelen (og dens auto-indeks), og lærdomsregisteret (lessons ledger).

Når brukeren flagger en feil, legger agenten til en én-linjes lærdom i kodelagerets
`.tezgah/lessons.md`; de nyeste linjene injiseres ved øktoppstart slik at den
samme feilen ikke kan gjentas i stillhet.

<a id="cost"></a>

## Kostnad

Målt på denne maskinen (macOS, Python 3.10), ikke estimert:

- **Kontekst.** En øktoppstart injiserer ~5,4 KB (~1,3k tokens) med kontrakttekst.
  På Codex følger en 480-byte påminnelse med hver tur; Claude og de andre vertene har
  ingen hook per tur, så deres kostnad per tur er null. Den fulle `tezgah-contract`-ferdigheten
  (~19,9k tegn) betales bare når en oppgave laster den. På opencode leveres
  kontrakten som en ~5,8 KB instruksjonsfil. opencode ville ellers
  injisert tekst for ferdighetsnavn/-beskrivelse/-plassering i hver økts
  system-prompt; tezgah nekter den listen (`permission.skill = deny`) og leverer
  en generert ferdighetsruter i stedet, slik at en ferdighet finnes ved å lese dens
  `SKILL.md`-sti fra ruteren.
- **Forsinkelse (Latency).** Hooks er separate Python-prosesser, så oppstarten av tolken på ~19 ms
  dominerer. På toppen av dette legger øktoppstart til ~25 ms, et portstyrt verktøykall
  (Bash/Grep/Task) legger til ~9 ms, og Codex sitt Stop-segment legger til ~15 ms per tur.
- **Disk.** Installasjon tar ~58 ms og hver fil tezgah skriver om beholdes
  én gang som `<file>.tezgah-bak`.

Gevinsten viser seg på oppkallerspørsmål. I ett ekte kodelager ignorerte en standard `grep`
den relevante mappen og fant ingenting; med ignorering deaktivert tok det
3,95 s og blandet fortsatt definisjoner med kallsteder. Kodegrafen svarte på det
samme spørsmålet på 16 ms, og listet bare opp de 8 sanne kallstedene.

opencode er også utstyrt for konteksthygiene i lange økter: `tezgah-setup --install`
setter `compaction.prune` slik at gamle verktøyresultater fjernes fra prompten i stedet for
å bli sendt på nytt ved hvert trinn, og en `watcher.ignore`-liste holder filovervåkeren
ute av `.git`, `node_modules` og byggemapper. Begge flettes — en eksplisitt brukerverdi
vinner. Dette er viktig fordi opencode bare auto-komprimerer nær modellens kontekstgrense
(for en 1M-token modell, omtrent 980k), så uten beskjæring vokser arbeidssettet
til hundretusenvis av tokens. `bin/tezgah-doctor` rapporterer det
resulterende diskavtrykket; `--prune-sessions DAYS` sletter inaktive økter gjennom
opencode CLI, som er den eneste handlingen som faktisk krymper databasen —
VACUUM alene kan ikke det, siden sidene dens alle er levende.

<a id="development"></a>

## Utvikling

```bash
python3 -m unittest discover -s tests -v   # stdlib test suite
pip install -r requirements-dev.txt        # pinned ruff, the only dev dep
ruff check .                               # lint (config in pyproject.toml)
```

CI kjører både på Python 3.10 og 3.12. For å oppdatere en installert Claude-kopi fra
denne utsjekkingen, bruk `bin/tezgah-setup --sync`, og valider manifestet med
`claude plugin validate .claude-plugin/plugin.json`. Når du øker versjonen,
oppdater `.claude-plugin/plugin.json` og `.claude-plugin/marketplace.json`
sammen — de må stemme overens.

`codebase-memory-mcp` installeres av brukeren. Orcas hooks og filer er ikke
en del av dette prosjektet og forblir urørt. Claude mottar den alltid-på-kjernen
fra SessionStart-hooken; `output-styles/tezgah.md` er et duplikat for bygg
som laster plugin-utdatastiler, så hooken er den autoritative stien.

<a id="contributing"></a>

## Bidra

Små, enkle endringer med ett formål er de letteste å akseptere. En regel hører hjemme i den
delte kjernen (`hooks/`) med mindre den er genuint vertspesifikk; en vertsforskjell
hører hjemme i dens adapter under `hosts/<name>/`. Hold diffen så kort som den kan
være mens den fortsatt er riktig — prosjektets egen regel for minimal kode gjelder for
prosjektet.

Før du åpner en pull request, kjør de samme tre sjekkene som CI kjører:

```bash
python3 -m compileall -q hooks hosts bin statusline.py   # byte-compile every script
python3 -m unittest discover -s tests                     # stdlib test suite
ruff check .                                              # lint; config in pyproject.toml
```

`ruff` kommer fra `requirements-dev.txt` (`pip install -r requirements-dev.txt`),
som er den eneste utviklingsavhengigheten.

<a id="security"></a>

## Sikkerhet

Rapporter sårbarheter privat gjennom GitHubs sikkerhetsvarsler
(**Security**-fanen → **Report a vulnerability**) i stedet for en offentlig issue.

tezgah kjører skall-hooks, skriver vertskonfigurasjon og injiserer tekst i hver
økt, så alt som får en hook til å utføre angriper-kontrollert kode, lekker en
nøkkel inn i en konfigurasjonsfil, utvider en sandkasse, eller lar kodelagerinnhold eskalere
til instruksjonstekst er innenfor omfanget. Inkluder verten, tezgah-versjonen
(`bin/tezgah-setup --version`), og en minimal reproduksjon.

<a id="license"></a>

## Lisens

Rotfilen `LICENSE` (MIT) dekker tezgahs egne filer. `skills/ponytail` og
`skills/no-ai-slop` er inkludert (vendored) under sine egne MIT-vilkår, registrert i
`NOTICE`.
