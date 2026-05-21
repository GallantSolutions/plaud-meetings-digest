# Publishing Plaud Meetings Digest to GitHub

**Audience:** Garrett, one-time setup. After this, every client install is a single curl command.

**Time:** ~15 minutes total. Mostly clicking through GitHub UI.

---

## Why publish?

Without a GitHub repo, every client install means:
- AirDrop the 42 KB zip to their Mac
- Walk them through unzipping it
- `cd` into the folder
- Run `./install.sh`

With a GitHub repo, every client install becomes:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/GallantSolutions/plaud-meetings-digest/main/bootstrap.sh)
```

One line. Pasted into their Terminal. Done. The bootstrap script downloads the latest release, drops it in the canonical install location, and chains into `install.sh`.

---

## Step 1 — Create the GitHub repo

1. Go to https://github.com/new
2. Owner: pick the account/org that should own this (your personal `@garrettbratton` or an org like `@GallantSolutions`)
3. Name: **`plaud-meetings-digest`** (must match what's in `bootstrap.sh` — see Step 5 if you want a different name)
4. Visibility: **Public**
   - Why public: the bootstrap is a curl-pipe install. Private would require auth on the client's Mac, which defeats the one-command pattern.
   - Risk: anyone can see the install code. There are no secrets in the bundle (Notion API keys are entered by the client at install time + stored in their `~/.claude/skills/meetings-digest/config.json` mode 600). Safe to be public.
5. Don't initialize with README / .gitignore / license — we'll push from local.
6. Click **Create repository**.

GitHub shows you the repo URL — copy it for Step 2.

---

## Step 2 — Push the bundle from this vault

From this vault's terminal:

```bash
cd "/Users/garrett3ratton/Documents/Claude MASTER/04_labs/g_labs/plaud-meetings-digest"

git init
git add .
git commit -m "v1.2.0: Friday weekly rollup"
git branch -M main
git remote add origin git@github.com:GallantSolutions/plaud-meetings-digest.git
git push -u origin main
```

Replace `GallantSolutions` with whatever you picked in Step 1.

If you don't have SSH set up for GitHub, use HTTPS instead:

```bash
git remote add origin https://github.com/GallantSolutions/plaud-meetings-digest.git
```

GitHub may prompt for a personal access token (the GitHub username + PAT pattern). Generate one at https://github.com/settings/tokens (classic, `repo` scope, no expiry needed).

---

## Step 3 — Tag the release

The bootstrap downloads the latest tagged release. Create v1.2.0:

```bash
git tag -a v1.2.0 -m "v1.2.0 — Friday weekly rollup"
git push origin v1.2.0
```

Then go to https://github.com/GallantSolutions/plaud-meetings-digest/releases/new

- Tag: `v1.2.0` (pick from dropdown)
- Title: `v1.2.0 — Friday Weekly Rollup`
- Description: paste the version notes from `README.md`'s Versions section
- Click **Publish release**

GitHub auto-generates a release tarball (`v1.2.0.tar.gz`) — that's what `bootstrap.sh` downloads.

---

## Step 4 — Test the one-liner on YOUR Mac first

Don't ship to the client until you've verified the one-liner end-to-end. Open a fresh Terminal on your Mac:

```bash
# Optional: delete any existing install first so this is a true fresh-install test
rm -rf "$HOME/Library/Application Support/plaud-meetings-digest"
~/.claude/skills/meetings-digest/scripts/../../../../Documents/Claude\ MASTER/04_labs/g_labs/plaud-meetings-digest/uninstall.sh 2>/dev/null || true

# Run the one-liner
bash <(curl -fsSL https://raw.githubusercontent.com/GallantSolutions/plaud-meetings-digest/main/bootstrap.sh)
```

It should:
1. Resolve `v1.2.0` as the latest release
2. Download the tarball to a temp dir
3. Extract + move to `~/Library/Application Support/plaud-meetings-digest`
4. Chain into `install.sh` which walks the interactive setup

If anything breaks, fix it in this vault, push a commit, retag (`v1.2.1`), redo the release, and re-test. Don't ship until clean.

---

## Step 5 — If your repo name differs from `GallantSolutions/plaud-meetings-digest`

`bootstrap.sh` has this default:

```bash
REPO="${PLAUD_DIGEST_REPO:-GallantSolutions/plaud-meetings-digest}"
```

If your GitHub `<owner>/<repo>` is different:

**Option A — edit the default.** Open `bootstrap.sh`, change the default value, commit, push, retag.

**Option B — override at run-time.** The client's one-liner becomes:

```bash
PLAUD_DIGEST_REPO=GallantSolutions/<your-repo> bash <(curl -fsSL https://raw.githubusercontent.com/GallantSolutions/<your-repo>/main/bootstrap.sh)
```

A is cleaner for repeatable installs. Pick A.

---

## Step 6 — Update the operator install guide

The current `OPERATOR-INSTALL-GUIDE.md` documents the AirDrop+zip flow. Replace Step 7 ("Unzip the bundle + run the installer") with the one-liner:

```markdown
### Step 7 — Install everything with the one-liner

Have the client's Terminal open. Paste this exact command:

`bash <(curl -fsSL https://raw.githubusercontent.com/GallantSolutions/plaud-meetings-digest/main/bootstrap.sh)`

Press Enter. The bootstrap downloads the latest release and chains into the interactive installer.

The interactive parts (Plaud OAuth, Notion setup, schedule confirmation) work the same as before — see Part 7a, 7b, 7c below.
```

I can update the operator guide for you if you want — say the word and I'll do it. (You'll need to substitute `GallantSolutions` once you've decided.)

---

## Ongoing workflow — shipping updates

When you ship v1.3.0:

1. Make changes in this vault at `04_labs/g_labs/plaud-meetings-digest/`
2. `cd` into that folder
3. `git add . && git commit -m "v1.3.0: <what changed>"`
4. `git push`
5. `git tag -a v1.3.0 -m "v1.3.0 — <one-liner>"`
6. `git push origin v1.3.0`
7. On GitHub: Releases → Draft new release → tag `v1.3.0` → publish
8. Test the one-liner on your Mac
9. Existing clients: tell them to re-run the one-liner (it overwrites the install). Their Notion DB + config + dedup state survive because they live in `~/.claude/skills/meetings-digest/` and the user's Notion workspace, both of which the installer preserves.

The bootstrap auto-resolves "latest release" each time it's run — so no client needs to know the version number, ever.

---

## Repo hygiene (optional but recommended)

- **Branch protection** on `main`: Settings → Branches → Add rule → require PR + status checks before merge. Prevents you from breaking `bootstrap.sh` with a direct push.
- **Add a LICENSE file**: pick MIT or Apache 2.0. Makes the public-repo intent explicit.
- **Add a `.gitignore`** at repo root to exclude `__pycache__/`, `*.pyc`, `.DS_Store`, the testing artifacts under `_generated/` (if any creep in).
- **GitHub Actions for syntax check**: a tiny workflow that runs `bash -n install.sh`, `bash -n bootstrap.sh`, `python3 -m py_compile scripts/*.py` on every push. Catches typos before clients hit them.

I can scaffold any of these for you in a follow-up if you want.

---

## Quick reference

After Step 3, your client-install one-liner is:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/GallantSolutions/plaud-meetings-digest/main/bootstrap.sh)
```

Bookmark that line. It's your ship.
