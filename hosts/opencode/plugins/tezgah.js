// tezgah opencode plugin: the opencode half of the tezgah contract.
//
// opencode has no stdout "inject context" hook, so the standing contract ships
// as a managed block in ~/.config/opencode/AGENTS.md (written by tezgah-setup
// from the shared policy). This plugin adds what AGENTS.md cannot: blocking the
// first blind identifier search toward the code graph, and recording which
// tezgah tools a session used so `tezgah-status` can show it.
//
// Every path fails open: if anything here throws unexpectedly, the tool runs.
import { existsSync } from "node:fs"
import { appendFile, mkdir, readFile, writeFile } from "node:fs/promises"
import { createHash } from "node:crypto"
import { homedir } from "node:os"
import { join } from "node:path"

const HOME = homedir()
const CONFIG = join(process.env.XDG_CONFIG_HOME || join(HOME, ".config"), "tezgah")
const CACHE = join(HOME, ".cache", "tezgah")
const CBM_DIR = join(HOME, ".cache", "codebase-memory-mcp")
const IDENT = /^[A-Za-z_][A-Za-z0-9_]{2,}$/

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
    "tool.execute.before": async (input, output) => {
      if (off("pretooluse-off")) return
      const base = await rootFor(dir)
      if (!base) return
      const tool = String(input?.tool || "").toLowerCase()
      const args = output?.args || input?.args || {}
      const sessionID = input?.sessionID || input?.sessionId

      const sub = String(args.subagent_type || args.agent || "")
      if (tool === "task" && /explore/i.test(sub)) {
        throw new Error(
          "A grep-only explorer subagent is not allowed in this tree. Use a " +
          "general-purpose agent and name the codebase-memory-mcp graph tools " +
          "(search_graph, trace_path, search_code) in its prompt."
        )
      }
      if (identifierFrom(tool, args)) {
        const js = indexSlug(dir)
        if (js && (await oncePerSession(sessionID))) {
          throw new Error(
            `Code graph index is ready for this repo (${js}). For a definition, ` +
            "its callers or blast radius use the codebase-memory-mcp search_graph / " +
            "trace_path tools. If you need literal text, re-run this search unchanged; " +
            "it will pass - this nudge fires once per session."
          )
        }
      }
    },

    "tool.execute.after": async (input, output) => {
      if (!(await rootFor(dir))) return
      const tool = String(input?.tool || "").toLowerCase()
      const kind = classify(tool, output?.args || input?.args || {})
      if (kind) await record(input?.sessionID || input?.sessionId, kind)
    },
  }
}
