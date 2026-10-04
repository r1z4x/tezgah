#!/usr/bin/env python3
"""End-to-end check: the tezgah status line renders in the real dsh Web UI.

Boots `dsh --profile web`, opens it in headless Chromium (Playwright), opens the
first persisted session from the sidebar, and asserts the tezgah status string
appears in the session header and that /api/tezgah.status answered 200.

Opt-in local check, not collected by the stdlib suite (name does not match
`test*.py`): it needs dsh, Playwright with a Chromium build, and at least one
persisted session. It exits 0 with "SKIP: ..." when one of those is missing, and
1 only on a real render failure.

    python3 tests/e2e_dsh_statusline.py
"""
import glob
import os
import shutil
import subprocess
import sys
import threading


def dsh_bin():
    for p in (shutil.which("dsh"),
              os.path.expanduser("~/.local/bin/dsh"),
              os.path.expanduser("~/.config/tezgah/bin/dsh")):
        if p and os.path.exists(p):
            return p
    return None


def chromium_executable():
    """A cached Playwright Chromium headless shell, when the installed
    Playwright revision does not match its own download."""
    patterns = [
        "~/Library/Caches/ms-playwright/chromium_headless_shell-*/"
        "chrome-headless-shell-*/chrome-headless-shell",
        "~/.cache/ms-playwright/chromium_headless_shell-*/"
        "chrome-headless-shell-linux64/chrome-headless-shell",
        "~/.cache/ms-playwright/chromium_headless_shell-*/"
        "chrome-linux/chrome-headless-shell",
    ]
    for pattern in patterns:
        hits = sorted(glob.glob(os.path.expanduser(pattern)))
        if hits:
            return hits[-1]
    return None


def boot_web(dsh):
    """Start dsh web on an ephemeral port and return (process, token URL)."""
    proc = subprocess.Popen(
        [dsh, "--profile", "web", "--port", "0", "--no-open"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    found = {}

    def read_url():
        for line in proc.stdout:
            if "?token=" in line:
                found["url"] = line.split()[-1]
                return

    thread = threading.Thread(target=read_url, daemon=True)
    thread.start()
    thread.join(60)
    if "url" not in found:
        proc.terminate()
        return None, None
    return proc, found["url"]


def render_check(page):
    """Open a session and return the rendered status line, or None."""
    page.wait_for_timeout(6000)
    rows = page.locator('div[class*="sessionRow"]')
    target = None
    for i in range(rows.count()):
        first = rows.nth(i).inner_text().strip().splitlines()
        if first and first[0].strip() != "New Session":
            target = first[0].strip()
            break
    if not target:
        return "no-session"
    page.get_by_text(target, exact=False).first.click(timeout=5000)
    for _ in range(20):
        page.wait_for_timeout(1000)
        for line in page.inner_text("body").splitlines():
            if "pony" in line and "idx" in line:
                return line.strip()
    return None


def run():
    dsh = dsh_bin()
    if not dsh:
        return "SKIP: dsh not installed"
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "SKIP: playwright not installed"
    proc, url = boot_web(dsh)
    if not url:
        return "FAIL: dsh web did not print a URL"
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except Exception:
                exe = chromium_executable()
                if not exe:
                    return "SKIP: no Chromium (run `playwright install chromium`)"
                browser = p.chromium.launch(headless=True, executable_path=exe)
            try:
                page = browser.new_page()
                statuses = []
                page.on("response", lambda r: statuses.append(r.status)
                        if "/api/tezgah.status" in r.url else None)
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                rendered = render_check(page)
                if rendered == "no-session":
                    return "SKIP: no persisted session in the sidebar"
                if not rendered:
                    return "FAIL: status line never rendered in the session header"
                if 200 not in statuses:
                    return "FAIL: /api/tezgah.status was never answered 200"
                return "PASS: rendered %r" % rendered
            finally:
                browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def main():
    result = run()
    print(result)
    return 0 if result.startswith(("PASS", "SKIP")) else 1


if __name__ == "__main__":
    sys.exit(main())
