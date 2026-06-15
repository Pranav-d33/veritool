import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="veritool",
        description="VeriTool — Runtime trace invariant verification for multi-agent LLM systems",
    )
    parser.add_argument("--version", action="version", version="veritool 1.0.1")
    args = parser.parse_args()
    parser.print_help()
    sys.exit(1)
