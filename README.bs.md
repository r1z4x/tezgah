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

<h3 align="center">Jedan radni ugovor za svakog AI asistenta za kodiranje kojeg pokrenete.</h3>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/github/license/r1z4x/tezgah?style=flat-square"></a>
  <a href="https://github.com/r1z4x/tezgah/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/r1z4x/tezgah/ci.yml?style=flat-square&label=ci"></a>
  <a href="https://github.com/r1z4x/tezgah/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/r1z4x/tezgah?style=flat-square"></a>
</p>

<p align="center">
  <a href="#what-it-enforces">Šta sprovodi</a> &bull;
  <a href="#supported-hosts">Podržani hostovi</a> &bull;
  <a href="#install">Instalacija</a> &bull;
  <a href="#day-to-day">Svakodnevna upotreba</a> &bull;
  <a href="#configuration">Konfiguracija</a> &bull;
  <a href="#cost">Trošak</a> &bull;
  <a href="#development">Razvoj</a> &bull;
  <a href="#contributing">Doprinos</a> &bull;
  <a href="#security">Sigurnost</a> &bull;
  <a href="#license">Licenca</a>
</p>

<p align="center"><sub>Engleski jezik je izvor istine; prevodi mogu zaostajati za njim.</sub></p>

---

Jedan radni ugovor za svakog AI asistenta za kodiranje kojeg pokrenete — Claude Code,
opencode, Codex, Cursor i DeepSeek-ov dsh alat — unutar skupa
konfigurisanih korijena repozitorija.

Prepušteni sami sebi, svaki asistent ima svoje navike: jedan odgovara na turskom, drugi
na engleskom; jedan koristi grep za sve, drugi pretražuje graf koda; jedan kaže
"gotovo" bez pokretanja testa. Tezgah uklanja to odstupanje. Otvorite bilo koji host i
dobit ćete isti jezik, istu disciplinu i isti standard dokaza.

Dizajn se sastoji od dva sloja. Pravila žive na jednom mjestu u zajedničkoj jezgri; svaki host dobija
tanki adapter koji prevodi tu jezgru u oblik koji host razumije.
Promijenite pravilo na jednom mjestu i svih pet hostova će to vidjeti — nema petostrukog kopiranja
istog teksta.

<a id="what-it-enforces"></a>

## Šta sprovodi

- **Izvještavanje na turskom sa ishodom na prvom mjestu.** Svaki odgovor je na turskom i počinje
  rezultatom ili odlukom (BLUF), a zatim slijede tačke poredane po uticaju. Kod, commitovi,
  dokumentacija i promptovi podagenata ostaju na engleskom; imena, CLI komande i stringovi
  grešaka se nikada ne prevode.
- **Minimalan kod (ponytail).** Najljenija promjena koja zapravo radi: YAGNI,
  zatim ponovna upotreba postojećeg pomoćnika, zatim stdlib, zatim nativna funkcija platforme,
  zatim instalirana zavisnost, zatim jedna linija. Bez netraženih apstrakcija.
  Validacija, rukovanje greškama i sigurnost se nikada ne pojednostavljuju.
- **Otkrivanje prvenstveno putem grafa koda.** "Gdje je X", "ko poziva Y", "šta se kvari ako
  se Z promijeni" idu na `codebase-memory-mcp` graf (`search_graph`,
  `trace_path`, `search_code`), a ne na grep. Grep ostaje prikladan za doslovni tekst,
  konfiguracije i datoteke koje nisu kod.
- **Analiza aplikacija prvenstveno putem pristupačnosti.** Pokrenuta web ili mobilna aplikacija se čita
  kroz njeno stablo pristupačnosti / DOM / nativno stablo prikaza, a ne putem snimka ekrana po koraku.
  `analyze-app` pokriva pretraživač (Playwright MCP), iOS Simulator ili Android
  emulator (Mobile MCP) i opcionu web dijagnostiku (Chrome DevTools MCP);
  snimak ekrana je eksplicitna akcija na zahtjev za ono na šta stablo ne može odgovoriti.
