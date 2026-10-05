"""`reply_lang` (config.json) names the reply language; the value is the switch.

Written from plan 047's Phase C acceptance list (ADR 001, REPORT.md R03 part 5):
the contract's first rule asked for Turkish replies and the Stop rule refused an
English one, and the only escapes (`exec-mode.off`, `verify-off`) dropped
unrelated discipline with it. `tr` (the default, and what an install without
the key reads) keeps that behaviour; `en` asks for English and `any` for the
user's language, and under both the Stop rule judges no language: an English
reply carries the contract's own hedge word `doğrulanmadı` or quotes the user's
Turkish, so a Turkish detector cannot hold a reply to English.
`--install --reply-lang` stores it, and the rendered contract says it.

Guards hooks/tezgah_integrity.py (the Stop language check), hooks/tezgah_policy.py
and hooks/tezgah_context.py (the rendered rule), hooks/tezgah_paths.py
(`reply_lang`) and bin/tezgah-setup (`--reply-lang`, the config refusal).

The Stop rule runs as the real hook in a throwaway HOME; installs run with no
host CLI and write only under that HOME.
"""
import json
import os
import subprocess
import sys
import unittest

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

    def install(self, *extra):
        return subprocess.run(
            [sys.executable, SETUP, "--install", "--hosts", "claude"] + list(extra),
            capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=300,
            env=self.env(extra={"TEZGAH_NO_DEPS": "1",
                                "TEZGAH_OMP_BIN": os.path.join(self.home, "no-omp")}))

    def stored(self):
        with open(self.cfg) as fh:
            return json.load(fh)

    def claude_md(self):
        with open(os.path.join(self.home, ".claude", "CLAUDE.md")) as fh:
            return fh.read()

    def test_the_flag_stores_the_value_and_the_contract_says_it(self):
        proc = self.install("--reply-lang", "en")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(self.stored()["reply_lang"], "en")
        self.assertIn("**English, BLUF.** Every user-facing reply in English",
                      self.claude_md())
        # a later install without the flag keeps the stored answer
        self.assertEqual(self.install().returncode, 0)
        self.assertEqual(self.stored()["reply_lang"], "en")

    def test_an_install_without_the_flag_stays_turkish(self):
        proc = self.install()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("reply_lang", self.stored())
        self.assertIn("**Turkish, BLUF.** Every user-facing reply in Turkish",
                      self.claude_md())

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


if __name__ == "__main__":
    unittest.main()
