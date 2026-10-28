# PaperTrack

PaperTrack is a small reading and note taking application. This repository
holds the application modules and the public regression suite that covers
their documented behaviour.

## Domains

- `app/ui` – selection tracking, the highlight colour palette and the theme
  manager that switches between the light and the dark appearance.
- `app/net` – downloads of remote images and the in-memory image cache that
  keeps the most recently used payloads.
- `app/reader` – pagination of documents into fixed size pages and the
  reading anchors that remember the last position of a document.
- `app/sync` – the queue of pending synchronisation jobs and the retry policy
  used when the server reports a transient failure.
- `app/auth` – the cache of issued credentials and the helpers that decode
  and refresh access tokens.
- `app/media` – playback control of a single track and the ordering rules of
  the playlist.

## Conventions

The public helpers are plain classes and functions with type hints and short
docstrings. Code that depends on the outside world accepts an injected
collaborator: the clock, the transport, the sleep function or the decoder.
The test suite therefore never touches the network and never waits.

## Tests

Run the public regression suite from the repository root with:

    python -m unittest discover -s tests
