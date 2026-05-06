---
name: volcengine-cloned-voice-tts
description: Use when the user wants to turn Chinese markdown, articles, scripts, or long-form text into narrated audio using any cloned Volcengine/Doubao voice speaker_id. Supports rewriting text for oral delivery, planning per-segment tone with `<cot>` prompts, synthesizing with Volcengine `seed-icl-2.0`, and concatenating MP3 narration. Trigger phrases include 火山引擎配音, 声音复刻2.0, speaker_id, 用复刻音色念稿, 长文转口播, 情绪配音, and 生成口播音频.
version: 0.1.0
---

# Volcengine Cloned Voice TTS

Create narrated MP3 audio from text using a Volcengine cloned voice.

## Default Model

- TTS endpoint: `https://openspeech.bytedance.com/api/v3/tts/unidirectional`
- Resource model: `seed-icl-2.0`
- Speaker: require a Volcengine `speaker_id` from the user or current context, for example `S_...`.
- Voice cloning is completed by the user in the Volcengine console. This skill only uses an existing `speaker_id` for synthesis.

## Workflow

1. Rewrite the user text into natural oral Chinese.
   - Preserve meaning and structure.
   - Split long written sentences into shorter spoken sentences.
   - Remove markdown that should not be spoken.
   - Keep headings only if useful as spoken transitions.

2. Create `segments.json`.
   - Each segment should be short enough for stable synthesis, usually 1-3 spoken sentences.
   - Add a `cue` describing delivery style, not content summary.
   - Use `text` for the actual words to be spoken.

3. Synthesize with the bundled script:

```bash
export VOLCENGINE_API_KEY="..."
python3 /Users/links/.codex/skills/volcengine-cloned-voice-tts/scripts/volc_narrate.py \
  --segments /path/to/segments.json \
  --speaker S_yourSpeakerId \
  --output /tmp/narration.mp3
```

4. Return the final MP3 path and the `segments.json` path.

## Segment Format

```json
[
  {
    "cue": "平静开场，像认真分享一个最近想通的体会",
    "text": "这几年，我一直在实践复利人生这个想法。慢慢地，我发现，自己的心境，真的和过去不一样了。"
  }
]
```

## Tone Control

The script wraps each segment as:

```xml
<cot text=SEGMENT_CUE>SEGMENT_TEXT</cot>
```

and sends `use_tag_parser=true` to Volcengine. Prefer expressive Chinese cues such as:

- `平静开场，真诚`
- `稍微加重，带一点回忆感`
- `像课堂解释，节奏放慢`
- `引用名言，稳重`
- `关键提醒，加重`
- `结尾，温暖有希望`

For synthesis fields and failure handling, read [references/volcengine_api.md](references/volcengine_api.md).
