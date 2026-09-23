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

<h3 align="center">Un contrat de travail unique pour chaque assistant de codage IA que vous exécutez.</h3>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/github/license/r1z4x/tezgah?style=flat-square"></a>
  <a href="https://github.com/r1z4x/tezgah/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/r1z4x/tezgah/ci.yml?style=flat-square&label=ci"></a>
  <a href="https://github.com/r1z4x/tezgah/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/r1z4x/tezgah?style=flat-square"></a>
</p>

<p align="center">
  <a href="#what-it-enforces">Ce qu'il applique</a> &bull;
  <a href="#supported-hosts">Hôtes pris en charge</a> &bull;
  <a href="#install">Installation</a> &bull;
  <a href="#day-to-day">Au quotidien</a> &bull;
  <a href="#configuration">Configuration</a> &bull;
  <a href="#benchmark">Benchmark</a> &bull;
  <a href="#cost">Coût</a> &bull;
  <a href="#development">Développement</a> &bull;
  <a href="#contributing">Contribution</a> &bull;
  <a href="#security">Sécurité</a> &bull;
  <a href="#license">Licence</a>
</p>

<p align="center"><sub>L'anglais est la source de vérité ; les traductions peuvent être en décalage.</sub></p>

---

Un contrat de travail unique pour chaque assistant de codage IA que vous exécutez — Claude Code,
opencode, Codex, Cursor et le harnais dsh de DeepSeek — au sein d'un ensemble de
racines de dépôts configurées.

Laissés à eux-mêmes, chaque assistant a ses propres habitudes : l'un répond en turc, un autre
en anglais ; l'un utilise grep pour tout, un autre interroge un graphe de code ; l'un dit
« terminé » sans exécuter de test. Tezgah élimine cette dérive. Ouvrez n'importe quel hôte et vous
obtenez la même langue, la même discipline et le même niveau de preuve.

La conception repose sur deux couches. Les règles résident une seule fois dans un cœur partagé ; chaque hôte reçoit
un adaptateur léger qui traduit ce cœur dans le format que l'hôte comprend.
Modifiez une règle à un endroit et les cinq hôtes la voient — pas de
copie en cinq exemplaires du même texte.

<a id="what-it-enforces"></a>

## Ce qu'il applique

- **Rapports en turc axés sur les résultats.** Chaque réponse est en turc et commence par
  le résultat ou la décision (BLUF), puis par des points classés par impact. Le code, les commits,
  la documentation et les prompts des sous-agents restent en anglais ; les noms, les commandes CLI et les chaînes
  d'erreur ne sont jamais traduits.
- **Code minimal (ponytail).** La modification la plus paresseuse qui fonctionne réellement : YAGNI,
  puis réutilisation d'un helper existant, puis stdlib, puis une fonctionnalité native de la plateforme,
  puis une dépendance installée, puis une seule ligne. Aucune abstraction non demandée.
  La validation, la gestion des erreurs et la sécurité ne sont jamais
  simplifiées à l'excès. Le niveau d'intensité est un véritable interrupteur -
  `tezgah-pony lite|full|ultra`, ou `/tezgah:ponytail` sur Claude - et un
  niveau non par défaut accompagne le rappel à chaque tour.
- **Forme de sortie actionnable (i-have-adhd).** La réponse ou l'action
  suivante est sur la première ligne ; le travail en plusieurs étapes est une
  liste numérotée dont la position est redite en une ligne pendant qu'elle
  s'exécute ; les digressions attendent que le sujet en cours soit terminé ;
  les erreurs se lisent comme emplacement, cause, correction ; une liste
  montre au plus cinq éléments classés et le reste est gardé en réserve ; une
  estimation est en unités concrètes et est signalée comme une estimation.
  L'interrupteur est `tezgah-adhd off|on` (ou `/tezgah:adhd` sur Claude ; un
  dépôt peut le désactiver avec `.no-adhd`). Intégré et adapté depuis
  `i-have-adhd` (MIT).
