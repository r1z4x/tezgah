// tezgah opencode plugin: the opencode half of the tezgah contract.
//
// opencode has no stdout "inject context" hook, so the standing contract ships
// as `instructions` files that tezgah-setup generates from the shared policy
// (opencode-contract.md + opencode-skills.md). This plugin adds what those
// static files cannot:
//   - tool.execute.before + permission.ask: refuse a git/gh write that credits
//     an AI/model, block the first blind identifier search toward the code
//     graph, and refuse a grep-only explorer subagent. permission.ask is the
//     native allow/deny path where a build emits it; tool.execute.before is the
//     always-available fallback (1.18.30 never emits permission.ask, so the
//     fallback is what enforces today).
//   - shell.env: export the tezgah roots and paths into every shell call.
//   - experimental.session.compacting: restate the contract across compaction.
//   - tool.execute.after: record which tezgah tools a session used so
//     `tezgah-status` can show it.
//
// Every path fails open: if anything here throws unexpectedly, the tool runs.
// Hook names a given opencode build does not know are skipped by the runtime
// (Plugin.trigger does `if (!hook) continue`), so returning a hook that build
// lacks is safe and must never be a load-time error.
import { existsSync } from "node:fs"
import { appendFile, mkdir, readFile, writeFile } from "node:fs/promises"
import { spawn } from "node:child_process"
import { createHash } from "node:crypto"
import { homedir } from "node:os"
import { join } from "node:path"

const HOME = homedir()
const CONFIG = join(process.env.XDG_CONFIG_HOME || join(HOME, ".config"), "tezgah")
const CACHE = join(HOME, ".cache", "tezgah")
const CBM_DIR = join(HOME, ".cache", "codebase-memory-mcp")
const STATUS_BIN = join(CONFIG, "bin", "tezgah-status")
const INDEX_BIN = join(CONFIG, "bin", "tezgah-index")
const AGENTS_BIN = join(CONFIG, "bin", "tezgah-agents")
const SETUP_BIN = join(CONFIG, "bin", "tezgah-setup")
const IDENT = /^[A-Za-z_][A-Za-z0-9_]{2,}$/
const EXPLORE_DENY =
  "A grep-only explorer subagent is not allowed in this tree. Use a " +
  "general-purpose agent and name the codebase-memory-mcp graph tools " +
  "(search_graph, trace_path, search_code) in its prompt."
// The credit forms on a git/gh write, ported from hooks/tezgah_gate.py
// (WRITE_CMD/ATTRIB) so opencode enforces the same ban from the same shapes.
const ATTRIB =
  /co-authored-by\s*:|generated with|made with|built by|assisted by|authored by|noreply@anthropic|\u{1F916}/iu
const WRITE_CMD =
  /(?:^|[|;&]\s*|\s)git\s+(?:-{1,2}\S+(?:\s+\S+)?\s+)*(?:commit|merge|tag|notes)\b|(?:^|[|;&]\s*|\s)gh\s+api\b|(?:^|[|;&]\s*|\s)gh\s+(?:pr|issue|release)\s+(?:create|edit|comment|review|merge|close)\b/i
const ATTRIB_DENY =
  "Attribution is banned in every artifact tezgah touches. Remove the " +
  "Co-Authored-By / \"Generated with\" / robot-emoji / model-name credit from " +
  "the commit, PR, issue or review text and re-run. Naming a tool in order to " +
  "use it or describe real behavior is fine; crediting it as author is not."
