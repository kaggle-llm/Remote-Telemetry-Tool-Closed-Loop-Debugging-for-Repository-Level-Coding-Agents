"""Word-count tool for the paper draft.

Reports the prose word count (code blocks, image markup and table separators
removed) and the raw token count (everything counted as separated tokens), so
the submission limit can be checked without guesswork.
"""

import argparse
import re
from pathlib import Path

DEFAULT_DRAFT = Path(__file__).resolve().parent / "PAPER_DRAFT.md"
LIMIT = 3000


def prose_words(text):
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and re.fullmatch(r"\|[\s:\-|]+\|", stripped):
            continue
        stripped = stripped.replace("|", " ")
        stripped = re.sub(r"^#+\s*", "", stripped)
        stripped = re.sub(r"^[-*]\s+", "", stripped)
        stripped = re.sub(r"^\d+\.\s+", "", stripped)
        stripped = stripped.replace("**", "").replace("*", "").replace("`", "")
        lines.append(stripped)
    return [word for word in " ".join(lines).split() if re.search(r"[A-Za-z0-9]", word)]


def raw_tokens(text):
    return [word for word in text.split() if re.search(r"[A-Za-z0-9]", word)]


def main():
    parser = argparse.ArgumentParser(description="Count the words in the paper draft")
    parser.add_argument("--draft", default=str(DEFAULT_DRAFT))
    parser.add_argument("--limit", type=int, default=LIMIT)
    args = parser.parse_args()

    text = Path(args.draft).read_text(encoding="utf-8")
    prose = len(prose_words(text))
    raw = len(raw_tokens(text))
    print(f"draft: {args.draft}")
    print(f"prose words: {prose}")
    print(f"raw tokens: {raw}")
    print(f"limit: {args.limit}")
    print(f"prose headroom: {args.limit - prose}")
    if raw > args.limit:
        print("WARNING: the raw token count exceeds the limit")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
