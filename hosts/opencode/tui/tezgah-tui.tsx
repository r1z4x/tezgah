/** @jsxImportSource @opentui/solid */
// tezgah status line for the opencode TUI.
//
// opencode has no command statusLine: a TUI plugin is the only surface. This is
// a LOCAL TUI plugin (not the server plugin in plugin/): it is declared in
// ~/.config/opencode/tui.json's "plugin" array and default-exports { id, tui }.
// It renders the same string `tezgah-status` prints, refreshed every 5s, in the
// always-visible app_bottom slot. Peer deps (@opentui/solid, solid-js) are
// virtualized by opencode's own TUI runtime, so nothing to install here.
import { createSignal, onCleanup } from "solid-js"
import type { TuiPluginApi } from "@opencode-ai/plugin/tui"

const HOME = process.env.HOME || ""
const STATUS = process.env.TEZGAH_STATUS_BIN || `${HOME}/.config/tezgah/bin/tezgah-status`

function TezgahBar(props: { api: TuiPluginApi }) {
  const [line, setLine] = createSignal("")
  const update = () => {
    try {
      const dir = props.api.state.path.directory || process.cwd()
      const run = Bun.spawnSync({
        cmd: ["python3", STATUS, dir],
        stdout: "pipe",
        stderr: "ignore",
      })
      setLine(new TextDecoder().decode(run.stdout).trim())
    } catch {
      setLine("")
    }
  }
  update()
  const timer = setInterval(update, 5000)
  onCleanup(() => clearInterval(timer))
  return (
    <box paddingLeft={1} flexShrink={0}>
      <text fg={props.api.theme.current.textMuted}>{line() || "tezgah"}</text>
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
  },
}