// Anti-shortcut: a check neutered so it cannot fail, or a test disabled so a
// failure disappears. Ported from hooks/tezgah_integrity.py so opencode denies
// the same shapes from the same patterns.
const VERIFY =
  /(?:^|[|;&(]\s*|\s)(?:(?:python3?|uv run)\s+-m\s+(?:pytest|unittest|mypy|ruff|flake8|compileall)|pytest|py\.test|npm\s+(?:test|t\b)|npm\s+run\s+\S*(?:test|lint|typecheck|check|build|ci)|(?:yarn|pnpm|bun)\s+(?:test|run\s+\S*(?:test|lint|build|check))|ruff|flake8|mypy|pyright|tsc|eslint|prettier|vitest|jest|ava|mocha|go\s+(?:test|vet)|cargo\s+(?:test|clippy|check|build)|tox|nox|pre-commit|(?:^|\s)(?:make|just)\b|\.\/\S*(?:test|check|lint)\S*|(?:\.\/)?(?:gradlew|mvn)\s+\S*(?:test|check)|dotnet\s+(?:test|build)|swift\s+test|golangci-lint|shellcheck)\b/i
const NEUTER = /\|\|\s*(?:true|:|exit\s+0)(?:\s|$|[|;&])|;\s*true\s*(?:$|[|;&])/
const SKIP_ENV = /\b(?:SKIP|HUSKY_SKIP_HOOKS)\s*=|\bHUSKY=0\b/
const NO_VERIFY = /--no-verify\b/
const GITISH = /\b(?:git|commit|push|husky|pre-commit|npm|yarn|pnpm)\b/i
const SKIP_TEST = new RegExp(
  "@pytest\\.mark\\.(?:skip|skipif|xfail)|@pytest\\.mark\\.only|" +
  "@unittest\\.(?:skip|skipIf|expectedFailure)|@Ignore\\b|@Disabled\\b|" +
  "\\bpytest\\.skip\\(|\\bunittest\\.skip\\w*\\(|\\bt\\.Skip\\w*\\(|" +
  "\\b(?:it|test|describe)\\.(?:skip|only)\\(|\\bxit\\(|\\bxdescribe\\(|" +
  "\\bpytestmark\\s*=\\s*pytest\\.mark\\.skip", "gi")
const WRITE_TOOLS = new Set(["edit", "write", "multiedit", "notebookedit",
  "edit_file", "write_file", "search_replace"])
const BASH_TOOLS = new Set(["bash", "shell", "command"])

function verifyCommand(cmd) {
  const m = String(cmd || "").match(VERIFY)
  return m ? m[0] : null
}

function shortcutCommand(cmd) {
  const c = String(cmd || "")
  if (NO_VERIFY.test(c) && GITISH.test(c))
    return "Verification bypass denied: `--no-verify` skips the commit/push " +
      "hooks that run the checks. Run the checks, fix what they report, and " +
      "commit without it."
  if (SKIP_ENV.test(c))
    return "Verification bypass denied: an env var that skips the hooks " +
      "(SKIP=/HUSKY_SKIP_HOOKS/HUSKY=0) turns the checks off. Run them instead."
  if (verifyCommand(c) && NEUTER.test(c))
    return "Verification neutered: this check is chained with `|| true` / " +
      "`; true`, so it reports success no matter what it found. Run it plain " +
      "and read the real exit status."
  return null
}

function addedSkips(newText, oldText) {
  const before = new Set((String(oldText || "").match(SKIP_TEST) || [])
    .map((s) => s.toLowerCase()))
  const out = []
  for (const m of String(newText || "").matchAll(SKIP_TEST))
    if (!before.has(m[0].toLowerCase())) out.push(m[0])
  return out
}

async function shortcutEdit(args) {
  const oldText = String(args?.oldString ?? args?.old_string ?? "")
  const newText = String(
    args?.newString ?? args?.new_string ?? args?.content ?? "")
  if (!newText) return null
  let base = oldText
  if (!base) {
    const p = String(args?.filePath ?? args?.file_path ?? args?.path ?? "")
    if (p) { try { base = await readFile(expand(p), "utf8") } catch { base = "" } }
  }
  const added = addedSkips(newText, base)
  if (!added.length) return null
  return "Test disable denied: this change adds " +
    [...new Set(added)].join(", ") + ". Making a failing test disappear is not " +
    "a fix - fix the code or say the test is failing. Ask the user first if the " +
    "skip is genuinely intended."
}

// Evidence ledger, the same JSONL the Python gate and Stop hook read. Written
// per tool call so a "done/tested" claim can be checked against what ran.
// The bash tool returns `metadata.exit` (the process exit code), so a check's
// real outcome is available: exit 0 -> verify_ok, non-zero -> verify_fail, and
// `verify` only when the code is absent (aborted/spawn failure).
async function recordEvidence(sessionID, tool, args, metadata) {
  if (!sessionID) return
  const t = String(tool || "").toLowerCase()
  let kind = null
  if (WRITE_TOOLS.has(t)) kind = "edit"
  else if (BASH_TOOLS.has(t)) {
    if (!verifyCommand(args?.command || args?.cmd || "")) kind = "run"
    else {
      const exit = metadata?.exit
      kind = typeof exit === "number"
        ? (exit === 0 ? "verify_ok" : "verify_fail") : "verify"
    }
  }
  if (!kind) return
  const detail = String(
    args?.command || args?.filePath || args?.file_path || "").slice(0, 200)
  try {
    const dir = join(CACHE, "evidence")
    await mkdir(dir, { recursive: true })
    await appendFile(join(dir, slug(sessionID) + ".jsonl"),
      JSON.stringify({ kind, ts: Math.floor(Date.now() / 1000), detail }) + "\n")
  } catch {}
}

function attribution(tool, args) {
  const t = String(tool || "").toLowerCase()
  if (t !== "bash" && t !== "shell" && t !== "command") return false
  const cmd = String(args?.command || args?.cmd || "")
  return WRITE_CMD.test(cmd) && ATTRIB.test(cmd)
}
// Re-injected around compaction so the contract survives the summary.
const CONTRACT_REMINDER =
  "Tezgah contract still in force: reply Turkish, BLUF; code minimal per " +
  "ponytail (code first, max 3 note lines, `ponytail:` on any cut corner); " +
  "\"who calls X\" = codebase-memory-mcp trace_path/search_graph, not grep " +
  "alone; code-discovery subagents name the graph tools and are never " +
  "grep-only explorers; done/tested claims need observed evidence; no " +
  "AI/model attribution anywhere persisted or published."

function expand(p) {
  return String(p || "").replace(/^~(?=$|\/)/, HOME)
}

async function roots() {
  if (process.env.TEZGAH_ROOTS) {
    return process.env.TEZGAH_ROOTS.split(":").map(expand).filter(Boolean)
  }
  try {
    const cfg = JSON.parse(await readFile(join(CONFIG, "config.json"), "utf8"))
    if (Array.isArray(cfg.roots) && cfg.roots.length) return cfg.roots.map(expand)
  } catch {}
  return [join(HOME, "Projects")]
}

function under(dir, root) {
  return dir === root || dir.startsWith(root.endsWith("/") ? root : root + "/")
}

async function rootFor(dir) {
  for (const r of await roots()) if (under(dir, r)) return r
  return null
}

function off(name) {
  return existsSync(join(CONFIG, name)) || existsSync(join(HOME, ".claude", name))
}

function slug(p) {
  return p.replace(/[^A-Za-z0-9]+/g, "-").replace(/^-+|-+$/g, "")
}

// The nearest enclosing path that has a codebase-memory index db.
function indexSlug(dir) {
  let d = dir
  for (;;) {
    if (existsSync(join(CBM_DIR, slug(d) + ".db"))) return slug(d)
    const parent = d.replace(/\/[^/]+\/?$/, "")
    if (!parent || parent === d) return null
    d = parent
  }
}

function identifierFrom(tool, args) {
  if (tool === "grep") {
    const p = String(args.pattern || "")
    return IDENT.test(p) ? p : null
  }
  if (tool === "bash" || tool === "shell") {
    const cmd = String(args.command || "")
    const m = cmd.match(/(?:^|[|;&(]\s*|\s)(?:grep|rg)\s+((?:-\S+\s+)*)(\S+)/)
    if (!m) return null
    const tok = m[2].replace(/^['"]|['"]$/g, "")
    return IDENT.test(tok) ? tok : null
  }
  return null
}

// Best-effort view of a permission request as a {tool, args} pair. The payload
// shape drifts across opencode versions (the 1.17 plugin types use
// `type`/`pattern`; newer internal payloads use `permission`/`patterns`/
// `metadata`), so read every plausible field and bail out rather than guess.
// Conservative on purpose: a wrong match would deny an unrelated tool.
function permissionToolArgs(input) {
  const md =
    input && typeof input.metadata === "object" && input.metadata ? input.metadata : {}
  const kind = String(input?.type || input?.permission || md.tool || "").toLowerCase()
  const tool = String(md.tool || input?.tool || kind || "").toLowerCase()
  let patterns = input?.pattern ?? input?.patterns
  if (typeof patterns === "string") patterns = [patterns]
  if (!Array.isArray(patterns)) patterns = []
  const first = patterns.length ? String(patterns[0]) : ""
  const args = {
    pattern: md.pattern ?? md.patterns ?? first,
    command: md.command ?? md.cmd ?? "",
    subagent_type: md.subagent_type ?? md.subagent ?? "",
    agent: md.agent ?? md.subagent_type ?? "",
  }
  if (!args.command && /shell|bash|command/.test(kind)) {
    args.command = first || String(input?.title || "")
  }
  return { tool, args }
}

async function oncePerSession(sessionID) {  const key = createHash("sha1").update(String(sessionID || "nosession")).digest("hex").slice(0, 16)
  const dir = join(CACHE, "nudged")
  const mark = join(dir, key)
  if (existsSync(mark)) return false
  try {
    await mkdir(dir, { recursive: true })
    await writeFile(mark, "")
    return true // consume before denying: later greps pass
  } catch {
    return false
  }
}

async function record(sessionID, kind) {
  if (!sessionID || !kind) return
  try {
    const dir = join(CACHE, "sessions")
    await mkdir(dir, { recursive: true })
    await appendFile(join(dir, slug(sessionID) + ".jsonl"), JSON.stringify({ kind }) + "\n")
  } catch {}
}

function classify(tool, args) {
  const blob = tool + " " + JSON.stringify(args || {})
  if (/search_graph|trace_path|search_code|get_architecture|detect_changes|codebase.memory/.test(blob)) return "cbm"
  if (tool === "task") return "orch"
  if ((tool === "bash" || tool === "shell") && /consult/.test(blob)) return "consult"
  if ((tool === "bash" || tool === "shell") && /\borx\b/.test(blob)) return "research"
  return null
}

// The repo's generated subagents as opencode config.agent entries, or null.
// Runs the same Python source the other hosts use, so the gating and the bodies
// cannot drift.
function opencodeAgents(directory) {
  return new Promise((resolve) => {
    let out = ""
    let child
    try {
      child = spawn("python3", [AGENTS_BIN, "--json", directory],
                    { stdio: ["ignore", "pipe", "ignore"] })
    } catch {
      return resolve(null)
    }
    child.stdout.on("data", (d) => (out += d))
    child.on("error", () => resolve(null))
    child.on("close", () => {
      try { resolve(JSON.parse(out)) } catch { resolve(null) }
    })
  })
}

export const Tezgah = async ({ directory }) => {
  // installed under both plugin/ and plugins/ for opencode version drift; if
  // both are scanned, only the first module instance registers hooks
  if (globalThis.__tezgahPluginLoaded) return {}
  globalThis.__tezgahPluginLoaded = true
  const dir = directory || process.cwd()

  return {
    // Register the repo's generated subagents at config load so opencode sees
    // them in the SAME session (a brand-new .opencode/agents/ dir is otherwise
    // only read at the next launch). A user-defined agent of the same name wins.
    config: async (cfg) => {
      try {
        if (!cfg || typeof cfg !== "object") return
        if (off("agents-off")) return
        if (!(await rootFor(dir))) return
        const extra = await opencodeAgents(dir)
        const agents = (extra && extra.agent) || {}
        if (!Object.keys(agents).length) return
        const target = cfg.agent && typeof cfg.agent === "object"
          ? cfg.agent : (cfg.agent = {})
        for (const [name, spec] of Object.entries(agents)) {
          if (!(name in target)) target[name] = spec
        }
      } catch {}
    },

    // Native allow/deny where the build emits it. Inert (never called) on
    // builds that do not, which is exactly why the before-hook fallback stays.
    "permission.ask": async (input, output) => {
      try {
        if (!output || typeof output !== "object") return
        if (off("pretooluse-off")) return
        if (!(await rootFor(dir))) return
        const { tool, args } = permissionToolArgs(input)
        const sessionID = input?.sessionID || input?.sessionId
        const sub = String(args.subagent_type || args.agent || "")
        if (attribution(tool, args)) {
          output.status = "deny"
          return
        }
        if (/task|agent|subagent/.test(tool) && /explore/i.test(sub)) {
          output.status = "deny"
          return
        }
        if (identifierFrom(tool, args)) {
          const js = indexSlug(dir)
          if (js && (await oncePerSession(sessionID))) output.status = "deny"
        }
      } catch {}
    },

    "tool.execute.before": async (input, output) => {
      let deny = null
      try {
        if (off("pretooluse-off")) return
        const base = await rootFor(dir)
        if (!base) return
        const tool = String(input?.tool || "").toLowerCase()
        const args = output?.args || input?.args || {}
        const sessionID = input?.sessionID || input?.sessionId

        const sub = String(args.subagent_type || args.agent || "")
        if (attribution(tool, args)) {
          deny = ATTRIB_DENY
        } else if (tool === "task" && /explore/i.test(sub)) {
          deny = EXPLORE_DENY
        } else if (BASH_TOOLS.has(tool)) {
          deny = shortcutCommand(args.command || args.cmd || "")
        } else if (WRITE_TOOLS.has(tool)) {
          deny = await shortcutEdit(args)
        } else if (identifierFrom(tool, args)) {
          const js = indexSlug(dir)
          // oncePerSession is shared with permission.ask so exactly one of the
          // two hooks consumes the nudge, whichever the build runs first.
          if (js && (await oncePerSession(sessionID))) {
            deny =
              `Code graph index is ready for this repo (${js}). For a definition, ` +
              "its callers or blast radius use the codebase-memory-mcp search_graph / " +
              "trace_path tools. If you need literal text, re-run this search unchanged; " +
              "it will pass - this nudge fires once per session."
          }
        }
      } catch {}
      if (deny) throw new Error(deny)
    },

    // Every shell call (tool or user terminal) sees the same tezgah roots, and
    // the session id so a shell-run `tezgah-status` can light up the used marks.
    "shell.env": async (input, output) => {
      try {
        if (!output || typeof output !== "object") return
        const env = output.env && typeof output.env === "object" ? output.env : (output.env = {})
        const rs = await roots()
        if (rs.length) env.TEZGAH_ROOTS = rs.join(":")
        env.TEZGAH_HOME = CONFIG
        env.TEZGAH_STATUS_BIN = STATUS_BIN
        if (input && input.sessionID) env.TEZGAH_SESSION = String(input.sessionID)
      } catch {}
    },

    // Keep the contract alive when a long session is compacted.
    "experimental.session.compacting": async (input, output) => {
      try {
        if (!output || typeof output !== "object") return
        const context = Array.isArray(output.context) ? output.context : (output.context = [])
        context.push(CONTRACT_REMINDER)
      } catch {}
    },

    // Every other host runs the graph auto-index from its SessionStart hook.
    // opencode has no session-lifecycle hook that can run the Python contract,
    // so the first user message of a session triggers it once, detached: the
    // index runs in the background and never blocks the turn.
    "chat.message": async (input) => {
      try {
        if (!(await rootFor(dir))) return
        const sessionID = String(input?.sessionID || "")
        // per-repo agent file fallback: same one-shot entry as the index, so a
        // changed manifest or repo stack is rewritten once per session
        if (await oncePerSession(sessionID + "|agents")) {
          spawn("python3", [AGENTS_BIN, dir], { detached: true, stdio: "ignore" }).unref()
        }
        // re-render the contract if the policy or the full-contract skill changed
        // since the last --install; opencode has no session-start hook to do it
        if (await oncePerSession(sessionID + "|contract")) {
          spawn("python3", [SETUP_BIN, "--refresh"], { detached: true, stdio: "ignore" }).unref()
        }
        if (!(await oncePerSession(sessionID + "|index"))) return
        spawn("python3", [INDEX_BIN, dir], { detached: true, stdio: "ignore" }).unref()
      } catch {}
    },

    "tool.execute.after": async (input, output) => {
      try {
        if (!(await rootFor(dir))) return
        const tool = String(input?.tool || "").toLowerCase()
        const args = input?.args || output?.args || {}
        const kind = classify(tool, args)
        if (kind) await record(input?.sessionID || input?.sessionId, kind)
        await recordEvidence(input?.sessionID || input?.sessionId, tool, args,
                             output?.metadata)
      } catch {}
    },

    // TODO(custom tool): a `tool()` export (e.g. a direct tezgah-status call)
    // would need `import { tool } from "@opencode-ai/plugin"`. That package
    // resolves from a config-local node_modules that may not exist at runtime,
    // and a failed static import would break the whole plugin at load. Not
    // shipped until that resolution is confirmed on each host; the CLI
    // (TEZGAH_STATUS_BIN) is the safe path today.
  }
}
