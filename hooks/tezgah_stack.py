#!/usr/bin/env python3
"""The effective stack each host loads on this machine, and where it collides.

`tezgah-doctor --stack` prints it. For every host it lists, in the host's own
load order: the context files that exist, the skill dirs and which copy of a
skill name wins, the hook commands per event with their owner (tezgah, Orca, a
user's own), and the MCP servers. Then it flags what the owner otherwise finds
out by hand when omp, Claude Code, Codex, Cursor and opencode run side by side:

  - skill-differs   one host reads two skills of one name whose SKILL.md
                    differ; the copy that wins is named (first-wins hosts)
  - skill-dup       the same skill reached twice through two dirs one host reads
  - skill-stale     a shipped tezgah skill whose copy is not this tree's bytes
  - rule-twice      two context files one host loads both carry the tezgah block
  - backup-in-scan  a `.tezgah-bak` inside a dir the host enumerates
  - hook-twice      one host runs tezgah's same hook command twice for one event
  - mcp-twice       one host reads two definitions of one MCP server name

The load orders are the hosts' documented ones (docs/hosts.md#precedence), not
a probe of a running session: this module reads files and runs nothing.
Read-only, stdlib only.
"""
import hashlib
import json
import os
import re

import tezgah_paths as tp

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEZGAH_SKILLS = os.path.join(HERE, "skills")
BLOCK = "<!-- tezgah:start -->"
OWNERS = (("tezgah", "tezgah"), ("orca", "orca"), ("ORCA_", "orca"),
          ("codegraph", "codegraph"))


def _read(path, limit=None):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read(limit) if limit else fh.read()
    except OSError:
        return ""


def _json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _digest(path):
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()[:12]
    except OSError:
        return None


def owner(command):
    text = str(command)
    return next((name for key, name in OWNERS if key in text), "other")


def yaml_list(text, key):
    """The `- item` lines under `key:` in a block-style YAML file. omp's
    config.yml is the only YAML read here, and only for two string lists."""
    out, indent = [], None
    for line in text.splitlines():
        m = re.match(r"^(\s*)%s:\s*$" % re.escape(key), line)
        if m:
            indent = len(m.group(1))
            continue
        if indent is None:
            continue
        item = re.match(r"^(\s*)-\s+(.+?)\s*$", line)
        if item and len(item.group(1)) >= indent:
            out.append(item.group(2).strip("\"'"))
        elif line.strip():
            break
    return out


def toml_tables(text, prefix):
    """Names of `[prefix.<name>]` tables in a TOML file (Codex's MCP rows)."""
    return sorted({m.group(1) for m in re.finditer(
        r"^\[%s\.([A-Za-z0-9_-]+)\]" % re.escape(prefix), text, re.M)})


def hook_rows(data, source, who=None):
    """{event: [(owner, source, matcher + command)]} from a Claude/Codex/Cursor
    hooks object. `who` names the owner of every row (a plugin's own hooks
    file). One command under two matchers answers two different tool sets, so
    the matcher is part of what makes a row a duplicate."""
    out = {}
    hooks = data.get("hooks", {})
    for event, groups in (hooks.items() if isinstance(hooks, dict) else []):
        for group in groups if isinstance(groups, list) else []:
            entries = (group.get("hooks") or [group]) if isinstance(group, dict) else []
            matcher = str(group.get("matcher") or "") if isinstance(group, dict) else ""
            for entry in entries:
                if isinstance(entry, dict) and entry.get("command"):
                    cmd = str(entry["command"])
                    key = "%s %s" % (matcher, cmd) if matcher else cmd
                    out.setdefault(event, []).append((who or owner(cmd), source, key))
    return out


def merge_hooks(*parts):
    out = {}
    for part in parts:
        for event, rows in part.items():
            out.setdefault(event, []).extend(rows)
    return out


def claude_plugin():
    """(root of the tezgah plugin copy Claude loads, every tezgah copy on disk)."""
    plugins = os.path.join(tp.HOST_DIRS["claude"], "plugins")
    rows = _json(os.path.join(plugins, "installed_plugins.json")).get("plugins") or {}
    active = next((r[-1].get("installPath") for k, r in rows.items()
                   if k.split("@")[0] == "tezgah" and r), None)
    cache = os.path.join(plugins, "cache")
    copies = []
    for market in sorted(os.listdir(cache)) if os.path.isdir(cache) else []:
        base = os.path.join(cache, market, "tezgah")
        if os.path.isdir(base):
            copies += [os.path.join(base, v) for v in sorted(os.listdir(base))]
    return active, copies


