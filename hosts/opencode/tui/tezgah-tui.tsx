/** @jsxImportSource @opentui/solid */
// tezgah status line for the opencode TUI.
//
// opencode has no command statusLine: a TUI plugin is the only surface. This is
// a LOCAL TUI plugin (not the server plugin in plugin/): it is declared in
// ~/.config/opencode/tui.json's "plugin" array and default-exports { id, tui }.
//
// Event-driven, not polled: it refreshes on the session's own event bus (message
// parts, session state, permissions) and keeps a slow safety timer only for
// out-of-band changes (a new .no-cbm, a new plan file). Each segment is colored
// by state from the active theme: green in force, yellow on-demand, red off. A
// command ("tezgah: status legend") opens a dialog that explains the marks.
import { createSignal, onCleanup, For } from "solid-js"
import type { TuiPluginApi } from "@opencode-ai/plugin/tui"

const HOME = process.env.HOME || ""
const STATUS = process.env.TEZGAH_STATUS_BIN || `${HOME}/.config/tezgah/bin/tezgah-status`
const SAFETY_MS = 30000

type Seg = { key: string; state: string; glyph: string; text: string }

function run(args: string[]): string {
  try {
    const proc = Bun.spawnSync({ cmd: ["python3", STATUS, ...args], stdout: "pipe", stderr: "ignore" })
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
  // The active session id is what lets the used marks (cbm/consult/orch) light.
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
              {i() < segs().length - 1 ? "  " : ""}
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
