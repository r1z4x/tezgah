"""hooks/tezgah_context.py: context_for scope and health_lines format."""
import json
import os
import re
import subprocess
import sys
import unittest

import support
from support import TempHome, run_json


class ContextFor(TempHome):
    def call(self, payload, env=None):
        return run_json([support.PROBE_CONTEXT], payload, env=env or self.env())

    def test_outside_roots_returns_none(self):
        out, proc = self.call({"fn": "context_for", "event": "session_start",
                               "cwd": self.home})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNone(out)

    def test_inside_roots_returns_context(self):
        repo = self.make_repo()
        out, proc = self.call({"fn": "context_for", "event": "session_start",
                               "cwd": repo})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsInstance(out, str)
        self.assertIn("Ponytail", out)
        self.assertIn("On-demand rules", out)
        # the conditional rules are armed per prompt, not paid every session
        self.assertNotIn("**Spec before building.**", out)

    def test_user_prompt_reminder_and_kill_switch(self):
        repo = self.make_repo()
        out, _ = self.call({"fn": "context_for", "event": "user_prompt", "cwd": repo})
        self.assertIn("harness-reminder", out)
        self.touch(os.path.join(self.home, ".config", "tezgah", "reminder-off"))
        out2, _ = self.call({"fn": "context_for", "event": "user_prompt", "cwd": repo})
        self.assertIsNone(out2)


