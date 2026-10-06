// The opencode plugin's shell readers for tests/fuzz_shell.py: argv[2] is the
// plugin path, stdin a JSON list of lines, stdout a JSON list of
// {mask, programs} - maskText and shellPrograms, the ports of
// hooks/tezgah_integrity.mask and hooks/tezgah_context.shell_programs. They are
// module-private, so the source is re-imported with one export line appended.
import { readFileSync } from "node:fs"

const src = readFileSync(process.argv[2], "utf8") +
  "\nexport { maskText as __mask, shellPrograms as __programs }\n"
const mod = await import("data:text/javascript;base64," +
  Buffer.from(src).toString("base64"))
const lines = JSON.parse(readFileSync(0, "utf8"))
process.stdout.write(JSON.stringify(lines.map((text) =>
  ({ mask: mod.__mask(text), programs: mod.__programs(text) }))))
