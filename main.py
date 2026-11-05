"""CLI demo: runs every premade example. Run with: python main.py"""
import json

from examples import TEST_GROUPS
from pipeline import NLFilterPipeline

CREDS = dict(auth_token="jwt_token_valid_123", tenant_id="tenant_realsoft_prod")


def main():
    pipeline = NLFilterPipeline()
    for group, queries in TEST_GROUPS.items():
        print(f"\n=== {group} ===")
        for q in queries:
            print(f"\n> {q}")
            print(json.dumps(pipeline.translate(q, **CREDS), indent=2))


if __name__ == "__main__":
    main()
