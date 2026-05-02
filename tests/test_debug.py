"""
Debug test suite for YtFLAC engine.
Tests unused debug functions and modules.
"""
import sys
import time
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ytflac.core.progress import DownloadManager, ProgressCallback
from ytflac.core.console import print_track_header, print_source_banner, print_summary
from ytflac.core.provider_stats import ProviderScorer, record_success, record_failure, prioritize
from ytflac.core.history import HistoryManager
from ytflac.core.isrc_cache import get_cached_isrc, put_cached_isrc
from ytflac.core.musicbrainz import set_mb_status, should_skip_mb, fetch_mb_metadata


def test_progress_manager():
    """Test the singleton DownloadManager."""
    print("\n=== Testing DownloadManager ===")
    
    # Get singleton instance
    manager = DownloadManager()
    
    # Add items to queue
    manager.add_to_queue("track1", "Song 1", "Artist 1", "Album 1", "spotify1")
    manager.add_to_queue("track2", "Song 2", "Artist 2", "Album 2", "spotify2")
    
    # Start download
    manager.start_download("track1")
    
    # Update progress
    manager.update_progress("track1", 5.0, 2.5)
    
    # Complete download
    manager.complete_download("track1", "/path/to/file1.flac", 10.0)
    
    # Fail download
    manager.fail_download("track2", "Network error")
    
    # Get stats
    stats = manager.get_stats()
    print(f"Stats: {json.dumps(stats, indent=2, default=str)}")
    
    assert stats['queued'] == 0
    assert stats['completed'] == 1
    assert stats['failed'] == 1
    
    print("✓ DownloadManager test passed")


def test_progress_callback():
    """Test ProgressCallback with throttling."""
    print("\n=== Testing ProgressCallback ===")
    
    callback = ProgressCallback("test_item")
    
    # Simulate download progress
    total_bytes = 10 * 1024 * 1024  # 10 MB
    
    for i in range(0, 11):
        current_bytes = int(total_bytes * i / 10)
        callback(current_bytes, total_bytes)
        time.sleep(0.1)  # Small delay to test throttling
    
    print("✓ ProgressCallback test passed")


def test_console_output():
    """Test console output functions."""
    print("\n=== Testing Console Output ===")
    
    print_track_header(1, 5, "Test Song", "Test Artist", "Test Album")
    print_source_banner("tidal", "https://api.tidal.com", "HI_RES")
    print_summary(5, 4, [("Song 1", "Artist 1", "Error 1")], 120.5)
    
    print("✓ Console output test passed")


def test_provider_stats():
    """Test ProviderScorer."""
    print("\n=== Testing ProviderScorer ===")
    
    scorer = ProviderScorer()
    scorer.reset()
    
    # Record successes and failures
    record_success("tidal", "https://api1.tidal.com")
    record_success("tidal", "https://api1.tidal.com")
    record_failure("tidal", "https://api2.tidal.com")
    
    # Test prioritization
    apis = [
        "https://api1.tidal.com",
        "https://api2.tidal.com",
        "https://api3.tidal.com"
    ]
    prioritized = prioritize("tidal", apis)
    
    print(f"Original APIs: {apis}")
    print(f"Prioritized APIs: {prioritized}")
    
    # api1 should come first (more successes)
    assert prioritized[0] == "https://api1.tidal.com"
    assert prioritized[-1] == "https://api2.tidal.com"
    
    print("✓ ProviderScorer test passed")


def test_history_manager():
    """Test HistoryManager."""
    print("\n=== Testing HistoryManager ===")
    
    from ytflac.core.models import TrackMetadata
    
    history = HistoryManager()
    
    # Add download record using TrackMetadata
    test_metadata = TrackMetadata(
        id="spotify1",
        title="Song 1",
        artists="Artist 1",
        album="Album 1",
        album_artist="Artist 1",
        duration_s=180,
        isrc="TESTISRC123"
    )
    history.add(test_metadata)
    
    # Get recent downloads
    recent = history.get_all()
    print(f"Recent downloads: {len(recent)}")
    
    print("✓ HistoryManager test passed")


def test_isrc_cache():
    """Test ISRC cache."""
    print("\n=== Testing ISRC Cache ===")
    
    # Test get and put
    put_cached_isrc("TESTISRC123", "TESTISRC123456")
    cached = get_cached_isrc("TESTISRC123")
    
    print(f"Cached ISRC: {cached}")
    assert cached == "TESTISRC123456"
    
    print("✓ ISRC cache test passed")


def test_musicbrainz():
    """Test MusicBrainz integration (with offline mode)."""
    print("\n=== Testing MusicBrainz ===")
    
    # Set offline mode
    set_mb_status(False)
    
    # Check if we should skip MB
    skip = should_skip_mb()
    print(f"Should skip MB: {skip}")
    
    # Test fetch with a dummy ISRC (will fail but tests the function)
    try:
        result = fetch_mb_metadata("")
        print(f"Fetch result (empty ISRC): {result}")
    except Exception as e:
        print(f"Fetch failed as expected: {e}")
    
    print("✓ MusicBrainz test passed")


def run_all_tests():
    """Run all debug tests."""
    print("=" * 60)
    print("YtFLAC Debug Test Suite")
    print("=" * 60)
    
    tests = [
        test_progress_manager,
        test_progress_callback,
        test_console_output,
        test_provider_stats,
        test_history_manager,
        test_isrc_cache,
        test_musicbrainz,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__} failed: {e}")
            failed += 1
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
