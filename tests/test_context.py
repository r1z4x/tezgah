"""hooks/tezgah_context.py: context_for scope and health_lines format."""
import json
import os
import re
import shutil
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

    def test_color_paints_the_whole_mark_by_state(self):
        # the glyph is still there, so color is a second channel and never the
        # only one (WCAG 1.4.1); the separator is dimmed, not colored
        repo = self.make_repo()
        self.armed_key()
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "health_lines", "cwd": repo,
                              "session_id": "s", "color": True},
                             env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("\033[32mpony\u2713\033[0m", out)      # in force
        self.assertIn("\033[33mconsult\u25cb\033[0m", out)   # armed, unused
        self.assertIn("\033[31mresearch\u2717\033[0m", out)  # off
        self.assertIn("\033[2midx\u2013\033[0m", out)        # no state
        self.assertIn("\033[2m  \u00b7  \033[0m", out)

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


class InflectedTurkishArming(unittest.TestCase):
    """Turkish is agglutinative: the hints are stems, so a suffix must still arm
    them. The trailing \\b the English hints need silently dropped the most
    natural Turkish phrasing - including `düzgün çalışsın`, the underspecified
    request the contract itself names."""

    def setUp(self):
        sys.path.insert(0, os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))
        import tezgah_context as tc  # noqa: E402
        self.armed = tc.classify_prompt

    def test_suffixed_stems_arm_their_rule(self):
        cases = {
            "bu ekran düzgün çalışsın": {"spec"},
            "arayüz güzel görünsün": {"spec"},
            "metin biraz daha iyi olsun": {"spec"},
            "kök nedenini bulalım": {"consult"},
            "mimarisini yeniden kuralım": {"consult"},
            "araştırma yap": {"research"},
            "hipotezi test et": {"research"},
            "bu fonksiyonu kim çağırıyor?": {"cbm"},
            "bu modül nasıl bağlanmış?": {"cbm"},
            "bu değişiklikten hangi dosyalar etkilenir": {"cbm"},
        }
        for prompt, want in cases.items():
            self.assertEqual(self.armed(prompt), want, prompt)

    def test_suffix_tolerance_does_not_widen_the_hints(self):
        # a whole-word hint keeps its plain boundary, and the Turkish hints are
        # spelled with their own letters: neither a missing suffix nor a
        # diacritic-free spelling may arm anything
        for prompt in ("add a docstring to parse_quantity",
                       "nasılsın, bugün bir sorun var mı?",
                       "arastirmaci ekibi kurduk",
                       "kullanıcı deneyimi raporu"):
            self.assertEqual(self.armed(prompt), set(), prompt)


