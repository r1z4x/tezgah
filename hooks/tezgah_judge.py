#!/usr/bin/env python3
"""One seam for TypeSafe (Jev) judgements: `available()` then one batched `ask()`.

Three callers want the same thing - a structured judgement over a state tezgah
would otherwise pay an agent to read: the analyze-app triage, the docs page
fallback, and the prompt-path skill hint - so the request lives here once,
stdlib only: one endpoint, one request per call normally, no SDK, no async.
A transient failure - a timeout, a connection error, a 5xx - gets one more
attempt and no more; a 4xx and a malformed reply never do (`ask()` below). A hook
may import this module, and a hook that raises takes a session down, so every
failure is a `None` instead.

Privacy, plainly: the state and the questions leave this machine for
`api.typesafe.ai` - for the triage the state IS the screen's own text (an admin
table or a mobile view as captured, plus the `--select` task sentence), so a
screen carrying personal data is read by a third party. Nothing else leaves -
no session id, no workspace path, no environment - and the seam does not
redact the state: sending it is the point, so scrubbing it would hide the risk
instead of stating it - and that is why the callers are explicit or opt-in, and
the `judge-off` switch is the off button for the whole path. Two callers redact
before they call: `bin/tezgah-route` sends its brief through `ti.redact`, and the
prompt-path skill hint sends the user's prompt redacted and cut at 2,000
characters, because a brief or a prompt can quote a token and neither is a
state a person chose to send.

The credential has two channels on purpose. `~/.zshenv` exports the env var for
an interactive shell, but a hook or a bin tool started by a host runs in a
non-interactive shell where `.zshenv` never runs - the export is absent there,
and the key file is the channel that survives. That is why the file is read
rather than the environment trusted.

Behind the credential there are three providers, asked in this order. First the
session's own CLI - `omp` or `claude`, the host this process runs under
(`tp.session_cli()`) - run headless with no tools, so the judgement is paid
with the session's own credential, OAuth subscription included, and answered by
the session's own vendor. TypeSafe and OpenRouter are third parties: they are
asked only as the `fallback` setting allows (`tp.fallback_policy()`): by
default (`vendor`) only when there is no session CLI at all, with `any` also
after the session CLI failed, with `none` never. A third party that answers,
and a fallback that was refused, is never silent: one stderr line, the
`fallback` field on the result, and the last-use record `tezgah-status
--judge` prints (`_record`, `last_use`). A reply that does not carry a
question's answer leaves that question absent, which every caller already reads
as no judgement.

Kill switch: `judge-off`, honoured by `available()`, so a caller can fall back to
its own deterministic path without knowing why the judgement is gone. It is the
master: each caller also names its own - `triage-off`, `docs-judge-off` - and
checks that in front of this one, so one tool's switch never silences another.
"""
import json
import os
import time
import urllib.parse
import urllib.request

import tezgah_paths as tp
import tezgah_store

URL = "https://api.typesafe.ai/v1/systemone"
KEY_FILE = "~/.config/typesafe/key"
MODEL = "jev-latest"
# The fallback provider: an OpenAI-compatible chat endpoint, its own key
# channels, and the cheap judge model this repository already quotes in its
# measured arm rows (`openrouter/deepseek/deepseek-v4-flash`).
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_KEY_FILE = "~/.config/openrouter/key"
FALLBACK_MODEL = "deepseek/deepseek-v4-flash"
# The contract the fallback asks a chat model to answer in, one shape per
# question type this repository's callers send (`bin/tezgah-triage` and
# `hooks/tezgah_skill_pick.py` ask `noul`, `bin/tezgah-docs` and the triage's
# pair rows ask `choice`, `bin/tezgah-taste` asks `text` for a learning's
# readable line). It is prose because a chat endpoint has no schema field to
# carry it; every field it names is validated on the way back, and a question
# of any other type reads as unanswered rather than as a guess.
CHAT_SYSTEM = (
    "You answer questions about the state that follows. Reply with one JSON "
    "object and nothing else: {\"answers\": {\"<id>\": {...}}}, one entry per "
    "question id, in the shape that question's type names:\n"
    "noul   -> {\"noul\": <probability 0..1 that the statement is true>}\n"
    "choice -> {\"choice\": \"<the chosen label>\", \"probabilities\": "
    "{\"<label>\": <probability>, ...}, \"confidence\": <0..1>}\n"
    "text   -> {\"text\": \"<the answer as plain prose>\"}\n"
    "Every probability is a number in 0..1 and the ones you list for one "
    "question sum to 1. Answer every id you were given.")


