"""hooks/tezgah_taste_ledger.py: taste-1's symbolic layer and meta loop (design
T1P of research line taste-architecture) and what the hooks inject from it.

In-process, with the user store, the cache and the kill-switch dirs pointed into
a temp HOME; the decisions are written by hand, so every transition is checked
against the rule it implements rather than against a model's answer.
"""
import json
import os
import shutil
import subprocess
import sys
import unittest
from unittest import mock

import support
from support import TempHome

sys.path.insert(0, support.HOOKS)
import tezgah_context as tc  # noqa: E402
import tezgah_paths as tp  # noqa: E402
import tezgah_taste as tt  # noqa: E402
import tezgah_taste_ledger as tl  # noqa: E402

DAY = tl.now_day()  # the hooks read the ledger at the real now


def dec(kind="preference", p=0.9, category="naming", scope="repository",
        relations=None, verified=True):
    return {"kind": (kind, p), "category": (category, 0.9), "scope": (scope, 0.9),
            "relations": relations or {}, "verified": verified}


def sig(n, session, text="name it snake_case", paths=("a.py",)):
    return {"id": "s%d" % n, "session": session, "text": text, "paths": list(paths)}


class Ledger(TempHome):

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        os.makedirs(os.path.join(self.repo, ".tezgah"))
        with open(os.path.join(self.repo, "a.py"), "w") as fh:
            fh.write("x = 1\n")
        self.config_dir = os.path.join(self.home, ".config", "tezgah")
        os.makedirs(self.config_dir)
        for mod, name, value in ((tp, "OFF_DIRS", (self.config_dir,)),
                                 (tp, "CACHE", os.path.join(self.home, ".cache", "tezgah")),
                                 (tl, "CONFIG_DIR", self.config_dir)):
            self.addCleanup(setattr, mod, name, getattr(mod, name))
            setattr(mod, name, value)
        env = mock.patch.dict(os.environ, {"TEZGAH_ROOTS": self.roots})
        env.start()
        self.addCleanup(env.stop)
        self.books = tl.load(self.repo)

    def only(self):
        [learning] = tl.every(self.books).values()
        return learning

    def labels(self, agree, n):
        for i in range(n):
            tl.append(self.repo, "labels", {"id": "l%d" % i, "provider": "typesafe",
                                            "decided": "preference",
                                            "label": "preference" if i < agree else "none"})

    def active(self, r=3.0, scope="repository", where=".", text="use pathlib"):
        tl.apply(self.books, dict(sig(1, "A", text), paths=["a.py"]),
                 dec(scope=scope), DAY)
        learning = self.only()
        tl.apply(self.books, sig(2, "B", text), dec(relations={learning["id"]: ("supports", 1.0)}),
                 DAY)
        learning.update(r=r, s=0.0, updated=DAY, where=where)
        tl.save(self.repo, self.books)
        return learning

    # --- evidence calculus

    def test_confidence_is_the_beta_expectation_and_forgets_at_the_scope_rate(self):
        learning = {"r": 3.0, "s": 0.0, "scope": "repository", "updated": DAY}
        self.assertAlmostEqual(tl.confidence(learning, DAY), 0.8)
        # thirty days at 0.99 a day: r = 3 * 0.99^30, below the rule threshold
        self.assertLess(tl.confidence(learning, DAY + 30), tl.RULE_AT)
        self.assertAlmostEqual(tl.confidence(learning, DAY + 30),
                               (3 * 0.99 ** 30 + 1) / (3 * 0.99 ** 30 + 2), places=9)
        # a path learning forgets faster than a user learning
        fast = dict(learning, scope="path")
        slow = dict(learning, scope="user")
        self.assertLess(tl.confidence(fast, DAY + 30), tl.confidence(slow, DAY + 30))

    def test_clopper_pearson_lower_bound(self):
        self.assertAlmostEqual(tl.cp_lower(6, 6), 0.5407, places=4)
        self.assertLess(tl.cp_lower(16, 16), 0.8)
        self.assertGreaterEqual(tl.cp_lower(17, 17), 0.8)
        # the exact interval of 8/10 starts at 0.4439
        self.assertAlmostEqual(tl.cp_lower(8, 10), 0.4439, places=4)
        self.assertEqual(tl.cp_lower(0, 5), 0.0)

    # --- the symbolic layer

    def test_a_preference_needs_two_sessions_before_it_is_active(self):
        self.assertEqual(tl.apply(self.books, sig(1, "A"), dec(), DAY), "learned")
        learning = self.only()
        self.assertEqual(learning["state"], "candidate")
        tl.apply(self.books, sig(2, "A"), dec(relations={learning["id"]: ("supports", 1.0)}), DAY)
        self.assertEqual(learning["state"], "candidate", "one session promoted it")
        tl.apply(self.books, sig(3, "B"), dec(relations={learning["id"]: ("supports", 1.0)}), DAY)
        self.assertEqual(learning["state"], "active")

    def test_an_unverified_or_non_preference_decision_never_touches_the_ledger(self):
        self.assertEqual(tl.apply(self.books, sig(1, "A"), dec(verified=False), DAY),
                         "unverified")
        self.assertEqual(tl.apply(self.books, sig(2, "A"), dec(kind="defect"), DAY), "defect")
        self.assertEqual(tl.apply(self.books, sig(3, "A"), dec(category="vibes"), DAY), "none")
        self.assertEqual(tl.every(self.books), {})

    def test_a_contradiction_flags_the_active_learning_and_quarantines_the_claim(self):
        old = self.active()
        tl.apply(self.books, sig(3, "C", "use os.path"),
                 dec(relations={old["id"]: ("contradicts", 1.0)}), DAY)
        [new] = [v for v in tl.every(self.books).values() if v["id"] != old["id"]]
        self.assertEqual((old["state"], new["state"]), ("conflicted", "quarantined"))
        self.assertEqual((old["conflicts"], new["conflicts"]), ([new["id"]], [old["id"]]))
        self.assertGreater(old["s"], 0)
        self.assertEqual(old["text"], "use pathlib", "the new claim overwrote the old one")
        # one more contradiction pushes the old side under 0.4: it retires and
        # the contrary claim is released to candidate
        old["s"] = 6.0
        tl.settle(self.books, DAY)
        self.assertEqual((old["state"], new["state"]), ("retired", "candidate"))

    def test_a_corroborated_contrary_claim_is_withheld_until_the_conflict_resolves(self):
        old = self.active()
        tl.apply(self.books, sig(3, "C", "use os.path"),
                 dec(relations={old["id"]: ("contradicts", 1.0)}), DAY)
        [new] = [v for v in tl.every(self.books).values() if v["id"] != old["id"]]
        tl.apply(self.books, sig(4, "D", "os.path again"),
                 dec(relations={new["id"]: ("supports", 1.0)}), DAY)
        self.assertEqual((old["state"], new["state"]), ("conflicted", "conflicted"))
        tl.save(self.repo, self.books)
        self.assertEqual(tl.usable(self.repo, DAY), [])

    def test_an_id_is_never_issued_twice_after_a_learning_is_forgotten(self):
        old = self.active()
        tl.apply(self.books, sig(3, "C", "use os.path"),
                 dec(p=0.6, relations={old["id"]: ("contradicts", 0.1)}), DAY)
        [gone] = [v["id"] for v in tl.every(self.books).values() if v["id"] != old["id"]]
        tl.settle(self.books, DAY + 200)
        self.assertNotIn(gone, tl.every(self.books))
        self.assertNotIn(gone, old["conflicts"])
        tl.apply(self.books, sig(5, "E", "tabs"), dec(category="formatting"), DAY + 200)
        self.assertNotIn(gone, tl.every(self.books), "a forgotten id was issued again")

    def test_narrows_keeps_the_broad_learning_and_adds_a_narrower_one(self):
        broad = self.active(scope="repository")
        tl.apply(self.books, sig(3, "C", "except in tests use plain asserts", ("tests/t.py",)),
                 dec(scope="path", relations={broad["id"]: ("narrows", 1.0)}), DAY)
        [narrow] = [v for v in tl.every(self.books).values() if v["id"] != broad["id"]]
        self.assertEqual(broad["state"], "active")
        self.assertEqual((narrow["scope"], narrow["where"], narrow["parent"]),
                         ("path", "tests/**", broad["id"]))

    def test_an_applied_learning_corrected_in_its_category_and_scope_loses_confidence(self):
        learning = self.active()
        before = tl.confidence(learning, DAY)
        tl.apply(self.books, sig(3, "C", "no, camelCase here"), dec(), DAY,
                 applied={learning["id"]})
        self.assertLess(tl.confidence(learning, DAY), before)
        # a correction in another category leaves it alone
        s = learning["s"]
        tl.apply(self.books, sig(4, "C", "add a test"), dec(category="testing"), DAY,
                 applied={learning["id"]})
        self.assertEqual(learning["s"], s)
        # so does one outside a path learning's directory
        learning.update(scope="path", where="pkg/**")
        tl.apply(self.books, sig(5, "C", "camelCase", ("web/x.py",)), dec(), DAY,
                 applied={learning["id"]})
        self.assertEqual(learning["s"], s)

    def test_a_one_session_claim_is_forgotten_unless_corroborated(self):
        tl.apply(self.books, sig(1, "A"), dec(p=0.6), DAY)
        tl.settle(self.books, DAY + 100)
        self.assertEqual(tl.every(self.books), {})

    def test_the_user_accepts_rejects_and_edits(self):
        learning = self.active()
        self.assertTrue(tl.decide_user(self.books, learning["id"], "edit", DAY, "Prefer pathlib."))
        self.assertEqual((learning["text"], learning["edited"]), ("Prefer pathlib.", True))
        self.assertTrue(tl.decide_user(self.books, learning["id"], "reject", DAY))
        self.assertEqual(learning["state"], "retired")
        self.assertFalse(tl.decide_user(self.books, "t9999", "accept", DAY))

    # --- apply

    def test_rule_needs_confidence_and_the_calibration_bound(self):
        learning = self.active(r=3.0)  # confidence 0.8
        [(mode, _)] = tl.usable(self.repo, DAY)
        self.assertEqual(mode, "hint", "a rule without a calibration bound")
        self.labels(17, 17)
        [(mode, _)] = tl.usable(self.repo, DAY)
        self.assertEqual(mode, "rule")
        learning.update(r=1.0)
        tl.save(self.repo, self.books)
        [(mode, _)] = tl.usable(self.repo, DAY)
        self.assertEqual(mode, "hint")  # 0.667
        learning.update(r=0.0)
        tl.save(self.repo, self.books)
        self.assertEqual(tl.usable(self.repo, DAY), [])  # 0.5

    def test_conflicted_and_suspended_learnings_are_withheld(self):
        learning = self.active()
        learning["state"] = "conflicted"
        tl.save(self.repo, self.books)
        self.assertEqual(tl.usable(self.repo, DAY), [])
        learning["state"] = "active"
        tl.save(self.repo, self.books)
        self.assertEqual(len(tl.usable(self.repo, DAY)), 1)
        os.remove(os.path.join(self.repo, "a.py"))
        self.assertEqual(tl.usable(self.repo, DAY), [], "evidence is gone, still injected")

    def test_the_session_block_names_the_learning_and_returns_its_ids(self):
        learning = self.active()
        text, ids = tl.block(self.repo, DAY)
        self.assertIn("hint [naming, %s]: use pathlib" % learning["id"], text)
        self.assertIn("narrower scope wins", text)
        self.assertEqual(ids, [learning["id"]])
        self.assertEqual(tl.injected(self.repo, "S9"), set(), "recorded before the budget")

    def test_context_for_carries_the_block_only_when_taste_is_armed(self):
        learning = self.active()
        payload = {"session_id": "S10"}
        self.assertNotIn("Taste (learned", tc.context_for("session_start", self.repo, payload) or "")
        self.assertEqual(tl.injected(self.repo, "S10"), set())
        open(os.path.join(self.config_dir, tt.ARM), "w").close()
        self.assertIn("Taste (learned", tc.context_for("session_start", self.repo, payload))
        self.assertEqual(tl.injected(self.repo, "S10"), {learning["id"]})

    def test_the_write_note_shows_each_in_scope_learning_once_per_session(self):
        self.active(scope="language", where="*.py")
        self.assertIn("use pathlib", tl.write_note(self.repo, "S", "pkg/b.py"))
        self.assertEqual(tl.write_note(self.repo, "S", "pkg/c.py"), "", "repeated in one session")
        self.assertEqual(tl.write_note(self.repo, "S", "web/x.ts"), "", "out of scope")
        self.assertIn("use pathlib", tl.write_note(self.repo, "T", "c.py"))

    def test_a_path_learning_shows_at_its_directory_after_another_write_of_the_type(self):
        self.active(scope="path", where="tests/**")
        self.assertEqual(tl.write_note(self.repo, "S", "pkg/b.py"), "")
        self.assertIn("use pathlib", tl.write_note(self.repo, "S", "tests/t.py"))

    def test_tezgah_taste_write_note_skips_a_read_and_needs_the_marker(self):
        self.active(scope="language", where="*.py")
        inp = {"file_path": "a.py", "old_string": "x = 1", "new_string": "x = 2"}
        self.assertEqual(tt.write_note("S", inp, self.repo, "Edit"), "", "unarmed")
        open(os.path.join(self.config_dir, tt.ARM), "w").close()
        self.assertEqual(tt.write_note("S", {"file_path": "a.py"}, self.repo, "Read"), "")
        self.assertIn("use pathlib", tt.write_note("S", inp, self.repo, "Edit"))

    # --- markdown, export, gate

    def test_markdown_and_agents_export(self):
        learning = self.active()
        [path] = tl.markdown(self.repo, DAY)
        with open(path) as fh:
            self.assertIn("- use pathlib (repository, %s). Confidence: 0.80" % learning["id"],
                          fh.read())
        self.assertEqual(tl.export_agents(self.repo), 0)
        self.assertFalse(os.path.exists(os.path.join(self.repo, "AGENTS.md")),
                         "an empty export wrote AGENTS.md")
        with open(os.path.join(self.repo, "AGENTS.md"), "w") as fh:
            fh.write("# Rules\n\nkeep this\n")
        tl.decide_user(self.books, learning["id"], "accept", DAY)
        tl.save(self.repo, self.books)
        self.assertEqual(tl.export_agents(self.repo), 1)
        self.assertEqual(tl.export_agents(self.repo), 1)
        with open(os.path.join(self.repo, "AGENTS.md")) as fh:
            text = fh.read()
        self.assertTrue(text.startswith("# Rules\n\nkeep this\n"))
        self.assertEqual(text.count(tl.START), 1)
        self.assertIn("- use pathlib", text)

    def test_the_gate_splits_at_the_first_injection_by_turn_time(self):
        learning = self.active()
        tl.record_injection(self.repo, "S", [learning["id"]], day=DAY)
        for i in range(10):
            # every row decided now; the turn time alone picks the arm
            for arm, at in (("b", DAY - 1), ("a", DAY + 1)):
                tl.append(self.repo, "decisions", {
                    "id": "%s%d" % (arm, i), "provider": "typesafe", "day": DAY + 5,
                    "at": at, "kind": "preference" if i < 3 else "none"})
        report = tl.gate(self.repo, need=10)
        self.assertEqual((report["before"]["turns"], report["after"]["turns"]), (10, 10))
        self.assertTrue(report["stopped"])
        self.assertEqual(tl.block(self.repo, DAY), ("", []))
        self.assertTrue(tl.stopped(self.repo))

    # --- the store

    def test_the_legacy_files_import_and_are_renamed(self):
        store = tl.store_dir(self.repo)
        self.assertEqual((tl.rows(self.repo, "signals"), tl.stopped(self.repo)), ([], False))
        self.assertFalse(os.path.exists(store), "a read created the store")
        tl.apply(self.books, sig(1, "A"), dec(), DAY)
        tl.apply(self.books, sig(2, "A", "tabs"), dec(category="formatting", scope="user"), DAY)
        tables = {"signals": [{"kind": "prompt", "session": "A", "text": "use pathlib"}],
                  "decisions": [{"id": "s1", "provider": "typesafe", "at": DAY,
                                 "kind": "preference"}],
                  "defects": [{"id": "s2", "session": "A", "text": "it fails"}],
                  "labels": [{"id": "s1", "provider": "typesafe", "decided": "preference",
                              "label": "preference"}],
                  "injected": [{"session": "A", "day": DAY, "ids": ["t0001"]}]}
        legacy = {os.path.join(store, "ledger.json"): self.books["repo"],
                  os.path.join(tl.user_dir(), "ledger.json"): self.books["user"],
                  os.path.join(store, "gate.json"): {"stopped": True, "report": {}}}
        os.makedirs(store)
        os.makedirs(tl.user_dir())
        for path, data in legacy.items():
            with open(path, "w") as fh:
                json.dump(data, fh)
        for table, rows in tables.items():
            path = os.path.join(store, table + ".jsonl")
            legacy[path] = rows
            with open(path, "w") as fh:
                fh.write("".join(json.dumps(r) + "\n" for r in rows) + '{"torn')
        books = tl.load(self.repo)
        self.assertEqual(books["repo"]["learnings"], self.books["repo"]["learnings"])
        self.assertEqual(books["repo"]["meta"], self.books["repo"]["meta"])
        self.assertEqual(books["user"]["learnings"], self.books["user"]["learnings"])
        self.assertTrue(tl.stopped(self.repo))
        for table, rows in tables.items():
            self.assertEqual(tl.rows(self.repo, table), rows, table)
        self.assertEqual(tl.injected(self.repo, "A"), {"t0001"})
        for path in legacy:
            self.assertFalse(os.path.exists(path), path)
            self.assertTrue(os.path.exists(path + ".imported"), path)
        # a row file that appears later (an older install still writing it) is
        # appended on the next open, beside the first import's file, never over it
        again = os.path.join(store, "signals.jsonl")
        late = {"kind": "prompt", "session": "B", "text": "late"}
        with open(again, "w") as fh:
            fh.write(json.dumps(late) + "\n")
        self.assertEqual(tl.rows(self.repo, "signals"), tables["signals"] + [late])
        self.assertFalse(os.path.exists(again))
        self.assertTrue(os.path.exists(again + ".imported.1"))
        self.assertTrue(os.path.exists(again + ".imported"))
        # a ledger document imports only into empty tables: a later one stays put
        stale = os.path.join(store, "ledger.json")
        with open(stale, "w") as fh:
            json.dump({"v": 1, "learnings": {}, "meta": {"next_id": 99}}, fh)
        self.assertEqual(tl.load(self.repo)["repo"], books["repo"])
        self.assertTrue(os.path.exists(stale))

    def test_a_torn_multibyte_tail_keeps_the_rows_before_it(self):
        store = tl.store_dir(self.repo)
        os.makedirs(store)
        row = {"kind": "prompt", "session": "A", "text": "çalış"}
        path = os.path.join(store, "signals.jsonl")
        with open(path, "wb") as fh:
            fh.write(json.dumps(row, ensure_ascii=False).encode() + b'\n{"text": "\xc5')
        self.assertEqual(tl.rows(self.repo, "signals"), [row])
        self.assertTrue(os.path.exists(path + ".imported"))

    def test_a_legacy_file_that_does_not_parse_is_tried_again_on_the_next_open(self):
        store = tl.store_dir(self.repo)
        os.makedirs(store)
        path = os.path.join(store, "ledger.json")
        with open(path, "w") as fh:
            fh.write('{"learnings": ')
        self.assertEqual(tl.load(self.repo)["repo"]["learnings"], {})
        self.assertTrue(os.path.exists(path), "an unparsed file was moved away")
        tl.apply(self.books, sig(1, "A"), dec(), DAY)
        with open(path, "w") as fh:
            json.dump(self.books["repo"], fh)
        self.assertEqual(tl.load(self.repo)["repo"]["learnings"],
                         self.books["repo"]["learnings"])
        self.assertTrue(os.path.exists(path + ".imported"))

    def test_a_strict_append_raises_where_a_hook_append_drops(self):
        os.makedirs(os.path.dirname(tl.store_dir(self.repo)), exist_ok=True)
        open(tl.store_dir(self.repo), "w").close()  # the store's directory is a file
        row = {"id": "s1", "provider": "typesafe"}
        self.assertIsNone(tl.append(self.repo, "decisions", row))
        with self.assertRaises(OSError):
            tl.append(self.repo, "decisions", row, strict=True)


