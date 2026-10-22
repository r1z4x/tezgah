/** @jsxImportSource @opentui/solid */
// tezgah status line for the opencode 2 terminal (a CLI plugin).
//
// opencode 2 ignores tui.json: a local CLI plugin is a DIRECTORY listed in
// ~/.config/opencode/cli.json `plugins` (a spec naming a file is skipped), whose
// `tui` module default-exports Plugin.define({ id, setup }). Same data and marks
// as ../tezgah-tui.tsx (the opencode 1 shape, kept for v1 installs): one
// `tezgah-status <dir> --json [sessionID]` call per refresh, each segment colored
// green in force, yellow on-demand, red off, and a palette command for the legend.
import { Plugin } from "@opencode/plugin/tui"
import { createSignal, onCleanup, For } from "solid-js"
import { run } from "../tezgah-tui.tsx"

const SAFETY_MS = 30000
// Server events arrive per streamed part; one status call per burst is enough.
const DEBOUNCE_MS = 250

type Seg = { key: string; state: string; glyph: string; text: string; group?: number }
type Tone = { base: string }
// The part of the CLI plugin context this file reads (opencode.ai/v2/docs/build/plugins/cli).
type Ctx = {
  location?: { directory?: string }
  theme: { text: { muted: string; feedback: { success: Tone; warning: Tone; error: Tone } } }
  data: { location: { default(): { directory?: string } | undefined }; listen(fn: () => void): () => void }
  ui: { router: { current(): { type: string; sessionID?: string } | undefined } }
}

function color(ctx: Ctx, state: string) {
  const t = ctx.theme.text
  if (state === "on") return t.feedback.success.base
  if (state === "ready") return t.feedback.warning.base
  if (state === "off") return t.feedback.error.base
  return t.muted
}

function args(ctx: Ctx): string[] {
  const dir = ctx.location?.directory || ctx.data.location.default()?.directory || process.cwd()
  // The active session id is what lets the used marks (graph/consult/orch) light.
  const route = ctx.ui.router.current()
  return route?.type === "session" && route.sessionID ? [dir, "--json", route.sessionID] : [dir, "--json"]
}

function TezgahBar(props: { ctx: Ctx }) {
  const [segs, setSegs] = createSignal<Seg[]>([])
  const update = () => {
    try {
      setSegs(JSON.parse(run(args(props.ctx)) || "[]"))
    } catch {
      setSegs([])
    }
  }
  let pending: Timer | undefined
  const soon = () => {
    clearTimeout(pending)
    pending = setTimeout(update, DEBOUNCE_MS)
  }

  update()
  const stop = props.ctx.data.listen(soon)
  const timer = setInterval(update, SAFETY_MS)
  onCleanup(() => {
    stop()
    clearTimeout(pending)
    clearInterval(timer)
  })

  return (
    <box paddingLeft={1} flexShrink={0} flexDirection="row">
      <For each={segs()}>
        {(s, i) => (
          <box flexDirection="row">
            <text fg={color(props.ctx, s.state)}>{s.text + (s.glyph || "")}</text>
            <text fg={props.ctx.theme.text.muted}>
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

export default Plugin.define({
  id: "tezgah.status",
  setup(ctx) {
    ctx.keymap.layer(() => ({
      mode: "global",
      commands: [{
        id: "tezgah.legend",
        title: "tezgah: status legend",
        group: "tezgah",
        palette: true,
        run: () => ctx.ui.dialog.alert({ title: "tezgah status marks", message: run(["--legend"]) }),
      }],
    }))
    return ctx.ui.slot({ append: "prompt.footer", render: () => <TezgahBar ctx={ctx} /> })
  },
})
