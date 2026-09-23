/** @jsxImportSource @opentui/solid */
// tezgah status line for the opencode TUI.
//
// opencode has no command statusLine: a TUI plugin is the only surface. This is
// a LOCAL TUI plugin (not the server plugin in plugin/): it is declared in
// ~/.config/opencode/tui.json's "plugin" array and default-exports { id, tui }.
//
// Event-driven, not polled: it refreshes on the session's own event bus (message
// parts, session state, permissions) and keeps a slow safety timer only for
// out-of-band changes (a new .no-graph, a new plan file). Each segment is colored
// by state from the active theme: green in force, yellow on-demand, red off. A
// command ("tezgah: status legend") opens a dialog that explains the marks.
import { existsSync } from "node:fs"
import { delimiter, join } from "node:path"
import { createSignal, onCleanup, For } from "solid-js"
import type { TuiPluginApi } from "@opencode-ai/plugin/tui"

const HOME = process.env.HOME || ""
const STATUS = process.env.TEZGAH_STATUS_BIN || `${HOME}/.config/tezgah/bin/tezgah-status`
const SAFETY_MS = 30000

type Seg = { key: string; state: string; glyph: string; text: string; group?: number }

// The interpreter tezgah-status runs under, resolved the way tezgah's own
// `hooks/tezgah_paths.python_cmd()` resolves it and the server plugin does it
// (hosts/opencode/plugins/tezgah.js): the tezgah override first, then the names
// the platforms ship. A line that cannot start its binary is a line that never
// appears, and the machine that ships `python`/`py` instead is exactly the case
// the plan's Windows half is about. Memoised: the probe reads PATH, and the
// status line must not pay for it on every refresh.
let pythonMemo: string | undefined

function pythonBin(): string {
  if (pythonMemo) return pythonMemo
  // The order is the order they answer in: `py` is the Windows launcher, and
  // TEZGAH_PYTHON overrides the list entirely.
  const names = ["python3", "python", "py"]
  if (process.env.TEZGAH_PYTHON) return (pythonMemo = process.env.TEZGAH_PYTHON)
  // A bare name is resolved by the OS at spawn time only through its own rules,
  // and this host cannot be asked which one it uses: the lookup is done here
  // against PATH with the platform's separator, and `.exe` beside each name on
  // Windows.
  const dirs = String(process.env.PATH || "").split(delimiter)
  const win = process.platform === "win32"
  const found = names.find((name) => dirs.some((dir) => {
    try {
      return existsSync(join(dir, name))
        || (win && existsSync(join(dir, name + ".exe")))
    } catch { return false }
  }))
  return (pythonMemo = found || names[0])
}

function run(args: string[]): string {
  try {
    const proc = Bun.spawnSync({ cmd: [pythonBin(), STATUS, ...args], stdout: "pipe", stderr: "ignore" })
    return new TextDecoder().decode(proc.stdout).trim()
  } catch {
    return ""
  }
}

function segmentColor(api: TuiPluginApi, state: string) {
  const t = api.theme.current
  if (state === "on") return t.success
  if (state === "ready") return t.warning
  if (state === "off") return t.error
  return t.textMuted
}

function sessionParams(api: TuiPluginApi): string[] {
  // The active session id is what lets the used marks (graph/consult/orch) light.
  const route = api.route?.current as { params?: { sessionID?: string } } | undefined
  const sid = route?.params?.sessionID
  return sid ? [sid] : []
}

function TezgahBar(props: { api: TuiPluginApi }) {
  const [segs, setSegs] = createSignal<Seg[]>([])
  const update = () => {
    try {
      const dir = props.api.state.path.directory || process.cwd()
      const raw = run([dir, "--json", ...sessionParams(props.api)])
      setSegs(JSON.parse(raw || "[]"))
    } catch {
      setSegs([])
    }
  }

  update()
  const offs = ["message.part.updated", "message.updated", "session.idle",
    "session.status", "permission.replied"].map(
    (ev) => props.api.event.on(ev as never, () => update()))
  const timer = setInterval(update, SAFETY_MS)
  onCleanup(() => {
    offs.forEach((off) => off())
    clearInterval(timer)
  })

  return (
    <box paddingLeft={1} flexShrink={0} flexDirection="row">
      <For each={segs()}>
        {(s, i) => (
          <box flexDirection="row">
            {/* the whole name+glyph carries the state color, as on every host */}
            <text fg={segmentColor(props.api, s.state)}>{s.text + (s.glyph || "")}</text>
            <text fg={props.api.theme.current.textMuted}>
              {/* the host's own spacing: one space inside a group, "  ·  "
                  between groups, exactly as render_line() draws it */}
              {i() < segs().length - 1
                ? (segs()[i() + 1].group === s.group ? " " : "  ·  ")
                : ""}
            </text>
          </box>
        )}
      </For>
    </box>
  )
}

function LegendDialog(props: { api: TuiPluginApi; body: () => string }) {
  return (
    <box flexDirection="column" padding={1}>
      <text fg={props.api.theme.current.text}>tezgah status marks</text>
      <For each={props.body().split("\n")}>
        {(line) => <text fg={props.api.theme.current.textMuted}>{line}</text>}
      </For>
    </box>
  )
}

export default {
  id: "tezgah-status",
  tui: async (api: TuiPluginApi) => {
    api.slots.register({
      slots: {
        app_bottom: () => <TezgahBar api={api} />,
      },
    })
    // The legend lives behind a command, so the always-visible bar stays one line.
    api.command?.register(() => [{
      title: "tezgah: status legend",
      value: "tezgah.legend",
      description: "Explain the tezgah status marks",
      onSelect: () => {
        const body = () => run(["--legend"])
        api.ui.dialog.replace(() => <LegendDialog api={api} body={body} />)
      },
    }])
  },
}
