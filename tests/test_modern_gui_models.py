from meeting_recorder.audio_monitor import WaveformLevels, pseudo_level
from meeting_recorder.gui import recording_button_text, stop_title_default, window_geometry_for_mini


def test_waveform_levels_ring_buffer_clamps_values():
    levels = WaveformLevels(size=4)
    for value in [-1, 0.25, 0.5, 2.0, 0.75]:
        levels.push(value)

    assert levels.values() == [0.25, 0.5, 1.0, 0.75]


def test_pseudo_level_is_deterministic_range():
    value = pseudo_level(1.25, 3)

    assert 0.0 <= value <= 1.0
    assert value == pseudo_level(1.25, 3)


def test_recording_button_text():
    assert recording_button_text(False, False) == "● Record"
    assert recording_button_text(True, False) == "■ Stop"
    assert recording_button_text(True, True) == "Saving…"


def test_window_geometry_for_mini():
    geometry = window_geometry_for_mini(screen_width=1920, screen_height=1080, width=360, height=170)

    assert geometry == "360x170+1536+24"


def test_stop_title_default_prefers_current_title():
    assert stop_title_default(" Team Sync ") == "Team Sync"
    assert stop_title_default("").startswith("Meeting ")
