from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from ytflac.providers.youtube_input import parse_playlist_video_ids


def _build_playlist_html(count: int) -> str:
    parts = []
    for i in range(count):
        vid = f"{i:011d}"
        parts.append(f'"videoId":"{vid}"')
    return "".join(parts)


def test_parse_playlist_video_ids_no_default_cap() -> None:
    html = _build_playlist_html(209)
    video_ids = parse_playlist_video_ids(html)
    assert len(video_ids) == 209


if __name__ == "__main__":
    test_parse_playlist_video_ids_no_default_cap()
    print("ok")
