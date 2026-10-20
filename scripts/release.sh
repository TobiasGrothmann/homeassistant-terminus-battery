#!/usr/bin/env bash
# Cut a release: bump the version, commit, push, wait for the Validate
# workflow, then publish a GitHub release (which is what HACS picks up).
#
#   scripts/release.sh 0.1.1                     # bump → push → wait for CI → release v0.1.1
#   scripts/release.sh 0.1.1 --notes "Fix X"     # custom notes instead of GitHub's generated ones
#   scripts/release.sh 0.1.1 --no-wait           # don't wait for the workflow
#   scripts/release.sh 0.1.1 --dry-run           # report what would happen or block, change nothing
#
# Re-running with the same version after a failed workflow skips the bump and
# only waits/publishes again.
set -euo pipefail

die() { echo "error: $*" >&2; exit 1; }
usage() { sed -n '2,11p' "$0"; exit "${1:-0}"; }

[[ $# -ge 1 ]] || usage 1
[[ "$1" == "-h" || "$1" == "--help" ]] && usage 0

VERSION="${1#v}"
shift
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "version must look like 1.2.3 (got '$VERSION')"
TAG="v$VERSION"

WAIT=1
DRY_RUN=0
NOTES=""
while (($#)); do
  case "$1" in
    --no-wait) WAIT=0 ;;
    --dry-run) DRY_RUN=1 ;;
    --notes) [[ $# -ge 2 ]] || die "--notes needs a value"; NOTES="$2"; shift ;;
    -h|--help) usage 0 ;;
    *) die "unknown option: $1" ;;
  esac
  shift
done

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MANIFEST="$ROOT/custom_components/trmnl_terminus/manifest.json"
PYPROJECT="$ROOT/pyproject.toml"
cd "$ROOT"

# --- preflight ---------------------------------------------------------------
# In dry-run mode every blocking condition is reported and the script goes on,
# so you can see the whole picture at once.
BLOCKED=0
block() {
  if ((DRY_RUN)); then echo "[dry-run] would stop: $*"; BLOCKED=1; else die "$*"; fi
}

command -v gh >/dev/null || block "GitHub CLI (gh) is not installed"
gh auth status >/dev/null 2>&1 || block "gh is not logged in (run: gh auth login)"
[[ "$(git rev-parse --abbrev-ref HEAD)" == "main" ]] || block "switch to main first"
[[ -z "$(git status --porcelain)" ]] || block "working tree is not clean; commit or stash first"
git fetch -q origin main
[[ "$(git rev-parse HEAD)" == "$(git rev-parse origin/main)" ]] \
  || block "main and origin/main differ; pull or push first"
git rev-parse -q --verify "refs/tags/$TAG" >/dev/null && block "tag $TAG already exists locally"
gh release view "$TAG" >/dev/null 2>&1 && block "release $TAG already exists on GitHub"

CURRENT="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$MANIFEST")"

# --- bump + push -------------------------------------------------------------
if [[ "$CURRENT" == "$VERSION" ]]; then
  echo "manifest already at $VERSION, skipping bump"
elif ((DRY_RUN)); then
  echo "[dry-run] would bump $CURRENT → $VERSION in manifest.json and pyproject.toml, commit 'Release $TAG', push to origin/main"
else
  echo "bump $CURRENT → $VERSION"
  python3 - "$MANIFEST" "$VERSION" <<'PY'
import json, sys
path, version = sys.argv[1], sys.argv[2]
with open(path) as f:
    data = json.load(f)
data["version"] = version
with open(path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PY
  sed -i '' -E "s/^version = \"[0-9.]+\"/version = \"$VERSION\"/" "$PYPROJECT"
  git add "$MANIFEST" "$PYPROJECT"
  git commit -q -m "Release $TAG"
  git push -q origin main
  echo "pushed $(git rev-parse --short HEAD)"
fi

if ((DRY_RUN)); then
  ((WAIT)) && echo "[dry-run] would wait for the Validate workflow to pass"
  echo "[dry-run] would run: gh release create $TAG --target main --title $TAG ${NOTES:+--notes '…'}${NOTES:---generate-notes}"
  ((BLOCKED)) && { echo "[dry-run] a real run would have stopped at the first problem above"; exit 1; }
  exit 0
fi

# --- wait for CI -------------------------------------------------------------
SHA="$(git rev-parse HEAD)"
if ((WAIT)); then
  echo "waiting for Validate workflow on ${SHA:0:7} …"
  RUN_ID=""
  for _ in $(seq 1 24); do
    RUN_ID="$(gh run list --workflow Validate --commit "$SHA" --json databaseId --jq '.[0].databaseId' 2>/dev/null || true)"
    [[ -n "$RUN_ID" ]] && break
    sleep 5
  done
  [[ -n "$RUN_ID" ]] || die "no Validate run found for $SHA after two minutes"
  if ! gh run watch "$RUN_ID" --exit-status --interval 10 >/dev/null; then
    die "Validate failed, no release created. Fix it, push, then re-run: scripts/release.sh $VERSION"
  fi
  echo "Validate passed"
fi

# --- release -----------------------------------------------------------------
if [[ -n "$NOTES" ]]; then
  gh release create "$TAG" --target main --title "$TAG" --notes "$NOTES"
else
  gh release create "$TAG" --target main --title "$TAG" --generate-notes
fi
