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
  <a href="https://github.com/r1z4x/tezgah/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/r1z4x/tezgah?style=flat-square"></a>
</p>

<p align="center">
  <a href="#what-it-enforces">Hvad den håndhæver</a> &bull;
  <a href="#supported-hosts">Understøttede værter</a> &bull;
  <a href="#install">Installation</a> &bull;
  <a href="#day-to-day">Daglig brug</a> &bull;
  <a href="#configuration">Konfiguration</a> &bull;
  <a href="#benchmark">Benchmark</a> &bull;
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

| Vært | Forbundet via |
|---|---|
| **omp** (oh-my-pi) — primær | `~/.omp/agent`: administreret `RULES.md` altid-aktiv blok, skills, genererede underagenter, `mcp.json` og en udvidelse (`hooks/pre/tezgah-hook.ts`) der aktiverer reglerne pr. prompt, sætter værktøjer bag en port, registrerer evidens og kører Stop-reglen; wiringen kontrolleres af `tezgah-setup` |
| **Claude Code** | lokal plugin-markedsplads: hooks, kommandoer, to skrivebeskyttede agenter, output-stil |
| **opencode** | plugin + instruktioner + MCP + genereret skill-router (indbygget skill-liste afvist), repo auto-indeksering ved første besked |
| **Codex** | `hooks.json` + skills + MCP, inklusive en `PreToolUse`-port |
| **Cursor** | `hooks.json` + skills + MCP |
| **dsh** | Claude Code hook-bro + administreret patch-blok (hooks, MCP, LLM-ruter, en out-of-tree Web-statuslinje) |

Codex-porten kører Bash, `exec_command`, `apply_patch`, Edit/Write, MCP-værktøjer,
og underagentkald gennem det samme tjek som de andre værter. På Claude håndhæves
tilskrivningsforbuddet også mekanisk: `attribution`-indstillingen tømmes
(`commit`, `pr`, `sessionUrl`), så commit- og PR-krediteringer er slået fra ved kilden.

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

I en terminal er den kommando uden argumenter i stedet installationsguiden: den spørger,
hvilke værter der skal aktiveres, rodmapperne, om de manglende valgfrie værktøjer skal
installeres, og om den valgfrie DevTools MCP skal wires, udskriver planen og skriver først
efter et ja. Flagene er guidens standarder, så `--wizard --hosts omp` spørger kun om resten.
En piped, agent- eller CI-kørsel bliver aldrig promptet — den udskriver rapporten, præcis
som før.