def host_stack(host, repo):
    """{context, skills: (mode, [dir]), hooks, mcp, scan} for one host.

    `mode` is `first` when the host keeps the first copy of a name, `all` when
    it lists every copy (Codex says so; Cursor documents no winner). `scan` is
    every dir the host enumerates, where a stray backup is one more entry."""
    h = tp.HOME
    agents_user = os.path.join(h, ".agents", "skills")
    agents_repo = os.path.join(repo, ".agents", "skills")
    if host == "claude":
        c = tp.HOST_DIRS["claude"]
        active, _ = claude_plugin()
        plugin_hooks = hook_rows(_json(os.path.join(active, "hooks", "hooks.json")),
                                 "plugin", "tezgah") if active else {}
        mcp = sorted(_json(os.path.join(h, ".claude.json")).get("mcpServers") or {})
        mcp += ["%s (project)" % n for n in sorted(
            _json(os.path.join(repo, ".mcp.json")).get("mcpServers") or {})]
        if active:
            mcp += ["%s (plugin)" % n for n in sorted(
                _json(os.path.join(active, ".mcp.json")).get("mcpServers") or {})]
        return {
            "context": [os.path.join(c, "CLAUDE.md"), os.path.join(repo, "CLAUDE.md"),
                        os.path.join(repo, ".claude", "CLAUDE.md"),
                        os.path.join(repo, "CLAUDE.local.md")],
            "skills": ("first", [os.path.join(repo, ".claude", "skills"),
                                 os.path.join(c, "skills")]),
            "hooks": merge_hooks(
                hook_rows(_json(os.path.join(c, "settings.json")), "settings.json"),
                hook_rows(_json(os.path.join(repo, ".claude", "settings.json")), "project"),
                plugin_hooks),
            "mcp": mcp,
            "scan": [os.path.join(c, "agents"), os.path.join(c, "skills"),
                     os.path.join(c, "commands")],
        }
    if host == "codex":
        c = tp.HOST_DIRS["codex"]
        user = os.path.join(c, "AGENTS.override.md")
        return {
            "context": [user if os.path.isfile(user) else os.path.join(c, "AGENTS.md"),
                        os.path.join(repo, "AGENTS.md")],
            "skills": ("all", [agents_repo, agents_user, os.path.join(c, "skills")]),
            "hooks": merge_hooks(
                hook_rows(_json(os.path.join(c, "hooks.json")), "hooks.json"),
                hook_rows(_json(os.path.join(repo, ".codex", "hooks.json")), "project")),
            "mcp": toml_tables(_read(os.path.join(c, "config.toml")), "mcp_servers"),
            "scan": [os.path.join(c, "skills"), os.path.join(c, "rules"),
                     os.path.join(c, "prompts")],
        }
    if host == "cursor":
        c = tp.HOST_DIRS["cursor"]
        rules = os.path.join(repo, ".cursor", "rules")
        return {
            "context": [os.path.join(repo, "AGENTS.md"), os.path.join(repo, ".cursorrules")]
            + sorted(os.path.join(rules, n) for n in (
                os.listdir(rules) if os.path.isdir(rules) else []) if n.endswith(".mdc")),
            # Cursor's documented order; it names no winner for a shared name
            "skills": ("all", [agents_repo, os.path.join(repo, ".cursor", "skills"),
                               agents_user, os.path.join(c, "skills"),
                               os.path.join(repo, ".claude", "skills"),
                               os.path.join(repo, ".codex", "skills"),
                               os.path.join(h, ".claude", "skills"),
                               os.path.join(h, ".codex", "skills")]),
            "hooks": merge_hooks(
                hook_rows(_json(os.path.join(c, "hooks.json")), "hooks.json"),
                hook_rows(_json(os.path.join(repo, ".cursor", "hooks.json")), "project")),
            "mcp": sorted(_json(os.path.join(c, "mcp.json")).get("mcpServers") or {}),
            "scan": [os.path.join(c, "skills"), rules],
        }
    if host == "opencode":
        c = tp.HOST_DIRS["opencode"]
        conf = _json(os.path.join(c, "opencode.json"))
        plugins = []
        for d in ("plugins", "plugin"):
            p = os.path.join(c, d)
            plugins += [(n, d) for n in sorted(os.listdir(p) if os.path.isdir(p) else [])
                        if n.endswith((".js", ".ts"))]
        return {
            "context": [os.path.join(c, "AGENTS.md")]
            + [p for p in conf.get("instructions") or [] if isinstance(p, str)]
            + [os.path.join(repo, "AGENTS.md")],
            # tezgah denies opencode's native skill tool; its router reads these, first wins
            "skills": ("first", [os.path.join(c, "skills"), os.path.join(h, ".claude", "skills"),
                                 agents_user]),
            "hooks": {"plugin (every event)": [(owner(n), "%s/%s" % (d, n), n)
                                               for n, d in plugins]},
            "mcp": sorted(conf.get("mcp") or {}),
            "scan": [os.path.join(c, "skills"), os.path.join(c, "plugins"),
                     os.path.join(c, "plugin")],
        }
    if host == "omp":
        a = os.path.join(tp.HOST_DIRS["omp"], "agent")
        conf = _read(os.path.join(a, "config.yml"))
        enabled = set(yaml_list(conf, "enabledProviders"))
        custom = yaml_list(conf, "customDirectories")
        skills = list(custom) + [os.path.join(repo, ".omp", "skills"),
                                 os.path.join(a, "skills"),
                                 os.path.join(repo, ".claude", "skills")]
        if "claude" in enabled or os.environ.get("CLAUDE_CONFIG_DIR"):
            skills.append(os.path.join(h, ".claude", "skills"))
        skills += [agents_repo, agents_user]
        if "codex" in enabled:
            skills.append(os.path.join(h, ".codex", "skills"))
        ext_dir = os.path.join(a, "extensions")
        found = sorted(os.path.join(ext_dir, n) for n in (
            os.listdir(ext_dir) if os.path.isdir(ext_dir) else []) if n.endswith((".ts", ".js")))
        configured = [os.path.expanduser(p) for p in yaml_list(conf, "extensions")]
        order = found + [p for p in configured if p not in found]
        hooks = {"extension (every event)": [(owner(p), p, p) for p in order]}
        for kind in ("pre", "post"):
            d = os.path.join(a, "hooks", kind)
            listed = sorted(os.listdir(d)) if os.path.isdir(d) else []
            if listed:
                hooks["hooks/%s capability" % kind] = [
                    (owner(n), n + ("" if n.endswith((".ts", ".js")) else " (listed, not loaded)"), n)
                    for n in listed if not n.startswith(".")]
        mcp = sorted(_json(os.path.join(a, "mcp.json")).get("mcpServers") or {})
        return {
            "context": [os.path.join(a, "SYSTEM.md"), os.path.join(a, "APPEND_SYSTEM.md"),
                        os.path.join(a, "RULES.md"), os.path.join(repo, ".omp", "AGENTS.md"),
                        os.path.join(repo, "AGENTS.md"), os.path.join(repo, "CLAUDE.md")]
            + ([os.path.join(h, ".claude", "CLAUDE.md")] if "claude" in enabled else []),
            "skills": ("first", skills),
            "hooks": hooks,
            "mcp": mcp,
            "scan": [os.path.join(a, "agents"), os.path.join(a, "skills"),
                     os.path.join(a, "hooks", "pre"), os.path.join(a, "hooks", "post"),
                     os.path.join(a, "rules"), ext_dir],
        }
    if host == "dsh":
        c = tp.HOST_DIRS["dsh"]
        return {"context": [os.path.join(c, "cordis.patch.yml")],
                "skills": ("first", [os.path.join(c, "skills")]),
                "hooks": {}, "mcp": [], "scan": [os.path.join(c, "skills")]}
    raise ValueError(host)


