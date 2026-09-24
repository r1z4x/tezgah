#!/usr/bin/env python3
"""End-to-end check: install -> uninstall -> install inside a Docker container.

The claim this makes good is the one a throwaway-HOME unit test cannot quite
reach: on a machine with nothing but python3, `--install` arms the detected
hosts, `--uninstall` leaves nothing behind, and a second install then works
from that clean state. The leftover scan runs in the container from paths alone
- not through tezgah's own code - so the uninstaller's bookkeeping cannot grade
its own homework.

Opt-in and local only, like the other e2e scripts: it prints SKIP when docker
or its daemon is missing and exits 0; CI sets TEZGAH_E2E_STRICT=1 to turn a
skip into a failure.

    TEZGAH_E2E_DOCKER_IMAGE  image to run (default python:3.12-slim; pulled
                             on first use)
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
IMAGE = os.environ.get("TEZGAH_E2E_DOCKER_IMAGE") or "python:3.12-slim"
STRICT = os.environ.get("TEZGAH_E2E_STRICT") == "1"
HOSTS = "codex,omp"
# TEZGAH_E2E_DOCKER_DEPS=1 exercises the path a plain container cannot: node is
# installed first and `--install` runs WITHOUT --no-deps, so install_deps() really
# runs the vendor installers (orx, cursor-agent, pnpm via npm -g, dsh via npx) over
# the network before the hosts are armed.
DEPS = os.environ.get("TEZGAH_E2E_DOCKER_DEPS") == "1"


def skipped(reason):
    print("SKIP: %s" % reason)
    return 1 if STRICT else 0


def inner_script():
    """The bash the container runs: two installs, one uninstall, three proofs.

    The scan is spelled in `python3 - <<'EOF'` over absolute paths under $HOME
    on purpose: nothing in it imports tezgah, so a path the uninstaller forgot
    fails here even when tezgah's own verify pass was never taught about it."""
    prelude = ""
    install_flags = "--no-deps"
    if DEPS:
        prelude = r"""
echo "== node =="
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq curl ca-certificates gnupg >/dev/null
curl -fsSL https://deb.nodesource.com/setup_22.x | bash - >/tmp/node-setup.log
apt-get install -y -qq nodejs >/dev/null
echo "node $(node --version), npm $(npm --version)"
"""
        install_flags = ""
    script = prelude + r"""
set -eu
export HOME=/root
setup=/src/bin/tezgah-setup
hosts=@HOSTS@

echo "== install =="
mkdir -p "$HOME/.codex" "$HOME/.omp" "$HOME/repos"
"$setup" --install --hosts "$hosts" @NO_DEPS@ --roots "$HOME/repos" >/tmp/install.log
test -f "$HOME/.config/tezgah/config.json"
grep -q tezgah "$HOME/.codex/hooks.json"
grep -q "mcp_servers.tezgah" "$HOME/.codex/config.toml"
test -f "$HOME/.omp/agent/RULES.md"
test -f "$HOME/.omp/agent/mcp.json"
test -f "$HOME/.omp/agent/hooks/pre/tezgah-hook.ts"
echo "OK: install armed codex and omp"

echo "== uninstall =="
"$setup" --uninstall --hosts "$hosts" >/tmp/uninstall.log
grep -q "uninstall complete" /tmp/uninstall.log
echo "OK: uninstall reported a complete removal"

echo "== independent leftover scan =="
python3 - <<'EOF'
import os, sys
home = os.environ.get("HOME", "/root")
def p(*parts):
    return os.path.join(home, *parts)
left = []
def gone(path):
    if os.path.lexists(path):
        left.append(path)
def clean(path):
    if os.path.lexists(path):
        with open(path, encoding="utf-8", errors="replace") as fh:
            if "tezgah" in fh.read():
                left.append(path + " (still wired)")
skills = ("harness", "tezgah-contract", "ponytail", "i-have-adhd",
          "no-ai-slop", "analyze-app", "plan-add", "plan-status",
          "plan-sync", "research", "product-analysis", "feature-audit",
          "pm-frameworks", "ai-research")
# codex
clean(p(".codex", "hooks.json"))
clean(p(".codex", "config.toml"))
for s in skills:
    gone(p(".codex", "skills", s))
gone(p(".codex", "bin", "consult"))
# omp
gone(p(".omp", "agent", "RULES.md"))
gone(p(".omp", "agent", "mcp.json"))
gone(p(".omp", "agent", "hooks", "pre", "tezgah-hook.ts"))
agents = p(".omp", "agent", "agents")
if os.path.isdir(agents):
    for name in os.listdir(agents):
        if name.startswith("tezgah-"):
            left.append(os.path.join(agents, name))
for s in skills:
    gone(p(".omp", "agent", "skills", s))
# shared state: a full run takes all of it
gone(p(".config", "tezgah"))
gone(p(".cache", "tezgah"))
gone("/tmp/tezgah")
gone(p(".local", "share", "tezgah"))
gone(p(".local", "bin", "dsh"))
if left:
    print("FAIL: %d leftover path(s):" % len(left))
    for path in left:
        print("  " + path)
    sys.exit(1)
print("OK: no tezgah path remains on disk")
EOF

echo "== reinstall from the clean state =="
"$setup" --install --hosts "$hosts" --no-deps --roots "$HOME/repos" >/tmp/install2.log
test -f "$HOME/.config/tezgah/config.json"
grep -q tezgah "$HOME/.codex/hooks.json"
test -f "$HOME/.omp/agent/RULES.md"
echo "OK: a second install arms from the clean state"
"""
    return script.replace("@NO_DEPS@", install_flags).replace("@HOSTS@", HOSTS)


def main():
    docker = shutil.which("docker")
    if not docker:
        return skipped("docker is not on PATH")
    info = subprocess.run([docker, "info"], capture_output=True, text=True)
    if info.returncode != 0:
        detail = ((info.stderr or info.stdout) or "").strip().splitlines()
        return skipped("the docker daemon is not reachable: %s"
                       % (detail[-1] if detail else "docker info failed"))
    # -i is what carries the script on stdin: without it bash -s reads an
    # empty stream, exits 0 immediately, and every assertion is skipped -
    # a false pass this file existed to make impossible.
    proc = subprocess.run([docker, "run", "--rm", "-i", "--volume",
                           "%s:/src:ro" % ROOT, IMAGE, "bash", "-s"],
                          input=inner_script(), capture_output=True, text=True)
    sys.stdout.write(proc.stdout)
    if proc.returncode != 0:
        print("FAIL: the container cycle exited %d\n%s"
              % (proc.returncode, proc.stderr))
        return 1
    print("OK: docker cycle passed (%s)" % IMAGE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
