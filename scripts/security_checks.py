from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SRC = ROOT / "frontend" / "src"
COMPOSE_FILE = ROOT / "docker-compose.yml"
CONFIG_FILE = ROOT / "app" / "core" / "config.py"

SECRET_PATTERNS = {
    "Private key": re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
    "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "GitHub token": re.compile(r"ghp_[A-Za-z0-9]{36}"),
    "Slack token": re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    "OpenAI key": re.compile(r"sk-[A-Za-z0-9]{20,}"),
}

TEXT_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".ini",
    ".cfg",
    ".env",
    ".sh",
}


def tracked_files() -> list[Path]:
    commands = [
        ["git", "ls-files", "-z"],
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
    ]
    discovered: set[Path] = set()
    for command in commands:
        try:
            result = subprocess.run(
                command,
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=False,
            )
        except Exception:
            continue
        for raw_path in result.stdout.split(b"\0"):
            if not raw_path:
                continue
            path = ROOT / raw_path.decode("utf-8")
            if path.is_file() and path.suffix in TEXT_SUFFIXES:
                discovered.add(path)
    if discovered:
        return sorted(discovered)
    return sorted(path for path in ROOT.rglob("*") if path.is_file() and path.suffix in TEXT_SUFFIXES)


def find_secret_hits(files: list[Path]) -> list[str]:
    findings: list[str] = []
    for path in files:
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(ROOT)
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                findings.append(f"{label}: {rel}")
    return findings


def check_frontend_localhost() -> list[str]:
    findings: list[str] = []
    pattern = re.compile(r"localhost:8000|127\.0\.0\.1:8000")
    for path in FRONTEND_SRC.rglob("*.ts*"):
        content = path.read_text(encoding="utf-8")
        if pattern.search(content):
            findings.append(f"Hardcoded backend host in {path.relative_to(ROOT)}")
    return findings


def check_runtime_security_defaults() -> list[str]:
    findings: list[str] = []
    compose_text = COMPOSE_FILE.read_text(encoding="utf-8")
    config_text = CONFIG_FILE.read_text(encoding="utf-8")

    if "CORS_ORIGINS=*" in compose_text:
        findings.append("docker-compose.yml still sets wildcard CORS origins")
    if 'cors_origins: str = "*"' in config_text:
        findings.append("app/core/config.py still defaults to wildcard CORS origins")
    if "GF_SECURITY_ADMIN_PASSWORD=admin" in compose_text:
        findings.append("docker-compose.yml hardcodes the Grafana admin password")

    return findings


def main() -> int:
    failures: list[str] = []
    failures.extend(find_secret_hits(tracked_files()))
    failures.extend(check_frontend_localhost())
    failures.extend(check_runtime_security_defaults())

    if failures:
        print("Security checks failed:")
        for item in failures:
            print(f"- {item}")
        return 1

    print("Security checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())