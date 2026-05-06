# Volcengine API Notes

## Voice Status

Check a cloned voice:

- Endpoint: `https://openspeech.bytedance.com/api/v3/tts/get_voice`
- Headers:
  - `Content-Type: application/json`
  - `X-Api-Key: <api key>`
  - `X-Api-Request-Id: <uuid>`
- Body:

```json
{"speaker_id": "S_..."}
```

Usable statuses:

- `2`: Success
- `4`: Active

Use a real `speaker_id` from the user's Volcengine console. The skill does not assume a fixed voice.

## Synthesis

Use:

- Endpoint: `https://openspeech.bytedance.com/api/v3/tts/unidirectional`
- Header `X-Api-Resource-Id: seed-icl-2.0`
- Body field `req_params.speaker: S_...`

Minimal body shape:

```json
{
  "user": {"uid": "codex-narration"},
  "namespace": "BidirectionalTTS",
  "req_params": {
    "text": "<cot text=平静真诚>要朗读的文本。</cot>",
    "speaker": "S_yourSpeakerId",
    "model": "seed-tts-2.0-expressive",
    "audio_params": {
      "format": "mp3",
      "sample_rate": 24000,
      "bit_rate": 128000,
      "speech_rate": -2
    },
    "additions": "{\"disable_default_bit_rate\": true, \"use_tag_parser\": true}"
  }
}
```

Important: `req_params.additions` must be a JSON string, not an object.

## Common Errors

- `resource ID is mismatched with speaker related resource`: the `speaker_id` is not owned by or not bound to the current resource/account. Use a real speaker ID from the Volcengine console.
- `json: cannot unmarshal object into Go struct field ... additions of type string`: encode `additions` with `json.dumps(...)`.
- Empty audio with success-like code: inspect returned chunks for non-`3000` codes and retry that segment.
