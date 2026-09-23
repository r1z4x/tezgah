# E4 - does the probe carry the detection, or the prose?

## What changes

The E3 arm is the control: three rater contexts that applied the frozen artifact
with no instruction about how to gather evidence. This experiment adds a fourth and
fifth context that apply the **same artifact text**, differing in exactly one
instruction: they must run the probe below before filling the capability matrix, and
record its output as the matrix's evidence.

## The probe (arm B's raters run this verbatim)

```sh
cd /Users/rizax/Projects/Ustam && python3 - <<'PY'
import json, re, subprocess, pathlib
spec = json.loads(pathlib.Path("docs/openapi.json").read_text())
api = {f"{m.upper()} {p.replace('/api/v1','')}" for p, ops in spec["paths"].items()
       for m in ops if m.lower() in ("get","post","patch","put","delete")}
files = subprocess.run(["bash","-lc","grep -rloE 'adminApi\\(' apps/admin/app apps/admin/lib "
                        "--include=*.ts --include=*.tsx"],capture_output=True,text=True).stdout.split()
surface = set()
for f in files:
    t = pathlib.Path(f).read_text()
    for m in re.finditer(r"adminApi\(\s*[`']([^`']+)", t):
        p = m.group(1)
        if p.startswith("/users"):
            tail = t[m.end():m.end()+200]
            meth = "POST" if "'POST'" in tail or '"POST"' in tail else ("PATCH" if "'PATCH'" in tail or '"PATCH"' in tail else "GET")
            surface.add(f"{meth} /users{p[len('/users'):]}")
norm = lambda k: re.sub(r"\$\{[^}]+\}", "{id}", k)
c = {norm(k) for k in api if k.split(' ')[1].startswith("/users")}
s = {norm(k) for k in surface}
print("contract-only:", sorted(c - s))
print("surface-only:", sorted(s - c))
PY
```

It reads the API's committed contract and the surface's call sites and prints the set
difference in both directions: endpoints no surface reaches, and surface calls no
endpoint declares.

## Method

Two rater contexts, same feature, same blindness rules as E3, briefed identically
except for the probe step. Scored against the same frozen corpus, per class.

## Predicts

Arm A (the three E3 raters) and arm B detect the *same* classes: the artifact's
matrices already force the comparison the probe performs, so a rater that fills the
capability matrix by reading reaches the same two declared-and-unreached rows the
probe reports. A difference of one class or more in arm B's favour is evidence for
H4; no difference is evidence that the probe is a convenience rather than a
mechanism, and the skill should say so.

## Falsification criterion

Arm B detecting a class arm A did not, by a margin that survives adjudication of the
bundled rows, would falsify the prediction - and would be reported as support for H4
rather than as a surprise. Arm B detecting fewer classes would falsify H4 outright.

## Why

H4 claims a mechanism, not a paragraph. The control is the arm that already exists
(same artifact, same feature, same model family, three contexts), so the ablation
costs two rater contexts instead of six, and the difference between the arms is one
instruction.
