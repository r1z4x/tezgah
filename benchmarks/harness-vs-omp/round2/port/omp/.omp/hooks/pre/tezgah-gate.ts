const IDENT = /^[A-Za-z_][A-Za-z0-9_]*$/;

function reason(tool: string): string {
  return (
    "tezgah gate: identifier " +
    tool +
    " is blocked. For definitions, callers and blast radius use the " +
    "codebase-memory-mcp graph tools (search_graph, trace_path, " +
    "get_architecture, check_index_coverage); grep is for literal text only."
  );
}

export default function tezgahGate(pi: any): void {
  pi.on("tool_call", async (event: any) => {
    const name = event?.toolName;
    const input = event?.input ?? {};

    if (name === "grep") {
      const pattern = String(input.pattern ?? input.query ?? "").trim();
      if (IDENT.test(pattern)) {
        return { block: true, reason: reason("grep") };
      }
    }

    if (name === "bash") {
      const command = String(input.command ?? "");
      const match = command.match(/\bgrep\b[^\n|]*?(['"])([A-Za-z_][A-Za-z0-9_]*)\1/);
      if (match) {
        return { block: true, reason: reason("grep") };
      }
    }

    return undefined;
  });
}
