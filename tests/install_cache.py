"""One install per argv per test process, laid back down for every later test.

No import-time side effects (unlike tests/support.py), so a module that passes
its own environment to every child can use it as it is.
"""
import os
import shutil
import tempfile


class InstallCache:
    """A HOME at one path for the whole process, emptied for each test, so the
    tree an install leaves - which names that path - is laid back down instead
    of re-run.

    `fresh(dirs)` empties the HOME's parent and makes `dirs` in the HOME;
    `run(key, fn)` returns `fn()`, and while the HOME is still exactly as
    `fresh` left it, the first call per `key` keeps a copy of the HOME and the
    result and every later one restores that copy and returns the same result.
    A key of None never caches; a HOME the test already wrote to is never
    served from the cache."""

    def __init__(self):
        self._tmp = None
        self._done = {}

    def fresh(self, dirs):
        if self._tmp is None:
            self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        base = os.path.realpath(self._tmp.name)
        self.store = os.path.join(base, "store")
        run = os.path.join(base, "run")
        shutil.rmtree(run, ignore_errors=True)
        self.home = os.path.join(run, "home")
        os.makedirs(self.home)
        for d in dirs:
            os.makedirs(os.path.join(self.home, d), exist_ok=True)
        self._fresh = self._listing()
        return self.home

    def _listing(self):
        return sorted(os.path.relpath(os.path.join(d, n), self.home)
                      for d, dirs, files in os.walk(self.home) for n in dirs + files)

    def run(self, key, fn):
        if key is None or self._listing() != self._fresh:
            return fn()
        if key in self._done:
            copy, result = self._done[key]
            shutil.rmtree(self.home)
            shutil.copytree(copy, self.home, symlinks=True)
            return result
        result = fn()
        copy = os.path.join(self.store, str(len(self._done)))
        shutil.copytree(self.home, copy, symlinks=True)
        self._done[key] = (copy, result)
        return result


if __name__ == "__main__":
    # self-check: a cached key restores the HOME and the result; a written HOME
    # or a None key always runs
    cache, calls = InstallCache(), []

    def install():
        calls.append(1)
        with open(os.path.join(cache.home, "installed"), "w") as fh:
            fh.write(cache.home)
        return len(calls)

    home = cache.fresh((".codex",))
    assert cache.run("k", install) == 1
    assert cache.fresh((".codex",)) == home and not os.path.exists(home + "/installed")
    assert cache.run("k", install) == 1 and len(calls) == 1
    assert open(os.path.join(home, "installed")).read() == home
    cache.fresh((".codex",))
    open(os.path.join(home, "mine"), "w").close()
    assert cache.run("k", install) == 2
    cache.fresh((".codex",))
    assert cache.run(None, install) == 3
    print("ok")
