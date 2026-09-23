@echo off
rem tezgah-dsh.cmd - launch the DeepSeek Harness (dsh) CLI on Windows.
rem
rem The Windows twin of bin/tezgah-dsh, the /bin/sh wrapper: a machine with no
rem sh cannot start that file, so tezgah-setup copies this one to
rem ~/.local/bin/dsh.cmd, the name cmd.exe resolves through PATHEXT. Everything
rem below is resolved absolutely - the CLI under the profile home and the index
rem farm under the config dir - so the copy works from anywhere. Arguments are
rem passed through untouched.
rem
rem dsh boots its hooks under a workspace-write sandbox that confines hook
rem subprocesses to the workspace plus the platform temp dir. The graph index
rem worker writes .codegraph/ inside the repository and the CLI it calls wants a
rem writable cache of its own, which that sandbox denies for a repo dsh has
rem never seen; without the warm-up below such a repo would never get indexed
rem from the hook. The launcher runs in the user's shell, unconfined, so it
rem starts the same worker the hooks use - HEAD-stamped, so it is a no-op when
rem the graph is current.
setlocal

rem The profile home defaults to the place the sh launcher's ${DSH_HOME:-...}
rem resolves to, so both twins find one tree.
if not defined DSH_HOME set "DSH_HOME=%USERPROFILE%\.dsh"
set "BIN=%DSH_HOME%\profiles\node_modules\@deepseek-ai\dsh\lib\bin.js"

if exist "%BIN%" goto dsh_cli
where npx >nul 2>nul
if errorlevel 1 goto no_cli

rem A fresh machine has no profile tree yet; npx runs dsh and materializes the
rem profile home, so the host works before the first explicit dsh web boot.
call :warm
rem cmd.exe has no exec, so the launcher waits for the CLI and returns its own
rem exit code, which is what a caller scripts against.
npx -y @deepseek-ai/dsh %*
exit /b %errorlevel%

:dsh_cli
call :warm
node "%BIN%" %*
exit /b %errorlevel%

:no_cli
echo tezgah-dsh: dsh CLI not found at %BIN% 1>&2
echo tezgah-dsh: install the DeepSeek Harness (npx -y @deepseek-ai/dsh) or set DSH_HOME 1>&2
exit /b 127

:warm
rem Best effort, as in the sh twin: a machine that cannot start the worker
rem still starts dsh. The farm entry is a Python script
rem (a relay where a symlink was refused), so it is started the way
rem hooks/tezgah_paths.python_cmd resolves an interpreter: the pin first, then
rem the names Windows ships - python3 is never one of them - and py last.
set "CONFIG=%XDG_CONFIG_HOME%"
if not defined CONFIG set "CONFIG=%USERPROFILE%\.config"
set "INDEX=%TEZGAH_INDEX_BIN%"
if not defined INDEX set "INDEX=%CONFIG%\tezgah\bin\tezgah-index"
if not exist "%INDEX%" exit /b 0
set "PY=%TEZGAH_PYTHON%"
if defined PY goto warm_run
where python3 >nul 2>nul && set "PY=python3"
if defined PY goto warm_run
where python >nul 2>nul && set "PY=python"
if defined PY goto warm_run
where py >nul 2>nul && set "PY=py"
if not defined PY exit /b 0

:warm_run
"%PY%" "%INDEX%" "%CD%" >nul 2>nul
exit /b 0
