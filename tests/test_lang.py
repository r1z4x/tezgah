"""hooks/tezgah_lang.py: the Turkish-identifier heuristic.

The letter set, the curated word list and the refusal they produce, read in
process. The gate's half - which commands create an identifier - is pinned in
tests/test_gate.py; this file pins the decision those commands are handed to,
including the tokens the heuristic is KNOWN to be wrong about (`I` in `Fix CI`,
`sil` in `silent`), because a ceiling stated in a docstring and nowhere else
drifts the way any unpinned behaviour does.
"""
import os
import sys
import unittest

import support

sys.path.insert(0, os.path.join(support.REPO, "hooks"))
import tezgah_lang as tl  # noqa: E402


class Detector(unittest.TestCase):
    # ---- the letter set ----------------------------------------------------
    def test_a_turkish_letter_is_a_hit_anywhere(self):
        # a token carrying a character English does not spell is named, whatever
        # the word around it is
        for text, token in (("onarım", "onarım"), ("Şubat", "Şubat"),
                            ("güncelle", "güncelle"), ("ölçüm", "ölçüm"),
                            ("çalışma", "çalışma"),
                            ("plan/004-muhasebe-onarımı", "onarımı")):
            self.assertEqual(tl.offending(text), [token], text)

    def test_the_fold_reads_an_all_caps_turkish_word(self):
        # `ONARIM` folds to `onarim`, which is what the curated list holds, so an
        # all-caps Turkish word is caught through the fold rather than through a
        # letter rule. `I` used to be in the letter set for this case, and that
        # refused `CI`, `ID` and `I1` - the last of which blocked the commit
        # subject recording this rule's own acceptance run. The letter half is
        # now a non-ASCII test, and the case below is the guard on it.
        self.assertEqual(tl.offending("ONARIM"), ["ONARIM"])
        for english in ("Fix CI", "ID", "I1", "ITEM"):
            self.assertEqual(tl.offending(english), [], english)

    # ---- the half that is not Turkish at all -------------------------------
    def test_a_letter_outside_ascii_is_refused_whatever_the_language(self):
        # the contract says identifiers are English, not "not Turkish": every one
        # of these passed before the letter half became a non-ASCII test
        for text in ("plan/004-статус-ремонт", "plan/004-إصلاح-الحالة",
                     "plan/004-状态修复", "plan/004-κατάσταση",
                     "plan/004-kế-hoạch", "plan/004-état-des-lieux",
                     "plan/004-durum-onarım"):
            self.assertTrue(tl.offending(text), text)

    def test_the_ceiling_is_an_ascii_folded_word_from_another_language(self):
        # stated rather than hidden: no list here reads Polish or German, and a
        # language detector on a denial path is the dependency this module is not
        for text in ("plan/004-naprawa-stanu", "plan/004-status-reparatur"):
            self.assertEqual(tl.offending(text), [], text)

    def test_a_version_and_an_ascii_slug_stay_clean(self):
        for text in ("plan/004-status-repair", "fix: status repair",
                     "plan/004-version-4.2.1", "I1 recorded in C40"):
            self.assertEqual(tl.offending(text), [], text)

    # ---- the word list -----------------------------------------------------
    def test_folded_turkish_in_a_slug(self):
        # the identifier a public repository keeps forever, and the form the
        # folding leaves behind
        self.assertEqual(tl.offending("plan/004-admin-durum-onarimi"),
                         ["durum", "onarimi"])
        self.assertEqual(tl.offending("silme-sayfasi"), ["silme", "sayfasi"])
        self.assertEqual(tl.offending("kullanim_kilavuzu"), ["kullanim"])
        self.assertEqual(tl.offending("hazirla.deneme"), ["hazirla", "deneme"])

    def test_a_turkish_commit_subject(self):
        self.assertEqual(tl.offending("durum onarimi ve hata raporu"),
                         ["durum", "onarimi", "hata", "raporu"])

    def test_a_token_is_reported_once(self):
        self.assertEqual(tl.offending("durum, durum"), ["durum"])

    # ---- the English that must pass ---------------------------------------
    def test_english_identifiers_pass(self):
        for text in ("plan/004-status-repair", "fix: status repair",
                     "add a rule for tags", "update the README",
                     "compare two retry budgets", "review the index"):
            self.assertEqual(tl.offending(text), [], text)

    def test_a_word_that_is_both_languages_passes(self):
        # `data` and `test` are English words a Turkish list would love to hold,
        # and holding them would refuse an ordinary commit subject
        for text in ("data", "test", "test data", "policy/test", "status"):
            self.assertEqual(tl.offending(text), [], text)

    def test_a_word_the_stems_merely_start(self):
        # the floor under SHORT: `sil` prefixes `silent`/`silk`, so the short
        # stem is matched whole-token and its suffixed Turkish form is its own
        # entry
        self.assertEqual(tl.offending("silent retry"), [])
        self.assertEqual(tl.offending("kayit-sil"), ["sil"])
        self.assertEqual(tl.offending("silme"), ["silme"])

    # ---- the widened list: the ordinary words a probe found missing -------
    def test_the_ordinary_words_are_caught_in_every_shape(self):
        # a slug, the shape a plan writes
        self.assertEqual(tl.offending("plan/007-kullanici-yetki-guvenlik"),
                         ["kullanici", "yetki", "guvenlik"])
        # a subject, the shape a commit writes
        self.assertEqual(tl.offending("veri donusum ve yapilandirma"),
                         ["veri", "donusum", "yapilandirma"])
        # a branch, the shape plan-add derives
        self.assertEqual(tl.offending("feature/arama-sayfasi"),
                         ["arama", "sayfasi"])
        # and the rest of the probe's list, each on its own
        for word in ("hazirlik", "silindi", "degisiklik", "temizlik", "tasarim",
                     "baglanti", "ayarlar", "testler", "senaryo", "aciklama",
                     "ornek", "cikti", "girdi", "surum", "yayin", "baslatma",
                     "durdurma", "bekleme", "hiz", "boyut"):
            self.assertEqual(tl.offending(word), [word], word)

    def test_a_whole_token_stem_still_catches_its_own_form(self):
        # `arama`, `veri` and `girdi` are read whole-token (see WHOLE): the word
        # on its own and every slug or subject that separates it are caught ...
        for text, token in (("veri", "veri"), ("veri-tabani", "veri"),
                            ("arama-sonuclari", "arama"),
                            ("girdi-dosyasi", "girdi")):
            self.assertIn(token, tl.offending(text), text)
        # ... and the English the prefix would have swallowed is not
        for word in ("verify", "verification", "verifiable", "Aramaic",
                     "girding"):
            self.assertEqual(tl.offending(word), [], word)

    def test_the_stems_do_not_touch_english_words(self):
        # The reverse guard, and the test that keeps the next addition honest:
        # every stem is here because no English word grows out of it, and this
        # is that claim, checked. An addition that trips one of these lines is
        # an addition that refuses English.
        for word in ("verify", "verification", "verifiable", "Aramaic",
                     "girding", "senary", "test", "tests", "service", "fast",
                     "size", "version", "release", "start", "stop", "wait",
                     "speed", "link", "user", "example", "output", "scenario",
                     "description", "permission", "security", "settings",
                     "preparation", "cleanup", "design", "conversion",
                     "configuration", "change", "deleted", "data", "silent",
                     "similar", "install", "restart", "status", "repair",
                     "list", "review", "compare"):
            self.assertEqual(tl.offending(word), [], word)

    def test_empty_and_none_are_not_a_hit(self):
        for text in ("", None, "   ", "./"):
            self.assertEqual(tl.offending(text), [], repr(text))

    # ---- the refusal -------------------------------------------------------
    def test_the_replacement_is_read_through_the_fold(self):
        # the list is written in ASCII, so both spellings of the same word find
        # the same English
        for token in ("onarimi", "onarım", "ONARIM", "Onarım"):
            self.assertEqual(tl.replacement(token), "repair", token)
        self.assertEqual(tl.replacement("silme"), "deletion")

    def test_a_token_off_the_list_gets_no_replacement(self):
        self.assertIsNone(tl.replacement("Şubat"))
        self.assertIsNone(tl.replacement("CI"))
        self.assertIsNone(tl.replacement("data"))

    def test_the_refusal_names_the_identifier_the_token_and_the_english(self):
        reason = tl.refusal("branch name", "plan/004-admin-durum-onarimi")
        self.assertIn("branch name", reason)
        self.assertIn("`durum`", reason)
        self.assertIn("`durum` -> `status`", reason)
        self.assertIn("`onarimi` -> `repair`", reason)

    def test_the_refusal_admits_it_is_a_heuristic_and_names_the_override(self):
        reason = tl.refusal("PR title", "Şubat raporu")
        self.assertIsNotNone(reason)
        self.assertIn("Şubat", reason)
        self.assertIn("heuristic", reason)
        self.assertIn("user", reason)

    def test_a_letter_hit_the_list_does_not_know_offers_no_translation(self):
        reason = tl.refusal("branch name", "Şubat")
        self.assertIn("`Şubat`", reason)
        self.assertNotIn("->", reason)

    def test_english_text_earns_no_refusal(self):
        for what, text in (("commit subject", "fix: status repair"),
                          ("branch name", "plan/004-status-repair"),
                          ("branch name", "")):
            self.assertIsNone(tl.refusal(what, text), text)

    def test_ascii_capital_i_is_not_a_turkish_letter(self):
        # `İ` folds to `I`, and the letter set briefly held the ASCII form with
        # it - which refused the commit subject recording this rule's own
        # acceptance run (`I1`), and would have refused `ID`, `ITEM` and the
        # `Q01`-style row ids other rules write. The set is the characters an
        # English identifier never contains, and `I` is not one of them.
        for text in ("I", "ID", "I1", "ITEM", "ITEM 4", "E1 acceptance run",
                     "C40 recorded", "Q01 source id", "plan/004-status-repair"):
            self.assertEqual(tl.offending(text), [], text)
            self.assertIsNone(tl.refusal("commit subject", text), text)

    def test_the_dotted_and_dotless_i_themselves_still_hit(self):
        for text in ("İstanbul", "ığ", "ıIİ"):
            self.assertTrue(tl.offending(text), text)


if __name__ == "__main__":
    unittest.main()