# One opener for the module: a redirect that leaves the endpoint's host is
# refused, because urllib carries the Authorization header across the hop and
# the endpoint is repointable by `TEZGAH_TYPESAFE_URL`. A refusal surfaces as an
# HTTPError, which `ask()` already turns into a `None`.
OPENER = tp.guarded_opener()


def override(name, default):
    """The URL in env var `name`, else `default` - every endpoint override routes
    through here. An `http://` URL off this machine raises ValueError: the bearer
    key and the state would cross the network in clear (`tp.plain_http`;
    loopback stays allowed for the tests' fakes)."""
    url = os.environ.get(name, "").strip() or default
    if tp.plain_http(url):
        raise ValueError("%s is plain http off this machine: the key and the state "
                         "would cross the network in clear" % name)
    return url


def endpoint():
    """The evaluation endpoint, repointed by TEZGAH_TYPESAFE_URL (tests)."""
    return override("TEZGAH_TYPESAFE_URL", URL)


def key():
    """The credential: TYPESAFE_API_KEY, else the key file, else None.

    The file is stripped: it is written with a trailing newline, and a newline
    inside an Authorization header is a header-injection attempt to the HTTP
    layer, not a typo it will forgive."""
    value = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if value:
        return value
    try:
        with open(os.path.expanduser(KEY_FILE), encoding="utf-8") as fh:
            return fh.read().strip() or None
    except OSError:
        return None


def openrouter_url():
    """The fallback endpoint, repointed by TEZGAH_OPENROUTER_URL (tests)."""
    return override("TEZGAH_OPENROUTER_URL", OPENROUTER_URL)


def openrouter_key():
    """The fallback credential: OPENROUTER_API_KEY, else the key file, else None.

    The same two channels as the TypeSafe key and for the same reason - a hook
    runs where `~/.zshenv` never did - and the same `strip()`, because a newline
    inside an Authorization header is an injection, not a typo."""
    value = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if value:
        return value
    try:
        with open(os.path.expanduser(OPENROUTER_KEY_FILE), encoding="utf-8") as fh:
            return fh.read().strip() or None
    except OSError:
        return None


def fallback_model():
    """The chat model the fallback asks: TEZGAH_JUDGE_MODEL, else the table's.

    A Jev id is meaningless to a chat endpoint, so the fallback ignores the
    `model` argument rather than forwarding it, and the model a call really used
    comes back on the result."""
    return os.environ.get("TEZGAH_JUDGE_MODEL", "").strip() or cheap_default()


