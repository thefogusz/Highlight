import json
import subprocess

import pytest

from highlight_mcp.core import Settings, Failure
from highlight_mcp.pipeline import choose_candidates, render_clip, validate_proposal
from highlight_mcp.pipeline import validate_source_duration, discovery_windows
from highlight_mcp.pipeline import selection_ranges


def test_timestamp_scope_filters_early_clips_and_validates_end():
    focus = selection_ranges({'start_seconds': 574, 'focus_ranges': []}, 1187)
    selected = choose_candidates([{'start_seconds': 550, 'end_seconds': 590}, {'start_seconds': 574, 'end_seconds': 620}], [], 1187, 30, 60, 8, focus)
    assert selected == [{'start_seconds': 574, 'end_seconds': 620, 'replay_score': None}]
    with pytest.raises(Failure):
        selection_ranges({'start_seconds': 1187, 'focus_ranges': []}, 1187)
    with pytest.raises(Failure):
        selection_ranges({'start_seconds': 574, 'focus_ranges': [{'start_seconds': 0, 'end_seconds': 60}]}, 1187)


def test_actual_long_episode_is_supported():
    validate_source_duration(8292, False)


@pytest.mark.parametrize('duration,live', [(21601, False), (8292, True), (0, False)])
def test_source_limits_remain_bounded(duration, live):
    with pytest.raises(Failure):
        validate_source_duration(duration, live)


@pytest.mark.parametrize('duration,target', [(8292, 8), (21600, 8), (21600, 20)])
def test_long_episode_windows_cover_source_within_call_budget(duration, target):
    windows = discovery_windows(duration, target)
    assert windows[0][0] == 0 and windows[-1][1] == duration
    assert all(b[0] <= a[1] for a, b in zip(windows, windows[1:]))
    assert len(windows) + target + 1 <= 30


def test_missing_heatmap_does_not_invent_replay_score():
    proposals = [{"start_seconds": 10, "end_seconds": 50, "categories": ["funny"], "reason_th": "test"}]
    selected = choose_candidates(proposals, [], 100, 30, 60, 8, [])
    assert selected[0]["replay_score"] is None


def test_candidate_dedup_and_focus():
    proposals = [{"start_seconds": 10, "end_seconds": 50}, {"start_seconds": 12, "end_seconds": 48}, {"start_seconds": 70, "end_seconds": 110}]
    selected = choose_candidates(proposals, [], 120, 20, 60, 8, [{"start_seconds": 0, "end_seconds": 60}])
    assert len(selected) == 1


def test_provider_range_is_grounded():
    with pytest.raises(Failure):
        validate_proposal({"start_seconds": 0, "end_seconds": 90}, 60)


def test_long_cached_clip_cannot_render(tmp_path):
    with pytest.raises(Failure, match='60 seconds'):
        render_clip(Settings(tmp_path), tmp_path / 'unused.mp4', tmp_path / 'out.mp4', 0, 61, '16:9', lambda: None)


def test_old_options_cannot_select_long_highlight():
    assert choose_candidates([{'start_seconds': 0, 'end_seconds': 90}], [], 120, 5, 120, 8, []) == []


def test_real_media_render(tmp_path):
    settings = Settings(tmp_path)
    ffmpeg = settings.binary("ffmpeg")
    assert ffmpeg and settings.binary("ffprobe"), "Install FFmpeg before running media integration tests"
    source = tmp_path / "source.mp4"
    subprocess.run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=25", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "4", "-c:v", "libx264", "-c:a", "aac", str(source)], check=True)
    output = tmp_path / "clip.mp4"
    render_clip(settings, source, output, 1, 3, "16:9", lambda: None)
    probe = subprocess.run([settings.binary("ffprobe"), "-v", "error", "-show_format", "-show_streams", "-of", "json", str(output)], capture_output=True, check=True)
    info = json.loads(probe.stdout)
    assert abs(float(info["format"]["duration"]) - 2) < 0.12
    assert {s["codec_type"] for s in info["streams"]} >= {"audio", "video"}
