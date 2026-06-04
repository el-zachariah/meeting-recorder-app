import pytest

from meeting_recorder.obsidian import export_meeting_to_obsidian
from meeting_recorder.organizer import organize_recording


def test_export_obsidian_rejects_folder_path_traversal(tmp_path):
    raw = tmp_path / "raw.mkv"
    raw.write_bytes(b"media")
    meeting = organize_recording(raw, tmp_path / "Meetings", "Demo")

    with pytest.raises(ValueError, match="inside the vault"):
        export_meeting_to_obsidian(meeting, tmp_path / "Vault", folder="../outside")


def test_export_obsidian_rejects_absolute_folder(tmp_path):
    raw = tmp_path / "raw.mkv"
    raw.write_bytes(b"media")
    meeting = organize_recording(raw, tmp_path / "Meetings", "Demo")

    with pytest.raises(ValueError, match="inside the vault"):
        export_meeting_to_obsidian(meeting, tmp_path / "Vault", folder=str(tmp_path / "outside"))