class GitSpawnBudget(TempHome):
    """One git spawn per question per process. A session start asks the same two
    questions twice over (context_for, then the status line's idx mark), and that
    second pair of forks was pure waste - two spawns where four ran."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        self.touch(os.path.join(self.repo, "f"))
        subprocess.run(["git", "-C", self.repo, "add", "."], check=True)
        subprocess.run(["git", "-C", self.repo, "-c", "user.email=a@b",
                        "-c", "user.name=t", "commit", "-qm", "x"], check=True)
        head = subprocess.run(["git", "-C", self.repo, "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
        slug = support.slug(os.path.realpath(self.repo))
        # stamp == HEAD: autoindex reports "index current" and forks no worker
        stamp = os.path.join(self.home, ".cache", "tezgah", slug)
        self.touch(stamp)
        with open(stamp, "w") as fh:
            fh.write(head)
        # an index db, so the idx mark really has a reason to compare HEAD
        db_dir = os.path.join(self.home, ".cache", "codebase-memory-mcp")
        os.makedirs(db_dir, exist_ok=True)
        open(os.path.join(db_dir, slug + ".db"), "w").close()

    def test_a_session_start_forks_git_twice(self):
        shim = os.path.join(self.home, "shim")
        os.makedirs(shim, exist_ok=True)
        log = os.path.join(self.home, "git.log")
        script = os.path.join(shim, "git")
        with open(script, "w") as fh:
            fh.write('#!/bin/sh\nprintf "%%s\\n" "$*" >> "$TEZGAH_GIT_LOG"\n'
                     'exec %s "$@"\n' % shutil.which("git"))
        os.chmod(script, 0o755)
        env = self.env(extra={"TEZGAH_CBM_BIN": sys.executable,
                              "TEZGAH_GIT_LOG": log,
                              "PATH": shim + os.pathsep + os.environ["PATH"]})
        body = ("import sys\n"
                "sys.path.insert(0, %r)\n"
                "import tezgah_context as tc\n"
                "tc.context_for('session_start', %r)\n"
                "tc.health_lines(%r)\n"
                "tc.health_lines(%r)\n" % (support.HOOKS, self.repo,
                                           self.repo, self.repo))
        proc = subprocess.run([sys.executable, "-c", body],
                              capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        with open(log) as fh:
            asked = [line.split(" rev-parse ", 1)[1] for line in fh.read().splitlines()
                     if line]
        # one top-level and one HEAD, however often the line is rendered
        self.assertEqual(sorted(asked), ["--show-toplevel", "HEAD"], asked)


class IndexRedraw(unittest.TestCase):
    """A host that redraws its status line per event passes the glyph it already
    resolved, so the cosmetic redraw forks no git for the idx mark."""

    def setUp(self):
        sys.path.insert(0, os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))
        import tezgah_context as tc  # noqa: E402
        self.tc = tc
        self.probes = []
        tc._IDX.clear()
        # The idx mark short-circuits to "-" when no code-graph binary resolves,
        # so pin one: whether this machine happens to have codebase-memory-mcp
        # installed (it is absent in CI) must not decide whether the mark probes.
        prev_cbm = os.environ.get("TEZGAH_CBM_BIN")
        os.environ["TEZGAH_CBM_BIN"] = sys.executable
        self.addCleanup(self._restore_cbm_bin, prev_cbm)
        self.addCleanup(setattr, tc, "git", tc.git)
        self.addCleanup(setattr, tc, "repo_marks", tc.repo_marks)
        tc.git = lambda *a: self.probes.append(a) or "deadbeef" * 5
        tc.repo_marks = lambda cwd: ("/base", set())

    @staticmethod
    def _restore_cbm_bin(prev):
        if prev is None:
            os.environ.pop("TEZGAH_CBM_BIN", None)
        else:
            os.environ["TEZGAH_CBM_BIN"] = prev

    def test_a_resolved_glyph_is_used_and_probes_nothing(self):
        segs = self.tc.health_segments("/base/proj", "s", used_override=[],
                                       idx_override="\u2713")
        idx = [s for s in segs if s["key"] == "idx"][0]
        self.assertEqual(idx["glyph"], "\u2713")
        self.assertEqual(idx["state"], "on")
        self.assertEqual(self.probes, [])

    def test_without_a_glyph_the_mark_still_probes(self):
        import tezgah_gate
        self.addCleanup(setattr, tezgah_gate, "index_slug", tezgah_gate.index_slug)
        tezgah_gate.index_slug = lambda cwd, base: "slug"
        self.tc.health_segments("/base/proj", "s", used_override=[])
        # the probe asks both questions: repo_root's top-level, then HEAD
        self.assertEqual([p[-1] for p in self.probes],
                         ["--show-toplevel", "HEAD"], self.probes)


class UsedToolKind(unittest.TestCase):
    """A mark may only turn green when the tool really ran, so the kind has to
    come from a command position: not from a word carried as an argument, and
    not from the body of a heredoc."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, support.HOOKS)
        import tezgah_context as tc
        cls.tc = tc

    def kind(self, command):
        return self.tc.shell_kind(command)

    def test_a_real_run_is_seen_through_wrappers_and_keywords(self):
        for command, want in (
                ("consult q", "consult"),
                ("cd /tmp && sudo env X=1 consult --online q", "consult"),
                ("timeout 30 consult q", "consult"),
                ("sudo -u root consult q", "consult"),
                ("env -i consult q", "consult"),
                ("bash -c 'consult q'", "consult"),
                ("sh -c 'orx run'", "research"),
                ("if consult q; then echo ok; fi", "consult"),
                ("! orx skill", "research"),
                ("echo hi\nconsult q", "consult")):
            self.assertEqual(self.kind(command), want, command)

    def test_a_mention_is_not_a_use(self):
        for command in ("grep -n consult hooks/",
                        "git log --grep=consult",
                        "echo 'run consult later'",
                        "cat <<'EOF'\nconsult q\nEOF",
                        "python3 - <<EOF\norx skill\nEOF",
                        "echo $((1<<2)); grep orx hooks/"):
            self.assertIsNone(self.kind(command), command)


