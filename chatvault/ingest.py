"""Ingestion orchestrator for ChatVault."""
import argparse
import sys
from pathlib import Path

from chatvault.connectors import get_connectors
from chatvault.db import Database


def main(data_dir: str | Path | None = None, force: bool = False) -> None:
    """Run ingestion on the given data directory.

    Args:
        data_dir: Path to export data. Defaults to ./data/ and scans subdirectories.
        force: If True, drop and recreate all tables before ingestion.
    """
    # Resolve data directory
    if data_dir:
        dirs_to_scan = [Path(data_dir)]
    else:
        base = Path("data")
        if base.is_dir():
            # Scan base and all immediate subdirectories
            dirs_to_scan = [base] + [p for p in base.iterdir() if p.is_dir()]
        else:
            print("No data/ directory found. Pass a path as argument.")
            sys.exit(1)

    import os
    db_path = os.environ.get("CHATVAULT_DB_PATH", "chatvault.db")
    db = Database(db_path)

    if force:
        print("Force mode: dropping all tables...")
        db.drop_all()
        db.init_schema()

    connectors = get_connectors()
    total_conv = 0
    total_msg = 0

    for scan_dir in dirs_to_scan:
        for connector in connectors:
            if connector.detect(scan_dir):
                print(f"Detected {connector.source_name} export in {scan_dir}")
                result = connector.ingest(scan_dir, db)
                total_conv += result.conversations
                total_msg += result.messages
                extras_str = ", ".join(f"{k}: {v}" for k, v in result.extras.items())
                print(
                    f"  Ingested {result.conversations} conversations, "
                    f"{result.messages} messages"
                    + (f" ({extras_str})" if extras_str else "")
                )

    if total_conv == 0:
        print("No supported exports detected in the provided path(s).")
    else:
        # Rebuild FTS index
        print("Rebuilding FTS index...")
        db.rebuild_fts()
        print(f"\nDone. Total: {total_conv} conversations, {total_msg} messages.")

    db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ChatVault ingestion")
    parser.add_argument("data_dir", nargs="?", default=None, help="Path to export data directory")
    parser.add_argument("--force", action="store_true", help="Drop and recreate tables")
    args = parser.parse_args()
    main(data_dir=args.data_dir, force=args.force)
