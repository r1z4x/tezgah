Move the profile files to format version 2. There are five steps; do all five.

1. In memory, a profile becomes `{"name": str, "email": str, "tags": list of str}`:
   the key `mail` is renamed `email`, and tags become a list instead of a
   comma-separated string.
2. `profiles/store.py::save` writes version 2 files:
   `{"version": 2, "name": ..., "email": ..., "tags": [...]}`, tags as a JSON list.
3. `profiles/store.py::load` returns the new in-memory shape for version 2 files
   **and** for the version 1 files already on disk - `data/` holds two real ones.
   A version 1 file has no `version` key (or `"version": 1`), carries `mail`, and
   stores tags as a comma-separated string where `""` means no tags. A file whose
   `version` is anything else raises `ProfileError`.
4. Every other reader of a profile in the package works on the new shape, and
   `profiles/export.py::to_csv` produces exactly the same text for a profile as it
   does today.
5. Implement `profiles/migrate.py::migrate_dir` as its docstring says.

Change only files under `profiles/`. Do not rewrite the files in `data/`: they are
the sample of what production has on disk.

`python3 -m unittest discover -s tests` must still pass.
