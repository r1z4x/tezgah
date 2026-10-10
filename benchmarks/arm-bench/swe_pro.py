#!/usr/bin/env python3
"""Idea 190: an unsaturated SWE-Bench Pro split for arm-bench (arXiv 2509.16941).

    swe_pro.py sample --out <sample.json> --n N --seed S [--max-image-mb M]
    swe_pro.py grade --sample <sample.json> --instance I --container C [--log F]
    swe_pro.py validate --sample <sample.json> [--keep-images]

Data: the public V2 split of ScaleAI/SWE-bench_Pro (Hugging Face config
`default`, 642 tasks), read through the datasets-server rows API. The verifier
files the dataset does not carry (tests/test.sh, run_script.sh, parser.py) come
from the official harness, scaleapi/SWE-bench_Pro-os, at a pinned commit.
Grading runs that verifier unchanged inside the instance container: test.sh
resets the test surface, applies the test patch, runs run_script.sh over
selected_test_files_to_run, parses the output with parser.py and exits 0 only
when every fail_to_pass and pass_to_pass test passed. `validate` grades each
instance's base tree (must fail) and base + gold patch (must pass). No model is
called anywhere.
"""
from __future__ import annotations

import argparse
import ast
import functools
import json
import random
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import swe

DATASET, CONFIG = "ScaleAI/SWE-bench_Pro", "default"
ROWS = ("https://datasets-server.huggingface.co/rows?dataset={}&config={}"
        "&split=test&offset={}&length=100")