class KillSwitchEnforcement(TempHome):
    """A documented kill switch must remove its rule from the injected text,
    not just flip a status mark. The labels are pinned here, so editing one in
    hooks/tezgah_policy.py fails this test instead of silently disabling it."""

    OFF = "**Turkish, BLUF.**"
    PONY = "**Ponytail (minimal code).**"
    FIDELITY = "**Deliver the whole ask; never the shortcut.**"
    INTEGRITY = '**Integrity: evidence, or "doğrulanmadı".**'
    LOOP = "**Loop discipline.**"
    SPEC = "**Spec before building.**"
    LESSONS = "**Lessons ledger: stop repeating mistakes.**"
    CBM = "**Code discovery: graph first.**"
    CONSULT = "**Consult before irreversible.**"
    RESEARCH = "**Research: route it to OpenResearch.**"
    ATTRIBUTION = "**No AI attribution, ever, on any host.**"

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
        for label in (self.OFF, self.PONY, self.FIDELITY, self.INTEGRITY,
                      self.LOOP, self.ATTRIBUTION, self.LESSONS):
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


class ChildCall(TempHome):
    """A hook call in a child process.

    Both the paths tezgah_paths derives from HOME and the module constants below
    it (the byte budget) are read at import time, so a test that has to change
    one cannot be an in-process call: it runs the call in a child whose HOME is
    the temp one, the way GitSpawnBudget already does."""

    def child(self, body, extra=None):
        proc = subprocess.run([sys.executable, "-c", body], capture_output=True,
                              text=True, env=self.env(extra=extra))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)


