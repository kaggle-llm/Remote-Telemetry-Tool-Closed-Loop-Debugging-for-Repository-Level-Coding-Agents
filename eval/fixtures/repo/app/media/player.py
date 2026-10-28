"""Playback control for a single media track."""

from __future__ import annotations

import time
from enum import Enum
from typing import Callable, Protocol


class DecoderError(RuntimeError):
    """Raised when the media decoder refuses a command."""


class PlaybackState(Enum):
    """States a player can be in."""

    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


class Decoder(Protocol):
    """Backend that turns compressed media into audio and video."""

    def start(self) -> None:
        """Begin decoding the current track."""
        ...

    def pause(self) -> None:
        """Pause decoding."""
        ...

    def stop(self) -> None:
        """Stop decoding and release the decoder resources."""
        ...


class MediaPlayer:
    """Drives a decoder and keeps track of the playback state."""

    def __init__(self, decoder: Decoder, clock: Callable[[], float] = time.monotonic) -> None:
        self._decoder = decoder
        self._clock = clock
        self._state = PlaybackState.STOPPED
        self._last_error: str | None = None
        self._started_at: float | None = None

    @property
    def state(self) -> PlaybackState:
        """The playback state of the player."""
        return self._state

    @property
    def is_playing(self) -> bool:
        """Whether the player currently plays media."""
        return self._state is PlaybackState.PLAYING

    @property
    def last_error(self) -> str | None:
        """Description of the most recent decoder failure."""
        return self._last_error

    @property
    def position_ms(self) -> int:
        """Milliseconds played since the current track started."""
        if self._started_at is None:
            return 0
        return int((self._clock() - self._started_at) * 1000)

    def play(self) -> bool:
        """Start playback and report whether the decoder accepted it."""
        if self._state is PlaybackState.PLAYING:
            return True
        self._state = PlaybackState.PLAYING
        try:
            self._decoder.start()
        except DecoderError:
            return False
        self._started_at = self._clock()
        return True

    def pause(self) -> None:
        """Pause playback."""
        if self._state is not PlaybackState.PLAYING:
            return
        self._decoder.pause()
        self._state = PlaybackState.PAUSED

    def stop(self) -> None:
        """Stop playback and reset the player."""
        self._decoder.stop()
        self._state = PlaybackState.STOPPED
        self._started_at = None
