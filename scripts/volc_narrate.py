#!/usr/bin/env python3
"""Synthesize segmented narration with Volcengine seed-icl-2.0."""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
DEFAULT_RESOURCE_ID = "seed-icl-2.0"
DEFAULT_MODEL = "seed-tts-2.0-expressive"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--segments", required=True, help="JSON array of {cue,text} objects")
    parser.add_argument("--output", required=True, help="Final MP3 output path")
    parser.add_argument("--speaker", required=True, help="Volcengine speaker_id, e.g. S_...")
    parser.add_argument("--api-key", default=os.environ.get("VOLCENGINE_API_KEY") or os.environ.get("VOLC_API_KEY"))
    parser.add_argument("--resource-id", default=DEFAULT_RESOURCE_ID)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--speech-rate", type=int, default=-2, help="Volcengine speech_rate [-50,100]")
    parser.add_argument("--sample-rate", type=int, default=24000)
    parser.add_argument("--bit-rate", type=int, default=128000)
    parser.add_argument("--work-dir", help="Directory for segment MP3s; defaults next to output")
    parser.add_argument("--resume", action="store_true", help="Reuse existing segment files")
    parser.add_argument("--retries", type=int, default=3)
    return parser.parse_args()


def load_segments(path: Path) -> list[dict[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("segments JSON must be a non-empty array")
    segments: list[dict[str, str]] = []
    for index, item in enumerate(data, 1):
        if not isinstance(item, dict):
            raise ValueError(f"segment {index} must be an object")
        cue = str(item.get("cue", "")).strip()
        text = str(item.get("text", "")).strip()
        if not text:
            raise ValueError(f"segment {index} missing text")
        segments.append({"cue": cue or "自然、清晰、真诚", "text": text})
    return segments


def synthesize_segment(
    *,
    api_key: str,
    resource_id: str,
    model: str,
    speaker: str,
    cue: str,
    text: str,
    speech_rate: int,
    sample_rate: int,
    bit_rate: int,
) -> bytes:
    tagged_text = f"<cot text={cue}>{text}</cot>"
    payload = {
        "user": {"uid": "codex-narration"},
        "namespace": "BidirectionalTTS",
        "req_params": {
            "text": tagged_text,
            "speaker": speaker,
            "model": model,
            "audio_params": {
                "format": "mp3",
                "sample_rate": sample_rate,
                "bit_rate": bit_rate,
                "speech_rate": speech_rate,
            },
            "additions": json.dumps(
                {
                    "disable_default_bit_rate": True,
                    "use_tag_parser": True,
                },
                ensure_ascii=False,
            ),
        },
    }
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": api_key,
        "X-Api-Resource-Id": resource_id,
        "X-Api-Request-Id": str(uuid.uuid4()),
    }
    request = Request(
        API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    audio = bytearray()
    errors: list[str] = []
    try:
        with urlopen(request, timeout=120) as response:
            logid = response.headers.get("X-Tt-Logid", "")
            for line in response:
                if not line.strip():
                    continue
                obj = json.loads(line.decode("utf-8", "replace"))
                code = obj.get("code")
                if code not in (None, 0, 3000, 20000000):
                    errors.append(json.dumps(obj, ensure_ascii=False))
                data = obj.get("data") or obj.get("audio")
                if data:
                    audio.extend(base64.b64decode(data))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {exc.code}: {body[:1000]}") from exc
    except URLError as exc:
        raise RuntimeError(f"network error: {exc}") from exc

    if errors:
        raise RuntimeError(f"TTS returned errors: {errors[:2]}")
    if not audio:
        raise RuntimeError(f"TTS returned no audio; logid={logid}")
    return bytes(audio)


def concat_mp3(segment_paths: list[Path], output: Path, concat_file: Path) -> None:
    concat_file.write_text(
        "".join(f"file '{path.as_posix()}'\n" for path in segment_paths),
        encoding="utf-8",
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-c",
        "copy",
        str(output),
    ]
    subprocess.run(cmd, check=True)


def main() -> int:
    args = parse_args()
    if not args.api_key:
        print("ERROR: set VOLCENGINE_API_KEY or pass --api-key", file=sys.stderr)
        return 2

    segments_path = Path(args.segments).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    work_dir = Path(args.work_dir).expanduser().resolve() if args.work_dir else output.with_suffix("")
    work_dir.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)

    segments = load_segments(segments_path)
    segment_paths: list[Path] = []
    manifest: list[dict[str, object]] = []

    for index, segment in enumerate(segments, 1):
        segment_path = work_dir / f"seg{index:03d}.mp3"
        if args.resume and segment_path.exists() and segment_path.stat().st_size > 0:
            print(f"SKIP {index:03d}/{len(segments)} {segment_path}")
        else:
            last_error: Exception | None = None
            for attempt in range(1, args.retries + 1):
                try:
                    audio = synthesize_segment(
                        api_key=args.api_key,
                        resource_id=args.resource_id,
                        model=args.model,
                        speaker=args.speaker,
                        cue=segment["cue"],
                        text=segment["text"],
                        speech_rate=args.speech_rate,
                        sample_rate=args.sample_rate,
                        bit_rate=args.bit_rate,
                    )
                    segment_path.write_bytes(audio)
                    print(f"OK {index:03d}/{len(segments)} {len(audio)} bytes")
                    last_error = None
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    print(f"RETRY {index:03d} attempt {attempt}: {exc}", file=sys.stderr)
                    if attempt < args.retries:
                        time.sleep(1.5 * attempt)
            if last_error is not None:
                raise last_error

        segment_paths.append(segment_path)
        manifest.append(
            {
                "id": index,
                "cue": segment["cue"],
                "text": segment["text"],
                "file": str(segment_path),
            }
        )

    (work_dir / "segments.manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    concat_mp3(segment_paths, output, work_dir / "concat.txt")
    print(f"DONE {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
