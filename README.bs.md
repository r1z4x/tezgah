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
  <a href="#benchmark">Benchmark</a> &bull;
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

| Host | Povezan putem |
|---|---|
| **omp** (oh-my-pi) — primarni | `~/.omp/agent`: upravljani `RULES.md` always-on blok, vještine, generisani podagenti, `mcp.json`, i ekstenzija (`hooks/pre/tezgah-hook.ts`) koja naoružava pravila po promptu, propušta alate kroz kapiju, bilježi dokaze i pokreće Stop pravilo; povezivanje provjerava `tezgah-setup` |
| **Claude Code** | lokalno tržište dodataka: hookovi, komande, dva agenta samo za čitanje, stil izlaza |
| **opencode** | dodatak + instrukcije + MCP + generisani ruter vještina (nativna lista vještina odbijena), auto-indeksiranje repozitorija pri prvoj poruci |
| **Codex** | `hooks.json` + vještine + MCP, uključujući `PreToolUse` kapiju |
| **Cursor** | `hooks.json` + vještine + MCP |
| **dsh** | Claude Code hook most + upravljani patch blok (hookovi, MCP, LLM rute, Web statusna linija van stabla) |

Codex kapija pokreće Bash, `exec_command`, `apply_patch`, Edit/Write, MCP alate,
i pozive podagenata kroz istu provjeru kao i ostali hostovi. Na Claude-u,
zabrana pripisivanja se također mehanički sprovodi: postavka `attribution` se
prazni (`commit`, `pr`, `sessionUrl`) tako da su zasluge za commit i PR isključene na
izvoru.

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

U terminalu je ta komanda bez argumenata umjesto toga čarobnjak za instalaciju: pita koje
hostove naoružati, korijenske direktorije, da li da instalira nedostajuće opcionalne alate,
i da li da poveže opcionalni DevTools MCP, ispisuje plan i piše tek nakon potvrdnog
odgovora. Zastavice su čarobnjakove zadane vrijednosti, pa `--wizard --hosts omp` pita samo
ostatak. Pipe, agentsko ili CI pokretanje nikad se ne pita — ispisuje izvještaj, tačno kao
prije.

`--install` također instalira opcione alate koji nedostaju pokretanjem vlastitog instalatera
svakog dobavljača **preko mreže**: `orx` (`openresearch.sh/install.sh`), `cursor-agent`
(`cursor.com/install`), `dsh` (njegov početni profil kroz `npx`) i `pnpm` kada je dsh-u
potreban (preko `npm`) — `curl ... | sh` uključujući. Nijednom nije potreban sudo;
pokretanje se bilježi u
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

<a id="benchmark"></a>

## Benchmark

| Blok | Pokretanja | Šta je razriješio |
|---|---|---|
| dva hosta, 28 zadataka, k=3 | 336 | `omp+tezgah` 0.95 i `opencode+tezgah` 0.96 imaju preklapajuće intervale i isti trošak po riješenom zadatku; na golim rukama omp je jeftiniji ($0.0047 protiv $0.0074 CPS), pa je dnevni pokretač omp bez troška u kvaliteti |
| teška familija, 5 zadataka, k=5, dvije familije modela | 200 | objedinjeno, tri od četiri ruke slijeću na 40/50: nema efekta alata te veličine, a jedini signal koji je prvi model proizveo obrnuo se na drugom |
| familija kapije, kapija naoružana | 36 | nijedna ruka nije uzela putanju prečice; mehanizam kapije je direktno verifikovan (izmjena preskakanja se odbija), njen efekat na rad još nije izmjeren |
| ablacija klauzula, dva pravila koja razdvajaju, k=8 | 160 | ruke sa ugovorom prolaze 23/32 (0.72) protiv 12/32 (0.38) gole sidre |

Da li ovaj ugovor poboljšava rad, ili samo izgleda kao da bi trebao? To se mjeri u
`benchmarks/arm-bench/`, ne tvrdi: skrivene provjere koje agent nikad ne vidi, trošak iz
vlastitog zapisa o upotrebi hosta, i kolateralne izmjene ocijenjene kao neuspjesi.
`PREREGISTRATION.md` fiksira krajnje tačke prije pokretanja i `python3 bench.py report` ih
ispisuje; cijela studija, sa id-ovima pokretanja, je
`docs/research/2026-09-16-tezgah-quality.md`. Svaka cifra ispod je zapis pokretanja.

**Pomaže tačno tamo gdje je zadana vrijednost modela pogrešna.** `c04` (engleski prompt gdje
samo ugovor čini odgovor turskim) čita 9/16 sa ugovorom i 0/16 bez njega; `h02` (novčani
ugovor čiji je vidljivi paket zelen u oba slučaja) čita 14/16 protiv 12/16. Tamo gdje nema
praznine za zatvoriti - 22 od 25 pilot zadataka prošlo je pod svakom rukom pri svakom
ponavljanju - benchmark može samo prijaviti nulu.

**Dvije klauzule ga nose.** Uklanjanje klauzule 1 vodi `c04` na 0/8, vlastiti rezultat gole
sidre, dok jedva pomjera `h02`. Uklanjanje klauzule 3 vodi `h02` na 2/8 - ispod 6/8 gole
sidre - jer klauzula 3 zabranjuje zaustavljanje na najkraćoj gotovo-gotovoj putanji, a na
tom zadatku najkraća putanja je one-liner koji prolazi vidljivi paket i krši dokumentovano
pravilo. Klauzule 2 i 4 ne pomjeraju ništa mjerljivo.

