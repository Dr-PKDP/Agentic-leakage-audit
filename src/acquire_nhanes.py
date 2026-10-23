import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--inventory", required=True)
    args = parser.parse_args()

    if args.split.startswith("locked"):
        raise SystemExit("Locked split refused by acquisition script.")

    manifest = pd.read_csv(args.manifest)
    subset = manifest[manifest["split"] == args.split]
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    records = []
    for row in subset.itertuples(index=False):
        destination = output_dir / f"{row.file}.xpt"
        event = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "cycle": row.cycle,
            "split": row.split,
            "file": row.file,
            "url": row.url,
        }

        try:
            if destination.exists() and destination.stat().st_size > 1024:
                event.update(
                    status="reused",
                    bytes=destination.stat().st_size,
                    sha256=sha256(destination),
                )
            else:
                response = requests.get(row.url, timeout=(20, 180))
                response.raise_for_status()
                destination.write_bytes(response.content)
                event.update(
                    status="downloaded",
                    http_status=response.status_code,
                    bytes=destination.stat().st_size,
                    sha256=sha256(destination),
                )
        except Exception as error:
            event.update(status="failed", error=repr(error), bytes=None, sha256=None)

        log_path = Path(args.log)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")

        records.append(event)

    Path(args.inventory).parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records).to_csv(args.inventory, index=False)

    if any(record["status"] == "failed" for record in records):
        raise SystemExit(2)

if __name__ == "__main__":
    main()
