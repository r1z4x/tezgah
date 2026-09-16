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
  <a href="#benchmark">Benchmark</a> &bull;
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

| Vert | Koblet via |
|---|---|
| **omp** (oh-my-pi) — primær | `~/.omp/agent`: administrert alltid-på-blokk `RULES.md`, ferdigheter, genererte underagenter, `mcp.json`, og en utvidelse (`hooks/pre/tezgah-hook.ts`) som armerer reglene per prompt, porter verktøy, registrerer bevis og kjører Stop-regelen; koblingen sjekkes av `tezgah-setup` |
| **Claude Code** | lokal plugin-markedsplass: hooks, kommandoer, to skrivebeskyttede agenter, utdatastil |
| **opencode** | plugin + instruksjoner + MCP + generert ferdighetsruter (innebygd ferdighetsliste nektet), repo auto-indeksering på første melding |
| **Codex** | `hooks.json` + ferdigheter + MCP, inkludert en `PreToolUse`-port |
| **Cursor** | `hooks.json` + ferdigheter + MCP |
| **dsh** | Claude Code hook-bro + administrert patch-blokk (hooks, MCP, LLM-ruter, en out-of-tree Web-statuslinje) |

Codex-porten kjører Bash, `exec_command`, `apply_patch`, Edit/Write, MCP-verktøy,
og underagent-kall gjennom den samme sjekken som de andre vertene. På Claude håndheves også
krediteringsforbudet mekanisk: `attribution`-innstillingen tømmes (`commit`, `pr`, `sessionUrl`)
slik at commit- og PR-krediteringer er slått av ved kilden.

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

I en terminal er den kommandoen uten argumenter installasjonsveiviseren i stedet: den spør
hvilke verter som skal armeres, rotkatalogene, om de manglende valgfrie verktøyene skal
installeres, og om den valgfrie DevTools MCP skal kobles til, skriver ut planen, og skriver
først etter et ja. Flaggene er veiviserens standardverdier, så `--wizard --hosts omp` spør
bare om resten. En kjøring i rør, fra en agent eller i CI blir aldri spurt — den skriver ut
rapporten, nøyaktig som før.

`--install` installerer også de valgfrie verktøyene som mangler ved å kjøre hver leverandørs
eget installasjonsprogram **over nettverket**: `orx` (`openresearch.sh/install.sh`),
`cursor-agent` (`cursor.com/install`), `dsh` (dens hjemmeprofil gjennom `npx`), og `pnpm`
når dsh trenger det (via `npm`) — `curl ... | sh` inkludert. Ingen trenger sudo; kjøringen
registreres i `~/.config/tezgah/install.log`. Forhåndsvis med `--dry-run`, hopp over det med
`--no-deps` (nyttig i CI), eller installer verktøyene alene med `--deps`. Verktøy lander i
`~/.local/bin` eller `~/.cargo/bin`, så et nytt skall kan være nødvendig før de er på PATH;
tezgahs egne sjekker leter i disse mappene uansett, så et ikke-interaktivt
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
| `bin/tezgah-setup` | I en terminal: installasjonsveiviseren; i et rør eller i CI: rapporter hva som er aktivert, per vert |
| `bin/tezgah-setup --wizard` | Tvinger installasjonsveiviseren overalt; `--report` tvinger rapporten |
| `bin/tezgah-status [PATH]` | Vis om reglene er aktive i det kodelageret |
| `bin/tezgah-setup --status [PATH]` | Skriv ut sjekklisten for aktivert/brukt |
| `bin/tezgah-setup --deps [--dry-run]` | Installer manglende valgfrie verktøy (orx, cursor-agent, dsh) |
| `bin/tezgah-research init\|check\|status` | Oppretter og sjekker en forskningslinje: tilstand, funn, påstander og regelen protokoll-før-resultater |
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

<a id="benchmark"></a>

## Benchmark

Forbedrer denne kontrakten arbeidet, eller ser den bare ut som om den burde det? Det måles i
`benchmarks/arm-bench/`, ikke påstås: skjulte kontroller som agenten aldri ser testen for,
kostnad fra vertens egen brukslogg, og sideordnede redigeringer som scores som feil.
`PREREGISTRATION.md` fastsetter endepunktene før en kjøring og `python3 bench.py report`
skriver dem ut; hele studien, med kjørings-id-ene, er
`docs/research/2026-09-16-tezgah-quality.md`. Hvert tall nedenfor er en kjøringslogg.

| Blokk | Kjøringer | Hva den fastslo |
|---|---|---|
| to verter, 28 oppgaver, k=3 | 336 | `omp+tezgah` 0.95 og `opencode+tezgah` 0.96 har overlappende intervaller og samme kostnad per løste oppgave; på de bare armene er omp billigere ($0.0047 mot $0.0074 CPS), så dagligdriveren er omp uten kostnad i kvalitet |
| hard familie, 5 oppgaver, k=5, to modellfamilier | 200 | samlet lander tre av de fire armene på 40/50: ingen harness-effekt ved den størrelsen, og det ene signalet den første modellen produserte, reverserte på den andre |
| port-familie, port armert | 36 | ingen arm tok snarveien; port-mekanismen er verifisert direkte (en skip-redigering avvises), effekten på arbeidet er ennå ikke målt |
| klausul-ablasjon, de to reglene som skiller, k=8 | 160 | kontraktarmene passerer 23/32 (0.72) mot den bare ankerens 12/32 (0.38) |

**Den hjelper nøyaktig der modellens standard er feil.** `c04` (en engelsk prompt der bare
kontrakten gjør svaret tyrkisk) leser 9/16 med en kontrakt og 0/16 uten; `h02` (en
pengekontrakt hvis synlige suite er grønn uansett) leser 14/16 mot 12/16. Der det ikke er
noe gap å lukke - 22 av de 25 pilotoppgavene passerte under hver arm på hver repetisjon -
kan en benchmark bare rapportere en null.

