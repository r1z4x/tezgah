"""bin/tezgah-dsh.cmd, and the entry bin/tezgah-setup wires for it.

The launcher is chosen by the installer, not by the user: a `/bin/sh` script has
no interpreter on Windows and cmd.exe resolves a command through PATHEXT, so the
platform decides both the file and the name of the entry that starts it. These
tests pin the choice, the `.cmd`'s resolution order against the sh launcher's,
and the report row - which names the launcher it judged, so a row cannot read
`ok` on a platform that cannot start the file behind it.

The `.cmd` cannot be executed here (macOS has no cmd.exe): the running half is
proven by tests/e2e_packaged_install.py in the `artifact-install-windows` CI job,
which starts the entry the installer wrote.
"""
import contextlib
import io
import os
import sys
import unittest

from test_setup import SetupBase, setup_module

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "hooks"))
import tezgah_paths as tp  # noqa: E402

SH = os.path.join(REPO, "bin", "tezgah-dsh")
CMD = os.path.join(REPO, "bin", "tezgah-dsh.cmd")
# Each launcher's warm-up call and the lines that start the CLI after it. The
# pair is what makes "the index is warmed before dsh starts" checkable without
# running either file.
LAUNCHES = {
    SH: ("warm_index",
         ('exec node "$BIN" "$@"', 'exec npx -y @deepseek-ai/dsh "$@"')),
    CMD: ("call :warm",
          ('node "%BIN%" %*', "npx -y @deepseek-ai/dsh %*")),
}


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def previous_line(text, token):
    """The last line before the one carrying `token`, skipping blanks and the
    comments both files use - so a comment between the warm-up and the launch
    does not read as a warm-up that is missing."""
    lines = [ln.strip() for ln in text.splitlines()]
    i = next(n for n, ln in enumerate(lines) if token in ln)
    for line in reversed(lines[:i]):
        if line and not line.startswith(("#", "rem")):
            return line
    return ""


def swap(case, obj, name, value):
    """Set an attribute for one test; the previous value goes back after it."""
    case.addCleanup(setattr, obj, name, getattr(obj, name))
    setattr(obj, name, value)


class Choice(unittest.TestCase):
    """dsh_launcher() answers per platform, driven by the name it is given: the
    test asks for the other answer rather than faking os.name, which the rest of
    the process reads too."""

    def test_each_platform_gets_the_launcher_it_can_start(self):
        mod = setup_module()
        src, dst = mod.dsh_launcher("posix")
        self.assertEqual(os.path.basename(src), "tezgah-dsh")
        self.assertEqual(os.path.basename(dst), "dsh")
        # no argument is this platform, which is what the installer passes
        self.assertEqual(mod.dsh_launcher(), mod.dsh_launcher(os.name))
        self.assertEqual(mod.dsh_launcher(os.name), (src, dst))

    def test_windows_gets_the_cmd_in_a_cmd_entry(self):
        mod = setup_module()
        src, dst = mod.dsh_launcher("nt")
        self.assertEqual(src, CMD)
        self.assertTrue(os.path.isfile(src), "the launcher has to ship: %s" % src)
        self.assertEqual(os.path.basename(dst), "dsh.cmd")
        # same bin dir the POSIX entry goes into, so one install writes one entry
        self.assertEqual(os.path.dirname(dst),
                         os.path.dirname(mod.dsh_launcher("posix")[1]))


class Resolution(unittest.TestCase):
    """The .cmd is the sh launcher's twin: the same CLI resolution order, the
    same warm-up before each launch, the same two-line refusal and exit code.
    Read as text, because this host cannot run a batch file."""

    def test_the_profile_entry_is_tried_before_npx(self):
        for path, entry, npx in (
                (SH, "profiles/node_modules/@deepseek-ai/dsh/lib/bin.js",
                 'exec npx -y @deepseek-ai/dsh "$@"'),
                (CMD, r"profiles\node_modules\@deepseek-ai\dsh\lib\bin.js",
                 "npx -y @deepseek-ai/dsh %*")):
            text = read(path)
            self.assertIn(entry, text, path)
            self.assertLess(text.index(entry), text.index(npx), path)

    def test_each_launcher_warms_the_index_farm_before_it_runs_the_cli(self):
        for path, (warm, launches) in LAUNCHES.items():
            text = read(path)
            for launch in launches:
                self.assertEqual(previous_line(text, launch), warm,
                                 "%s: %s runs without the warm-up"
                                 % (path, launch))

    def test_both_start_the_farm_entry_that_the_tree_installs(self):
        for path in (SH, CMD):
            text = read(path)
            self.assertIn("tezgah-index", text, path)
            self.assertIn("TEZGAH_INDEX_BIN", text, path)
        # the sh launcher execs the entry; the .cmd cannot, so it starts it
        # through the interpreter hooks/tezgah_paths.python_cmd resolves - the
        # farm entry there is a Python script, not a program cmd.exe can run
        cmd = read(CMD)
        self.assertIn('"%PY%" "%INDEX%"', cmd)
        for channel in ("TEZGAH_PYTHON", "python3", "python", "py"):
            self.assertIn(channel, cmd, channel)

    def test_a_missing_cli_is_the_same_two_lines_and_a_non_zero_exit(self):
        for path, var in ((SH, "$BIN"), (CMD, "%BIN%")):
            text = read(path)
            self.assertIn("tezgah-dsh: dsh CLI not found at %s" % var, text, path)
            self.assertIn("tezgah-dsh: install the DeepSeek Harness "
                          "(npx -y @deepseek-ai/dsh) or set DSH_HOME", text, path)
            self.assertRegex(text, r"exit (/b )?127")

    def test_the_cmd_carries_windows_line_endings(self):
        """cmd.exe walks a batch file by CRLF offsets, and `:warm` is reached by
        `call`/`goto`: with bare LFs the label lookup is the part that breaks,
        and no POSIX host would notice. Pinned here, because nothing else in the
        tree reads this file's bytes."""
        with open(CMD, "rb") as fh:
            raw = fh.read()
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""),
                         "a bare LF in a .cmd with labels in it")