- **Eksterno drugo mišljenje.** Prije netrivijalne ili teško opozive odluke,
  `~/.config/tezgah/bin/consult` paralelno pita nezavisne modele putem OpenRoutera (ili
  DeepSeek API-ja sa `--provider deepseek`), a agent izvještava o tome gdje su se
  složili ili razišli.
- **Istraživanje putem OpenResearch.** Kada ruter procijeni da je zadatak istraživanje —
  pregled literature, formiranje i testiranje hipoteza, izvođenje eksperimenata,
  istraživački artefakt — on vodi rad kroz alphaXiv-ov OpenResearch (`orx`)
  i prvo učitava `orx` priručnik, umjesto da improvizuje protokol. Obično
  otkrivanje koda ostaje na grafu koda. Kada `orx` nije prisutan, ruter to kaže
  i prebacuje se na podagenta hosta.
- **Iskrenost pod verifikacijom.** Ništa se ne prijavljuje kao gotovo, testirano ili popravljeno
  osim ako izlaz nije viđen. Test koji pada prijavljuje se kao neuspješan sa svojom
  tačnom greškom, a preskočena provjera se jasno navodi.
- **Bez pripisivanja AI-ju, nigdje.** Ništa što je sačuvano ili objavljeno — commit,
  merge i tag poruke, tekst PR-a i issue-a, komentari u kodu, zaglavlja datoteka, dokumentacija
  — ne smije pripisivati zasluge asistentu, modelu, dobavljaču ili "AI-ju". Korištenje alata je u redu;
  potpisivanje njegovog imena na vaš rad nije.
- **Orkestracija u dva nivoa.** Glavna nit odlučuje i verificira; jeftin
  model (`~/.config/tezgah/bin/codegen`, OpenRouter podrazumijevano ili `--provider deepseek`) skicira
  ograničene, dobro specificirane izmjene u privremeni direktorij. Ništa ne stiže u repozitorij
  osim preko rutera, a neuspješna skica se automatski vraća na glavni model.
- **Podagenti po repozitoriju.** Na početku sesije, obuhvatajući repozitorij dobija mali skup
  agenata sa ograničenim mogućnostima (`tezgah-explorer`, `tezgah-reviewer`,
  `tezgah-researcher`, `tezgah-verifier`) plus `tezgah-orchestrator`, renderovanih
  u nativnu površinu svakog instaliranog hosta (Claude/Cursor `.claude/agents/`,
  opencode `.opencode/agents/` plus ubacivanje konfiguracije uživo, Codex
  `.codex/agents/`) i ignorisanih pomoću jednog upravljanog `.gitignore` bloka. Na Claude-u
  lista dozvoljenih `Agent(tezgah-*)` orkestratora stupa na snagu samo kada se pokreće kao
  glavna nit (`claude --agent tezgah-orchestrator`); kao podagent, lista se
  ignoriše. dsh nema površinu po ulogama, pa ga pokriva pravilo rutera iz ugovora.

<a id="supported-hosts"></a>

## Podržani hostovi

| Host | Povezan putem | Statusna linija |
|---|---|---|
| **Claude Code** | lokalno tržište dodataka: hookovi, komande, dva agenta samo za čitanje, stil izlaza | nativni `statusLine` |
| **opencode** | dodatak + instrukcije + MCP + generisani ruter vještina (nativna lista vještina odbijena), auto-indeksiranje repozitorija pri prvoj poruci | TUI dodatak (bez komandnog statusLine-a) |
| **Codex** | `hooks.json` + vještine + MCP, uključujući `PreToolUse` kapiju | hook `systemMessage` (lista stavki u podnožju je zatvorena) |
| **Cursor** | `hooks.json` + vještine + MCP | `statusLine` u `cli-config.json` |
| **dsh** | Claude Code hook most + upravljani patch blok (hookovi, MCP, LLM rute, Web statusna linija van stabla) | Web UI dodatak: `tezgah-dsh-statusline` u zaglavlju sesije |

Codex kapija pokreće Bash, `exec_command`, `apply_patch`, Edit/Write, MCP alate,
i pozive podagenata kroz istu provjeru kao i ostali hostovi. Na Claude-u,
zabrana pripisivanja se također mehanički sprovodi: postavka `attribution` se
prazni (`commit`, `pr`, `sessionUrl`) tako da su zasluge za commit i PR isključene na
izvoru.

