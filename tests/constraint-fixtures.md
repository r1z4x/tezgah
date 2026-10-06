# Constraint recogniser fixture

The sentences `hooks/tezgah_context.py::user_constraints` was measured on (plan
056 part h). `real` rows are sentences cut from user prompts in this machine's
omp and Claude transcripts. The set is 85 top-level sessions and 1,452 prompts
under `~/Projects`, read uncut on 2026-10-06 with `bin/tezgah-taste`'s walkers.
Each row is one sentence, never the whole prompt, with markup, paths and names
trimmed. `hand` rows are written probes for the shapes the real set lacks.

Labels:

- `constraint`: a constraint the user issued, and the recogniser pins it.
- `none`: not a constraint, and the recogniser leaves it.
- `missed`: a constraint the recogniser does not pin, kept so a widening is
  measured.
- `false-positive`: not meant as a constraint, yet pinned.

A row's source is `real`, `hand` or `pasted`. A `pasted` row is a sentence
from a pasted agent log: the shape pins it on its own, and the prompt-length
bound keeps it out of the prompt it came in.

A pinned row ends in `=> <pinned sentence> | <needle>`.

On the uncut real set the recogniser pins 7 sentences in 6 prompts, all real
constraints, and no false positive. Before the length bound and the quote rule
it pinned 17 times in 11 prompts, and one 387,905-char pasted agent log alone
held 6 of them. Three real constraints are now missed: one sits in a fenced
block, two sit in prompts over the length bound. The `pasted` false-positive
rows come from that log. The `hand` false-positive rows show the known limit,
a prohibition verb read without its sense.

- constraint (real): Sadece sunucu; üretime dokunma. => üretime dokunma | üretime
- constraint (real): - Üretim ortamına, gerçek kiracı verisine ve Play yorum verisine dokunma (fetcher kapalıysa => Üretim ortamına, gerçek kiracı verisine ve Play yorum verisine dokunma (fetcher kapalıysa | Play yorum verisine
- constraint (real): Target repository: the admin app. Do not modify tracked files: put any scratch output somewhere else. => Do not modify tracked files | tracked files
- constraint (real): - Do not remove necessary technical terms. => Do not remove necessary technical terms | necessary technical terms
- constraint (hand): don't touch hooks/hooks.json while at it => don't touch hooks/hooks.json while at it | hooks/hooks.json
- constraint (hand): never push to main without me => never push to main without me | main
- constraint (hand): README'ye dokunma => README'ye dokunma | README
- constraint (hand): bana sormadan push etme => bana sormadan push etme | push
- constraint (hand): Then apply them, but ask before applying. => ask before applying | applying
- constraint (hand): fix it but don't touch `hooks/hooks.json` please => don't touch `hooks/hooks.json` please | hooks/hooks.json
- constraint (hand): don't touch "config.json" while at it => don't touch "config.json" while at it | config.json
- constraint (hand): `README`'ye dokunma => `README`'ye dokunma | README
- none (real): bana sormadan paralel olarak devam et
- none (real): devam et bana sormadan hızlıca sonlandır.
- none (real): Kontrast, dokunma hedefi, focus sırası → ölç ya da ekran görüntüsü
- none (real): Do not improvise a lighter method.
- none (real): Bitince: compileall + ruff + dokunduğun test modülleri; çıktıyı dosyaya yaz.
- none (real): Diğer projelerin volume'larına dokunmadım ve şu an da dokunmuyorum.
- none (real): Do not invent facts, requirements, measurements, sources, or implementation details.
- none (real): Don't paraphrase; don't skip the patches.
- none (real): Never run bare
- none (real): Continue the task you were working on when the limit was reached; do not repeat work that is already complete.
- none (real): Wait, "Do not modify tracked files" means writing new untracked files under gitignored analysis is fine.
- none (hand): mobilde dokunma alanı çok küçük
- none (hand): add a docstring to parse_quantity
- none (hand): keep the line `don't touch hooks.json` in the doc
- missed (real): Ama önce bana sor.
- false-positive (pasted): Never touch existing dev.db / shared volumes; if the default dev DB already exists, stop. => Never touch existing dev.db / shared volumes | existing dev.db
- false-positive (pasted): Verify the dev DB is disposable; never touch docker volumes shared names. => never touch docker volumes shared names | docker volumes shared
- false-positive (pasted): Do not modify tracked files; report any throwaway scripts left in runtime/. => Do not modify tracked files | tracked files
- false-positive (hand): never change a winning team => never change a winning team | winning team
- false-positive (hand): don't touch base with them until Monday => don't touch base with them until Monday | base