class ContextBudget(ChildCall):
    """C2: context_for returns under a per-event byte budget and logs what it
    dropped and why that block. Every block is individually capped (lessons 5,
    plans 3); the sum was bounded by nothing, and a trim that left no trace
    would be a silent redefinition of what the session was armed with."""

    LESSON = "a lesson line that is long enough to be worth dropping"

    def repo_with_state(self):
        repo = self.make_repo()
        path = os.path.join(repo, ".tezgah", "lessons.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(self.LESSON + "\n")
        self.touch(os.path.join(repo, "plans", "open", "001-something.md"))
        return repo

    def session_start_text(self, repo, limit=None):
        """The session-start text for `repo`, the budget patched to `limit`."""
        patch = ("tc.CONTEXT_BUDGET['session_start'] = %d\n" % limit
                 if limit is not None else "")
        return self.child("import json, tezgah_context as tc\n" + patch
                          + "print(json.dumps(tc.context_for"
                            "('session_start', %r)))\n" % repo)

    def budget(self, event):
        sys.path.insert(0, support.HOOKS)
        import tezgah_context as tc  # noqa: E402
        return tc.CONTEXT_BUDGET[event]

    def test_one_byte_over_budget_gives_up_the_lowest_value_block_first(self):
        repo = self.repo_with_state()
        whole = self.session_start_text(repo)
        out = self.session_start_text(repo, limit=len(whole.encode()) - 1)
        # exactly one block was given up, and it is the lowest-value one
        self.assertIn("dropped lessons (", out)
        self.assertIn("lowest value first", out)
        self.assertNotIn(self.LESSON, out)
        # ...while every block that outranks lessons is still there
        self.assertIn("Open plans in this repo", out)
        self.assertIn("codebase-memory-mcp is not installed", out)
        self.assertIn("tezgah-contract` skill", out)

    def test_a_limit_below_the_core_is_reported_not_silently_missed(self):
        out = self.session_start_text(self.repo_with_state(), limit=3000)
        self.assertIn("still", out)
        self.assertIn("the always-on core and that is never dropped", out)

    def test_the_drop_is_logged_with_what_went_and_at_what_size(self):
        repo = self.repo_with_state()
        limit = len(self.session_start_text(repo).encode()) - 1
        self.session_start_text(repo, limit=limit)
        log = os.path.join(self.home, ".cache", "tezgah", "context-drops.log")
        with open(log) as fh:
            rows = [r for r in fh.read().splitlines() if r]
        self.assertTrue(rows, "no drop row was written")
        self.assertIn("event=session_start", rows[-1])
        self.assertIn("limit=%d" % limit, rows[-1])
        self.assertIn("dropped=lessons:", rows[-1])

    def test_a_subagent_brief_fits_the_smaller_subagent_budget(self):
        # the brief is a third of the core; a payload that paid the full core
        # here would blow the budget and drop real state instead
        out = self.child("import json, tezgah_context as tc\n"
                         "print(json.dumps(tc.context_for('subagent_start', %r,"
                         " {'prompt': 'x'})))\n" % self.repo_with_state())
        self.assertIn("Full text in the `tezgah-contract` skill", out)
        self.assertNotIn("Context budget", out)

    def test_a_healthy_repo_pays_no_drop_and_stays_under_its_budget(self):
        repo = self.repo_with_state()
        out = self.session_start_text(repo)
        self.assertNotIn("Context budget", out)
        self.assertLess(len(out.encode()), self.budget("session_start"))
        # every conditional rule armed at once is the largest prompt text the
        # classifier can build, so it is the case the prompt budget must hold
        prompt = ("design decision and root cause, migration schema change, "
                  "literature review hypothesis benchmark, who calls it, "
                  "düzgün çalışsın")
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "context_for", "event": "user_prompt",
                              "cwd": repo, "payload": {"prompt": prompt}},
                             env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("Context budget", out)
        self.assertLess(len(out.encode()), self.budget("user_prompt"))


