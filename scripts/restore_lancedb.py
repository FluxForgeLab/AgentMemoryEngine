"""Stop the API, replace a LanceDB named volume from a tar.gz, then chown.

Uses stdlib + the docker CLI (Windows / Linux). Never runs
`docker compose down -v`. Restore is offline and wipes the target volume
before extract so the result matches the archive.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VOLUME = "ame_lance_data"
SERVICE = "agent-memory-engine"
ALPINE = "alpine:3.20"
APP_UID = "10001"
ARCHIVE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
HELP_EXAMPLES = """
Examples (successful on this repo):

  # Production volume (compose name ame_lance_data)
  python scripts/backup_lancedb.py
  python scripts/restore_lancedb.py backup/lance-YYYYMMDD-HHMMSS.tar.gz --yes --start

  # Mock overlay volume (32-dim, isolated from qwen)
  python scripts/backup_lancedb.py --volume ame_lance_mock_data
  python scripts/restore_lancedb.py backup/lance-YYYYMMDD-HHMMSS.tar.gz --volume ame_lance_mock_data --yes --start

Restore stops the API, deletes current volume files, extracts the archive,
then chown 10001:10001 so the non-root container can write. Do not use
compose down -v. Do not restore while the API is still serving traffic.
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


def container_exists(name: str = SERVICE) -> bool:
    completed = subprocess.run(
        ["docker", "inspect", name],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0


def stop_service() -> bool:
    if not container_running():
        print(f"{SERVICE} is not running")
        return False
    run(["docker", "stop", SERVICE])
    return True


def start_service() -> None:
    run(["docker", "start", SERVICE])


def confirm_replace(volume: str, assume_yes: bool) -> None:
    if assume_yes:
        return
    if not sys.stdin.isatty():
        fail("refusing to replace a volume without --yes (stdin is not a TTY)")
    answer = input(
        f"Replace ALL data in volume {volume}? Type yes to continue: "
    ).strip()
    if answer != "yes":
        fail("restore cancelled")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline restore of a LanceDB Docker named volume.",
        epilog=HELP_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "archive",
        help="host path to a .tar.gz produced by backup_lancedb.py",
    )
    parser.add_argument(
        "--volume",
        default=DEFAULT_VOLUME,
        help=f"compose volume name (default: {DEFAULT_VOLUME})",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="do not prompt before replacing volume contents",
    )
    parser.add_argument(
        "--start",
        action="store_true",
        help="start the API container after restore",
    )
    parser.add_argument(
        "--uid",
        default=APP_UID,
        help=f"volume owner after restore (default: {APP_UID})",
    )
    args = parser.parse_args(argv)

    archive = Path(args.archive).resolve()
    if not archive.is_file():
        fail(f"archive not found: {archive}")
    if not ARCHIVE_NAME_RE.fullmatch(archive.name):
        fail(f"unsafe archive filename: {archive.name}")

    volume = resolve_volume(args.volume)
    confirm_replace(volume, args.yes)
    stop_service()

    inner = (
        "find /target -mindepth 1 -exec rm -rf {} +; "
        f"tar xzf /backup/{archive.name} -C /target; "
        f"chown -R {args.uid}:{args.uid} /target"
    )
    run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{volume}:/target",
            "-v",
            f"{archive.parent}:/backup",
            ALPINE,
            "sh",
            "-c",
            inner,
        ]
    )

    if args.start:
        if not container_exists():
            fail(
                "container is gone; start with docker compose up -d "
                "(do not use down -v)"
            )
        start_service()
    else:
        print(f"{SERVICE} is stopped. Start it with docker compose up -d")

    print(f"restored {archive} -> {volume}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