def skill_copies(dirs):
    """[(name, dir, sha of SKILL.md, realpath)] in dir order."""
    out = []
    for d in dirs:
        for name in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            path = os.path.join(d, name, "SKILL.md")
            if os.path.isfile(path):
                out.append((name, d, _digest(path), os.path.realpath(path)))
    return out


def tezgah_skill_dirs():
    """The dirs tezgah-setup links its skills into, plus the plugin copy's."""
    dirs = [os.path.join(tp.HOST_DIRS[x], "skills") for x in ("codex", "cursor", "opencode", "dsh")]
    dirs.append(os.path.join(tp.HOST_DIRS["omp"], "agent", "skills"))
    active, _ = claude_plugin()
    return dirs + ([os.path.join(active, "skills")] if active else [])


def conflicts(host, stack, repo):
    """[(kind, detail)] for one host's stack."""
    out = []
    mode, dirs = stack["skills"]
    by_name = {}
    for name, d, sha, real in skill_copies(dirs):
        by_name.setdefault(name, []).append((d, sha, real))
    shipped = set(os.listdir(TEZGAH_SKILLS)) if os.path.isdir(TEZGAH_SKILLS) else set()
    if host == "claude":
        active, _ = claude_plugin()
        for name, d, sha, real in skill_copies([os.path.join(active, "skills")] if active else []):
            by_name.setdefault("tezgah:" + name, []).append((d, sha, real))
    owned = tezgah_skill_dirs()
    for name, copies in sorted(by_name.items()):
        bare = name.split(":", 1)[-1]
        if bare in shipped:
            want = _digest(os.path.join(TEZGAH_SKILLS, bare, "SKILL.md"))
            out += [("skill-stale", "%s in %s differs from %s" % (bare, d, TEZGAH_SKILLS))
                    for d, sha, _real in copies if d in owned and sha != want]
        if len(copies) < 2:
            continue
        where = ", ".join(d for d, _s, _r in copies)
        if len({sha for _d, sha, _r in copies}) > 1:
            win = copies[0][0] if mode == "first" else "no documented winner"
            out.append(("skill-differs", "%s: %s (wins: %s)" % (name, where, win)))
        elif mode == "all":
            # a first-wins host collapses identical copies; a list-all host shows each
            out.append(("skill-dup", "%s: %s" % (name, where)))
    for event, rows in sorted(stack["hooks"].items()):
        mine = [cmd for who, _src, cmd in rows if who == "tezgah"]
        twice = sorted({cmd for cmd in mine if mine.count(cmd) > 1})
        if twice and "every event" not in event:
            out.append(("hook-twice", "%s: %s" % (event, ", ".join(twice))))
    names = [n.split(" (")[0] for n in stack["mcp"]]
    out += [("mcp-twice", "%s: %s" % (n, ", ".join(m for m in stack["mcp"]
                                                  if m.split(" (")[0] == n)))
            for n in sorted(set(names)) if names.count(n) > 1]
    carrying = [p for p in stack["context"] if BLOCK in _read(p)]
    if len(carrying) > 1:
        out.append(("rule-twice", ", ".join(carrying)))
    for d in stack["scan"]:
        for root, dirnames, files in os.walk(d) if os.path.isdir(d) else []:
            dirnames[:] = [] if root.count(os.sep) - d.count(os.sep) >= 1 else dirnames
            out += [("backup-in-scan", os.path.join(root, n))
                    for n in sorted(files) if n.endswith(".tezgah-bak")]
    if host == "claude":
        active, copies = claude_plugin()
        out += [("orphan-copy", p) for p in copies
                if active and os.path.realpath(p) != os.path.realpath(active)]
    return out


