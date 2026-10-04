#!/usr/bin/env python3
"""Test probe: run one hook with a core function poisoned to raise.

Usage: python3 _probe_poisoned.py <hook path> <module> <function>

The function is replaced on the real module *before* the hook is loaded, so the
hook's own `from <module> import <function>` binds the raiser. What is therefore
measured is the hook's guard and not the core's behaviour: an unguarded hook lets
the traceback out and exits non-zero, a guarded one answers with the empty
envelope it uses for every other failure and exits 0.

The payload arrives on stdin, the way a host hands it over. It is not passed as
an argument: a probe that left stdin empty would exercise the hook's own decode
guard and never reach the call under test.
"""
import os
import runpy
import sys

hook = os.path.abspath(sys.argv[1])
module, function = sys.argv[2], sys.argv[3]

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))


def boom(*_args, **_kwargs):
    raise RuntimeError("poisoned core: %s" % function)


setattr(__import__(module), function, boom)
runpy.run_path(hook, run_name="__main__")
