#!/usr/bin/env python3
"""The layer's editable components: one manifest, and AHE's seven beside it.

AHE's first pillar gives every editable harness component a file-level,
revertible representation, so the action space of a refinement loop is explicit
rather than implied (arXiv 2604.25850). This module is that representation for
this layer: `COMPONENTS`, one entry per editable component, and `keys()`, the
list a prediction row may name.

One entry, six fields, each one a fact a reader can check against the file it
names (a test pins the fields against their own other definitions, so the
manifest cannot drift into being a second, stale copy of the rules):

- `key` - the name a prediction row uses. Unique.
- `label` - the `CORE_RULES` rule this component owns, or the surface name when
  it owns no rule. Every rule key appears exactly once.
- `files` - repository-relative paths the component lives in: a file, a
  directory, or a glob.
- `switch` - the kill switch (`~/.config/tezgah/<name>`) or per-repo mark (`.<name>`
  in the repo tree) whose presence drops this component's rule from the injected
  text, or `none` when it has neither. `none` is honest and not a claim of
  immutability: a broader switch such as `pretooluse-off` still turns off the
  enforcement of a rule that no switch removes.
- `editable` - whether the refinement loop may edit the component without a human
  grant: true exactly when every file it declares is outside `FROZEN_PATHS`
  (`hooks/tezgah_research.py`). A component that reaches a frozen file is false,
  because the loop may not change a rule's text while the checker that reads it
  moves underneath.
- `revert` - how a change is undone. `git` when git tracks the declared files;
  `snapshot` when the edit target is state git does not carry (the lessons
  ledger), where the only revert is the pre-write copy the gate's `capture`
  took, restored by `bin/tezgah-rollback`.

AHE's seven components, each row read from the paper's own list and pointed at
this repository. `not-owned` means the row exists here only as a mount or a
subscription, so no edit in this checkout changes it:

| AHE component | This repository |
|---|---|
| system prompt | owned - `hooks/tezgah_policy.py:613` (`CORE`), injected by `hooks/tezgah_context.py:596` (`core_for`) |
| tool descriptions | not-owned - each MCP server authors its own schema and this layer mounts it (`bin/tezgah-setup`); no text here reaches a model as a tool description |
| tool implementations | not-owned - the tool body runs inside the host CLI and this layer only refuses a call before it (`hooks/tezgah_gate.py:1581`) |
| middleware | not-owned - the host's own agent loop; this layer subscribes to the host's hook events and never sits in the loop |
| skills | owned - `skills/<name>/SKILL.md`, symlinked into each host's skill directory by `bin/tezgah-setup` |
| sub-agents | owned - `hooks/tezgah_agents.py:511` (`sync_root`) renders the per-host briefs |
| long-term memory | owned - `.tezgah/lessons.md`, read by `hooks/tezgah_context.py:369` (`lessons`), plus `.tezgah/plans/` in the repository |

The claim this table makes checkable is the one that was an argument before it:
AHE's ablation localizes the gain to tools, middleware and long-term memory, not
to the system prompt, and the reading offered was that those components sit
inside the host rather than in this layer. Two of the three are indeed the
host's - tools (descriptions and implementations) and middleware are
`not-owned` - and one is not: long-term memory is this layer's own, and its
ledger is a component here (`memory`, the one entry whose revert is a snapshot
rather than git). So the boundary is a row a reader can point at, not a
sentence to be re-argued.

Import nothing heavy: this module is standard library only and imports no other
tezgah module, because `hooks/tezgah_research.py` imports it lazily from a hot
path and the rule text's builder has no business being pulled in by a manifest.
"""

