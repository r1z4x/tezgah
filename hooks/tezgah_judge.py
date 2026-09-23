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
no session id, no workspace path, no environment - and the state is not
redacted: sending it is the point, so scrubbing it would hide the risk instead
of stating it - and that is why the callers are explicit or opt-in, and the
`judge-off` switch is the off button for the whole path.

The credential has two channels on purpose. `~/.zshenv` exports the env var for
an interactive shell, but a hook or a bin tool started by a host runs in a
non-interactive shell where `.zshenv` never runs - the export is absent there,
and the key file is the channel that survives. That is why the file is read
rather than the environment trusted.

Behind the credential there are two providers. TypeSafe answers in its own
schema; when no TypeSafe key resolves, the same questions go to an
OpenAI-compatible chat endpoint - OpenRouter, whose key rides the same two
channels (`OPENROUTER_API_KEY`, then `~/.config/openrouter/key`) - and its JSON
reply is mapped back into the shapes the callers already read. That path is a
fallback, never a peer: it is chosen only when `key()` is empty, it sends the
same state to a different host, and a reply that does not carry a question's
answer leaves that question absent, which every caller already reads as no
judgement.

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

URL = "https://api.typesafe.ai/v1/systemone"
KEY_FILE = "~/.config/typesafe/key"
MODEL = "jev-latest"
# The fallback provider: an OpenAI-compatible chat endpoint, its own key
# channels, and the cheap judge model this repository already quotes in its
# measured arm rows (plan 009: `openrouter/deepseek/deepseek-v4-flash`).
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_KEY_FILE = "~/.config/openrouter/key"
FALLBACK_MODEL = "deepseek/deepseek-v4-flash"
# The contract the fallback asks a chat model to answer in, one shape per
# question type this repository's callers send (`bin/tezgah-triage` and
# `hooks/tezgah_skill_pick.py` ask `noul`, `bin/tezgah-docs` and the triage's
# pair rows ask `choice`). It is prose because a chat endpoint has no schema
# field to carry it; every field it names is validated on the way back, and a
# question of any other type reads as unanswered rather than as a guess.
CHAT_SYSTEM = (
    "You answer questions about the state that follows. Reply with one JSON "
    "object and nothing else: {\"answers\": {\"<id>\": {...}}}, one entry per "
    "question id, in the shape that question's type names:\n"
    "noul   -> {\"noul\": <probability 0..1 that the statement is true>}\n"
    "choice -> {\"choice\": \"<the chosen label>\", \"probabilities\": "
    "{\"<label>\": <probability>, ...}, \"confidence\": <0..1>}\n"
    "Every probability is a number in 0..1 and the ones you list for one "
    "question sum to 1. Answer every id you were given.")


class _NoCrossHostRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse a redirect that leaves the endpoint's host.

    urllib carries the Authorization header across a 301/302 hop, so following one
    would hand the credential to whatever host the answer named - and the endpoint
    is repointable by `TEZGAH_TYPESAFE_URL`, so the redirecting host is not
    necessarily TypeSafe's. A same-host redirect is still followed; a refusal
    surfaces as an HTTPError, which `ask()` already turns into a `None`."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).netloc != \
                urllib.parse.urlsplit(req.full_url).netloc:
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


# One opener for the module: its default handlers plus the refusal above, which
# replaces urllib's own redirect handler because it is a subclass of it.
OPENER = urllib.request.build_opener(_NoCrossHostRedirect)


def endpoint():
    """The evaluation endpoint, repointed by TEZGAH_TYPESAFE_URL (tests)."""
    return os.environ.get("TEZGAH_TYPESAFE_URL", "").strip() or URL


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
    return os.environ.get("TEZGAH_OPENROUTER_URL", "").strip() or OPENROUTER_URL


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
    """The chat model the fallback asks: TEZGAH_JUDGE_MODEL, else the default.

    A Jev id is meaningless to a chat endpoint, so the fallback ignores the
    `model` argument rather than forwarding it, and the model a call really used
    comes back on the result."""
    return os.environ.get("TEZGAH_JUDGE_MODEL", "").strip() or FALLBACK_MODEL


