#!/usr/bin/env bash
# Publish docs/wiki/ to the GitHub Wiki (personal-ai.wiki.git).
#
# Prerequisite: wiki must exist once. If `git push` says "Repository not found",
# open https://github.com/sreeram843/personal-ai/wiki and click
# "Create the first page" (any Home content), Save, then re-run this script.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${ROOT}/docs/wiki"
TMP="${TMPDIR:-/tmp}/personal-ai.wiki-publish.$$"
WIKI_URL="${WIKI_GIT_URL:-https://github.com/sreeram843/personal-ai.wiki.git}"

if [[ ! -d "$SRC" ]]; then
  echo "Missing $SRC" >&2
  exit 1
fi

cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

if git ls-remote "$WIKI_URL" HEAD &>/dev/null; then
  git clone "$WIKI_URL" "$TMP"
else
  mkdir -p "$TMP"
  git -C "$TMP" init
  git -C "$TMP" remote add origin "$WIKI_URL"
  git -C "$TMP" checkout -B master
fi

rsync -a --delete --exclude .git "$SRC/" "$TMP/"
git -C "$TMP" add -A
if git -C "$TMP" diff --cached --quiet; then
  echo "No wiki changes to publish."
  exit 0
fi
git -C "$TMP" -c user.email="${GIT_AUTHOR_EMAIL:-wiki@users.noreply.github.com}" \
  -c user.name="${GIT_AUTHOR_NAME:-CurAI Wiki}" \
  commit -m "Update CurAI wiki handbook."
git -C "$TMP" push -u origin HEAD:master
echo "Published → https://github.com/sreeram843/personal-ai/wiki"
