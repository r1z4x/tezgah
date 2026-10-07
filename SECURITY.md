# Security

## Reporting a vulnerability

Report vulnerabilities privately through GitHub's security advisories
(**Security** tab → **Report a vulnerability**), or directly at
https://github.com/r1z4x/tezgah/security/advisories/new. Please do not open a
public issue for a suspected vulnerability.

## In scope

tezgah runs shell hooks, writes host configuration, and injects text into every
session. Anything that makes a hook execute attacker-controlled code, leaks a
key into a config file, widens a sandbox, or lets repository content escalate
into instruction text is in scope.

## Threat model

tezgah is held to a **cooperative but fallible** agent: one that means to follow
the rules and still reaches for a switch it was shown, deletes a hook that is in
its way, or reads a damaged record as a clean one. It is not a sandbox against
an adversarial agent, and it does not claim to be one.

- **A core error fails open.** Every hook runs the shared core through
  `hooks/tezgah_guard.py`: an exception becomes a `crash` row in the ledger and
  the call is allowed. A rule that cannot run has refused nothing.
- **What is protected, and how.** The gate's `control` rule
  (`hooks/tezgah_gate.py`, `docs/gate.md`) refuses a write tool, and the shell
  shapes it reads (a redirect, `touch`, `rm`, `mv`, `cp`, `chmod`, `tee`,
  `sed -i`, `cp -t`, `curl -o`, `tar -C`, `unzip -d`, `git config
  core.hooksPath`, with `cd`, `if`/`for`/`!`, `eval` and `bash -c` read
  through), on the path as written and through a link, on:
  - the kill switches and opt-in markers (`hooks/tezgah_paths.py` `SWITCHES`,
    under `~/.config/tezgah` and the legacy `~/.claude`) and all of
    `~/.config/tezgah`;
  - the evidence ledger, the session store, the switch baseline and the
    status marks in the cache (`evidence/`, `sessions/`, `switches/`,
    `gate-inactive/`, `harness-drift/`, `import-crash/`,
    `workspace-index.json`);
  - the hook wiring: each host's hook registration file (in a shared file such
    as `~/.claude/settings.json`, only the entries that are tezgah's and
    `disableAllHooks`; in Codex's `config.toml`, every `[hooks...]` trust
    entry), the installed hook tree and the Claude plugin copy;
  - a repository's `.no-*` marks (the `REPO_MARKS` names, under a root), the
    session checkout's `.git/hooks`, and a delete, chmod that takes a
    permission away, or move of `.husky`;
  - a delete or move of a directory that holds any of the above
    (`rm -rf ~/.cache`, `mv .git /tmp/x`);
  - a forced `git add` of a `.tezgah/` path, and a delete or move under
    `.tezgah/plans/open/` (a `--cached` removal is plan-sync's and passes);
  - the CLIs that change that state: `tezgah-gate decide`, `tezgah-capture`,
    `tezgah-pony <level>`, `tezgah-adhd on|off`, `tezgah-context attest`.
    The task CLI is the task rule's.

  Only `pretooluse-off` removes the rule, and it is one of the protected
  files. The refusal names no command. A ledger line that is not a row is
  recorded as `ledger_damage` and blocks a done-claim in that turn as
  "evidence tampered" instead of failing the Stop rule open. A switch armed
  mid-session leaves a `disarm` row and the status line's `gate` mark.
  The session-level backstop for the routes the rule cannot see: a switch file
  newer than the session's first ledger row is ignored in that session (switch
  latching, [docs/contract.md](docs/contract.md#how-a-rule-is-disarmed)) until
  the user's prompt names it.
- **Who the rule can tell apart.** It sees only the calls a host routes
  through its tool hook, so the user's own terminal is never refused. Inside a
  session it cannot tell a change the user asked for from one the agent chose:
  both are refused, and the user makes the change in their own terminal.
- **Residual routes, named rather than closed.**
  - An interpreter: `python3 -c "open(...)"`, `node -e`, any script the agent
    writes and then runs. The path is assembled at run time and the gate reads
    the command line, not what the program does. This includes appending a
    forged `verify_ok` row to the ledger, which passes the Stop rule until
    began/pass pairing ships (plan 051), and emptying the ledger the same way.
  - Began-row forgery through `tezgah-gate decide`: the rule refuses the CLI
    by name, and an interpreter can still import the core and write the row.
  - `find -delete`, `xargs`, and a path built from variables the gate does not
    expand (anything but `~`, `$HOME` and the XDG variables).
  - A glob or brace in a directory component (`rm -rf ~/.config/tez?ah`), and a
    link the same command line creates and then writes through.
  - `tezgah-setup --uninstall`, the user's own command, and any CLI the gate
    has not listed: the rule holds the names it holds.
  - An archive extracted, or a tree copied, into a directory without naming
    the protected path (`cd ~/.config/tezgah && unzip x.zip`, `cp -r h .git/`).
  - A script fed to a shell on stdin (`echo '…' | bash`, `bash <<< '…'`): the
    gate opens `bash -c`, not a shell's standard input.
  - A script fed to a shell on stdin through a quoted-tag heredoc
    (`bash <<'EOF'`): bash expands nothing in that body, and the gate reads it
    as data.
  - Switch latching's ways through are bytes the agent can write: an
    `authorized` row appended to the ledger, and the uninstall's stand-down
    text in `pretooluse-off`, both written by an interpreter. The latch is a
    keyword match, not intent: "don't touch verify-off" authorizes the flip,
    and a prompt computed by a workflow, or a parent's task text a host hands
    a child as its prompt, arrives through the same path as the user's. A
    clock set back makes a new switch look old, and a switch the user flips in
    their own terminal waits for the next session or a prompt that names it.
- **The same uid ceiling.** The agent runs as the user, with the user's file
  permissions. Nothing tezgah writes is out of its reach at the filesystem
  level; the gate is the only barrier, and it is a policy check, not a
  privilege boundary.
- **The shared-ledger taint ceiling.** Subagents of one Claude session write
  one ledger. Claude's hook payload carries `agent_id` for a subagent's call,
  and tezgah keys the taint notice and the repeat ceilings on it, so one
  sibling's web read no longer marks another's effects. On a host where tezgah
  reads no agent key (every host but Claude and omp), siblings that share one
  ledger still share its taint - that is the agent key ceiling; omp writes one
  ledger per subagent.

## What to include

- the host (Claude Code, Codex, Cursor, opencode, dsh, omp) and its version
- the tezgah version: `bin/tezgah-setup --version`
- a minimal reproduction

We aim to acknowledge a report within a few days and to ship a fix in the next
release, with credit if you want it.