class HealthLines(TempHome):
    def armed_key(self):
        self.touch(os.path.join(self.home, ".config", "openrouter", "key"))

    def test_outside_roots_still_shows_checklist(self):
        # Global indicator: the checklist prints off-root too, so the opencode
        # TUI does not go silent when the session cwd is outside ~/Projects.
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "health_lines", "cwd": self.home},
                             env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out, "pony\u2713 exec\u2713  \u00b7  "
                              "consult\u2717 research\u2717 cbm\u25cb orch\u25cb")

    def test_armed_but_unused_checklist(self):
        repo = self.make_repo()
        self.armed_key()
        out, _ = run_json([support.PROBE_CONTEXT],
                          {"fn": "health_lines", "cwd": repo, "session_id": "s"},
                          env=self.env())
        self.assertEqual(out, "pony\u2713 exec\u2713  \u00b7  "
                              "consult\u25cb research\u2717 cbm\u25cb orch\u25cb  \u00b7  idx\u2013")

    def test_used_kind_flips_a_mark(self):
        repo = self.make_repo()
        self.armed_key()
        _, proc = run_json([support.PROBE_CONTEXT],
                           {"fn": "record", "session_id": "s", "kind": "cbm"},
                           env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out, _ = run_json([support.PROBE_CONTEXT],
                          {"fn": "health_lines", "cwd": repo, "session_id": "s"},
                          env=self.env())
        self.assertIn("cbm\u2713", out)

    def test_repo_no_cbm_mark(self):
        repo = self.make_repo()
        self.armed_key()
        self.touch(os.path.join(repo, ".no-cbm"))
        out, _ = run_json([support.PROBE_CONTEXT],
                          {"fn": "health_lines", "cwd": repo, "session_id": "s"},
                          env=self.env())
        self.assertIn("cbm\u2717", out)

    def test_open_plans_segment(self):
        repo = self.make_repo()
        self.armed_key()
        self.touch(os.path.join(repo, "plans", "open", "001-a.md"))
        self.touch(os.path.join(repo, "plans", "open", "002-b.md"))
        with open(os.path.join(repo, "plans", "open", "001-a.md"), "w") as fh:
            fh.write("status: blocked\n")
        out, _ = run_json([support.PROBE_CONTEXT],
                          {"fn": "health_lines", "cwd": repo, "session_id": "s"},
                          env=self.env())
        self.assertIn("plans 2 (1 blk)", out)


class IndexMark(TempHome):
    """The `idx` segment: graph readiness of the enclosing repo."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        # a real executable so cbm_bin() is truthy without a real index daemon
        self.envv = self.env(extra={"TEZGAH_CBM_BIN": sys.executable})
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        self.touch(os.path.join(self.repo, "f"))
        subprocess.run(["git", "-C", self.repo, "add", "."], check=True)
        subprocess.run(["git", "-C", self.repo, "-c", "user.email=a@b",
                        "-c", "user.name=t", "commit", "-qm", "x"], check=True)

    def head(self):
        return subprocess.run(["git", "-C", self.repo, "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()

    def index(self, stamp):
        slug = support.slug(os.path.realpath(self.repo))
        db_dir = os.path.join(self.home, ".cache", "codebase-memory-mcp")
        os.makedirs(db_dir, exist_ok=True)
        open(os.path.join(db_dir, slug + ".db"), "w").close()
        if stamp is not None:
            self.touch(os.path.join(self.home, ".cache", "tezgah", slug))
            with open(os.path.join(self.home, ".cache", "tezgah", slug), "w") as fh:
                fh.write(stamp)

    def mark(self):
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "health_lines", "cwd": self.repo},
                             env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out.rsplit("idx", 1)[1]

    def test_not_indexed(self):
        self.assertEqual(self.mark(), "\u2717")

    def test_fresh_index(self):
        self.index(self.head())
        self.assertEqual(self.mark(), "\u2713")

    def test_stale_index(self):
        self.index("deadbeef" * 5)
        self.assertEqual(self.mark(), "\u21bb")


class KillSwitchEnforcement(TempHome):
    """A documented kill switch must remove its rule from the injected text,
    not just flip a status mark. The labels are pinned here, so editing one in
    hooks/tezgah_policy.py fails this test instead of silently disabling it."""

    OFF = "**Turkish, BLUF.**"
    PONY = "**Ponytail (minimal code).**"
    FIDELITY = "**Deliver the whole ask; never the shortcut.**"
    SPEC = "**Spec before building.**"
    LESSONS = "**Lessons ledger: stop repeating mistakes.**"
    CBM = "**Code discovery: graph first.**"
    CONSULT = "**Consult before irreversible.**"
    RESEARCH = "**Research: route it to OpenResearch.**"

    def session(self, repo):
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "context_for", "event": "session_start",
                              "cwd": repo}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def switch(self, name):
        self.touch(os.path.join(self.home, ".config", "tezgah", name))

    def prompt(self, repo, text):
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "context_for", "event": "user_prompt",
                              "cwd": repo, "payload": {"prompt": text}},
                             env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def test_default_keeps_the_invariants(self):
        repo = self.make_repo()
        out = self.session(repo)
        for label in (self.OFF, self.PONY, self.FIDELITY, self.LESSONS):
            self.assertIn(label, out)

    def test_fidelity_and_the_sycophancy_ban_are_invariants(self):
        # no kill switch removes these: they are not opt-out rules
        repo = self.make_repo()
        for name in ("exec-mode.off", "ponytail-auto.off", "spec-off",
                     "consult-off", "research-off", "orchestrate-off"):
            self.switch(name)
        out = self.session(repo)
        self.assertIn(self.FIDELITY, out)
        self.assertIn("haklısın", out)
        self.assertNotIn(self.OFF, out)  # exec-mode.off still removed its own rule

    def test_conditional_rules_are_armed_by_task_class(self):
        repo = self.make_repo()
        out = self.session(repo)
        for label in (self.SPEC, self.CBM, self.CONSULT, self.RESEARCH):
            self.assertNotIn(label, out)
        self.assertIn(self.SPEC,
                      self.prompt(repo, "Bu ekranı daha kullanıcı dostu yap"))
        self.assertIn(self.CONSULT,
                      self.prompt(repo, "Which approach for the schema change?"))
        self.assertIn(self.RESEARCH,
                      self.prompt(repo, "Run a literature review and form a hypothesis"))
        self.assertIn(self.CBM, self.prompt(repo, "who calls calc_total?"))

    def test_a_plain_prompt_arms_no_conditional_rule(self):
        out = self.prompt(self.make_repo(), "add a docstring to parse_quantity")
        self.assertIn("harness-reminder", out)
        for label in (self.SPEC, self.CBM, self.CONSULT, self.RESEARCH):
            self.assertNotIn(label, out)

    def test_exec_mode_off_drops_the_reporting_rule(self):
        repo = self.make_repo()
        self.switch("exec-mode.off")
        out = self.session(repo)
        self.assertNotIn(self.OFF, out)
        self.assertIn("exec-mode.off", out)

    def test_ponytail_auto_off_drops_the_ponytail_rule(self):
        repo = self.make_repo()
        self.switch("ponytail-auto.off")
        self.assertNotIn(self.PONY, self.session(repo))

    def test_repo_no_ponytail_drops_the_ponytail_rule(self):
        repo = self.make_repo()
        self.touch(os.path.join(repo, ".no-ponytail"))
        self.assertNotIn(self.PONY, self.session(repo))

    def test_spec_off_drops_the_spec_rule(self):
        repo = self.make_repo()
        self.switch("spec-off")
        out = self.prompt(repo, "Bu ekranı daha kullanıcı dostu yap")
        self.assertNotIn(self.SPEC, out)
        self.assertIn("spec-off", out)

    def test_repo_no_lessons_drops_the_lessons_rule(self):
        repo = self.make_repo()
        self.touch(os.path.join(repo, ".no-lessons"))
        self.assertNotIn(self.LESSONS, self.session(repo))

    def test_consult_off_drops_the_consult_rule(self):
        repo = self.make_repo()
        self.switch("consult-off")
        self.assertNotIn(
            self.CONSULT, self.prompt(repo, "Which approach for the migration?"))

    def test_research_off_drops_the_research_rule(self):
        repo = self.make_repo()
        self.switch("research-off")
        self.assertNotIn(
            self.RESEARCH, self.prompt(repo, "literature review and hypothesis"))

    def test_missing_orx_is_surfaced_in_the_context(self):
        repo = self.make_repo()
        out = self.session(repo)
        self.assertIn("orx (OpenResearch) is not installed", out)

    def test_orx_installed_suppresses_the_missing_note(self):
        repo = self.make_repo()
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "context_for", "event": "session_start",
                              "cwd": repo},
                             env=self.env(extra={"TEZGAH_ORX_BIN": sys.executable}))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("orx (OpenResearch) is not installed", out)

    def test_orchestrate_off_says_do_not_delegate(self):
        repo = self.make_repo()
        self.switch("orchestrate-off")
        self.assertIn("Orchestration is off", self.session(repo))

    def test_repo_no_cbm_drops_the_graph_rule(self):
        repo = self.make_repo()
        self.touch(os.path.join(repo, ".no-cbm"))
        out = self.session(repo)
        self.assertNotIn(self.CBM, out)
        self.assertIn("disabled for this repo", out)

    def test_user_prompt_names_the_disabled_rule(self):
        repo = self.make_repo()
        self.switch("exec-mode.off")
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "context_for", "event": "user_prompt",
                              "cwd": repo}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("exec-mode.off", out)


class LessonsLedger(TempHome):
    """`.tezgah/lessons.md` is injected (recent lines only) at session start and
    can be opted out per repo with `.no-lessons`."""

    def session(self, repo):
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "context_for", "event": "session_start",
                              "cwd": repo}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def write_lessons(self, repo, lines):
        path = os.path.join(repo, ".tezgah", "lessons.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write("\n".join(lines) + "\n")

    def test_recent_lessons_are_injected(self):
        repo = self.make_repo()
        self.write_lessons(repo, ["# header", "",
                                  "- always clamp the padding",
                                  "- never center a long form"])
        out = self.session(repo)
        self.assertIn("- always clamp the padding", out)
        self.assertIn("- never center a long form", out)
        self.assertNotIn("- - always", out)
        self.assertNotIn("# header", out)

    def test_only_the_last_five_are_injected(self):
        repo = self.make_repo()
        self.write_lessons(repo, ["lesson %d" % i for i in range(8)])
        out = self.session(repo)
        self.assertIn("lesson 7", out)
        self.assertIn("lesson 3", out)
        self.assertNotIn("lesson 2", out)
        self.assertIn("(+3 older", out)

    def test_no_lessons_mark_suppresses_the_block(self):
        repo = self.make_repo()
        self.write_lessons(repo, ["a lesson that must not leak"])
        self.touch(os.path.join(repo, ".no-lessons"))
        self.assertNotIn("a lesson that must not leak", self.session(repo))


class HealthSegments(TempHome):
    """health_segments() is the structured source the colored renderers use."""

    def test_segments_carry_state_glyph_and_text(self):
        self.touch(os.path.join(self.home, ".config", "openrouter", "key"))
        repo = self.make_repo()
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "health_segments", "cwd": repo,
                              "session_id": "s"}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        states = {s["key"]: s["state"] for s in out}
        self.assertEqual(states["pony"], "on")        # always-on
        self.assertEqual(states["consult"], "ready")  # armed, unused
        self.assertEqual(states["cbm"], "ready")
        self.assertEqual(states["orch"], "ready")
        self.assertEqual(states["idx"], "info")       # no cbm_bin in tests
        self.assertEqual([s for s in out if s["key"] == "pony"][0]["glyph"], "\u2713")


class StatusCli(TempHome):
    """bin/tezgah-status must light up the used marks from the session id."""

    def armed(self):
        self.touch(os.path.join(self.home, ".config", "openrouter", "key"))

    def record(self, sid, kinds):
        d = os.path.join(self.home, ".cache", "tezgah", "sessions")
        os.makedirs(d, exist_ok=True)
        slug = "-".join(re.findall(r"[A-Za-z0-9]+", sid))
        with open(os.path.join(d, slug + ".jsonl"), "w") as fh:
            for kind in kinds:
                fh.write(json.dumps({"kind": kind}) + "\n")

    def status(self, *args, env=None):
        cli = os.path.join(support.REPO, "bin", "tezgah-status")
        return subprocess.run([sys.executable, cli] + list(args),
                              capture_output=True, text=True, env=env or self.env())

    def test_session_arg_lights_up_the_used_marks(self):
        self.armed()
        repo = self.make_repo()
        self.record("ses_test_1", ["cbm", "consult"])
        env = self.env()
        env.pop("TEZGAH_SESSION", None)
        out = self.status(repo, "ses_test_1", env=env).stdout
        self.assertIn("cbm\u2713", out)
        self.assertIn("consult\u2713", out)

    def test_without_a_session_id_marks_stay_unused(self):
        self.armed()
        repo = self.make_repo()
        self.record("ses_test_1", ["cbm", "consult"])
        env = self.env()
        env.pop("TEZGAH_SESSION", None)
        out = self.status(repo, env=env).stdout
        self.assertIn("cbm\u25cb", out)

    def test_unknown_option_is_rejected(self):
        proc = self.status("--bogus")
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("unknown option", proc.stderr)

    def test_env_session_id_is_used_when_no_arg(self):
        self.armed()
        repo = self.make_repo()
        self.record("ses_test_1", ["cbm"])
        env = self.env()
        env["TEZGAH_SESSION"] = "ses_test_1"
        self.assertIn("cbm\u2713", self.status(repo, env=env).stdout)

    def test_json_flag_emits_segments(self):
        self.armed()
        repo = self.make_repo()
        segs = json.loads(self.status(repo, "--json").stdout)
        keys = {s["key"] for s in segs}
        self.assertIn("cbm", keys)
        self.assertIn("idx", keys)
        self.assertTrue(all("state" in s and "glyph" in s for s in segs))

    def test_legend_explains_the_marks(self):
        out = self.status("--legend").stdout
        self.assertIn("yellow", out)
        self.assertIn("on demand", out)

    def test_color_and_no_color(self):
        repo = self.make_repo()
        self.assertIn("\033[", self.status(repo, "--color").stdout)
        self.assertNotIn("\033[", self.status(repo, "--no-color").stdout)


class ArmingConformance(TempHome):
    """The same prompt must arm the same advisory rules on every host, and the
    safety rule must never depend on the classifier at all."""

    LABELS = {"spec": "**Spec before building.**",
              "consult": "**Consult before irreversible.**",
              "research": "**Research: route it to OpenResearch.**",
              "cbm": "**Code discovery: graph first.**"}
    PROMPTS = {
        "Bu ekranı daha kullanıcı dostu yap": {"spec"},
        "Which approach for the schema change?": {"consult"},
        "Run a literature review and form a hypothesis": {"research"},
        "who calls calc_total?": {"cbm"},
        "add a docstring to parse_quantity": set(),
    }

    def armed(self, text):
        return {k for k, label in self.LABELS.items() if label in text}

    def test_all_hosts_arm_the_same_rules(self):
        repo = self.make_repo()
        env = self.env()
        for prompt, expected in self.PROMPTS.items():
            payload = {"hook_event_name": "UserPromptSubmit", "cwd": repo,
                       "prompt": prompt}
            got = {}
            out, _ = run_json([support.AUTO_INIT], payload, env=env)
            got["claude"] = self.armed(out["hookSpecificOutput"]["additionalContext"])
            out, _ = run_json([support.CODEX_HOOK], payload, env=env)
            got["codex"] = self.armed(out["hookSpecificOutput"]["additionalContext"])
            out, _ = run_json([support.CURSOR_HOOK],
                              {"hook_event_name": "beforeSubmitPrompt",
                               "cwd": repo, "prompt": prompt}, env=env)
            got["cursor"] = self.armed(out["additional_context"])
            for host, keys in got.items():
                self.assertEqual(keys, expected,
                                 "%s / %r -> %s" % (host, prompt, keys))

    def test_every_advisory_rule_has_an_always_on_pointer(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sys.path.insert(0, os.path.join(root, "hooks"))
        import tezgah_context as tc  # noqa: E402
        core = tc.always_on_core()
        for needle in ("Spec-first", "second opinion", "OpenResearch",
                       "code graph"):
            self.assertIn(needle, core)

    def test_irreversible_actions_stay_on_without_the_classifier(self):
        repo = self.make_repo()
        out, _ = run_json([support.PROBE_CONTEXT],
                          {"fn": "context_for", "event": "session_start",
                           "cwd": repo}, env=self.env())
        self.assertIn("Irreversible or outward-facing actions", out)
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sys.path.insert(0, os.path.join(root, "hooks"))
        import tezgah_context as tc  # noqa: E402
        self.assertIn("Irreversible or outward-facing actions",
                      tc.always_on_core())


class OutputStyleMirrorsCore(unittest.TestCase):
    """output-styles/tezgah.md is the hookless duplicate of the always-on core."""

    CONDITIONAL = ("**Spec before building.**", "**Consult before irreversible.**",
                   "**Research: route it to OpenResearch.**",
                   "**Code discovery: graph first.**")

    def test_body_is_the_always_on_core(self):
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sys.path.insert(0, os.path.join(repo, "hooks"))
        import tezgah_context as tc  # noqa: E402
        with open(os.path.join(repo, "output-styles", "tezgah.md")) as fh:
            body = fh.read().split("---", 2)[2]
        self.assertIn(tc.always_on_core().strip(), body)
        for label in self.CONDITIONAL:
            self.assertNotIn(label, body)


if __name__ == "__main__":
    unittest.main()
