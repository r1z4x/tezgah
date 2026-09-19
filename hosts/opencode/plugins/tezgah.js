// tezgah opencode plugin: the opencode half of the tezgah contract.
//
// opencode has no stdout "inject context" hook, so the always-on core ships as
// `instructions` files that tezgah-setup generates from the shared policy
// (opencode-contract.md + opencode-skills.md); the per-turn and post-compact
// text is paid by chat.message and experimental.session.compacting, which call
// the shared builder (hooks/tezgah_context.py) through bin/tezgah-context rather
// than keeping a copy of it here. This plugin adds what those files cannot:
//   - tool.execute.before + permission.ask: refuse a git/gh write that credits
//     an AI/model, block the first blind identifier search toward the code
//     graph, and refuse a grep-only explorer subagent. permission.ask is the
//     native allow/deny path where a build emits it; tool.execute.before is the
//     always-available fallback (1.18.30 never emits permission.ask, so the
//     fallback is what enforces today).
//   - tool.execute.before also carries the rules that need the ledger: consent
//     for an unasked irreversible or outward-facing shell command (refused once
//     per action, so the ask reaches the user), secret for a credential on its
//     way into a file, the two repeat ceilings (loop per user turn, retry per
//     session), and the one ordering obligation (a commit while the newest check
//     in this session failed). One class of that rule is not derived here: an
//     outbound `send` (mail, a payment, a remote API called with a write, a copy
//     to another host, a `gh pr`/`gh issue` write) has no pattern in this file at
//     all - a command that looks like one is put to the core through the same
//     gate CLI, so the SEND pattern stays in exactly one place and this host
//     cannot drift from it.
//   - a write is put to the core itself, through bin/tezgah-gate: the active
//     task's phase and path allowlist is a rule of hooks/tezgah_gate.py, and
//     this host asks for its answer rather than keeping a JS copy of it (the
//     rule-by-rule port below is documented as incomplete and divergent, which
//     is exactly why a new rule never enters through it). The same ask covers
//     the record's shell route - a bash command that would move the phase or
//     the allowlist - through the same CLI and the same rule, asked only on a
//     command that names the task CLI (see TASK_CLI for the bound).
//   - the same hook keeps the pre-write bytes of what a write tool is about to
//     change, through bin/tezgah-capture, on the allow path only: opencode is
//     the one host whose plugin cannot call tezgah_snapshot.capture in process.
//   - shell.env: export the tezgah roots and paths into every shell call.
//   - chat.message: pay the shared builder's text for the submitted prompt -
//     the per-turn reminder plus the conditional rule that prompt arms.
//   - experimental.session.compacting: the builder's post-compact block, so the
//     contract survives the summary.
//   - tool.execute.after: record which tezgah tools a session used so
//     `tezgah-status` can show it.
//
// Known gap: every rule of hooks/tezgah_gate.py is enforced here, but the ledger
// the counters read is complete only for the rules ported last - consent, secret,
// loop, retry and order write the rows the Python gate's `_deny` writes, while
// the explorer, attribution and shortcut refusals (and the nudge, marked by its
// cache-dir file alone) still leave no row of their own.
//
// Every path fails open: if anything here throws unexpectedly, the tool runs.
// Hook names a given opencode build does not know are skipped by the runtime
// (Plugin.trigger does `if (!hook) continue`), so returning a hook that build
// lacks is safe and must never be a load-time error.
import { createReadStream, existsSync, mkdirSync, realpathSync, rmSync,
  writeFileSync } from "node:fs"
import { appendFile, mkdir, open, readFile, writeFile } from "node:fs/promises"
import { spawn } from "node:child_process"
import { createHash } from "node:crypto"
import { homedir, tmpdir } from "node:os"
import { basename, dirname, isAbsolute, join, resolve, sep } from "node:path"

const HOME = homedir()
const CONFIG = join(process.env.XDG_CONFIG_HOME || join(HOME, ".config"), "tezgah")
const CACHE = join(HOME, ".cache", "tezgah")
// A sandboxed host denies the global cache. The Python half falls back to temp
// (hooks/tezgah_paths.py cache_dir) and this half must do the same, or the
// nudge, the evidence ledger and the used marks all disappear on the first
// unwritable write.
const FALLBACK_CACHE = join(tmpdir(), "tezgah-" + String(process.getuid?.() ?? "u"))
let cacheMemo = null

function writableDir(dir) {
  try {
    mkdirSync(dir, { recursive: true })
    const probe = join(dir, ".tezgah-write-probe")
    writeFileSync(probe, "")
    rmSync(probe, { force: true })
    return true
  } catch {
    return false
  }
}

function cacheDir() {
  if (cacheMemo) return cacheMemo
  for (const d of [CACHE, FALLBACK_CACHE]) {
    if (writableDir(d)) { cacheMemo = d; return d }
  }
  cacheMemo = CACHE
  return CACHE
}
const CBM_DIR = join(HOME, ".cache", "codebase-memory-mcp")
const STATUS_BIN = join(CONFIG, "bin", "tezgah-status")
const INDEX_BIN = join(CONFIG, "bin", "tezgah-index")
const AGENTS_BIN = join(CONFIG, "bin", "tezgah-agents")
const SETUP_BIN = join(CONFIG, "bin", "tezgah-setup")
const CONTEXT_BIN = join(CONFIG, "bin", "tezgah-context")
const CAPTURE_BIN = join(CONFIG, "bin", "tezgah-capture")
const GATE_BIN = join(CONFIG, "bin", "tezgah-gate")
const IDENT = /^[A-Za-z_][A-Za-z0-9_]{2,}$/
const EXPLORE_DENY =
  "A grep-only explorer subagent is not allowed in this tree. Use a " +
  "general-purpose agent and name the codebase-memory-mcp graph tools " +
  "(search_graph, trace_path, search_code) in its prompt."
// The credit forms on a git/gh write, ported from hooks/tezgah_gate.py
// (WRITE_CMD/ATTRIB) so opencode enforces the same ban from the same shapes.
const ATTRIB =
  /co-authored-by\s*:|generated with|made with|built by|assisted by|authored by|noreply@anthropic|\u{1F916}/iu
