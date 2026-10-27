import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.pilot_critic_gate import evaluate_gate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    if args.output.resolve() == args.review.resolve():
        parser.error("Output must differ from the review input.")

    review = json.loads(args.review.read_text(encoding="utf-8"))
    result = evaluate_gate(review)
    result["review_source"] = str(args.review.resolve())

    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")

    print(json.dumps(result, indent=2))
    print("Consistency check only; no modelling was executed.")


if __name__ == "__main__":
    main()