class HostNotes(TempHome):
    """Every host's post-tool channel carries the taste note on the first write
    to a file type with an in-scope active learning - run through each host's
    own hook script (and opencode's plugin through its node harness), with the
    marker armed in the throwaway HOME."""

    EDIT = {"file_path": "a.py", "old_string": "x = 1", "new_string": "x = 2"}

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        os.makedirs(os.path.join(self.repo, ".tezgah"))
        with open(os.path.join(self.repo, "a.py"), "w") as fh:
            fh.write("x = 1\n")
        config = os.path.join(self.home, ".config", "tezgah")
        os.makedirs(os.path.join(config, "bin"))
        open(os.path.join(config, tt.ARM), "w").close()
        self.addCleanup(setattr, tl, "CONFIG_DIR", tl.CONFIG_DIR)
        tl.CONFIG_DIR = config
        books = tl.load(self.repo)
        tl.apply(books, sig(1, "A", "prefer pathlib"), dec(scope="language"), DAY)
        [learning] = tl.every(books).values()
        tl.apply(books, sig(2, "B", "prefer pathlib"),
                 dec(relations={learning["id"]: ("supports", 1.0)}), DAY)
        tl.save(self.repo, books)
        self.envv = self.env()

    def hook(self, script, payload):
        out, proc = support.run_json([script], payload, env=self.envv)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out or {}

    def test_claude_and_dsh(self):
        out = self.hook(support.POSTTOOLUSE, {
            "hook_event_name": "PostToolUse", "cwd": self.repo, "session_id": "c1",
            "tool_name": "Edit", "tool_input": self.EDIT, "tool_response": {}})
        self.assertIn("prefer pathlib", out["hookSpecificOutput"]["additionalContext"])
        again = self.hook(support.POSTTOOLUSE, {
            "hook_event_name": "PostToolUse", "cwd": self.repo, "session_id": "c1",
            "tool_name": "Edit", "tool_input": self.EDIT, "tool_response": {}})
        self.assertNotIn("prefer pathlib", json.dumps(again))

    def test_codex(self):
        out = self.hook(support.CODEX_HOOK, {
            "hook_event_name": "PostToolUse", "cwd": self.repo, "session_id": "x1",
            "tool_name": "Edit", "tool_input": self.EDIT, "tool_response": {}})
        self.assertIn("prefer pathlib", out["hookSpecificOutput"]["additionalContext"])

    def test_cursor(self):
        out = self.hook(support.CURSOR_HOOK, {
            "hook_event_name": "postToolUse", "cwd": self.repo, "conversation_id": "k1",
            "tool_name": "Edit", "tool_input": self.EDIT, "tool_output": "ok"})
        self.assertIn("prefer pathlib", out["additional_context"])

    def test_omp(self):
        out = self.hook(support.OMP_HOOK, {
            "event": "post_tool_use", "cwd": self.repo, "session_id": "o1",
            "tool": "edit", "input": {"path": "a.py", "old_text": "x", "new_text": "y"},
            "failed": False})
        self.assertIn("prefer pathlib", out["label"])

    def test_opencode(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        os.symlink(os.path.join(support.REPO, "bin", "tezgah-capture"),
                   os.path.join(self.home, ".config", "tezgah", "bin", "tezgah-capture"))
        spec = {"plugin": support.OPENCODE_PLUGIN, "dir": self.repo, "calls": [{
            "hook": "tool.execute.after",
            "input": {"tool": "edit", "sessionID": "p1",
                      "args": {"filePath": "a.py", "oldString": "x", "newString": "y"}},
            "output": {"metadata": {}, "output": "edited"}}]}
        proc = subprocess.run([node, support.OPENCODE_HARNESS], input=json.dumps(spec),
                              capture_output=True, text=True, env=self.envv, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        [result] = json.loads(proc.stdout)["results"]
        self.assertIn("prefer pathlib", result["output"]["output"])
        self.assertTrue(result["output"]["output"].endswith("edited"))


if __name__ == "__main__":
    unittest.main()