`--install` installerer også de valgfrie værktøjer, der mangler, ved at køre hver
leverandørs eget installationsprogram **over netværket**: `orx`
(`openresearch.sh/install.sh`), `cursor-agent` (`cursor.com/install`), `dsh` (dens
hjemmeprofil gennem `npx`), og `pnpm` når dsh har brug for det (via `npm`) —
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
bin/tezgah-setup --install --hosts omp
bin/tezgah-setup --install --hosts claude,codex,cursor,opencode,dsh
bin/tezgah-setup --roots ~/work:~/oss --install
```

<a id="day-to-day"></a>

## Daglig brug

Intet at køre: reglerne indlæses, når en vært starter. Et par kommandoer er værd at
kende:

| Kommando | Formål |
|---|---|
| `bin/tezgah-setup` | I en terminal: installationsguiden; i et pipe eller i CI: rapporter, hvad der er aktiveret, pr. vært |
| `bin/tezgah-setup --wizard` | Tvinger installationsguiden frem overalt; `--report` tvinger rapporten |
| `bin/tezgah-status [PATH]` | Vis, om reglerne er aktive i det repo |
| `bin/tezgah-setup --status [PATH]` | Udskriv den aktiverede/brugte tjekliste |
| `bin/tezgah-setup --deps [--dry-run]` | Installer manglende valgfrie værktøjer (orx, cursor-agent, dsh) |
| `bin/tezgah-research init\|check\|status` | Opretter og tjekker en forskningslinje: tilstand, findings, claims og reglen protokol-før-resultater |
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

<a id="benchmark"></a>

## Benchmark

Forbedrer denne kontrakt arbejdet, eller ser det bare sådan ud, som om det burde? Det måles
i `benchmarks/arm-bench/`, ikke påstås: skjulte checks, som agenten aldrig ser checken for,
omkostning fra værtens egen brugsregistrering, og kollaterale redigeringer scoret som fejl.
`PREREGISTRATION.md` fastlægger endepunkterne før en kørsel, og `python3 bench.py report`
udskriver dem; det fulde studie med kørsels-id'erne er
`docs/research/2026-09-16-tezgah-quality.md`. Hvert tal nedenfor er en kørselslog.

| Blok | Kørsler | Hvad den afgjorde |
|---|---|---|
| to-vært, 28 opgaver, k=3 | 336 | `omp+tezgah` 0.95 og `opencode+tezgah` 0.96 har overlappende intervaller og samme omkostning pr. løst opgave; på de bare arme er omp billigere ($0.0047 mod $0.0074 CPS), så den daglige driver er omp uden omkostning i kvalitet |
| hård familie, 5 opgaver, k=5, to modelfamilier | 200 | samlet lander tre af de fire arme på 40/50: ingen harness-effekt i den størrelse, og det ene signal, det første model gav, vendte om på det andet |
| port-familie, port aktiveret | 36 | ingen arm tog genvejsruten; port-mekanismen er verificeret direkte (en skip-redigering afvises), dens effekt på arbejdet er endnu ikke målt |
| klausul-ablation, de to regler der skiller, k=8 | 160 | kontraktarmene består 23/32 (0.72) mod den bare ankers 12/32 (0.38) |


**Det hjælper præcis hvor modellens standard er forkert.** `c04` (en engelsk prompt, hvor
kun kontrakten gør svaret tyrkisk) læses 9/16 med en kontrakt og 0/16 uden; `h02` (en
pengekontrakt, hvis synlige suite er grøn uanset hvad) læses 14/16 mod 12/16. Hvor der ikke
er et hul at lukke - 22 af de 25 pilotopgaver bestod under hver arm ved hver gentagelse -
kan en benchmark kun rapportere en null.

**To klausuler bærer det.** At fjerne klausul 1 bringer `c04` til 0/8, den bare ankers egen
score, mens `h02` næsten ikke flytter sig. At fjerne klausul 3 bringer `h02` til 2/8 - under
den bare ankers 6/8 - fordi klausul 3 forbyder at stoppe ved den korteste færdig-udseende
vej, og på den opgave er den korteste vej den one-liner, der består den synlige suite og
bryder den dokumenterede regel. Klausul 2 og 4 flytter intet målbart.

**Omkostning følger kvalitet.** Pr. løst opgave: $0.0078 mod $0.0097 på fuldkontrakt-noden,
$0.0043 mod $0.0087 på minus-ponytail-noden. Kontraktarmene løser flere opgaver, så hver
løst opgave koster mindre; det samlede forbrug er højere, og benchmarken registrerer det pr.
række i stedet for at udligne det.

Det dette ikke viser: kodekvalitet, review-indsats eller vedligeholdelsesvenlighed, ingen af
hvilke måles her; portens effekt på en arms valg, da ingen arm greb genvejen i 36 aktiverede
kørsler; eller en klausul-*rækkefølge* - `k=8` fastlægger en retning, ved 8 kørsler pr.
celle. Én udbyder og én fixture-pakke hele vejen igennem, og ablationsrunderne kører på en
enkelt modelfamilie. En anden modelfamilie reproducerer 28-opgave-nullen præcis (51/56 mod
51/56), hvilket er det, der viser, at den første læsning ikke var et modelartefakt.

<a id="cost"></a>

## Omkostninger

Målt på denne maskine (macOS, Python 3.10), ikke estimeret. `tezgah-setup` udskriver det
aktuelle budget - læs det der i stedet for at stole på et tal kopieret hertil, hvilket er
hvordan en tidligere revision kom til at citere et kernebånd mindre end det, den installerer.

| Bånd | Hvad det koster |
|---|---|
| Sessionsstart | den altid-aktive kontrakt (invarianterne plus en enlinjes pointer pr. on-demand-regel): på denne maskine og skill-sæt ~1.3k tokens kontrakttekst og ~1.3k skill-metadata, hvor de betingede regler (spec, consult, research, graph) kun tilføjer ~0.6k på den tur, hvis prompt matcher |
| Pr. tur | en kort påmindelse (~0.2k tokens) plus den aktiverede regel, når den matcher; hooks er separate Python-processer, så den ~19 ms interpretestart dominerer - sessionsstart tilføjer ~25 ms, et gated værktøjskald (Bash/Grep/Task) ~9 ms. opencode har ingen prompt-tids-hook, så den betaler nul |
| On demand | den fulde `tezgah-contract`-skill (~6.0k tokens), kun betalt når en opgave indlæser den |
| MCP-skemaer | det største bånd og det, ingen statisk rapport ser: alene grafserveren erklærer 15 værktøjer / 24,508 bytes (~6.1k tokens), rider på hver anmodning medmindre værten henter skemaer on demand. `tezgah-setup --mcp-schemas` måler det |
| Disk | installationen tager ~58 ms, og hver fil, tezgah genskriver, gemmes én gang som `<file>.tezgah-bak` |

**Arming-gulvet.** Invarianterne er altid aktive - execution mode, ponytail,
deliver-the-whole-ask, integritet, loop-disciplin, lessons-ledgeren og attributionsforbuddet
- og sikkerhedsreglen ("irreversible eller udadvendte handlinger kræver først et
udtrykkeligt spørgsmål") er en af dem, så den afhænger aldrig af en klassificerer. Hver
rådgivende regel holder en handlingsdygtig enlinjes pointer altid aktiv, så et forpasset
match koster detalje, aldrig reglen, og en værtshook, der fejler, falder tilbage til
pointerne plus on-demand-skillen i stedet for til ingen kontrakt. Falske negativer er
reviderbare: hver prompt tilføjer `armed=<rules|none> chars=<n>` - ingen prompttekst - til
`~/.cache/tezgah/classify.log` (afkortet til de sidste 200 linjer efter 64 KB), og alle fem
hook-værter aktiverer det samme sæt for den samme prompt
(`tests/test_context.py::ArmingConformance`).

**opencode aktiveres anderledes.** Den har intet injektionspunkt ved prompt-tid, så
kontrakten leveres som en genereret instruktionsfil, og dens altid-aktive router lister kun
de buckets, en kodningssession griber efter, og kollapser resten til en pointer ved
`~/.config/tezgah/opencode-skills.full.md`, læst on demand; `permission.skill = deny`
forhindrer opencode i i stedet at injicere hver skills metadata. `--install` sætter også
`compaction.prune` og `watcher.ignore`, hvilket rydder gamle værktøjsresultater fra prompten
i stedet for at gensende dem hvert skridt - uden det vokser working settet til
hundredtusindvis af tokens, før opencode auto-kompakter nær modellens grænse (omkring 980k
for en 1M-token-model). `bin/tezgah-doctor` rapporterer diskaftrykket, og `--prune-sessions
DAYS` sletter inaktive sessioner gennem opencode-CLI'en, den eneste handling, der faktisk
krymper databasen, da VACUUM alene ikke kan.

**Hvorfor det betaler sig.** I et rigtigt repo ignorerede et standard-`grep` den relevante
mappe og fandt intet; med ignore deaktiveret tog det 3.95 s og blandede stadig definitioner
med kaldesteder, mens kodegrafen besvarede det samme spørgsmål på 16 ms med de 8 sande
kaldesteder.

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
