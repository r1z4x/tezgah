// tezgah status line for the DeepSeek Harness Web UI, browser half.
//
// Renders the same marks `tezgah-status` prints on the other hosts, but colored
// by state (green in force, yellow on-demand, red off). Hover shows the legend;
// a click pins it open. Refresh is visibility-gated: it stops while the tab is
// hidden and fires once on return, so an idle Web UI is not polling.
window.__ModuleLoader__.load({
	id: "tezgah-dsh-statusline",
	factory: (require) => {
		var module = { exports: {} };
		var exports = module.exports;
		Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
		let react = require("react");
		let react_jsx_runtime = require("react/jsx-runtime");

		const REFRESH_MS = 10000;
		// Fixed, theme-agnostic colors: the marks must read on light and dark.
		const STATE_COLOR = { on: "#3fb950", ready: "#d29922", off: "#f85149",
			info: "var(--dsw-alias-label-tertiary)" };

		/**
		 * One status line for a session, polled from the host route only while the
		 * tab is visible. The text and glyphs come from the host, so the component
		 * owns layout and color, not the wording.
		 * @param props - the slot's session id plus any injected services.
		 */
		function TezgahStatusLine({ sessionId }) {
			const [data, setData] = react.useState({ segments: [], legend: "" });
			const [open, setOpen] = react.useState(false);
			react.useEffect(() => {
				let alive = true;
				let timer;
				const load = async () => {
					try {
						if (typeof document !== "undefined" && document.hidden) return;
						const query = sessionId ? `&sessionId=${encodeURIComponent(sessionId)}` : "";
						const res = await fetch(`/api/tezgah.status?format=json${query}`, {
							headers: { accept: "application/json" }
						});
						const body = res.ok ? await res.json() : null;
						if (alive && body) {
							setData({ segments: body.segments || [], legend: body.legend || "" });
						}
					} catch {
						if (alive) setData({ segments: [], legend: "" });
					} finally {
						if (alive) timer = setTimeout(load, REFRESH_MS);
					}
				};
				load();
				const onVisibility = () => { if (!document.hidden) load(); };
				document.addEventListener("visibilitychange", onVisibility);
				return () => {
					alive = false;
					clearTimeout(timer);
					document.removeEventListener("visibilitychange", onVisibility);
				};
			}, [sessionId]);

			if (!data.segments.length) return null;
			const legend = data.legend || "tezgah status";
			return react_jsx_runtime.jsxs("span", {
				title: legend,
				onClick: () => setOpen((v) => !v),
				style: {
					position: "relative",
					cursor: "pointer",
					fontFamily: "var(--dsw-font-mono)",
					fontSize: "12px",
					whiteSpace: "nowrap",
					overflow: "hidden",
					textOverflow: "ellipsis",
					maxWidth: "32ch"
				},
				children: [
					data.segments.map((seg, i) =>
						react_jsx_runtime.jsxs("span", {
							key: `${seg.key}-${i}`,
							children: [
								react_jsx_runtime.jsx("span", {
									// the whole name+glyph carries the state color, the
									// same as the terminal hosts; `info` stays muted
									style: { color: STATE_COLOR[seg.state] || "inherit" },
									children: seg.text + (seg.glyph || "")
								}),
								i < data.segments.length - 1 ? "  " : ""
							]
						})
					),
					open
						? react_jsx_runtime.jsx("span", {
							style: {
								position: "absolute",
								top: "1.4em",
								right: 0,
								zIndex: 50,
								whiteSpace: "pre",
								background: "var(--dsw-alias-bg-layer-1, #222)",
								color: "var(--dsw-alias-label-secondary, #ddd)",
								border: "1px solid var(--dsw-alias-border, #444)",
								borderRadius: "6px",
								padding: "6px 8px",
								fontSize: "11px",
								maxWidth: "46ch"
							},
							children: legend
						})
						: null
				]
			});
		}

		/** Required service: the UI slot registry. */
		const inject = ["slots"];

		/** Register the header status line. */
		function apply(ctx) {
			ctx.slots.inject("conversation.session.header.utilities", () =>
				ctx.slots.register(
					{
						name: "conversation.session.header.utilities",
						id: "tezgah-statusline",
						order: 30
					},
					TezgahStatusLine
				)
			);
		}

		exports.apply = apply;
		exports.inject = inject;
		return module.exports;
	}
});