HARNESS = "66f92766bba642462d4bbe5479e83f91f9211862"  # SWE-bench_Pro-os release/v2.0.0 merge
RAW = "https://raw.githubusercontent.com/scaleapi/SWE-bench_Pro-os/{}/v2/tasks/{}/tests/{}"
VERIFIER = ("test.sh", "run_script.sh", "parser.py")
VERIFY_TIMEOUT = 3000  # task.toml [verifier] timeout_sec
MANIFEST_TYPES = ",".join([
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json"])


def fetch(url: str, headers: dict | None = None) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=120) as r:
        return r.read()


# ------------------------------------------------------------------ sample

def dataset_rows() -> list[dict]:
    rows, offset, total = [], 0, None
    while total is None or offset < total:
        page = json.loads(fetch(ROWS.format(DATASET, CONFIG, offset)))
        total = page["num_rows_total"]
        for r in page["rows"]:
            if r.get("truncated_cells"):
                raise RuntimeError(f"row {r['row']['instance_id']}: truncated {r['truncated_cells']}")
            rows.append(r["row"])
        offset += 100
    return rows


@functools.cache
def registry_token(host: str, repo: str) -> str:
    return json.loads(fetch(f"https://{host}/token?scope=repository:{repo}:pull"))["token"]


def image_mb(image: str) -> int:
    """Compressed linux/amd64 size of a public GHCR image: the bytes a pull downloads."""
    host, _, ref = image.partition("/")
    repo, _, tag = ref.rpartition(":")
    hdr = {"Authorization": f"Bearer {registry_token(host, repo)}", "Accept": MANIFEST_TYPES}

    def manifest(r: str) -> dict:
        return json.loads(fetch(f"https://{host}/v2/{repo}/manifests/{r}", hdr))
    m = manifest(tag)
    if "manifests" in m:
        m = manifest(next(d["digest"] for d in m["manifests"] if d.get("platform", {}).get(
            "architecture") == "amd64" and d["platform"].get("os") == "linux"))
    return round(sum(layer["size"] for layer in m["layers"]) / 1e6)


def entry(row: dict, mb: int) -> dict:
    iid = row["instance_id"]
    with ThreadPoolExecutor(len(VERIFIER)) as ex:
        files = dict(zip(VERIFIER, ex.map(lambda f: fetch(RAW.format(HARNESS, iid, f)).decode(), VERIFIER)))
    selected = json.loads(row["selected_test_files_to_run"])
    return {"instance_id": iid, "repo": row["repo"], "repo_language": row["repo_language"],
            "base_commit": row["base_commit"], "image": row["docker_image"], "image_mb": mb,
            "test_patch": row["test_patch"], "gold_patch": row["patch"],
            "fail_to_pass": json.loads(row["fail_to_pass"]),
            "pass_to_pass": json.loads(row["pass_to_pass"]),
            "selected_test_files": selected,
            "run_command": "bash /tests/run_script.sh " + ",".join(selected),
            "harness": HARNESS, "verifier": files}


def cmd_sample(args) -> int:
    """N instances in one seeded order over the split, skipping any image over
    --max-image-mb (compressed), so a small sample keeps its downloads small."""
    rows = {r["instance_id"]: r for r in dataset_rows()}
    ids = sorted(rows)
    random.Random(args.seed).shuffle(ids)
    with ThreadPoolExecutor(16) as ex:
        sizes = dict(zip(ids, ex.map(lambda i: image_mb(rows[i]["docker_image"]), ids)))
    keep = [i for i in ids if not args.max_image_mb or sizes[i] <= args.max_image_mb][:args.n]
    out = [entry(rows[i], sizes[i]) for i in keep]
    Path(args.out).write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(f"sample: {len(out)} of {len(rows)} instances, seed {args.seed}, "
          f"max image {args.max_image_mb or '-'} MB: {[e['instance_id'] for e in out]}")
    return 0 if len(out) == args.n else 1


# ------------------------------------------------------------------ grading

def tests_dir(inst: dict) -> dict[str, str]:
    """The verifier's /tests directory, as the harness task ships it."""
    config = {k: inst[k] for k in ("fail_to_pass", "pass_to_pass")}
    config["selected_test_files_to_run"] = inst["selected_test_files"]
    return {**inst["verifier"], "test_patch.patch": inst["test_patch"],
            "config.json": json.dumps(config)}


def grade(container: str, inst: dict, log: Path | None = None) -> dict:
    """The official verifier over the tree in `container`; exit 0 is resolved.
    `failed` is True only when the verifier itself reached its verdict
    (`RESULT: FAILED`), and `missing` is the required tests it reports absent, so
    a crashed parser or a failed write is never read as a failing tree."""
    for name, body in tests_dir(inst).items():
        wrote = swe.sh(["docker", "exec", "-i", container, "sh", "-c",
                        f"mkdir -p /tests && cat > /tests/{name}"], input=body)
        if wrote.returncode:
            raise RuntimeError(f"write /tests/{name}: {wrote.stderr.strip()[-300:]}")
    started = time.time()
    try:
        proc = swe.sh(["docker", "exec", container, "bash", "/tests/test.sh"], timeout=VERIFY_TIMEOUT)
        rc, out = proc.returncode, proc.stdout + "\n--- stderr ---\n" + proc.stderr
    except subprocess.TimeoutExpired as exc:
        partial = exc.stdout or b""
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", "replace")
        rc, out = None, partial + "\n--- verifier timeout ---"
    if log:
        log.write_text(out, encoding="utf-8")
    missing = re.search(r"^Missing tests: (\[.*\])\s*$", out, re.M)
    return {"rc": rc, "pass": rc == 0, "eval_s": round(time.time() - started, 1),
            "failed": rc == 1 and "RESULT: FAILED" in out,
            "missing": ast.literal_eval(missing.group(1)) if missing else []}


def start(image: str, name: str) -> None:
    """The instance image as is: the repository sits at its base commit in /app
    (or /testbed). The verifier keeps network access, as task.toml grants it."""
    swe.remove_container(name)
    proc = swe.sh(["docker", "run", "-d", "--platform", swe.PLATFORM, "--name", name,
                   "--entrypoint", "sleep", image, "infinity"])
    if proc.returncode:
        raise RuntimeError(f"docker run {name}: {proc.stderr.strip()[-300:]}")


def apply_gold(container: str, inst: dict) -> bool:
    """solution/solve.sh: git apply, else patch --fuzz=5."""
    swe.sh(["docker", "exec", "-i", container, "sh", "-c", "cat > /tmp/gold.diff"],
           input=inst["gold_patch"])
    return not swe.sh(["docker", "exec", container, "bash", "-c",
                       "cd /app 2>/dev/null || cd /testbed; git apply /tmp/gold.diff"
                       " || patch --fuzz=5 -p1 -i /tmp/gold.diff"]).returncode


def load(path: str) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cmd_grade(args) -> int:
    inst = {e["instance_id"]: e for e in load(args.sample)}[args.instance]
    res = grade(args.container, inst, Path(args.log) if args.log else None)
    print(f"{args.instance}: {show(res)}")
    return 0 if res["pass"] else 1


def show(res: dict) -> str:
    return f"{'PASS' if res['pass'] else 'FAIL'} (rc {res['rc']}, {res['eval_s']}s)"


def cmd_validate(args) -> int:
    sample, valid = load(args.sample), 0
    logs = Path(args.logs)
    logs.mkdir(parents=True, exist_ok=True)
    for inst in sample:
        iid, image = inst["instance_id"], inst["image"]
        pulled = bool(swe.sh(["docker", "image", "inspect", image]).returncode)
        if pulled:
            proc = swe.sh(["docker", "pull", "-q", "--platform", swe.PLATFORM, image], timeout=3600)
            if proc.returncode:
                print(f"{iid}: pull failed: {proc.stderr.strip()[-300:]}")
                continue
        res = {}
        try:
            for case in ("base", "gold"):
                name = f"swepro-{case}-{iid[-12:]}"
                try:
                    start(image, name)
                    if case == "gold" and not apply_gold(name, inst):
                        res[case] = {"rc": None, "pass": False, "eval_s": 0,
                                     "failed": False, "missing": []}
                        continue
                    res[case] = grade(name, inst, logs / f"{iid}-{case}.log")
                finally:
                    swe.remove_container(name)
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            print(f"{iid}: error: {exc}")
            res = {}
        finally:
            note = ""
            if pulled and not args.keep_images:
                size = swe.sh(["docker", "image", "inspect", "--format", "{{.Size}}",
                               image]).stdout.strip()
                swe.sh(["docker", "image", "rm", "-f", image])
                note = f"  (pulled {int(size or 0) / 1e9:.2f} GB, removed)"
        if len(res) < 2:
            print(f"{iid}: INVALID (not graded){note}", flush=True)
            continue
        # the base has to fail the verifier's own verdict on fail_to_pass tests
        # only: a crash, a timeout or a pass_to_pass miss is not a valid base
        base = res["base"]
        ok = (res["gold"]["pass"] and base["failed"] and base["missing"]
              and set(base["missing"]) <= set(inst["fail_to_pass"]))
        valid += bool(ok)
    print(f"validated: {valid}/{len(sample)}")
    return 0 if valid == len(sample) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("sample")
    p.add_argument("--out", required=True)
    p.add_argument("--n", type=int, required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--max-image-mb", type=int, default=0)
    p.set_defaults(func=cmd_sample)
    p = sub.add_parser("grade")
    p.add_argument("--sample", required=True)
    p.add_argument("--instance", required=True)
    p.add_argument("--container", required=True)
    p.add_argument("--log")
    p.set_defaults(func=cmd_grade)
    p = sub.add_parser("validate")
    p.add_argument("--sample", required=True)
    p.add_argument("--keep-images", action="store_true")
    p.add_argument("--logs", default=str(Path(swe.bench.RUN_ROOT) / "swe-pro-validate"))
    p.set_defaults(func=cmd_validate)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
