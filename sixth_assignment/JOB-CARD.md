# Job card

**What it does:** Classifies a support message so it lands on the right team.

**Input:**
`{ "text": "string, 1-2000 characters" }`

**Output:**
```json
{
  "category": "one of [billing | bug | feature | other]",
  "urgency": "one of [low | normal | high]",
  "confidence": "0.0-1.0",
  "reason": "one short sentence"
}