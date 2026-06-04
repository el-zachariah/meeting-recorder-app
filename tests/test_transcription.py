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


def test_transcription_engine_failure_writes_report(tmp_path, monkeypatch):
    monkeypatch.setattr("meeting_recorder.transcription._has_faster_whisper", lambda: "installed")
    monkeypatch.setattr(
        "meeting_recorder.transcription._transcribe_faster_whisper",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("model missing")),
    )
    media = tmp_path / "recording.mkv"
    media.write_bytes(b"fake")
    out = tmp_path / "transcript.txt"

    text = transcribe(media, out)

    assert text.startswith("# Transcript failed")
    assert "model missing" in text
    assert "faster-whisper" in text
    assert out.read_text() == text
