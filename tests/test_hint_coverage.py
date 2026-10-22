"""The arming corpus: which request arms which conditional rule.

Built from an internal survey - eleven
scout slices over the five classes, their Turkish phrasings, the wiring
surfaces and a corpus proposal - and frozen after review. Of the 114 rows the
survey proposed, twelve disagreed with the widened table; ten of those were the
table's own better answer (a surface ask pays `product` and `spec`, an A/B test
pays `research` as well, security and migration are `consult`'s), and two were
real defects the review fixed before freezing (`unprofessional` never matched
the bare `professional`; `animations` never matched the singular). The
narrowing's second pass added fifteen more - the six craft words that are also
ordinary English nouns, the UI asks that pass dropped with them, and the
positive half of every negative row - so the table holds 142, and the corpus
holds one row for every one of them. One row per request: the prompt is the
assertion and the set is what the reviewed table answers.

A failure here is a request that stopped reaching its rule, which is the defect
this corpus exists to catch - the arming is what makes a rule reach a session at
all, and a rule that never arms is indistinguishable from one that is wrong.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))
import tezgah_context as tc  # noqa: E402


CORPUS = {
    # spec
    "normal user behavior yeterli bu kadar": {"spec"},
    "make the settings page nicer": {"spec"},
    "clean ui please": {"spec", "design"},
    "more intuitive please": {"spec"},
    "the copy feels unprofessional": {"spec"},
    "düzgün çalışsın artık": {"spec"},
    "güzel görünsün": {"spec"},
    "metin biraz daha iyi olsun": {"spec"},
    "kullanıcı dostu olsun": {"spec"},
    "bu sayfanın css'ini tailwind'e taşı": {"product", "spec"},
    "admin componentlerini refactor et": {"spec"},
    "hover ve focus durumları eksik": {"spec"},
    "tasarımı responsive yap": {"spec", "design"},
    "dark mode ekle": {"spec", "design"},
    "bu componentin erişilebilirliğini düzelt": {"spec", "design"},
    "the layout is broken on mobile": {"spec", "design"},
    "add a wireframe for the checkout flow": {"spec", "design"},
    "spacing looks off in the header": {"spec"},
    "make it look better": {"spec"},
    # the qualified craft words, said the way a UI ask says them: every one of
    # these is the positive half of a negative row in the trap block below
    "center the login form": {"spec"},
    "the margins are off in the header": {"spec"},
    "the form's margins are too tight": {"spec"},
    "the page is cluttered": {"spec", "design"},
    "the badges look wrong": {"spec"},
    "skeleton loaders on the card": {"spec"},
    "theme tokens in the app": {"spec"},
    # the UI asks the narrowing dropped with the bare `refactor` alternation
    "refactor the login form": {"spec"},
    # the align family as a person writes it: the hint's `-?` allowed only a
    # hyphen between the two words, so "align items" armed nothing and neither
    # adjective form was a hint at all
    "align items in the header": {"spec"},
    "the flex row is misaligned": {"spec"},
    "the alignment is off": {"spec"},
    # and the two that already armed it stay armed: the property spelling and
    # the Turkish stem
    "align-items on the row": {"spec"},
    "hizala": {"spec"},
    # consult
    "deploy to production": {"consult"},
    "is this migration reversible, can we rollback?": {"consult"},
    "root cause of the flaky test": {"consult"},
    "which approach for the schema change?": {"consult"},
    "security review before we ship": {"consult"},
    "this is a design decision, not a bug": {"consult"},
    "the architecture is tangled, is a rewrite a trade-off?": {"consult"},
    "decide the migration path for the tenants": {"consult"},
    "migrate the DB to a new schema": {"consult"},
    "geri dönüşü olmayan bir karar mı": {"consult"},
    "kök nedenini bulalım": {"consult"},
    "mimarisini yeniden kuralım": {"consult"},
    "bu değişiklik irreversible mı": {"consult"},
    "which approach should we take": {"consult"},
    # research
    "run a literature review and form a hypothesis": {"research"},
    "research the literature on X": {"research"},
    "form a hypothesis and test it": {"research"},
    "run an ablation on the model": {"research"},
    "tune the hyperparameter search": {"research"},
    "benchmark these two approaches": {"research"},
    "survey the prior art": {"research"},
    "collect a dataset for the eval": {"research"},
    "read the paper and summarise it": {"research"},
    "experiment with two variants": {"research"},
    "araştırma yap": {"research"},
    "hipotezi test et": {"research"},
    "literatür taraması": {"research"},
    "deney kur": {"research"},
    # product
    "bu ürünü analiz et ve nasıl iyileştirebiliriz": {"product"},
    "ürünümüzü nasıl iyileştiririz": {"product"},
    "ürünle alakalı analiz istiyorum": {"product"},
    "ürün keşfi için bir çalışma yapalım": {"product"},
    "product manager seviyesinde analiz yap": {"product"},
    "retention düşüyor ne yapmalıyız": {"product"},
    "which feature should we build next": {"product"},
    "review this backlog before the roadmap review": {"product"},
    "north star metriğimiz ne": {"product"},
    "cohort analizi yapalım": {"product"},
    "dönüşüm oranını artıralım": {"product"},
    "fiyatlandırmayı gözden geçir": {"product"},
    "churn artıyor, onboarding'i düzeltelim": {"product"},
    "ab test kuralım": {"product", "research"},
    "müşteri geri bildirimlerini topla": {"product"},
    "jtbd çalışması yapalım": {"product"},
    "bu filtre çalışmıyor": {"product"},
    "bu tabloyu iyileştir": {"product"},
    "ekranı incele": {"product"},
    "arama kutusu çok yavaş": {"product"},
    "kullanıcı listesi ekranında crud var mı": {"product"},
    "admin paneldeki users ekranını incele": {"product"},
    "adım akışını sadeleştir": {"product", "spec"},
    "add a wizard for the signup steps": {"product"},
    "the data table pagination is wrong": {"product", "spec"},
    "check the form validation on signup": {"product"},
    # graph
    "who calls calc_total?": {"graph"},
    "callers of parse_quantity": {"graph"},
    "call sites of the auth check": {"graph"},
    "who invokes the hook": {"graph"},
    "who uses this module": {"graph"},
    "what breaks if I change the schema?": {"graph"},
    "blast radius of this edit": {"graph"},
    "where is the retry helper defined?": {"graph"},
    "where's the config loader": {"graph"},
    "definition of this type": {"graph"},
    "bu fonksiyonu kim çağırıyor?": {"graph"},
    "çağrı yerleri nerelerde": {"graph"},
    "bu nerede tanımlı": {"graph"},
    "bu modül nasıl bağlanmış?": {"graph"},
    "bu değişiklikten hangi dosyalar etkilenir": {"graph"},
    # negative: must arm nothing
    "add a docstring to parse_quantity": set(),
    "improve developer productivity": set(),
    "the build is productive now": set(),
    "ekran kartı sürücüsünü güncelle": set(),
    "adım sayısını azalt": set(),
    "format the output as json": set(),
    "kullanıcı deneyimi raporu": set(),
    "nasılsın, bugün bir sorun var mı?": set(),
    "deployment failed in CI": set(),
    "migrating the DB to Postgres": set(),
    "is this reversible?": set(),
    "güvenlik açığı var mı": {"consult"},
    "göç planını yazalım": {"consult"},
    "dağıtım başarısız oldu": set(),
    "bu sayfayı düzelt": {"product"},
    "kullanıcı görüşmeleri yapalım": {"research"},
    "how is this wired": {"graph"},
    "run codegraph affected on parse_quantity": set(),
    "check the usability of this flow": {"design"},
    "does it meet WCAG 2.2": {"spec", "design"},
    "üretim hattı yavaşladı": set(),
    "temel sorun nedir": set(),
    "the reproduction steps are unclear": set(),
    # the widened craft words read as surface nouns on their own, so each of
    # these ordinary non-UI asks armed the spec paragraph - the words are now
    # qualified by a UI object (the UI asks above still arm it)
    "focus the terminal window": set(),
    "align the two arrays": set(),
    # accepted over-arm, recorded rather than narrowed away: "misaligned" is
    # ordinary management English too, and the UI sense ("the flex row is
    # misaligned") is worth the paragraph on a false arm
    "misaligned incentives across the org": {"spec"},
    "what colors does matplotlib use": set(),
    "add a font to the PDF": set(),
    "the card model in the game": set(),
    "refactor the parser module": {"consult"},
    "align the teams on the roadmap": {"product"},
    # the six siblings of those words, read as ordinary English: each armed the
    # paragraph on a non-UI ask before the narrowing's second pass
    "our margins are down this quarter": set(),
    "the badges in the README": set(),
    "scaffold the skeleton of the parser": set(),
    "the theme of the meeting": set(),
    "cluttered imports in the module": set(),
    "migrate the data center to eu-west": {"consult"},
    "center the roadmap on retention": {"product"},
    # false-positive traps: expected non-empty, recorded so a pattern change cannot silently fix or worsen one
    "spacing in the log output": {"spec"},
    "disable animations in the CLI": {"spec"},
    "survey the codebase": {"research"},
    # kept armed on purpose: a sidebar is a rendered surface, so the ask is a UI
    # ask and pays the paragraph - it is not one of the words narrowed above
    "the sidebar of the docs site": {"spec"},
    # the context-03 probes (decision 006): generic stems qualified, not dropped,
    # so each code-sense ask arms nothing it does not belong to while the
    # positive rows above (which feature, bu sayfa, bu tablo, ekranı incele,
    # adım akışını sadeleştir) still arm
    "add a feature flag to the parser": set(),
    "segment fault in the C extension": set(),
    "tier list of the slow tests": set(),
    "ekrana bir log satırı yaz": set(),
    "tabloya yeni bir sütun ekle (sql)": set(),
    "write a migration for the users table": {"consult"},
    "bu fonksiyonu sadeleştir": set(),
    "add pagination to the API": set(),
    "measure how long the hook takes": set(),
    "pdf'e sayfa numarası ekle": set(),
    # fanout: two or more independent items arm the parallel-delegation rule
    # without the user having to say "use subagents" - a numbered or bulleted
    # list of work, or the explicit parallel/subagent ask
    "1. fix the parser\n2. update the release notes": {"fanout"},
    "- add a --json flag\n- write the docstring for main": {"fanout"},
    "do everything with subagents and in parallel": {"fanout"},
    "her şeyi alt ajanlarla paralel yap": {"fanout"},
    "one worktree per slice": {"fanout"},
    # the owner's own list shapes: `1 - `, `1- `, `1:`, `a)`, `+`, and an inline
    # `1. ... 2. ...`; a Turkish suffix on the English loanword; three files
    # named as one list; an explicit first/second sequence
    "1 - jev çağrılarını düzelt\n2 - review katmanı çok uzun sürüyor": {"fanout"},
    "1- fix the parser\n2- update the release notes": {"fanout"},
    "1: fix the parser\n2: update the release notes": {"fanout"},
    "a) fix the parser\nb) update the release notes": {"fanout"},
    "+ fix the parser\n+ update the release notes": {"fanout"},
    "do these: 1. fix the parser 2. update the release notes": {"fanout"},
    "tüm işlemleri subagentlerle tamamla": {"fanout"},
    "update hooks/a.py, bin/tezgah-task and docs/c.md": {"fanout"},
    "First, fix the parser. Second, update the docs.": {"fanout"},
    "fix the parser, update the release notes, and add a test for the CLI":
        {"fanout"},
    "parser'ı düzelt, dokümanı güncelle, testi ekle": {"fanout"},
    # one item, or a version number, is not a fan-out; parallelizing code is
    # code work, not delegation
    "1. fix the parser": set(),
    "parallelize the loop in compute()": set(),
    "version 2.1 is out": set(),
    # a timestamp, a numeric range and one file are not a list of work, and
    # neither is a traceback that names files one per line
    "12:30 the build broke\n13:05 it broke again": set(),
    "pages 1-2 of the report": set(),
    "fix hooks/a.py": set(),
    'File "a.py", line 3\nFile "b.py", line 9\nFile "c.py", line 1': set(),
    "fix the parser and add a test": set(),
    # a data ask said by its output arms the product rule (the user's own
    # sentence armed nothing before plan 072); a metric or dashboard in its
    # code sense - an endpoint, a counter, a config file - stays code
    "Bu veriye uygun bir metric dashboard tasarla": {"product", "design"},
    "I have this data, design a metric dashboard for it": {"product", "design"},
    "KPI dashboardu tasarlar mısın": {"product", "design"},
    "gösterge paneli tasarla": {"product", "design"},
    "hangi metrikleri takip etmeliyiz": {"product"},
    "choose metrics for the retention review": {"product"},
    "expose a prometheus metrics endpoint": set(),
    "add a metric counter to the parser": set(),
    "fix the grafana dashboard json provisioning": set(),
    "bump the metrics library": set(),
    "update the dashboard config file": set(),
    "pick a north star metric for onboarding": {"product"},
    "metric tasarla": {"product"},
    "bu veri için bir pano tasarla": {"product", "design"},
    "hangi göstergeleri izlemeliyiz": {"product"},
    "what metrics should we track": {"product"},
    "success metrics for the launch": {"product"},
    "visualize this data for the team": {"product"},
    "dashboard.json schema validation fails": set(),
    "refactor Dashboard.tsx to use hooks": set(),
    "the dashboard test is failing": set(),
    "which metrics endpoint is failing": set(),
    "which metric does prometheus scrape": set(),
    "choose a metrics library for go": set(),
    "design the metrics exporter interface": set(),
    "defined metrics are not exported": set(),
    "the kpi_service test fails": set(),
    "add a kpi column to the sql query": set(),
    "build the dashboard bundle with vite": set(),
    # round-2 review probes: code senses outside the first denylist, Turkish
    # code senses (clipboard `pano`, a progress `gösterge`), and data asks with
    # the commonest verbs
    "dashboard.py raises KeyError": set(),
    "define a metric struct in metrics.go": set(),
    "designer mode toggles metrics overlay": set(),
    "create dashboard.json for grafana": set(),
    "fix the grafana metrics dashboard json provisioning": set(),
    "create the dashboard config file": set(),
    "choose a metrics backend for go": set(),
    "build a dashboard bundle with webpack": set(),
    "design the metrics registry": set(),
    "design the metrics pipeline in kafka": set(),
    "track metrics with opentelemetry": set(),
    "track metrics in the cache layer with statsd": set(),
    "define metrics for the http handler in middleware.go": set(),
    "the success metric counter is not incremented": set(),
    "success metrics test is flaky in CI": set(),
    "prometheus metrics should use snake_case names": set(),
    "what metrics do we expose on /metrics": set(),
    "which metrics should be exported by the go server": set(),
    "kpis to use in the test fixture are hardcoded": set(),
    "select value from metrics where host = 1": set(),
    "SELECT name FROM kpis WHERE id = 3": set(),
    "select the metrics column in pandas": set(),
    "define a kpis table in the schema": set(),
    "panoya kopyalama fonksiyonu oluştur": set(),
    "pano içeriğini okuyan modülü hazırla": set(),
    "ilerleme göstergesini izleyen thread çöküyor": set(),
    "metrik dosyasını git takip etmiyor": set(),
    "metrik seçicisi bozuk": set(),
    "dashboard paketini oluştururken webpack hata veriyor": set(),
    "visualize data structures in the debugger": set(),
    "visualize the data flow in the parser": set(),
    "veri yapısını görselleştiren fonksiyon yaz": set(),
    "the dashboard page crashes on load": set(),
    "dashboard yüklenirken 500 hatası veriyor": set(),
    "which charts library supports svg export": set(),
    "kpi hesaplayan servisi refactor et": set(),
    "add caching to the dashboard query": set(),
    "design the metrics database index": set(),
    "grafik çizen kodu hızlandır": set(),
    "metric seç": {"product"},
    "build a dashboard for our sales data": {"product"},
    "metrikleri belirle": {"product"},
    "make a dashboard for sales data": {"product"},
    "satış verisi için bir dashboard yap": {"product"},
    "I need a dashboard showing revenue": {"product"},
    "what should the admin dashboard show": {"product"},
    "which charts should this dashboard show": {"product"},
    "suggest a chart for this data": {"product"},
    "bu veri için hangi grafik uygun": {"product"},
    "dashboard'da hangi grafikleri göstermeliyiz": {"product"},
    "data visualization for our sales numbers": {"product"},
    "help me pick kpis for the support team": {"product"},
    "our churn data needs a dashboard for the exec team": {"product"},
    "what should we put on the onboarding dashboard": {"product"},
    "haftalık satış raporu için dashboard tasarla": {"product", "design"},
    # design (plan 126): a UI ask - build, restyle, critique or audit a screen -
    # reads the design skills; the S2 set's Turkish asks armed nothing or only
    # spec. A dashboard said as a thing to design is a UI ask beside the data
    # ask above; a metric, an API or a schema to design is not.
    "bu ekrani iyilestir": {"product", "design"},
    "admin paneldeki form cok karisik, duzelt": {"design"},
    "tasarim tutarsiz, renkleri ve boslugu duzenle": {"spec", "design"},
    "kullanilabilirlik sorunlarini bul": {"design"},
    "design system kur": {"spec", "design"},
    "UX audit yap": {"spec", "design"},
    "improve this screen": {"design"},
    "the form in the admin panel is confusing, fix it": {"product", "design"},
    "spacing and colors are inconsistent across pages": {"spec", "design"},
    "open the app and click through the screens, list problems": {"design"},
    # a site's or an app's design is a UI ask too (round 2 of plan 126's
    # review): the three armed only spec once the bare `tasarım` was narrowed
    "sitenin tasarımını yenile": {"spec", "design"},
    "mobil uygulamanın tasarımını yenile": {"spec", "design"},
    "uygulamanın tasarımı kötü": {"spec", "design"},
    "web sitesinin tasarımı eski": {"spec", "design"},
    "API tasarla": set(),
    "inconsistent results from the parser": set(),
    # the generic craft words name a UI only beside a UI object (round 1 of
    # plan 126's review): a schema, a thread, a struct, an endpoint, a parser
    # or a test keeps the spec rule it had and arms no design rule
    "redesign the database schema": {"spec"},
    "REST API tasarımı yap": {"spec"},
    "veritabanı şeması tasarımı": {"consult", "spec"},
    "the ui thread blocks on io": {"spec"},
    "fix the memory layout of this struct": {"spec"},
    "bu endpoint erişilebilir mi": {"spec"},
    "the server is not accessible from outside": {"spec"},
    "is this button accessible": {"spec", "design"},
    "add a components field to the JSON schema": {"spec"},
    "write unit tests for the parser components": {"spec"},
    "test bileşenlerini ayır": {"spec"},
    # ... and the product stems: an identifier, a test order, building a
    # feature and filling a form in are code work
    "urun_id kolonunu ekle": set(),
    "ürün_id ekle": set(),
    "öncelik sırasına göre testleri çalıştır": set(),
    "bu özelliği implement et": set(),
    "formu doldur": set(),
    # product (plan 126): the PM asks, ASCII-typed Turkish and the mutated stem
    "PM gözüyle değerlendir bu uygulamayı": {"product"},
    "PM gozuyle degerlendir bu uygulamayi": {"product"},
    "evaluate this like a PM": {"product"},
    "urun analizi yap": {"product"},
    "hangi ozellik once yapilmali": {"product"},
    "randevu özelliğini baştan sona denetle": {"product"},
    "bu PR'ı değerlendir": set(),
}


class HintCoverage(unittest.TestCase):
    """Every reviewed request arms exactly the rules it was reviewed to arm.

    The sets are exact on purpose: an added key is as much a finding as a lost
    one - the paragraph it injects is paid on that turn, so a rule arming on a
    request that does not belong to it costs the reader context it has to read
    past."""

    def test_every_request_arms_the_rules_it_is_reviewed_to_arm(self):
        for prompt, want in CORPUS.items():
            with self.subTest(prompt=prompt):
                self.assertEqual(tc.classify_prompt(prompt), want, prompt)

    def test_the_corpus_is_not_thin(self):
        # a corpus that quietly shrank would keep passing; 100 is far under the
        # reviewed 137 and far over anything a partial revert would leave
        self.assertGreaterEqual(len(CORPUS), 100)
        for key in ("spec", "consult", "research", "product", "design", "graph",
                    "fanout"):
            self.assertTrue(any(key in want for want in CORPUS.values()), key)

    def test_a_long_paste_classifies_in_bounded_time(self):
        # the prompt hook runs every pattern over the whole prompt: an
        # unanchored file-list pattern took about a minute on 100 KB of word
        # characters, so each adversarial shape gets a wall-clock ceiling
        import time
        for text in ("a" * 100_000, "a/b." * 25_000, "1 - x\n" * 16_000,
                     "fix a, " * 14_000,
                     # a data ask runs the per-clause code-sense scan too
                     "select " * 15_000 + "design a sales dashboard"):
            started = time.monotonic()
            tc.classify_prompt(text)
            self.assertLess(time.monotonic() - started, 3.0, text[:20])
