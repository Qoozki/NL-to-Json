"""CLI demo: runs every premade example. Run with: python main.py"""
import json
import os

from examples import TEST_GROUPS
from pipeline import NLFilterPipeline


def main():
    pipeline = NLFilterPipeline(model_name=os.getenv("MODEL_NAME", "llama3.2"))
    for group, queries in TEST_GROUPS.items():
        print(f"\n=== {group} ===")
        for q in queries:
            print(f"\n> {q}")
            print(json.dumps(pipeline.translate(q), indent=2))


if __name__ == "__main__":
    main()
