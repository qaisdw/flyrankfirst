# Triage Support Endpoint

This API endpoint takes incoming customer support messages and uses an LLM to classify them so they land on the right internal team queue. It enforces a strict JSON schema, safely parses the output, and performs a single repair loop if the LLM hallucinates an invalid category.

### Try it out
```bash
curl -X POST http://127.0.0.1:8000/triage \
     -H "Content-Type: application/json" \
     -d '{"text": "I was double charged on my invoice!"}'