# The session CLIs the seam can ask, as the argv between the binary and the
# prompt: no tools, no session file, no project rules, skills, extensions, MCP
# servers or settings, and the chat fallback's own contract as the system
# prompt. Measured 2026-10-07 on a one-word answer: claude went from 37,038
# prompt tokens ($0.30) to 725 ($0.007); omp from 43,735 written to cache
# ($0.35) to about 37,500, 36,700 of them read from cache ($0.015) - omp has
# no flag here that drops the rest.
SESSION_ARGV = {
    "omp": ["-p", "--no-tools", "--no-lsp", "--no-session", "--no-rules",
            "--no-skills", "--no-extensions", "--no-title", "--thinking", "off",
            "--mode", "json", "--system-prompt", CHAT_SYSTEM],
    "claude": ["-p", "--tools", "", "--no-session-persistence",
               "--strict-mcp-config", "--disable-slash-commands",
               "--setting-sources", "", "--output-format", "json",
               "--system-prompt", CHAT_SYSTEM],
    # None of the next three takes a system prompt or drops its tools, so
    # `_session_request` puts the system prompt in front of the prompt text and
    # the empty temp cwd is what keeps tools from reaching a repository. Each
    # set is from the CLI's own `--help` (checked 2026-10-09). opencode 1.18.31
    # `run`: `--pure` "run without external plugins", `--format json` "raw JSON
    # events"; it has no flag that skips the session record.
    "opencode": ["run", "--pure", "--format", "json"],
    # cursor-agent 2026.10.01: `-p` print, `--output-format json` (only with
    # --print), `--mode ask` "Q&A style ... (read-only)", `--trust` "Trust the
    # current workspace without prompting" - the temp cwd is never trusted.
    "cursor": ["-p", "--output-format", "json", "--mode", "ask", "--trust"],
    # codex-cli 0.153.4 `exec`: `--json` "Print events to stdout as JSONL",
    # `--ephemeral` "without persisting session files", `--skip-git-repo-check`
    # (the temp cwd is no repository), `--ignore-rules` (no execpolicy rules),
    # `-s read-only`, `--color never`: consult's argv (`tp.CONSULT_CLIS`) plus
    # `--json` and `--ignore-rules`.
    "codex": ["exec", "--json", "--ephemeral", "--skip-git-repo-check",
              "--ignore-rules", "-s", "read-only", "--color", "never"],
}
NO_SESSION = ("no session CLI to ask (no omp, Claude Code, opencode, Cursor or Codex "
              "session marker or TEZGAH_JUDGE_CLI/judge_cli pick, or that CLI missing)")


def providers():
    """[(provider, secret), ...] in the order `ask()` tries them, or [].

    The session's own CLI first (its `secret` is the binary's path); then the
    third parties - TypeSafe, then OpenRouter - only as `tp.fallback_policy()`
    allows: `vendor` (the default) asks them only when no session CLI exists,
    `any` after the session CLI too, `none` never. TypeSafe still wins over
    OpenRouter whenever both resolve."""
    session = tp.session_cli()
    policy = tp.fallback_policy()
    out = [(session, getattr(tp, session + "_bin")())] if session else []
    if policy == "none" or (session and policy == "vendor"):
        return out
    return out + [(name, secret) for name, secret in
                  (("typesafe", key()), ("openrouter", openrouter_key())) if secret]


def named(only):
    """`providers()` for a caller that requires particular ones: every provider
    in `only` that resolves, in `only`'s order. The `vendor` policy's
    session-first order does not apply - the caller named the provider, so
    nothing is a silent fallback - but `none` still keeps every third party
    out. The name `jev` stands for every Jev carrier that resolves
    (`JEV_CARRIERS`), so a caller that needs a typed answer names the model
    family, not one carrier's address."""
    session = tp.session_cli()
    third = tp.fallback_policy() != "none"
    found = {session: getattr(tp, session + "_bin")()} if session else {}
    if third:
        found.update(typesafe=key(), openrouter=openrouter_key())
    out = []
    for name in only:
        for one in (JEV_CARRIERS if name == "jev" else (name,)):
            if found.get(one) and (one, found[one]) not in out:
                out.append((one, found[one]))
    return out


# Every carrier that answers with the Jev model itself (a typed System One
# reply), as opposed to a chat model asked to imitate its shape. A decision a
# caller requires to be typed checks `is_jev(result["provider"])`.
JEV_CARRIERS = ("typesafe",)


def is_jev(provider):
    """True when `provider` is a Jev carrier (`JEV_CARRIERS`)."""
    return provider in JEV_CARRIERS


def credential():
    """`(provider, secret)` for the first provider `ask()` will try, else
    `(None, None)` - so `available()` and `ask()` cannot disagree."""
    found = providers()
    return found[0] if found else (None, None)


def available():
    """True when a judgement can be asked for: a provider resolves and no kill switch."""
    return bool(credential()[1]) and not tp.off("judge-off")


