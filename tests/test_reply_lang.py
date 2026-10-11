"""`language` (config.json; an older `reply_lang` still reads) names the reply
language; the value is the switch.

Written from plan 047's Phase C acceptance list (ADR 001, REPORT.md R03 part 5):
the contract's first rule asked for Turkish replies and the Stop rule refused an
English one, and the only escapes (`exec-mode.off`, `verify-off`) dropped
unrelated discipline with it. `tr` (what a config with neither key reads) keeps
that behaviour; `en` asks for English and `any` for the user's language, and
under both the Stop rule judges no language: an English reply quotes the
user's Turkish, so a Turkish detector cannot hold a reply to English.
`--install --language` (or `--reply-lang`) stores it, and the rendered contract
says it.

Plan 086 S5 (V1+V4): a first install with no flag takes the environment's
locale (gettext order, `en` when it names no pack), an older config is pinned
to `tr` and an existing `reply_lang` is never rewritten; and the contract's own
tokens come from the configured language's pack, so `en` stops telling the
user to write "Engeller" and "doğrulanmadı", and the Stop refusals drop their
Turkish leads.

Guards hooks/tezgah_integrity.py (the Stop language check, the refusal words),
hooks/tezgah_policy.py and hooks/tezgah_context.py (the rendered rule),
hooks/tezgah_paths.py (`language`, `env_language`) and bin/tezgah-setup
(`--language`, the environment default, the config refusal).

The Stop rule runs as the real hook in a throwaway HOME; installs run with no
host CLI and write only under that HOME.
"""
import json
import os
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import support  # noqa: E402
from support import TempHome  # noqa: E402

SETUP = os.path.join(support.REPO, "bin", "tezgah-setup")

# 50 prose words of English, no list, no lead, no claim.
ENGLISH = ("The installer now reads the reply language from the config file "
           "and renders the first rule of the contract with it, so a session "
           "that asked for English gets English. The stop rule follows the same "
           "value, which means a reply in the configured language passes and "
           "a reply in the other one is sent back once.")
TURKISH = ("Kurulum artık yanıt dilini yapılandırma dosyasından okuyor ve "
           "sözleşmenin ilk kuralını bu değerle yazıyor; böylece İngilizce "
           "isteyen bir oturum İngilizce alıyor. Durdurma kuralı da aynı değeri "
           "izliyor, yani yapılandırılan dilde bir yanıt geçiyor ve öteki dilde "
           "bir yanıt bir kez geri gönderiliyor, bu yüzden kullanıcı için "
           "davranış her zaman açık ve tutarlı kalıyor.")
# An English reply that carries the hedge word the contract asks for (share 0.062
# on the old reversed check) and one that quotes the user's Turkish (0.194).
HEDGED = ("The parser change is in and the unit tests for the tokenizer pass, "
          "but the end to end run against the staging database was not done, "
          "so that part is doğrulanmadı and I have left it marked as such in "
          "the summary below for you to check before the release goes out.")
QUOTED = ("You wrote \"bu dosyayı silme, içinde kullanıcının ayarları var\", so "
          "I left the settings file alone and changed only the loader that reads "
          "it, which now skips a key it does not know instead of failing.")