- **Découverte axée sur le graphe de code.** « Où est X », « qui appelle Y », « qu'est-ce qui casse si
  Z change » passent par l'index `codegraph` (`codegraph_explore` via MCP et la CLI
  `codegraph callers|callees|impact|affected|node` depuis un shell), et non par grep. Grep reste approprié pour le texte littéral,
  les configurations et les fichiers non liés au code.
- **Analyse d'application axée sur l'accessibilité.** Une application web ou mobile en cours d'exécution est lue
  via son arbre d'accessibilité / DOM / vue native, et non par une capture d'écran à chaque étape.
  `analyze-app` couvre un navigateur (Playwright MCP), un simulateur iOS ou un émulateur Android
  (Mobile MCP), et des diagnostics web optionnels (Chrome DevTools MCP) ;
  une capture d'écran est une action explicite, à la demande, pour ce à quoi l'arbre ne peut pas répondre.
- **Second avis externe.** Avant une décision non triviale ou difficile à annuler,
  `~/.config/tezgah/bin/consult` interroge des modèles indépendants via OpenRouter (ou
  l'API DeepSeek avec `--provider deepseek`, ou Inception Labs avec
  `--provider inception`) en parallèle, et l'agent signale sur quels points ils
  sont d'accord ou en désaccord.
- **Recherche via OpenResearch.** Lorsque le routeur juge qu'une tâche relève de la recherche — une
  revue de littérature, la formulation et le test d'hypothèses, l'exécution d'expériences, un
  artefact de recherche — il pilote le travail via OpenResearch d'alphaXiv (`orx`)
  et charge d'abord le manuel `orx`, au lieu d'improviser le protocole. La simple
  découverte de code reste sur le graphe de code. Lorsque `orx` est absent, le routeur le signale
  et se rabat sur un sous-agent de l'hôte.
  Le savoir métier dont une expérience a besoin est embarqué : la bibliothèque
  `AI-research-SKILLs` intégrée au dépôt (98 skills, 23 catégories, MIT) arrive comme skill
  `ai-research`, et se lit entrée par entrée depuis son index par étape.
- **Honnêteté sous vérification.** Rien n'est signalé comme terminé, testé ou corrigé
  à moins que le résultat n'ait été vu. Un test qui échoue est signalé comme tel avec son
  erreur exacte, et une vérification ignorée est déclarée clairement.
- **Aucune attribution à l'IA, nulle part.** Rien de ce qui est persisté ou publié — messages de commit,
  de fusion et de tag, textes de PR et de tickets, commentaires de code, en-têtes de fichiers, documentation
  — ne doit créditer l'assistant, le modèle, le fournisseur ou « l'IA ». Utiliser un outil est acceptable ;
  signer votre travail de son nom ne l'est pas.
- **Orchestration à deux niveaux.** Le thread principal décide et vérifie ; un modèle
  peu coûteux (`~/.config/tezgah/bin/codegen`, OpenRouter par défaut, `--provider deepseek`
  ou `--provider inception`) rédige
  des modifications délimitées et bien spécifiées dans un répertoire temporaire. Rien n'atteint le dépôt
  si ce n'est par le routeur, et un brouillon qui échoue se rabat automatiquement sur le modèle principal.
- **Sous-agents par dépôt.** Au démarrage de la session, le dépôt englobant reçoit un petit ensemble d'agents
  à capacités restreintes (`tezgah-explorer`, `tezgah-reviewer`,
  `tezgah-researcher`, `tezgah-verifier`) plus un `tezgah-orchestrator`, rendus
  dans la surface native de chaque hôte installé (`.claude/agents/` pour Claude/Cursor,
  `.opencode/agents/` plus une injection de configuration en direct pour opencode, `.codex/agents/` pour Codex)
  et ignorés avec un bloc `.gitignore` géré. Sur Claude, la liste d'autorisation
  `Agent(tezgah-*)` de l'orchestrateur ne prend effet que lorsqu'il s'exécute en tant que
  thread principal (`claude --agent tezgah-orchestrator`) ; en tant que sous-agent, la liste est
  ignorée. dsh n'a pas de surface par rôle, donc la règle de routeur du contrat le couvre.

