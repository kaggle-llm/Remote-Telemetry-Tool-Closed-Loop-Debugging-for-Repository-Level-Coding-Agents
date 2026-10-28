"""Public regression tests for the PaperTrack synthetic application."""

import base64
import json
import unittest

from app.auth.cache import Credential, CredentialCache
from app.auth.token import TokenParser, TokenRefresher
from app.media.playlist import Playlist, Track
from app.media.player import MediaPlayer, PlaybackState
from app.net.cache import ImageCache
from app.net.imageloader import ImageLoader, ImageRequest
from app.reader.anchor import AnchorStore, ReadingAnchor
from app.reader.pagination import Page, Paginator
from app.sync.queue import SyncJob, SyncQueue
from app.sync.retry import RetryPolicy, RetryRunner, SyncError, TransientSyncError
from app.ui.palette import HighlightPalette, PaletteColor, PresentationContext
from app.ui.selection import Selection, SelectionTracker
from app.ui.theme import DARK_THEME, LIGHT_THEME, ThemeManager


def make_token(payload: dict) -> str:
    """Build an unsigned token that carries ``payload``."""
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8"))
    return "header." + encoded.decode("ascii").rstrip("=") + ".signature"


TOKEN = make_token({"sub": "reader-1", "scopes": ["drive.read"], "exp": 1_000_000})


class RecordingFetcher:
    """Fetcher that records the timeouts it was called with."""

    def __init__(self, payload: bytes = b"image-bytes") -> None:
        self.payload = payload
        self.calls: list[tuple[str, int]] = []

    def fetch(self, url: str, timeout_ms: int) -> bytes:
        self.calls.append((url, timeout_ms))
        return self.payload


class StubDecoder:
    """Decoder that accepts every command."""

    def __init__(self) -> None:
        self.commands: list[str] = []

    def start(self) -> None:
        self.commands.append("start")

    def pause(self) -> None:
        self.commands.append("pause")

    def stop(self) -> None:
        self.commands.append("stop")


class UiTests(unittest.TestCase):
    def test_palette_opens_with_an_explicit_context(self) -> None:
        context = PresentationContext(view="ReaderView", session_id="s-1")
        palette = HighlightPalette(context)
        self.assertTrue(palette.open_palette(context))
        self.assertTrue(palette.is_open)
        self.assertEqual(palette.current_context, context)
        palette.close_palette()
        self.assertFalse(palette.is_open)

    def test_palette_exposes_its_colors(self) -> None:
        context = PresentationContext(view="ReaderView", session_id="s-1")
        palette = HighlightPalette(context, [PaletteColor(name="pink", hex_value="ff2d55")])
        self.assertEqual([color.name for color in palette.colors], ["pink"])

    def test_selection_length_and_overlap(self) -> None:
        selection = Selection(start=4, end=10)
        self.assertEqual(selection.length, 6)
        self.assertTrue(selection.overlaps(Selection(start=8, end=12)))
        self.assertFalse(selection.overlaps(Selection(start=10, end=14)))

    def test_selection_tracker_follows_the_active_range(self) -> None:
        tracker = SelectionTracker()
        tracker.begin(3)
        tracker.extend_to(9)
        self.assertEqual(tracker.current, Selection(start=3, end=9))
        tracker.clear()
        self.assertIsNone(tracker.current)

    def test_theme_manager_notifies_listeners(self) -> None:
        manager = ThemeManager(LIGHT_THEME)
        seen: list[ThemeManager] = []
        manager.on_change(seen.append)
        manager.switch(DARK_THEME)
        self.assertEqual(manager.active, DARK_THEME)
        self.assertEqual(len(seen), 1)


class NetTests(unittest.TestCase):
    def test_image_loader_uses_the_request_timeout(self) -> None:
        fetcher = RecordingFetcher()
        loader = ImageLoader(fetcher)
        payload = loader.load(ImageRequest(url="https://cdn.test/a.png", timeout_ms=500))
        self.assertEqual(payload, b"image-bytes")
        self.assertEqual(fetcher.calls, [("https://cdn.test/a.png", 500)])

    def test_image_loader_serves_cached_payloads(self) -> None:
        fetcher = RecordingFetcher()
        loader = ImageLoader(fetcher)
        request = ImageRequest(url="https://cdn.test/a.png", timeout_ms=500)
        loader.load(request)
        loader.load(request)
        self.assertEqual(len(fetcher.calls), 1)

    def test_image_loader_rejects_oversized_payloads(self) -> None:
        loader = ImageLoader(RecordingFetcher(b"0123456789"))
        request = ImageRequest(url="https://cdn.test/a.png", max_bytes=4, timeout_ms=500)
        with self.assertRaises(ValueError):
            loader.load(request)

    def test_image_cache_evicts_the_oldest_entry(self) -> None:
        cache = ImageCache(max_entries=2)
        cache.put("a", b"a")
        cache.put("b", b"b")
        cache.put("c", b"c")
        self.assertEqual(len(cache), 2)
        self.assertIsNone(cache.get("a"))
        self.assertEqual(cache.get("c"), b"c")