### Statusna linija

Svaki host renderuje istu kontrolnu listu u jednoj liniji iz `tezgah-status`, tako da
ne mogu odstupati. Stanje je poenta: oznaka je **zelena** kada je pravilo aktivirano
i na snazi u ovoj sesiji, **žuta** kada je aktivirano ali na zahtjev (još nije korišteno),
i **crvena** kada ga je sigurnosni prekidač (kill switch) isključio. `idx` odvojeno izvještava o spremnosti grafa
(`✓` indeksirano, `↻` zastarjelo, `✗` nije indeksirano, `–` nije primjenjivo) a
`plans N (M blk)` o otvorenim planovima. `tezgah-status --legend` ispisuje legendu,
`--json` daje iste segmente za UI, a `--no-color` (ili `NO_COLOR`)
forsira običan tekst. Claude Code i Cursor boje nativnu statusnu liniju;
opencode TUI boji vlastitu komponentu i osvježava se na sabirnici događaja hosta;
dsh Web UI boji svoju komponentu zaglavlja i osvježava se samo dok je njena kartica
vidljiva; Codex prikazuje običan string u `systemMessage`.

dsh pokreće iste Claude hook datoteke kroz svoj `dsh-hooks-claude-code` most,
tako da se ugovor o početku sesije, kapija za pripisivanje i podsjetnik za prvi grep
primjenjuju i tamo. dsh izlaže jedan `subagent` alat, tako da je odbijanje explorer-a samo za grep
inertno — ne postoji explorer podagent kojeg bi odbio. Podrazumijevani
`workspace-write` sandbox dsh-a ograničava podprocese hook-a na radni prostor i
privremeni direktorij platforme, tako da tezgah zapisuje svoje stanje hook-a (oznake podsjetnika, pečat indeksa) u
upisivu rezervnu lokaciju tamo, umjesto da padne zbog odbijenog upisivanja. Radnik za indeksiranje grafa
ne može upisati `codebase-memory-mcp` keš iz unutrašnjosti tog sandbox-a, tako da
`dsh` pokretač zagrijava indeks u korisnikovoj neograničenoj ljusci prije pokretanja
dsh-a — novi repozitorij se indeksira tačno kao i na ostalim hostovima, sa HEAD pečatom.
Sesija pokrenuta bez pokretača i dalje dobija jasan izvještaj da
MCP server van sandbox-a opslužuje graf i da mu je potreban `index_repository` za repozitorij
koji nije indeksirao, umjesto sirovog `EPERM`. Upravljani
patch blok također deklariše dvije OpenAI-kompatibilne LLM rute na pi-ai adapteru
koji osnovna kompozicija montira: `openrouter` (`OPENROUTER_API_KEY`) i `deepseek`
(`DEEPSEEK_API_KEY`), koje se mogu odabrati uz nativnu `deepseek-official`
podrazumijevanu opciju. Ključevi se rješavaju iz okruženja pokretanja ili iz spremišta akreditiva alata;
nijedan ključ ne ulazi u konfiguracijsku datoteku. tezgah-setup također postavlja `dsh`
pokretač na PATH (`~/.local/bin/dsh`) koji pronalazi instalirani CLI pod
`$DSH_HOME`, tako da `dsh --profile web` radi iz bilo kojeg direktorija.

dsh nema komandnu statusnu liniju, pa tezgah isporučuje jednu kao Web UI dodatak:
`tezgah-dsh-statusline`. Njegova host polovina opslužuje `tezgah-status` string za
radni prostor sesije preko autentificirane `/api/tezgah.status` rute (sa
`?format=json` za obojeni prikaz); njegova polovina u pretraživaču ga renderuje u zaglavlju sesije,
obojenog prema stanju sa legendom na prelazak mišem/klik, i osvježava se samo dok je
kartica vidljiva. `tezgah-setup`
povezuje dodatak u web profil i omogućava ga upravljanim redom u
`profiles/web/cordis.patch.yml` (samo za web, jer host polovina ubacuje
`connection` servis koji je samo za web); profil koji nikada nije pokrenuo `web` se preskače
uz napomenu umjesto da bude napola zapisan. U `headless` režimu, most za hookove
ubacuje SessionStart ugovor kao svoj vlastiti prateći potez (njegov `agent/session-start`
poziva `agent.inject()` odvojeno, nakon što je jednokratni zadatak već prva poruka),
tako da `dsh --profile headless "<task>"` troši jedan dodatni potez i, za
prompt sa doslovnim odgovorom, ispisuje reakciju modela na ugovor umjesto
odgovora na zadatak; interaktivne web sesije nisu pogođene.

