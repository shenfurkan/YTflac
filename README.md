# YtFLAC

Get YouTube Music & Spotify tracks in true lossless FLAC from Tidal, Qobuz, Deezer & Amazon Music — no account required.

> Fork of [spotbye/SpotiFLAC](https://github.com/spotbye/SpotiFLAC)

---

## Features

- **YouTube Music support** — paste any YouTube Music URL (track, album, OLAK playlist)
- **Spotify support** — tracks, albums, playlists
- **Multi-service fallback** — Tidal → Qobuz → Deezer → Amazon Music
- **Desktop GUI** — dark minimalist PyQt6 interface
- **Settings dialog** — service priority, output folder, metadata, lyrics
- **Lyrics embedding** — synced lyrics from Spotify, Musixmatch, Apple, LRCLib
- **Metadata enrichment** — BPM, genre, label, cover art from multiple sources
- **MusicBrainz tagging** — automatic professional-grade tags
- **FLAC validation** — detects previews and corrupt downloads

---

## Installation

```bash
git clone https://github.com/shenfurkan/YTflac.git
cd YTflac
pip install -e .
```

---

## Usage

```bash
python -m ytflac
```

That's it. The GUI will open.

---

## Supported URLs

| Source | Example |
|---|---|
| Spotify track | `https://open.spotify.com/track/...` |
| Spotify album | `https://open.spotify.com/album/...` |
| Spotify playlist | `https://open.spotify.com/playlist/...` |
| YouTube Music track | `https://music.youtube.com/watch?v=...` |
| YouTube Music album | `https://music.youtube.com/playlist?list=OLAK5uy_...` |
| YouTube Music playlist | `https://music.youtube.com/playlist?list=...` |

---

## How It Works

1. Paste a YouTube Music or Spotify URL
2. YtFLAC resolves track metadata via Spotify catalogue
3. Downloads lossless audio from Tidal, Qobuz, Deezer, or Amazon
4. Embeds full metadata, cover art, and lyrics into FLAC files

YouTube Music URLs are **not** downloaded from YouTube — they are cross-referenced with Spotify to find proper lossless sources.

---

## Requirements

- Python 3.9+
- PyQt6 (for GUI)
- ffprobe (for validation, optional)

---

## Configuration

All settings are managed through the GUI Settings dialog:

- **Services** — drag to reorder, toggle to enable/disable
- **Files** — output folder, filename template, subfolder structure
- **Metadata** — enrichment providers
- **Lyrics** — provider priority, Spotify token
- **Advanced** — quality, format options

Settings are persisted automatically.

---

## Credits

Based on [SpotiFLAC](https://github.com/spotbye/SpotiFLAC) by spotbye.

Additional credits: [Song.link](https://song.link) · [MusicBrainz](https://musicbrainz.org) · [hifi-api](https://github.com/binimum/hifi-api)

---

## License

MIT