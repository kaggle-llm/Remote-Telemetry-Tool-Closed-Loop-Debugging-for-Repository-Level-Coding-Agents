"""Loading of the subtitle tracks that belong to a media track."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Cue:
    """One timed line of a subtitle track."""

    start_ms: int
    end_ms: int

    def contains(self, position_ms: int) -> bool:
        """Whether the cue is shown at the playback ``position_ms``."""
        return self.start_ms <= position_ms < self.end_ms


@dataclass(frozen=True)
class SubtitleTrack:
    """The subtitles that belong to one media track."""

    track_id: str
    language: str
    cues: tuple[Cue, ...] = ()

    def cue_at(self, position_ms: int) -> Cue | None:
        """The cue shown at the playback ``position_ms``."""
        for cue in self.cues:
            if cue.contains(position_ms):
                return cue
        return None


def _to_milliseconds(value: str) -> int:
    """Convert a ``hh:mm:ss,mmm`` time code into milliseconds."""
    hours, minutes, rest = value.split(":")
    seconds, _, millis = rest.replace(",", ".").partition(".")
    return (int(hours) * 3600 + int(minutes) * 60 + int(seconds)) * 1000 + int(millis.ljust(3, "0"))


def parse_cues(payload: str) -> tuple[Cue, ...]:
    """Parse the cues of a subtitle file ordered by their start time."""
    cues: list[Cue] = []
    for line in payload.splitlines():
        if "-->" not in line:
            continue
        start_text, _, end_text = line.strip().partition("-->")
        try:
            start_ms = _to_milliseconds(start_text.strip())
            end_ms = _to_milliseconds(end_text.strip().split(" ")[0])
        except ValueError as error:
            raise ValueError("the subtitle file has a broken time code") from error
        cues.append(Cue(start_ms=start_ms, end_ms=end_ms))
    return tuple(sorted(cues, key=lambda cue: cue.start_ms))


class SubtitleLoader:
    """Loads the subtitle tracks that belong to a media track."""

    def __init__(self, reader: Callable[[str], str]) -> None:
        self._reader = reader

    def load(self, track_id: str, language: str = "en") -> SubtitleTrack | None:
        """Load the subtitle track of ``track_id`` when one is available.

        A media track without subtitles is not an error, so the loader
        answers with ``None`` when the file of the track is missing."""
        try:
            payload = self._reader(f"{track_id}.{language}.srt")
        except FileNotFoundError:
            return None
        return SubtitleTrack(track_id=track_id, language=language, cues=parse_cues(payload))