`bin/tezgah-setup --install` također pokreće `orx install-skills` za Claude,
Codex, opencode i Cursor kada je `orx` na PATH-u, tako da pravilo za istraživanje ima
priručnik za učitavanje. Shim datoteke pripadaju orx-u, tako da tezgah samo pokreće taj instalater
i nikada ih ne navodi za deinstalaciju. dsh nema orx alat; pravilo za istraživanje se
tamo prebacuje na `orx skill` u ljusci.

Claude dodatak također isporučuje dva agenta samo za čitanje. `agents/tezgah-explorer.md`
vrši otkrivanje koda iz grafa i vraća `file:line` dokaze;
`agents/tezgah-reviewer.md` pretvara diff u njegov skup uticaja pomoću
`detect_changes` i zatim traži stvarne defekte. Obojici su alati za pisanje i komande
onemogućeni; njihov izlaz je savjetodavan.

### Analiza aplikacija

`analyze-app` upravlja pokrenutom aplikacijom iz njenog stabla pristupačnosti.
Podrazumijevana petlja je otvaranje, čitanje stabla, djelovanje, posmatranje konzole/mreže/logova, i
ponovno čitanje stabla — snimak ekrana je eksplicitna akcija za ono na šta stablo ne može
odgovoriti (canvas, igra, animacija, vizuelna regresija na nivou piksela). Vještina je
jedna putanja za sve hostove; serveri ispod nje su jedna zajednička specifikacija u
`hooks/tezgah_apps.py`:

| Server | Cilj | Povezan putem |
|---|---|---|
| `playwright` (`@playwright/mcp`) | web stranice, `browser_*` alati | opencode, Codex, Cursor, Claude (dodatak `.mcp.json`) |
| `mobile-mcp` (`@mobilenext/mobile-mcp`) | iOS Simulator / Android emulator, `mobile_*` alati | isto |
| `chrome-devtools` (opciono, `--devtools`) | tragovi web performansi, duboka mreža, konzola sa mapiranim izvornim kodom | isto |

Pretraživač podrazumijevano pokreće **izolovani** profil, tako da pokretanje nikada ne dotiče
vaše stvarno stanje u Chrome-u; analiziranje toka sa prijavom je namjerno povezivanje
(`--cdp-endpoint` ili Playwright ekstenzija), a ne podrazumijevano ponašanje. Snimci ekrana,
tragovi i ispisi stabla završavaju u `~/.cache/tezgah/apps` (može se prepisati sa
`TEZGAH_ARTIFACTS`) a agent dobija putanju nazad, nikada inline bajtove slike.
Serveri se pokreću preko `npx`, tako da im je potreban node, ali ne i vlastita instalacija;
`tezgah-setup --install --devtools` dodaje opcioni server za web dijagnostiku.
dsh povezuje ista dva servera kroz svoj `dsh-mcp-client` most
(`serverName` / `command` / `args` / `env`, potvrđeno prema objavljenoj
konfiguracijskoj šemi), a Claude ih dobija iz `.mcp.json` dodatka
(`claude plugin details tezgah` navodi MCP servere 2 i oba se povezuju).
`mobile-mcp` je polovina sa više trenja: macOS može tražiti dozvolu za Pristupačnost /
Snimanje ekrana, a stablo prikaza može pasti pod opterećenjem, tako da vještina
ponovo pokušava dobiti stablo prije nego što se prebaci na snimak ekrana.

