"""hooks/tezgah_paths.py: roots precedence, root_for boundaries, kill switches."""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import unittest
from unittest import mock

import support
from support import TempHome, run_json

sys.path.insert(0, support.HOOKS)
import tezgah_paths as tp  # noqa: E402


class RootsPrecedence(TempHome):
    def test_env_overrides_config_and_default(self):
        # distinct lengths => deterministic longest-first ordering
        a = os.path.join(self.home, "root-alpha-long")
        b = os.path.join(self.home, "b")
        os.makedirs(a)
        os.makedirs(b)
        self.config({"roots": [os.path.join(self.home, "from-config")]})
        out, proc = run_json([support.PROBE_PATHS, "roots"],
                             env=self.env(roots=[b, a]))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out, [os.path.realpath(a), os.path.realpath(b)])

    def test_config_used_when_no_env(self):
        cfg_root = os.path.join(self.home, "from-config")
        os.makedirs(cfg_root)
        self.config({"roots": [cfg_root]})
        env = self.env()
        env.pop("TEZGAH_ROOTS", None)
        out, proc = run_json([support.PROBE_PATHS, "roots"], env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out, [os.path.realpath(cfg_root)])

    def test_default_when_nothing_configured(self):
        env = self.env()
        env.pop("TEZGAH_ROOTS", None)
        out, proc = run_json([support.PROBE_PATHS, "roots"], env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out, [os.path.realpath(os.path.join(self.home, "Projects"))])


class RootForBoundaries(TempHome):
    def test_inside_and_exact_return_root(self):
        repo = self.make_repo("proj")
        sub = os.path.join(repo, "pkg", "deep")
        os.makedirs(sub)
        for path in (repo, sub):
            out, proc = run_json([support.PROBE_PATHS, "root_for", path],
                                 env=self.env())
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(out, self.roots, "for %s" % path)

    def test_common_prefix_sibling_is_not_inside(self):
        self.make_repo("proj")
        sibling = os.path.join(self.home, "Projects2")
        os.makedirs(sibling)
        out, _ = run_json([support.PROBE_PATHS, "root_for", sibling],
                          env=self.env())
        self.assertIsNone(out)

    def test_outside_is_none(self):
        out, _ = run_json([support.PROBE_PATHS, "root_for", self.home],
                          env=self.env())
        self.assertIsNone(out)


