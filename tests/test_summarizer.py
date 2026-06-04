import pytest

from meeting_recorder.summarizer import SummaryConfigurationError, summarize_transcript


def test_local_summary_extracts_key_points_and_actions(tmp_path):
    transcript = tmp_path / "transcript.txt"
    transcript.write_text(
        "[0.0-1.0] We discussed the launch plan and customer onboarding timeline. "
        "The launch plan needs documentation and QA review. "
        "Alex will follow up with the design team tomorrow. "
        "We should finalize customer onboarding metrics before Friday.\n",
        encoding="utf-8",
    )
    out = tmp_path / "summary.md"
    summary = summarize_transcript(transcript, out)
    assert summary.startswith("# Summary")
    assert "Key points" in summary
    assert "Alex will follow up" in summary
    assert "launch" in summary.lower()
    assert out.read_text(encoding="utf-8") == summary


def test_summary_handles_empty_transcript(tmp_path):
    transcript = tmp_path / "transcript.txt"
    transcript.write_text("# Transcript unavailable\nNo supported local Whisper", encoding="utf-8")
    out = tmp_path / "summary.md"
    summary = summarize_transcript(transcript, out)
    assert "No transcript content" in summary


def test_summary_handles_failed_transcript(tmp_path):
    transcript = tmp_path / "transcript.txt"
    transcript.write_text("# Transcript failed\n\nError: model missing", encoding="utf-8")
    out = tmp_path / "summary.md"
    summary = summarize_transcript(transcript, out)
    assert "fix the transcription failure" in summary


def test_use_api_requires_env_vars(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    transcript = tmp_path / "transcript.txt"
    transcript.write_text("hello", encoding="utf-8")
    with pytest.raises(SummaryConfigurationError, match="OPENAI_API_KEY"):
        summarize_transcript(transcript, tmp_path / "summary.md", use_api=True)
