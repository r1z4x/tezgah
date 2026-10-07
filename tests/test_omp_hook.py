"""hosts/omp/hook.py: the omp lifecycle envelope over the shared core.

omp's extension API is TypeScript, so the python half takes one JSON payload and
answers with one JSON object (hosts/omp/hook.py's docstring is the protocol).
These tests drive that protocol directly: they are the only host-level check
that omp's session context, gate, evidence ledger and Stop rule behave.
"""
import glob
import json
import os
import shutil
import unittest

import support
from support import TempHome, run, run_json


class OmpHook(TempHome):
    def event(self, payload, env=None):
        return run_json([support.OMP_HOOK], payload, env=env or self.env())

    def kinds(self, session):
        """The used kinds this session's ledger recorded, in order."""
        path = os.path.join(self.home, ".cache", "tezgah", "sessions",
                            support.slug(session) + ".jsonl")
        try:
            with open(path) as fh:
                return [json.loads(line)["kind"] for line in fh if line.strip()]
        except OSError:
            return []

    def indexed(self, repo):
        """Make the fixture repo's idx mark resolvable: the repo's own index db,
        and a code graph binary, so the probe is not short-circuited and really
        forks git.

        Resolvable is not fresh: no stamp is written and the fixture is not a git
        repository, so the mark these two tests probe for is the honest "?" - the
        comparison cannot be made - rather than the old silent fresh."""
        d = os.path.join(repo, ".codegraph")
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "codegraph.db"), "w").close()
        shim = os.path.join(self.home, "codegraph-shim")
        with open(shim, "w") as fh:
            fh.write("#!/bin/sh\nexit 1\n")
        os.chmod(shim, 0o755)
        return shim

    def counting_env(self, shim):
        """An env whose PATH has a `git` in front of the real one that logs every
        fork, so "the redraw forked nothing" is measured rather than assumed."""
        d = os.path.join(self.home, "bin")
        os.makedirs(d, exist_ok=True)
        log = os.path.join(self.home, "git.log")
        with open(os.path.join(d, "git"), "w") as fh:
            fh.write("#!/bin/sh\necho \"$@\" >> %s\nexec %s \"$@\"\n"
                     % (log, shutil.which("git") or "/usr/bin/git"))
        os.chmod(os.path.join(d, "git"), 0o755)
        return log, self.env(extra={
            "PATH": os.pathsep.join([d, os.environ.get("PATH", "")]),
            "TEZGAH_CODEGRAPH_BIN": shim})

    def forks(self, log):
        try:
            with open(log) as fh:
                return len([line for line in fh if line.strip()])
        except OSError:
            return 0

    def test_a_mention_of_a_tool_is_not_a_use_of_it(self):
        # the audit found the line claiming a consult the session never ran:
        # `consult` in the argument was enough to flip the mark
        repo = self.make_repo()
        cases = [
            ("grep -n consult hooks/ | head", None),
            ("ls -la /Users/x/.cargo/bin/orx", None),
            ('git commit -m "consult ran, and orx too"', None),
            ("~/.config/tezgah/bin/consult \"is this safe?\"", "consult"),
            ("orx run --project p", "research"),
            ("cd /tmp && sudo env X=1 consult --online q", "consult"),
        ]
        for cmd, kind in cases:
            session = support.slug(cmd)
            _out, proc = self.event(
                {"event": "post_tool_use", "cwd": repo, "session_id": session,
                 "tool": "bash", "input": {"command": cmd}})
            self.assertEqual(proc.returncode, 0, proc.stderr)
            # the ledger also carries a null kind per call; the marks read the
            # four names, so only those are the claim under test
            kinds = [k for k in self.kinds(session) if k]
            self.assertEqual(kinds, [] if kind is None else [kind], cmd)

    def test_a_scratch_write_outside_the_root_does_not_stale_a_passing_check(self):
        # omp never handed its cwd to the evidence writer, so the root boundary
        # that keeps a scratch file out of the freshness fold never applied: a
        # throwaway script in the temp dir after a green suite read as a new
        # revision and the reply reporting that suite was refused
        repo = self.make_repo()
        scratch = os.path.join(self.home, "smoke.py")
        base = {"cwd": repo, "session_id": "fresh"}
        self.event(dict(base, event="post_tool_use", tool="bash", failed=False,
                        result_len=12,
                        input={"command": "python3 -m unittest discover -s tests"}))
        write = {"file_path": scratch, "content": "print(1)\n"}
        self.event(dict(base, event="pre_tool_use", tool="write", input=write))
        with open(scratch, "w") as fh:
            fh.write("print(1)\n")
        self.event(dict(base, event="post_tool_use", tool="write", input=write,
                        failed=False))
        out, proc = self.event(dict(base, event="stop",
                                    last_assistant_message="Done: the suite passed."))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("Stale evidence", str((out or {}).get("reason")))
        # a write inside the repo is still a new revision
        inside = os.path.join(repo, "app.py")
        write = {"file_path": inside, "content": "x = 1\n"}
        self.event(dict(base, event="pre_tool_use", tool="write", input=write))
        with open(inside, "w") as fh:
            fh.write("x = 1\n")
        self.event(dict(base, event="post_tool_use", tool="write", input=write,
                        failed=False))
        out, _ = self.event(dict(base, event="stop",
                                 last_assistant_message="Done: the suite passed."))
        self.assertIn("Stale evidence", str((out or {}).get("reason")))

    def test_a_watched_tool_result_forks_no_git(self):
        # the idx mark is the only thing on the line that costs a subprocess, and
        # the session hands back the glyph the probed answer carried, so a busy
        # turn stops paying two git forks per watched tool
        repo = self.make_repo()
        log, env = self.counting_env(self.indexed(repo))
        payload = {"event": "post_tool_use", "cwd": repo, "session_id": "s",
                   "tool": "bash", "input": {"command": "pytest -q"},
                   "idx": "\u2713"}
        before = self.forks(log)
        for _ in range(3):
            out, proc = self.event(payload, env=env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.forks(log) - before, 0)
        # the line still carries the mark, and the glyph the next redraw uses
        self.assertIn("idx\u2713", out["status"])
        self.assertEqual(out["idx"], "\u2713")
        # without a glyph the same event has to ask - which is what makes the
        # zero above a saving and not a probe that never happens
        before = self.forks(log)
        probed, _ = self.event({k: v for k, v in payload.items() if k != "idx"},
                               env=env)
        self.assertGreater(self.forks(log) - before, 0)
        # the fixture has an index db and writes no stamp over a directory that is
        # not a git repo, so the probe's honest answer is "cannot compare": the
        # point of this half is that it asked at all, not which glyph came back
        self.assertIn("idx?", probed["status"])

    def test_the_turn_boundary_still_probes_the_mark(self):
        # turn_end is where the line is read, so the glyph never stands in for
        # the probe there, and the answer hands the fresh glyph back for the
        # redraws in between
        repo = self.make_repo()
        log, env = self.counting_env(self.indexed(repo))
        before = self.forks(log)
        out, proc = self.event({"event": "status", "cwd": repo,
                                "session_id": "s", "idx": "\u2013"}, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertGreater(self.forks(log) - before, 0)
        self.assertIn("idx?", out["status"])   # the probe's answer, not "–"
        self.assertEqual(out["idx"], "?")

    def test_session_start_carries_repo_state_without_the_core(self):
        repo = self.make_repo()
        out, proc = self.event({"event": "session_start", "cwd": repo,
                                "session_id": "s"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Graph", out["context"])
        # omp's managed RULES.md already carries the always-on core, so the
        # session payload must not pay for the contract a second time
        self.assertNotIn("**Turkish, BLUF.**", out["context"])
        self.assertIn("\033[33m\u2702 pony\u25cb\033[0m", out["status"])

    def test_post_compact_re_sends_the_state_and_records_the_compaction(self):
        # Audit L-3 (INT-06): the bridge's session_compact asks for this event;
        # the answer is the live state without the core, and the summary is
        # counted the way Claude's PostCompact is (size and digest, no text).
        repo = self.make_repo()
        plans = os.path.join(repo, ".tezgah", "plans", "open")
        os.makedirs(plans)
        with open(os.path.join(plans, "001-x.md"), "w") as fh:
            fh.write("---\nid: 001\ntitle: compact plan\n---\n")
        out, proc = self.event({"event": "post_compact", "cwd": repo,
                                "session_id": "s-compact",
                                "compact_summary": "summary text"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("compact plan", out["context"])
        self.assertIn("Graph", out["context"])
        self.assertNotIn("**Turkish, BLUF.**", out["context"])
        rows, _ = run_json([support.PROBE_INTEGRITY],
                           {"fn": "events", "session": "s-compact"},
                           env=self.env())
        row = next(r for r in rows if r["kind"] == "compact")
        self.assertEqual(row["summary_chars"], len("summary text"))
        self.assertNotIn("summary text", json.dumps(rows))

    def test_a_subagent_gets_the_brief_not_the_parents_payload(self):
        # a fan-out of task subagents each got the main payload: the indexer,
        # the agent regeneration and the "run plan-status first" line
        repo = self.make_repo()
        plans = os.path.join(repo, ".tezgah", "plans", "open")
        os.makedirs(plans)
        with open(os.path.join(plans, "001-x.md"), "w") as fh:
            fh.write("---\nid: 001\ntitle: x\n---\n## Next\ndo it\n")
        main, _ = self.event({"event": "session_start", "cwd": repo,
                              "session_id": "s"})
        sub, proc = self.event({"event": "session_start", "cwd": repo,
                                "session_id": "t", "subagent": True})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("plan-status", main["context"])
        self.assertNotIn("plan-status", sub["context"])
        self.assertIn("You are a subagent", sub["context"])
        self.assertNotIn("You are a subagent", main["context"])

    def test_a_subagent_s_ledger_opens_with_its_parent(self):
        # the route report finds a routed worker's checks through this row: the
        # worker's rows land in its own ledger, the route row in the parent's
        repo = self.make_repo()
        _, proc = self.event({"event": "session_start", "cwd": repo, "session_id": "t",
                              "subagent": True, "parent": "s", "agent": "Scout"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.event({"event": "session_start", "cwd": repo, "session_id": "m"})
        rows = {sid: run_json([support.PROBE_INTEGRITY], {"fn": "events", "session": sid},
                              env=self.env())[0] for sid in ("t", "m")}
        spawned = [r for r in rows["t"] if r["kind"] == "spawned"]
        self.assertEqual([(r["parent"], r["agent"]) for r in spawned], [("s", "Scout")])
        self.assertEqual([r for r in rows["m"] if r["kind"] == "spawned"], [])

    def test_a_task_call_records_which_agent_each_named_child_runs(self):
        # omp names a child's ledger by its task name, not its agent type; the
        # parent's task call is the one place both are known together
        repo = self.make_repo()
        tasks = {"tasks": [{"name": "Fix", "agent": "tezgah-cheap", "task": "x"},
                           {"name": "Look", "task": "y"},  # no agent: omp's `task`
                           {"agent": "scout", "task": "z"}]}  # no name: not joinable
        _, proc = self.event({"event": "post_tool_use", "cwd": repo, "session_id": "s",
                              "tool": "task", "input": tasks, "failed": False})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rows, _ = run_json([support.PROBE_INTEGRITY], {"fn": "events", "session": "s"},
                           env=self.env())
        self.assertEqual([(r["child"], r["agent"]) for r in rows if r["kind"] == "spawn"],
                         [("Fix", "tezgah-cheap"), ("Look", "task")])

    def test_session_start_names_the_specialists_omp_has(self):
        repo = self.make_repo()
        start = {"event": "session_start", "cwd": repo, "session_id": "s"}
        out, _ = self.event(start)
        self.assertNotIn("tezgah-reviewer", out["context"])
        agents = os.path.join(self.home, ".omp", "agent", "agents")
        os.makedirs(agents)
        # a retired role's file left behind by an older install is never named
        for name in ("tezgah-reviewer", "tezgah-orchestrator", "tezgah-explorer",
                     "tezgah-verifier", "tezgah-researcher"):
            open(os.path.join(agents, name + ".md"), "w").close()
        out, _ = self.event(start)
        self.assertIn("-> tezgah-reviewer", out["context"])
        for retired in ("tezgah-explorer", "tezgah-verifier", "tezgah-researcher"):
            self.assertNotIn(retired, out["context"])
        # only the files that exist: no tier worker was installed
        self.assertNotIn("tezgah-cheap", out["context"])
        # a repo's .no-graph turns the graph off there, so its role is not named
        self.touch(os.path.join(repo, ".no-graph"))
        out, _ = self.event(start)
        self.assertNotIn("-> tezgah-reviewer", out["context"])
        os.remove(os.path.join(repo, ".no-graph"))
        self.touch(os.path.join(self.home, ".config", "tezgah", "orchestrate-off"))
        out, _ = self.event(start)
        self.assertNotIn("-> tezgah-reviewer", out["context"])

    def test_status_answers_off_root(self):
        # the status line is the one global signal: tezgah loads as a globally
        # loaded rules file on omp, so the marks must not go silent off-root
        out, proc = self.event({"event": "status", "cwd": self.home})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("\033[33m\u2702 pony\u25cb\033[0m", out["status"])
        # the widget picks by width at draw time, so the answer carries every
        # tier, widest first, the first being the line itself
        self.assertEqual(out["tiers"][0][0], out["status"])
        widths = [w for _, w in out["tiers"]]
        self.assertEqual(widths, sorted(widths, reverse=True))
        self.assertGreater(widths[0], widths[-1])

    def test_the_logo_is_the_half_block_mark_on_every_terminal(self):
        # the inline-image logo was dropped for the half-block one: no terminal,
        # not even one that reads OSC 1337, gets an image escape in the line
        for term in ("Orca", "iTerm.app", "WezTerm", "Apple_Terminal"):
            out, proc = run_json([support.OMP_HOOK],
                                 {"event": "status", "cwd": self.home},
                                 env=self.env(extra={"TERM_PROGRAM": term}))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("\033]1337", out["status"], term)
            self.assertTrue(out["status"].startswith("\033[38;2;255;197;92m\u2580"), term)

    def test_status_drops_color_when_the_environment_opts_out(self):
        # NO_COLOR must strip the escapes at the source, so a terminal that
        # asked for none cannot end up showing them literally
        out, proc = run_json([support.OMP_HOOK],
                             {"event": "status", "cwd": self.home},
                             env=self.env(extra={"NO_COLOR": "1"}))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("\033", out["status"])
        self.assertIn("pony\u25cb", out["status"])

    def test_session_context_is_inert_off_root(self):
        out, proc = self.event({"event": "session_start", "cwd": self.home})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNone(out)  # an empty answer, not an empty object

    def test_user_prompt_carries_the_reminder_and_arms_by_task_class(self):
        repo = self.make_repo()
        out, proc = self.event({"event": "user_prompt", "cwd": repo,
                                "session_id": "s",
                                "prompt": "who calls calc_total?"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("<harness-reminder>", out["context"])
        # the matching conditional paragraph rides only this turn
        self.assertIn("**Code discovery: graph first.**", out["context"])
        other, _ = self.event({"event": "user_prompt", "cwd": repo,
                               "session_id": "s", "prompt": "add a flag"})
        self.assertNotIn("**Code discovery: graph first.**", other["context"])

    def test_pre_tool_use_denies_the_attribution_credit(self):
        repo = self.make_repo()
        out, _ = self.event({
            "event": "pre_tool_use", "cwd": repo, "session_id": "s",
            "tool": "bash",
            "input": {"command": 'git commit -m "x\n\nCo-Authored-By: Claude"'}})
        self.assertIn("attribution", out["deny"].lower())

    def test_pre_tool_use_denies_the_grep_only_explorer(self):
        repo = self.make_repo()
        out, _ = self.event({"event": "pre_tool_use", "cwd": repo,
                             "session_id": "s", "tool": "task",
                             "input": {"subagent_type": "explore"}})
        self.assertTrue(out["deny"].strip())

    def test_pre_tool_use_passes_an_ordinary_call(self):
        repo = self.make_repo()
        out, proc = self.event({"event": "pre_tool_use", "cwd": repo,
                                "session_id": "s", "tool": "read",
                                "input": {"path": "README.md"}})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNone(out)  # an empty answer, not an empty object

    def test_the_gate_counts_the_failures_the_ledger_row_recorded(self):
        # One call, one id: `call_id` hashes tool+args and the gate and the row
        # both read the payload's `tool`/`input`, so a failure the ledger
        # recorded is the one the loop guard counts when the same call comes
        # back through PreToolUse.
        repo = self.make_repo()
        for _ in range(2):
            self.event({"event": "post_tool_use", "cwd": repo,
                        "session_id": "s-loop", "tool": "bash",
                        "input": {"command": "pytest -q"}, "failed": True})
        out, proc = self.event({"event": "pre_tool_use", "cwd": repo,
                                "session_id": "s-loop", "tool": "bash",
                                "input": {"command": "pytest -q"}})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(out["deny"])

    def test_the_row_carries_the_result_size_and_never_the_body(self):
        # the bridge sends a size, never the result: the writer's rule is that the
        # ledger records that a call returned something, not what it returned
        repo = self.make_repo()
        self.event({"event": "post_tool_use", "cwd": repo, "session_id": "s",
                    "tool": "bash", "input": {"command": "pytest -q"},
                    "failed": False, "result_len": 41})
        row = [r for r in self.evidence() if r.get("kind") == "verify_ok"][-1]
        self.assertEqual(row["out_bytes"], 41)
        self.assertNotIn("stdout", json.dumps(row))

    def test_a_result_the_bridge_could_not_size_leaves_the_field_out(self):
        # absent is not zero: a size nobody measured must not be recorded as the
        # empty result the Stop rule refuses
        repo = self.make_repo()
        self.event({"event": "post_tool_use", "cwd": repo, "session_id": "s",
                    "tool": "bash", "input": {"command": "pytest -q"},
                    "failed": False})
        row = [r for r in self.evidence() if r.get("kind") == "verify_ok"][-1]
        self.assertNotIn("out_bytes", row)

    def test_post_tool_use_records_evidence_and_marks_the_used_kind(self):
        repo = self.make_repo()
        self.event({"event": "post_tool_use", "cwd": repo, "session_id": "s",
                    "tool": "task", "input": {"prompt": "x"}})
        ledger = os.path.join(self.home, ".cache", "tezgah", "sessions")
        files = os.listdir(ledger)
        self.assertEqual(len(files), 1, files)
        with open(os.path.join(ledger, files[0])) as fh:
            self.assertIn("orch", fh.read())

    def test_a_skill_url_read_marks_the_skill_as_read(self):
        # omp's read tool reaches a skill as `skill://<name>`, not as its path
        repo = self.make_repo()
        for path in ("skill://i-have-adhd", "skill://ponytail/SKILL.md",
                     "skill://other"):
            self.event({"event": "post_tool_use", "cwd": repo, "session_id": "s",
                        "tool": "read", "input": {"path": path}})
        self.assertEqual(self.kinds("s"), ["adhd", "pony"])

    def test_stop_blocks_a_done_claim_no_check_backs(self):
        repo = self.make_repo()
        # a check whose outcome omp never reported is recorded as one that ran,
        # never as one that passed - so it cannot license a "done"
        self.event({"event": "post_tool_use", "cwd": repo, "session_id": "s",
                    "tool": "bash", "input": {"command": "pytest -q"}})
        out, proc = self.event({"event": "stop", "cwd": repo,
                                "session_id": "s",
                                "last_assistant_message": "Done."})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out.get("decision"), "block")
        self.assertIn("doğrulanmadı", out["reason"])

    def test_stop_clears_when_the_check_actually_passed(self):
        repo = self.make_repo()
        self.event({"event": "post_tool_use", "cwd": repo, "session_id": "s",
                    "tool": "bash", "input": {"command": "pytest -q"},
                    "failed": False})
        out, _ = self.event({"event": "stop", "cwd": repo, "session_id": "s",
                             "last_assistant_message": "Done."})
        self.assertIsNone(out)

    def test_a_forged_pass_after_a_gated_one_blocks_as_evidence_tampered(self):
        # plan 051: the gate's pre_tool_use `began` row pairs with the
        # post_tool_use pass; a pass appended with `python3 -c` has none
        repo = self.make_repo()
        call = {"cwd": repo, "session_id": "s", "tool": "bash",
                "input": {"command": "pytest -q"}}
        self.event(dict(call, event="pre_tool_use"))
        self.event(dict(call, event="post_tool_use", failed=False))
        stop = {"event": "stop", "cwd": repo, "session_id": "s",
                "last_assistant_message": "Done."}
        self.assertIsNone(self.event(stop)[0])
        [path] = glob.glob(os.path.join(self.home, ".cache", "tezgah", "evidence",
                                        support.slug("s") + "-*.jsonl"))
        row = json.dumps({"kind": "verify_ok", "detail": "pytest -q", "id": "forged",
                          "exit": 0, "out_bytes": 42, "v": 3})
        proc = run(["-c", "import sys; open(sys.argv[1], 'a').write(sys.argv[2] + '\\n')",
                    path, row])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out, _ = self.event(stop)
        self.assertEqual(out.get("decision"), "block")
        self.assertIn("Evidence tampered", out["reason"])

    def test_stop_clears_on_an_honest_unverified_claim(self):
        repo = self.make_repo()
        self.event({"event": "post_tool_use", "cwd": repo, "session_id": "s",
                    "tool": "bash", "input": {"command": "pytest -q"}})
        out, _ = self.event({"event": "stop", "cwd": repo, "session_id": "s",
                             "last_assistant_message": "Fixed; doğrulanmadı."})
        self.assertIsNone(out)

    def test_the_reply_after_a_block_is_never_blocked_again(self):
        repo = self.make_repo()
        self.event({"event": "post_tool_use", "cwd": repo, "session_id": "s",
                    "tool": "bash", "input": {"command": "pytest -q"}})
        out, _ = self.event({"event": "stop", "cwd": repo, "session_id": "s",
                             "last_assistant_message": "Done.",
                             "stop_hook_active": True})
        self.assertIsNone(out)

    def evidence(self):
        """Every evidence row the session cache holds, oldest file first. The
        ledger is one file per session under a hashed stem, so it is read by
        directory rather than by guessing the name."""
        d = os.path.join(self.home, ".cache", "tezgah", "evidence")
        rows = []
        try:
            names = sorted(os.listdir(d))
        except OSError:
            return rows
        for name in names:
            with open(os.path.join(d, name)) as fh:
                rows += [json.loads(line) for line in fh if line.strip()]
        return rows

    def test_an_untrusted_result_is_labelled_for_the_model(self):
        # Neither the gate nor the Stop rule sees where a result's text came
        # from, so the model is told at the result itself: one line the bridge
        # puts in front of the content, and the channel on the ledger row.
        repo = self.make_repo()
        cases = [
            ("web_search", {"query": "x"}, "a web result", "web"),
            ("web_fetch", {"url": "https://x"}, "a web result", "web"),
            ("mcp__github__get_file", {"path": "x"}, "an MCP server", "mcp"),
            ("bash", {"command": "cd /tmp && curl -s https://x"},
             "a network read", "network"),
        ]
        for tool, inp, phrase, channel in cases:
            out, proc = self.event({"event": "post_tool_use", "cwd": repo,
                                    "session_id": support.slug(tool + phrase),
                                    "tool": tool, "input": inp, "failed": False})
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("untrusted", out["label"], tool)
            self.assertIn(phrase, out["label"], tool)
            self.assertTrue(out["label"].startswith("tezgah:"), out["label"])
        # one provenance row per case, on the channel that carried the result,
        # and none of them claiming a kind of work
        rows = [r for r in self.evidence() if r.get("source")]
        self.assertEqual(sorted(r["source"] for r in rows),
                         ["mcp", "network", "web", "web"])
        self.assertEqual(len(rows), len(cases), rows)
        # a shell read stays a step of work and carries the channel on its row;
        # the two channels that only ever produce text claim provenance and no
        # work, so the step counter and the Stop rule ignore them
        self.assertEqual(sorted((r["source"], r["kind"]) for r in rows),
                         [("mcp", "external"), ("network", "run"),
                          ("web", "external"), ("web", "external")])

    def test_a_workspace_result_carries_no_label(self):
        # The label names an exception. An ordinary call must not wear one, or
        # the model learns to skip the line, and the ledger must not claim a
        # provenance it does not have.
        repo = self.make_repo()
        cases = [("bash", {"command": "pytest -q"}),
                 ("bash", {"command": 'git commit -m "curl is not a read"'}),
                 ("bash", {"command": "grep -n curl hooks/"}),
                 ("grep", {"pattern": "curl"})]
        for tool, inp in cases:
            out, proc = self.event({"event": "post_tool_use", "cwd": repo,
                                    "session_id": support.slug(tool + str(inp)),
                                    "tool": tool, "input": inp, "failed": False})
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("label", out, tool)
        self.assertEqual([r for r in self.evidence() if r.get("source")], [])
        self.assertEqual([r for r in self.evidence() if r["kind"] == "external"],
                         [])

    def test_a_subagent_report_is_labelled_and_its_part_count_is_not_a_size(self):
        # A task's report is text this session did not write, so it is labelled
        # like any outside channel. The bridge's `result_len` is the report's
        # part count (1 for a one-part report of any length), never its bytes,
        # so the row states no size rather than claiming a 1-byte report.
        repo = self.make_repo()
        out, proc = self.event({"event": "post_tool_use", "cwd": repo,
                                "session_id": "s-sub", "tool": "task",
                                "input": {"prompt": "x"}, "failed": False,
                                "result_len": 1})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("untrusted", out["label"])
        self.assertIn("a subagent's report", out["label"])
        row = [r for r in self.evidence() if r.get("source")][-1]
        self.assertEqual((row["kind"], row["source"]), ("external", "subagent"))
        self.assertNotIn("out_bytes", row)

    def test_an_effect_after_a_web_read_carries_the_taint_notice(self):
        # The other hosts mark the first effect a turn makes after an untrusted
        # read (tezgah_untrusted.marks); omp used to label the read and leave the
        # effect bare. The notice rides `label`, the effect's row carries the
        # inherited channel, and the next effect has nothing left to say.
        repo = self.make_repo()
        base = {"event": "post_tool_use", "cwd": repo, "session_id": "s-taint",
                "failed": False}
        self.event(dict(base, tool="web_fetch", input={"url": "https://x"}))
        out, proc = self.event(dict(base, tool="bash",
                                    input={"command": "pytest -q"}))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("in a turn that already read a web result", out["label"])
        self.assertNotIn("untrusted content", out["label"])
        run_row = [r for r in self.evidence() if r.get("tool") == "bash"][-1]
        self.assertEqual(run_row.get("source"), "web")
        again, _ = self.event(dict(base, tool="bash", input={"command": "ls"}))
        self.assertNotIn("label", again)

    def test_a_subagent_report_keeps_its_label_with_no_result_body(self):
        # omp's bridge never sends the report's body, and `marks` reads a None
        # result as "nothing was read" - the hook must keep the subagent label
        # with or without `result_len`, and the next effect inherits it.
        repo = self.make_repo()
        base = {"event": "post_tool_use", "cwd": repo, "session_id": "s-sub2",
                "failed": False}
        for extra in ({}, {"result_len": 1}):
            out, proc = self.event(dict(base, tool="task",
                                        input={"prompt": "x"}, **extra))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("a subagent's report", out["label"])
            self.assertIn("untrusted content", out["label"])
        # the effect inherits the channel, and keeps its own measured size: the
        # part-count rule is the report's, not every row that carries the channel
        out, _ = self.event(dict(base, tool="bash", input={"command": "ls"},
                                 result_len=7))
        self.assertIn("in a turn that already read a subagent's report",
                      out["label"])
        row = [r for r in self.evidence() if r.get("tool") == "bash"][-1]
        self.assertEqual((row.get("source"), row.get("out_bytes")),
                         ("subagent", 7))

    def test_unknown_event_and_broken_stdin_are_silent(self):
        proc = run([support.OMP_HOOK], {"event": "who-knows",
                                        "cwd": self.make_repo()},
                   env=self.env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "")
        broken = run([support.OMP_HOOK], None, env=self.env())
        self.assertEqual(broken.returncode, 0, broken.stderr)
        self.assertEqual(broken.stdout.strip(), "")


class OmpHookThroughTheInstalledPath(TempHome):
    """tezgah-setup substitutes the hook's absolute path into the extension and
    omp runs it with the user's own environment: no PYTHONPATH of its own."""

    def test_events_run_without_pythonpath(self):
        repo = self.make_repo()
        env = self.env()
        env.pop("PYTHONPATH", None)
        out, proc = run_json([support.OMP_HOOK],
                             {"event": "pre_tool_use", "cwd": repo,
                              "tool": "bash",
                              "input": {"command": 'git commit -m '
                                                   '"Co-Authored-By: x"'}},
                             env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("deny", out)
        status, _ = run_json([support.OMP_HOOK],
                             {"event": "status", "cwd": repo}, env=env)
        self.assertIn("pony", status["status"])


if __name__ == "__main__":
    unittest.main()