COMPONENTS = [
    {"key": "exec", "label": "exec",
     "files": ["hooks/tezgah_policy.py"],
     "switch": "exec-mode.off", "editable": True, "revert": "git"},
    {"key": "ponytail", "label": "ponytail",
     "files": ["hooks/tezgah_policy.py", "skills/ponytail/SKILL.md"],
     "switch": "ponytail-auto.off", "editable": True, "revert": "git"},
    {"key": "adhd", "label": "adhd",
     "files": ["hooks/tezgah_policy.py", "skills/i-have-adhd/SKILL.md"],
     "switch": "adhd-off", "editable": True, "revert": "git"},
    {"key": "fidelity", "label": "fidelity",
     "files": ["hooks/tezgah_policy.py"],
     "switch": "none", "editable": True, "revert": "git"},
    {"key": "integrity", "label": "integrity",
     "files": ["hooks/tezgah_policy.py", "hooks/tezgah_integrity.py"],
     "switch": "verify-off", "editable": False, "revert": "git"},
    {"key": "loop", "label": "loop",
     "files": ["hooks/tezgah_policy.py", "hooks/tezgah_gate.py"],
     "switch": "none", "editable": False, "revert": "git"},
    {"key": "safety", "label": "safety",
     "files": ["hooks/tezgah_policy.py", "hooks/tezgah_gate.py"],
     "switch": "none", "editable": False, "revert": "git"},
    {"key": "scope", "label": "scope",
     "files": ["hooks/tezgah_policy.py"],
     "switch": "none", "editable": True, "revert": "git"},
    {"key": "spec", "label": "spec",
     "files": ["hooks/tezgah_policy.py"],
     "switch": "spec-off", "editable": True, "revert": "git"},
    {"key": "lessons", "label": "lessons",
     "files": ["hooks/tezgah_policy.py", "hooks/tezgah_context.py"],
     "switch": ".no-lessons", "editable": True, "revert": "git"},
    {"key": "graph", "label": "graph",
     "files": ["hooks/tezgah_policy.py", "hooks/tezgah_gate.py"],
     "switch": ".no-graph", "editable": False, "revert": "git"},
    {"key": "consult", "label": "consult",
     "files": ["hooks/tezgah_policy.py", "bin/consult"],
     "switch": "consult-off", "editable": True, "revert": "git"},
    {"key": "research", "label": "research",
     "files": ["hooks/tezgah_policy.py", "hooks/tezgah_research.py",
               "bin/tezgah-research", ".tezgah/research/"],
     "switch": "research-off", "editable": False, "revert": "git"},
    {"key": "product", "label": "product",
     "files": ["hooks/tezgah_policy.py", "skills/product-analysis/SKILL.md",
               "skills/feature-audit/SKILL.md"],
     "switch": "research-off", "editable": True, "revert": "git"},
    {"key": "attribution", "label": "attribution",
     "files": ["hooks/tezgah_policy.py", "hooks/tezgah_gate.py"],
     "switch": "none", "editable": False, "revert": "git"},
    {"key": "lang", "label": "lang",
     "files": ["hooks/tezgah_policy.py", "hooks/tezgah_gate.py"],
     "switch": "lang-off", "editable": False, "revert": "git"},
    {"key": "skills", "label": "skills",
     "files": ["skills/"],
     "switch": "none", "editable": True, "revert": "git"},
    {"key": "subagents", "label": "subagents",
     "files": ["hooks/tezgah_agents.py"],
     "switch": "none", "editable": True, "revert": "git"},
    {"key": "memory", "label": "memory",
     "files": [".tezgah/lessons.md"],
     "switch": ".no-lessons", "editable": True, "revert": "snapshot"},
    # The gate's own advisory surface: the long-turn notice (`drift`) is not a
    # CORE paragraph, so it owns no rule label. It is declared with no switch of
    # its own: `reminder-off` does drop it, but declaring that would say the
    # manifest owns the per-turn reminder, and the switch test's own model reads
    # every declared switch as one that leaves the rest of the turn intact.
    # Added when the drift-notice experiment needed a component to name.
    {"key": "drift-notice", "label": "drift-notice",
     "files": ["hooks/tezgah_gate.py"],
     "switch": "none", "editable": False, "revert": "git"},
]


def keys():
    """The component keys, in manifest order: what a prediction row may name."""
    return [c["key"] for c in COMPONENTS]
