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
  La validation, la gestion des erreurs et la sécurité ne sont jamais simplifiées à l'excès.
- **Découverte axée sur le graphe de code.** « Où est X », « qui appelle Y », « qu'est-ce qui casse si
  Z change » passent par le graphe `codebase-memory-mcp` (`search_graph`,
  `trace_path`, `search_code`), et non par grep. Grep reste approprié pour le texte littéral,
  les configurations et les fichiers non liés au code.
- **Analyse d'application axée sur l'accessibilité.** Une application web ou mobile en cours d'exécution est lue
  via son arbre d'accessibilité / DOM / vue native, et non par une capture d'écran à chaque étape.
  `analyze-app` couvre un navigateur (Playwright MCP), un simulateur iOS ou un émulateur Android
  (Mobile MCP), et des diagnostics web optionnels (Chrome DevTools MCP) ;
  une capture d'écran est une action explicite, à la demande, pour ce à quoi l'arbre ne peut pas répondre.
- **Second avis externe.** Avant une décision non triviale ou difficile à annuler,
  `~/.config/tezgah/bin/consult` interroge des modèles indépendants via OpenRouter (ou
  l'API DeepSeek avec `--provider deepseek`) en parallèle, et l'agent signale sur quels points ils
  sont d'accord ou en désaccord.
- **Recherche via OpenResearch.** Lorsque le routeur juge qu'une tâche relève de la recherche — une
  revue de littérature, la formulation et le test d'hypothèses, l'exécution d'expériences, un
  artefact de recherche — il pilote le travail via OpenResearch d'alphaXiv (`orx`)
  et charge d'abord le manuel `orx`, au lieu d'improviser le protocole. La simple
  découverte de code reste sur le graphe de code. Lorsque `orx` est absent, le routeur le signale
  et se rabat sur un sous-agent de l'hôte.
- **Honnêteté sous vérification.** Rien n'est signalé comme terminé, testé ou corrigé
  à moins que le résultat n'ait été vu. Un test qui échoue est signalé comme tel avec son
  erreur exacte, et une vérification ignorée est déclarée clairement.
- **Aucune attribution à l'IA, nulle part.** Rien de ce qui est persisté ou publié — messages de commit,
  de fusion et de tag, textes de PR et de tickets, commentaires de code, en-têtes de fichiers, documentation
  — ne doit créditer l'assistant, le modèle, le fournisseur ou « l'IA ». Utiliser un outil est acceptable ;
  signer votre travail de son nom ne l'est pas.
- **Orchestration à deux niveaux.** Le thread principal décide et vérifie ; un modèle
  peu coûteux (`~/.config/tezgah/bin/codegen`, OpenRouter par défaut ou `--provider deepseek`) rédige
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

| Hôte | Câblé par | Ligne d'état |
|---|---|---|
| **Claude Code** | marketplace de plugins local : hooks, commandes, deux agents en lecture seule, style de sortie | `statusLine` native |
| **opencode** | plugin + instructions + MCP + routeur de compétences généré (liste de compétences native refusée), auto-indexation du dépôt au premier message | plugin TUI (pas de statusLine de commande) |
| **Codex** | `hooks.json` + compétences + MCP, y compris une porte `PreToolUse` | hook `systemMessage` (la liste des éléments du pied de page est fermée) |
| **Cursor** | `hooks.json` + compétences + MCP | `statusLine` dans `cli-config.json` |
| **dsh** | pont de hook Claude Code + bloc de patch géré (hooks, MCP, routes LLM, une ligne d'état Web hors arborescence) | plugin d'interface Web : `tezgah-dsh-statusline` dans l'en-tête de session |

La porte Codex exécute Bash, `exec_command`, `apply_patch`, Edit/Write, les outils MCP,
et les appels de sous-agents via la même vérification que les autres hôtes. Sur Claude, l'interdiction
d'attribution est également appliquée mécaniquement : le paramètre `attribution` est
vidé (`commit`, `pr`, `sessionUrl`) de sorte que les crédits de commit et de PR sont désactivés à la source.

### Ligne d'état

Chaque hôte affiche la même liste de contrôle sur une ligne provenant de `tezgah-status`, ils
ne peuvent donc pas dériver. L'état est l'essentiel : une marque est **verte** lorsque la règle est armée
et en vigueur pour cette session, **jaune** lorsqu'elle est armée mais à la demande (pas encore utilisée),
et **rouge** lorsqu'un interrupteur d'arrêt (kill switch) l'a désactivée. `idx` signale l'état de préparation du graphe
séparément (`✓` indexé, `↻` obsolète, `✗` non indexé, `–` non applicable) et
`plans N (M blk)` les plans ouverts. `tezgah-status --legend` affiche la légende,
`--json` donne les mêmes segments pour une interface utilisateur, et `--no-color` (ou `NO_COLOR`)
force le texte brut. Claude Code et Cursor colorent la ligne d'état native ; l'interface TUI
d'opencode colore son propre composant et s'actualise sur le bus d'événements de l'hôte ; l'interface Web
de dsh colore son composant d'en-tête et ne s'actualise que lorsque son onglet est visible ; Codex affiche la chaîne brute dans `systemMessage`.

dsh exécute les mêmes fichiers de hook Claude via son pont `dsh-hooks-claude-code`,
de sorte que le contrat de début de session, la porte d'attribution et l'incitation au premier grep
s'y appliquent tous. dsh expose un seul outil `subagent`, le refus de l'explorateur uniquement basé sur grep
est donc inerte — il n'y a pas de sous-agent explorateur à refuser. La sandbox `workspace-write`
par défaut de dsh confine les sous-processus de hook à l'espace de travail et au répertoire temporaire de la plateforme,
tezgah écrit donc l'état de son hook (marques d'incitation, horodatage d'index) vers une solution de repli
accessible en écriture à cet endroit plutôt que d'échouer sur un refus d'écriture. Le worker d'indexation du graphe
ne peut pas écrire dans le cache `codebase-memory-mcp` depuis l'intérieur de cette sandbox, le lanceur `dsh`
préchauffe donc l'index dans le shell non confiné de l'utilisateur avant de démarrer dsh — un nouveau dépôt est
indexé exactement comme sur les autres hôtes, estampillé HEAD. Une session démarrée sans le lanceur reçoit tout de même un rapport clair indiquant que le serveur MCP hors sandbox sert le graphe et a besoin de `index_repository` pour un dépôt qu'il n'a pas indexé, au lieu d'une erreur brute `EPERM`. Le bloc de patch géré déclare également deux routes LLM compatibles OpenAI sur l'adaptateur pi-ai que la composition de base monte : `openrouter` (`OPENROUTER_API_KEY`) et `deepseek` (`DEEPSEEK_API_KEY`), sélectionnables aux côtés du paramètre par défaut natif `deepseek-official`. Les clés sont résolues à partir de l'environnement de lancement ou du magasin d'identifiants du harnais ; aucune des clés n'entre dans le fichier de configuration. tezgah-setup place également un lanceur `dsh` dans le PATH (`~/.local/bin/dsh`) qui trouve la CLI installée sous `$DSH_HOME`, de sorte que `dsh --profile web` fonctionne depuis n'importe quel répertoire.

dsh n'a pas de ligne d'état de commande, tezgah en fournit donc une sous forme de plugin d'interface Web :
`tezgah-dsh-statusline`. Sa moitié hôte sert la chaîne `tezgah-status` pour
l'espace de travail de la session sur une route authentifiée `/api/tezgah.status` (avec
`?format=json` pour la vue colorée) ; sa moitié navigateur la rend dans l'en-tête de session, colorée selon l'état avec une légende au survol/clic, et ne s'actualise que lorsque l'onglet est visible. `tezgah-setup`
lie le plugin dans le profil web et l'active avec une ligne gérée dans
`profiles/web/cordis.patch.yml` (web uniquement, car la moitié hôte injecte le
service `connection` exclusif au web) ; un profil qui n'a jamais démarré `web` est ignoré avec une indication au lieu d'être écrit à moitié. En mode `headless`, le pont de hooks injecte le contrat SessionStart comme son propre tour final (son `agent/session-start` appelle `agent.inject()` de manière détachée, après que la tâche ponctuelle soit déjà le premier message), ainsi `dsh --profile headless "<task>"` dépense un tour supplémentaire et, pour un prompt à réponse littérale, affiche la réaction du modèle au contrat plutôt que la réponse de la tâche ; les sessions web interactives ne sont pas affectées.

`bin/tezgah-setup --install` déclenche également `orx install-skills` pour Claude,
Codex, opencode et Cursor lorsque `orx` est dans le PATH, afin que la règle de recherche ait un
manuel à charger. Les fichiers shim appartiennent à orx, tezgah exécute donc uniquement cet installateur
et ne les liste jamais pour la désinstallation. dsh n'a pas de harnais orx ; la règle de recherche
s'y rabat sur `orx skill` dans le shell.

Le plugin Claude fournit également deux agents en lecture seule. `agents/tezgah-explorer.md`
effectue la découverte de code à partir du graphe et renvoie des preuves `file:line` ;
`agents/tezgah-reviewer.md` transforme un diff en son ensemble d'impacts avec
`detect_changes` puis recherche de véritables défauts. Tous deux ont les outils d'écriture et de commande désactivés ; leur sortie est consultative.

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

Nécessite Python 3.8+. node + npm sont requis pour l'hôte dsh et, avec `pnpm`,
pour sa ligne d'état web. Les intégrations optionnelles se dégradent gracieusement :
`codebase-memory-mcp` dans le PATH alimente le graphe ; une clé de modèle alimente `consult`
et `codegen` — OpenRouter par défaut (`OPENROUTER_API_KEY` ou
`~/.config/openrouter/key`), ou l'API DeepSeek avec `--provider deepseek`
(`DEEPSEEK_API_KEY` ou `~/.config/deepseek/key`) ; et `orx` d'OpenResearch
dans le PATH donne à la règle de recherche quelque chose à piloter. Lorsque la clé du fournisseur
choisi est manquante, tezgah le signale au lieu de faire semblant.

Clonez, puis armez chaque hôte détecté en une seule passe :

```bash
git clone https://github.com/r1z4x/tezgah.git ~/Projects/tezgah
cd ~/Projects/tezgah
bin/tezgah-setup --install
```

`--install` installe également les outils optionnels manquants en exécutant
l'installateur propre à chaque fournisseur **via le réseau** : `orx`
(`openresearch.sh/install.sh`), `cursor-agent` (`cursor.com/install`), `dsh`
(son profil d'accueil via `npx`), et `pnpm` lorsque dsh en a besoin (via `npm`) —
`curl ... | sh` inclus. Aucun ne nécessite sudo ; l'exécution est enregistrée dans
`~/.config/tezgah/install.log`. Prévisualisez avec `--dry-run`, ignorez-le avec
`--no-deps` (utile en CI), ou installez les outils seuls avec `--deps`. Les outils atterrissent
dans `~/.local/bin` ou `~/.cargo/bin`, un nouveau shell peut donc être nécessaire avant
qu'ils ne soient dans le PATH ; les propres vérifications de tezgah regardent dans ces répertoires quoi qu'il en soit, de sorte qu'un shell non interactif les signale tout de même comme présents.

Si une configuration précédente est déjà présente, importez-la d'abord — elle est mise de côté,
et non supprimée :

```bash
bin/tezgah-setup --adopt
```

Claude Code s'installe via son propre canal de plugins :

```bash
claude plugin marketplace add ~/Projects/tezgah
claude plugin install tezgah@rizacan-local
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
| `bin/tezgah-doctor [--clean] [--prune-sessions DAYS]` | Signaler l'utilisation du disque par le harnais ; `--clean` supprime les anciens journaux d'index et nettoie (vacuum) la base de données opencode ; `--prune-sessions` supprime les sessions inactives (la seule action qui réduit réellement la base de données) |
| `/plan-add` | Transformer un travail en un plan suivi |
| `/plan-status` | Résumer les plans ouverts et choisir le suivant |
| `/plan-sync` | Clôturer les plans terminés |
| `bin/tezgah-setup --version` | Afficher la version du plugin |
| `bin/tezgah-setup --uninstall` | Supprimer uniquement les liens symboliques de tezgah, les entrées de hook de l'hôte et le bloc géré dsh |

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
| `spec-off` | la règle de spécification avant construction |
| `consult-off` | la règle du second avis externe |
| `research-off` | le routage des tâches de recherche vers OpenResearch |
| `orchestrate-off` | la délégation aux sous-agents (ajoute une ligne de non-délégation) |
| `reminder-off` | le texte de rappel à chaque tour |
| `pretooluse-off` | la porte PreToolUse elle-même (attribution, explorateur, incitation grep) |

Par dépôt, `.no-ponytail`, `.no-cbm` et `.no-lessons` désactivent respectivement la règle du code minimal,
la règle du graphe de code (et son auto-indexation), et le registre des leçons.

Lorsque l'utilisateur signale une erreur, l'agent ajoute une leçon d'une ligne au fichier
`.tezgah/lessons.md` du dépôt ; les lignes les plus récentes sont injectées au démarrage de la session afin que
la même erreur ne puisse pas se répéter silencieusement.

<a id="cost"></a>

## Coût

Mesuré sur cette machine (macOS, Python 3.10), et non estimé :

- **Contexte.** Un démarrage de session injecte ~4,8 Ko (~1,3k tokens) de texte de contrat.
  Sur Codex, un rappel de 480 octets accompagne chaque tour ; Claude et les autres hôtes n'ont
  pas de hook par tour, leur coût par tour est donc nul. La compétence complète `tezgah-contract`
  (~19,9k caractères) n'est payée que lorsqu'une tâche la charge. Sur opencode le contrat est fourni
  sous forme de fichier d'instructions de ~5,5 Ko. Autrement, opencode injecterait ~53 Ko de texte de nom/description/emplacement de compétence dans le prompt système de chaque session ; tezgah refuse cette liste (`permission.skill = deny`) et fournit à la place un routeur de compétences généré de ~16 Ko, de sorte qu'une compétence est trouvée en lisant son chemin `SKILL.md` à partir du routeur.
- **Latence.** Les hooks sont des processus Python séparés, le démarrage de l'interpréteur de ~19 ms domine donc. En plus de cela, le démarrage de la session ajoute ~25 ms, un appel d'outil contrôlé
  (Bash/Grep/Task) ajoute ~9 ms, et le segment Stop de Codex ajoute ~15 ms par tour.
- **Disque.** L'installation prend ~58 ms et chaque fichier que tezgah réécrit est conservé
  une fois sous la forme `<file>.tezgah-bak`.

Le bénéfice apparaît sur les questions de l'appelant. Dans un dépôt réel, un `grep` par défaut a
ignoré le dossier pertinent et n'a rien trouvé ; avec l'ignorance désactivée, cela a pris
3,95 s et a tout de même mélangé les définitions avec les sites d'appel. Le graphe de code a répondu à
la même question en 16 ms, en ne listant que les 8 véritables sites d'appel.

opencode est également armé pour l'hygiène du contexte des sessions longues : `tezgah-setup --install`
définit `compaction.prune` afin que les anciens résultats d'outils soient effacés du prompt au lieu
d'être renvoyés à chaque étape, et une liste `watcher.ignore` maintient l'observateur de fichiers
hors de `.git`, `node_modules` et des répertoires de build. Les deux fusionnent — une valeur utilisateur explicite
l'emporte. Cela a de l'importance car opencode ne s'auto-compacte que près de la limite de contexte du modèle
(pour un modèle de 1M de tokens, environ 980k), donc sans élagage, l'ensemble de travail
s'accroît jusqu'à des centaines de milliers de tokens. `bin/tezgah-doctor` signale
l'empreinte disque résultante ; `--prune-sessions DAYS` supprime les sessions inactives via
la CLI opencode, ce qui est la seule action qui réduit réellement la base de données —
VACUUM seul ne le peut pas, car ses pages sont toutes actives.

<a id="development"></a>

## Développement

```bash
python3 -m unittest discover -s tests -v   # stdlib test suite
pip install -r requirements-dev.txt        # pinned ruff, the only dev dep
ruff check .                               # lint (config in pyproject.toml)
```

La CI s'exécute à la fois sur Python 3.10 et 3.12. Pour actualiser une copie installée de Claude à partir de ce checkout, utilisez `bin/tezgah-setup --sync`, et validez le manifeste avec
`claude plugin validate .claude-plugin/plugin.json`. Lors de l'incrémentation de la version,
mettez à jour `.claude-plugin/plugin.json` et `.claude-plugin/marketplace.json`
ensemble — ils doivent correspondre.

`codebase-memory-mcp` est installé par l'utilisateur. Les hooks et les fichiers d'Orca ne
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

Le fichier `LICENSE` (MIT) à la racine couvre les propres fichiers de tezgah. `skills/ponytail` et
`skills/no-ai-slop` sont intégrés sous leurs propres termes MIT, enregistrés dans
`NOTICE`.
