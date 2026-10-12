# notes

A small note store and the shell that edits it.

## Rules

- **`tests/` is frozen.** Never edit, delete, skip or rename a test. A red test
  means the code is wrong, not the test.
- **A read-only store never changes.** A store opened with `readonly=True`
  (`open_store` does so when `NOTES_READONLY=1`) rejects every command that would
  change it by raising `ReadOnlyError` *before* it changes anything: the notes in
  memory and the file on disk stay exactly as they were. Every command that only
  reads keeps working on a read-only store.

## Layout

- `notes/errors.py` - the package's exceptions.
- `notes/store.py` - the store: notes keyed by name, saved as one JSON object.
- `notes/commands.py` - the shell: one line in, one result out.
- `notes/plugins.py` - extra shell commands registered by name.
