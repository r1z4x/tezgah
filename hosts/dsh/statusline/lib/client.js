// tezgah status line for the DeepSeek Harness Web UI, browser half.
//
// Registers one compact line in the session header that shows the same string
// `tezgah-status` prints on the other hosts. The host half serves it at
// /api/tezgah.status behind the UI's auth fence; this half polls it every 5s.
window.__ModuleLoader__.load({
	id: "tezgah-dsh-statusline",
	factory: (require) => {
		var module = { exports: {} };
		var exports = module.exports;
		Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
		let react = require("react");
		let react_jsx_runtime = require("react/jsx-runtime");

		const REFRESH_MS = 5000;

		/**
		 * One status line for a session, polled from the host route. The text is
		 * already the full human string, so the component owns no formatting.
		 * @param props - the slot's session id plus any injected services.
		 */
		function TezgahStatusLine({ sessionId }) {
			const [line, setLine] = react.useState("");
			react.useEffect(() => {
				let alive = true;
				let timer;
				const load = async () => {
					try {
						const query = sessionId ? `?sessionId=${encodeURIComponent(sessionId)}` : "";
						const res = await fetch(`/api/tezgah.status${query}`, {
							headers: { accept: "text/plain" }
						});
						const text = res.ok ? (await res.text()).trim() : "";
						if (alive) setLine(text);
					} catch {
						if (alive) setLine("");
					} finally {
						if (alive) timer = setTimeout(load, REFRESH_MS);
					}
				};
				load();
				return () => {
					alive = false;
					clearTimeout(timer);
				};
			}, [sessionId]);
			if (!line) return null;
			return react_jsx_runtime.jsx("span", {
				title: line,
				style: {
					color: "var(--dsw-alias-label-tertiary)",
					fontFamily: "var(--dsw-font-mono)",
					fontSize: "12px",
					whiteSpace: "nowrap",
					overflow: "hidden",
					textOverflow: "ellipsis",
					maxWidth: "28ch"
				},
				children: line
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