class KillSwitches(TempHome):
    def test_off_by_default(self):
        out, proc = run_json([support.PROBE_PATHS, "off", "reminder-off"],
                             env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(out)

    def test_canonical_config_dir(self):
        self.touch(os.path.join(self.home, ".config", "tezgah", "pretooluse-off"))
        out, _ = run_json([support.PROBE_PATHS, "off", "pretooluse-off"],
                          env=self.env())
        self.assertTrue(out)

    def test_legacy_claude_dir(self):
        self.touch(os.path.join(self.home, ".claude", "reminder-off"))
        out, _ = run_json([support.PROBE_PATHS, "off", "reminder-off"],
                          env=self.env())
        self.assertTrue(out)


class CacheDirFallback(TempHome):
    """cache_dir() must hand back a writable dir even when the global cache is
    denied (the sandboxed-host case, simulated by a file in the dir's place)."""

    def test_global_cache_when_writable(self):
        out, proc = run_json([support.PROBE_PATHS, "cache_dir"], env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out, os.path.join(self.home, ".cache", "tezgah"))

    def test_fallback_when_global_cache_is_unwritable(self):
        path = os.path.join(self.home, ".cache", "tezgah")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").close()
        fallback = os.path.join(self.home, "fallback")
        env = self.env(extra={"TEZGAH_FALLBACK_CACHE": fallback})
        out, proc = run_json([support.PROBE_PATHS, "cache_dir"], env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out, fallback)


class ConcurrentProbe(TempHome):
    """Probes of one dir that overlap in time must all see it writable.

    The interleaving is forced, not left to luck: the module's `open` is wrapped
    so every probe holds the file it has just created in the probed dir until its
    siblings have created theirs too - all creates before any remove, the order
    in which a probe that reuses one filename loses that file to a sibling and
    reads the dir as unwritable, moving one session's ledger to the temp
    fallback. The hook keys on the directory, so it assumes nothing about how a
    probe names its file.

    `writable_dir` is the unit under test: cache_dir() folds its result into a
    memo, which would hide a per-round race after the first round."""

    PROBES = 8
    ROUNDS = 5

    def setUp(self):
        super().setUp()
        self.cache = os.path.join(self.home, ".cache", "tezgah")
        self.fallback = os.path.join(self.home, "fallback")
        os.makedirs(self.cache)
        patch = mock.patch.multiple(tp, CACHE=self.cache,
                                    fallback_cache=lambda: self.fallback)
        patch.start()
        self.addCleanup(patch.stop)

    def probe_together(self, call, count):
        """One round of `count` probes held at their create; (got, errors)."""
        both = threading.Barrier(count)
        real_open = open

        def hooked(path, *a, **kw):
            fh = real_open(path, *a, **kw)
            if os.path.dirname(str(path)) == self.cache:
                # the file exists now; hold here so no probe removes before a
                # sibling has created its own
                both.wait(timeout=10)
            return fh

        got, errors = [], []

        def run():
            try:
                got.append(call())
            except Exception as exc:  # a probe that raises is a failure too
                errors.append(exc)

        with mock.patch.object(tp, "open", hooked, create=True):
            threads = [threading.Thread(target=run) for _ in range(count)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(20)
        return got, errors

    def test_overlapping_probes_all_see_the_dir_writable(self):
        for round_no in range(self.ROUNDS):
            got, errors = self.probe_together(
                lambda: tp.writable_dir(self.cache), self.PROBES)
            self.assertEqual(errors, [], "round %d" % round_no)
            self.assertEqual(got, [True] * self.PROBES, "round %d" % round_no)

    def test_overlapping_probes_all_pick_the_global_cache(self):
        got, errors = self.probe_together(tp.cache_dir, 4)
        self.assertEqual(errors, [])
        self.assertEqual(got, [self.cache] * 4)

    def test_the_answer_does_not_move_when_a_later_probe_fails(self):
        self.assertEqual(tp.cache_dir(), self.cache)
        shutil.rmtree(self.cache)
        open(self.cache, "w").close()  # writable at first call, denied after
        self.assertEqual(tp.cache_dir(), self.cache)


class ConsultKey(TempHome):
    """A DeepSeek-only setup counts as having a consult key, since both consult
    and codegen accept --provider deepseek."""

    def test_deepseek_key_file_counts(self):
        p = os.path.join(self.home, ".config", "deepseek", "key")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").close()
        out, proc = run_json([support.PROBE_PATHS, "have_consult_key"],
                             env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(out)

    def test_inception_key_file_counts(self):
        p = os.path.join(self.home, ".config", "inception", "key")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").close()
        out, proc = run_json([support.PROBE_PATHS, "have_consult_key"],
                             env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(out)

    def test_no_key_is_false(self):
        out, _ = run_json([support.PROBE_PATHS, "have_consult_key"],
                          env=self.env())
        self.assertFalse(out)


class TypeSafeKey(TempHome):
    """omp spends TYPESAFE_API_KEY on its System One judgments (`judge()`, auto
    thinking, unexpected-stop, AI staging) and falls back to a chat model
    without it, so `have_typesafe_key()` counts exactly the two places omp
    resolves it from: the env var, and its own login store. tezgah's own seam
    answers a different question over a different channel set - see `JudgeKey`."""

    def login_store(self, provider="typesafe"):
        p = os.path.join(self.home, ".omp", "agent", "agent.db")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        conn = sqlite3.connect(p)
        conn.execute("create table auth_credentials (provider text)")
        conn.execute("insert into auth_credentials values (?)", (provider,))
        conn.commit()
        conn.close()

    def test_login_store_counts(self):
        self.login_store()
        out, proc = run_json([support.PROBE_PATHS, "have_typesafe_key"],
                             env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(out)

    def test_env_counts(self):
        out, proc = run_json([support.PROBE_PATHS, "have_typesafe_key"],
                             env=self.env(extra={"TYPESAFE_API_KEY": "test"}))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(out)

    def test_a_key_file_alone_is_not_enough(self):
        # omp never opens ~/.config/typesafe/key: a file with no export and no
        # login record means omp reads the fallback chat model, which is the
        # failure the row exists to expose. The seam does open it, which is why
        # its own row exists (JudgeKey.test_the_key_file_alone_serves_the_seam).
        p = os.path.join(self.home, ".config", "typesafe", "key")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").close()
        out, _ = run_json([support.PROBE_PATHS, "have_typesafe_key"],
                          env=self.env())
        self.assertFalse(out)

    def test_no_key_is_false(self):
        out, _ = run_json([support.PROBE_PATHS, "have_typesafe_key"],
                          env=self.env())
        self.assertFalse(out)


class JudgeKey(TempHome):
    """`have_judge_key()` is the seam's own channel: the env var, else the key
    file `hooks/tezgah_judge.key()` reads, which is what tezgah-triage,
    tezgah-docs and the skill picker spend. It is not omp's channel, and the
    installer's report carried one answer under both questions until a measured
    divergence showed in the file-only shape: omp on its fallback chat model,
    the seam working. Every case asserts both booleans, so the two definitions
    cannot drift apart again in either direction."""

    # Both modules under the throwaway HOME in one process: 'path' is the
    # paths-side predicate, the rest is the seam's own answer.
    PROBE = (
        "import json, sys\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "import tezgah_paths as tp\n"
        "import tezgah_judge as tj\n"
        "sys.stdout.write(json.dumps({'path': tp.have_judge_key(),\n"
        "  'omp': tp.have_typesafe_key(), 'seam': bool(tj.key()),\n"
        "  'provider': tj.credential()[0],\n"
        "  'available': tj.available()}))\n"
    )

    def answers(self, extra=None):
        proc = subprocess.run([sys.executable, "-c", self.PROBE, support.HOOKS],
                              capture_output=True, text=True, timeout=60,
                              env=self.env(extra=extra))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout.strip().splitlines()[-1])

    def key_file(self, content="k\n"):
        p = os.path.join(self.home, ".config", "typesafe", "key")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as fh:
            fh.write(content)

    def omp_login_store(self):
        p = os.path.join(self.home, ".omp", "agent", "agent.db")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        conn = sqlite3.connect(p)
        conn.execute("create table auth_credentials (provider text)")
        conn.execute("insert into auth_credentials values ('typesafe')")
        conn.commit()
        conn.close()

    def test_env_alone_serves_both_channels(self):
        got = self.answers(extra={"TYPESAFE_API_KEY": "test"})
        self.assertTrue(got["path"], got)
        self.assertTrue(got["omp"], got)
        self.assertTrue(got["seam"], got)
        self.assertTrue(got["available"], got)

    def test_the_key_file_alone_serves_the_seam(self):
        # The divergence this class pins: it was measured as have_typesafe_key()
        # False while hooks/tezgah_judge.available() was True, so the installer's
        # single row could tell a maintainer a working judgement path was broken.
        self.key_file()
        got = self.answers()
        self.assertTrue(got["path"], got)
        self.assertTrue(got["seam"], got)
        self.assertTrue(got["available"], got)
        self.assertFalse(got["omp"], got)

    def test_the_omp_store_alone_serves_omp_only(self):
        # The mirror image, and the reason the seam's row cannot just widen
        # have_typesafe_key(): a login-store record is a path the seam never opens.
        self.omp_login_store()
        got = self.answers()
        self.assertFalse(got["path"], got)
        self.assertFalse(got["seam"], got)
        self.assertFalse(got["available"], got)
        self.assertTrue(got["omp"], got)

    def test_a_blank_file_is_not_a_credential(self):
        # The seam strips the file and falls back to None, so a whitespace-only
        # file must not read as a key on either side.
        self.key_file("  \n")
        got = self.answers()
        self.assertFalse(got["path"], got)
        self.assertFalse(got["seam"], got)
        self.assertFalse(got["available"], got)

    def test_nothing_resolvable_reads_false_everywhere(self):
        self.assertEqual(self.answers(),
                         {"path": False, "omp": False, "seam": False,
                          "provider": None, "available": False})

    def test_an_openrouter_key_alone_serves_the_seam_through_the_fallback(self):
        # The second provider's env channel. `seam` stays False because it asks
        # the TypeSafe channel specifically, which is the distinction the two
        # questions are kept apart for; `path` and `available` follow the seam,
        # so a machine holding only an OpenRouter key still has a judge.
        got = self.answers(extra={"OPENROUTER_API_KEY": "or"})
        self.assertTrue(got["path"], got)
        self.assertTrue(got["available"], got)
        self.assertEqual(got["provider"], "openrouter")
        self.assertFalse(got["seam"], got)
        self.assertFalse(got["omp"], got)

    def test_the_fallback_key_file_alone_serves_the_seam_too(self):
        path = os.path.join(self.home, ".config", "openrouter", "key")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write("or-file\n")
        got = self.answers()
        self.assertTrue(got["path"], got)
        self.assertTrue(got["available"], got)
        self.assertEqual(got["provider"], "openrouter")
        self.assertFalse(got["omp"], got)

    def test_a_type_safe_key_still_picks_the_type_safe_provider(self):
        self.key_file()
        got = self.answers(extra={"OPENROUTER_API_KEY": "or"})
        self.assertEqual(got["provider"], "typesafe")


class UserBinFallback(TempHome):
    """A tool installed to a per-user bin dir must read as present even when the
    calling shell's PATH never picked it up (the non-interactive case)."""

    def install(self, rel, name):
        p = os.path.join(self.home, *rel, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as fh:
            fh.write("#!/bin/sh\n")
        os.chmod(p, 0o755)
        return p

    def empty_path(self):
        d = os.path.join(self.home, "emptybin")
        os.makedirs(d, exist_ok=True)
        return {"PATH": d}

    def test_which_user_finds_cargo_bin_off_path(self):
        want = self.install((".cargo", "bin"), "orx")
        out, proc = run_json([support.PROBE_PATHS, "which_user", "orx"],
                             env=self.env(extra=self.empty_path()))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out, want)

    def test_orx_bin_uses_the_fallback(self):
        want = self.install((".local", "bin"), "orx")
        env = self.env(extra=self.empty_path())
        env.pop("TEZGAH_ORX_BIN", None)  # let orx_bin() do the lookup itself
        out, proc = run_json([support.PROBE_PATHS, "orx_bin"], env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out, want)

    def test_missing_tool_is_none(self):
        out, _ = run_json([support.PROBE_PATHS, "which_user", "nope"],
                          env=self.env(extra=self.empty_path()))
        self.assertIsNone(out)


class CodegraphBin(TempHome):
    """`codegraph_bin()` is the one resolver for the graph engine.

    Three callers read it - the auto-index worker, the graph paragraph the
    context injects, and the agent-ability gate - and the retired
    codebase-memory-mcp resolver had the same three channels, so the cases pin
    the pin, the config file and the miss. The binaries are real executable files
    in the throwaway HOME, because `which_user()` refuses a path that is not one,
    and a case passing a made-up path would pin a resolution the product never
    performs."""

    def binary(self, name):
        path = os.path.join(self.home, name)
        with open(path, "w") as fh:
            fh.write("#!/bin/sh\n")
        os.chmod(path, 0o755)
        return path

    def resolved(self, extra=None):
        out, proc = run_json([support.PROBE_PATHS, "codegraph_bin"],
                             env=self.env(extra=extra))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def test_the_pin_decides_the_path(self):
        codegraph = self.binary("codegraph-fake")
        self.assertEqual(self.resolved({"TEZGAH_CODEGRAPH_BIN": codegraph}),
                         codegraph)

    def test_the_config_file_decides_it_too(self):
        codegraph = self.binary("codegraph-fake")
        self.config({"codegraph_bin": codegraph})
        # The fixture's base env pins the variable at a path that does not exist
        # so this machine's own binary cannot leak in; an empty pin is what makes
        # the config file the channel under test rather than the env.
        self.assertEqual(self.resolved({"TEZGAH_CODEGRAPH_BIN": ""}), codegraph)

    def test_the_pin_wins_over_the_config(self):
        pinned = self.binary("pinned-fake")
        self.config({"codegraph_bin": self.binary("configured-fake")})
        self.assertEqual(self.resolved({"TEZGAH_CODEGRAPH_BIN": pinned}), pinned)

    def test_no_install_resolves_to_none(self):
        # The state the graph paragraph and the agent-ability gate both read: no
        # binary means no graph claim, never a guessed path.
        self.assertIsNone(self.resolved())


if __name__ == "__main__":
    unittest.main()
