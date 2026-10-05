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

## Pourquoi tezgah

- **Un contrat, six hôtes.** omp, Claude Code, Codex, Cursor, opencode et dsh
  voient les mêmes règles, car chaque hôte est un adaptateur léger au-dessus
  d'un seul cœur partagé — modifiez une règle une fois, tous l'adoptent.
- **« Terminé » signifie que la vérification a tourné.** Une porte de 15
  refus arrête la vérification neutralisée — `--no-verify`, `|| true`, un test
  redirigé vers `tail`, un skip ajouté en plein vol — et bloque l'affirmation
  d'achèvement que l'exécution ne peut pas étayer.
- **La recherche arrive avec sa bibliothèque.** Les tâches de recherche
  passent par OpenResearch avec une bibliothèque intégrée de 98 compétences
  upstream, chargée une entrée à la fois pour que le contexte reste petit.
- **Chaque règle a un interrupteur.** Seize interrupteurs — plus des
  marques par dépôt — retirent le texte de la règle de la session ; la règle
  s'arrête vraiment au lieu de simplement figurer comme désactivée.
- **Des réponses sur lesquelles agir.** Les réponses sont en turc et
  commencent par le résultat ; une liste montre au plus cinq éléments classés
  ; une estimation est nommée estimation ; une erreur se lit lieu, cause,
  correctif.

<a id="install"></a>

## Installation

Une ligne, sur macOS, Linux ou WSL (Python 3.10+, `curl`, `tar`). Elle
télécharge la dernière version, vérifie son sha256 et arme chaque hôte
trouvé :

```bash
curl -fsSL https://raw.githubusercontent.com/r1z4x/tezgah/main/packaging/install.sh | sh
```

Ou via npm : `npm i -g @r1z4x/tezgah && tezgah --install`.

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