class ReaderTests(unittest.TestCase):
    def test_anchor_store_round_trip(self) -> None:
        store = AnchorStore()
        store.save("doc-1", ReadingAnchor(page=2, offset=40))
        self.assertEqual(store.load("doc-1"), ReadingAnchor(page=2, offset=40))

    def test_anchor_outside_the_document_is_rejected(self) -> None:
        store = AnchorStore()
        store.save("doc-1", ReadingAnchor(page=9, offset=0))
        self.assertIsNone(store.restore("doc-1", page_count=3))

    def test_anchor_inside_the_document_is_restored(self) -> None:
        store = AnchorStore()
        store.save("doc-1", ReadingAnchor(page=2, offset=7))
        self.assertEqual(store.restore("doc-1", page_count=3), ReadingAnchor(page=2, offset=7))

    def test_paginator_splits_text_into_pages(self) -> None:
        paginator = Paginator(page_size=4)
        self.assertEqual(paginator.page_count("abcdefgh"), 2)
        pages = paginator.pages("abcdefgh")
        self.assertEqual(pages[0], Page(index=0, start=0, end=4))
        self.assertEqual(pages[1].length, 4)
        self.assertIsNone(paginator.page_at("abcdefgh", 5))


class SyncTests(unittest.TestCase):
    def test_retry_succeeds_after_transient_failures(self) -> None:
        attempts: list[int] = []

        def operation() -> str:
            attempts.append(1)
            if len(attempts) < 3:
                raise TransientSyncError("the server is busy")
            return "saved"

        runner = RetryRunner(policy=RetryPolicy(attempts=3, base_delay_ms=1), sleep=lambda _: None)
        self.assertEqual(runner.run(operation, idempotency_key="key-1"), "saved")
        self.assertEqual(len(attempts), 3)

    def test_retry_gives_up_after_the_last_attempt(self) -> None:
        attempts: list[int] = []

        def operation() -> str:
            attempts.append(1)
            raise TransientSyncError("the server is busy")

        runner = RetryRunner(policy=RetryPolicy(attempts=2, base_delay_ms=1), sleep=lambda _: None)
        with self.assertRaises(SyncError):
            runner.run(operation, idempotency_key="key-1")
        self.assertEqual(len(attempts), 2)

    def test_queue_keeps_the_jobs_in_order(self) -> None:
        queue = SyncQueue(max_jobs=2)
        self.assertTrue(queue.push(SyncJob(document_id="doc-1", kind="upsert")))
        self.assertTrue(queue.push(SyncJob(document_id="doc-2", kind="upsert")))
        self.assertFalse(queue.push(SyncJob(document_id="doc-3", kind="upsert")))
        self.assertEqual(len(queue.pending("upsert")), 2)
        job = queue.pop()
        self.assertEqual(job.document_id, "doc-1")
        self.assertEqual(job.attempts, 1)
        self.assertEqual(len(queue), 1)


class AuthTests(unittest.TestCase):
    def test_credential_cache_serves_a_fresh_entry(self) -> None:
        now = [0.0]
        cache = CredentialCache(ttl_ms=1000, clock=lambda: now[0])
        cache.put("drive.read", Credential(token="abc", scope="drive.read"))
        now[0] = 500.0
        credential = cache.get("drive.read")
        self.assertIsNotNone(credential)
        self.assertEqual(credential.token, "abc")

    def test_credential_cache_invalidation(self) -> None:
        cache = CredentialCache(ttl_ms=1000, clock=lambda: 0.0)
        cache.put("drive.read", Credential(token="abc", scope="drive.read"))
        cache.invalidate("drive.read")
        self.assertIsNone(cache.get("drive.read"))

    def test_token_parser_reads_the_claims(self) -> None:
        claims = TokenParser().parse(TOKEN)
        self.assertEqual(claims.subject, "reader-1")
        self.assertTrue(claims.allows("drive.read"))
        self.assertFalse(claims.allows("drive.write"))

    def test_token_refresher_detects_an_expiring_token(self) -> None:
        refresher = TokenRefresher(refresh_margin_s=60)
        self.assertTrue(refresher.needs_refresh(TOKEN, now=1_000_000))
        self.assertFalse(refresher.needs_refresh(TOKEN, now=10))


class MediaTests(unittest.TestCase):
    def test_player_plays_pauses_and_stops(self) -> None:
        player = MediaPlayer(StubDecoder())
        self.assertTrue(player.play())
        self.assertTrue(player.is_playing)
        player.pause()
        self.assertIs(player.state, PlaybackState.PAUSED)
        player.stop()
        self.assertIs(player.state, PlaybackState.STOPPED)
        self.assertFalse(player.is_playing)

    def test_playlist_keeps_the_order(self) -> None:
        playlist = Playlist([Track(track_id="a", title="A", duration_ms=1000)])
        playlist.add(Track(track_id="b", title="B", duration_ms=2000))
        self.assertEqual(playlist.current.track_id, "a")
        self.assertEqual(playlist.next().track_id, "b")
        self.assertEqual(playlist.total_duration_ms, 3000)
        self.assertTrue(playlist.move("b", 0))
        self.assertEqual(playlist.current.track_id, "b")


if __name__ == "__main__":
    unittest.main()
