// tezgah status line for the DeepSeek Harness Web UI, host half.
//
// The browser half ships through exports["./client"]; this half only serves the
// text it renders. The status is whatever `tezgah-status` prints for the
// session's workspace - the same string every other host renders - behind the
// Web UI's own authenticated /api fence, so the client fetches it same-origin
// with no extra token handling.
import { execFile } from "node:child_process";
import os from "node:os";
import path from "node:path";

const STATUS_PATH = "/api/tezgah.status";

function statusBin() {
	if (process.env.TEZGAH_STATUS_BIN) return process.env.TEZGAH_STATUS_BIN;
	return path.join(os.homedir(), ".config", "tezgah", "bin", "tezgah-status");
}

/** Run tezgah-status; resolve "" on any failure so the UI just hides the line. */
function statusText(dir, sessionId) {
	return new Promise((resolve) => {
		const args = [statusBin(), dir];
		if (sessionId) args.push(sessionId);
		execFile(process.env.TEZGAH_PYTHON || "python3", args, { timeout: 5000 }, (error, stdout) => {
			resolve(error ? "" : String(stdout).trim());
		});
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
			const sessionId = new URL(request.url).searchParams.get("sessionId") ?? undefined;
			const session = sessionId === undefined ? undefined : ctx.sessions.get(sessionId);
			const dir = session?.header?.cwd ?? process.cwd();
			return new Response(await statusText(dir, sessionId), {
				headers: {
					"content-type": "text/plain; charset=utf-8",
					"cache-control": "no-store"
				}
			});
		}
	});
}
