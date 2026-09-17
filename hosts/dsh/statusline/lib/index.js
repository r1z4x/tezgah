// tezgah status line for the DeepSeek Harness Web UI, host half.
//
// The browser half ships through exports["./client"]; this half only serves the
// data it renders. Two shapes:
//   /api/tezgah.status                      -> the plain line (text/plain)
//   /api/tezgah.status?format=json&sessionId -> {segments, legend} for the colored
// The status is whatever `tezgah-status` prints for the session's workspace - the
// same source every other host renders - behind the Web UI's own authenticated
// /api fence, so the client fetches it same-origin with no extra token handling.
import { execFile } from "node:child_process";
import os from "node:os";
import path from "node:path";

const STATUS_PATH = "/api/tezgah.status";
// dsh's hook records the tool-use kinds (consult/research/cbm/orch) and nothing
// else, so its line must not claim a skill was never opened: the two skill-read
// marks state nothing here instead.
const OBSERVABLE = "--observable=consult,research,cbm,orch";

function statusBin() {
	if (process.env.TEZGAH_STATUS_BIN) return process.env.TEZGAH_STATUS_BIN;
	return path.join(os.homedir(), ".config", "tezgah", "bin", "tezgah-status");
}

/** Run tezgah-status; resolve "" on any failure so the UI just hides the line. */
function statusText(args) {
	return new Promise((resolve) => {
		execFile(process.env.TEZGAH_PYTHON || "python3", [statusBin(), ...args],
			{ timeout: 5000 }, (error, stdout) => resolve(error ? "" : String(stdout).trim()));
	});
}

/** Services required before the route can be registered. */
export const inject = ["connection", "sessions"];

/** Register the authenticated status route. */
export function apply(ctx) {
	ctx.connection.fetch.register({
		path: STATUS_PATH,
		methods: ["GET"],
		requestBody: "buffered",
		fetch: async (request) => {
			const url = new URL(request.url);
			const sessionId = url.searchParams.get("sessionId") ?? undefined;
			const session = sessionId === undefined ? undefined : ctx.sessions.get(sessionId);
			const dir = session?.header?.cwd ?? process.cwd();
			const where = sessionId === undefined ? [dir, OBSERVABLE]
				: [dir, sessionId, OBSERVABLE];
			if (url.searchParams.get("format") === "json") {
				const [raw, legend] = await Promise.all([
					statusText([...where, "--json"]),
					statusText(["--legend"]),
				]);
				let segments = [];
				try { segments = JSON.parse(raw || "[]"); } catch { segments = []; }
				return new Response(JSON.stringify({ segments, legend }), {
					headers: {
						"content-type": "application/json; charset=utf-8",
						"cache-control": "no-store",
					},
				});
			}
			return new Response(await statusText(where), {
				headers: {
					"content-type": "text/plain; charset=utf-8",
					"cache-control": "no-store",
				},
			});
		},
	});
}
