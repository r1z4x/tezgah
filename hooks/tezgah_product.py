"""The product-flow playbook (plan 074, ADR 025): the one place its steps are
written. `next_steps` computes each step's status from the topic's files under
`.tezgah/analysis/<topic>/` - `flow.md`, one `## <step>` heading per step, and
`spec.md` - and nothing stores it."""
import datetime
import os
import re

import tezgah_paths as tp

# A topic becomes a path below, so anything outside kebab-case reads no file.
TOPIC = re.compile(r"(?=.{1,64}\Z)[a-z0-9]+(?:-[a-z0-9]+)*")
OBSERVE = re.compile(r"observe after:\s*(\d{4}-\d{2}-\d{2})", re.I)


def _step(sid, skill, first=""):
    """A step whose artifact is its `## <sid>` note in flow.md; `first` is what
    the session does before writing it."""
    return {"id": sid, "skill": skill,
            "leaves": "## %s in .tezgah/analysis/<topic>/flow.md" % sid,
            "command": "%swrite ## %s in .tezgah/analysis/{topic}/flow.md"
                       % (first, sid)}


# `{topic}` in a command is filled per topic. The design check and the Stop UI
# rule judge design and build; the flow only asks for their note.
_STEPS = (
    _step("research", "research"),
    _step("metrics", "product-analysis"),
    _step("assumptions", "product-analysis"),
    _step("decision", "product-analysis"),
    _step("instrumentation", "product-analysis"),
    {"id": "forward-spec", "skill": "feature-audit",
     "leaves": ".tezgah/analysis/<topic>/spec.md",
     "command": "feature-audit forward mode: write .tezgah/analysis/{topic}/spec.md "
                "naming the decision"},
    _step("design", "design-contract", "tezgah-design check, then "),
    _step("build", "design-contract", "tezgah-design check, then "),
    _step("re-measure", "analyze-app", "measure the decision's metric again, then "),
)
FLOWS = {
    "metric-dashboard": _STEPS,
    # A feature may reuse a metric another topic owns: its own metric steps join
    # the flow only when its flow.md holds `## metrics` (`next_steps`).
    "feature": tuple(s for s in _STEPS if s["id"] not in ("metrics", "instrumentation")),
}


def _sections(text):
    """{step: body} of the `## <step>` headings in `text`, lower-cased."""
    parts = re.split(r"^##[ \t]+(.+?)[ \t]*$", text, flags=re.M)
    return {parts[i].lower(): parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def next_steps(repo, topic, flow="metric-dashboard", today=""):
    """[{"id", "skill", "status", "detail", "command"}] for `topic` under `flow`,
    status one of done | missing | due, read from `.tezgah/analysis/<topic>/` of
    `repo`. A topic outside TOPIC or with no folder lists every step missing."""
    if flow not in FLOWS:
        raise ValueError("unknown flow %r (%s)" % (flow, ", ".join(FLOWS)))
    try:
        day = datetime.date.fromisoformat(today) if today else datetime.date.today()
    except ValueError:
        raise ValueError("today %r is not YYYY-MM-DD" % (today,)) from None
    safe = isinstance(topic, str) and TOPIC.fullmatch(topic)
    rel = os.path.join(".tezgah", "analysis", topic if safe else "<topic>")
    folder = os.path.join(tp.workspace(repo), "analysis", topic) if safe else ""
    notes = _sections(_read(os.path.join(folder, "flow.md"))) if folder else {}
    flow_rel = os.path.join(rel, "flow.md")
    spec_rel = os.path.join(rel, "spec.md")
    steps = FLOWS["metric-dashboard"] if flow == "feature" and "metrics" in notes \
        else FLOWS[flow]

    def status(sid):
        if sid == "forward-spec":
            return ("done", "%s exists" % spec_rel) \
                if folder and os.path.isfile(os.path.join(folder, "spec.md")) \
                else ("missing", "%s does not exist" % spec_rel)
        if sid in notes:
            return "done", "%s ## %s" % (flow_rel, sid)
        if sid == "re-measure":
            after = OBSERVE.search(notes.get("decision", ""))
            try:
                when = datetime.date.fromisoformat(after.group(1)) if after else None
            except ValueError:
                when = None
            if when is not None:
                return ("due", "observe after %s has passed" % when) if day > when \
                    else ("missing", "observe after %s, not yet" % when)
            return "missing", "no observe after: in %s ## decision" % flow_rel
        return "missing", "no ## %s in %s" % (sid, flow_rel)

    out = []
    for s in steps:
        state, detail = status(s["id"])
        out.append({"id": s["id"], "skill": s["skill"], "status": state,
                    "detail": detail, "command": s["command"].format(
                        topic=topic if safe else "<topic>")})
    return out
