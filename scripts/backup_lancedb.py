"""Stop the API, then tar a LanceDB named volume to backup/*.tar.gz.

Uses stdlib + the docker CLI (Windows / Linux). Never runs
`docker compose down -v`. Backup is offline so the archive is consistent.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VOLUME = "ame_lance_data"
DEFAULT_OUTPUT_DIR = ROOT / "backup"
SERVICE = "agent-memory-engine"
ALPINE = "alpine:3.20"
HELP_EXAMPLES = """
Examples (successful on this repo):

  # Production volume (compose name ame_lance_data)
  python scripts/backup_lancedb.py
  python scripts/restore_lancedb.py backup/lance-YYYYMMDD-HHMMSS.tar.gz --yes --start

  # Mock overlay volume (32-dim, isolated from qwen)
  python scripts/backup_lancedb.py --volume ame_lance_mock_data
  python scripts/restore_lancedb.py backup/lance-YYYYMMDD-HHMMSS.tar.gz --volume ame_lance_mock_data --yes --start

Restore replaces all files in the target volume. Do not use compose down -v.
"""


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(cmd))
    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        fail(f"{' '.join(cmd)} exited {completed.returncode}: {detail}")
    return completed


def list_volumes() -> list[str]:
    completed = run(["docker", "volume", "ls", "-q"])
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def resolve_volume(name: str) -> str:
    volumes = list_volumes()
    if name in volumes:
        return name
    matches = [item for item in volumes if item.endswith(f"_{name}")]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        fail(f"ambiguous volume {name!r}: {', '.join(matches)}")
    fail(f"volume {name!r} not found; create it with docker compose up first")


def container_running(name: str = SERVICE) -> bool:
    completed = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", name],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def stop_service() -> bool:
    if not container_running():
        print(f"{SERVICE} is not running")
        return False
    run(["docker", "stop", SERVICE])
    return True


def start_service() -> None:
    run(["docker", "start", SERVICE])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline backup of a LanceDB Docker named volume.",
        epilog=HELP_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--volume",
        default=DEFAULT_VOLUME,
        help=f"compose volume name (default: {DEFAULT_VOLUME})",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="host directory for the tar.gz (default: ./backup)",
    )
    parser.add_argument(
        "--no-restart",
        action="store_true",
        help="leave the API stopped after backup",
    )
    args = parser.parse_args(argv)

    volume = resolve_volume(args.volume)
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_name = time.strftime("lance-%Y%m%d-%H%M%S.tar.gz")
    host_archive = output_dir / archive_name

    stopped = stop_service()
    try:
        run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{volume}:/source",
                "-v",
                f"{output_dir}:/backup",
                ALPINE,
                "tar",
                "czf",
                f"/backup/{archive_name}",
                "-C",
                "/source",
                ".",
            ]
        )
    finally:
        if stopped and not args.no_restart:
            start_service()

    if not host_archive.is_file() or host_archive.stat().st_size == 0:
        fail(f"backup archive missing or empty: {host_archive}")

    print(f"wrote {host_archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