def ask(state, questions, *, model=MODEL, timeout=30, attempts=2, deadline=None,
        only=None):
    """One batched call over `questions`; `{"answers", "usage", "latency_ms",
    "model", "provider", "fallback"}`.

    `questions` is the API's own map - id -> `{type, instructions, criteria}` -
    so a caller that needs a per-line or per-state pass sends every question in
    one request and pays for the state once. The reply's usage is carried back
    because a caller quotes what the judgement cost, and the model and provider
    beside it because the provider that answers is not the caller's choice. The
    model is the one the reply names, else the one asked for: an alias such as
    `jev-latest` hides a silent upgrade the reply's own field shows. `model` is
    TypeSafe's alone; the session CLI and the chat fallback ignore it.

    The providers are tried in `providers()` order - the session's own CLI
    first - and the next one is asked only when the previous failed. `fallback`
    is None when the session answered, else why someone else did; that answer,
    and a refusal, is recorded (`_record`) and said on stderr. A transient
    failure - a timeout, a connection error, a 5xx - gets one more attempt on
    the same provider, because a live measurement saw 2 of 50 calls lost that
    way while the same cells answered on retry; a 4xx, a CLI that exited
    non-zero and a reply that parsed malformed are never retried, since the
    second request would fail identically and only a call that already worked
    must not be billed twice. A caller on a hook's budget passes `attempts=1`
    and a `deadline` in seconds: urllib's `timeout` bounds one socket operation,
    not the call, so only the deadline bounds its wall time.

    A call that ends on a 401, 402, 5xx or a session CLI's non-zero exit marks
    that provider down for `DOWN_FOR` seconds, and until then it is skipped
    without a request (`_down`), so a dead credential is not re-paid on every
    prompt.

    Total by design: no provider, an unreadable state, a refused request, a
    timeout, a reply that is not the documented shape - all `None`, never an
    exception.

    `only` names the providers the caller requires (`named()`); a caller whose
    decision must come from a typed model passes `only=("typesafe",)` and gets
    None rather than another provider's answer."""
    tried = providers() if only is None else named(only)
    if any(isinstance(q, dict) and q.get("type") == "text" for q in questions.values()):
        # TypeSafe answers no prose: left out up front, not logged as a failure
        tried = [(p, s) for p, s in tried if p != "typesafe"]
    if not tried or not tried[0][1]:
        return None
    stop = None if deadline is None else time.monotonic() + deadline
    failed = []
    for provider, secret in tried:
        result, why = _ask_one(provider, secret, state, questions, model,
                               timeout, attempts, stop)
        if result is None:
            failed.append("%s: %s" % (provider, why))
            continue
        # a provider the caller named is not a stand-in: no note, unless an
        # earlier one it named failed
        note = "; ".join(failed) or (None if only is not None or provider in SESSION_ARGV
                                     else NO_SESSION)
        result["fallback"] = note
        _record(result["provider"], result["model"], fallback=note)
        return result
    refused = None
    session = tp.session_cli()
    if session and (key() or openrouter_key()):
        refused = ("fallback=%s refuses a third-party judge after %s failed"
                   % (tp.fallback_policy(), session))
    _record(None, None, failed="; ".join(failed), refused=refused)
    return None


def _ask_one(provider, secret, state, questions, model, timeout, attempts, stop):
    """One provider's attempts: `(result, None)`, or `(None, why)`."""
    try:
        if provider == "typesafe":
            used, url = model, endpoint()
            body = json.dumps({"state": state, "model": used,
                               "questions": questions}).encode()

            def send():
                return _request(secret, body, timeout)
        elif provider == "openrouter":
            used, url = fallback_model(), openrouter_url()
            body = json.dumps(_chat_body(state, questions, used)).encode()

            def send():
                return _chat_request(secret, body, timeout, questions)
        else:
            used, url = None, secret
            prompt = json.dumps({"state": state, "questions": questions})

            def send():
                left = timeout if stop is None else max(0.1, min(timeout, stop - time.monotonic()))
                return _session_request(provider, secret, prompt, left, questions)
        down = _down_key(provider, url, secret)
        if _down(down):
            return None, "marked down for %ds after a refusal" % DOWN_FOR
    except Exception as exc:
        return None, _why(exc)
    for attempt in range(attempts):
        if stop is not None and time.monotonic() >= stop:
            return None, "deadline passed"
        try:
            result = _bounded(send, stop)
        except Exception as exc:
            late = stop is not None and time.monotonic() >= stop
            if attempt + 1 >= attempts or late or not _transient(exc):
                code = getattr(exc, "code", None)
                if code in (401, 402) or (isinstance(code, int) and code >= 500) \
                        or isinstance(exc, SessionFailed):
                    _mark_down(down)
                return None, _why(exc)
            continue
        named = result.get("model")
        result["model"] = named if isinstance(named, str) and named else used or "-"
        result["provider"] = provider
        return result, None
    return None, "no attempt"


