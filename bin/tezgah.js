#!/usr/bin/env node
// bin/tezgah.js - npm's bin entry: finds a Python interpreter and execs
// bin/tezgah-setup with every argument passed through. npm resolves this
// symlink to the global prefix, so process.argv[1] is the shim, not the target.
const { spawn } = require("child_process");
const { existsSync } = require("fs");
const path = require("path");

const here = __dirname;
const setup = path.join(here, "tezgah-setup");
if (!existsSync(setup)) {
  process.stderr.write("tezgah: " + setup + " not found\n");
  process.exit(1);
}

const candidates = process.env.TEZGAH_PYTHON
  ? [process.env.TEZGAH_PYTHON]
  : ["python3", "python3.12", "python3.11", "python3.10", "python"];

const py = candidates.find(c => {
  try { require("child_process").execSync(c + " -c ''", { stdio: "ignore" }); return true; }
  catch (_) { return false; }
});

if (!py) {
  process.stderr.write("tezgah: no python interpreter found (looked for: " + candidates.join(", ") + ")\n");
  process.exit(1);
}

const child = spawn(py, [setup, ...process.argv.slice(2)], { stdio: "inherit" });
child.on("exit", code => process.exit(code));