**To klausuler bærer den.** Å fjerne klausul 1 tar `c04` til 0/8, den bare ankerens egen
score, mens `h02` knapt beveges. Å fjerne klausul 3 tar `h02` til 2/8 - under den bare
ankerens 6/8 - fordi klausul 3 forbyr å stoppe ved den korteste ferdig-utseende stien, og på
den oppgaven er den korteste stien én-lineren som passerer den synlige suiten mens den
bryter den dokumenterte regelen. Klausul 2 og 4 beveger ingenting målbart.

**Kostnad følger kvalitet.** Per løste oppgave: $0.0078 mot $0.0097 på full-kontrakt-noden,
$0.0043 mot $0.0087 på minus-ponytail-noden. Kontraktarmene løser flere oppgaver, så hver
løste oppgave koster mindre; det totale forbruket er høyere, og benchmarken registrerer det
rad for rad i stedet for å nette det ut.

Hva dette ikke viser: kodekvalitet, gjennomgangsinnsats eller vedlikeholdbarhet, som ingen
av dem måles her; portens effekt på en arms valg, siden ingen arm grep etter snarveien i 36
armerte kjøringer; eller en klausul-*rekkefølge* - `k=8` fastsetter en retning, ved 8
kjøringer per celle. Én leverandør og én fixture-pakke gjennom alt, og ablasjonsrundene
kjører på én modellfamilie. En andre modellfamilie reproduserer 28-oppgave-nullen nøyaktig
(51/56 mot 51/56), og det er hva som viser at den første lesningen ikke var et
modellartefakt.

<a id="cost"></a>

## Kostnad

Målt på denne maskinen (macOS, Python 3.10), ikke estimert. `tezgah-setup` skriver ut det
levende budsjettet - les det der i stedet for å stole på et tall kopiert hit, som er hvordan
en tidligere revisjon kom til å oppgi en kjernebånd som er mindre enn den den installerer.

| Bånd | Hva det koster |
|---|---|
| Øktoppstart | den alltid-på-kontrakten (invariantene pluss en én-linjes peker per on-demand-regel): på denne maskinen og med dette ferdighetssettet, ~1.3k tokens kontraktstekst og ~1.3k ferdighetsmetadata, med de betingede reglene (spec, consult, research, graph) som legger til ~0.6k bare på turen hvis prompt matcher |
| Per tur | en kort påminnelse (~0.2k tokens) pluss den armerte regelen når den matcher; hooks er separate Python-prosesser, så oppstarten av tolken på ~19 ms dominerer - øktoppstart legger til ~25 ms, et portstyrt verktøykall (Bash/Grep/Task) ~9 ms. opencode har ingen hook ved prompt-tid, så den betaler null |
| On demand | den fulle `tezgah-contract`-ferdigheten (~6.0k tokens), betalt bare når en oppgave laster den |
| MCP-skjemaer | det største båndet, og det ingen statisk rapport ser: grafserveren alene erklærer 15 verktøy / 24,508 byte (~6.1k tokens), som rir på hver forespørsel med mindre verten henter skjemaer on demand. `tezgah-setup --mcp-schemas` måler det |
| Disk | installasjonen tar ~58 ms, og hver fil tezgah skriver om beholdes én gang som `<file>.tezgah-bak` |

**Armeringsgulvet.** Invariantene er alltid på - kjøringsmodus, ponytail,
deliver-the-whole-ask, integritet, løkkedisiplin, leksjonsloggen og krediteringsforbudet -
og sikkerhetsregelen («irreversible eller utadrettede handlinger krever et eksplisitt
spørsmål først») er en av dem, så den avhenger aldri av en klassifiserer. Hver rådgivende
regel holder en handlingsrettet én-linjes peker alltid på, så en tapt match koster detaljer,
aldri regelen, og en vertshook som feiler faller tilbake til pekerne pluss
on-demand-ferdigheten i stedet for til ingen kontrakt. Falske negativer er reviderbare: hver
prompt legger til `armed=<rules|none> chars=<n>` - ingen prompttekst - i
`~/.cache/tezgah/classify.log` (kuttet til de siste 200 linjene etter 64 KB), og alle fem
hook-verter armerer det samme settet for samme prompt
(`tests/test_context.py::ArmingConformance`).

**opencode armeres annerledes.** Den har ikke noe injeksjonspunkt ved prompt-tid, så
kontrakten leveres som en generert instruksjonsfil, og dens alltid-på-ruter lister bare
bøttene en kodingsøkt griper etter, og kollapser resten til en peker på
`~/.config/tezgah/opencode-skills.full.md` lest on demand; `permission.skill = deny` stopper
opencode fra å injisere hver ferdighets metadata i stedet. `--install` setter også
`compaction.prune` og `watcher.ignore`, som fjerner gamle verktøyresultater fra prompten i
stedet for å sende dem på nytt ved hvert trinn - uten det vokser arbeidssettet til
hundretusenvis av tokens før opencode auto-komprimerer nær modellens grense (omtrent 980k
for en 1M-token-modell). `bin/tezgah-doctor` rapporterer diskavtrykket og `--prune-sessions
DAYS` sletter inaktive økter gjennom opencode-CLI-en, den eneste handlingen som faktisk
krymper databasen, siden VACUUM alene ikke kan.

**Hvorfor det lønner seg.** I ett ekte kodelager ignorerte en standard `grep` den relevante
mappen og fant ingenting; med ignorering deaktivert tok det 3.95 s og blandet fortsatt
definisjoner med kallsteder, mens kodegrafen svarte på det samme spørsmålet på 16 ms med de
8 sanne kallstedene.

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
