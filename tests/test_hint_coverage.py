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
    "clean ui please": {"spec"},
    "more intuitive please": {"spec"},
    "the copy feels unprofessional": {"spec"},
    "düzgün çalışsın artık": {"spec"},
    "güzel görünsün": {"spec"},
    "metin biraz daha iyi olsun": {"spec"},
    "kullanıcı dostu olsun": {"spec"},
    "bu sayfanın css'ini tailwind'e taşı": {"product", "spec"},
    "admin componentlerini refactor et": {"spec"},
    "hover ve focus durumları eksik": {"spec"},
    "tasarımı responsive yap": {"spec"},
    "dark mode ekle": {"spec"},
    "bu componentin erişilebilirliğini düzelt": {"spec"},
    "the layout is broken on mobile": {"spec"},
    "add a wireframe for the checkout flow": {"spec"},
    "spacing looks off in the header": {"spec"},
    "make it look better": {"spec"},
    # the qualified craft words, said the way a UI ask says them: every one of
    # these is the positive half of a negative row in the trap block below
    "center the login form": {"spec"},
    "the margins are off in the header": {"spec"},
    "the form's margins are too tight": {"spec"},
    "the page is cluttered": {"spec"},
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
    "check the usability of this flow": set(),
    "does it meet WCAG 2.2": {"spec"},
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
}


class HintCoverage(unittest.TestCase):
    """Every reviewed request arms exactly the rules it was reviewed to arm.

    The sets are exact on purpose: an added key is as much a finding as a lost
    one - the paragraph it injects is paid on that turn, so a rule arming on a
    request that does not belong to it costs the reader context it has to read
    past."""

    def test_every_request_arms_the_rules_it_is_reviewed_to_arm(self):
        for prompt, want in CORPUS.items():
            self.assertEqual(tc.classify_prompt(prompt), want, prompt)

    def test_the_corpus_is_not_thin(self):
        # a corpus that quietly shrank would keep passing; 100 is far under the
        # reviewed 137 and far over anything a partial revert would leave
        self.assertGreaterEqual(len(CORPUS), 100)
        for key in ("spec", "consult", "research", "product", "graph"):
            self.assertTrue(any(key in want for want in CORPUS.values()), key)
