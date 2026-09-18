"""The route half of the ask: did the open dimension reach the user?

The reply passes when it asks a question AND names the dimension the prompt left
open - which records belong in the list (a state: removed, failed) or what
happens to a record whose bytes are gone (a blob that is not in storage). It does
not grade which answer the run gave, or whether it also implemented one: that is
the literal check's business, and the two together are the endpoint.

WHAT IT READS, and why that is the whole design. The captured stream is the
host's json mode: thinking deltas, tool calls, tool results and the file contents
the run read, then the assistant's own messages. Only the last of those is the
reply. A check that searched the whole stream would pass for an arm that never
asked the user anything - the model's *thinking* routinely contains "should I
filter to only active ones?" and the fixture's own source contains `state`,
`removed` and `blob` - which is a false positive that would make the endpoint
vacuous. Measured, not assumed: the first version of this file did exactly that
and passed an armed run whose reply was a plain "done" report.

Every assistant text part is read, not just the last message, so an arm that
asked in one message and implemented in the next still counts as asking. The
order of ask against write is not recoverable from the stream, and is not
claimed.

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

# A question, in the two languages this corpus's arms answer in.
ASKS = re.compile(r"\?|should i|do you want|would you like|which one|"
                  r"ister misin|hangisini|mi\b|mı\b", re.I)
# The open dimension: the record's state, or a record whose bytes are gone.
STATE = re.compile(r"removed|deleted|failed|soft[- ]?delet|state\b|status\b|"
                   r"silinmi[sş]|durum", re.I)
BLOB = re.compile(r"blob|missing|absent|no longer (in|available)|storage|"
                  r"eksik|depoda", re.I)


def assistant_text(stream):
    """Every assistant text part in the captured stream, joined. None when the
    stream carries no message list at all - "unreadable" and "said nothing" are
    different answers, and only the second is a not-asking reply."""
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
    parts = []
    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        content = message.get("content")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            parts.extend(part.get("text", "") for part in content
                         if isinstance(part, dict) and part.get("type") == "text")
    return "\n".join(parts)


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

    said = assistant_text(stream)
    if said is None:
        print("the captured stream carries no agent_end message list: the reply "
              "cannot be classified, and an unreadable reply is not an asking one")
        return 1

    asks, state, blob = ASKS.search(said), STATE.search(said), BLOB.search(said)
    if asks and (state or blob):
        print("the reply asks about the open dimension")
        return 0
    print("the reply does not ask about the open dimension: asks=%s state=%s "
          "blob=%s" % (bool(asks), bool(state), bool(blob)))
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
