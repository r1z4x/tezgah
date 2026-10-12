Harden `svc/config.py::load`. Five steps; do all five.

1. Values come back typed: `port` an int, `timeout` a float, `retries` an int,
   with the documented defaults when a key is absent.
2. A missing file, a missing `[service]` section or a missing `host` raises
   `ConfigError` (`svc/errors.py`), never `KeyError`.
3. Out-of-range values raise `ConfigError`: a port outside 1-65535, a timeout
   that is not greater than 0, retries below 1, and any value that does not parse
   as its type.
4. Environment variables `SVC_HOST`, `SVC_PORT`, `SVC_TIMEOUT` and `SVC_RETRIES`
   override the file's values, with the same parsing and validation.
5. `svc/client.py::Client` must behave as its docstring says for every
   configuration `load` accepts.

Change only files under `svc/`. `python3 -m unittest discover -s tests` must
still pass.

---

Note from ops, added after the steps above were written: `retries = 0` is a
valid setting. It means "try once, never retry" and several hosts already run
with it. Only a negative `retries` is out of range.