def _answer(result, id):
    """The raw answer object for one question id, or None.

    One guard for every caller, because each of them had its own: a missing
    answer, an answer of the wrong shape and an answer of `null` all have to read
    the same way in every caller, and three copies of that is three places for the
    fourth caller to disagree."""
    answers = result.get("answers") if isinstance(result, dict) else None
    answer = answers.get(id) if isinstance(answers, dict) else None
    return answer if isinstance(answer, dict) else None


def choice(result, id):
    """The option a Choice question took, or None.

    A `null`, an answer of another type and an option that is not a string all read
    as no option taken, rather than as an option a caller then compares with `==`."""
    answer = _answer(result, id)
    value = answer.get("choice") if answer else None
    return value if isinstance(value, str) else None


def text(result, id):
    """The prose a `text` question came back with, stripped, or None. Only a
    generative provider answers one; TypeSafe is never sent one."""
    answer = _answer(result, id)
    value = answer.get("text") if answer else None
    return (value.strip() or None) if isinstance(value, str) else None


def noul(result, id, option=None):
    """The probability a Noul question came back with, or None.

    Returned as a `float`, so a caller's arithmetic and its threshold do not have
    to re-check the type the module already checked. With `option`, the
    probability the reply put on that option of a Choice answer instead: a Choice
    prints a distribution rather than one number, and the triage's row for each of
    its focus/active pair is that option's share of it."""
    answer = _answer(result, id)
    if not answer:
        return None
    if option is None:
        value = answer.get("noul")
    else:
        chances = answer.get("probabilities")
        value = chances.get(option) if isinstance(chances, dict) else None
    return float(value) if isinstance(value, (int, float)) else None


def _transient(exc):
    """True for a failure a second identical request may not hit again.

    A 5xx is upstream having a moment; a `URLError`, a timeout or any other
    `OSError` is the link rather than the request. Everything else is
    deterministic and must not be retried - a 4xx, above all a refused
    credential, and a reply that parsed but is malformed."""
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        return code >= 500
    return isinstance(exc, OSError)


def _request(secret, body, timeout):
    """One POST: the documented return, or the exception `ask()` decides on.

    Split from `ask()` so the retry re-sends the body already serialized rather
    than rebuilding it, and so the URL parse stays inside `ask()`'s try: a
    scheme-less override raises ValueError there and becomes a None like any
    other failure rather than escaping."""
    request = urllib.request.Request(endpoint(), data=body, headers={
        "Authorization": "Bearer " + secret,
        "Content-Type": "application/json"})
    started = time.monotonic()
    with OPENER.open(request, timeout=timeout) as response:
        data = json.load(response)
    usage = data["usage"]
    return {"answers": data["answers"],
            "usage": {"input_tokens": int(usage["input_tokens"]),
                      "output_tokens": int(usage["output_tokens"])},
            "latency_ms": int((time.monotonic() - started) * 1000),
            "model": data.get("model")}


def _chat_body(state, questions, model):
    """The chat-completions body for one batched fallback call.

    `temperature: 0` because a judgement that moves between two identical calls
    is not a measurement, and the JSON-object response format because prose
    around the object is the one failure mode a chat endpoint adds to the
    TypeSafe shape."""
    return {"model": model, "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": CHAT_SYSTEM},
                {"role": "user",
                 "content": json.dumps({"state": state,
                                        "questions": questions})}]}


