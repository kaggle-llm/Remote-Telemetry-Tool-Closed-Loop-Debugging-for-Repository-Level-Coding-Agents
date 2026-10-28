"""Playback control for a single media track."""

from __future__ import annotations

from enum import Enum
from typing import Protocol


class DecoderError(RuntimeError):
    """Raised when the media decoder refuses a command."""


class PlaybackState(Enum):
    """States a player can be in."""

    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


class Decoder(Protocol):
    """Backend that turns compressed media into audio and video."""

    def start(self) -> None: ...

    def pause(self) -> None: ...

    def stop(self) -> None: ...


class MediaPlayer:
    """Drives a decoder and keeps track of the playback state."""

    def __init__(self, decoder: Decoder) -> None:
        self._decoder = decoder
        self._state = PlaybackState.STOPPED
        self._last_error: str | None = None

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

    def play(self) -> bool:
        """Start playback and report whether the decoder accepted it."""
        if self._state is PlaybackState.PLAYING:
            return True
        self._state = PlaybackState.PLAYING
        try:
            self._decoder.start()
        except DecoderError:
            return False
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
