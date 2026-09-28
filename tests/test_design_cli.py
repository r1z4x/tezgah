"""bin/tezgah-design: the derivation and the check that can fail.

The contract is the per-repo floor a UI turn is judged against, so the two
things that matter are mechanical: `derive` reads the repository's OWN token
source and invents nothing (it exits 2 rather than write a palette nobody
chose), and `check` fails on a measurement that disagrees with the file. Each
case runs the real CLI in a subprocess - the exit code and the printed count are
the deliverable - and the state set the checker carries is pinned equal to the
three lists the repository already ships, because a fourth copy with no pin is
how the set drifts.
"""
import importlib.machinery
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(REPO, "bin", "tezgah-design")

# The interactive and data halves of the shipped set, in the order the contract
# writes them, and the thirteen distinct states the two share: `loading` and
# `error` are named in both halves.
INTERACTIVE = ("default", "hover", "focus", "active", "disabled", "loading",
               "error")
DATA = ("empty", "loading", "skeleton", "error", "offline", "partial",
        "long-text", "permission-denied")
STATES = INTERACTIVE + tuple(s for s in DATA if s not in INTERACTIVE)

# A repository whose only token source is a hand-written CSS file: the shape
# `derive` must read without a model and without a design system.
TOKENS_CSS = """:root {
  --color-text: #111111;
  --color-surface: #ffffff;
  --color-accent: #0b5fff;
  --space-unit: 4px;
  --font-size-sm: 14px;
  --font-size-md: 16px;
}

.button { color: var(--color-text); background: var(--color-surface); }
"""

TAILWIND = """module.exports = {
  theme: {
    extend: {
      colors: { ink: '#111111', paper: '#ffffff', brand: '#0b5fff' },
      spacing: { unit: '4px' },
      fontSize: { sm: '14px', md: '16px' },
    },
  },
};
"""


def load_cli():
    """bin/tezgah-design as a module, for the constants its tests pin."""
    name = "tezgah_design_under_test"
    loader = importlib.machinery.SourceFileLoader(name, CLI)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def contract_json(source="css-custom-properties", colors=None, space=4,
                  type_scale=(14, 16), components=(), states=True):
    """The machine half of a contract, in the shape the CLI writes."""
    data = {
        "version": 1,
        "source": source,
        "tokens": {
            "space_unit": space,
            "type_scale": list(type_scale),
            "colors": colors if colors is not None else {
                "text": "#111111", "surface": "#ffffff", "accent": "#0b5fff"},
            "tap_target": 24,
            "contrast": {"normal": 4.5, "large": 3.0},
        },
        "components": [{"name": n, "kind": k} for n, k in components],
    }
    if states:
        data["states"] = {"interactive": list(INTERACTIVE), "data": list(DATA)}
    return data


def contract_md(data, header="source: css-custom-properties\n"):
    return ("# Design contract\n\n" + header +
            "\nThe floor this repository's screens are judged against.\n\n"
            "```json\n" + json.dumps(data, indent=2, sort_keys=True)
            + "\n```\n")


def measurement(components):
    return {"components": components}


def clean_component(name="Button", kind="interactive", **styles):
    base = {"font-size": "16px", "padding": "8px 12px", "gap": "8px",
            "color": "#111111", "background-color": "#ffffff",
            "width": "120px", "height": "40px"}
    base.update(styles)
    return {"name": name, "kind": kind,
            "states": list(STATES),
            "styles": base}


class DesignCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)

    def path(self, *parts):
        return os.path.join(self.dir, *parts)

    def write(self, rel, text):
        path = self.path(rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def read(self, path):
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    def write_json(self, rel, data):
        return self.write(rel, json.dumps(data, indent=2))

    def run_cli(self, *argv):
        return subprocess.run([sys.executable, CLI] + list(argv),
                              capture_output=True, text=True)

    def contract(self, data, header="source: css-custom-properties\n"):
        return self.write("contract.md", contract_md(data, header))


class Derive(DesignCase):
    """`derive` writes the contract from the repository's own tokens, and exits
    2 rather than invent one when there is nothing to read."""

    def test_a_css_custom_property_block_is_read_and_written(self):
        self.write("app/styles/tokens.css", TOKENS_CSS)
        proc = self.run_cli("derive", "--repo", self.dir, "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = self.path(".tezgah", "design-contract.md")
        self.assertTrue(os.path.isfile(out), "no contract written")
        report = json.loads(proc.stdout)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["source"], "css-custom-properties")
        data = json.loads(re.search(r"```json\n(.*?)\n```",
                                    self.read(out), re.S).group(1))
        self.assertEqual(data["tokens"]["colors"]["text"], "#111111")
        self.assertEqual(data["tokens"]["colors"]["accent"], "#0b5fff")
        self.assertEqual(data["tokens"]["space_unit"], 4)
        self.assertEqual(data["tokens"]["type_scale"], [14, 16])
        self.assertEqual(data["source"], "css-custom-properties")
        self.assertEqual(data["components"], [])
        self.assertEqual(data["states"]["interactive"], list(INTERACTIVE))

    def test_a_tailwind_config_is_a_token_source_too(self):
        self.write("tailwind.config.js", TAILWIND)
        proc = self.run_cli("derive", "--repo", self.dir, "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["source"], "tailwind-config")
        text = self.read(self.path(".tezgah", "design-contract.md"))
        self.assertIn("#0b5fff", text)

    def test_a_tokens_json_is_a_token_source_too(self):
        self.write_json("design-tokens.json", {
            "color": {"text": "#111111", "surface": "#ffffff", "brand": "#0b5fff"},
            "spacing": {"2": "8px", "4": "16px"},
            "fontSize": {"sm": "14px", "md": "16px"}})
        proc = self.run_cli("derive", "--repo", self.dir, "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["source"], "theme-json")
        text = self.read(self.path(".tezgah", "design-contract.md"))
        self.assertIn("#0b5fff", text)
        self.assertIn('"space_unit": 8', text)

    def test_an_out_path_is_honoured(self):
        self.write("styles/tokens.css", TOKENS_CSS)
        out = self.path("docs", "floor.md")
        proc = self.run_cli("derive", "--repo", self.dir, "--out", out)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(os.path.isfile(out))
        self.assertFalse(os.path.exists(self.path(".tezgah")))

    def test_an_existing_contract_is_not_overwritten(self):
        # the inventory someone filled in is the reason: a re-derive would drop
        # every component row with it
        self.write("styles/tokens.css", TOKENS_CSS)
        out = self.path(".tezgah", "design-contract.md")
        self.write(".tezgah/design-contract.md", "hand-written, keep me\n")
        proc = self.run_cli("derive", "--repo", self.dir)
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("already exists", proc.stderr)
        self.assertEqual(self.read(out), "hand-written, keep me\n")

    def test_a_repo_with_no_token_source_exits_2_and_writes_nothing(self):
        self.write("src/main.js", "export const x = 1\n")
        proc = self.run_cli("derive", "--repo", self.dir)
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("token source", proc.stderr)
        self.assertFalse(os.path.exists(self.path(".tezgah")),
                         "a contract was written for a repo with no tokens")

    def test_the_json_failure_is_machine_readable(self):
        proc = self.run_cli("derive", "--repo", self.dir, "--json")
        self.assertEqual(proc.returncode, 2)
        report = json.loads(proc.stdout)
        self.assertFalse(report["ok"])
        self.assertIn("token source", report["error"])


class Check(DesignCase):
    """`check` compares a measurement - the per-component styles and states the
    analyze-app loop produces - against the contract, and every disagreement is
    a violation that names its rule."""

    def check(self, data, measured, *argv):
        return self.run_cli("check", "--contract", self.contract(data),
                            "--measured", self.write_json("measured.json", measured),
                            *argv)

    def test_a_conforming_measurement_exits_0(self):
        data = contract_json(components=[("Button", "interactive")])
        proc = self.check(data, measurement([clean_component()]))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("0 violations", proc.stdout)

    def test_an_off_rhythm_padding_names_the_spacing_rule(self):
        data = contract_json(components=[("Button", "interactive")])
        proc = self.check(data, measurement([clean_component(padding="10px")]))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("spacing-rhythm", proc.stdout)
        self.assertIn("Button", proc.stdout)
        self.assertIn("4px spacing unit", proc.stdout)

    def test_a_colour_outside_the_palette_names_the_palette_rule(self):
        data = contract_json(components=[("Button", "interactive")])
        proc = self.check(data, measurement(
            [clean_component(**{"background-color": "#ff00ff"})]))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("palette", proc.stdout)
        self.assertIn("#ff00ff", proc.stdout)

    def test_a_face_outside_the_type_scale_names_the_type_rule(self):
        data = contract_json(components=[("Button", "interactive")])
        proc = self.check(data, measurement([clean_component(**{"font-size": "18px"})]))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("type-scale", proc.stdout)

    def test_a_missing_state_names_the_state_rule_and_the_states(self):
        data = contract_json(components=[("Button", "interactive")])
        comp = clean_component()
        comp["states"] = ["default", "hover"]
        proc = self.check(data, measurement([comp]))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("state-coverage", proc.stdout)
        self.assertIn("focus", proc.stdout)

    def test_a_control_below_the_wcag_touch_floor_is_a_violation(self):
        data = contract_json(components=[("Button", "interactive")])
        proc = self.check(data, measurement([clean_component(height="20px")]))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("tap-target", proc.stdout)
        self.assertIn("24", proc.stdout)

    def test_unreadable_text_on_its_own_background_is_a_contrast_violation(self):
        data = contract_json(components=[("Button", "interactive")],
                             colors={"text": "#111111", "surface": "#ffffff",
                                     "accent": "#eeeeee"})
        proc = self.check(data, measurement(
            [clean_component(color="#eeeeee", **{"background-color": "#ffffff"})]))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("contrast", proc.stdout)

    def test_a_component_outside_the_inventory_is_a_violation(self):
        data = contract_json(components=[("Button", "interactive")])
        proc = self.check(data, measurement([clean_component(name="Card")]))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("component-inventory", proc.stdout)
        self.assertIn("Card", proc.stdout)

    def test_a_contract_that_weakens_the_state_set_is_refused(self):
        data = contract_json(components=[("Button", "interactive")])
        data["states"]["interactive"] = ["default"]
        proc = self.check(data, measurement([clean_component()]))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("state-set", proc.stdout)

    def test_a_contract_with_no_source_line_is_refused(self):
        # the machine half is where the `source` lives: a header alone cannot say
        # whether the floor was read from this repository or invented
        data = contract_json(source="", components=[("Button", "interactive")])
        proc = self.check(data, measurement([clean_component()]))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("contract-source", proc.stdout)

    def test_a_derived_contract_is_a_contract(self):
        # the no-design-system path: nothing was read, and the file says so
        data = contract_json(source="derived",
                             components=[("Button", "interactive")])
        proc = self.check(data, measurement([clean_component()]))
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_the_json_report_carries_the_count_and_every_rule(self):
        data = contract_json(components=[("Button", "interactive")])
        proc = self.check(data, measurement([clean_component(padding="10px")]),
                          "--json")
        self.assertEqual(proc.returncode, 1)
        report = json.loads(proc.stdout)
        self.assertFalse(report["ok"])
        self.assertEqual(report["count"], len(report["violations"]))
        self.assertTrue(report["count"] >= 1)
        self.assertEqual(report["violations"][0]["component"], "Button")
        self.assertIn(report["violations"][0]["rule"],
                      ("spacing-rhythm", "state-coverage"))

    def test_the_json_report_of_a_clean_measurement_is_ok(self):
        data = contract_json(components=[("Button", "interactive")])
        proc = self.check(data, measurement([clean_component()]), "--json")
        self.assertEqual(proc.returncode, 0)
        report = json.loads(proc.stdout)
        self.assertTrue(report["ok"])
        self.assertEqual(report["count"], 0)
        self.assertEqual(report["violations"], [])

    def test_a_value_the_contract_cannot_judge_is_counted_not_passed(self):
        data = contract_json(components=[("Button", "interactive")])
        proc = self.check(data, measurement([clean_component(gap="1em")]),
                          "--json")
        report = json.loads(proc.stdout)
        self.assertEqual(report["count"], 0, report)
        self.assertTrue(report["unjudged"] >= 1, report)

    def test_a_missing_contract_or_measurement_is_a_usage_error(self):
        proc = self.run_cli("check", "--contract", self.path("nope.md"),
                            "--measured", self.path("nope.json"))
        self.assertEqual(proc.returncode, 2, proc.stdout)


class StateSetPin(unittest.TestCase):
    """The 13 states already live in three places. The checker is a fourth
    reader of the same set, so the four are pinned equal here instead of
    drifting apart one edit at a time."""

    def read(self, rel):
        with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_the_checker_carries_the_shipped_set(self):
        mod = load_cli()
        self.assertEqual(tuple(mod.STATES_INTERACTIVE), INTERACTIVE)
        self.assertEqual(tuple(mod.STATES_DATA), DATA)
        self.assertEqual(tuple(mod.STATES), STATES)
        self.assertEqual(len(STATES), 13)

    def test_tezgah_triage_carries_the_same_set(self):
        text = self.read(os.path.join("bin", "tezgah-triage"))
        block = re.search(r"^STATES = \((.*?)\)", text, re.S | re.M)
        self.assertIsNotNone(block, "bin/tezgah-triage has no STATES tuple")
        self.assertEqual(tuple(re.findall(r'"([^"]+)"', block.group(1))), STATES)

    def test_product_analysis_carries_the_same_set(self):
        text = self.read(os.path.join("skills", "product-analysis", "SKILL.md"))
        row = next(line for line in text.splitlines()
                   if "interactive: default" in line)
        body = [c.strip() for c in row.split("|")][3]
        interactive, data = body.split("; data:")
        # `long-text/overflow` is the same state said at more length
        self.assertEqual(tuple(s.strip().split("/")[0] for s in
                               interactive.split(":", 1)[1].split(",")),
                         INTERACTIVE)
        self.assertEqual(tuple(s.strip().split("/")[0] for s in data.split(",")),
                         DATA)

    def test_the_product_rule_carries_the_same_set(self):
        text = self.read(os.path.join("hooks", "tezgah_policy.py"))
        block = re.search(r"\((default, hover, focus.*?permission-denied)\)",
                          text, re.S)
        self.assertIsNotNone(block, "the PRODUCT paragraph lost its state set")
        flat = re.sub(r"\s+", " ", block.group(1))
        interactive, data = flat.split("; ")
        self.assertEqual(tuple(s.strip() for s in interactive.split(",")),
                         INTERACTIVE)
        # the paragraph names `loading` and `error` once, in the interactive
        # half, and does not repeat them in the data half: those two are the
        # only states it may leave implicit, and every other member must be
        # there in the shipped order.
        data = tuple(s.strip() for s in data.split(","))
        shared = ("loading", "error")
        self.assertEqual(tuple(s for s in DATA if s not in data), shared)
        self.assertEqual(data, tuple(s for s in DATA if s not in shared))


if __name__ == "__main__":
    unittest.main()
