import argparse
from pathlib import Path

import pandas as pd

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract variables and data types from downloaded NHANES XPT files."
    )
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    inventory = pd.read_csv(args.inventory)
    successful = inventory[inventory["status"].isin(["downloaded", "reused"])]

    schema_rows = []
    report_rows = []

    for row in successful.itertuples(index=False):
        source = Path(args.raw_dir) / f"{row.file}.xpt"

        try:
            frame = pd.read_sas(source, format="xport", encoding="latin1")

            for variable in frame.columns:
                schema_rows.append(
                    {
                        "cycle": row.cycle,
                        "split": row.split,
                        "file": row.file,
                        "variable": str(variable),
                        "dtype": str(frame[variable].dtype),
                    }
                )

            report_rows.append(
                {
                    "cycle": row.cycle,
                    "file": row.file,
                    "status": "parsed",
                    "rows": len(frame),
                    "columns": len(frame.columns),
                }
            )
        except Exception as error:
            report_rows.append(
                {
                    "cycle": row.cycle,
                    "file": row.file,
                    "status": "failed",
                    "error": repr(error),
                }
            )

    output = Path(args.output)
    report = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(schema_rows).to_csv(output, index=False)
    pd.DataFrame(report_rows).to_csv(report, index=False)

if __name__ == "__main__":
    main()
