#!/usr/bin/env bash
# Deprecated: docs/wiki/ was removed during the documentation consolidation.
# The canonical docs now live in docs/*.md (see docs/README.md and the root README).
set -euo pipefail
echo "docs/wiki/ no longer exists. The GitHub Wiki handbook was consolidated into" >&2
echo "the repo docs (docs/*.md, docs/runbooks/, docs/adr/). Nothing to publish." >&2
exit 0