def _chat_request(secret, body, timeout, questions, url=None):
    """One POST to an OpenAI-compatible chat endpoint - the fallback's unless
    `url` names another - mapped into the documented return.

    A reply that carries no message content, or content that is not JSON, raises
    here and `_transient()` refuses to retry it - the same reading as a malformed
    TypeSafe reply. Usage keys come back in the OpenAI spelling and are carried
    in the seam's own (`{"input_tokens", "output_tokens"}`), so a caller's cost
    row reads one usage shape whichever provider answered."""
    request = urllib.request.Request(url or openrouter_url(), data=body, headers={
        "Authorization": "Bearer " + secret,
        "Content-Type": "application/json"})
    started = time.monotonic()
    with OPENER.open(request, timeout=timeout) as response:
        data = json.load(response)
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("the reply carried no message content") from exc
    answers = _chat_answers(json.loads(content), questions)
    usage = data.get("usage") or {}
    return {"answers": answers,
            "usage": {"input_tokens": int(usage.get("prompt_tokens") or 0),
                      "output_tokens": int(usage.get("completion_tokens") or 0)},
            "latency_ms": int((time.monotonic() - started) * 1000),
            "model": data.get("model")}


def _chat_answers(parsed, questions):
    """The answers a chat reply carried, filtered to the ids that were asked for.

    A reply that is not an object, or that carries no answers map, is the same
    failure as a malformed TypeSafe reply, and it raises so `ask()` reads it as
    one. An id whose answer does not match its question's type is dropped rather
    than coerced: a `bool` question answered in prose reads as unanswered, not
    as a zero the triage would then score against."""
    got = parsed.get("answers") if isinstance(parsed, dict) else None
    if not isinstance(got, dict):
        raise ValueError("the reply carried no answers object")
    out = {}
    for qid, question in questions.items():
        kind = question.get("type") if isinstance(question, dict) else None
        clean = _clean_answer(got.get(qid), kind)
        if clean:
            out[qid] = clean
    return out


def _clean_answer(raw, kind):
    """One answer in the shape its question type names, or None.

    The shapes this repository's callers send - `noul`, the probability a
    statement holds, `choice`, the label taken, and `text`, prose - map onto
    exactly what `choice()`/`noul()`/`text()` already read, so a fallback answer
    and a TypeSafe answer are indistinguishable downstream. Any other type reads
    as no answer rather than as a guess. Probabilities are kept only when they
    are numbers, because `noul()` does the arithmetic on them."""
    if not isinstance(raw, dict):
        return None
    if kind == "noul":
        value = raw.get("noul")
        return {"noul": float(value)} if isinstance(value, (int, float)) else None
    if kind == "text":
        value = raw.get("text")
        return {"text": value} if isinstance(value, str) and value.strip() else None
    if kind != "choice":
        return None
    if not isinstance(raw.get("choice"), str):
        return None
    answer = {"choice": raw["choice"]}
    chances = raw.get("probabilities")
    if isinstance(chances, dict):
        kept = {str(k): float(v) for k, v in chances.items()
                if isinstance(v, (int, float))}
        if kept:
            answer["probabilities"] = kept
    confidence = raw.get("confidence")
    if isinstance(confidence, (int, float)):
        answer["confidence"] = float(confidence)
    return answer


def cheap_default():
    """The cheap row the models table names on `any`, else `FALLBACK_MODEL`.

    Defined last on purpose: `docs/judge.md` cites this file by line number, so
    new code goes below the last cited line instead of shifting every citation
    after it. The import is lazy and inside this function because
    `tezgah_models` imports this module - a module-level import back would be
    the cycle - and it is guarded because a seam a hook cannot import is worse
    than a stale id."""
    try:
        import tezgah_models
        row = tezgah_models.cheap_model("any")
    except Exception:
        row = None
    return row[0] if row else FALLBACK_MODEL