// The same forms anchored to the start of a line, for the text a write/edit
// tool is about to land. Mirrors hooks/tezgah_gate.py ATTRIB_LINE: a credit owns
// its line, while prose naming the ban does not, and that anchor is what keeps
// the rule from denying the documentation that describes it.
const ATTRIB_LINE =
  /^[\s>#*/<!+-]*(?:co-authored-by\s*:|generated with|made with|built by|assisted by|authored by|noreply@anthropic|\u{1F916})/imu
const EDIT_TEXT = ["content", "new_string", "newString", "new_str", "file_text",
  "patch", "text"]
const WRITE_CMD =
  /(?:^|[|;&]\s*|\s)git\s+(?:-{1,2}\S+(?:\s+\S+)?\s+)*(?:commit|merge|tag|notes)\b|(?:^|[|;&]\s*|\s)gh\s+api\b|(?:^|[|;&]\s*|\s)gh\s+(?:pr|issue|release)\s+(?:create|edit|comment|review|merge|close)\b/i
const ATTRIB_DENY =
  "Attribution is banned in every artifact tezgah touches. Remove the " +
  "Co-Authored-By / \"Generated with\" / robot-emoji / model-name credit from " +
  "the commit, PR, issue or review text and re-run. Naming a tool in order to " +
  "use it or describe real behavior is fine; crediting it as author is not."

// --- consent: an irreversible or outward-facing command ---------------------
// A `git push` carrying a force flag, to a branch that is not scratch: a scratch
// branch is disposable, so the history it loses costs nobody else anything. The
// flag has to sit in the push segment the command's own separators bound.
const GIT_PUSH =
  /(?:^|[|;&]\s*|\s)git\s+(?:-{1,2}\S+(?:\s+\S+)?\s+)*push\b([^|;&]*)/gi
const FORCE_FLAG =
  /(?:^|\s)(?:-f|--force|--force-with-lease|--force-if-includes)(?=[\s=]|$)/
const SCRATCH =
  /\b(?:tmp|temp|scratch|wip|spike|throwaway|trash|sandbox)[-/][\w./-]*/i
// `git branch -D`/`--delete`, and the remote delete `git push --delete`/`-d`. The
// delete flag is matched by shape, because `--merged` also carries a `d`.
const BRANCH_DELETE =
  /(?:^|[|;&]\s*|\s)git\s+(?:-{1,2}\S+(?:\s+\S+)?\s+)*(?:branch\s+(?:-[A-Za-z]*[dD]\b|--delete\b)|push\b[^|;&]*(?:--delete\b|-d\b))/i
// The destructive effect that lands on a shared resource at a service instead of
// on this machine (hooks/tezgah_gate.REMOTE_DESTROY): the remote repository
// `gh repo delete|archive` closes for everyone, the bucket `aws s3 rb` removes,
// the prefix `aws s3 rm --recursive` empties, and `gh run delete`/`gh cache
// delete` drop a CI run's record and the caches other runs read. Read as
// `destructive` beside the branch delete, never as a `send`: nothing of this
// workspace's is carried out, something both parties owned stops existing.
// `aws s3 rm` without `--recursive` is the shape of `rm` on one file and stays
// out.
const REMOTE_DESTROY =
  /(?:^|[|;&]\s*|\s)(?:gh\s+repo\s+(?:delete|archive)\b|gh\s+(?:run|cache)\s+delete\b|aws\s+s3\s+rb\b)/i
const AWS_S3_RM = /(?:^|[|;&]\s*|\s)aws\s+s3\s+rm\b/gi
const AWS_RECURSIVE = /--recursive\b/
// A recursive force-delete: both flags have to be there (`rm -f` and `rm -r` on
// their own are not this rule's), and the targets come from the raw text so a
// quoted path still resolves - the `rm` itself is matched on the masked text, so
// a message that describes the command is not the command.
const RM = /(?:^|[|;&]\s*|\s)rm\s+((?:-\S+\s+)*)([^|;&]*)/g
// The same pattern anchored at one offset, for the raw-text read in rmOutside.
const RM_AT = new RegExp(RM.source, "y")
const RM_RECURSIVE = /-[A-Za-z]*r[A-Za-z]*\b|--recursive\b/i
const RM_FORCE = /-[A-Za-z]*f[A-Za-z]*\b|--force\b/
// Applying a migration, by the runners that name it. `clean` is here with the
// upgrade/down words because `flyway clean` drops every object in the configured
// schemas - the same class, reached by the runner's own verb rather than by a
// downgrade (hooks/tezgah_gate.MIGRATION).
// ponytail: a hand-written `psql -c "ALTER TABLE ..."` is not caught - reading
// SQL intent is not a regex.
const MIGRATION =
  /(?:^|[|;&]\s*|\s)(?:(?:alembic|flyway|goose|dbmate|sqitch)\s+(?:upgrade|up|migrate|deploy|down|downgrade|rollback|reset|redo|clean)\b|(?:knex|prisma|sequelize|typeorm)\s+\S*migrat\S*|(?:django-admin|manage\.py)\s+migrate\b|python\d?\s+-m\s+django\s+migrate\b|(?:bin\/)?rails\s+db:(?:migrate|rollback|reset|schema:load)\b)/i
// A deploy: putting code in front of users, by the runners that name it.
const DEPLOY =
  /(?:^|[|;&]\s*|\s)(?:(?:vercel|netlify|fly|flyctl|railway|render|wrangler|firebase|gcloud|eb)\b[^|;&]*?\bdeploy\b|(?:serverless|sls)\s+deploy\b|terraform\s+(?:apply|destroy)\b|helm\s+(?:install|upgrade|uninstall)\b|kubectl\s+(?:apply|delete|rollout|scale)\b|ansible-playbook\b)/i
// Shipping an artifact outward: a registry, a release, an image.
const PUBLISH =
  /(?:^|[|;&]\s*|\s)(?:(?:npm|yarn|pnpm|bun)\s+publish\b|twine\s+upload\b|docker\s+push\b|gh\s+release\s+create\b)/i
// A push to a target that is live rather than a branch under review.
const OUTWARD =
  /(?:^|[|;&]\s*|\s)git\s+(?:-{1,2}\S+(?:\s+\S+)?\s+)*push\s+\S*\s*(?:heroku|production|prod)\b/i
// A command that could be carrying data out to a service that acts on it: mail,
// a payment, a remote API called with a write, a copy to another host. This is
// a PRE-FILTER and not the rule - the rule is hooks/tezgah_gate.py's SEND
// pattern, and a command this sees is put to the core through bin/tezgah-gate
// (see the header). So it is deliberately looser than the pattern: a match here
// costs one spawn and the core's answer, a miss costs the ask that does not
// happen, which is the failure this pre-filter exists to avoid.
const SEND_CANDIDATE =
  /(?:^|[|;&(]\s*)(?:sendmail|msmtp|mutt|mailx|swaks|mail\s|aws\s+ses\b|stripe\b|paypal\b|nc\b|ncat\b|scp\b|ssh\b|rsync\b|curl\b|gh\s+api\b|gh\s+(?:pr|issue)\s+(?:create|edit|comment|review|merge|close)\b)/i
// The classes a refused command's effect belongs to, and what each one is. The
// refusal names the class and this clause, never the pattern that matched: the
// agent has to see what it is about to do, not which regex caught it.
const EFFECTS = {
  destructive: "this one rewrites or drops history, a branch, files outside " +
    "the run directory, or a resource other people share - a repository, a " +
    "bucket, a CI run or its cache",
  schema: "this one changes the shape of a database",
  deploy: "this one puts code in front of users",
  publish: "this one ships an artifact to a registry or a release",
  outward: "this one pushes to a live target rather than a branch under review",
  // No pattern of its own here (SEND_CANDIDATE asks the core instead), but the
  // class has to be named: the refusal quotes this clause, and a declaration
  // reads this table to know which classes exist.
  send: "this one carries data out to a service that acts on it - mail, a " +
    "payment, a remote API called with a write, a copy to another host",
}
const CONSENT_DENY =
  "Consent gate (`%s` effect): %s. The contract requires the user's own " +
  "decision before an irreversible or outward-facing action, and a re-issued " +
  "command is not that decision: the ledger holds no approval for this action, " +
  "so this keeps refusing. Put the exact command and what it cannot undo in " +
  "front of the user; `bin/tezgah-consent %s` writes their approval - `--last` " +
  "answers the newest ask - and the command passes once. No checkpoint can be " +
  "taken for a shell effect (a force-push, a migration or a deploy changes a " +
  "remote or a live system this ledger holds no pre-state for), so their " +
  "approval is the whole record on the rollback side."
// Appended when this gate's own refusal is on record already: the second refusal
// reads as "still waiting for the user", not as a fresh ask.
const ASK_STANDS_NOTE =
  " The ask is on record already (`consent`, this action's id); what is " +
  "missing is the user's own answer, and a repeat is not it."
// The classes from the one that cannot be walked back at all to the one a
// reviewer can still catch. It is the order "at least as severe" is read in (see
// consentEffect), which is what keeps a declared effect a way to raise a
// command's class and never a way to lower it.
const EFFECT_RANK = ["send", "outward", "publish", "deploy", "schema", "destructive"]
// The class a command declares for itself. Read off the RAW text, not the masked
// text: the natural place for the declaration is a trailing `#` comment, and
// maskText blanks comments. ponytail: a command that merely quotes the form - a
// commit message documenting this rule - is held to the declared class too; the
// direction is the safe one (the class can only go up) and the refusal is
// one-shot.
const DECLARED_EFFECT = /tezgah:effect\s*=\s*([A-Za-z]+)/
// Appended to the refusal when the command declared a lower class than the one it
// is held to: the attempt to talk the class down is the user's to see, in the
// refusal and in the deny row's detail.
const DOWNGRADE_NOTE =
  " The command declared `tezgah:effect=%s`; a declaration can only make this " +
  "stricter, so `%s` stands."
// --- secret: a credential on its way into a file ----------------------------
// Only the two shapes the contract names: a bearer header, or a `name=value`
// assignment. `:` is NOT a separator here - `{"api_key": "x"}` is a JSON field in
// a program's text, while `token=$TOKEN` and `api_key=...` are a credential being
// carried, and the value may be an env reference the shell resolves.
const SECRET_TOKEN =
  /authorization\s*:\s*bearer\s+\S|[A-Za-z0-9_.-]*(?:api[_-]?key|access[_-]?token|auth[_-]?token|token|secret|password|passwd)\s*=\s*["']?[^\s"']/i
// The sinks that carry a command's own text into a file. `>>?` is read off the
// masked text, so a quoted `>` is not a redirect and `2>&1` is not a file.
// curl's -o/--output writes the response BODY, not the request header, so it is
// not a sink; its traces are, because those do carry the header.
const SECRET_SINK =
  />>?(?![&=])|\|\s*tee\b|--trace(?:-ascii)?\b|(?:^|[|;&]\s*|\s)git\s+(?:-{1,2}\S+(?:\s+\S+)?\s+)*add\b/
// The simple commands of a shell line: a sink only carries the text of its own
// simple command, so `git add -A && git commit -m "fix api_key= handling"` is a
// message about the rule rather than a credential in a write. `|` is NOT a
// boundary here but a carrier, and the split is read off the masked text.
const SEGMENT = /\|\||&&|[;&\n]/g
const SECRET_DENY =
  "Credential write denied: this command would land a credential in a file " +
  "(`>`/`>>`, `tee`, `git add` or a curl trace). Record the credential's " +
  "name, length or a fingerprint instead of its value, pass it through the " +
  "tool's own environment, or let the tool read it from there rather than " +
  "writing it out."
// --- loop and retry: the two repeat ceilings --------------------------------
// The attempt a repeat is refused on, per failure class. Two identical failures
// are the retry the agent may still be fixing while it changes the code between
// them; the third is the loop the contract bans ("three attempts on one failure
// is the ceiling"). A transient failure - a timeout, a connection error, a rate
// limit, a 5xx - can clear on its own, so its identical call gets one more try.
// No row written here carries a class: opencode reports the process exit code and
// no error text, so a class is never observed and the base allowance applies
// (tezgah_integrity.fail_class).
const LOOP_CEILING = 2
const CLASS_CEILING = { transient: LOOP_CEILING + 1 }
const CLASS_NOTE = {
  transient: "the failure it names can clear on its own, so this class gets " +
    "one more identical attempt than a permanent one",
  permanent: "an assertion or a bad argument does not change by re-running it",
}
const NO_CLASS_NOTE = "the host reported no error text for it, so the class " +
  "is unknown and the base allowance applies"
// The session-wide half, blind to the outcome: a call the gate has seen run
// three times may not run a fourth, whatever those runs returned. Set above the
// common work loop (edit, test, edit, test reaches two identical test runs, and
// a session's third `git status` still passes) so only a genuine spin reaches it.
const RETRY_CEILING = 3
// How much of the ledger tail the one-shot consent mark and the repeat guards
// read before an action is visible again (hooks/tezgah_gate.CONSENT_TAIL and the
// tail tezgah_integrity.prior_calls reads its attempts from).
const LEDGER_TAIL = 200
// Anti-shortcut: a check neutered so it cannot fail, or a test disabled so a
// failure disappears. Ported from hooks/tezgah_integrity.py so opencode denies
// the same shapes from the same patterns.
const VERIFY =
  /(?:^|[|;&(]\s*|\s)(?:(?:python3?|uv run)\s+-m\s+(?:pytest|unittest|mypy|ruff|flake8|compileall)|pytest|py\.test|npm\s+(?:test|t\b)|npm\s+run\s+\S*(?:test|lint|typecheck|check|build|ci)|(?:yarn|pnpm|bun)\s+(?:test|run\s+\S*(?:test|lint|build|check))|ruff|flake8|mypy|pyright|tsc|eslint|prettier|vitest|jest|ava|mocha|go\s+(?:test|vet)|cargo\s+(?:test|clippy|check|build)|tox|nox|pre-commit|(?:^|\s)(?:make|just)\b|\.\/\S*(?:test|check|lint)\S*|(?:\.\/)?(?:gradlew|mvn)\s+\S*(?:test|check)|dotnet\s+(?:test|build)|swift\s+test|golangci-lint|shellcheck)\b/i
const NEUTER = /\|\|\s*(?:true|:|exit\s+0)(?:\s|$|[|;&])|;\s*true\s*(?:$|[|;&])/
const SKIP_ENV = /\b(?:SKIP|HUSKY_SKIP_HOOKS)\s*=|\bHUSKY=0\b/
const NO_VERIFY = /--no-verify\b/
const GITISH = /\b(?:git|commit|push|husky|pre-commit|npm|yarn|pnpm)\b/i
const SKIP_TEST = new RegExp(
  "@pytest\\.mark\\.(?:skip|skipif|xfail|only)\\b|" +
  "@unittest\\.(?:skip|skipIf|skipTest|expectedFailure)\\b|" +
  "@Ignore\\b|@Disabled\\b|" +
  "\\bpytest\\.skip\\(|\\bunittest\\.(?:skip|skipIf|skipTest)\\(|" +
  "\\bt\\.Skip\\w*\\(|" +
  "\\b(?:it|test|describe)\\.(?:skip|only)\\(|\\bxit\\(|\\bxdescribe\\(|" +
  "\\bpytestmark\\s*=\\s*pytest\\.mark\\.skip", "gi")
// Only a test file can be disabled by a skip marker; a probe script, a note or
// a fixture that quotes one is not this rule's business. Ported from
// hooks/tezgah_integrity.TEST_PATH.
const TEST_PATH =
  /(?:^|\/)(?:tests?|__tests__|spec|specs)\/|(?:^|\/)(?:test_[^/]*|conftest|[^/]*_test)\.[A-Za-z0-9]+$|\.(?:test|spec)\.[A-Za-z0-9]+$/i
// Strings, comments and heredoc bodies are neither commands nor test code: the
// repo's own tests quote a skip marker, and a commit message that *describes*
// `--no-verify` disables nothing. Both scans run on a copy where those regions
// are blanked - length preserved, so a match keeps its offset.
const LITERALS =
  /'''[\s\S]*?'''|"""[\s\S]*?"""|'(?:\\.|[^'\\\n])*'|"(?:\\.|[^"\\\n])*"|\/\*[\s\S]*?\*\/|\/\/[^\n]*|#[^\n]*/g
const HEREDOC = /<<-?\s*['"]?([A-Za-z_][A-Za-z0-9_]*)['"]?/
// Mirrors hooks/tezgah_integrity.py WRITE_TOOLS exactly: the two halves must
// agree on what counts as a write, or a credit or a skip marker lands on
// whichever host has the narrower list.
const WRITE_TOOLS = new Set(["edit", "write", "multiedit", "notebookedit",
  "apply_patch", "str_replace_editor", "create_file", "str_replace",
  "edit_file", "write_file", "search_replace"])
// Mirrors hooks/tezgah_integrity.py BASH_TOOLS. A shell tool missing from this
// set takes the wrong branch twice: its command is hashed as a JSON object and
// its row is never written, so one call would carry two identities and the
// metrics would lose the call entirely. `pwsh` is there because dsh's own
// PowerShell tool is named that, while the five other spellings are what the
// hosts send.
const BASH_TOOLS = new Set(["bash", "shell", "command", "exec_command",
  "run_command", "powershell", "pwsh"])
// The core's task rule has a shell half no write tool takes: a command that
// moves the active task's own record (`hooks/tezgah_gate.TASK_CHANGE`), which is
// how an agent moves the phase or the allowlist it is being held to instead of
// retyping the record file. The rule, and the masking that lets a command merely
// naming the CLI through, are the core's, so its answer is asked for and used
// verbatim; what stays here is only the pre-test that decides whether asking is
// worth a spawn. A spawn per bash call would tax every command in the session
// for a rule about one, so the core is asked when the raw command names the CLI
// and carries an argument - loose on purpose in that direction, because a
// commit message or a comment that mentions the CLI costs one spawn whose answer
// comes back empty, while a pre-test tight enough to miss nothing would be the
// second implementation this host exists not to keep.
const TASK_CLI = /\btezgah-task\b\s+\S/
// Mirrors hooks/tezgah_integrity.py READ_TOOLS: known calls that do no step of
// work and that no rule reads a row for. A name missing from this set is not
// silently dropped - it records as `unknown`, which would fill the trace with
// every read.
const READ_TOOLS = new Set(["read", "read_file", "readfile", "notebookread",
  "notebook_read", "view", "cat", "grep", "grep_search", "search",
  "search_files", "rg", "find", "glob", "glob_search", "ls", "list",
  "list_dir", "listdir", "list_files", "tree"])

function blankHeredocs(text) {
  const lines = String(text || "").split("\n")
  const out = []
  let i = 0
  while (i < lines.length) {
    const m = lines[i].match(HEREDOC)
    if (!m) { out.push(lines[i]); i += 1; continue }
    const tag = m[1]
    let j = i + 1
    while (j < lines.length && lines[j].trim() !== tag) j += 1
    if (j === lines.length) { out.push(lines[i]); i += 1; continue }
    out.push(lines[i])
    for (let k = i + 1; k < j; k += 1) out.push(" ".repeat(lines[k].length))
    out.push(lines[j])
    i = j + 1
  }
  return out.join("\n")
}

function maskText(text) {
  return blankHeredocs(text).replace(LITERALS, (m) => " ".repeat(m.length))
}

function verifyCommand(cmd) {
  const m = String(cmd || "").match(VERIFY)
  return m ? m[0] : null
}

function shortcutCommand(cmd) {
  // the masked text, so a message that names the flag is not the flag
  const c = maskText(cmd)
  if (NO_VERIFY.test(c) && GITISH.test(c))
    return "Verification bypass denied: `--no-verify` skips the commit/push " +
      "hooks that run the checks. Run the checks, fix what they report, and " +
      "commit without it."
  if (SKIP_ENV.test(c) && GITISH.test(c))
    return "Verification bypass denied: an env var that skips the hooks " +
      "(SKIP=/HUSKY_SKIP_HOOKS/HUSKY=0) turns the checks off. Run them instead."
  if (verifyCommand(c) && NEUTER.test(c))
    return "Verification neutered: this check is chained with `|| true` / " +
      "`; true`, so it reports success no matter what it found. Run it plain " +
      "and read the real exit status."
  return null
}

function addedSkips(newText, oldText) {
  const before = {}
  for (const m of String(oldText || "").matchAll(SKIP_TEST)) {
    const low = m[0].toLowerCase()
    before[low] = (before[low] || 0) + 1
  }
  const out = []
  for (const m of String(newText || "").matchAll(SKIP_TEST)) {
    const low = m[0].toLowerCase()
    if (before[low] > 0) before[low] -= 1
    else if (!out.includes(m[0])) out.push(m[0])
  }
  return out
}

async function shortcutEdit(args) {
  const oldText = String(args?.oldString ?? args?.old_string ?? "")
  const newText = String(
    args?.newString ?? args?.new_string ?? args?.content ?? "")
  if (!newText) return null
  const p = String(args?.filePath ?? args?.file_path ?? args?.path ?? "")
  if (!TEST_PATH.test(p)) return null
  let base = oldText
  if (!base && p) {
    try { base = await readFile(expand(p), "utf8") } catch { base = "" }
  }
  const added = addedSkips(maskText(newText), maskText(base))
  if (!added.length) return null
  return "Test disable denied: this change adds " +
    [...new Set(added)].join(", ") + ". Making a failing test disappear is not " +
    "a fix - fix the code or say the test is failing. Ask the user first if the " +
    "skip is genuinely intended."
}

// --- the shell's write body: three write-tool rules reached through a heredoc -
// What this closes (hooks/tezgah_gate.SHELL_WRITE, and the route E7c measured):
// SKIP_TEST, ATTRIB_LINE and the credential scan are attached to WRITE_TOOLS,
// which is disjoint from BASH_TOOLS, so a heredoc that wrote a test skip, an
// attribution line or a key into a file was refused by nothing - and E7c watched
// the armed arm take exactly that route once the write tools were refused. Each
// of the three now also reads the body a shell command writes, and the body is
// the RAW text because maskText blanks heredoc bodies by design: a command that
// merely names a rule must not be denied.
//
// The shape test is the core's own SHELL_WRITE, ported here because the three
// rules below read a written body (the task rule's phase check is the core's and
// stays there). ponytail: only a heredoc's body is read; a write whose content is
// a quoted argument (`echo "Co-Authored-By: x" > f`) is not, and the measured
// route is the heredoc.
const SHELL_WRITE =
  />>?(?!\s*\/dev\/null)(?![&=])|\|\s*tee\b|(?<![\w-])(?:sed|perl)\s+(?:-\S+\s+)*(?:-[A-Za-z]*i[A-Za-z]*)(?![A-Za-z])|(?<![\w-])truncate\s|\bdd\s+[^|;&]*\bof=|(?<![\w-])(?:cp|mv)\s|(?<![\w-])patch\s|(?<![\w-])git\s+(?:apply\b|restore\b|checkout\s+--)/
const SHELL_TARGET = />>?(?![&=])\s*(\S+)|(?<![\w-])tee\s+(?:-\S+\s+)*(\S+)/

// Every heredoc body in `text`, in order, read off the raw text. Unterminated
// markers are skipped the way the masker skips them.
function heredocBodies(text) {
  const lines = String(text || "").split("\n")
  const out = []
  let i = 0
  while (i < lines.length) {
    const m = HEREDOC.exec(lines[i])
    if (!m) { i += 1; continue }
    const tag = m[1]
    let j = i + 1
    while (j < lines.length && lines[j].trim() !== tag) j += 1
    if (j === lines.length) { i += 1; continue }
    out.push(lines.slice(i + 1, j).join("\n"))
    i = j + 1
  }
  return out
}

// The file a shell command's own text writes, or "" - the real redirect's target
// (or `tee`'s argument) sliced from the raw text at the offset the masked match
// proved, so a quoted `>` is not a redirect and `> /dev/null` is not a file.
// The one reader of a shell write's target (hooks/tezgah_gate.shell_target):
// `writtenPath` uses it for the file a shell call changes, which is what makes
// the gate capture a pre-state for that write and `postWrite` hash its
// after-state, and `shellWriteBody` uses it for the file whose body the three
// write-tool twins read.
function shellTarget(command) {
  const c = String(command || "")
  if (!c) return ""
  const masked = maskText(c)
  if (!SHELL_WRITE.test(masked)) return ""
  const m = SHELL_TARGET.exec(masked)
  if (!m) return ""
  // Both branches capture the last token of the match, so its offset is the tail
  // of `m[0]` - no index lookup that a target named after a flag letter
  // (`| tee e`) could fool.
  const token = m[1] || m[2]
  return c.slice(m.index + m[0].length - token.length, m.index + m[0].length)
    .replace(/^['"]|['"]$/g, "")
}

// The `{filePath, content}` a shell command writes into a file, or null when this
// command writes no file's content of its own: the target is the real redirect's
// target (or `tee`'s argument), resolved against the call's own directory so a
// write to a test file is compared against the file the CALL named.
function shellWriteBody(command, dir) {
  const c = String(command || "")
  if (!c || !SHELL_WRITE.test(maskText(c))) return null
  const bodies = heredocBodies(c)
  if (!bodies.length) return null
  let p = shellTarget(c)
  if (p && !p.startsWith("/")) p = join(dir || process.cwd(), p)
  return { filePath: p, content: bodies.join("\n") }
}

// The text a write tool would land: the same predicate the edit/write half uses,
// reachable from the shell twin above.
function attributionText(args) {
  return EDIT_TEXT.some(
    (k) => typeof args?.[k] === "string" && ATTRIB_LINE.test(args[k]))
}

// The same action seen twice has to hash the same, or the ledger cannot tell a
// re-run from a different call. Objects are serialized as compact JSON with
// sorted keys, so the host's payload order cannot move the id and the string
// matches Python's json.dumps(sort_keys=True, separators=(",", ":")).
// A number needs its own form, because the id hashes Python's json.dumps text:
// an integral value prints as "1.0" there and "1" here, a small one as "1e-07"
// there and "1e-7" here, and an integral value at 2^53 or above in Python's
// float form ("1e+21"). The Python half coerces an integral float below 2^53 to
// an int, so that range is printed here in full digits; everything else is
// rendered in Python's repr shape - fixed while the exponent stays inside
// [-4, 15], scientific with a two-digit exponent outside it. One case is out of
// reach for both: an integer argument at or above 2^53 written as digits keeps
// its digits in Python and has already lost its intness by the time JavaScript
// parses it. A number printed the other way would give one call two ids.
function pyNumber(n) {
  if (Number.isInteger(n) && Math.abs(n) < 2 ** 53) return BigInt(n).toString()
  const m = n.toExponential().match(/^(-?)(\d)(?:\.(\d+))?e([+-]?\d+)$/)
  const digits = m[2] + (m[3] || "")
  const e = Number(m[4])
  if (e >= -4 && e <= 15) {
    const point = e + 1
    if (point <= 0) return m[1] + "0." + "0".repeat(-point) + digits
    return m[1] + digits.slice(0, point) + "." + (digits.slice(point) || "0")
  }
  return m[1] + m[2] + (m[3] ? "." + m[3] : "") + "e" +
    (e < 0 ? "-" : "+") + String(Math.abs(e)).padStart(2, "0")
}

function stable(value) {
  if (Array.isArray(value)) return "[" + value.map(stable).join(",") + "]"
  if (value && typeof value === "object") {
    return "{" + Object.keys(value).sort().map(
      (k) => JSON.stringify(k) + ":" + stable(value[k])).join(",") + "}"
  }
  if (typeof value === "number" && Number.isFinite(value)) return pyNumber(value)
  return JSON.stringify(value === undefined ? null : value)
}

// The action's identity, frozen with the Python writer (hooks/tezgah_integrity
// call_id) so one call hashes the same on both halves:
// sha1(tool + " " + canonical)[:12]. Shell tools have one canonical argument -
// the command every other check in this file reads, whitespace collapsed so a
// re-typed call is the same call; everything else is the args object as compact
// key-sorted JSON (Python: json.dumps(sort_keys=True, separators=(",", ":"))).
function canonicalArgs(tool, args) {
  const t = String(tool || "").toLowerCase()
  if (BASH_TOOLS.has(t)) {
    return String(args?.command || args?.cmd || "").replace(/\s+/g, " ").trim()
  }
  return stable(args || {})
}

function actionID(tool, args) {
  return createHash("sha1")
    .update(String(tool || "").toLowerCase() + " " + canonicalArgs(tool, args))
    .digest("hex").slice(0, 12)
}

// Credential redaction, ported from hooks/tezgah_integrity.redact: the ledger
// records what a call carried, and a token typed on a command line or written
// into a file would sit in plain text in a cache file every reader of the
// evidence reads. The marker keeps the removed value's length, so the row still
// says a credential was there instead of hiding that it was. The three patterns
// run in this order so a named value that carries `Bearer` is consumed as one.
// (SECRET_KEY/SECRET_TOKEN would be the names the Python half uses; the gate's
// own secret-sink detector above already holds SECRET_TOKEN here.)
const MARKED = "[redacted:"
const REDACT_KEY =
  /([A-Za-z0-9_\-]*(?:password|passwd|pwd|secret|token|api[_-]?key|apikey|access[_-]?key|authorization|client[_-]?secret))(\s*[:=]\s*)(?:Bearer\s+)?("[^"]*"|'[^']*'|\S+)/gi
const REDACT_BEARER = /\bBearer\s+[A-Za-z0-9._\-+/=]{8,}/gi
const REDACT_TOKEN =
  /\b(?:sk|pk|rk)[-_](?:live|test|proj|ant|api[0-9]*)?[-_]?[A-Za-z0-9_\-]{16,}|\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}|\bgithub_pat_[A-Za-z0-9_]{20,}|\bxox[baprs]-[A-Za-z0-9-]{10,}|\b(?:AKIA|ASIA)[0-9A-Z]{16}\b|\bAIza[0-9A-Za-z_\-]{30,}|\bglpat-[A-Za-z0-9_\-]{20,}|\bnpm_[A-Za-z0-9]{30,}/gi

function redact(text) {
  const mark = (value) => MARKED + value.length + "]"
  return String(text == null ? "" : text)
    .replace(REDACT_KEY, (m, name, sep, value) => name + sep + mark(value))
    .replace(REDACT_BEARER, (m) => mark(m))
    .replace(REDACT_TOKEN, (m) => mark(m))
}

// The row's own bound: what a tip-off line costs, and enough of a command to
// recognize it. The scan runs over the whole text before this cut, so a
// credential near the end cannot hide by being half-stored (DETAIL_MAX in
// hooks/tezgah_integrity).
const DETAIL_MAX = 200
// ponytail: the lengths above and the cut below count UTF-16 units where Python
// counts characters. Every shape the three patterns name is ASCII, so the two
// agree on the credential itself; they differ only for an astral character
// inside a quoted named value.

// Evidence ledger, the same JSONL the Python gate and Stop hook read. Written
// per tool call so a "done/tested" claim can be checked against what ran.
// The bash tool returns `metadata.exit` (the process exit code), so a check's
// real outcome is available: exit 0 -> verify_ok, non-zero -> verify_fail, and
// `verify` only when the code is absent (aborted/spawn failure).
// The row carries the contract's fields - id, exit, out_bytes, workspace - so
// an opencode session is not second-class in the metrics. A field the host did
// not report stays out of the row: an absent exit is not an exit of 0.
// A name outside every list - a tool this host does not have (a fabricated
// call), or one it added since this was written - records as `unknown` with the
// name in the detail, as hooks/tezgah_integrity.note_tool does: dropping the
// call left no ledger line at all, so the trace could not show it happened. Only
// the read/search tools record nothing. A write also carries the target's
// after-state (postWrite).
async function recordEvidence(sessionID, tool, args, result, workspace, cwd) {
  if (!sessionID) return
  const t = String(tool || "").toLowerCase()
  const exit = result?.metadata?.exit
  let kind = null
  let detail = String(args?.command || args?.filePath || args?.file_path || "")
  if (WRITE_TOOLS.has(t)) kind = "edit"
  else if (BASH_TOOLS.has(t)) {
    if (!verifyCommand(args?.command || args?.cmd || "")) kind = "run"
    else {
      kind = typeof exit === "number"
        ? (exit === 0 ? "verify_ok" : "verify_fail") : "verify"
    }
  } else if (READ_TOOLS.has(t)) {
    return
  } else {
    const name = String(tool || "").trim()
    if (!name) return
    kind = "unknown"
    detail = "unknown tool: " + name
  }
  const out = typeof result?.output === "string" ? result.output
    : (typeof result?.metadata?.output === "string" ? result.metadata.output : null)
  const row = {
    kind, ts: Math.floor(Date.now() / 1000),
    detail: redact(detail).slice(0, DETAIL_MAX),
    id: actionID(tool, args), workspace: workspace || null,
  }
  if (typeof exit === "number") row.exit = exit
  if (out !== null) row.out_bytes = Buffer.byteLength(out)
  // A write tool's `edit` row and a shell call that writes a file (`run`) carry
  // the same after-state pair, because the gate captured the same target for both
  // (hooks/tezgah_integrity.note_tool). A check row is not one: the row that
  // carries the pass cannot also be the row the freshness fold reads as the
  // change, or a check redirecting its own output would put the two at one
  // position and refuse the turn that ran it.
  if (kind === "edit" || (kind === "run" && writtenPath(args))) {
    Object.assign(row, await postWrite(sessionID, args, cwd))
  }
  await appendRow(sessionID, row)
}

// How far back the pre-state search reads: the gate writes its snapshot row in
// the call immediately before the write, so the newest rows are where it is
// (SNAPSHOT_TAIL in hooks/tezgah_integrity).
const SNAPSHOT_TAIL = 50
// The file a call writes: the tool's own path field, else the first path an
// apply_patch body names, else the file a shell command's own text writes through
// a redirect or `tee` - the one write whose target leaves no path field behind
// (hooks/tezgah_gate.write_paths, shellTarget). Raw and unresolved, as the Python
// reader returns it: each caller resolves it against its own directory.
const WRITE_PATH = ["file_path", "filePath", "path"]
const PATCH_FILE = /^\*\*\* (?:Update|Add|Delete) File: (\S.*?)\s*$/m

function writtenPath(args) {
  const a = args || {}
  for (const key of WRITE_PATH) {
    const value = a[key]
    if (typeof value === "string" && value.trim()) return value.trim()
  }
  const m = PATCH_FILE.exec(String(a.patch || ""))
  if (m) return m[1]
  const target = shellTarget(a.command || a.cmd || "")
  return target || null
}

// sha256 of a file's bytes, the digest the Python half records
// (hooks/tezgah_snapshot._hash_file), or null when it is not there or not
// readable. Streamed, block by block: a hash the size of the file would be a
// second copy of it in memory.
function fileDigest(path) {
  return new Promise((resolve) => {
    try {
      const hash = createHash("sha256")
      const stream = createReadStream(path)
      stream.on("error", () => resolve(null))
      stream.on("data", (block) => hash.update(block))
      stream.on("end", () => resolve(hash.digest("hex")))
    } catch {
      resolve(null)
    }
  })
}

// The pre-write hash the gate's capture recorded for this path, or null
// (hooks/tezgah_integrity._snapshot_hash): a `snapshot` row whose detail is the
// file's realpath carries its pre-write sha256. Null means no capture ran - a
// new file, an over-large one, a write the gate never saw - and a pre-state that
// was never recorded is not invented.
async function snapshotHash(sessionID, path) {
  const rows = await ledgerTail(sessionID, SNAPSHOT_TAIL)
  for (let i = rows.length - 1; i >= 0; i--) {
    if (rows[i].kind === "snapshot" && String(rows[i].detail || "") === path) {
      return rows[i].hash ?? null
    }
  }
  return null
}

// The after-state of a write: the target's sha256 once the host returned, and -
// when the capture left a pre-state - whether the two differ, exactly as
// hooks/tezgah_integrity._post_write records it. tool.execute.after is this
// host's post-write surface: it runs after the host has written, which is the
// one moment the after-state exists, so the plugin carries it rather than
// claiming it cannot. A call the host reports as a successful write need not
// have changed anything - an edit whose anchor text was not found, a patch
// already applied - and this is what tells those apart. The first target is the
// one recorded, the single-path rule the row's `detail` already follows.
async function postWrite(sessionID, args, cwd) {
  const path = writtenPath(args)
  if (!path) return {}
  let apath
  try {
    apath = realpathSync(isAbsolute(path) ? path : join(cwd || ".", path))
  } catch {
    return {}  // gone or unreadable: the row carries what was seen, not assumed
  }
  const after = await fileDigest(apath)
  if (after === null) return {}
  const before = await snapshotHash(sessionID, apath)
  if (before === null) return { hash: after }
  return { hash: after, changed: before !== after }
}

// One row appended to a session's ledger, the same JSONL the Python gate and the
// Stop hook read (hooks/tezgah_integrity.note). Best effort: a write failure is
// not fatal, and the one caller that needs the row to exist - the consent mark -
// then refuses again next time rather than letting the action through.
//
// The line is written by one write(2) of the whole row on an O_APPEND handle,
// which is not the flock the Python writer takes: node core exposes no flock(2)
// (typeof fs.flock is undefined, and fcntl is not bound either), so the same
// lock would need a native addon or a helper process, neither of which belongs
// in a plugin that has to load on a bare host. Same file, one line at a time,
// not the same lock: the kernel's atomic append for a single write is what
// serializes this writer against Python's, and on a filesystem where that
// atomicity is not guaranteed (NFS) a torn line is possible here where the
// flock would prevent it.
async function appendRow(sessionID, row) {
  try {
    const dir = join(cacheDir(), "evidence")
    await mkdir(dir, { recursive: true })
    await appendFile(join(dir, ledgerStem(sessionID) + ".jsonl"),
      JSON.stringify(row) + "\n")
  } catch {}
}

// The ledger tail, oldest first, as the Python guard reads it
// (hooks/tezgah_integrity.events(session_id, tail)). It is read only after a
// rule has matched, so a normal call pays nothing - but it runs on every gated
// bash call of a matched one, and the file grows with the session, so the read
// is bounded like the Python one: backwards in chunks until the last `tail`
// lines are in hand, never a parse of the whole ledger. A chunk boundary can
// split the first line; it fails to parse and is dropped, which is the same
// partial-line tolerance `_tail_lines` has.
const TAIL_CHUNK = 8192

async function ledgerTail(sessionID, tail) {
  let text = ""
  try {
    const fh = await open(join(cacheDir(), "evidence",
                               ledgerStem(sessionID) + ".jsonl"), "r")
    try {
      let pos = (await fh.stat()).size
      while (pos > 0 && (text.match(/\n/g) || []).length <= tail) {
        const step = Math.min(TAIL_CHUNK, pos)
        pos -= step
        const buf = Buffer.alloc(step)
        await fh.read(buf, 0, step, pos)
        text = buf.toString("utf8") + text
      }
    } finally {
      await fh.close()
    }
  } catch {
    return []
  }
  const rows = []
  for (const line of text.split("\n").filter((l) => l.trim()).slice(-tail)) {
    try { rows.push(JSON.parse(line)) } catch {}
  }
  return rows
}

// (attempts in the current user turn, attempts over the whole tail, the newest
// attempt's exit, its failure class) for one action identity - the Python
// guard's tezgah_integrity.prior_calls. Only rows that carry an `exit` are
// attempts: a `deny` row and the consent mark carry the same id with no outcome,
// so counting them would leave the refusal itself as the newest row, read as "no
// failure" and disarm the ceiling on every second repeat. A `turn` row opens the
// current user turn; when the ledger carries none, the whole window is the turn.
function priorCalls(rows, digest) {
  let start = 0
  for (let i = rows.length - 1; i >= 0; i--) {
    if (rows[i].kind === "turn") { start = i + 1; break }
  }
  let made = 0
  let turn = 0
  let last = null
  rows.forEach((row, i) => {
    if (row.id !== digest || !("exit" in row)) return
    made++
    if (i >= start) { turn++; last = row }
  })
  if (!turn) return [0, made, null, null]
  return [turn, made, last.exit, last.fail_class ?? null]
}

// The identical attempts this failure class allows (hooks/tezgah_gate
// .loop_ceiling): a class no host error text named gets the base allowance.
function loopCeiling(klass) {
  return CLASS_CEILING[klass] ?? LOOP_CEILING
}

// The failure-scoped half of the repeat rule, or null: this exact call already
// failed often enough in this user turn. Past the ceiling the identical retry
// cannot work - the agent has to change the approach or stop, which is the
// contract's loop rule ("never repeat an identical failing command") given a
// mechanical half. A call that never failed, or that failed differently, is not
// this rule's.
function loopReason(tool, args, rows) {
  const [turn, , lastExit, klass] = priorCalls(rows, actionID(tool, args))
  const ceiling = loopCeiling(klass)
  if (lastExit !== 1 || turn < ceiling) return null
  return "Loop guard denied: this is attempt " + (turn + 1) + " of an identical " +
    "call whose " + turn + " previous attempt" + (turn === 1 ? "" : "s") +
    " exited 1" + (klass ? " (a " + klass + " failure)" : "") +
    ". This class allows " + ceiling + " identical attempt" +
    (ceiling === 1 ? "" : "s") + ", because " +
    (CLASS_NOTE[klass] ?? NO_CLASS_NOTE) + ". Repeating an identical failing " +
    "command is not a retry - change the approach (fix what the error names, " +
    "or run something else) or stop and report what is still unknown."
}

// The session-wide half, blind to the outcome, or null: a call this session has
// already attempted RETRY_CEILING times may not run again, whatever those runs
// returned. `loop` needs a failure to fire, so the call that runs ten times and
// returns 0 each time - the spin that never reaches a decision - would pass it
// forever. A refused call never ran, so the gate's own rows are not attempts.
function retryReason(tool, args, rows) {
  const attempts = priorCalls(rows, actionID(tool, args))[1]
  if (attempts < RETRY_CEILING) return null
  return "Retry ceiling denied: this is attempt " + (attempts + 1) + " of an " +
    "identical call in this session, past the ceiling of " + RETRY_CEILING +
    " attempts whatever their outcome. An unchanged repeat is not a retry - " +
    "change the arguments or the target, or stop and report what is still " +
    "unknown. (The `loop` guard is the narrower rule: the identical attempts " +
    "that FAILED, counted per user turn.)"
}

// --- ordering: a commit while the newest check failed -----------------------
// The one rule here that asserts a relation between two actions rather than
// reading one call plus a ledger tail (hooks/tezgah_gate.commit_order_reason).
// The reader is the Stop rule's own fold, `lastVerify` over the tail, and the
// rule cannot fire in either direction that would punish honest work: no check
// folds to null and a passing newest check to "ok", so a commit in a session that
// ran no check, and a commit after a green run, both pass. Only "fail" refuses.
// The passing_check narrowing (an exit-0 check with no output, or a piped one,
// counting as "ran" rather than "ok") is not mirrored because this rule reads
// only `fail`: those rows fold to "ok"/"ran" on both sides and the outcome is
// identical. The refusal names the failing check and no command that lifts it.
const FAILED_MARK = "[exit!=0]"
const COMMIT_CMD =
  /(?:^|[|;&]\s*|\s)git\s+(?:-{1,2}\S+(?:\s+\S+)?\s+)*commit(?=\s|$|[|;&])/
const ORDER_DENY =
  "Commit order denied: the newest check in this session failed, and a commit " +
  "is a claim that the tree passed. What would be frozen is the state that " +
  "check just rejected - the newest failing one was %s - so fix what it " +
  "reported and run it again, commit once the newest check is green, or say " +
  "plainly that it is failing and why the commit is wanted anyway."

// The newest check's state, folded exactly as tezgah_integrity._last_verify
// folds it: "ok"/"ran" for the verify kinds, "fail" for verify_fail, null when
// the tail carries no check at all.
function lastVerify(rows) {
  let state = null
  for (const row of rows) {
    if (row.kind === "verify_ok") state = "ok"
    else if (row.kind === "verify_fail") state = "fail"
    else if (row.kind === "verify") state = "ran"
  }
  return state
}

// The command of the newest failed check, for the reason text: the tail marker
// the record writes is not part of it.
function failedCheck(rows) {
  for (let i = rows.length - 1; i >= 0; i--) {
    if (rows[i].kind === "verify_fail") {
      const text = String(rows[i].detail || "").split(FAILED_MARK).join("").trim()
      return text || "a check"
    }
  }
  return "a check"
}

// The ordering refusal, or null: this command is a commit and the newest check
// in this session failed. Not a rule about commits - with no check in the tail
// nothing is refused.
function orderReason(args, rows) {
  if (!COMMIT_CMD.test(maskText(args?.command || args?.cmd || ""))) return null
  if (lastVerify(rows) !== "fail") return null
  return ORDER_DENY.replace("%s", failedCheck(rows))
}

// The kinds a PostToolUse hook writes after a call ran, whatever the host
// reported about the outcome (hooks/tezgah_integrity.STEP_KINDS). What spends a
// grant is one of these, never the presence of `exit`: this host records no exit
// for a shell call whose result carries no `metadata.exit`, and a lease only
// `exit` could spend would be a standing permit there.
const STEP_KINDS = new Set(["run", "edit", "verify", "verify_ok", "verify_fail"])

// Which consent record this action already carries in this workspace: "grant"
// when bin/tezgah-consent recorded the user's own approval and the effect has
// not spent it yet, "ask" when only the gate's refusal is on record for this
// workspace, null when neither is (hooks/tezgah_gate.consent_mark).
//
// A grant is a lease on ONE effect, not a standing permit: the row the effect
// leaves behind - the same id carrying an outcome - is what proves it ran, so the
// next identical command goes back to the user instead of running on the first
// approval forever (hooks/tezgah_gate.unspent_grant). The lease also belongs to
// one workspace: the action id is tool plus args with no cwd (the loop guard's
// key too), while the effect is resolved against the directory the call runs in,
// so the ask row records that directory and a grant answers the action there and
// not the same text somewhere else. Two rows, two facts, never one row
// conflating them: the gate writes `consent` (it asked) and never `grant` - a
// grant is the user's, written by the CLI, so the approval cannot be forged by
// the rule it constrains. Read by kind, id and that workspace, so "who was asked
// to confirm what, and who answered" is a query over rows rather than a match on
// a deny message a later reword would silently break.
async function consentMark(sessionID, digest, workspace) {
  if (!sessionID || !digest) return null
  const rows = await ledgerTail(sessionID, LEDGER_TAIL)
  const at = rows.map((row) => row.kind === "grant" && row.id === digest)
    .lastIndexOf(true)
  const asked = rows.map((row) => row.kind === "consent" && row.id === digest)
    .lastIndexOf(true)
  const mine = asked === -1 || (rows[asked].workspace ?? null) === workspace
  const spent = at !== -1
    && rows.slice(at + 1).some((row) => row.id === digest
                                && STEP_KINDS.has(row.kind))
  if (at !== -1 && !spent && mine) return "grant"
  if (asked !== -1 && mine) return "ask"
  return null
}

// The directory a call runs in, as the lease's scope: hooks/tezgah_gate.py
// records os.path.realpath(cwd) on the ask row and compares the same value, so
// this half resolves the path the same way - a row written here is then one the
// Python reader honours, and vice versa (bin/tezgah-gate is handed the same dir
// as cwd). Falls back to the raw string, and the lease then simply does not
// match: a scope that cannot be resolved must never be a standing permit.
function leaseScope(dir) {
  try {
    return realpathSync(dir)
  } catch {
    return String(dir || "")
  }
}

// A consent row: the gate's own fact, `consent` (it asked). `detail` is the
// effect class and `id` the action digest, so both are read back by kind and id.
// The gate writes no `grant` - that row belongs to the user.
async function noteConsentRow(sessionID, kind, klass, digest, workspace) {
  if (!sessionID) return
  await appendRow(sessionID, {
    kind, ts: Math.floor(Date.now() / 1000), detail: klass,
    id: digest, workspace: workspace || null,
  })
}

// The refusal recorded before it is returned, as the Python gate's `_deny` does:
// a deny nobody counts is a rule whose effect can never be argued about, and the
// row says which action the rule stopped and where. `extra` appends a fact the
// row must keep beyond the 80 characters of the reason it truncates, which is
// where a declaration the class refused stays visible (consentEffect).
async function noteDeny(sessionID, rule, reason, tool, args, workspace, extra) {
  if (!sessionID) return
  let detail = rule + ": " + String(reason).slice(0, 80)
  if (extra) detail += "; " + extra
  await appendRow(sessionID, {
    kind: "deny", ts: Math.floor(Date.now() / 1000), detail,
    id: actionID(tool, args), workspace: workspace || null,
  })
}

// Consent, then secret: the two shell rules that need the ledger. The class is
// the one the command text derives, raised by a `tezgah:effect=` declaration that
// is at least as severe and never lowered by one that is not (consentEffect);
// what the ledger then holds is one row per fact - `consent` for the ask, and,
// written by bin/tezgah-consent and never here, the user's own `grant`. An
// action already asked about falls through to the secret scan exactly as it does
// in the Python gate. Both stay armed under `verify-off`: that kill switch
// removes the shortcut
// and repeat rules, not the consent the user owes.
async function shellRules(tool, args, sessionID, base, dir) {
  const cmd = String(args.command || args.cmd || "")
  const digest = actionID(tool, args)
  // The lease's scope, the directory this call runs in - the digest carries the
  // command text and not the place, so the ask row records the place (see
  // consentMark).
  const scope = leaseScope(dir)
  const [klass, ignored] = consentEffect(cmd, dir, base)
  const mark = klass ? await consentMark(sessionID, digest, scope) : null
  if (klass && mark === null) {
    await noteConsentRow(sessionID, "consent", klass, digest, scope)
    const reason = consentReason(klass, ignored, false, digest)
    await noteDeny(sessionID, "consent", reason, tool, args, base,
                   ignored ? "declared `" + ignored + "` ignored, `" + klass +
                             "` stands" : null)
    return reason
  }
  if (klass && mark === "ask") {
    // The ask is on record and no approval came back, so a bare re-issue is
    // refused again rather than passing on its own earlier refusal - the Python
    // gate does the same (hooks/tezgah_gate.decision). No second `consent` row:
    // one question, asked once. A `grant` here would claim a consent the user
    // never gave.
    const reason = consentReason(klass, ignored, true, digest)
    await noteDeny(sessionID, "consent", reason, tool, args, base,
                   ignored ? "declared `" + ignored + "` ignored, `" + klass +
                             "` stands" : null)
    return reason
  }
  if (klass === null && SEND_CANDIDATE.test(cmd)) {
    // The one class this file does not derive, asked of the core that owns the
    // SEND pattern: bin/tezgah-gate runs hooks/tezgah_gate.decision, whose
    // refusal is used here verbatim, and that side writes its own `consent` and
    // `deny` rows - so this half writes none. An empty answer (a CLI that is not
    // installed, or a command the core lets through) falls through to the
    // credential scan exactly as before.
    const fromCore = await gateReason(tool, args, dir, sessionID)
    if (fromCore) return fromCore
  }
  const reason = secretCommand(cmd)
  if (reason) {
    await noteDeny(sessionID, "secret", reason, tool, args, base)
    return reason
  }
  // The body a heredoc writes: maskText blanks it, so the text-level scan above
  // cannot see a key that sits in it (hooks/tezgah_gate.shell_write_body).
  const body = shellWriteBody(cmd, dir)
  if (body && SECRET_TOKEN.test(body.content)) {
    await noteDeny(sessionID, "secret", SECRET_DENY, tool, args, base)
    return SECRET_DENY
  }
  return null
}

// `loop` then `retry`, over one read of the ledger tail, after every
// argument-shaped rule: a call another rule would have refused has to be counted
// as that rule, not as a repeat.
async function repeatRules(tool, args, sessionID, base) {
  if (!sessionID) return null
  const rows = await ledgerTail(sessionID, LEDGER_TAIL)
  const loop = loopReason(tool, args, rows)
  if (loop) {
    await noteDeny(sessionID, "loop", loop, tool, args, base)
    return loop
  }
  const retry = retryReason(tool, args, rows)
  if (retry) await noteDeny(sessionID, "retry", retry, tool, args, base)
  return retry
}

function attribution(tool, args) {
  const t = String(tool || "").toLowerCase()
  if (BASH_TOOLS.has(t)) {
    const cmd = String(args?.command || args?.cmd || "")
    return WRITE_CMD.test(cmd) && ATTRIB.test(cmd)
  }
  // The bash path needs WRITE_CMD to establish that a commit or PR body is
  // being written; for a write/edit tool the tool itself is the write, so the
  // content is the whole question.
  if (WRITE_TOOLS.has(t)) return attributionText(args)
  return false
}

// The shell's own write route: a credit inside a heredoc lands in a file exactly
// as one in an edit's content does, and BASH_TOOLS/ WRITE_TOOLS are disjoint, so
// the text check above never sees it (hooks/tezgah_gate.shell_write_body).
function shellAttribution(args) {
  const body = shellWriteBody(args?.command || args?.cmd || "")
  return body !== null && attributionText(body)
}

// Python's os.path.realpath(strict=False): the symlinks that exist are resolved
// and the segments below them are kept, so a path that does not exist yet still
// compares the way the Python gate compares it. macOS makes /tmp and /var
// symlinks, which is what keeps `rm -rf /tmp/x` outside a run directory under
// /tmp.
function realPath(p) {
  const abs = resolve(p)
  let dir = abs
  const tail = []
  for (;;) {
    try {
      return join(realpathSync(dir), ...tail)
    } catch {}
    const up = dirname(dir)
    if (up === dir) return abs
    tail.unshift(basename(dir))
    dir = up
  }
}

// The temp roots (SCRATCH_ROOTS in the Python gate): a `rm -rf` under one is
// scratch, not an irreversible effect - the directory exists to be thrown away,
// so the user's ask would protect nothing and a session clearing its own
// fixtures is held to none. The root itself is NOT scratch (deleting all of
// /tmp is not a cleanup) and neither is a path that only escapes through it:
// both sides are realpath'd before the test, so `/tmp/../etc` escapes.
const SCRATCH_ROOTS = [realPath(tmpdir()), realPath("/tmp")]

// True when this line recursively force-deletes a path outside the run directory
// (`cwd`, the directory the command runs in). The `rm` is found on the masked
// text - a message that names the command deletes nothing - while the flags and
// targets are read from the raw text at the same offset, so a quoted path still
// resolves. The run directory itself counts as outside: deleting where the
// command runs is not a delete inside it. A target this cannot resolve (`$VAR`,
// `~`, a URL) counts as outside too; the conservative direction is the one that
// stops to ask. A target UNDER a temp root is neither: that is the session's own
// scratch. ponytail: a target behind a `cd` in the same line resolves against
// `cwd`, not against the `cd`, so that case can pass - it fails open.
function rmOutside(masked, raw, cwd, base) {
  const root = realPath(cwd || base)
  for (const m of masked.matchAll(RM)) {
    // The args come from the raw text at the offset the masked match proved is a
    // real `rm`: on the masked text a blanked target reads as more flags.
    RM_AT.lastIndex = m.index
    const r = RM_AT.exec(raw)
    if (!r) continue
    if (!(RM_RECURSIVE.test(r[1]) && RM_FORCE.test(r[1]))) continue
    for (const flagless of r[2].split(/\s+/)) {
      if (!flagless || flagless.startsWith("-")) continue
      const tok = flagless.replace(/^['"]+|['"]+$/g, "")
      if (!tok) continue
      if (tok.includes("$") || tok.includes("~") || tok.includes("://")) return true
      const p = realPath(isAbsolute(tok) ? tok : resolve(root, tok))
      if (p === root) return true
      if (p.startsWith(root + sep)) continue
      if (SCRATCH_ROOTS.some((s) => p.startsWith(s + sep))) continue
      return true
    }
  }
  return false
}

// The effect class of an irreversible or outward-facing command, or null:
// `destructive` rewrites or drops history, a branch or files outside the run
// directory; `schema` changes the shape of a database; `deploy` puts code in
// front of users; `publish` ships an artifact to a registry or a release;
// `outward` pushes to a live target rather than a branch under review. A command
// carries the first class that matches, so the refusal says what the action is
// instead of listing the patterns it hit.
//
// One call is all the gate sees and it cannot ask, so the ask becomes a refusal
// the user reads. What the ledger then says is the point: the `consent` row
// records the ask, and a `grant` - the user's own approval, written by
// bin/tezgah-consent and never here - records a pass the user authorised before
// the command ran, for one effect (see consentMark). That is the least friction
// that still stops an agent spending someone else's branch, database or
// deployment unasked: the refusal stands until the user answers, and a bare
// re-issue is refused again rather than passing on its own earlier refusal. A
// session whose ledger cannot be written refuses every time, so there the ask has
// to happen outside the agent.
// True when this line destroys a shared resource at a service: the remote
// repository `gh repo delete|archive`, the bucket `aws s3 rb`, or the prefix
// `aws s3 rm --recursive` (hooks/tezgah_gate.remote_destroy).
//
// The command is found on the masked text - a message that names it destroys
// nothing - while the `--recursive` flag is read from the raw text at the same
// offset, because the masker blanks a `//` comment tail and takes the flag with
// it. The flag has to sit in the same simple command.
function remoteDestroy(masked, raw) {
  if (REMOTE_DESTROY.test(masked)) return true
  for (const m of masked.matchAll(AWS_S3_RM)) {
    const tail = raw.slice(m.index)
    const end = tail.search(/[;&\n]/)
    if (AWS_RECURSIVE.test(end === -1 ? tail : tail.slice(0, end))) return true
  }
  return false
}

function effectClass(command, cwd, base) {
  const c = String(command || "")
  if (!c) return null
  const masked = maskText(c)
  for (const m of masked.matchAll(GIT_PUSH)) {
    if (FORCE_FLAG.test(m[1]) && !SCRATCH.test(m[1])) return "destructive"
  }
  if (BRANCH_DELETE.test(masked) || remoteDestroy(masked, c)
      || rmOutside(masked, c, cwd, base)) {
    return "destructive"
  }
  if (MIGRATION.test(masked)) return "schema"
  if (DEPLOY.test(masked)) return "deploy"
  if (PUBLISH.test(masked)) return "publish"
  if (OUTWARD.test(masked)) return "outward"
  return null
}

// The class this command declares for itself with `tezgah:effect=<class>`, or
// null when it declares nothing or nothing this gate knows how to rank.
function declaredEffect(command) {
  const m = DECLARED_EFFECT.exec(String(command || ""))
  const klass = m ? m[1].toLowerCase() : ""
  return Object.prototype.hasOwnProperty.call(EFFECTS, klass) ? klass : null
}

// The class to hold this command to, and the declaration it ignored, as the
// Python gate's consent_effect decides it.
//
// A command may declare `tezgah:effect=<class>`, which is how an effect no
// pattern here can see - someone's own deploy script, a migration runner this
// module does not know - still gets asked about. The declaration is taken only
// when it stands at or above the class the command text derives along
// EFFECT_RANK, and one that would stand below it is ignored: a declaration able
// to lower a class is a bypass of the very gate that reads it. So the declaration
// can tighten the rule and never loosen it. Returns [class, ignored declaration].
function consentEffect(command, cwd, base) {
  const derived = effectClass(command, cwd, base)
  const declared = declaredEffect(command)
  if (declared === null) return [derived, null]
  if (derived !== null &&
      EFFECT_RANK.indexOf(declared) < EFFECT_RANK.indexOf(derived)) {
    return [derived, declared]
  }
  return [declared, null]
}

// The refusal for one effect class: the class, what it means, and what to ask,
// never the list of patterns the command happened to match. An ignored
// declaration is named with it, so an attempt to talk the class down reaches the
// user instead of failing silently.
function consentReason(klass, ignored, asked, digest) {
  let reason = CONSENT_DENY.replace("%s", klass)
    .replace("%s", EFFECTS[klass])
    .replace("%s", digest || "?")
  if (asked) {
    reason += ASK_STANDS_NOTE
  }
  if (ignored) {
    reason += DOWNGRADE_NOTE.replace("%s", ignored).replace("%s", klass)
  }
  return reason
}

// The refusal when this command would write a credential into a file, or null.
// Reading an env var or running a tool with a key in its env is the normal work
// this must not touch, so a token only counts next to a write sink, and a sink
// only carries the text of its own simple command.
function secretCommand(command) {
  const c = String(command || "")
  if (!c || !SECRET_TOKEN.test(c)) return null
  const masked = maskText(c)
  let start = 0
  const ends = [...masked.matchAll(SEGMENT)].map((m) => m.index)
  for (const end of ends.concat(c.length)) {
    if (SECRET_TOKEN.test(c.slice(start, end))
        && SECRET_SINK.test(masked.slice(start, end))) {
      return SECRET_DENY
    }
    start = end
  }
  return null
}

function expand(p) {
  return String(p || "").replace(/^~(?=$|\/)/, HOME)
}

async function roots() {
  if (process.env.TEZGAH_ROOTS) {
    return process.env.TEZGAH_ROOTS.split(":").map(expand).filter(Boolean)
  }
  try {
    const cfg = JSON.parse(await readFile(join(CONFIG, "config.json"), "utf8"))
    if (Array.isArray(cfg.roots) && cfg.roots.length) return cfg.roots.map(expand)
  } catch {}
  return [join(HOME, "Projects")]
}

function under(dir, root) {
  return dir === root || dir.startsWith(root.endsWith("/") ? root : root + "/")
}

async function rootFor(dir) {
  for (const r of await roots()) if (under(dir, r)) return r
  return null
}

function off(name) {
  return existsSync(join(CONFIG, name)) || existsSync(join(HOME, ".claude", name))
}

function slug(p) {
  return p.replace(/[^A-Za-z0-9]+/g, "-").replace(/^-+|-+$/g, "")
}

// The evidence ledger's filename stem, frozen with the Python reader
// (hooks/tezgah_integrity._slug): the punctuation-collapsed session id cut to
// 40 characters, then the first 12 hex of sha1 over the raw id. Two ids
// differing only in punctuation collapse to the same prefix, and without the
// hash suffix this writer would append one session's rows to another session's
// ledger - the file the loop guard and the counters then read. The plain
// `slug()` above still names the used-marks and index files, as before.
function ledgerStem(sessionID) {
  const raw = String(sessionID == null ? "" : sessionID) || "nosession"
  return slug(raw).slice(0, 40) + "-" +
    createHash("sha1").update(raw, "utf8").digest("hex").slice(0, 12)
}

// The nearest enclosing path that has a codebase-memory index db.
function indexSlug(dir) {
  let d = dir
  for (;;) {
    if (existsSync(join(CBM_DIR, slug(d) + ".db"))) return slug(d)
    const parent = d.replace(/\/[^/]+\/?$/, "")
    if (!parent || parent === d) return null
    d = parent
  }
}

function identifierFrom(tool, args) {
  if (tool === "grep") {
    const p = String(args.pattern || "")
    return IDENT.test(p) ? p : null
  }
  if (tool === "bash" || tool === "shell") {
    const cmd = String(args.command || "")
    const m = cmd.match(/(?:^|[|;&(]\s*|\s)(?:grep|rg)\s+((?:-\S+\s+)*)(\S+)/)
    if (!m) return null
    const tok = m[2].replace(/^['"]|['"]$/g, "")
    return IDENT.test(tok) ? tok : null
  }
  return null
}

// Best-effort view of a permission request as a {tool, args} pair. The payload
// shape drifts across opencode versions (the 1.17 plugin types use
// `type`/`pattern`; newer internal payloads use `permission`/`patterns`/
// `metadata`), so read every plausible field and bail out rather than guess.
// Conservative on purpose: a wrong match would deny an unrelated tool.
function permissionToolArgs(input) {
  const md =
    input && typeof input.metadata === "object" && input.metadata ? input.metadata : {}
  const kind = String(input?.type || input?.permission || md.tool || "").toLowerCase()
  const tool = String(md.tool || input?.tool || kind || "").toLowerCase()
  let patterns = input?.pattern ?? input?.patterns
  if (typeof patterns === "string") patterns = [patterns]
  if (!Array.isArray(patterns)) patterns = []
  const first = patterns.length ? String(patterns[0]) : ""
  const args = {
    pattern: md.pattern ?? md.patterns ?? first,
    command: md.command ?? md.cmd ?? "",
    subagent_type: md.subagent_type ?? md.subagent ?? "",
    agent: md.agent ?? md.subagent_type ?? "",
  }
  if (!args.command && /shell|bash|command/.test(kind)) {
    args.command = first || String(input?.title || "")
  }
  return { tool, args }
}

async function oncePerSession(sessionID) {  const key = createHash("sha1").update(String(sessionID || "nosession")).digest("hex").slice(0, 16)
  const dir = join(cacheDir(), "nudged")
  const mark = join(dir, key)
  if (existsSync(mark)) return false
  try {
    await mkdir(dir, { recursive: true })
    await writeFile(mark, "")
    return true // consume before denying: later greps pass
  } catch {
    return false
  }
}

async function record(sessionID, kind) {
  if (!sessionID || !kind) return
  try {
    const dir = join(cacheDir(), "sessions")
    await mkdir(dir, { recursive: true })
    await appendFile(join(dir, slug(sessionID) + ".jsonl"), JSON.stringify({ kind }) + "\n")
  } catch {}
}

// The shared tokenizer's answer for one shell command, or null. A mention of a
// tool is not a use of it, so this host asks the same code the Python hosts run
// instead of pattern-matching the JSON it was handed.
function commandKind(command) {
  return new Promise((resolve) => {
    let out = ""
    let child
    try {
      child = spawn("python3", [CONTEXT_BIN, "kind", String(command)],
                    { stdio: ["ignore", "pipe", "ignore"] })
    } catch {
      return resolve(null)
    }
    child.stdout.on("data", (d) => (out += d))
    child.on("error", () => resolve(null))
    child.on("close", (code) => resolve(code === 0 && out.trim() ? out.trim() : null))
  })
}

// A read of a tezgah skill file is the one read whose result moves a status
// mark: reading the full text is the only signal that the always-on summary was
// not the whole rule. Matched in-process so ordinary reads stay free. Mirrors
// hooks/tezgah_context.skill_read_kind - the two halves must agree on the path
// shape and on the mark names.
const SKILL_MARKS = { ponytail: "pony", "i-have-adhd": "adhd" }

function skillReadKind(tool, args) {
  // the read names the integrity mirror above already lists: a second list here
  // would be a second definition of "a read", and a skill read by `cat` counts
  if (!READ_TOOLS.has(String(tool || "").toLowerCase())) return null
  const raw = (args && (args.filePath || args.file_path || args.path)) || ""
  const path = String(raw).replace(/\\/g, "/")
  for (const [name, mark] of Object.entries(SKILL_MARKS)) {
    if (path.endsWith("skills/" + name + "/SKILL.md")) return mark
  }
  return null
}

async function classify(tool, args) {
  const blob = tool + " " + JSON.stringify(args || {})
  const read = skillReadKind(tool, args)
  if (read) return read
  if (/search_graph|trace_path|search_code|get_architecture|detect_changes|codebase.memory/.test(blob)) return "cbm"
  if (tool === "task") return "orch"
  if (tool === "bash" || tool === "shell") {
    // the cheap substring only decides whether asking is worth a process; the
    // answer itself comes from the shared tokenizer
    if (/consult|\borx\b/.test(blob)) {
      const command = typeof args === "string" ? args
        : (args && (args.command || args.cmd)) || ""
      return command ? await commandKind(command) : null
    }
  }
  return null
}

// The repo's generated subagents as opencode config.agent entries, or null.
// Runs the same Python source the other hosts use, so the gating and the bodies
// cannot drift.
function opencodeAgents(directory) {
  return new Promise((resolve) => {
    let out = ""
    let child
    try {
      child = spawn("python3", [AGENTS_BIN, "--json", directory],
                    { stdio: ["ignore", "pipe", "ignore"] })
    } catch {
      return resolve(null)
    }
    child.stdout.on("data", (d) => (out += d))
    child.on("error", () => resolve(null))
    child.on("close", () => {
      try { resolve(JSON.parse(out)) } catch { resolve(null) }
    })
  })
}

// The shared builder (hooks/tezgah_context.py) through bin/tezgah-context: the
// same text Claude, Codex, Cursor, dsh and omp get, so opencode cannot drift
// into a hand-kept paraphrase of it again. Fails open: a missing CLI, a
// non-zero exit or a broken pipe all yield "", and the caller injects nothing.
function builderText(event, directory, payload) {
  return new Promise((resolve) => {
    let out = ""
    let child
    try {
      child = spawn("python3", [CONTEXT_BIN, event, directory],
                    { stdio: ["pipe", "pipe", "ignore"] })
    } catch {
      return resolve("")
    }
    child.stdout.on("data", (d) => (out += d))
    child.on("error", () => resolve(""))
    child.on("close", (code) => resolve(code === 0 ? out.trim() : ""))
    try { child.stdin.end(JSON.stringify(payload || {})) } catch {}
  })
}

// The core's own decision for one write, through bin/tezgah-gate: the rule
// that reads the active task (its phase and path allowlist,
// hooks/tezgah_gate.task_reason) lives in Python, and the CLI is how a host
// that cannot import it asks for the answer. The payload is the one the CLI's
// usage names, as a single JSON object on stdin, and its stdout is the refusal
// verbatim. Same idiom as builderText above, and the same fail-open rule: a
// missing CLI, a non-zero exit or a broken pipe all yield "", and the caller
// then enforces its own rules unchanged - a binary that is not there must never
// break the tool call it guards.
function gateReason(tool, args, dir, sessionID) {
  return new Promise((resolve) => {
    let out = ""
    let child
    try {
      child = spawn("python3", [GATE_BIN, "check"],
                    { stdio: ["pipe", "pipe", "ignore"] })
    } catch {
      return resolve("")
    }
    child.stdout.on("data", (d) => (out += d))
    child.on("error", () => resolve(""))
    child.on("close", (code) => resolve(code === 0 ? out.trim() : ""))
    try {
      child.stdin.end(JSON.stringify({
        tool, input: args, cwd: dir, session_id: sessionID || null }))
    } catch {}
  })
}

// The pre-write bytes of what a write tool is about to change, taken through
// bin/tezgah-capture: the CLI the snapshot slice added for the one host that
// cannot call tezgah_snapshot.capture in process (every other host calls it
// directly from the Python gate, at this same point). The argument is the
// payload the gate hands capture, as one JSON object and one argv element, as
// the CLI's usage says. Best effort and silent - the capture, a missing CLI, a
// non-zero exit and the id it prints are all ignored: the snapshot is a
// convenience, and it must never block the edit it protects. Awaited, because
// the bytes have to be read before the write lands and not after it. Returns
// nothing either way.
function captureSnapshot(tool, args, dir, sessionID) {
  return new Promise((resolve) => {
    try {
      const child = spawn("python3", [CAPTURE_BIN, JSON.stringify({
        tool, input: args, cwd: dir, session_id: sessionID || null })],
      { stdio: "ignore" })
      child.on("error", () => resolve())
      child.on("close", () => resolve())
    } catch {
      resolve()
    }
  })
}

export const Tezgah = async ({ directory }) => {
  // installed under both plugin/ and plugins/ for opencode version drift; if
  // both are scanned, only the first module instance registers hooks
  if (globalThis.__tezgahPluginLoaded) return {}
  globalThis.__tezgahPluginLoaded = true
  const dir = directory || process.cwd()

  return {
    // Register the repo's generated subagents at config load so opencode sees
    // them in the SAME session (a brand-new .opencode/agents/ dir is otherwise
    // only read at the next launch). A user-defined agent of the same name wins.
    config: async (cfg) => {
      try {
        if (!cfg || typeof cfg !== "object") return
        if (off("agents-off")) return
        if (!(await rootFor(dir))) return
        const extra = await opencodeAgents(dir)
        const agents = (extra && extra.agent) || {}
        if (!Object.keys(agents).length) return
        const target = cfg.agent && typeof cfg.agent === "object"
          ? cfg.agent : (cfg.agent = {})
        for (const [name, spec] of Object.entries(agents)) {
          if (!(name in target)) target[name] = spec
        }
      } catch {}
    },

    // Native allow/deny where the build emits it. Inert (never called) on
    // builds that do not, which is exactly why the before-hook fallback stays.
    "permission.ask": async (input, output) => {
      try {
        if (!output || typeof output !== "object") return
        if (off("pretooluse-off")) return
        if (!(await rootFor(dir))) return
        const { tool, args } = permissionToolArgs(input)
        const sessionID = input?.sessionID || input?.sessionId
        const sub = String(args.subagent_type || args.agent || "")
        if (attribution(tool, args)) {
          output.status = "deny"
          return
        }
        if (/task|agent|subagent/.test(tool) && /explore/i.test(sub)) {
          output.status = "deny"
          return
        }
        if (identifierFrom(tool, args)) {
          const js = indexSlug(dir)
          if (js && (await oncePerSession(sessionID))) output.status = "deny"
        }
      } catch {}
    },

    "tool.execute.before": async (input, output) => {
      let deny = null
      try {
        if (off("pretooluse-off")) return
        const base = await rootFor(dir)
        if (!base) return
        const tool = String(input?.tool || "").toLowerCase()
        const args = output?.args || input?.args || {}
        const sessionID = input?.sessionID || input?.sessionId

        const sub = String(args.subagent_type || args.agent || "")
        // the shortcut denials are the gate half of the integrity rule, which
        // `verify-off` removes; attribution and explore are other rules and stay
        const shortcuts = !off("verify-off")
        if (attribution(tool, args) || shellAttribution(args)) {
          deny = ATTRIB_DENY
        } else if (tool === "task" && /explore/i.test(sub)) {
          deny = EXPLORE_DENY
        } else if (WRITE_TOOLS.has(tool)) {
          // This file's own write rule first, then the core. The Python gate
          // refuses a shortcut edit before it reaches the task rule
          // (hooks/tezgah_gate.decision: shortcut, attribution, race, task), and
          // a host that picked the other order would name a different reason for
          // the same call. The core is asked (bin/tezgah-gate) for the active
          // task's phase and allowlist - a rule this mirror does not carry - and
          // its answer is used verbatim. One spawn per write is the whole bound:
          // writes are rare, and the JS mirror of the gate is documented as
          // incomplete and divergent, so a new rule enters this host by being
          // asked for here rather than by being copied into it.
          deny = shortcuts ? await shortcutEdit(args) : null
          if (!deny) {
            deny = await gateReason(tool, args, dir, sessionID)
          }
        } else if (shortcuts && BASH_TOOLS.has(tool)) {
          deny = shortcutCommand(args.command || args.cmd || "")
          if (!deny) {
            // the shell's own write route, the one E7c measured once the write
            // tools were refused: a test skip inside a heredoc disables a test
            // exactly as one in an edit's content does
            const body = shellWriteBody(args.command || args.cmd || "", dir)
            if (body) deny = await shortcutEdit(body)
          }
        }
        // The record's shell route, asked of the core (TASK_CLI carries why the
        // pre-test is here and why it is the whole bound): a command that names
        // the task CLI may be moving the phase or the allowlist this session is
        // held to, and the refusal is the core's own text - the same one a write
        // to the record gets. The core masks the command, so one that only
        // mentions the CLI comes back empty and falls through to the rules
        // below. Asked ahead of the shell rules for the same reason the Python
        // gate orders it there (hooks/tezgah_gate.decision): a call another rule
        // would refuse is counted as that rule and never as a repeat.
        if (!deny && BASH_TOOLS.has(tool) &&
            TASK_CLI.test(String(args.command || args.cmd || ""))) {
          deny = await gateReason(tool, args, dir, sessionID)
        }
        // Consent and the credential sink, then the two repeat ceilings, then
        // the nudge: the Python gate's own order (hooks/tezgah_gate.decision),
        // so a call another rule would refuse is counted as that rule and never
        // as a repeat.
        if (!deny && BASH_TOOLS.has(tool)) {
          deny = await shellRules(tool, args, sessionID, base, dir)
        }
        // The ordering rule: a commit over a check that just failed. An
        // argument-shaped rule, so it sits with them and above the repeat guards
        // (hooks/tezgah_gate.decision), and it rides `verify-off` like the rest
        // of the integrity rule.
        if (!deny && shortcuts && BASH_TOOLS.has(tool)) {
          deny = orderReason(args, await ledgerTail(sessionID, LEDGER_TAIL))
          if (deny) await noteDeny(sessionID, "order", deny, tool, args, base)
        }
        if (!deny && shortcuts &&
            (BASH_TOOLS.has(tool) || WRITE_TOOLS.has(tool))) {
          deny = await repeatRules(tool, args, sessionID, base)
        }
        if (!deny && identifierFrom(tool, args)) {
          const js = indexSlug(dir)
          // oncePerSession is shared with permission.ask so exactly one of the
          // two hooks consumes the nudge, whichever the build runs first.
          if (js && (await oncePerSession(sessionID))) {
            deny =
              `Code graph index is ready for this repo (${js}). For a definition, ` +
              "its callers or blast radius use the codebase-memory-mcp search_graph / " +
              "trace_path tools. If you need literal text, re-run this search unchanged; " +
              "it will pass - this nudge fires once per session."
          }
        }
        // Nothing refused this call, so a write is about to land: keep the bytes
        // it is about to change, which is what bin/tezgah-rollback restores by
        // hand. A refused write changes no file, so it is captured nowhere. The
        // Python gate keeps its snapshot at this same point, after every deny
        // check and before the call proceeds.
        if (!deny && WRITE_TOOLS.has(tool)) {
          await captureSnapshot(tool, args, dir, sessionID)
        } else if (!deny && BASH_TOOLS.has(tool)) {
          // A shell call that writes a file (a redirect or `tee`; writtenPath)
          // takes the same pre-state a write tool's target takes: without it the
          // after-state alone cannot tell a write that landed from a no-op, and
          // the freshness rule would count every redirect as a change. `capture`
          // reads a write tool's own path field and takes no shell tool name, so
          // the target goes in the shape it reads
          // (hooks/tezgah_gate.SHELL_AS_WRITE) and the row it writes names no
          // tool.
          const target = writtenPath(args)
          if (target) {
            await captureSnapshot("write", { file_path: target }, dir, sessionID)
          }
        }
      } catch {}
      if (deny) throw new Error(deny)
    },

    // Every shell call (tool or user terminal) sees the same tezgah roots, and
    // the session id so a shell-run `tezgah-status` can light up the used marks.
    "shell.env": async (input, output) => {
      try {
        if (!output || typeof output !== "object") return
        const env = output.env && typeof output.env === "object" ? output.env : (output.env = {})
        const rs = await roots()
        if (rs.length) env.TEZGAH_ROOTS = rs.join(":")
        env.TEZGAH_HOME = CONFIG
        env.TEZGAH_STATUS_BIN = STATUS_BIN
        if (input && input.sessionID) env.TEZGAH_SESSION = String(input.sessionID)
      } catch {}
    },

    // Keep the contract alive when a long session is compacted: the shared
    // builder's post-compact block, the same text Claude and Codex re-inject
    // there, so the summarizer is steered by the live rules rather than by a
    // copy kept in this file.
    "experimental.session.compacting": async (input, output) => {
      try {
        if (!output || typeof output !== "object") return
        const context = Array.isArray(output.context) ? output.context : (output.context = [])
        const text = await builderText("post_compact", dir, {})
        if (text) context.push(text)
      } catch {}
    },

    // Every other host runs the graph auto-index from its SessionStart hook.
    // opencode has no session-lifecycle hook that can run the Python contract,
    // so the first user message of a session triggers it once, detached: the
    // index runs in the background and never blocks the turn. The per-turn text
    // IS awaited - it has to be in the message it applies to.
    "chat.message": async (input, output) => {
      try {
        if (!(await rootFor(dir))) return
        const sessionID = String(input?.sessionID || "")
        // The builder classifies the submitted prompt and returns the per-turn
        // reminder plus whichever conditional rule it arms (spec/consult/
        // research/cbm). Pushed as a synthetic part - the shape opencode's own
        // plan-mode injection uses - so the model reads it in this message. The
        // session id rides along: the builder keys the user-turn marker (the row
        // the loop guard resets on) and its per-turn state delta on it, so
        // without it opencode paid the reminder and nothing that reads the turn.
        const parts = output && Array.isArray(output.parts) ? output.parts : null
        if (parts) {
          const prompt = parts
            .filter((p) => p && p.type === "text" && typeof p.text === "string")
            .map((p) => p.text).join("\n")
          const text = await builderText("user_prompt", dir,
                                         { prompt, session_id: sessionID })
          if (text) {
            const anchor = output.message && typeof output.message === "object"
              ? output.message : {}
            parts.push({
              id: "prt_" + Date.now().toString(36)
                + Math.random().toString(36).slice(2, 10),
              messageID: anchor.id || input?.messageID || "",
              sessionID: input?.sessionID || anchor.sessionID || "",
              type: "text",
              text,
              synthetic: true,
            })
          }
        }
        // per-repo agent file fallback: same one-shot entry as the index, so a
        // changed manifest or repo stack is rewritten once per session
        if (await oncePerSession(sessionID + "|agents")) {
          spawn("python3", [AGENTS_BIN, dir], { detached: true, stdio: "ignore" }).unref()
        }
        // re-render the contract if the policy or the full-contract skill changed
        // since the last --install; opencode has no session-start hook to do it
        if (await oncePerSession(sessionID + "|contract")) {
          spawn("python3", [SETUP_BIN, "--refresh"], { detached: true, stdio: "ignore" }).unref()
        }
        if (!(await oncePerSession(sessionID + "|index"))) return
        spawn("python3", [INDEX_BIN, dir], { detached: true, stdio: "ignore" }).unref()
      } catch {}
    },

    "tool.execute.after": async (input, output) => {
      try {
        const workspace = await rootFor(dir)
        if (!workspace) return
        const tool = String(input?.tool || "").toLowerCase()
        const args = input?.args || output?.args || {}
        const kind = await classify(tool, args)
        if (kind) await record(input?.sessionID || input?.sessionId, kind)
        await recordEvidence(input?.sessionID || input?.sessionId, tool, args,
                             output, workspace, dir)
      } catch {}
    },

    // TODO(custom tool): a `tool()` export (e.g. a direct tezgah-status call)
    // would need `import { tool } from "@opencode-ai/plugin"`. That package
    // resolves from a config-local node_modules that may not exist at runtime,
    // and a failed static import would break the whole plugin at load. Not
    // shipped until that resolution is confirmed on each host; the CLI
    // (TEZGAH_STATUS_BIN) is the safe path today.
  }
}
