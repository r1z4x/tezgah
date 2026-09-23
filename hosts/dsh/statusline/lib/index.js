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
import { existsSync } from "node:fs";
import os from "node:os";
import path from "node:path";

const STATUS_PATH = "/api/tezgah.status";
// dsh's hook is the shared projects-posttooluse.py, so it records the same
// tool-use kinds as every other host - consult/research/graph/orch and judge -
// and may not claim the two skill-read marks, which only the prompt hook can set.
const OBSERVABLE = "--observable=consult,research,graph,orch,judge";

function statusBin() {
	if (process.env.TEZGAH_STATUS_BIN) return process.env.TEZGAH_STATUS_BIN;
	return path.join(os.homedir(), ".config", "tezgah", "bin", "tezgah-status");
}

/** The interpreter tezgah-status runs under: the tezgah override first - the
 * name hooks/tezgah_paths.python_cmd() and every host manifest resolve through -
 * then the names the platforms ship, because a status line whose binary cannot
 * start is a line that never appears. Memoised: the probe reads PATH, and this
 * runs on the first status request. */
let pythonMemo;
function pythonBin() {
	if (pythonMemo) return pythonMemo;
	// The order is the order they answer in: `py` is the Windows launcher, and
	// TEZGAH_PYTHON overrides the list entirely.
	const names = ["python3", "python", "py"];
	if (process.env.TEZGAH_PYTHON) return (pythonMemo = process.env.TEZGAH_PYTHON);
	// A bare name is resolved by the OS at spawn time only through its own rules,
	// and node does not read a shell's hash, so the lookup is done here: PATH with
	// the platform's separator, and `.exe` beside each name on Windows.
	const dirs = String(process.env.PATH || "").split(path.delimiter);
	const win = process.platform === "win32";
	const found = names.find((name) => dirs.some((dir) => {
		try {
			return existsSync(path.join(dir, name))
				|| (win && existsSync(path.join(dir, name + ".exe")));
		} catch { return false; }
	}));
	return (pythonMemo = found || names[0]);
}

/** Run tezgah-status; resolve "" on any failure so the UI just hides the line. */
function statusText(args) {
	return new Promise((resolve) => {
		execFile(pythonBin(), [statusBin(), ...args],
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
