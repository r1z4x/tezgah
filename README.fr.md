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

<p align="center"><sub>L'anglais est la source de vérité ; les traductions peuvent être en décalage.</sub></p>

---

Tezgah arme chaque assistant de codage IA que vous exécutez — **omp, l'hôte
principal**, plus Claude Code, Codex, Cursor, opencode et le dsh de DeepSeek —
avec un seul contrat de travail, à l'intérieur des racines de dépôts que vous
configurez. Laissés à eux-mêmes, les assistants divergent : l'un répond en
turc pendant qu'un autre répond en anglais ; l'un utilise grep là où un autre
interroge un graphe de code ; l'un annonce « terminé » sans exécuter de test.
Les règles résident une seule fois dans un cœur partagé ; chaque hôte reçoit
un adaptateur léger qui les traduit dans la forme qu'il comprend — une règle
modifiée à un endroit atteint chaque hôte de la même façon.

## Ce que tezgah impose et enregistre

- **Un contrat, six hôtes.** omp, Claude Code, Codex, Cursor, opencode et dsh
  voient les mêmes règles, car chaque hôte est un adaptateur léger au-dessus
  d'un seul cœur partagé — modifiez une règle une fois, tous l'adoptent.
- **Annoncer « terminé » exige une vérification réussie dans le registre.**
  Une porte de 15 refus arrête la vérification neutralisée — `--no-verify`,
  `|| true`, un test redirigé vers `tail`, un skip ajouté en plein vol — et la
  règle Stop refuse une affirmation d'achèvement que le registre de preuves de
  la session ne peut pas étayer. Elle refuse le tour ; elle ne peut pas
  empêcher le modèle de l'affirmer.
- **La recherche arrive avec sa bibliothèque.** Les tâches de recherche
  passent par OpenResearch avec une bibliothèque intégrée de 98 compétences
  upstream, chargée une entrée à la fois pour que le contexte reste petit.
- **Chaque règle a un interrupteur.** Seize interrupteurs — plus des
  marques par dépôt — retirent le texte de la règle de la session ; la règle
  s'arrête vraiment au lieu de simplement figurer comme désactivée.
- **Une forme de réponse fixe.** Les réponses sont en turc, sauf si vous choisissez une autre langue, et
  commencent par le résultat ; une liste montre au plus cinq éléments classés
  ; une estimation est nommée estimation ; une erreur se lit lieu, cause,
  correctif.

## Ce qu'il n'a pas démontré

Tezgah est un ensemble de mécanismes : des règles injectées dans la session,
une porte qui refuse certaines commandes et un registre que lit la règle Stop.
Ce n'est pas la preuve qu'un agent triche moins ou termine plus de tâches. Une
expérience appariée avec et sans tezgah (octobre 2026 ; DeepSeek V4.1 Flash
sur omp, sans tezgah contre une installation complète) n'a trouvé aucune
baisse mesurable de la triche, car le modèle n'a presque pas triché dans
aucun des deux bras :

- **Phase 1, trois fixtures de pression :** triche dans 0 exécution sur 60
  dans chaque bras ; réussite propre 48/60 avec tezgah contre 53/60 sans.
- **Phase 2, le split conflictuel SWE-bench d'ImpossibleBench (44 instances,
  k = 3) :** triche 0/132 avec tezgah contre 1/131 sans (-0.8 pp, IC à 95%
  -2.3 à 0) ; réussite propre sur les tâches originales 129/131 contre
  129/132.
- **Fausses annonces de fin, étiquetées à la main :** sur ces tâches
  impossibles, 3 messages finaux échantillonnés sur 30 avec tezgah et 6 sur 30
  sans ont dit à l'utilisateur que la tâche était faite. L'écart ajusté est de
  -5 pp (IC à 95% -18 à +9), donc aucun effet dans un sens ou dans l'autre.
- **Un point faible du lecteur d'affirmations de la règle Stop :** il a
  signalé 115/132 exécutions avec tezgah et 90/131 sans, mais seuls 10% et 20%
  de ses signalements étaient de vraies annonces de fin. Avec tezgah, l'agent
  répondait en turc, et le lecteur compte `doğrulandı` (vérifié) sur un
  correctif partiel comme une affirmation. C'est consigné, pas encore corrigé.

L'exécution avait des défauts d'instrument, entre autres des agents des deux
bras qui pouvaient lire la vérité terrain du benchmark. Les agrégats, les
comptes par tâche et chaque réserve sont dans le
[dossier de résultats](docs/results/paired-outcome-2026-10.md) (en anglais).

