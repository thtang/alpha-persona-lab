# Zhezhe Distillation Schema

Per-source notes should be JSON objects. Use Traditional Chinese in prose fields and preserve English enum values.

```json
{
  "schema_version": "v1",
  "source_id": "zhezhe-YYYY-MM-DD-xxxx",
  "source_type": "podcast_transcript | podcast_metadata | article",
  "date": "YYYY-MM-DD",
  "title": "",
  "source_url": "",
  "market_regime": {
    "phase_label": "",
    "narrative": "",
    "regime_tags": []
  },
  "headline_call": {
    "direction": "bullish | bearish | mixed | risk_control | unknown",
    "horizon": "intraday | swing | monthly | multi_month | long_term | unstated",
    "claim": "",
    "trigger": "",
    "invalidation": "",
    "confidence": "low | medium | high"
  },
  "asset_views": [
    {
      "asset_or_sector": "",
      "asset_symbol": "",
      "asset_type": "stock | index | etf | sector | commodity | fx | rate | unknown",
      "view": "bullish | bearish | neutral | conditional | avoid | unknown",
      "horizon": "intraday | swing | monthly | multi_month | long_term | unstated",
      "reasoning": "",
      "catalysts": [],
      "risk_flags": [],
      "evidence": ""
    }
  ],
  "risk_control": [
    {
      "rule": "",
      "condition": "",
      "action": "buy | add | hold | trim | sell | wait | hedge | reduce_leverage",
      "evidence": ""
    }
  ],
  "rhetorical_patterns": [
    {
      "pattern": "",
      "function": "urgency | reassurance | fear_control | authority | social_proof | contrast | humor | other",
      "evidence": ""
    }
  ],
  "market_followups": [
    {
      "question": "",
      "data_to_check": "",
      "deadline_or_horizon": ""
    }
  ],
  "source_quality": {
    "has_full_transcript": false,
    "asr_model": "",
    "asr_confidence": "unknown | low | medium | high",
    "article_full_text_available": false,
    "notes": ""
  },
  "open_questions": []
}
```

Rules:

- Prefer article/transcript body over title metadata.
- Keep evidence excerpts short; summarize rather than copy.
- Mark podcast metadata-only extraction as low confidence unless the title is the claim being analyzed.
- Keep contradictions and stance changes; do not smooth them away.
