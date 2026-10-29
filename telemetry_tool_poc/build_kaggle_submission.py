"""Assemble the Kaggle submission package from the paper draft and figures.

Writes `kaggle_submission/writeup.md` (the draft with figure links rewritten to
the packaged `figures/` folder), copies the four figures next to it and writes
the live word count so the submission can be checked against the 3,000-word
limit without guesswork.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from paper_word_count import LIMIT, prose_words, raw_tokens

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
SOURCE = ROOT / "PAPER_DRAFT.md"
OUTPUT_DIR = REPO / "kaggle_submission"
FIGURES_DIR = OUTPUT_DIR / "figures"
FIGURES = (
    "figure_trust_boundaries.png",
    "figure_closed_loop.png",
    "figure_state_machine.png",
    "figure_ab_results.png",
)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    text = SOURCE.read_text(encoding="utf-8")
    for name in FIGURES:
        source = ROOT / name
        if source.is_file():
            shutil.copyfile(source, FIGURES_DIR / name)

    text = re.sub(
        r"!\[([^\]]*)\]\(([^)]+)\)",
        lambda match: f"![{match.group(1)}](figures/{Path(match.group(2)).name})",
        text,
    )
    (OUTPUT_DIR / "writeup.md").write_text(text, encoding="utf-8", newline="\n")

    prose = len(prose_words(text))
    raw = len(raw_tokens(text))
    report = (
        f"prose words: {prose}\n"
        f"raw tokens: {raw}\n"
        f"limit: {LIMIT}\n"
        f"prose headroom: {LIMIT - prose}\n"
        f"raw headroom: {LIMIT - raw}\n"
    )
    (OUTPUT_DIR / "word_count.txt").write_text(report, encoding="utf-8", newline="\n")

    print(f"Wrote {OUTPUT_DIR / 'writeup.md'}")
    print(report)


if __name__ == "__main__":
    main()
