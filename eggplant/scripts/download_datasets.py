#!/usr/bin/env python3
"""Download HuggingFace datasets listed in eggplant/manifest.json."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EGGPLANT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = EGGPLANT_ROOT / "manifest.json"
DATASETS_DIR = EGGPLANT_ROOT / "datasets"
STATUS_PATH = DATASETS_DIR / "download_status.json"

DEFAULT_MAX_ROWS = 1000


def _json_safe(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"__bytes__": True, "length": len(value)}
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _text_column(row: dict[str, Any]) -> str | None:
    for key in ("text", "prompt", "query", "question", "input", "content", "instruction"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _label_value(row: dict[str, Any]) -> Any:
    for key in ("label", "labels", "is_injection", "injection", "class", "category"):
        if key in row:
            return row[key]
    return None


def _download_hf_dataset(
    *,
    dataset_id: str,
    config: str | None,
    split: str,
    max_rows: int,
    dest: Path,
) -> dict[str, Any]:
    from datasets import load_dataset

    load_kwargs: dict[str, Any] = {"path": dataset_id, "split": split}
    if config:
        load_kwargs["name"] = config

    # Slice split to avoid multiprocess pickling issues during full scans.
    if max_rows > 0:
        load_kwargs["split"] = f"{split}[:{max_rows}]"

    table = load_dataset(**load_kwargs)
    rows: list[dict[str, Any]] = []
    columns: set[str] = set()
    for row in table:
        normalized = _json_safe(dict(row))
        rows.append(normalized)
        columns.update(normalized.keys())

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(
            {
                "hf_id": dataset_id,
                "config": config,
                "split": split,
                "row_limit": max_rows,
                "row_count": len(rows),
                "columns": sorted(columns),
                "rows": rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "status": "downloaded",
        "row_count": len(rows),
        "columns": sorted(columns),
        "path": str(dest.relative_to(EGGPLANT_ROOT)),
    }


def _download_entry(entry: dict[str, Any], *, force: bool) -> dict[str, Any]:
    entry_id = entry["id"]
    hf_id = entry.get("hf_id")
    dest = DATASETS_DIR / f"{entry_id}.json"

    if dest.exists() and not force:
        cached = json.loads(dest.read_text(encoding="utf-8"))
        return {
            "id": entry_id,
            "status": "cached",
            "row_count": cached.get("row_count", 0),
            "columns": cached.get("columns", []),
            "path": str(dest.relative_to(EGGPLANT_ROOT)),
        }

    if not hf_id:
        return {
            "id": entry_id,
            "status": "skipped",
            "reason": entry.get("github") or entry.get("url") or "no HuggingFace id",
        }

    max_rows = int(entry.get("max_rows") or DEFAULT_MAX_ROWS)
    config = entry.get("hf_config")
    split = entry.get("hf_split") or "train"

    try:
        result = _download_hf_dataset(
            dataset_id=hf_id,
            config=config,
            split=split,
            max_rows=max_rows,
            dest=dest,
        )
        return {"id": entry_id, "hf_id": hf_id, **result}
    except Exception as exc:  # noqa: BLE001 - collect per-dataset failures
        message = str(exc)
        if "gated dataset" in message.lower():
            message += " (set HF_TOKEN and accept the dataset license on HuggingFace)"
        return {
            "id": entry_id,
            "hf_id": hf_id,
            "status": "failed",
            "error": message,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Download eggplant manifest datasets from HuggingFace.")
    parser.add_argument("--force", action="store_true", help="Re-download even if cached JSON exists.")
    parser.add_argument("--id", action="append", dest="ids", help="Only download specific manifest ids.")
    args = parser.parse_args()

    manifest = _load_manifest()
    entries = manifest["sources"]
    if args.ids:
        wanted = set(args.ids)
        entries = [entry for entry in entries if entry["id"] in wanted]

    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for entry in entries:
        print(f"→ {entry['id']} ({entry.get('hf_id') or 'no-hf'})")
        results.append(_download_entry(entry, force=args.force))

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
        "counts": {
            "downloaded": sum(1 for item in results if item.get("status") == "downloaded"),
            "cached": sum(1 for item in results if item.get("status") == "cached"),
            "skipped": sum(1 for item in results if item.get("status") == "skipped"),
            "failed": sum(1 for item in results if item.get("status") == "failed"),
        },
    }
    STATUS_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary["counts"], indent=2))
    print(f"Wrote {STATUS_PATH}")
    return 0 if summary["counts"]["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
