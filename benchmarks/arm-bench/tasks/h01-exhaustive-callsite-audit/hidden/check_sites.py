#!/usr/bin/env python3
"""Score the call-site audit against the tree's own AST.

The key is (path, line, enclosing, callee): which sites exist, which line each
one starts on, and which scope owns it. The argument text is printed by the
answer but not compared - copying a dict literal exactly tests typing, not
analysis, while the nested call on report.py:22 (two callees, one line, one
scope) is exactly the analysis this task is about.

Runs in the candidate tree, so it reads whatever the agent left behind.
"""
import ast
import os
import re
import sys

TARGETS = ("calc_total", "apply_discount", "parse_quantity")
SKIP = {"__pycache__", ".git", ".pytest_cache", ".ruff_cache"}

LINE = re.compile(r"^\s*(?P<path>[^\s:]+):(?P<line>\d+)\s+(?P<enclosing>\S+)\s*::\s*"
                  r"(?P<callee>[A-Za-z_][\w.]*)\s*\(")


def callee_of(node: ast.Call):
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


class Sites(ast.NodeVisitor):
    """Collect call sites with the scope that encloses them."""

    def __init__(self, path: str):
        self.path = path
        self.scopes: list[str] = []
        self.sites: set[tuple] = set()

    def _visit_def(self, node):
        name = node.name
        if self.scopes and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # a method: qualify it with the class the visitor is inside
            last = self.scopes[-1]
            if last and last[0].isupper():
                name = "%s.%s" % (last, name)
        self.scopes.append(name)
        self.generic_visit(node)
        self.scopes.pop()

    visit_FunctionDef = _visit_def
    visit_AsyncFunctionDef = _visit_def
    visit_ClassDef = _visit_def

    def visit_Call(self, node: ast.Call):
        callee = callee_of(node)
        if callee in TARGETS:
            enclosing = self.scopes[-1] if self.scopes else "module"
            self.sites.add((self.path, node.lineno, enclosing, callee))
        self.generic_visit(node)


def truth(root: str) -> set[tuple]:
    found: set[tuple] = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP]
        for name in filenames:
            if not name.endswith(".py"):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            with open(full, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), filename=rel)
            visitor = Sites(rel)
            visitor.visit(tree)
            found |= visitor.sites
    return found


def main() -> int:
    root = os.getcwd()
    answer = os.path.join(root, "ANSWER.md")
    if not os.path.exists(answer):
        print("no ANSWER.md")
        return 1
    with open(answer, encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    said = set()
    for line in lines:
        match = LINE.match(line)
        if match:
            said.add((match["path"], int(match["line"]), match["enclosing"], match["callee"]))
    if not said:
        print("ANSWER.md carries no '<path>:<line> <enclosing> :: <callee>(...)' line")
        return 1

    expected = truth(root)
    misses = sorted(expected - said)
    extra = sorted(said - expected)
    print("expected %d sites, answered %d" % (len(expected), len(said)))
    print("precision %.2f recall %.2f"
          % (len(said & expected) / len(said), len(said & expected) / len(expected)))
    for path, line, enclosing, callee in misses:
        print("missing: %s:%d %s :: %s" % (path, line, enclosing, callee))
    for path, line, enclosing, callee in extra:
        print("not a call site: %s:%d %s :: %s" % (path, line, enclosing, callee))
    return 0 if not misses and not extra else 1


if __name__ == "__main__":
    raise SystemExit(main())
