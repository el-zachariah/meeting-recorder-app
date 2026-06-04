from __future__ import annotations

from collections import Counter
from pathlib import Path
import os
import re
import json
import urllib.request

SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]{2,}")
STOPWORDS = set("""
a an and are as at be by for from has have i in is it its of on or that the this to was were will with you your we our they them their but not can if then so about into after before over under just very
""".split())


class SummaryConfigurationError(RuntimeError):
    pass


def summarize_transcript(transcript_path: Path, output_path: Path, max_sentences: int = 6, use_api: bool = False) -> str:
    transcript_path = Path(transcript_path)
    output_path = Path(output_path)
    text = transcript_path.read_text(encoding="utf-8") if transcript_path.exists() else ""
    if use_api and (not os.environ.get("OPENAI_API_KEY") or not os.environ.get("OPENAI_BASE_URL")):
        raise SummaryConfigurationError("--use-api requires OPENAI_API_KEY and OPENAI_BASE_URL to be set")
    if use_api:
        summary = _summarize_openai_compatible(text)
    else:
        summary = _local_extractive_summary(text, max_sentences=max_sentences)
    output_path.write_text(summary, encoding="utf-8")
    return summary


def _clean_transcript(text: str) -> str:
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.lower().startswith("language:"):
            continue
        line = re.sub(r"^\[[^\]]+\]\s*", "", line)
        lines.append(line)
    return " ".join(lines)


def _local_extractive_summary(text: str, max_sentences: int = 6) -> str:
    clean = _clean_transcript(text)
    if not clean.strip() or "No supported local Whisper" in text or text.lstrip().startswith("# Transcript failed"):
        return "# Summary\n\nNo transcript content is available yet. Record/transcribe a meeting first, or fix the transcription failure noted in transcript.txt, then generate a summary.\n"
    sentences = [s.strip() for s in SENTENCE_RE.split(clean) if len(s.strip()) > 20]
    if not sentences:
        sentences = [clean.strip()]
    words = [w.lower() for w in WORD_RE.findall(clean) if w.lower() not in STOPWORDS]
    freqs = Counter(words)
    scored = []
    for idx, sentence in enumerate(sentences):
        score = sum(freqs.get(w.lower(), 0) for w in WORD_RE.findall(sentence)) / max(1, len(sentence.split()))
        scored.append((score, idx, sentence))
    chosen = sorted(scored, reverse=True)[:max_sentences]
    chosen = [s for _, _, s in sorted(chosen, key=lambda item: item[1])]
    keywords = ", ".join([w for w, _ in freqs.most_common(10)]) or "n/a"
    actions = [s for s in sentences if re.search(r"\b(todo|action|follow up|follow-up|need to|should|must|will)\b", s, re.I)]
    action_lines = "\n".join(f"- {a}" for a in actions[:8]) or "- No explicit action items detected."
    bullets = "\n".join(f"- {s}" for s in chosen)
    return f"# Summary\n\n## Key points\n{bullets}\n\n## Possible action items\n{action_lines}\n\n## Keywords\n{keywords}\n"


def _summarize_openai_compatible(text: str) -> str:
    """Optional API path. Only used when caller opts in and env vars are set."""
    base = os.environ["OPENAI_BASE_URL"].rstrip("/")
    key = os.environ["OPENAI_API_KEY"]
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Summarize meeting transcripts into key points, decisions, and action items."},
            {"role": "user", "content": text[:60000]},
        ],
        "temperature": 0.2,
    }
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 - explicit user opt-in endpoint
        data = json.loads(resp.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"].strip()
    return "# Summary\n\n" + content + "\n"
