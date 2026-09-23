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

    def test_a_research_prompt_writes_the_false_negative_log(self):
        # A keyword the hints miss is silent by nature, so `audit_classification`
        # is the only audit trail of a wrong arming - and nothing under tests/
        # read the log or its row. Pin the entry and the place it lands, both
        # derivable only from cache_dir().
        repo = self.make_repo()
        prompt = "research the literature on X"
        out, proc = self.call({"fn": "context_for", "event": "user_prompt",
                               "cwd": repo, "payload": {"prompt": prompt}})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("**Research: route it to OpenResearch.**", out)
        log = os.path.join(self.home, ".cache", "tezgah", "classify.log")
        with open(log) as fh:
            rows = fh.read().splitlines()
        self.assertEqual(len(rows), 1, rows)
        m = re.fullmatch(r"(\d+) armed=research chars=(\d+)", rows[0])
        self.assertIsNotNone(m, rows[0])
        self.assertGreater(int(m.group(1)), 0)          # a stamp, not a placeholder
        self.assertEqual(int(m.group(2)), len(prompt))

    def line(self, repo, slug, phase, report=True, review=None, protocol=None,
             results=None, analysis=False):
        """One research line on disk: the phase, the to_human pair and one
        experiment, each one a switch the open-line rule reads."""
        base = os.path.join(repo, ".tezgah", "research", slug)
        self.touch(os.path.join(base, "log.md"))
        with open(os.path.join(base, "state.json"), "w") as fh:
            json.dump({"phase": phase}, fh)
        if report:
            self.touch(os.path.join(base, "to_human", "report.md"))
        if review is not None:
            with open(os.path.join(base, "to_human", "review.json"), "w") as fh:
                json.dump({"findings": review}, fh)
        if protocol:
            self.touch(os.path.join(base, "experiments", "e0", "protocol.md"))
            if results is not None:
                with open(os.path.join(base, "experiments", "e0",
                                       "results.jsonl"), "w") as fh:
                    fh.write(results)
            if analysis:
                self.touch(os.path.join(base, "experiments", "e0",
                                        "analysis.md"))
        return base

    def test_the_research_rule_names_the_lines_already_open(self):
        # The rule routed research and said nothing about a line already under
        # way, which is how thirteen lines came to stand with eleven of them
        # unfinished. The armed paragraph now carries the open ones - built
        # where the repo is known, which no static string could be.
        repo = self.make_repo()
        # three listing-level reasons: a phase past nothing, a pre-registered
        # experiment nobody ran, and a finding the review never labelled
        self.line(repo, "halted", "inner", review=[{"quote": "x"}],
                  protocol=True)
        # one reason, and the singular form of the count: the run happened but
        # nothing analysed it
        self.line(repo, "midrun", "concluded", review=[{"status": "fixed"}],
                  protocol=True, results='{"source": "real"}\n')
        # every signal closed, so this one is not named
        self.line(repo, "settled", "concluded", review=[{"status": "fixed"}])
        out, proc = self.call({"fn": "context_for", "event": "user_prompt",
                               "cwd": repo, "payload": {
                                   "prompt": "research the literature on X",
                                   "session_id": "s-open"}})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("At most one line is open at a time", out)
        self.assertIn("Open research line(s)", out)
        self.assertIn("`halted` (3 reasons)", out)
        self.assertIn("`midrun` (1 reason)", out)
        self.assertNotIn("`settled`", out)
        self.assertNotIn("{OPEN_LINES}", out)

    def test_the_research_rule_names_no_line_when_the_tree_is_closed(self):
        # The other half of the sentence: a repo with no line open pays for the
        # listing and not for a sentence about nothing - and never for the raw
        # placeholder, which is what a missing wiring would leave behind.
        repo = self.make_repo()
        out, proc = self.call({"fn": "context_for", "event": "user_prompt",
                               "cwd": repo, "payload": {
                                   "prompt": "research the literature on X",
                                   "session_id": "s-clean"}})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("At most one line is open at a time", out)
        self.assertNotIn("Open research line(s)", out)
        self.assertNotIn("{OPEN_LINES}", out)


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
        self.assertEqual(out, PREFIX + "pony\u25cb exec\u2713 adhd\u25cb  \u00b7  "
                              "consult\u2717 research\u2717 graph\u25cb orch\u25cb "
                              "judge\u2717")

    def test_armed_but_unused_checklist(self):
        repo = self.make_repo()
        self.armed_key()
        out, _ = run_json([support.PROBE_CONTEXT],
                          {"fn": "health_lines", "cwd": repo, "session_id": "s"},
                          env=self.env())
        self.assertEqual(out, PREFIX + "pony\u25cb exec\u2713 adhd\u25cb  \u00b7  "
                              "consult\u25cb research\u2717 graph\u25cb orch\u25cb "
                              "judge\u2717  \u00b7  idx\u2013")

    def test_used_kind_flips_a_mark(self):
        repo = self.make_repo()
        self.armed_key()
        _, proc = run_json([support.PROBE_CONTEXT],
                           {"fn": "record", "session_id": "s", "kind": "graph"},
                           env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out, _ = run_json([support.PROBE_CONTEXT],
                          {"fn": "health_lines", "cwd": repo, "session_id": "s"},
                          env=self.env())
        self.assertIn("graph\u2713", out)

    def test_reading_the_skill_flips_the_pony_mark(self):
        # the mark's whole point: armed is not the same as read. A host records
        # the kind when the session opens the skill's full text.
        repo = self.make_repo()
        self.armed_key()
        before, _ = run_json([support.PROBE_CONTEXT],
                             {"fn": "health_lines", "cwd": repo,
                              "session_id": "s"}, env=self.env())
        self.assertIn("pony\u25cb", before)
        _, proc = run_json([support.PROBE_CONTEXT],
                           {"fn": "record", "session_id": "s", "kind": "pony"},
                           env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        after, _ = run_json([support.PROBE_CONTEXT],
                            {"fn": "health_lines", "cwd": repo,
                             "session_id": "s"}, env=self.env())
        self.assertIn("pony\u2713", after)
        self.assertIn("adhd\u25cb", after)   # one skill read is not the other

    def test_repo_no_graph_mark(self):
        repo = self.make_repo()
        self.armed_key()
        self.touch(os.path.join(repo, ".no-graph"))
        out, _ = run_json([support.PROBE_CONTEXT],
                          {"fn": "health_lines", "cwd": repo, "session_id": "s"},
                          env=self.env())
        self.assertIn("graph\u2717", out)

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
        self.assertIn("\033[32mexec\u2713\033[0m", out)      # always-on
        self.assertIn("\033[33mpony\u25cb\033[0m", out)      # armed, not read
        self.assertIn("\033[33madhd\u25cb\033[0m", out)      # armed, not read
        self.assertIn("\033[33mconsult\u25cb\033[0m", out)   # armed, unused
        self.assertIn("\033[31mresearch\u2717\033[0m", out)  # off
        self.assertIn("\033[2midx\u2013\033[0m", out)        # no state
        self.assertIn("\033[2m  \u00b7  \033[0m", out)

    def test_open_plans_segment(self):
        repo = self.make_repo()
        self.armed_key()
        self.touch(os.path.join(repo, ".tezgah", "plans", "open", "001-a.md"))
        self.touch(os.path.join(repo, ".tezgah", "plans", "open", "002-b.md"))
        with open(os.path.join(repo, ".tezgah", "plans", "open", "001-a.md"), "w") as fh:
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
        # a real executable so codegraph_bin() is truthy without a real index
        self.envv = self.env(extra={"TEZGAH_CODEGRAPH_BIN": sys.executable})
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        self.touch(os.path.join(self.repo, "f"))
        subprocess.run(["git", "-C", self.repo, "add", "."], check=True)
        subprocess.run(["git", "-C", self.repo, "-c", "user.email=a@b",
                        "-c", "user.name=t", "commit", "-qm", "x"], check=True)

    def head(self):
        return subprocess.run(["git", "-C", self.repo, "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()

    def index(self, stamp):
        """The repo's own codegraph index, plus the HEAD the worker stamped."""
        slug = support.slug(os.path.realpath(self.repo))
        os.makedirs(os.path.join(self.repo, ".codegraph"), exist_ok=True)
        open(os.path.join(self.repo, ".codegraph", "codegraph.db"), "w").close()
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
            # `ekran` and `arayüz` are feature surfaces now, so naming one as
            # the thing to fix arms the feature-audit half of the product rule
            # alongside the UI adjective's `spec`
            "bu ekran düzgün çalışsın": {"product", "spec"},
            "arayüz güzel görünsün": {"product", "spec"},
            "metin biraz daha iyi olsun": {"spec"},
            "kök nedenini bulalım": {"consult"},
            "mimarisini yeniden kuralım": {"consult"},
            "araştırma yap": {"research"},
            "hipotezi test et": {"research"},
            "bu fonksiyonu kim çağırıyor?": {"graph"},
            "bu modül nasıl bağlanmış?": {"graph"},
            "bu değişiklikten hangi dosyalar etkilenir": {"graph"},
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


class ProductClassArming(unittest.TestCase):
    """The product class exists because a product question armed nothing at all:
    the four classes above are about code, a UI adjective or a study, so "ürünle
    alakalı analiz istiyorum" reached no rule and the answer came from priors -
    the exact defect the rule was added to fix."""

    def setUp(self):
        sys.path.insert(0, os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))
        import tezgah_context as tc  # noqa: E402
        self.armed = tc.classify_prompt

    def test_a_product_question_arms_the_product_class(self):
        for prompt in ("bu ürünü analiz et ve nasıl iyileştirebiliriz",
                       "ürünle alakalı analiz istiyorum ürünleri daha iyi "
                       "hale getirmek istiyorum",
                       "ürünümüzü nasıl iyileştiririz",
                       "product manager seviyesinde analiz yap",
                       "retention düşüyor ne yapmalıyız",
                       "which feature should we build next",
                       "feature önerilerini önceliklendir",
                       "review this backlog before the roadmap review"):
            self.assertIn("product", self.armed(prompt), prompt)

    def test_the_product_hint_does_not_fire_on_a_shared_prefix(self):
        # `production` and `productivity` are code words that merely share the
        # prefix with `product`; arming product analysis on a deploy question
        # would spend the paragraph on the wrong task class.
        self.assertNotIn("product", self.armed("deploy to production"))
        self.assertEqual(self.armed("improve developer productivity"), set())
        self.assertEqual(self.armed("kullanıcı deneyimi raporu"), set())


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
        # the repo's own index, so the idx mark really has a reason to compare
        # HEAD to the stamp
        os.makedirs(os.path.join(self.repo, ".codegraph"), exist_ok=True)
        open(os.path.join(self.repo, ".codegraph", "codegraph.db"), "w").close()

    def test_a_session_start_forks_git_twice(self):
        shim = os.path.join(self.home, "shim")
        os.makedirs(shim, exist_ok=True)
        log = os.path.join(self.home, "git.log")
        script = os.path.join(shim, "git")
        with open(script, "w") as fh:
            fh.write('#!/bin/sh\nprintf "%%s\\n" "$*" >> "$TEZGAH_GIT_LOG"\n'
                     'exec %s "$@"\n' % shutil.which("git"))
        os.chmod(script, 0o755)
        env = self.env(extra={"TEZGAH_CODEGRAPH_BIN": sys.executable,
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
        # so pin one: whether this machine happens to have codegraph installed
        # (it is absent in CI) must not decide whether the mark probes.
        prev_bin = os.environ.get("TEZGAH_CODEGRAPH_BIN")
        os.environ["TEZGAH_CODEGRAPH_BIN"] = sys.executable
        self.addCleanup(self._restore_graph_bin, prev_bin)
        self.addCleanup(setattr, tc, "git", tc.git)
        self.addCleanup(setattr, tc, "repo_marks", tc.repo_marks)
        tc.git = lambda *a: self.probes.append(a) or "deadbeef" * 5
        tc.repo_marks = lambda cwd: ("/base", set())

    @staticmethod
    def _restore_graph_bin(prev):
        if prev is None:
            os.environ.pop("TEZGAH_CODEGRAPH_BIN", None)
        else:
            os.environ["TEZGAH_CODEGRAPH_BIN"] = prev

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

    def test_the_layers_own_cli_is_a_research_run(self):
        # `tezgah-research` reads and writes the research workspace, so a run of
        # it is a research run; before this it was classified as nothing, and the
        # mark could only light from `orx` - the tool the rule routes to, never
        # the layer the rule is about. The installed CLI is spelled as an absolute
        # path by the rule's own text, so that spelling has to arrive as the same
        # word as the bare name.
        for command in ("tezgah-research check",
                        "tezgah-research check --strict",
                        "bin/tezgah-research status",
                        "/Users/u/.config/tezgah/bin/tezgah-research source h "
                        "--run r1",
                        "cd repo && tezgah-research migrate line --dry-run",
                        "bash -c 'tezgah-research claim line'"):
            self.assertEqual(self.kind(command), "research", command)

    def test_a_mention_is_not_a_use(self):
        for command in ("grep -n consult hooks/",
                        "git log --grep=consult",
                        "echo 'run consult later'",
                        "grep -rn tezgah-research docs/",
                        "echo 'tezgah-research check is the reader'",
                        "cat <<'EOF'\nconsult q\nEOF",
                        "python3 - <<EOF\norx skill\nEOF",
                        "python3 - <<EOF\ntezgah-research check\nEOF",
                        "echo $((1<<2)); grep orx hooks/"):
            self.assertIsNone(self.kind(command), command)


class KillSwitchEnforcement(TempHome):
    """A documented kill switch must remove its rule from the injected text,
    not just flip a status mark. The labels are pinned here, so editing one in
    hooks/tezgah_policy.py fails this test instead of silently disabling it."""

    OFF = "**Turkish, BLUF.**"
    PONY = "**Ponytail (minimal code).**"
    ADHD = "**Output shape: ADHD-friendly.**"
    FIDELITY = "**Deliver the whole ask; never the shortcut.**"
    INTEGRITY = '**Integrity: evidence, or "doğrulanmadı".**'
    LOOP = "**Loop discipline.**"
    SPEC = "**Spec before building.**"
    LESSONS = "**Lessons ledger: stop repeating mistakes.**"
    GRAPH = "**Code discovery: graph first.**"
    CONSULT = "**Consult before irreversible.**"
    RESEARCH = "**Research: route it to OpenResearch.**"
    PRODUCT = ("**Product analysis: five axes, one evidence class per "
               "finding.**")
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
        for label in (self.OFF, self.PONY, self.ADHD, self.FIDELITY,
                      self.INTEGRITY, self.LOOP, self.ATTRIBUTION, self.LESSONS):
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
        for label in (self.SPEC, self.GRAPH, self.CONSULT, self.RESEARCH,
                      self.PRODUCT):
            self.assertNotIn(label, out)
        self.assertIn(self.SPEC,
                      self.prompt(repo, "Bu ekranı daha kullanıcı dostu yap"))
        self.assertIn(self.CONSULT,
                      self.prompt(repo, "Which approach for the schema change?"))
        self.assertIn(self.RESEARCH,
                      self.prompt(repo, "Run a literature review and form a hypothesis"))
        self.assertIn(self.GRAPH, self.prompt(repo, "who calls calc_total?"))
        self.assertIn(self.PRODUCT,
                      self.prompt(repo, "which feature should we build next"))

    def test_a_plain_prompt_arms_no_conditional_rule(self):
        out = self.prompt(self.make_repo(), "add a docstring to parse_quantity")
        self.assertIn("harness-reminder", out)
        for label in (self.SPEC, self.GRAPH, self.CONSULT, self.RESEARCH,
                      self.PRODUCT):
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

    def test_adhd_off_drops_the_adhd_rule(self):
        repo = self.make_repo()
        self.switch("adhd-off")
        self.assertNotIn(self.ADHD, self.session(repo))

    def test_repo_no_adhd_drops_the_adhd_rule(self):
        repo = self.make_repo()
        self.touch(os.path.join(repo, ".no-adhd"))
        self.assertNotIn(self.ADHD, self.session(repo))

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

    def test_research_off_drops_the_product_rule_too(self):
        # One switch, two rules: the product paragraph routes through the same
        # research workspace, so leaving it armed under research-off would leave
        # a rule that names a switch which no longer applies to it.
        repo = self.make_repo()
        self.switch("research-off")
        self.assertNotIn(
            self.PRODUCT, self.prompt(repo, "which feature should we build next"))

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

    def test_repo_no_graph_drops_the_graph_rule(self):
        repo = self.make_repo()
        self.touch(os.path.join(repo, ".no-graph"))
        out = self.session(repo)
        self.assertNotIn(self.GRAPH, out)
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
        self.touch(os.path.join(repo, ".tezgah", "plans", "open", "001-something.md"))
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
        self.assertIn("codegraph is not installed", out)
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
        self.touch(os.path.join(self.repo, ".tezgah", "plans", "open", "042-thing.md"))
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
        self.assertIn("**Output shape: ADHD-friendly.**", out)
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
        # a real executable so codegraph_bin() is truthy without a real index
        self.envv = self.env(extra={"TEZGAH_CODEGRAPH_BIN": sys.executable})
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        self.touch(os.path.join(self.repo, "f"))
        subprocess.run(["git", "-C", self.repo, "add", "."], check=True)
        subprocess.run(["git", "-C", self.repo, "-c", "user.email=a@b",
                        "-c", "user.name=t", "commit", "-qm", "first"], check=True)
        slug = support.slug(os.path.realpath(self.repo))
        os.makedirs(os.path.join(self.repo, ".codegraph"), exist_ok=True)
        open(os.path.join(self.repo, ".codegraph", "codegraph.db"), "w").close()
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

    def test_no_stamp_at_all_is_unknown_rather_than_a_stale_stamp(self):
        # C10 closed the other half of this: no stamp is not a stale stamp, and
        # it is not a fresh one either. The turn is told the age is unknown
        # rather than being told nothing.
        out = self.turn()
        self.assertIn("unknown", out)
        self.assertNotIn("the index is behind", out)


class ActiveTaskLine(TempHome):
    """The active task's phase rides every user turn. The gate reads the same
    record and refuses a write the phase or the allowlist excludes, but only
    after the call, and a refusal costs a turn - so the line that prevents it
    has to be in the turn the write is decided in, and it has to follow the plan
    file, which the user edits with the CLI between turns."""

    def plan(self, repo, name="001-thing.md", phase=None, allow=None):
        lines = ["---", "id: %s" % name[:3], "title: a plan worth a phase",
                 "status: open"]
        if phase is not None:
            lines.append("phase: %s" % phase)
        if allow is not None:
            lines.append("allowed_paths:")
            lines += ["  - %s" % glob for glob in allow]
        lines += ["created: 2026-09-18", "updated: 2026-09-18", "---",
                  "## Goal", "the thing worth doing", ""]
        path = os.path.join(repo, ".tezgah", "plans", "open", name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write("\n".join(lines))
        return path

    def turn(self, repo, session="s1"):
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "context_for", "event": "user_prompt",
                              "cwd": repo,
                              "payload": {"session_id": session,
                                          "prompt": "add a docstring"}},
                             env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def test_the_line_names_the_phase_and_the_scope_not_a_command(self):
        repo = self.make_repo()
        self.plan(repo, phase="implementation", allow=["hooks/**", "tests/**"])
        out = self.turn(repo)
        self.assertIn("Active task 001 is in phase `implementation`", out)
        self.assertIn("hooks/**, tests/**", out)
        # The line used to end with the command that moves the phase, and E7b
        # watched the armed arm run that command five times in a row against a
        # gate that refuses it every time. It names the user now, not an act the
        # gate will refuse.
        self.assertIn("belongs to the user", out)
        self.assertNotIn("Advance it with", out)
        # the per-turn channel is a prompt hook: a session start already carries
        # the plans block, and a second copy of the phase there would be paid by
        # every session, including the ones with no task
        start, proc = run_json([support.PROBE_CONTEXT],
                               {"fn": "context_for", "event": "session_start",
                                "cwd": repo}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("Active task", start)

    def test_an_empty_allowlist_says_the_whole_repo(self):
        repo = self.make_repo()
        self.plan(repo, phase="verification", allow=[])
        self.assertIn("any path in the repo", self.turn(repo))

    def test_no_active_plan_means_no_line(self):
        repo = self.make_repo()
        self.assertNotIn("Active task", self.turn(repo))
        # a plan without a phase is not an active task either: the phase is what
        # activates it, so a plan-status file must not look like a task
        self.plan(repo)
        self.assertNotIn("Active task", self.turn(repo))

    def test_a_phase_outside_the_three_is_ignored_not_guessed(self):
        # fail open: a typo in the frontmatter must not arm a phase the user
        # never set, and must not refuse anything either
        repo = self.make_repo()
        self.plan(repo, phase="implementing")
        self.assertNotIn("Active task", self.turn(repo))

    def test_a_phase_change_is_visible_in_the_next_turn(self):
        repo = self.make_repo()
        path = self.plan(repo, phase="discovery")
        self.assertIn("`discovery`", self.turn(repo))
        with open(path) as fh:
            text = fh.read()
        with open(path, "w") as fh:
            fh.write(text.replace("phase: discovery", "phase: implementation"))
        out = self.turn(repo)
        self.assertIn("`implementation`", out)
        self.assertNotIn("`discovery`", out)

    # the largest prompt the classifier can build: all four conditional rules
    # armed at once
    PROMPT = ("design decision and root cause, migration schema change, "
              "literature review hypothesis benchmark, who calls it, "
              "düzgün çalışsın")
    ARMED = ("**Spec before building.**", "**Consult before irreversible.**",
             "**Research: route it to OpenResearch.**",
             "**Code discovery: graph first.**")

    def test_the_turn_that_pays_the_most_still_fits_its_budget(self):
        # the line is paid on every user turn, so the turn that decides the
        # prompt budget is the largest one: every conditional rule armed, beside
        # an active task
        repo = self.make_repo()
        self.plan(repo, phase="implementation", allow=["hooks/**", "tests/**"])
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "context_for", "event": "user_prompt",
                              "cwd": repo, "payload": {"prompt": self.PROMPT}},
                             env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for label in self.ARMED:
            self.assertIn(label, out)
        sys.path.insert(0, support.HOOKS)
        import tezgah_context as tc  # noqa: E402
        self.assertNotIn("Context budget", out)
        self.assertLess(len(out.encode()), tc.CONTEXT_BUDGET["user_prompt"])


class ScratchEvidenceReminder(TempHome):
    """The turn that decided from a scratch script: the ledger says every check
    that passed this session ran somewhere the session generated. Warn-class,
    because whether a scratch script exercises the real system is not decidable
    from the command - so the turn gets the command and the rule, and the switch
    that removes the integrity rule removes this line with it."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")

    def check(self, command, session="s1", kind="verify_ok", exit=0, out_bytes=9):
        _, proc = run_json([support.PROBE_INTEGRITY],
                           {"fn": "note", "session": session, "kind": kind,
                            "detail": command, "exit": exit,
                            "out_bytes": out_bytes}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def turn(self, session="s1"):
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "context_for", "event": "user_prompt",
                              "cwd": self.repo,
                              "payload": {"session_id": session,
                                          "prompt": "add a docstring"}},
                             env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def test_a_scratch_path_is_named_and_the_rule_is_stated(self):
        self.check("python3 /tmp/x.py")
        out = self.turn()
        self.assertIn("`python3 /tmp/x.py`", out)
        self.assertIn("that is evidence about the code path, not the running "
                      "system", out)
        self.assertIn("a claim about the product needs a check that ran "
                      "against it", out)

    def test_a_check_against_the_real_repo_is_evidence_and_says_nothing(self):
        self.check("python3 -m pytest tests/")
        self.assertNotIn("Evidence scope", self.turn())

    def test_a_real_check_beside_the_scratch_one_says_nothing(self):
        self.check("python3 /tmp/x.py")
        self.check("python3 -m pytest tests/")
        self.assertNotIn("Evidence scope", self.turn())

    def test_a_scratch_check_that_did_not_pass_says_nothing(self):
        # the reader folds with `passing_check`: a failed run is not evidence, so
        # there is nothing to warn about yet
        self.check("python3 /tmp/x.py", kind="verify_fail", exit=1, out_bytes=0)
        self.assertNotIn("Evidence scope", self.turn())

    def test_another_sessions_ledger_does_not_arm_it(self):
        self.check("python3 /tmp/x.py", session="other")
        self.assertNotIn("Evidence scope", self.turn("s1"))

    def test_verify_off_silences_the_line(self):
        self.check("python3 /tmp/x.py")
        self.assertIn("Evidence scope", self.turn())
        self.touch(os.path.join(self.home, ".config", "tezgah", "verify-off"))
        self.assertNotIn("Evidence scope", self.turn())


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
        self.assertEqual(states["pony"], "ready")     # armed, skill not read
        self.assertEqual(states["exec"], "on")        # always-on
        self.assertEqual(states["adhd"], "ready")     # armed, skill not read
        self.assertEqual(states["consult"], "ready")  # armed, unused
        self.assertEqual(states["graph"], "ready")
        self.assertEqual(states["orch"], "ready")
        self.assertEqual(states["idx"], "info")       # no codegraph binary in tests
        self.assertEqual([s for s in out if s["key"] == "pony"][0]["glyph"], "\u25cb")

    def test_the_group_is_what_a_renderer_separates_on(self):
        # opencode's TUI and dsh's Web status line build their own line from
        # this JSON, so the group must be there and must ascend: without it they
        # cannot tell the flag groups from the per-repo facts.
        repo = self.make_repo()
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "health_segments", "cwd": repo,
                              "session_id": "s"}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        groups = [s["group"] for s in out]
        self.assertEqual(groups, sorted(groups), "groups must be in order")
        self.assertEqual(groups[:3], [-1, 0, 0],
                         "the version prefix leads, then pony and exec")
        self.assertNotEqual(groups[1], groups[-1], "per-repo marks are their own")


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
        self.assertEqual(self.record("s1", "graph"), ["consult", "graph"])


class PostToolUseUsedKind(TempHome):
    """Which tool call earns the graph mark, through the hook that writes it.

    projects-posttooluse.py is the only writer on a host without a transcript
    (dsh's Web status line reads this store), and it classifies from the tool
    NAME: codegraph's MCP tools arrive namespaced (`mcp__codegraph__<tool>`), so
    the server name is what identifies the call - whatever the tool does, and
    whether it came from the CLI or the MCP server."""

    def kinds(self, tool, inp, session="s"):
        repo = self.make_repo()
        _, proc = run_json([support.POSTTOOLUSE],
                           {"hook_event_name": "PostToolUse", "cwd": repo,
                            "tool_name": tool, "tool_input": inp,
                            "session_id": session}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        path = os.path.join(self.home, ".cache", "tezgah", "sessions",
                            support.slug(session) + ".jsonl")
        if not os.path.exists(path):
            return []
        with open(path) as fh:
            return [json.loads(line)["kind"] for line in fh if line.strip()]

    def test_a_codegraph_mcp_call_marks_the_graph(self):
        self.assertEqual(self.kinds("mcp__codegraph__codegraph_explore",
                                    {"query": "x"}, session="s1"), ["graph"])
        self.assertEqual(self.kinds("mcp__codegraph__codegraph_callers",
                                    {"symbol": "x"}, session="s2"), ["graph"])

    def test_another_servers_mcp_call_marks_nothing(self):
        # the name is the whole signal, so it has to be the graph's own: a
        # store keyed on the transport instead of the server turns every MCP
        # call green
        self.assertEqual(self.kinds("mcp__tezgah__search", {"query": "x"}), [])


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
        self.record("ses_test_1", ["graph", "consult"])
        env = self.env()
        env.pop("TEZGAH_SESSION", None)
        out = self.status(repo, "ses_test_1", env=env).stdout
        self.assertIn("graph\u2713", out)
        self.assertIn("consult\u2713", out)

    def test_without_a_session_id_marks_stay_unused(self):
        self.armed()
        repo = self.make_repo()
        self.record("ses_test_1", ["graph", "consult"])
        env = self.env()
        env.pop("TEZGAH_SESSION", None)
        out = self.status(repo, env=env).stdout
        self.assertIn("graph\u25cb", out)

    def test_unknown_option_is_rejected(self):
        proc = self.status("--bogus")
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("unknown option", proc.stderr)

    def test_a_measure_the_surface_cannot_see_states_nothing(self):
        # "armed, unused" is a claim, and a host that would have to spawn a
        # process per read to see a skill read cannot make it. It passes the
        # measures it does have; those two marks render dim with no glyph, while
        # a measure it can see keeps its own state.
        self.armed()
        repo = self.make_repo()
        env = self.env()
        out = self.status(repo, "--no-color",
                          "--observable=consult,research,graph,orch", env=env).stdout
        self.assertIn("pony ", out)
        self.assertNotIn("pony\u25cb", out)
        self.assertIn("consult\u25cb", out)

    def test_env_session_id_is_used_when_no_arg(self):
        self.armed()
        repo = self.make_repo()
        self.record("ses_test_1", ["graph"])
        env = self.env()
        env["TEZGAH_SESSION"] = "ses_test_1"
        self.assertIn("graph\u2713", self.status(repo, env=env).stdout)

    def test_json_flag_emits_segments(self):
        self.armed()
        repo = self.make_repo()
        segs = json.loads(self.status(repo, "--json").stdout)
        keys = {s["key"] for s in segs}
        self.assertIn("graph", keys)
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
              "product": "**Product analysis: five axes, one evidence class "
                         "per finding.**",
              "graph": "**Code discovery: graph first.**"}
    PROMPTS = {
        "Bu ekranı daha kullanıcı dostu yap": {"product", "spec"},
        "Which approach for the schema change?": {"consult"},
        "Run a literature review and form a hypothesis": {"research"},
        "which feature should we build next": {"product"},
        "ürünle alakalı analiz istiyorum ürünleri daha iyi hale getirmek "
        "istiyorum": {"product"},
        "who calls calc_total?": {"graph"},
        "add a docstring to parse_quantity": set(),
        "kullanıcı deneyimi raporu": set(),
        # Turkish hints are stems, so their inflected forms must arm too
        # "ekran" now carries the feature-audit half of the product rule with it:
        # a screen named as the thing to fix is a feature-level ask, and the
        # screen-level answer it used to get is the defect the rule exists for.
        "bu ekran düzgün çalışsın": {"product", "spec"},
        "hipotezi test et": {"research"},
        "bu fonksiyonu kim çağırıyor?": {"graph"},
        # one feature said by its surface, which armed nothing before
        "admin paneldeki users ekranını incele": {"product"},
        "bu filtre çalışmıyor": {"product"},
        "bu tabloyu iyileştir": {"product"},
        "kullanıcı listesi ekranında crud var mı": {"product"},
        # and the code senses the lookaheads keep out
        "ekran kartı sürücüsünü güncelle": set(),
        "adım sayısını azalt": set(),
        "format the output as json": set(),
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
                       "Product analysis", "code graph"):
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


class OutputShapeParagraphPinsItsRules(unittest.TestCase):
    """The always-on ADHD paragraph compresses the full rule, and only its bold
    label was pinned: the two rules the compression had already dropped - rule
    10's no-preamble/no-recap/no-closer ban and rule 5's mid-work exception -
    could be missing from the text a session actually pays for and every test
    still passed. The body is asserted, not the label."""

    def core(self):
        """`always_on_core()`, whitespace-flattened: the paragraphs are wrapped
        to ~78 columns, so a phrase assertion must not depend on where the wrap
        fell - that is a formatting change, not a rule change."""
        sys.path.insert(0, support.HOOKS)
        import tezgah_context as tc  # noqa: E402
        return " ".join(tc.always_on_core().split())

    def test_there_is_exactly_one_adhd_paragraph(self):
        # `core_split` keys a paragraph by its label, so a stray blank line that
        # broke the block in two would silently split the rule from its switch
        self.assertEqual(1, self.core().count("**Output shape: ADHD-friendly.**"),
                         self.core())

    def test_the_paragraph_bans_the_recap_and_the_closer(self):
        # the failure this fixes: a status reply that re-states the plan and
        # closes on a pleasantry, with nothing in the always-on text saying no
        self.assertRegex(self.core(), r"No preamble, no recap, no closer",
                         "the paragraph drops rule 10's no-recap/no-closer ban")

    def test_the_paragraph_keeps_the_mid_work_exception(self):
        # without it, a question the reader raises mid-work reads as the second
        # issue the paragraph defers, so the reader's own question goes unanswered
        self.assertRegex(self.core(),
                         r"a question the reader raises mid-work is answered",
                         "the paragraph drops rule 5's mid-work exception")

    def test_the_paragraph_names_the_skill_that_earns_the_adhd_mark(self):
        self.assertRegex(self.core(),
                         r"read the full `i-have-adhd` skill from the router",
                         "the paragraph never tells the session to read the skill "
                         "its `adhd` mark is keyed on")


class MarkedRulesNameTheirSkill(unittest.TestCase):
    """SKILL_MARKS says a read of that skill flips a status mark, but the mark is
    only reachable if the always-on core tells the session to read the skill. The
    ADHD paragraph asked for none, so its mark could only ever be lit by a session
    that guessed the path; nothing tied the mark to the text that earns it."""

    def test_every_marked_skill_is_named_in_the_core(self):
        sys.path.insert(0, support.HOOKS)
        import tezgah_context as tc  # noqa: E402
        core = " ".join(tc.always_on_core().split())
        self.assertTrue(tc.SKILL_MARKS, "no mark is wired to a skill read")
        for skill, mark in sorted(tc.SKILL_MARKS.items()):
            self.assertIn("read the full `%s` skill from the router" % skill, core,
                          "the core never tells the session to read the %s skill, "
                          "so the `%s` mark can never flip" % (skill, mark))


class PromptReminderCarriesTheOutputShape(TempHome):
    """The per-turn reminder is the text a session re-reads every turn, and it
    carried no output-shape clause at all: nothing on that surface said answer
    first, no recap or closer, at most five ranked items - the turn that answers
    with a 30-line table pays the reminder either way."""

    def prompt(self, repo):
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "context_for", "event": "user_prompt",
                              "cwd": repo, "payload": {"prompt": "fix it"}},
                             env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def test_the_rendered_reminder_states_the_output_shape(self):
        out = self.prompt(self.make_repo())
        self.assertIn("harness-reminder", out)
        self.assertRegex(out, r"answer first -\s+no recap, no closer, at most "
                              r"five ranked items")


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
                   "**Product analysis: five axes, one evidence class per "
                   "finding.**",
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


class PonyLevel(TempHome):
    """The intensity level is a stored setting, not a phrase in a document: the
    CLI is what writes it and the per-turn reminder is what names it."""

    CLI = os.path.join(support.REPO, "bin", "tezgah-pony")

    def cli(self, *args):
        return support.run([self.CLI] + list(args), env=self.env())

    def level_file(self):
        return os.path.join(self.home, ".config", "tezgah", "ponytail.level")

    def prompt(self, repo):
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "context_for", "event": "user_prompt",
                              "cwd": repo, "payload": {"prompt": "fix it"}},
                             env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def test_the_cli_sets_shows_and_clears_the_level(self):
        proc = self.cli("ultra")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "ponytail level: ultra")
        with open(self.level_file()) as fh:
            self.assertEqual(fh.read().strip(), "ultra")
        # the bare call is the query
        self.assertEqual(self.cli().stdout.strip(), "ultra")
        # `full` is the absence of the file, so going back to it removes the state
        self.assertEqual(self.cli("full").stdout.strip(), "ponytail level: full")
        self.assertFalse(os.path.exists(self.level_file()))
        self.assertEqual(self.cli().stdout.strip(), "full")

    def test_an_unknown_level_is_a_usage_error(self):
        proc = self.cli("lazier")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("usage: tezgah-pony", proc.stderr)
        self.assertFalse(os.path.exists(self.level_file()))

    def test_a_non_default_level_rides_the_reminder(self):
        repo = self.make_repo()
        self.assertNotIn("Ponytail level", self.prompt(repo))
        self.cli("lite")
        self.assertIn("Ponytail level: lite - build what's asked", self.prompt(repo))

    def test_every_level_says_what_it_changes(self):
        """The armed line used to name the level and stop ("Ponytail level:
        lite."), leaving what that level changes to a file the session may never
        open. Each level now carries a clause, every clause reads differently,
        and every clause is the skill's own wording rather than a paraphrase."""
        policy, paths = pony_modules()
        lines = {level: policy.pony_level_line(level)
                 for level in paths.PONY_LEVELS}
        self.assertEqual(len(set(lines.values())), len(paths.PONY_LEVELS), lines)
        self.assertEqual(lines["full"], "")   # the default costs no characters
        # a level with no clause would render as the empty line, so the map is
        # exactly the non-default levels: a fourth level fails here
        self.assertEqual(set(policy.PONY_LEVEL_CLAUSES),
                         set(paths.PONY_LEVELS) - {"full"})
        with open(os.path.join(support.REPO, "skills", "ponytail",
                               "SKILL.md")) as fh:
            skill = fh.read().lower()
        for level, clause in policy.PONY_LEVEL_CLAUSES.items():
            self.assertIn(level, lines[level])
            self.assertIn(clause, lines[level])
            self.assertIn(clause.lower(), skill,
                          "%s: the clause is not the skill's own wording" % level)

    def test_a_corrupt_level_file_falls_back_to_the_default(self):
        # an unreadable value must not arm a level nobody chose
        repo = self.make_repo()
        path = self.level_file()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write("turbo\n")
        self.assertNotIn("Ponytail level", self.prompt(repo))
        self.assertEqual(self.cli().stdout.strip(), "full")


class AdhdSwitch(TempHome):
    """`tezgah-adhd off` is what the rule's own text names as its switch, so the
    documented way to turn the rule off has to work, not just the file."""

    CLI = os.path.join(support.REPO, "bin", "tezgah-adhd")

    def cli(self, *args):
        return support.run([self.CLI] + list(args), env=self.env())

    def session(self, repo):
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "context_for", "event": "session_start",
                              "cwd": repo}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def test_off_disarms_the_rule_and_on_arms_it_again(self):
        repo = self.make_repo()
        self.assertIn("**Output shape: ADHD-friendly.**", self.session(repo))
        self.assertEqual(self.cli().stdout.strip(), "on")
        self.assertEqual(self.cli("off").stdout.strip(), "adhd rule: off")
        self.assertEqual(self.cli().stdout.strip(), "off")
        self.assertNotIn("**Output shape: ADHD-friendly.**", self.session(repo))
        self.assertEqual(self.cli("on").stdout.strip(), "adhd rule: on")
        self.assertIn("**Output shape: ADHD-friendly.**", self.session(repo))

    def test_an_unknown_argument_is_a_usage_error(self):
        proc = self.cli("maybe")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("usage: tezgah-adhd", proc.stderr)


class IndexMarkUncompared(TempHome):
    """C10: the `idx` mark may only say fresh when it really compared HEAD to the
    stamp. Both ways the comparison fails - no stamp file (the sandboxed host
    whose hook cannot write one) and an unreadable HEAD - used to fall through to
    the green glyph, and the turn was told nothing, which is the failure the
    stale-graph notice exists to prevent.

    Its own fixture rather than IndexMark's: a subclass would re-run that class's
    three cases against the same setup, and this file already sets each fixture
    up where it is used."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        # a real executable so codegraph_bin() is truthy without a real index
        self.envv = self.env(extra={"TEZGAH_CODEGRAPH_BIN": sys.executable})
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        self.touch(os.path.join(self.repo, "f"))
        subprocess.run(["git", "-C", self.repo, "add", "."], check=True)
        subprocess.run(["git", "-C", self.repo, "-c", "user.email=a@b",
                        "-c", "user.name=t", "commit", "-qm", "x"], check=True)
        # the repo's own index, so the mark has a reason to compare HEAD at all
        slug = support.slug(os.path.realpath(self.repo))
        os.makedirs(os.path.join(self.repo, ".codegraph"), exist_ok=True)
        open(os.path.join(self.repo, ".codegraph", "codegraph.db"), "w").close()
        self.stamp_path = os.path.join(self.home, ".cache", "tezgah", slug)

    def head(self):
        return subprocess.run(["git", "-C", self.repo, "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()

    def stamp(self, sha):
        self.touch(self.stamp_path)
        with open(self.stamp_path, "w") as fh:
            fh.write(sha)

    def mark(self, env=None):
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "health_lines", "cwd": self.repo},
                             env=env or self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out.rsplit("idx", 1)[1]

    def turn(self):
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "context_for", "event": "user_prompt",
                              "cwd": self.repo,
                              "payload": {"session_id": "s",
                                          "prompt": "add a docstring"}},
                             env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def test_a_db_with_no_stamp_is_not_fresh(self):
        # the db is there and HEAD is readable, so it looks indexed - but nobody
        # wrote the stamp, so nothing was compared
        self.assertEqual(self.mark(), "?")

    def test_an_unreadable_head_is_not_fresh(self):
        # a stamp exists, but the comparison needs HEAD and git cannot be run
        self.stamp(self.head())
        env = self.env(extra={"TEZGAH_CODEGRAPH_BIN": sys.executable, "PATH": self.home})
        self.assertEqual(self.mark(env), "?")

    def test_the_turn_says_the_graph_cannot_be_compared(self):
        # silence was the whole bug: the graph answered with the index's
        # authority and the turn that decides from it was told nothing
        out = self.turn()
        self.assertIn("Graph index:", out)
        self.assertIn("unknown", out)


class MergeCarveOut(unittest.TestCase):
    """C11: the contract grants standing merge authority, and a PR merge is a
    write to an external service, so the rule that sends outward-facing actions
    back for an ask has to carve the merge out. Without the carve-out the
    exception swallows the authority stated beside it: the same text both grants
    the merge and demands an ask for it."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, support.HOOKS)
        import tezgah_context as tc  # noqa: E402
        import tezgah_policy as policy  # noqa: E402
        cls.tc, cls.policy = tc, policy

    @staticmethod
    def sentence(text, needle):
        """The sentence carrying `needle`, or "". The claim is made by one
        sentence, and the paragraph it sits in names other rules too."""
        return next((s for s in text.replace("\n", " ").split(". ")
                     if needle in s), "")

    def test_the_always_on_invariant_does_not_ask_for_the_merge(self):
        carries = self.sentence(self.tc.always_on_core(), "external service")
        self.assertTrue(carries, "no sentence names an external-service write")
        self.assertIn("merge", carries)

    def test_the_standing_reminder_does_not_ask_for_the_merge(self):
        carries = self.sentence(self.policy.REMINDER, "external service")
        self.assertTrue(carries, "no sentence names an external-service write")
        self.assertIn("merge", carries)


class SubagentBriefHeader(unittest.TestCase):
    """C12: the brief's own header says every rule below is in force, so the two
    always-on blocks that are not CORE_RULES paragraphs have to ride with it -
    the on-demand-rules pointer and the kill-switch list. A delegate that never
    sees them cannot learn that spec-first, consult, research routing or the
    graph exist, and cannot tell its caller how a rule is switched off."""

    def setUp(self):
        sys.path.insert(0, support.HOOKS)
        import tezgah_context as tc  # noqa: E402
        self.tc = tc
        self.brief = tc.subagent_core()

    def test_the_on_demand_rules_are_named(self):
        for needle in ("On-demand rules", "Spec-first", "second opinion",
                       "OpenResearch", "code graph"):
            self.assertIn(needle, self.brief)

    def test_every_kill_switch_the_always_on_text_names_is_named(self):
        paragraphs = [p for p in self.tc.always_on_core().split("\n\n")
                      if p.startswith("**Kill switches:")]
        self.assertEqual(1, len(paragraphs), paragraphs)
        names = re.findall(r"`([^`]+)`", paragraphs[0])
        self.assertTrue(names, "the kill-switch paragraph names no switch")
        for name in names:
            self.assertIn(name, self.brief)


class LessonsDigestIsTheShownText(ChildCall):
    """C13: the digest's one job is "this fact changed", so it may only move when
    the text the model was shown moves. Each lesson is cut to a bounded line for
    injection, so an edit past that cut changes nothing the model saw - the
    digest covered the untruncated lines and fired on one.

    Its own fixture, and the per-turn turn() as the channel that acts, because
    that is where the wrong "this changed" reaches the model."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        self.touch(os.path.join(self.repo, "f"))
        subprocess.run(["git", "-C", self.repo, "add", "."], check=True)
        subprocess.run(["git", "-C", self.repo, "-c", "user.email=a@b",
                        "-c", "user.name=t", "commit", "-qm", "first"], check=True)

    def lesson(self, tail):
        path = os.path.join(self.repo, ".tezgah", "lessons.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write("y" * 260 + tail + "\n")

    def ledger(self):
        with open(os.path.join(self.repo, ".tezgah", "lessons.md")) as fh:
            return fh.read().strip()

    def shown(self):
        """The lesson block as injected, read through the builder that injects
        it, so "the text the model was shown" is the text compared."""
        return self.child("import json, tezgah_context as tc\n"
                          "print(json.dumps(tc.lessons(%r)))\n" % self.repo)

    def turn(self):
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "context_for", "event": "user_prompt",
                              "cwd": self.repo,
                              "payload": {"session_id": "s1",
                                          "prompt": "add a docstring"}},
                             env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def test_an_edit_past_the_shown_cut_is_not_a_change(self):
        self.lesson("A")
        before, was = self.shown(), self.ledger()
        self.turn()
        self.lesson("B")
        self.assertNotEqual(was, self.ledger())        # the ledger moved
        self.assertEqual(before, self.shown())         # the shown text did not
        self.assertNotIn("State since your last turn", self.turn())


class VersionPrefix(ChildCall):
    """The line opens with tezgah's own name and version, from one reader that
    `bin/tezgah-setup --version` also calls: two readers of one rule drift, and
    the line is the surface every host draws, so a second copy of the number
    would show up as two answers to "which version is this".

    The prefix is a segment like the marks - a host that builds its line from
    `--json` (opencode's TUI, dsh's client) draws its own line and would
    otherwise miss it - but it is not a mark: nothing is armed or used by it, so
    it carries no glyph and the state that says exactly that."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()

    def line(self):
        out, proc = run_json([support.PROBE_CONTEXT],
                             {"fn": "health_lines", "cwd": self.repo,
                              "session_id": "s"}, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def head(self):
        """The line's first chip: the prefix, separated from the marks the way
        the groups are."""
        return self.line().split("  \u00b7  ")[0]

    def test_the_line_opens_with_the_name_and_the_version(self):
        self.assertEqual(self.head(), "tezgah v" + changelog_version())

    def test_the_version_is_the_one_the_installer_prints(self):
        # one definition, not two: a release moves the changelog and both prints
        # with it, and a reader left behind in the installer fails here
        proc = subprocess.run([sys.executable, SETUP, "--version"],
                              capture_output=True, text=True, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), changelog_version())
        self.assertEqual(self.head(), "tezgah v" + proc.stdout.strip())

    def test_the_json_form_carries_the_version_a_program_reads(self):
        # `--json` is the shape the host plugins consume, so the value has to be
        # a field there and not only a chip in the rendered string
        proc = subprocess.run([sys.executable, STATUS, self.repo, "s", "--json"],
                              capture_output=True, text=True, env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        segs = json.loads(proc.stdout)
        self.assertEqual(segs[0]["key"], "tezgah")
        self.assertEqual(segs[0]["version"], changelog_version())
        self.assertEqual(segs[0]["text"], "tezgah v" + changelog_version())
        # not a mark: no glyph, and the state that reports none
        self.assertEqual((segs[0]["state"], segs[0]["glyph"]), ("info", ""))
        # the marks still follow it, and still start where they always started
        self.assertEqual([s["key"] for s in segs[1:]][:3],
                         ["pony", "exec", "adhd"])

    def test_a_checkout_with_no_readable_version_prints_the_bare_name(self):
        """Not a placeholder: `vNone` on the line would be a version the reader
        invented. The mark half is what must not move, so the same segments are
        rendered with the version unreadable and without it."""
        out = self.child(
            "import json, tezgah_context as tc\n"
            "tc.PLUGIN_ROOT = %r\n"
            "segs = tc.health_segments(%r, 's')\n"
            "head = tc.version_segment()\n"
            "marks = tc.render_line(segs[1:])\n"
            "print(json.dumps({'raw': tc.version(), 'head': head,\n"
            "                  'marks': marks,\n"
            "                  'line': tc.render_line([head] + segs[1:])}))\n"
            % (self.home, self.repo))
        self.assertIsNone(out["raw"])
        self.assertEqual((out["head"]["text"], out["head"]["version"]),
                         ("tezgah", None))
        self.assertNotIn("None", out["line"])
        self.assertEqual(out["line"], "tezgah  \u00b7  " + out["marks"])


STATUS = os.path.join(support.REPO, "bin", "tezgah-status")
SETUP = os.path.join(support.REPO, "bin", "tezgah-setup")


def changelog_version():
    """The newest release heading in CHANGELOG.md, read the way the reader reads
    it - the first `## [x.y.z]` in the file - so a release moves the test with
    the code instead of leaving a number behind that the next one fails on.

    Defined at the foot, with PREFIX beside it: the classes above cite nothing,
    but `docs/` cites this file by line, and a helper inserted at the top would
    move every one of those numbers."""
    with open(os.path.join(support.REPO, "CHANGELOG.md"), encoding="utf-8") as fh:
        return re.search(r"^## \[(\d+\.\d+\.\d+)\]", fh.read(), re.M).group(1)


# The line's first chip and the separator after it: the product's own name and
# version, which the exact-line assertions above carry ahead of the marks.
PREFIX = "tezgah v%s  \u00b7  " % changelog_version()


def pony_modules():
    """`hooks/tezgah_policy` and `hooks/tezgah_paths`: the rule's text and the
    level it stores.

    Imported here rather than at the top for the reason `changelog_version`
    states: `docs/` cites this file's early lines by number, and two import lines
    at the top would move every one of them."""
    sys.path.insert(0, support.HOOKS)
    import tezgah_paths
    import tezgah_policy
    return tezgah_policy, tezgah_paths


class Ladder(unittest.TestCase):
    """The ponytail ladder is written in three places - the skill's `## The
    ladder`, the always-on `PONYTAIL` text and the per-turn `CORE` paragraph -
    and nothing held them to each other. Every rung is matched in order in every
    copy, so a copy that drops a rung, or names two of them the other way round,
    fails here."""

    # One marker per rung, in the order the ladder claims, in the words all three
    # copies use for it. The search is sequential, so an earlier mention of the
    # same words is stepped over rather than matched: the skill's rung 1 says
    # "say so in one line" long before rung 6 is the one about one line.
    RUNGS = (("YAGNI", "yagni"),
             ("reuse", "reuse"),
             ("stdlib", "stdlib"),
             ("native platform", "native platform"),
             ("dependency", "dependency"),
             ("one line", "one line"),
             ("minimum code", "minimum code"))

    def copies(self):
        policy, _paths = pony_modules()
        with open(os.path.join(support.REPO, "skills", "ponytail",
                               "SKILL.md")) as fh:
            skill = fh.read()
        return {"skill": skill, "PONYTAIL (armed text)": policy.PONYTAIL,
                "CORE (per-turn paragraph)": policy.CORE}

    def test_all_three_copies_name_the_rungs_in_the_same_order(self):
        for name, text in self.copies().items():
            lowered = text.lower()
            at = -1
            for rung, marker in self.RUNGS:
                found = lowered.find(marker, at + 1)
                self.assertGreater(found, at, "%s: the %s rung is missing or out "
                                              "of order" % (name, rung))
                at = found


if __name__ == "__main__":
    unittest.main()
