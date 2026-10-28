"""Held-out validation suite for the PaperTrack synthetic application.

Every test in this module checks one reported failure through the public
behaviour of the application. A test passes as soon as the observable
symptom is gone, no matter how the fix was implemented.
"""

import unittest

from app.auth.cache import Credential, CredentialCache
from app.media.player import DecoderError, MediaPlayer, PlaybackState
from app.net.imageloader import ImageLoader, ImageRequest
from app.reader.anchor import AnchorStore, ReadingAnchor
from app.sync.retry import RetryPolicy, RetryRunner, SyncError, TransientSyncError
from app.ui.palette import HighlightPalette, PresentationContext


class PaletteValidation(unittest.TestCase):
    """The highlight palette has to open on the context it was created for."""

    def test_palette_opens_with_presentation_context(self) -> None:
        context = PresentationContext(view="HighlightPaletteView", session_id="s-7")
        palette = HighlightPalette(context)
        self.assertTrue(palette.open_palette())
        self.assertTrue(palette.is_open)
        self.assertEqual(palette.current_context, context)


class ImageLoaderValidation(unittest.TestCase):
    """A download without an explicit timeout still has to be bounded."""

    def test_image_download_uses_a_bounded_timeout(self) -> None:
        recorded: list[int] = []

        class RecordingFetcher:
            def fetch(self, url: str, timeout_ms: int) -> bytes:
                recorded.append(timeout_ms)
                return b"image-bytes"

        loader = ImageLoader(RecordingFetcher(), timeout_ms=2500)
        payload = loader.load(ImageRequest(url="https://cdn.test/a.png"))
        self.assertEqual(payload, b"image-bytes")
        self.assertEqual(len(recorded), 1)
        self.assertGreater(recorded[0], 0)
        self.assertLessEqual(recorded[0], 2500)


class AnchorValidation(unittest.TestCase):
    """An anchor on a page that no longer exists has to be dropped."""

    def test_anchor_on_a_missing_page_is_rejected(self) -> None:
        store = AnchorStore()
        store.save("doc-1", ReadingAnchor(page=5, offset=12))
        self.assertIsNone(store.restore("doc-1", page_count=5))


class RetryValidation(unittest.TestCase):
    """An operation without an idempotency key must not be replayed."""

    def test_operation_without_idempotency_key_is_not_retried(self) -> None:
        attempts: list[int] = []

        def operation() -> str:
            attempts.append(1)
            raise TransientSyncError("the server is busy")

        runner = RetryRunner(policy=RetryPolicy(attempts=3, base_delay_ms=1), sleep=lambda _: None)
        with self.assertRaises(SyncError):
            runner.run(operation)
        self.assertEqual(len(attempts), 1)


class CredentialCacheValidation(unittest.TestCase):
    """A credential must not be served once its lifetime has passed."""

    def test_expired_credential_is_not_served(self) -> None:
        now = [1000.0]
        cache = CredentialCache(ttl_ms=1000, clock=lambda: now[0])
        cache.put("drive.read", Credential(token="abc", scope="drive.read"))
        now[0] = 1000.0 + 5000
        self.assertIsNone(cache.get("drive.read"))


class MediaPlayerValidation(unittest.TestCase):
    """A decoder that refuses to start must leave the player stopped."""

    def test_refused_decoder_leaves_the_player_stopped(self) -> None:
        class RefusingDecoder:
            def start(self) -> None:
                raise DecoderError("the decoder is unavailable")

            def pause(self) -> None:
                raise AssertionError("pause must not be called")

            def stop(self) -> None:
                return None

        player = MediaPlayer(RefusingDecoder())
        try:
            started = player.play()
        except DecoderError:
            started = False
        self.assertFalse(started)
        self.assertFalse(player.is_playing)
        self.assertIs(player.state, PlaybackState.STOPPED)


if __name__ == "__main__":
    unittest.main()