CI pokreće determinističko rukovanje za oba servera (bez pretraživača, bez uređaja):
`TEZGAH_E2E_STRICT=1 python3 tests/e2e_analyze_wiring.py`. Dva opciona lokalna
smoke testa idu dalje: `TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_web.py` pokreće
Playwright MCP, navigira i čita snapshot bez snimka ekrana;
`TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_mobile.py` pokreće Mobile MCP, provjerava
alate za stablo prikaza i navodi uređaj. Oni ispisuju `SKIP: ...` kada node,
build pretraživača ili uređaj nedostaje.

<a id="install"></a>

## Instalacija

Zahtijeva Python 3.8+. node + npm su potrebni za dsh host i, uz `pnpm`,
za njegovu web statusnu liniju. Opcione integracije degradiraju graciozno:
`codebase-memory-mcp` na PATH-u pokreće graf; ključ modela pokreće `consult`
i `codegen` — OpenRouter podrazumijevano (`OPENROUTER_API_KEY` ili
`~/.config/openrouter/key`), ili DeepSeek API sa `--provider deepseek`
(`DEEPSEEK_API_KEY` ili `~/.config/deepseek/key`); a OpenResearch-ov `orx` na
PATH-u daje pravilu za istraživanje nešto čime će upravljati. Kada nedostaje ključ odabranog provajdera,
tezgah to kaže umjesto da se pretvara.

Klonirajte, a zatim aktivirajte svaki detektovani host u jednom prolazu:

```bash
git clone https://github.com/r1z4x/tezgah.git ~/Projects/tezgah
cd ~/Projects/tezgah
bin/tezgah-setup --install
```

`--install` također instalira opcione alate koji nedostaju pokretanjem vlastitog instalatera svakog dobavljača **preko mreže**: `orx`
(`openresearch.sh/install.sh`), `cursor-agent` (`cursor.com/install`), `dsh`
(njegov početni profil kroz `npx`) i `pnpm` kada je dsh-u potreban (preko `npm`) —
`curl ... | sh` uključujući. Nijednom nije potreban sudo; pokretanje se bilježi u
`~/.config/tezgah/install.log`. Pregledajte sa `--dry-run`, preskočite sa
`--no-deps` (korisno u CI), ili instalirajte samo alate sa `--deps`. Alati završavaju
u `~/.local/bin` ili `~/.cargo/bin`, tako da može biti potrebna nova ljuska prije nego što
budu na PATH-u; tezgah-ove vlastite provjere svakako gledaju u te direktorije, tako da ih neinteraktivna
ljuska i dalje prijavljuje kao prisutne.

Ako je prethodna postavka već prisutna, prvo je uvezite — bit će pomjerena u stranu,
a ne izbrisana:

```bash
bin/tezgah-setup --adopt
```

Claude Code se instalira kroz svoj vlastiti kanal za dodatke:

```bash
claude plugin marketplace add ~/Projects/tezgah
claude plugin install tezgah@rizacan-local
```

Eksplicitno ograničite instalaciju kada je to potrebno:

```bash
bin/tezgah-setup --install --hosts omp
bin/tezgah-setup --install --hosts claude,codex,cursor,opencode,dsh
bin/tezgah-setup --roots ~/work:~/oss --install
```

<a id="day-to-day"></a>

## Svakodnevna upotreba

Nema se šta pokretati: pravila se učitavaju kada se host pokrene. Nekoliko komandi je vrijedno
znati:

| Komanda | Svrha |
|---|---|
| `bin/tezgah-setup` | U terminalu: čarobnjak za instalaciju; u pipe-u ili CI-ju: izvještava šta je aktivirano, po hostu |
| `bin/tezgah-setup --wizard` | Prisiljava čarobnjak za instalaciju bilo gdje; `--report` prisiljava izvještaj |
| `bin/tezgah-status [PATH]` | Prikazuje da li su pravila aktivna u tom repozitoriju |
| `bin/tezgah-setup --status [PATH]` | Ispisuje kontrolnu listu aktiviranog/korištenog |
| `bin/tezgah-setup --deps [--dry-run]` | Instalira opcione alate koji nedostaju (orx, cursor-agent, dsh) |
| `bin/tezgah-doctor [--clean] [--prune-sessions DAYS]` | Izvještava o upotrebi diska alata; `--clean` briše stare logove indeksa i usisava (vacuum) opencode bazu podataka; `--prune-sessions` briše neaktivne sesije (jedina akcija koja zapravo smanjuje bazu podataka) |
| `/plan-add` | Pretvara dio posla u praćeni plan |
| `/plan-status` | Sumira otvorene planove i bira sljedeći |
| `/plan-sync` | Zatvara završene planove |
| `bin/tezgah-setup --version` | Ispisuje verziju dodatka |
| `bin/tezgah-setup --uninstall` | Uklanja samo tezgah-ove simboličke linkove, unose hookova hosta i dsh upravljani blok |

