"""Ordering rules for the media playlist."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Track:
    """One entry of the playlist."""

    track_id: str
    title: str
    duration_ms: int


class Playlist:
    """Keeps the ordered list of tracks queued for playback."""

    def __init__(self, tracks: list[Track] | None = None) -> None:
        self._tracks = list(tracks) if tracks is not None else []
        self._index = 0

    def __len__(self) -> int:
        return len(self._tracks)

    @property
    def current(self) -> Track | None:
        """The track that is playing, if the playlist is not empty."""
        if not self._tracks:
            return None
        return self._tracks[self._index]

    @property
    def total_duration_ms(self) -> int:
        """Sum of the durations of every queued track."""
        return sum(track.duration_ms for track in self._tracks)

    def add(self, track: Track) -> None:
        """Append ``track`` to the end of the playlist."""
        self._tracks.append(track)

    def next(self) -> Track | None:
        """Advance to the next track and return it."""
        if not self._tracks:
            return None
        self._index = (self._index + 1) % len(self._tracks)
        return self._tracks[self._index]

    def move(self, track_id: str, position: int) -> bool:
        """Move a track to ``position``, reporting whether it was found.

        The track that is playing keeps playing after the move.
        """
        if position < 0 or position >= len(self._tracks):
            return False
        playing = self.current
        for index, track in enumerate(self._tracks):
            if track.track_id != track_id:
                continue
            self._tracks.pop(index)
            self._tracks.insert(position, track)
            if playing is not None:
                self._index = next(
                    slot for slot, item in enumerate(self._tracks) if item.track_id == playing.track_id
                )
            return True
        return False
