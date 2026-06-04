from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess
import tempfile


class TranscriptionUnavailable(RuntimeError):
    pass


def engine_status() -> dict[str, str | None]:
    return {
        "faster_whisper_python": _has_faster_whisper(),
        "whisper_cpp": shutil.which("whisper-cli") or shutil.which("main") or shutil.which("whisper.cpp"),
        "openai_whisper_cli": shutil.which("whisper"),
        "ffmpeg": shutil.which("ffmpeg"),
    }


def _has_faster_whisper() -> str | None:
    try:
        import faster_whisper  # type: ignore  # noqa: F401
    except Exception:
        return None
    return "installed"


def extract_audio(media_path: Path, wav_path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise TranscriptionUnavailable("ffmpeg is required to extract audio for transcription")
    cmd = [ffmpeg, "-y", "-i", str(media_path), "-vn", "-ac", "1", "-ar", "16000", str(wav_path)]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def transcribe(media_path: Path, output_path: Path, model: str = "base") -> str:
    """Transcribe with installed local engines only. Returns transcript text or fallback instructions."""
    media_path = Path(media_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if _has_faster_whisper():
        text = _transcribe_faster_whisper(media_path, model)
        output_path.write_text(text, encoding="utf-8")
        return text

    whisper_cpp = shutil.which("whisper-cli") or shutil.which("main") or shutil.which("whisper.cpp")
    if whisper_cpp:
        text = _transcribe_whisper_cpp(whisper_cpp, media_path)
        output_path.write_text(text, encoding="utf-8")
        return text

    whisper_cli = shutil.which("whisper")
    if whisper_cli:
        text = _transcribe_openai_whisper_cli(whisper_cli, media_path, model)
        output_path.write_text(text, encoding="utf-8")
        return text

    msg = fallback_message(media_path)
    output_path.write_text(msg, encoding="utf-8")
    return msg


def _transcribe_faster_whisper(media_path: Path, model: str) -> str:
    from faster_whisper import WhisperModel  # type: ignore

    device = "cpu"
    compute_type = "int8"
    local_files_only = os.environ.get("MEETING_RECORDER_OFFLINE", "").lower() in {"1", "true", "yes"}
    whisper_model = WhisperModel(model, device=device, compute_type=compute_type, local_files_only=local_files_only)
    segments, info = whisper_model.transcribe(str(media_path), vad_filter=True)
    lines = [f"# Transcript\n", f"Language: {getattr(info, 'language', 'unknown')}\n"]
    for seg in segments:
        lines.append(f"[{seg.start:0.1f}-{seg.end:0.1f}] {seg.text.strip()}")
    return "\n".join(lines).strip() + "\n"


def _transcribe_whisper_cpp(binary: str, media_path: Path) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "audio.wav"
        extract_audio(media_path, wav)
        result = subprocess.run([binary, "-f", str(wav), "-nt"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            raise TranscriptionUnavailable(result.stderr.strip() or "whisper.cpp failed")
        return result.stdout.strip() + "\n"


def _transcribe_openai_whisper_cli(binary: str, media_path: Path, model: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            [binary, str(media_path), "--model", model, "--output_dir", tmp, "--output_format", "txt"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            raise TranscriptionUnavailable(result.stderr.strip() or "whisper CLI failed")
        txts = sorted(Path(tmp).glob("*.txt"))
        if not txts:
            raise TranscriptionUnavailable("whisper CLI did not produce a .txt file")
        return txts[0].read_text(encoding="utf-8").strip() + "\n"


def fallback_message(media_path: Path) -> str:
    return f"""# Transcript unavailable

No supported local Whisper-compatible transcription engine was found.

Recording saved at: {media_path}

Install one of these local options, then rerun transcription:

1. faster-whisper in a virtual environment. Note: using a model name such as "base"
   may download model files from Hugging Face the first time. For fully offline use,
   download/verify the model yourself, pass its local path with --model, and set
   MEETING_RECORDER_OFFLINE=1.
   uv venv && uv pip install faster-whisper
   ./meeting-recorder transcribe --media "{media_path}"

2. whisper.cpp:
   Install/build whisper.cpp and ensure whisper-cli is on PATH, with a model configured per whisper.cpp docs.
   ./meeting-recorder transcribe --media "{media_path}"

3. OpenAI Whisper CLI locally:
   uv pip install openai-whisper
   ./meeting-recorder transcribe --media "{media_path}"

This app does not upload recordings or transcripts by default.
"""