<a id="configuration"></a>

## Konfiguracija

Tezgah je aktiviran samo pod svojim konfigurisanim korijenima; bilo gdje drugo je tih.

- Podrazumijevani korijen: `~/Projects`.
- `~/.config/tezgah/config.json`: `{"roots": ["~/Projects", "~/work"]}`.
- `TEZGAH_ROOTS` (lista odvojena separatorom putanje) prepisuje datoteku za jednokratne slučajeve i CI.

Sigurnosni prekidači (kill switches) se nalaze u `~/.config/tezgah/`. Svaki od njih uklanja svoje pravilo iz
teksta ubačenog u sesiju, tako da se pravilo zapravo zaustavlja:

| Prekidač | Isključuje |
|---|---|
| `exec-mode.off` | Izvještavanje na turskom, sa ishodom na prvom mjestu |
| `ponytail-auto.off` | pravilo minimalnog koda |
| `spec-off` | pravilo specifikacije prije izgradnje |
| `consult-off` | pravilo eksternog drugog mišljenja |
| `research-off` | usmjeravanje istraživačkih zadataka na OpenResearch |
| `orchestrate-off` | delegiranje podagenata (dodaje liniju za nedelegiranje) |
| `reminder-off` | tekst podsjetnika po potezu |
| `pretooluse-off` | samu PreToolUse kapiju (pripisivanje, explorer, podsjetnik za grep) |

Po repozitoriju, `.no-ponytail`, `.no-cbm` i `.no-lessons` isključuju pravilo minimalnog koda,
pravilo grafa koda (i njegov auto-indeks), odnosno knjigu lekcija.

Kada korisnik označi grešku, agent dodaje lekciju u jednoj liniji u `.tezgah/lessons.md` repozitorija;
najnovije linije se ubacuju na početku sesije tako da se ista greška ne može tiho ponoviti.

<a id="cost"></a>

## Trošak

Izmjereno na ovoj mašini (macOS, Python 3.10), nije procijenjeno:

- **Kontekst.** Početak sesije ubacuje ~5.4 KB (~1.3k tokena) teksta ugovora.
  Na Codex-u podsjetnik od 480 bajtova prati svaki potez; Claude i ostali hostovi
  nemaju hook po potezu, tako da je njihov trošak po potezu nula. Puna `tezgah-contract`
  vještina (~25k karaktera) se plaća samo kada je zadatak učita. Na opencode-u
  ugovor se isporučuje kao datoteka sa instrukcijama od ~5.8 KB. opencode bi inače
  ubacio teksta sa imenom/opisom/lokacijom vještine u sistemski prompt svake sesije;
  tezgah odbija tu listu (`permission.skill = deny`) i umjesto toga isporučuje
  generisani ruter vještina , tako da se vještina pronalazi čitanjem njene
  `SKILL.md` putanje iz rutera.
- **Latencija.** Hookovi su zasebni Python procesi, tako da dominira pokretanje interpretera od ~19 ms.
  Povrh toga, početak sesije dodaje ~25 ms, poziv alata sa kapijom
  (Bash/Grep/Task) dodaje ~9 ms, a Codex-ov Stop segment dodaje ~15 ms po potezu.
- **Disk.** Instalacija traje ~58 ms i svaka datoteka koju tezgah prepisuje se čuva
  jednom kao `<file>.tezgah-bak`.