<a id="supported-hosts"></a>

## Hôtes pris en charge

| Hôte | Câblé par |
|---|---|
| **omp** (oh-my-pi) — principal | `~/.omp/agent` : bloc toujours actif `RULES.md` géré, compétences, sous-agents générés, `mcp.json`, et une extension (`hooks/pre/tezgah-hook.ts`) qui arme les règles par prompt, contrôle les outils, enregistre les preuves et exécute la règle Stop ; le câblage est vérifié par `tezgah-setup` |
| **Claude Code** | marketplace de plugins local : hooks, commandes, deux agents en lecture seule, style de sortie |
| **opencode** | plugin + instructions + MCP + routeur de compétences généré (liste de compétences native refusée), auto-indexation du dépôt au premier message |
| **Codex** | `hooks.json` + compétences + MCP, y compris une porte `PreToolUse` |
| **Cursor** | `hooks.json` + compétences + MCP |
| **dsh** | pont de hook Claude Code + bloc de patch géré (hooks, MCP, routes LLM, une ligne d'état Web hors arborescence) |

La porte Codex exécute Bash, `exec_command`, `apply_patch`, Edit/Write, les outils MCP,
et les appels de sous-agents via la même vérification que les autres hôtes. Sur Claude, l'interdiction
d'attribution est également appliquée mécaniquement : le paramètre `attribution` est
vidé (`commit`, `pr`, `sessionUrl`) de sorte que les crédits de commit et de PR sont désactivés à la source.

### Analyse d'application

`analyze-app` pilote une application en cours d'exécution à partir de son arbre d'accessibilité. La
boucle par défaut est : ouvrir, lire l'arbre, agir, observer la console/le réseau/les journaux, et
relire l'arbre — une capture d'écran est une action explicite pour ce à quoi l'arbre ne peut pas
répondre (canvas, jeu, animation, régression visuelle au niveau du pixel). La compétence est
un chemin unique pour tous les hôtes ; les serveurs sous-jacents constituent une spécification partagée dans
`hooks/tezgah_apps.py` :

| Serveur | Cible | Câblé par |
|---|---|---|
| `playwright` (`@playwright/mcp`) | pages web, outils `browser_*` | opencode, Codex, Cursor, Claude (plugin `.mcp.json`) |
| `mobile-mcp` (`@mobilenext/mobile-mcp`) | Simulateur iOS / émulateur Android, outils `mobile_*` | idem |
| `chrome-devtools` (opt-in, `--devtools`) | traces de perf web, réseau profond, console avec source-map | idem |

Le navigateur exécute un profil **isolé** par défaut, de sorte qu'une exécution ne touche jamais
votre véritable état Chrome ; l'analyse d'un flux connecté est un attachement délibéré
(`--cdp-endpoint` ou l'extension Playwright), et non un comportement par défaut. Les captures d'écran,
les traces et les vidages d'arbre atterrissent dans `~/.cache/tezgah/apps` (remplaçable avec
`TEZGAH_ARTIFACTS`) et l'agent récupère un chemin en retour, jamais d'octets d'image en ligne.
Les serveurs s'exécutent via `npx`, ils ont donc besoin de node mais d'aucune installation propre ;
`tezgah-setup --install --devtools` ajoute le serveur de diagnostics web optionnel.
dsh câble les deux mêmes serveurs via son pont `dsh-mcp-client`
(`serverName` / `command` / `args` / `env`, confirmé par rapport au schéma de configuration publié), et Claude les obtient à partir du `.mcp.json` du plugin
(`claude plugin details tezgah` liste les serveurs MCP 2 et les deux se connectent).
`mobile-mcp` est la moitié avec le plus de friction : macOS peut demander l'autorisation d'Accessibilité /
d'Enregistrement de l'écran et l'arbre des vues peut chuter sous la charge, la compétence
réessaie donc l'arbre avant de se rabattre sur une capture d'écran.

L'intégration continue (CI) exécute un handshake déterministe pour les deux serveurs (sans navigateur, sans appareil) :
`TEZGAH_E2E_STRICT=1 python3 tests/e2e_analyze_wiring.py`. Deux tests de fumée locaux optionnels
vont plus loin : `TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_web.py` démarre
Playwright MCP, navigue et lit le snapshot sans capture d'écran ;
`TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_mobile.py` démarre Mobile MCP, vérifie
les outils de l'arbre des vues et liste un appareil. Ils affichent `SKIP: ...` lorsque node, une
build de navigateur ou un appareil est manquant.

<a id="install"></a>

## Installation

Nécessite Python 3.10+. node + npm sont requis pour l'hôte dsh et, avec `pnpm`,
pour sa ligne d'état web. Les intégrations optionnelles se dégradent gracieusement :
`codegraph` dans le PATH alimente le graphe ; une clé de modèle alimente `consult`
et `codegen` — OpenRouter par défaut (`OPENROUTER_API_KEY` ou
`~/.config/openrouter/key`), l'API DeepSeek avec `--provider deepseek`
(`DEEPSEEK_API_KEY` ou `~/.config/deepseek/key`), ou Inception Labs avec
`--provider inception` (`INCEPTION_API_KEY` ou `~/.config/inception/key`) ; et
`orx` d'OpenResearch
dans le PATH donne à la règle de recherche quelque chose à piloter. Lorsque la clé du fournisseur
choisi est manquante, tezgah le signale au lieu de faire semblant.

Clonez, puis armez chaque hôte détecté en une seule passe :

```bash
git clone https://github.com/r1z4x/tezgah.git ~/Projects/tezgah
cd ~/Projects/tezgah
bin/tezgah-setup --install
```

Dans un terminal, cette commande sans argument est l'assistant d'installation à la place :
il demande quels hôtes armer, les répertoires racine, s'il faut installer les outils
optionnels manquants, et s'il faut câbler le DevTools MCP optionnel, affiche le plan, et
n'écrit qu'après un oui. Les options sont les valeurs par défaut de l'assistant
d'installation, donc `--wizard --hosts omp` ne demande que le reste. Une exécution en pipe,
par un agent ou en CI n'est jamais sollicitée — elle imprime le rapport, exactement comme
avant.

`--install` installe également les outils optionnels manquants en exécutant l'installateur
propre à chaque fournisseur **via le réseau** : `orx` (`openresearch.sh/install.sh`),
`cursor-agent` (`cursor.com/install`), `dsh` (son profil d'accueil via `npx`), et `pnpm`
lorsque dsh en a besoin (via `npm`) — `curl ... | sh` inclus. Aucun ne nécessite sudo ;
l'exécution est enregistrée dans `~/.config/tezgah/install.log`. Prévisualisez avec
`--dry-run`, ignorez-le avec `--no-deps` (utile en CI), ou installez les outils seuls avec
`--deps`. Les outils atterrissent dans `~/.local/bin` ou `~/.cargo/bin`, un nouveau shell
peut donc être nécessaire avant qu'ils ne soient dans le PATH ; les propres vérifications de
tezgah regardent dans ces répertoires quoi qu'il en soit, de sorte qu'un shell non
interactif les signale tout de même comme présents.

Si une configuration précédente est déjà présente, importez-la d'abord — elle est mise de côté,
et non supprimée :

```bash
bin/tezgah-setup --adopt
```

Claude Code est armé par le même script - le manifeste du plugin est un fichier local, non versionné :

```bash
bin/tezgah-setup --install --hosts claude
```

Limitez l'installation explicitement lorsque cela est nécessaire :

```bash
bin/tezgah-setup --install --hosts omp
bin/tezgah-setup --install --hosts claude,codex,cursor,opencode,dsh
bin/tezgah-setup --roots ~/work:~/oss --install
```

<a id="day-to-day"></a>

## Au quotidien

Rien à exécuter : les règles se chargent au démarrage d'un hôte. Quelques commandes méritent
d'être connues :

| Commande | Objectif |
|---|---|
| `bin/tezgah-setup` | Dans un terminal : l'assistant d'installation ; dans un pipe ou en CI : signaler ce qui est armé, par hôte |
| `bin/tezgah-setup --wizard` | Force l'assistant d'installation partout ; `--report` force le rapport |
| `bin/tezgah-status [PATH]` | Afficher si les règles sont actives dans ce dépôt |
| `bin/tezgah-setup --status [PATH]` | Afficher la liste de contrôle armée/utilisée |
| `bin/tezgah-setup --deps [--dry-run]` | Installer les outils optionnels manquants (orx, cursor-agent, dsh) |
| `bin/tezgah-research init\|check\|status\|claim\|migrate\|source` | Crée et vérifie une ligne de recherche : état, findings, claims avec leur type et leurs preuves, la règle protocole-avant-résultats et l'index de littérature ; `check --strict` refuse ce que le vérificateur ne peut pas établir, `migrate` remplit les champs manquants des lignes plus anciennes |
| `bin/tezgah-doctor [--clean] [--prune-sessions DAYS]` | Signaler l'utilisation du disque par le harnais ; `--clean` supprime les anciens journaux d'index et nettoie (vacuum) la base de données opencode ; `--prune-sessions` supprime les sessions inactives (la seule action qui réduit réellement la base de données) |
| `/tezgah:plan-add` | Transformer un travail en un plan suivi |
| `/tezgah:plan-status` | Résumer les plans ouverts et choisir le suivant |
| `/tezgah:plan-sync` | Clôturer les plans terminés |
| `bin/tezgah-setup --version` | Afficher la version du plugin |
| `bin/tezgah-setup --uninstall` | Supprimer uniquement les liens symboliques de tezgah, les entrées de hook de l'hôte et le bloc géré dsh |

La ligne d'état marque chaque règle avec son état d'abord : une coche signifie
armée et en vigueur dans cette session (ou toujours actif), un cercle signifie
armée mais à la demande - pas encore utilisée dans cette session - et une
croix signifie désactivée par un interrupteur d'arrêt ou une marque `.no-*`.
`pony` et `adhd` se lisent comme un cercle jusqu'à ce que la session ait
réellement lu le texte complet de cette compétence, puis comme une coche ; sur
Claude, opencode et omp cette lecture est observable, alors que sur codex,
cursor et dsh elle ne l'est pas à un coût acceptable, donc là ces deux marques
s'affichent en grisé et sans glyphe : la ligne n'affirme rien plutôt que de
prétendre que la compétence n'a jamais été ouverte. Un interrupteur d'arrêt
reste rouge partout.

<a id="configuration"></a>

## Configuration

Tezgah n'est armé que sous ses racines configurées ; partout ailleurs, il est silencieux.

- Racine par défaut : `~/Projects`.
- `~/.config/tezgah/config.json` : `{"roots": ["~/Projects", "~/work"]}`.
- `TEZGAH_ROOTS` (liste séparée par des séparateurs de chemin) remplace le fichier pour les cas ponctuels et la CI.

Les interrupteurs d'arrêt (kill switches) se trouvent dans `~/.config/tezgah/`. Chacun supprime sa règle du
texte injecté dans la session, de sorte que la règle s'arrête réellement :

| Interrupteur | Désactive |
|---|---|
| `exec-mode.off` | les rapports en turc axés sur les résultats |
| `ponytail-auto.off` | la règle du code minimal |
| `adhd-off` | la forme de sortie actionnable (i-have-adhd) |
| `spec-off` | la règle de spécification avant construction |
| `consult-off` | la règle du second avis externe |
| `research-off` | le routage des tâches de recherche vers OpenResearch |
| `orchestrate-off` | la délégation aux sous-agents (ajoute une ligne de non-délégation) |
| `reminder-off` | le texte de rappel à chaque tour |
| `pretooluse-off` | la porte PreToolUse elle-même (attribution, explorateur, incitation grep) |

Par dépôt, `.no-ponytail`, `.no-adhd`, `.no-graph` et `.no-lessons` désactivent
respectivement la règle du code minimal, la forme de sortie actionnable, la
règle du graphe de code (et son auto-indexation), et le registre des leçons.

Lorsque l'utilisateur signale une erreur, l'agent ajoute une leçon d'une ligne au fichier
`.tezgah/lessons.md` du dépôt ; les lignes les plus récentes sont injectées au démarrage de la session afin que
la même erreur ne puisse pas se répéter silencieusement.

<a id="benchmark"></a>

## Benchmark

Ce contrat améliore-t-il le travail, ou donne-t-il seulement l'impression qu'il le devrait ?
C'est mesuré, pas affirmé : des contrôles cachés dont l'agent ne voit jamais le test, le
coût tiré du propre relevé d'usage de l'hôte, et les modifications collatérales comptées
comme des échecs. L'instrument - les bras, la préinscription et `bench.py` - vit sur la
branche `benchmarks/lab`, donc cette branche porte les résultats et non le laboratoire ;
l'étude complète, avec les identifiants d'exécution, est le projet OpenResearch
`tezgah-harness-research`. Chaque chiffre ci-dessous est un journal d'exécution.

| Bloc | Exécutions | Ce qu'elle a établi |
|---|---|---|
| deux hôtes, 28 tâches, k=3 | 336 | `omp+tezgah` 0.95 et `opencode+tezgah` 0.96 ont des intervalles qui se chevauchent et le même coût par tâche résolue ; sur les bras nus, omp est moins cher ($0.0047 contre $0.0074 CPS), donc le pilote quotidien est omp sans coût en qualité |
| famille difficile, 5 tâches, k=5, deux familles de modèles | 200 | regroupés, trois des quatre bras tombent sur 40/50 : aucun effet du harnais à cette taille, et le seul signal produit par le premier modèle s'est inversé sur le second |
| famille de la porte, porte armée | 36 | aucun bras n'a pris la route du raccourci ; le mécanisme de la porte est vérifié directement (une modification de skip est refusée), son effet sur le travail n'est pas encore mesuré |
| ablation de clause, les deux règles qui séparent, k=8 | 160 | les bras avec contrat passent 23/32 (0.72) contre 12/32 (0.38) pour l'ancre nue |

**Il aide exactement là où la valeur par défaut du modèle est fausse.** `c04` (un prompt en
anglais où seul le contrat rend la réponse turque) lit 9/16 avec un contrat et 0/16 sans ;
`h02` (un contrat d'argent dont la suite visible est verte dans les deux cas) lit 14/16
contre 12/16. Là où il n'y a aucun écart à combler - 22 des 25 tâches pilotes ont passé sous
chaque bras à chaque répétition - un benchmark ne peut rapporter qu'un nul.

**Deux clauses le portent.** Retirer la clause 1 amène `c04` à 0/8, le score de l'ancre nue
elle-même, tout en bougeant à peine `h02`. Retirer la clause 3 amène `h02` à 2/8
- en dessous du 6/8 de l'ancre nue - parce que la clause 3 interdit de s'arrêter au chemin
le plus court qui a l'air terminé, et sur cette tâche le chemin le plus court est le
one-liner qui passe la suite visible tout en violant la règle documentée. Les clauses 2 et 4
ne bougent rien de mesurable.

**Le coût suit la qualité.** Par tâche résolue : $0.0078 contre $0.0097 sur le nœud contrat
complet, $0.0043 contre $0.0087 sur le nœud sans ponytail. Les bras avec contrat résolvent
plus de tâches, donc chaque tâche résolue coûte moins ; la dépense totale est plus élevée,
et le benchmark l'enregistre ligne par ligne plutôt que de la compenser.

Ce que cela ne montre pas : la qualité du code, l'effort de revue ou la maintenabilité, dont
rien n'est mesuré ici ; l'effet de la porte sur les choix d'un bras, puisque aucun bras n'a
cherché le raccourci en 36 exécutions armées ; ni un *ordre* de clauses - `k=8` fixe une
direction, à 8 exécutions par cellule. Un seul fournisseur et un seul paquet de fixtures
tout du long, et les tours d'ablation tournent sur une seule famille de modèles. Une seconde
famille de modèles reproduit exactement le nul des 28 tâches (51/56 contre 51/56), ce qui
montre que la première lecture n'était pas un artefact de modèle.

<a id="cost"></a>

## Coût

Mesuré sur cette machine (macOS, Python 3.10), pas estimé. `tezgah-setup` imprime le budget
en direct - lisez-le là plutôt que de faire confiance à un chiffre copié ici, ce qui a valu
à une révision antérieure de citer une bande de cœur plus petite que celle qu'elle installe.

| Bande | Ce qu'elle coûte |
|---|---|
| Démarrage de session | le contrat toujours actif (les invariants plus un pointeur d'une ligne par règle à la demande) : sur cette machine et ce jeu de compétences, ~1.5k tokens de texte de contrat et ~1.4k de métadonnées de compétences, les règles conditionnelles (spec, consult, research, graph) n'ajoutant ~0.7k que sur le tour dont le prompt correspond |
| Par tour | un court rappel (~0.2k tokens) plus la règle armée quand elle correspond ; les hooks sont des processus Python distincts, donc le démarrage de l'interpréteur de ~19 ms est la base - un tour ajoute ~31 ms, le démarrage de session ajoute ~50-81 ms, un appel d'outil contrôlé (Bash/Grep/Task) ~24-25 ms. opencode n'a pas de hook au moment du prompt, il ne paie donc rien |
| À la demande | la compétence complète `tezgah-contract` (~6.6k tokens), payée seulement quand une tâche la charge |
| Schémas MCP | la plus grande bande, et celle qu'aucun rapport statique ne voit : le serveur de graphe à lui seul déclare 15 outils / 24,508 octets (~6.1k tokens), embarqués dans chaque requête sauf si l'hôte récupère les schémas à la demande. `tezgah-setup --mcp-schemas` le mesure |
| Disque | l'installation prend ~58 ms, et chaque fichier que tezgah réécrit est conservé une fois sous `<file>.tezgah-bak` |

**Le plancher d'armement.** Les invariants sont toujours actifs - mode d'exécution,
ponytail, deliver-the-whole-ask, intégrité, discipline de boucle, le registre de leçons et
l'interdiction d'attribution - et la règle de sécurité (« les actions irréversibles ou
tournées vers l'extérieur exigent une demande explicite d'abord ») en fait partie, elle ne
dépend donc jamais d'un classifieur. Chaque règle consultative garde un pointeur d'une ligne
exploitable toujours actif, donc une correspondance manquée coûte du détail, jamais la
règle, et un hook d'hôte qui échoue retombe sur les pointeurs plus la compétence à la
demande plutôt que sur aucun contrat. Les faux négatifs sont auditables : chaque prompt
ajoute `armed=<rules|none> chars=<n>` - aucun texte de prompt - à
`~/.cache/tezgah/classify.log` (tronqué aux 200 dernières lignes au-delà de 64 KB), et les
cinq hôtes à hook arment le même ensemble pour le même prompt
(`tests/test_context.py::ArmingConformance`).

**opencode est armé différemment.** Il n'a pas de point d'injection au moment du prompt, le
contrat est donc livré sous forme de fichier d'instructions généré, et son routeur toujours
actif ne liste que les catégories auxquelles une session de codage fait appel, réduisant le
reste à un pointeur vers `~/.config/tezgah/opencode-skills.full.md` lu à la demande ;
`permission.skill = deny` empêche opencode d'injecter à la place les métadonnées de chaque
compétence. `--install` définit aussi `compaction.prune` et `watcher.ignore`, effaçant les
anciens résultats d'outils du prompt au lieu de les renvoyer à chaque étape - sans cela
l'ensemble de travail croît jusqu'à des centaines de milliers de tokens avant qu'opencode ne
se compacte automatiquement près de la limite du modèle (environ 980k pour un modèle de 1M
de tokens). `bin/tezgah-doctor` rapporte l'empreinte disque et `--prune-sessions DAYS`
supprime les sessions inactives via la CLI opencode, la seule action qui réduit réellement
la base de données, car VACUUM seul ne le peut pas.

**Pourquoi ça paie.** Dans un vrai dépôt, un `grep` par défaut a ignoré le dossier pertinent
et n'a rien trouvé ; avec l'ignorance désactivée, cela a pris 3.95 s et a encore mélangé les
définitions avec les sites d'appel, tandis que le graphe de code a répondu à la même
question en 16 ms avec les 8 véritables sites d'appel.

<a id="development"></a>

## Développement

```bash
python3 -m unittest discover -s tests -v   # stdlib test suite
pip install -r requirements-dev.txt        # pinned ruff, the only dev dep
ruff check .                               # lint (config in pyproject.toml)
```

La CI s'exécute à la fois sur Python 3.10 et 3.12. Pour actualiser une copie installée de Claude à partir de ce checkout, utilisez `bin/tezgah-setup --sync`, et validez le manifeste avec
`claude plugin validate .claude-plugin/plugin.json` (le manifeste est local et non versionné). Lors de l'incrémentation de la version,
mettez à jour `.claude-plugin/plugin.json` et `.claude-plugin/marketplace.json`
ensemble — ils doivent correspondre.

`codegraph` est installé par l'utilisateur. Les hooks et les fichiers d'Orca ne
font pas partie de ce projet et sont laissés intacts. Claude reçoit le cœur toujours actif
du hook SessionStart ; `output-styles/tezgah.md` est un doublon pour les builds
qui chargent les styles de sortie de plugin, le hook est donc le chemin faisant autorité.

<a id="contributing"></a>

## Contribution

Les petites modifications à but unique sont les plus faciles à accepter. Une règle appartient au
cœur partagé (`hooks/`) à moins qu'elle ne soit véritablement spécifique à l'hôte ; une différence d'hôte
appartient à son adaptateur sous `hosts/<name>/`. Gardez le diff aussi court que possible
tout en restant correct — la propre règle de code minimal du projet s'applique au projet.

Avant d'ouvrir une pull request, exécutez les trois mêmes vérifications que la CI :

```bash
python3 -m compileall -q hooks hosts bin statusline.py   # byte-compile every script
python3 -m unittest discover -s tests                     # stdlib test suite
ruff check .                                              # lint; config in pyproject.toml
```

`ruff` provient de `requirements-dev.txt` (`pip install -r requirements-dev.txt`),
qui est la seule dépendance de développement.

<a id="security"></a>

## Sécurité

Signalez les vulnérabilités en privé via les avis de sécurité de GitHub
(onglet **Security** → **Report a vulnerability**) plutôt que par un ticket public.

tezgah exécute des hooks shell, écrit la configuration de l'hôte et injecte du texte dans chaque
session, donc tout ce qui fait qu'un hook exécute du code contrôlé par un attaquant, divulgue
une clé dans un fichier de configuration, élargit une sandbox ou permet au contenu du dépôt de
s'élever au rang de texte d'instruction est dans le périmètre. Incluez l'hôte, la version de tezgah
(`bin/tezgah-setup --version`) et une reproduction minimale.

<a id="license"></a>

## Licence

Le fichier `LICENSE` (MIT) à la racine couvre les propres fichiers de tezgah. `skills/ponytail`,
`skills/no-ai-slop` et `skills/i-have-adhd` sont intégrés sous leurs propres termes MIT, enregistrés dans
`NOTICE`.