def credential():
    """`(provider, secret)` for the first channel that resolves, else `(None, None)`.

    TypeSafe wins whenever it resolves, so adding a fallback cannot move a
    machine that already judges with Jev. The pair is returned rather than the
    secret alone so that `available()` and `ask()` cannot disagree about which
    provider a call will use."""
    secret = key()
    if secret:
        return "typesafe", secret
    secret = openrouter_key()
    return ("openrouter", secret) if secret else (None, None)


def available():
    """True when a judgement can be asked for: a key resolves and no kill switch."""
    return bool(credential()[1]) and not tp.off("judge-off")


def ask(state, questions, *, model=MODEL, timeout=30):
    """One batched call over `questions`; `{"answers", "usage", "latency_ms", "model"}`.

    `questions` is the API's own map - id -> `{type, instructions, criteria}` -
    so a caller that needs a per-line or per-state pass sends every question in
    one request and pays for the state once. The reply's usage is carried back
    because a caller quotes what the judgement cost, and the model beside it
    because the fallback answers with a different one than the caller named.

    One request per call in the normal case, to whichever provider the credential
    resolves - TypeSafe first, the chat fallback only when `key()` is empty. A
    transient failure - a timeout, a connection error, a 5xx - gets one more
    attempt, because a live measurement saw 2 of 50 calls lost that way while the
    same cells answered on retry; a 4xx (a refused credential, a rejected body)
    and a reply that parsed malformed are never retried, since the second request
    would fail identically and only a call that already worked must not be billed
    twice. The ceiling is one, so the worst case is one duplicated request on a
    call that answered nothing anyway.

    Total by design: no key, an unreadable state, a refused request, a timeout,
    a reply that is not the documented shape - all `None`, never an exception."""
    provider, secret = credential()
    if not secret:
        return None
    try:
        if provider == "typesafe":
            used = model
            body = json.dumps({"state": state, "model": used,
                               "questions": questions}).encode()

            def send():
                return _request(secret, body, timeout)
        else:
            used = fallback_model()
            body = json.dumps(_chat_body(state, questions, used)).encode()

            def send():
                return _chat_request(secret, body, timeout, questions)
    except Exception:
        return None
    for attempt in (0, 1):
        try:
            result = send()
        except Exception as exc:
            if attempt or not _transient(exc):
                return None
            continue
        result["model"] = used
        return result
    return None


def _answer(result, id):
    """The raw answer object for one question id, or None.

    One guard for the three callers, because each of them had its own: a missing
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
            "latency_ms": int((time.monotonic() - started) * 1000)}


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


def _chat_request(secret, body, timeout, questions):
    """One POST to the fallback endpoint, mapped into the documented return.

    A reply that carries no message content, or content that is not JSON, raises
    here and `_transient()` refuses to retry it - the same reading as a malformed
    TypeSafe reply. Usage keys come back in the OpenAI spelling and are carried
    in the seam's own (`{"input_tokens", "output_tokens"}`), so a caller's cost
    row does not learn which provider answered."""
    request = urllib.request.Request(openrouter_url(), data=body, headers={
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
            "latency_ms": int((time.monotonic() - started) * 1000)}


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

    The two shapes this repository's callers send - `noul`, the probability a
    statement holds, and `choice`, the label taken - map onto exactly what
    `choice()`/`noul()` already read, so a fallback answer and a TypeSafe answer
    are indistinguishable downstream. Any other type reads as no answer rather
    than as a guess. Probabilities are kept only when they are numbers, because
    `noul()` does the arithmetic on them."""
    if not isinstance(raw, dict):
        return None
    if kind == "noul":
        value = raw.get("noul")
        return {"noul": float(value)} if isinstance(value, (int, float)) else None
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