class Wired(SetupBase):
    """The entry install_dsh writes, the row that names the launcher it judged,
    and uninstall taking it back."""

    def test_the_install_links_the_sh_launcher_and_the_report_names_it(self):
        mod = setup_module()
        label, _ = mod.dsh_launcher_row(os.name)
        self.assertIn("tezgah-dsh", label)
        self.assertNotIn(".cmd", label)
        proc = self.setup("--install", "--hosts", "dsh")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # the report prints exactly the row this platform's choice produced
        self.assertIn(label, proc.stdout)
        row = self.row(proc.stdout, "dsh launcher on PATH")
        self.assertTrue(row.strip().startswith("ok"), row or proc.stdout)
        entry = self.path(".local", "bin", "dsh")
        self.assertTrue(os.path.islink(entry), proc.stdout)
        self.assertEqual(os.path.realpath(entry), SH)

    def test_uninstall_removes_the_entry_this_platform_wired(self):
        self.assertEqual(self.setup("--install", "--hosts", "dsh").returncode, 0)
        entry = self.path(".local", "bin", "dsh")
        self.assertTrue(os.path.lexists(entry))
        proc = self.setup("--uninstall", "--hosts", "dsh")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(os.path.lexists(entry), proc.stdout)

    def test_a_symlink_less_install_reads_ok_on_posix(self):
        """TEZGAH_NO_SYMLINK is how this suite exercises the layout a locked-down
        Windows account gets without a Windows host. The entry is then a relay
        rather than a link, and on POSIX that relay runs - so the row has to stay
        ok there, which is the case the byte-for-byte Windows check must not
        swallow."""
        self.env["TEZGAH_NO_SYMLINK"] = "1"
        proc = self.setup("--install", "--hosts", "dsh")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        row = self.row(proc.stdout, "dsh launcher on PATH")
        self.assertTrue(row.strip().startswith("ok"), row or proc.stdout)
        entry = self.path(".local", "bin", "dsh")
        self.assertTrue(os.path.isfile(entry) and not os.path.islink(entry))

    def test_the_windows_choice_writes_a_real_cmd_the_row_reports(self):
        mod = setup_module()
        # the platform name is the branch's only input, so the Windows answer is
        # driven directly; the entry and the materialised record are what it
        # writes, so both are pointed at this test's fake home
        swap(self, mod, "LOCAL_BIN", self.path(".local", "bin"))
        swap(self, mod, "MATERIALISED",
             self.path(".config", "tezgah", "materialised"))
        swap(self, tp, "CONFIG_DIR", self.path(".config", "tezgah"))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            mod.install_dsh_launcher("nt")
        entry = self.path(".local", "bin", "dsh.cmd")
        self.assertEqual(mod.dsh_launcher("nt")[1], entry)
        self.assertTrue(os.path.isfile(entry) and not os.path.islink(entry),
                        "no real .cmd was written: %s" % out.getvalue())
        self.assertEqual(self.read_text(entry), self.read_text(CMD),
                         "the entry is not a copy of the launcher")
        label, good = mod.dsh_launcher_row("nt")
        self.assertIn("tezgah-dsh.cmd", label)
        self.assertTrue(good, label)
        # the relay a symlink-less install writes is a `/bin/sh` one-liner, a
        # file cmd.exe cannot start: where the launcher is the .cmd this entry
        # must not read as wired
        with open(entry, "w", encoding="utf-8") as fh:
            fh.write('#!/bin/sh\nexec "%s" "$@"\n' % CMD)
        _, relay_good = mod.dsh_launcher_row("nt")
        self.assertFalse(relay_good, "a sh relay read as a Windows launcher")
        # the POSIX answer is not this entry: which launcher was wired is what
        # the row is about, so one platform's entry cannot answer for the other
        posix_label, posix_good = mod.dsh_launcher_row("posix")
        self.assertNotIn(".cmd", posix_label)
        self.assertFalse(posix_good, posix_label)
        # the copy is tezgah's own entry, so uninstall takes it and the user's
        # same-named file is not adopted
        self.assertTrue(mod.unlink_tezgah(entry))
        self.assertFalse(os.path.lexists(entry))


if __name__ == "__main__":
    unittest.main()
