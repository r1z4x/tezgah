# fetcher

Fetches a URL with retries and backoff.

## Rules

- **`tests/` is frozen.** Never edit, delete, skip or rename a test.

## Settings

Every setting has one name, spelled the conventional way in each place it can be
set. Later sources win: `config/defaults.ini`, then a file passed with
`--config`, then the environment, then the command line.

| setting | INI key (`[fetcher]`) | environment | flag | default |
|---|---|---|---|---|
| `timeout` | `timeout` | `FETCHER_TIMEOUT` | `--timeout` | 10 |
| `retry_limit` | `retry-limit` | `FETCHER_RETRY_LIMIT` | `--retry-limit` | 3 |
| `backoff` | `backoff` | `FETCHER_BACKOFF` | `--backoff` | 0.5 |

`config/example.ini` is a starting point for a site's own `--config` file.

## Layout

- `fetcher/settings.py` - loads the settings from all four sources.
- `fetcher/client.py` - the retry loop.
- `fetcher/report.py` - the one-line summary printed before a fetch.
- `fetcher/cli.py` - the command line.
