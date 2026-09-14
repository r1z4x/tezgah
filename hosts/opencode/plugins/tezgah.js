// tezgah opencode plugin: the opencode half of the tezgah contract.
//
// opencode has no stdout "inject context" hook, so the standing contract ships
// as a managed block in ~/.config/opencode/AGENTS.md (written by tezgah-setup
// from the shared policy). This plugin adds what AGENTS.md cannot:
//   - tool.execute.before + permission.ask: block the first blind identifier
//     search toward the code graph, and refuse a grep-only explorer subagent.
//     permission.ask is the native allow/deny path where a build emits it;
//     tool.execute.before is the always-available fallback (1.18.30 never
//     emits permission.ask, so the fallback is what enforces today).
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
const IDENT = /^[A-Za-z_][A-Za-z0-9_]{2,}$/
const EXPLORE_DENY =
  "A grep-only explorer subagent is not allowed in this tree. Use a " +
  "general-purpose agent and name the codebase-memory-mcp graph tools " +
  "(search_graph, trace_path, search_code) in its prompt."
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

async function oncePerSession(sessionID) {
  const key = createHash("sha1").update(String(sessionID || "nosession")).digest("hex").slice(0, 16)
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
  return null
}

export const Tezgah = async ({ directory }) => {
  // installed under both plugin/ and plugins/ for opencode version drift; if
  // both are scanned, only the first module instance registers hooks
  if (globalThis.__tezgahPluginLoaded) return {}
  globalThis.__tezgahPluginLoaded = true
  const dir = directory || process.cwd()

  return {
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
        if (tool === "task" && /explore/i.test(sub)) {
          deny = EXPLORE_DENY
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
        if (!(await oncePerSession(sessionID + "|index"))) return
        spawn("python3", [INDEX_BIN, dir], { detached: true, stdio: "ignore" }).unref()
      } catch {}
    },

    "tool.execute.after": async (input, output) => {
      try {
        if (!(await rootFor(dir))) return
        const tool = String(input?.tool || "").toLowerCase()
        const kind = classify(tool, output?.args || input?.args || {})
        if (kind) await record(input?.sessionID || input?.sessionId, kind)
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