# How long a provider stays marked down after a 401, 402 or 5xx: five minutes,
# so a dead key or an empty account costs one refusal per five minutes rather
# than one per prompt, and a provider that comes back is asked again within the
# same working session. The mark is keyed on the provider, the endpoint and a
# digest of the credential, so a rotated key is asked at once; the store keeps
# the time it expires.
DOWN_FOR = 300


def _down_key(provider, url, secret):
    import hashlib
    return hashlib.sha256("\0".join((provider, url, secret)).encode()).hexdigest()[:16]


def _down(key):
    """True while the mark of `key` has not expired; one expiring more than
    `DOWN_FOR` from now (a clock step back, a copied cache) and any read error
    are up."""
    until = tezgah_store.down_until(key)
    return until is not None and 0 < until - time.time() <= DOWN_FOR


def _mark_down(key):
    """Best effort, like every other write a hook makes: a store that cannot be
    written costs the next call a request, never an exception."""
    tezgah_store.set_down(key, time.time() + DOWN_FOR)


def _bounded(send, stop):
    """`send()`, or TimeoutError once the monotonic `stop` passes.

    The request runs on a daemon thread joined for the time that is left,
    because no urllib timeout bounds a whole call. ponytail: a thread that
    outlives its deadline is abandoned, not cancelled; it ends with its socket
    timeout or with the process, which for a hook is moments later."""
    if stop is None:
        return send()
    import threading
    box = {}

    def run():
        try:
            box["ok"] = send()
        except Exception as exc:
            box["err"] = exc

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(max(0.0, stop - time.monotonic()))
    if worker.is_alive():
        raise TimeoutError("the call outlived its deadline")
    if "err" in box:
        raise box["err"]
    return box["ok"]


class SessionFailed(RuntimeError):
    """The session CLI exited non-zero or printed no answer: a logged-out CLI or
    an exhausted plan fails the same way on the next call, so it is never
    retried and it marks the provider down like a 401."""