class StateDelta(ChildCall):
    """C1: the standing constraints are re-stated every turn and a long turn
    re-states them again without being able to say what moved. The per-turn
    state stamp (HEAD, open plans, lessons digest) turns that into one delta
    line, and the full re-statement stays for a turn with nothing comparable."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        self.touch(os.path.join(self.repo, "f"))
        self.commit("first")

    def git(self, *args):
        return subprocess.run(["git", "-C", self.repo] + list(args),
                              capture_output=True, text=True, check=True).stdout

    def head(self):
        return self.git("rev-parse", "HEAD").strip()

    def commit(self, message):
        self.git("add", ".")
        self.git("-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm",
                 message)

    def turn(self, session="s1"):
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "context_for", "event": "user_prompt",
                              "cwd": self.repo,
                              "payload": {"session_id": session,
                                          "prompt": "add a docstring"}},
                             env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def test_the_first_turn_keeps_the_re_statement_and_has_no_delta(self):
        out = self.turn()
        self.assertIn("harness-reminder", out)
        self.assertNotIn("State since your last turn", out)

    def test_a_head_move_is_named_on_the_next_turn(self):
        was = self.head()
        self.turn()
        self.touch(os.path.join(self.repo, "g"))
        self.commit("second")
        out = self.turn()
        self.assertIn("State since your last turn: HEAD %s -> %s"
                      % (was[:7], self.head()[:7]), out)

    def test_an_unchanged_turn_carries_no_delta(self):
        # the delta is a difference, not another re-statement: a turn that
        # changed nothing says nothing
        self.turn()
        self.assertNotIn("State since your last turn", self.turn())

    def test_a_new_lesson_is_named_with_its_count(self):
        self.turn()
        path = os.path.join(self.repo, ".tezgah", "lessons.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write("always clamp the padding\n")
        self.assertIn("lessons 0 -> 1", self.turn())

    def test_a_new_plan_is_named(self):
        self.turn()
        self.touch(os.path.join(self.repo, "plans", "open", "042-thing.md"))
        self.assertIn("open plans 0 -> 1 (+042-thing.md)", self.turn())

    def test_the_stamp_is_per_session(self):
        self.turn("s1")
        self.assertNotIn("State since your last turn", self.turn("s2"))

    def test_a_stamp_from_another_repo_is_not_comparable(self):
        # the fallback, not a wrong delta: an unusable stamp must not be read as
        # "the state moved"
        self.turn()
        turns = os.path.join(self.home, ".cache", "tezgah", "turns")
        path = os.path.join(turns, os.listdir(turns)[0])
        with open(path) as fh:
            stamp = json.load(fh)
        stamp["root"] = "/somewhere/else"
        with open(path, "w") as fh:
            json.dump(stamp, fh)
        self.touch(os.path.join(self.repo, "g"))
        self.commit("second")
        self.assertNotIn("State since your last turn", self.turn())


class ConstraintNotice(ChildCall):
    """The gate's drift notice (`constraints_line`) re-states every standing
    rule it can see. With a comparable stamp it carries the delta instead; the
    full re-statement is what it falls back to, so the notice can never end up
    saying less than it does today."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        self.touch(os.path.join(self.repo, "f"))
        subprocess.run(["git", "-C", self.repo, "add", "."], check=True)
        subprocess.run(["git", "-C", self.repo, "-c", "user.email=a@b",
                        "-c", "user.name=t", "commit", "-qm", "first"], check=True)

    def turn(self):
        return self.child(
            "import json, tezgah_context as tc\n"
            "print(json.dumps(tc.context_for('user_prompt', %r,"
            " {'session_id': 's1', 'prompt': 'x'})))\n" % self.repo)

    def notice(self):
        return self.child("import json, tezgah_context as tc\n"
                          "print(json.dumps(tc.constraint_notice(%r, 's1')))\n"
                          % self.repo)

    def test_without_a_comparable_stamp_it_re_states_the_constraints(self):
        out = self.notice()
        self.assertIn("**Turkish, BLUF.**", out)
        self.assertIn("**Ponytail (minimal code).**", out)
        self.assertIn("On-demand rules", out)

    def test_with_a_moved_state_it_carries_the_delta(self):
        self.turn()
        subprocess.run(["git", "-C", self.repo, "-c", "user.email=a@b",
                        "-c", "user.name=t", "commit", "-q", "--allow-empty",
                        "-m", "second"], check=True)
        out = self.notice()
        self.assertIn("State since your last turn: HEAD ", out)
        self.assertNotIn("**Turkish, BLUF.**", out)


