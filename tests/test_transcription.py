from meeting_recorder.transcription import transcribe


def test_transcription_fallback_writes_instructions(tmp_path, monkeypatch):
    monkeypatch.setattr("meeting_recorder.transcription._has_faster_whisper", lambda: None)
    monkeypatch.setattr("meeting_recorder.transcription.shutil.which", lambda name: None)
    media = tmp_path / "recording.mkv"
    media.write_bytes(b"fake")
    out = tmp_path / "transcript.txt"
    text = transcribe(media, out)
    assert "Transcript unavailable" in text
    assert "faster-whisper" in text
    assert out.read_text() == text
