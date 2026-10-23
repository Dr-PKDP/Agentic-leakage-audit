import argparse
from pathlib import Path

import pandas as pd

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a descriptive cross-cycle NHANES variable-availability table."
    )
    parser.add_argument("--schema", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    schema = pd.read_csv(args.schema)

    schema["component"] = schema["file"].str.replace(
        r"_[A-Z]$",
        "",
        regex=True,
    )

    harmonization = (
        schema.groupby(["component", "variable"], as_index=False)
        .agg(
            cycles=("cycle", lambda values: "|".join(sorted(set(values)))),
            n_cycles=("cycle", "nunique"),
            dtypes=("dtype", lambda values: "|".join(sorted(set(values)))),
        )
        .sort_values(["component", "variable"])
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    harmonization.to_csv(output, index=False)

if __name__ == "__main__":
    main()