def report(repo, hosts=None):
    """{host: stack + conflicts} for the installed hosts (or `hosts`)."""
    repo = os.path.abspath(repo)
    out = {}
    for host in hosts or [h for h in tp.HOST_DIRS if tp.host_installed(h)]:
        stack = host_stack(host, repo)
        mode, dirs = stack["skills"]
        copies = skill_copies(dirs)
        out[host] = {
            "context": [p for p in stack["context"] if os.path.isfile(p)],
            "skill_mode": mode,
            "skill_dirs": [(d, sum(1 for c in copies if c[1] == d))
                           for d in dirs if os.path.isdir(d)],
            "skills": len({c[0] for c in copies}),
            "hooks": stack["hooks"],
            "mcp": stack["mcp"],
            "conflicts": conflicts(host, stack, repo),
        }
    return out


def render(data):
    lines = []
    for host, s in data.items():
        lines.append("== %s" % host)
        lines.append("  context (load order):")
        lines += ["    %s" % p for p in s["context"]] or ["    (none)"]
        lines.append("  skills: %d names, %s copy wins" % (
            s["skills"], "first" if s["skill_mode"] == "first" else "no single"))
        lines += ["    %4d  %s" % (n, d) for d, n in s["skill_dirs"]]
        lines.append("  hooks:")
        for event, rows in sorted(s["hooks"].items()):
            lines.append("    %-28s %s" % (event, " -> ".join(
                "%s[%s]" % (who, src) for who, src, _cmd in rows)))
        lines.append("  mcp: %s" % (", ".join(s["mcp"]) or "(none)"))
        counts = {}
        for kind, _ in s["conflicts"]:
            counts[kind] = counts.get(kind, 0) + 1
        lines.append("  conflicts: %s" % (", ".join(
            "%s=%d" % kv for kv in sorted(counts.items())) or "none"))
        lines += ["    %s  %s" % kv for kv in s["conflicts"]]
    return "\n".join(lines)
