import argparse
import urllib.request

from . import report, settings
from .client import Client


def build_parser():
    parser = argparse.ArgumentParser(prog="fetcher")
    parser.add_argument("url")
    parser.add_argument("--config")
    parser.add_argument("--timeout", type=int)
    parser.add_argument("--max-retries", type=int)
    parser.add_argument("--backoff", type=float)
    return parser


def _open(url, timeout):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read()


def main(argv=None, opener=_open, env=None, out=print):
    args = build_parser().parse_args(argv)
    loaded = settings.load(args.config, env, {
        "timeout": args.timeout,
        "max_retries": args.max_retries,
        "backoff": args.backoff,
    })
    client = Client(loaded, opener)
    out(report.summary(client))
    return client.fetch(args.url)