Isplativost se pokazuje na pitanjima pozivaoca. U jednom stvarnom repozitoriju, podrazumijevani `grep`
je ignorisao relevantni folder i nije pronašao ništa; sa onemogućenim ignorisanjem trebalo mu je
3.95 s i dalje je miješao definicije sa mjestima poziva. Graf koda je odgovorio na
isto pitanje za 16 ms, navodeći samo 8 pravih mjesta poziva.

opencode je također opremljen za higijenu konteksta dugih sesija: `tezgah-setup --install`
postavlja `compaction.prune` tako da se stari rezultati alata brišu iz prompta
umjesto da se ponovo šalju na svakom koraku, a `watcher.ignore` lista drži posmatrača datoteka
dalje od `.git`, `node_modules` i build direktorija. Oba se spajaju — eksplicitna korisnička
vrijednost pobjeđuje. Ovo je važno jer opencode vrši automatsko sažimanje samo blizu ograničenja konteksta modela
(za model od 1M tokena, oko 980k), tako da bez čišćenja radni skup
raste na stotine hiljada tokena. `bin/tezgah-doctor` izvještava o
rezultujućem zauzeću diska; `--prune-sessions DAYS` briše neaktivne sesije kroz
opencode CLI, što je jedina akcija koja zapravo smanjuje bazu podataka — sam VACUUM
to ne može, jer su sve njegove stranice žive.

<a id="development"></a>

## Razvoj

```bash
python3 -m unittest discover -s tests -v   # stdlib test suite
pip install -r requirements-dev.txt        # pinned ruff, the only dev dep
ruff check .                               # lint (config in pyproject.toml)
```

CI se pokreće i na Pythonu 3.10 i 3.12. Da biste osvježili instaliranu Claude kopiju
iz ovog checkout-a, koristite `bin/tezgah-setup --sync`, i validirajte manifest sa
`claude plugin validate .claude-plugin/plugin.json`. Prilikom povećanja verzije,
ažurirajte `.claude-plugin/plugin.json` i `.claude-plugin/marketplace.json`
zajedno — moraju se slagati.

`codebase-memory-mcp` instalira korisnik. Orca-ini hookovi i datoteke nisu
dio ovog projekta i ostavljeni su netaknuti. Claude prima uvijek uključenu jezgru
iz SessionStart hook-a; `output-styles/tezgah.md` je duplikat za buildove
koji učitavaju stilove izlaza dodataka, tako da je hook autoritativna putanja.

<a id="contributing"></a>

## Doprinos

Male promjene sa jednom svrhom je najlakše prihvatiti. Pravilo pripada u
zajedničkoj jezgri (`hooks/`) osim ako nije zaista specifično za host; razlika hosta
pripada njegovom adapteru pod `hosts/<name>/`. Neka diff bude što kraći,
a da i dalje bude tačan — vlastito pravilo minimalnog koda projekta primjenjuje se na projekat.

Prije otvaranja pull request-a, pokrenite iste tri provjere koje pokreće CI:

```bash
python3 -m compileall -q hooks hosts bin statusline.py   # byte-compile every script
python3 -m unittest discover -s tests                     # stdlib test suite
ruff check .                                              # lint; config in pyproject.toml
```

`ruff` dolazi iz `requirements-dev.txt` (`pip install -r requirements-dev.txt`),
što je jedina razvojna zavisnost.

<a id="security"></a>

## Sigurnost

Prijavite ranjivosti privatno kroz GitHub-ova sigurnosna upozorenja
(kartica **Security** → **Report a vulnerability**) umjesto javnog issue-a.

tezgah pokreće shell hookove, zapisuje konfiguraciju hosta i ubacuje tekst u svaku
sesiju, tako da je sve što uzrokuje da hook izvrši kod pod kontrolom napadača, procuri
ključ u konfiguracijsku datoteku, proširi sandbox ili dozvoli da sadržaj repozitorija eskalira
u tekst instrukcija u opsegu. Uključite host, verziju tezgah-a
(`bin/tezgah-setup --version`) i minimalnu reprodukciju.

<a id="license"></a>

## Licenca

Korijenska `LICENSE` (MIT) pokriva tezgah-ove vlastite datoteke. `skills/ponytail` i
`skills/no-ai-slop` su uključeni (vendored) pod njihovim vlastitim MIT uslovima, zabilježenim u
`NOTICE`.