**Trošak slijedi kvalitet.** Po riješenom zadatku: $0.0078 protiv $0.0097 na čvoru punog
ugovora, $0.0043 protiv $0.0087 na čvoru bez-ponytail. Ruke sa ugovorom rješavaju više
zadataka, pa svaki riješeni zadatak košta manje; ukupna potrošnja je veća, a benchmark je
bilježi po redu umjesto da je netira.

Šta ovo ne pokazuje: kvalitet koda, trud recenzije ili održivost, ništa od toga se ovdje ne
mjeri; efekat kapije na izbore ruke, jer nijedna ruka nije posegnula za prečicom u 36
naoružanih pokretanja; niti *redoslijed* klauzula - `k=8` fiksira smjer, pri 8 pokretanja po
ćeliji. Jedan provajder i jedan fixture paket sve vrijeme, a runde ablacije rade na jednoj
familiji modela. Druga familija modela reprodukuje nulu od 28 zadataka tačno (51/56 protiv
51/56), što pokazuje da prvo čitanje nije bilo artefakt modela.

<a id="cost"></a>

## Trošak

| Opseg | Šta košta |
|---|---|
| Početak sesije | always-on ugovor (invarijante plus pokazivač od jedne linije po pravilu na zahtjev): na ovoj mašini i skupu vještina, ~1.3k tokena teksta ugovora i ~1.1k metapodataka vještina, pri čemu uslovna pravila (spec, consult, research, graph) dodaju ~0.6k samo na potezu čiji se prompt poklopi |
| Po potezu | kratki podsjetnik (~0.2k tokena) plus naoružano pravilo kada se poklopi; hookovi su odvojeni Python procesi, pa ~19 ms pokretanja interpretera dominira - početak sesije dodaje ~25 ms, poziv alata kroz kapiju (Bash/Grep/Task) ~9 ms. opencode nema hook u vrijeme prompta, pa plaća nulu |
| Na zahtjev | puna `tezgah-contract` vještina (~5.8k tokena), plaća se samo kada je zadatak učita |
| MCP šeme | najveći opseg, i onaj koji nijedan statički izvještaj ne vidi: samo graf server deklariše 15 alata / 24,508 bajtova (~6.1k tokena), jaše na svakom zahtjevu osim ako host dohvati šeme na zahtjev. `tezgah-setup --mcp-schemas` to mjeri |
| Disk | instalacija traje ~58 ms, i svaka datoteka koju tezgah prepisuje čuva se jednom kao `<file>.tezgah-bak` |

**Pod naoružavanja.** Invarijante su always-on - režim izvršavanja, ponytail,
deliver-the-whole-ask, integritet, disciplina petlje, evidencija lekcija i zabrana
pripisivanja - a sigurnosno pravilo ("nepovratne ili prema van okrenute akcije zahtijevaju
prvo eksplicitan upit") je jedno od njih, pa nikad ne zavisi od klasifikatora. Svako
savjetodavno pravilo drži pokazivač od jedne linije koji se može izvršiti uvijek aktivnim,
pa propušteni poklopac košta detalj, nikad pravilo, a hook hosta koji ne uspije pada natrag
na pokazivače plus vještinu na zahtjev umjesto na nikakav ugovor. Lažni negativi su
revizijski: svaki prompt dodaje `armed=<rules|none> chars=<n>` - bez teksta prompta - u
`~/.cache/tezgah/classify.log` (skraćen na zadnjih 200 linija nakon 64 KB), i svih pet hook
hostova naoružava isti skup za isti prompt (`tests/test_context.py::ArmingConformance`).

**opencode se naoružava drugačije.** Nema tačku ubacivanja u vrijeme prompta, pa se ugovor
isporučuje kao generisana datoteka instrukcija, a njegov always-on ruter navodi samo grupe
koje kod-sesija poseže, sažimajući ostatak na pokazivač na
`~/.config/tezgah/opencode-skills.full.md` koji se čita na zahtjev; `permission.skill =
deny` zaustavlja opencode da umjesto toga ubaci metapodatke svake vještine. `--install`
također postavlja `compaction.prune` i `watcher.ignore`, čisteći stare rezultate alata iz
prompta umjesto da ih ponovo šalje na svakom koraku - bez toga radni skup raste na stotine
hiljada tokena prije nego opencode automatski kompaktira blizu granice modela (oko 980k za
model od 1M tokena). `bin/tezgah-doctor` izvještava o zauzeću diska, a `--prune-sessions
DAYS` briše neaktivne sesije kroz opencode CLI, jedina akcija koja zapravo smanjuje bazu
podataka, jer VACUUM sam ne može.

**Zašto se isplati.** U jednom stvarnom repozitoriju zadani `grep` je ignorisao relevantni
folder i ništa nije našao; sa isključenim ignore-om trebalo je 3.95 s i još uvijek je
miješao definicije sa mjestima poziva, dok je graf koda odgovorio na isto pitanje za 16 ms
sa 8 pravih mjesta poziva.

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