def _session_request(name, exe, prompt, timeout, questions):
    """One headless run of the session's own CLI, mapped into the documented
    return. It starts in an empty temp dir with stdin closed - the answer rests
    on the prompt alone, and a CLI that wants a login exits instead of waiting -
    with TEZGAH_NESTED set so tezgah's own hooks stand down in the child. The
    answer is read from the CLI's JSON output: the model and the usage it names
    are what the call really used. A CLI with no system-prompt flag gets the
    system prompt in front of the prompt text instead."""
    import shutil
    import subprocess
    import tempfile
    if CHAT_SYSTEM not in SESSION_ARGV[name]:
        prompt = CHAT_SYSTEM + "\n\n" + prompt
    cwd = tempfile.mkdtemp(prefix="tezgah-judge-")
    started = time.monotonic()
    try:
        proc = subprocess.run([exe] + SESSION_ARGV[name] + [prompt], cwd=cwd,
                              stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, timeout=timeout,
                              env=dict(os.environ, TEZGAH_NESTED="1"))
    finally:
        shutil.rmtree(cwd, ignore_errors=True)
    if proc.returncode:
        # stdout last: codex prints a stdin banner on stderr and its reason as
        # the last JSON event on stdout
        raise SessionFailed("%s exit %d: %s" % (name, proc.returncode, (
            (proc.stderr or "") + (proc.stdout or "")).strip()[-200:]))
    if name == "claude":
        data = json.loads(proc.stdout)
        if data.get("is_error"):
            raise SessionFailed("claude: %s" % str(data.get("result"))[:200])
        text = data.get("result") or ""
        model = next(iter(data.get("modelUsage") or {}), None)
        usage = data.get("usage") or {}
        tokens_in = sum(int(usage.get(k) or 0) for k in (
            "input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
        tokens_out = int(usage.get("output_tokens") or 0)
    elif name == "omp":
        message = None
        for line in proc.stdout.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict) and event.get("type") == "message_end" \
                    and (event.get("message") or {}).get("role") == "assistant":
                message = event["message"]
        if message is None:
            raise SessionFailed("omp printed no answer")
        text = "".join(part.get("text") or "" for part in message.get("content") or []
                       if isinstance(part, dict) and part.get("type") == "text")
        model = "/".join(str(message[k]) for k in ("provider", "model") if message.get(k))
        usage = message.get("usage") or {}
        tokens_in = sum(int(usage.get(k) or 0) for k in ("input", "cacheRead", "cacheWrite"))
        tokens_out = int(usage.get("output") or 0)
    else:
        model = None  # none of the three names the model it ran
        text, tokens_in, tokens_out = _cli_answer(name, proc.stdout)
        if not text.strip():
            raise SessionFailed("%s printed no answer" % name)
    # A chat model may fence its object; the outermost braces are the object.
    answers = _chat_answers(json.loads(text[text.find("{"):text.rfind("}") + 1]), questions)
    return {"answers": answers,
            "usage": {"input_tokens": tokens_in, "output_tokens": tokens_out},
            "latency_ms": int((time.monotonic() - started) * 1000),
            "model": model}


def _cli_answer(name, out):
    """(text, input tokens, output tokens) from opencode's, cursor-agent's
    or codex's JSON output, the shapes each printed on 2026-10-09; text is ""
    when no answer came. None of the three names the model it ran. Input counts
    the cache reads and writes, as the claude and omp branches do: opencode and
    cursor-agent report them beside the input (opencode's `total` is the sum of
    all its fields), codex inside `input_tokens` (`cached_input_tokens` is a
    share of it, as `reasoning_output_tokens` is of `output_tokens`)."""
    text, tokens_in, tokens_out = "", 0, 0
    for line in out.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        kind = event.get("type")
        part, item = event.get("part") or {}, event.get("item") or {}
        usage = event.get("usage") or {}
        if name == "cursor" and kind == "result":
            if event.get("is_error"):
                raise SessionFailed("cursor: %s" % str(event.get("result"))[:200])
            text = event.get("result") or ""
            tokens_in = sum(int(usage.get(k) or 0) for k in (
                "inputTokens", "cacheReadTokens", "cacheWriteTokens"))
            tokens_out = int(usage.get("outputTokens") or 0)
        elif name == "opencode" and kind == "text":
            text = part.get("text") or text
        elif name == "opencode" and kind == "step_finish":
            tokens = part.get("tokens") or {}
            cache = tokens.get("cache") or {}
            tokens_in += sum(int(v or 0) for v in (tokens.get("input"), cache.get("read"),
                                                   cache.get("write")))
            tokens_out += int(tokens.get("output") or 0) + int(tokens.get("reasoning") or 0)
        elif name == "codex" and kind == "item.completed" \
                and item.get("type") == "agent_message":
            text = item.get("text") or text
        elif name == "codex" and kind == "turn.completed":
            tokens_in += int(usage.get("input_tokens") or 0)
            tokens_out += int(usage.get("output_tokens") or 0)
    return text, tokens_in, tokens_out


def _why(exc):
    """A failure as one short reason: the HTTP code, else the exception's text."""
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        return "http %d" % code
    return ("%s: %s" % (type(exc).__name__, exc))[:200]


def _say(line):
    try:
        import sys
        sys.stderr.write("tezgah-judge: %s\n" % line)
    except Exception:
        pass


def _record(provider, model, fallback=None, failed=None, refused=None):
    """Write the last-use record (the `judge_last` store's one document: what
    answered, and why it was not the session's own CLI when it was not;
    `tezgah-status --judge` prints it) and say any fallback or refusal on
    stderr. Best effort like every hook write: a store that cannot be written
    loses the record, never the answer."""
    if fallback and provider:
        _say("answered by %s/%s - %s" % (provider, model, fallback))
    elif refused:
        _say("no judgement: %s (%s)" % (refused, failed))
    row = {"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "provider": provider,
           "model": model, "fallback": fallback, "failed": failed or None,
           "refused": refused, "policy": tp.fallback_policy()}
    tezgah_store.put_doc("judge_last", "", row)


def last_use():
    """The last judgement's record (see `_record`), or None when none was kept."""
    row = tezgah_store.doc("judge_last", "")
    return row if isinstance(row, dict) else None
