# Demo conversations

The challenge asks for **3 to 5 varied conversations**, including one non-trivial scenario.

**Do not treat this file as a real conversation.** The examples must come from actually running the agent against a configured API.

Run from the project root:

```bash
python test_atendimento.py | tee exemplos/conversas_reais.md
```

Then open `exemplos/conversas_reais.md` and confirm the responses genuinely consulted the tools. Fix any failure before submitting.

Extra suggestions for the CLI:
- Order without an email: `Qual o status do pedido 2?` (should ask for verification)
- Out-of-stock product: ask for an unavailable item, confirming it is not offered as available
- Promotion: ask about its validity (there are no start/end dates in the CSV)

Avoid committing real personal data or credentials to Git.
