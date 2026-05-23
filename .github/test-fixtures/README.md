# Test fixtures

Files in this directory are inputs to the install-correctness validation
workflow at [`../workflows/test-install.yml`](../workflows/test-install.yml).
They are not used at install time on a client's machine — they only drive
non-interactive validation runs.

## `canned-input.txt`

One answer per `read -p` prompt that `install.sh` / `install.ps1` issues
during a non-interactive sandboxed install. Order matches the prompts in
`install.sh`:

```
                # Step 1: press-enter prompt after prereq check
2               # Step 3: destination choice → 2 = folder (skips Notion API key requirement)
                # Step 3: folder path → empty = default
                # Step 4: routing defaults → empty = Y (use defaults)
                # Step 5: schedule enable → empty = Y
```

Used by Gallant's `/validate-build` skill (vault-internal tooling).
Without this fixture, sandboxed installs hit an interactive prompt with
no stdin and exit early.