class StopLanguage(TempHome):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")

    def stop(self, text, lang=None):
        if lang:
            self.config({"roots": [self.roots], "reply_lang": lang})
        payload = {"hook_event_name": "Stop", "cwd": self.repo,
                   "session_id": "s-lang", "last_assistant_message": text}
        out, proc = support.run_json([support.STOP_HOOK], payload, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def test_the_default_still_refuses_an_english_reply(self):
        self.assertGreaterEqual(len(ENGLISH.split()), 50)
        out = self.stop(ENGLISH)
        self.assertEqual((out or {}).get("decision"), "block", out)
        self.assertIn("not in Turkish", out["reason"])

    def test_tr_refuses_an_english_reply(self):
        out = self.stop(ENGLISH, "tr")
        self.assertEqual((out or {}).get("decision"), "block", out)

    def test_en_lets_an_english_reply_through(self):
        self.assertIsNone(self.stop(ENGLISH, "en"))

    def test_en_judges_no_language(self):
        # the reply in the asked-for language, and the two English replies a
        # Turkish detector misreads, all pass; so does Turkish itself
        for text in (ENGLISH, HEDGED, QUOTED, TURKISH):
            self.assertIsNone(self.stop(text, "en"), text)

    def test_any_judges_no_language(self):
        self.assertIsNone(self.stop(ENGLISH, "any"))
        self.assertIsNone(self.stop(TURKISH, "any"))

    def test_an_unknown_value_reads_as_tr(self):
        out = self.stop(ENGLISH, "klingon")
        self.assertEqual((out or {}).get("decision"), "block", out)


class RenderedRule(TempHome):
    def context(self, lang=None):
        cfg = {"roots": [self.roots]}
        if lang:
            cfg["reply_lang"] = lang
        self.config(cfg)
        out, proc = support.run_json(
            [support.PROBE_CONTEXT],
            {"fn": "context_for", "event": "user_prompt",
             "cwd": self.make_repo(), "payload": {"prompt": "fix it"}},
            env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.dumps(out)

    def test_each_value_names_its_language_in_the_reminder(self):
        self.assertIn("reply Turkish, BLUF", self.context())
        self.assertIn("reply English, BLUF", self.context("en"))
        self.assertIn("reply in the user's language, BLUF", self.context("any"))
        for lang in (None, "en", "any"):
            self.assertNotIn("{REPLY_", self.context(lang))

    def test_en_names_the_canonical_tokens_and_no_turkish_one(self):
        """S5 F6: the contract named `doğrulanmadı`, "Engeller" and KARAR/YETKİ/
        GERİ ALINAMAZ/ORTAM whatever the reply language was."""
        sys.path.insert(0, support.HOOKS)
        import tezgah_context as tc
        import tezgah_policy as policy
        for lang in ("en", "any"):
            with mock.patch("tezgah_paths.config", return_value={"language": lang}):
                text = tc.render("\n".join((tc.always_on_core(), policy.EXEC,
                                            policy.PROMPT_REMINDER)))
            for word in ("doğrulanmadı", "Engeller", "KARAR", "YETKİ",
                         "GERİ ALINAMAZ", "ORTAM", "haklısın", "yaptım"):
                self.assertNotIn(word, text, lang)
            for word in ('"unverified"', '"Blockers"', "DECISION", "IRREVERSIBLE"):
                self.assertIn(word, text, lang)
            self.assertNotRegex(text, r"\{[A-Z_]+\}")
        self.assertIn("Engeller", self.context())


class RefusalWords(TempHome):
    """The Stop refusals name the tokens, and open with the lead, of the
    configured language: the owner's tr refusal keeps its Turkish first line,
    en's opens on the English instruction."""

    def said(self, lang):
        sys.path.insert(0, support.HOOKS)
        import tezgah_integrity as ti
        with mock.patch("tezgah_paths.config", return_value={"language": lang}):
            return [ti._said(t) for t in (ti.RESIDUAL_WORK % "x", ti.ADMISSION,
                                          ti.STOPPED_SLICE % ("a", "b", "c", "d"))]

    def test_en_refusals_are_english(self):
        residual, admission, stopped = self.said("en")
        self.assertTrue(residual.startswith("The reply lists work"), residual)
        self.assertTrue(stopped.startswith("Slice a,"), stopped)
        for text in (residual, admission, stopped):
            self.assertNotRegex(text, "[çğıöşüÇĞİÖŞÜ]|\\{")
        self.assertIn('"Blockers"', residual)
        self.assertIn('"unverified"', admission)

    def test_tr_refusals_keep_the_turkish_lead_and_tokens(self):
        residual, admission, stopped = self.said("tr")
        self.assertTrue(residual.startswith("Bu maddeleri şimdi yap veya engel türü "
                                            "ve kanıtla yaz. The reply lists"))
        self.assertTrue(stopped.startswith("Durmuş bir dilim var. Slice a,"))
        self.assertIn("KARAR (a choice", residual)
        self.assertIn('"doğrulanmadı" ends the turn', admission)

    def test_no_refusal_text_in_the_module_names_a_turkish_token_under_en(self):
        """Review F1: two `no ui_ok` refusals still said "doğrulanmadı",
        "Engeller" and ORTAM under `en`. A sweep, not a list: every string
        literal in hooks/tezgah_integrity.py outside a docstring, filled by
        `_said` under `en`, carries no Turkish letter or tr token - so the next
        refusal written with a literal token fails here. The allowlist is the
        three literals that are regex letter classes or the Turkish fold."""
        import ast
        import re
        sys.path.insert(0, support.HOOKS)
        import tezgah_integrity as ti
        with open(os.path.join(support.HOOKS, "tezgah_integrity.py"),
                  encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        docs = {id(n.body[0].value) for n in ast.walk(tree)
                if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef))
                and n.body and isinstance(n.body[0], ast.Expr)
                and isinstance(n.body[0].value, ast.Constant)}
        allowed = {r"\b(?:%s|%s)[A-ZÇĞİIÖŞÜ]*\b", "İ", "ı"}
        token = re.compile(r"[çğıöşüÇĞİÖŞÜ]|\b(?:KARAR|YETK|ORTAM|ALINAMAZ|Engeller)\b")
        with mock.patch("tezgah_paths.config", return_value={"language": "en"}):
            found = [(n.lineno, n.value[:60]) for n in ast.walk(tree)
                     if isinstance(n, ast.Constant) and isinstance(n.value, str)
                     and id(n) not in docs and n.value not in allowed
                     and token.search(ti._said(n.value))]
        self.assertEqual(found, [])

    def test_the_hookless_copy_names_both_spellings(self):
        """Review F2: the static output style serves every language, so it
        names the English token and its tr alias, and tr's banned openers."""
        sys.path.insert(0, support.HOOKS)
        import tezgah_context as tc
        import tezgah_policy as policy
        core = tc.always_on_core()
        for key, words in policy.REPLY_LANG_HOOKLESS.items():
            core = core.replace(key, words)
        for words in ('"unverified"/"doğrulanmadı"', '"Blockers"/"Engeller"',
                      "DECISION\n(tr: KARAR;", "ENV (tr: ORTAM;", '"haklısın"',
                      "\"you're right\""):
            self.assertIn(words, core)
        self.assertNotRegex(core, r"\{[A-Z_]+\}")

    def test_the_default_render_keeps_the_first_rules_line_breaks(self):
        """Installed CLAUDE.md/AGENTS.md hold the rendered core: under `tr` the
        first rule must render to the bytes it had before `reply_lang`, or every
        upgrade rewrites those files for a whitespace change."""
        sys.path.insert(0, support.HOOKS)
        import tezgah_context as tc
        self.assertIn("**Turkish, BLUF.** Every user-facing reply in Turkish, even "
                      "when the user\nwrites English: outcome/decision first, then "
                      "points by impact. Code, commits,\ndocs, subagent prompts",
                      tc.render(tc.always_on_core()))


class InstallFlag(TempHome):
    def setUp(self):
        super().setUp()
        os.makedirs(os.path.join(self.home, ".claude"))
        with open(os.path.join(self.home, ".claude", "settings.json"), "w") as fh:
            fh.write("{}\n")
        self.cfg = os.path.join(self.home, ".config", "tezgah", "config.json")

    def install(self, *extra, lang="C.UTF-8"):
        return subprocess.run(
            [sys.executable, SETUP, "--install", "--hosts", "claude"] + list(extra),
            capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=300,
            env=self.env(extra={"TEZGAH_NO_DEPS": "1", "LANG": lang,
                                "TEZGAH_OMP_BIN": os.path.join(self.home, "no-omp")}))

    def stored(self):
        with open(self.cfg) as fh:
            return json.load(fh)

    def claude_md(self):
        with open(os.path.join(self.home, ".claude", "CLAUDE.md")) as fh:
            return fh.read()

    def test_the_flag_stores_the_value_and_the_contract_says_it(self):
        proc = self.install("--language", "en")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(self.stored()["language"], "en")
        self.assertIn("**English, BLUF.** Every user-facing reply in English",
                      self.claude_md())
        # a later install without the flag keeps the stored answer
        self.assertEqual(self.install(lang="tr_TR.UTF-8").returncode, 0)
        self.assertEqual(self.stored()["language"], "en")
        # the older spelling of the flag still reaches the same key
        self.assertEqual(self.install("--reply-lang", "any").returncode, 0)
        self.assertEqual(self.stored()["language"], "any")

    def test_a_first_install_takes_the_environments_language(self):
        proc = self.install(lang="tr_TR.UTF-8")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(self.stored()["language"], "tr")
        self.assertIn("**Turkish, BLUF.** Every user-facing reply in Turkish",
                      self.claude_md())

    def test_a_first_install_in_a_locale_with_no_pack_is_english(self):
        proc = self.install(lang="de_DE.UTF-8")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(self.stored()["language"], "en")
        self.assertIn("**English, BLUF.**", self.claude_md())

    def test_an_older_config_keeps_turkish_and_reply_lang_is_never_rewritten(self):
        os.makedirs(os.path.dirname(self.cfg), exist_ok=True)
        with open(self.cfg, "w") as fh:
            json.dump({"roots": [self.roots]}, fh)
        self.assertEqual(self.install(lang="en_US.UTF-8").returncode, 0)
        self.assertEqual(self.stored()["language"], "tr")
        with open(self.cfg, "w") as fh:
            json.dump({"roots": [self.roots], "reply_lang": "tr"}, fh)
        self.assertEqual(self.install(lang="en_US.UTF-8").returncode, 0)
        self.assertEqual(self.stored()["reply_lang"], "tr")
        self.assertNotIn("language", self.stored())
        self.assertIn("**Turkish, BLUF.**", self.claude_md())

    def test_a_config_only_jev_wrote_is_still_a_first_install(self):
        """Review F3: `--jev` writes config.json too, so the file's existence
        made the next install read as an upgrade and pinned `tr`."""
        proc = self.install("--jev", "auto", lang="de_DE.UTF-8")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(os.path.exists(self.cfg))
        proc = self.install(lang="de_DE.UTF-8")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(self.stored()["language"], "en")

    def test_an_unknown_value_is_a_usage_error(self):
        proc = self.install("--reply-lang", "de")
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertFalse(os.path.exists(self.cfg))

    def test_a_malformed_tezgah_config_is_refused_not_rewritten(self):
        """tezgah's own config.json is read as {} when it does not parse, so the
        install used to write its defaults over the user's roots and settings."""
        os.makedirs(os.path.dirname(self.cfg), exist_ok=True)
        bad = b'{"roots": ["/mine"], "reply_lang": "en",}\n'
        with open(self.cfg, "wb") as fh:
            fh.write(bad)
        proc = self.install("--reply-lang", "tr")
        out = proc.stdout + proc.stderr
        self.assertNotEqual(proc.returncode, 0, out)
        self.assertIn(self.cfg, out.split("refused to rewrite")[-1], out)
        with open(self.cfg, "rb") as fh:
            self.assertEqual(fh.read(), bad)


class EnvLanguage(unittest.TestCase):
    def test_gettext_order_and_the_english_fallback(self):
        sys.path.insert(0, support.HOOKS)
        import tezgah_paths as tp
        cases = [({"LANG": "tr_TR.UTF-8"}, "tr"),
                 ({"LANGUAGE": "tr:en", "LANG": "en_US.UTF-8"}, "tr"),
                 ({"LANGUAGE": "", "LC_ALL": "en_GB", "LANG": "tr_TR"}, "en"),
                 ({"LC_MESSAGES": "tr_TR@euro", "LANG": "en_US"}, "tr"),
                 ({"LANG": "C.UTF-8"}, "en"), ({"LANG": "de_DE.UTF-8"}, "en"),
                 ({}, "en")]
        for environ, code in cases:
            self.assertEqual(tp.env_language(environ), code, environ)


if __name__ == "__main__":
    unittest.main()
