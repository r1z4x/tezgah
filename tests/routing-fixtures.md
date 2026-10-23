# Routing fixtures

A situation a session actually gets handed, the skill it should reach, and the
words the generated router line has to keep for that to happen. The router is
generated from the descriptions, so a reworded description can drop the one term
a situation matches on and nothing else in the suite notices: this table is the
regression net. It is checked by `tests/test_setup.py::RoutingFixtures`, against
the routers the installer writes (`opencode-skills.md` and its on-demand
`opencode-skills.full.md`).

Three rules for a row:

- the skill is a name in `bin/tezgah-setup`'s `SKILLS`, and every name there has
  at least one row here - a skill with no fixture is one nothing proves reachable;
- the phrase in the last column has to sit inside the router line's 140-character
  cut, because a trigger past the cut names a skill a session cannot match, and
  inside the description's first 100 characters, the part omp still shows
  (`tests/test_skills.py`);
- a skill users ask for in Turkish carries a Turkish row too: its phrase is a
  Turkish word the description leads with.

| situation | skill | the router line must keep |
|---|---|---|
| an audit, "every call site", "what breaks if", a task too wide for one context | `harness` | every call site |
| the deep detail behind the compact core: the code graph, a subagent fan-out, codegen, a second opinion | `tezgah-contract` | subagent fan-out |
| any coding task - writing, fixing, refactoring, choosing a dependency | `ponytail` | refactoring |
| a fix, a plan, a report or a status update the reader has to act on | `i-have-adhd` | act on |
| a draft that must read less AI-sounding, or a question whether writing does | `no-ai-slop` | AI-sounding |
| verify a running app - walk a flow, read the UI or the console | `analyze-app` | walk a flow |
| "track this as a plan", work that spans sessions | `plan-add` | track this as a |
| "what plans are open", plan status at the start of a session | `plan-status` | what plans are open |
| "sync plans", close finished plans whose PR merged | `plan-sync` | sync plans |
| a deliverable that is evidence: a literature or reference review, a hypothesis | `research` | literature or reference review |
| product analysis, UX audit, competitor teardown, retention or churn | `product-analysis` | retention |
| "bu veriye uygun metric dashboard tasarla", a new metric or feature carried from research to re-measure | `product-flow` | metric dashboard |
| one existing feature - an admin panel, a CRUD screen, a wizard, a data table | `feature-audit` | admin panel |
| a UI turn that needs a design floor, tokens or a named state set | `design-contract` | design floor |
| a UI or product turn that needs a cognitive-load or visual-critique method | `design-library` | cognitive-load |
| a new page or landing page that must look designed rather than generated, or "redesign this page" | `hallmark` | Hallmark |
| a product question that needs the method, not the framework name: opportunity solution trees | `pm-frameworks` | opportunity solution trees |
| AI or ML machinery: training, fine-tuning, serving, evaluating a model | `ai-research` | fine-tuning |
| an agent that has to be trained with RL - build or port the environment it runs in | `rl-env` | RL training environment |
| "bunu detaylı incele, tüm çağrı noktalarını bul" | `harness` | detaylı incele |
| "alt ajan çalıştır, kod grafiğine bak, ikinci görüş al" | `tezgah-contract` | alt ajan |
| "minimum kod yaz, kütüphane ekleme" | `ponytail` | minimum kod |
| "kısaca, adım adım söyle ne yapmam lazım" | `i-have-adhd` | adım adım |
| "bu metin yapay zeka gibi duruyor, insani yaz" | `no-ai-slop` | yapay zeka gibi |
| "uygulamayı aç, ekranları gez, konsolda hata var mı bak" | `analyze-app` | uygulamayı aç |
| "bunun için plan oluştur, birkaç oturum sürecek" | `plan-add` | plan oluştur |
| "açık planlar neler, hangisine devam edelim" | `plan-status` | açık planlar |
| "merge edildi, biten planları kapat" | `plan-sync` | biten planları kapat |
| "literatür taraması yap, hipotezi kaynakla test et" | `research` | literatür |
| "ürün analizi yap: kullanıcı neden bırakıyor, rakip ne yapıyor" | `product-analysis` | ürün analizi |
| "yeni özellik ekleyelim, metriğini ölç" | `product-flow` | yeni özellik |
| "bu formu uçtan uca denetle: servis, veritabanı, panel" | `feature-audit` | uçtan uca denetle |
| "bu ekranın tasarımı tutarsız, renk ve boşlukları düzelt" | `design-contract` | tasarım |
| "bilişsel yük çok, görsel hiyerarşiyi eleştir" | `design-library` | bilişsel yük |
| "bunu fırsat çözüm ağacı ile çıkar" | `pm-frameworks` | fırsat çözüm ağacı |
| "dil modeline ince ayar yap, benchmark koş" | `ai-research` | ince ayar |
| "pekiştirmeli öğrenme için bir ortam kur" | `rl-env` | pekiştirmeli öğrenme |