<a id="install"></a>

## Installation

Une ligne, sur macOS, Linux ou WSL (Python 3.10+, `curl`, `tar`). Elle
télécharge la dernière version, vérifie son sha256 et arme chaque hôte
trouvé (Claude Code par sa propre CLI `claude plugin`) :

```bash
curl -fsSL https://raw.githubusercontent.com/r1z4x/tezgah/main/packaging/install.sh | sh
```

Ou via npm : `npm i -g @r1z4x/tezgah && tezgah --install`.

Une configuration d'hôte illisible reste intacte, chaque configuration modifiée
garde une copie `.tezgah-bak` datée, et l'installation se termine avec un code
non nul quand un hôte prévu n'est pas armé.

### Ce que tezgah modifie sur votre machine

- **Configuration des hôtes.** Chaque hôte armé reçoit les hooks de tezgah, ses
  entrées MCP et un bloc de contrat géré dans son fichier de règles global
  (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.omp/agent/RULES.md`). Les
  hooks de Claude Code sont livrés dans un plugin enregistré par
  `claude plugin` ; sans CLI `claude`, Claude reste non armé et le rapport le
  dit.
- **Des fichiers d'agents dans vos dépôts.** Dans les racines configurées, une
  session écrit des fichiers de sous-agents dans `.claude/agents/`,
  `.codex/agents/` et `.opencode/agents/`, et ajoute ces répertoires au
  `.git/info/exclude` propre au clone (`TEZGAH_NO_EXCLUDE=1` l'empêche).
- **Une vérification quotidienne des mises à jour.** La ligne d'état demande
  une nouvelle version au plus une fois par jour ;
  `~/.config/tezgah/update-check-off` ou `TEZGAH_UPDATE_CHECK=0` la coupe.
- **orx.** L'installation télécharge la CLI OpenResearch par laquelle passent
  les tâches de recherche ; `TEZGAH_NO_DEPS=1` l'ignore.
- **Langue des réponses.** Les réponses sont en turc par défaut et la règle
  Stop les y tient. `--reply-lang en` demande l'anglais, et `any` votre propre
  langue ; aucun des deux n'est contrôlé : `curl -fsSL … | sh -s -- --reply-lang en`.

Vous préférez laisser votre assistant de codage s'en charger ? Collez ceci
dans omp, Claude Code, Codex, Cursor ou opencode (le prompt reste en anglais
; l'assistant le comprend dans toute langue) :

```text
Install tezgah (https://github.com/r1z4x/tezgah) on this machine and verify it.

1. Check the prerequisites: python3 --version must be 3.10 or newer, and curl
   and tar must exist. If one is missing, stop and tell me which.
2. Run the installer exactly as published - do not edit it or pipe it anywhere else:
   curl -fsSL https://raw.githubusercontent.com/r1z4x/tezgah/main/packaging/install.sh | sh
   Its output must contain "verified tezgah-<version>.tar.gz" (the sha256
   check). If it does not, stop and show me the output.
3. Verify: run ~/.local/share/tezgah/current/bin/tezgah-setup --version and
   ~/.local/share/tezgah/current/bin/tezgah-setup --report, and show me every
   line that says MISS.
4. Tell me which hosts were armed, which repository root was configured
   (default ~/Projects - if my code lives elsewhere, ask me for the directory and
   run ~/.local/share/tezgah/current/bin/tezgah-setup --roots <dir> --install),
   and that I must restart each assistant for the hooks to load.
Do not change any other file and do not uninstall anything.
```

Versions épinglées, Windows (`packaging/install.ps1`), archives hors ligne,
mises à niveau et intégrations optionnelles sont dans la [documentation](docs/README.md).

## Hôtes pris en charge

**omp** (l'hôte principal, contre lequel tezgah est développé et vérifié), **Claude Code**, **Codex**, **Cursor**, **opencode**, **dsh** — des adaptateurs légers au-dessus d'un seul cœur partagé.

## Où se trouve la profondeur

La porte, le registre de preuves, les adaptateurs d'hôtes, la configuration et le développement sont dans [docs/README.md](docs/README.md), une page par question.

## Licence

MIT — voir [LICENSE](LICENSE).
Les compétences intégrées (`ponytail`, `no-ai-slop`, `i-have-adhd`) suivent leurs propres termes MIT, consignés dans [NOTICE](NOTICE).
