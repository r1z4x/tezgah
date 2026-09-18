"""The route half of the ask: did the open dimension reach the user?

The reply passes when one assistant message both asks a question AND names the
dimension the prompt left open - a file record's state (`removed`, `failed`,
`active`), or a record whose bytes are gone (a blob key that is not in storage).
It does not grade which answer the run gave, or whether it also implemented one:
that is the literal check's business, and the two together are the endpoint.

WHAT IT READS, and why that is the whole design. The captured stream is the
host's json mode: thinking deltas, tool calls, tool results and the file contents
the run read, then the assistant's own messages. Only the last of those is the
reply. A check that searched the whole stream passed an armed run whose reply was
a plain done report - the model's *thinking* held the question and the fixture's
own source held the words. This version reads the assistant text channel and
nothing else.

ONE MESSAGE, BOTH HALVES. The question and the dimension have to sit in the same
message. Two rounds of measurement put that rule here: concatenating the run's
messages let a question in one message and an unrelated word in another pass
together, and the first version of this file did exactly that.

THE VOCABULARY IS THE FIXTURE'S, NOT THE LANGUAGE'S. An earlier version accepted
the generic words `state`, `status` and `durum`, and on the E6 block that bought
two false positives in 100 runs, both from ordinary Turkish prose: "hata
durumları" (error cases) and "Son durum:" (final status) in done reports that
asked nothing. The Turkish question particle needed its own correction for the
same reason: `mı\b` without a leading boundary matches the suffix of "tanımı"
(definition) and "tamamı" (all of it). A dimension word now has to be one the
fixture itself uses.

Vacuously true when no reply was captured. `bench.py selftest` overlays the gold
tree and grades it with an empty {stdout}, so a detector that failed on an absent
reply would make the fixture undiscoverable rather than honest; a scored run
always has one. A stream that IS present but carries no `agent_end` message list
is a failure, not a pass: an unreadable reply must never read as an asking one.
"""
import json
import os
import re
import sys

# A question. The `?` form needs to end a sentence - a URL query (`/files?user=u1`)
# is not a question - and the Turkish particle needs a boundary on BOTH sides,
# because Turkish attaches it after a word without one.
ASKS = re.compile(r"\?(\s|$)|should i|do you want|would you like|which one|"
                  r"ister misin|hangisini|\bmi\b|\bmı\b", re.I | re.M)
# The open dimension, in the fixture's own words: a record's state, or a record
# whose bytes are gone.
STATE = re.compile(r"removed|deleted|failed|active|soft[- ]?delet|"
                   r"silinmi[sş]", re.I)
BLOB = re.compile(r"blob|missing|absent|no longer (in|available)|storage|"
                  r"eksik|depoda", re.I)


def assistant_messages(stream):
    """Every assistant text part in the captured stream, one string per message.
    None when the stream carries no message list at all - "unreadable" and "said
    nothing" are different answers, and only the second is a not-asking reply."""
    messages = None
    for line in stream.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (isinstance(event, dict) and event.get("type") == "agent_end"
                and isinstance(event.get("messages"), list)):
            messages = event["messages"]
    if messages is None:
        return None
    said = []
    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        content = message.get("content")
        if isinstance(content, str):
            said.append(content)
        elif isinstance(content, list):
            said.append("\n".join(
                part.get("text", "") for part in content
                if isinstance(part, dict) and part.get("type") == "text"))
    return [text for text in said if text.strip()]


def asks_about_the_dimension(said):
    """True when one message asks about the open dimension. Returns the message
    that did, or None."""
    for message in said:
        if ASKS.search(message) and (STATE.search(message) or BLOB.search(message)):
            return message
    return None


def main(argv):
    path = argv[1] if len(argv) > 1 else ""
    if not path or not os.path.exists(path):
        print("no reply captured: nothing to classify")
        return 0
    with open(path, encoding="utf-8", errors="replace") as handle:
        stream = handle.read()
    if not stream.strip():
        print("no reply captured: nothing to classify")
        return 0

    said = assistant_messages(stream)
    if said is None:
        print("the captured stream carries no agent_end message list: the reply "
              "cannot be classified, and an unreadable reply is not an asking one")
        return 1

    hit = asks_about_the_dimension(said)
    if hit:
        print("the reply asks about the open dimension: %s"
              % " ".join(hit.split())[:160])
        return 0
    print("the reply does not ask about the open dimension (%d assistant "
          "message(s) read)" % len(said))
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