class StaleIndexNotice(TempHome):
    """C3: a graph stamp behind HEAD used to end in a `↻` glyph on the status
    line, which the model does not read, so the turn that decides from the graph
    was told nothing. The same comparison now reaches the turn."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        # a real executable so cbm_bin() is truthy without a real index daemon
        self.envv = self.env(extra={"TEZGAH_CBM_BIN": sys.executable})
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        self.touch(os.path.join(self.repo, "f"))
        subprocess.run(["git", "-C", self.repo, "add", "."], check=True)
        subprocess.run(["git", "-C", self.repo, "-c", "user.email=a@b",
                        "-c", "user.name=t", "commit", "-qm", "first"], check=True)
        slug = support.slug(os.path.realpath(self.repo))
        db_dir = os.path.join(self.home, ".cache", "codebase-memory-mcp")
        os.makedirs(db_dir, exist_ok=True)
        open(os.path.join(db_dir, slug + ".db"), "w").close()
        self.stamp_path = os.path.join(self.home, ".cache", "tezgah", slug)

    def head(self):
        return subprocess.run(["git", "-C", self.repo, "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()

    def stamp(self, sha):
        self.touch(self.stamp_path)
        with open(self.stamp_path, "w") as fh:
            fh.write(sha)

    def turn(self):
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "context_for", "event": "user_prompt",
                              "cwd": self.repo,
                              "payload": {"session_id": "s",
                                          "prompt": "add a docstring"}},
                             env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def test_a_stamp_behind_head_is_injected_into_the_turn(self):
        self.stamp("deadbeef" * 5)
        out = self.turn()
        self.assertIn("Graph index: the graph is indexed at deadbee, HEAD is %s"
                      % self.head()[:7], out)
        self.assertIn("the index is behind", out)

    def test_a_fresh_stamp_adds_no_line(self):
        self.stamp(self.head())
        self.assertNotIn("Graph index:", self.turn())

    def test_no_stamp_at_all_is_not_a_stale_stamp(self):
        out = self.turn()
        self.assertNotIn("Graph index:", out)


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


class RecordKinds(TempHome):
    """record() is the ledger's only writer, and every host classifies every
    tool it sees, so the no-ops must not reach the file: a real 425-line session
    ledger held 395 `{"kind": null}` lines against 30 kinds."""

    def record(self, session_id, kind):
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "record", "session_id": session_id,
                              "kind": kind}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(out)
        return self.ledger(session_id)

    def ledger(self, session_id):
        path = os.path.join(self.home, ".cache", "tezgah", "sessions",
                            support.slug(session_id) + ".jsonl")
        if not os.path.exists(path):
            return []
        with open(path) as fh:
            return [json.loads(line)["kind"] for line in fh if line.strip()]

    def test_a_tool_that_is_not_one_of_ours_is_not_an_event(self):
        self.assertEqual(self.record("s1", None), [])
        self.assertEqual(self.record("s1", ""), [])

    def test_a_real_kind_is_written_once_and_read_back(self):
        self.assertEqual(self.record("s1", "consult"), ["consult"])
        self.assertEqual(self.record("s1", "cbm"), ["consult", "cbm"])


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
        # Turkish hints are stems, so their inflected forms must arm too
        "bu ekran düzgün çalışsın": {"spec"},
        "hipotezi test et": {"research"},
        "bu fonksiyonu kim çağırıyor?": {"cbm"},
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
            out, _ = run_json([support.OMP_HOOK],
                              {"event": "user_prompt", "cwd": repo,
                               "prompt": prompt}, env=env)
            got["omp"] = self.armed(out["context"])
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


class SubagentBrief(unittest.TestCase):
    """A delegated agent gets the rules in short form: every label, the opening
    clause, and a pointer to the full text. Losing a rule here would be silent,
    so the label set is asserted rather than trusted."""

    def setUp(self):
        sys.path.insert(0, os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))
        import tezgah_context as tc  # noqa: E402
        self.tc = tc

    def test_every_always_on_rule_appears_in_the_brief(self):
        brief = self.tc.subagent_core()
        for key, label in self.tc.CORE_RULES:
            if key in self.tc.CONDITIONAL_KEYS:
                continue
            self.assertIn(label, brief, "missing from the subagent brief: %s" % key)

    def test_the_brief_is_shorter_and_leaves_the_detail_on_demand(self):
        core = self.tc.always_on_core()
        brief = self.tc.subagent_core(core)
        self.assertLess(len(brief), len(core) * 0.5)
        self.assertIn("tezgah-contract", brief)
        for key, label in self.tc.CORE_RULES:
            if key in self.tc.CONDITIONAL_KEYS:
                self.assertNotIn(label, brief,
                                 "a conditional rule rode into the brief: %s" % key)

    def test_the_safety_rule_survives_the_shortening(self):
        self.assertIn("Irreversible or outward-facing", self.tc.subagent_core())



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
