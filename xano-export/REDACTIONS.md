# Redactions in this dump

The dump is otherwise a byte-faithful copy of the XanoScript. One value was
removed before the first commit, because committing it would write a live
credential into git history permanently.

| File | What | Where the real value lives |
|---|---|---|
| `apigroup/4_scripters/62_checkout.xs` | Klaviyo private API key, hardcoded in the stack | the Xano `checkout` stack; copy it into `KLAVIYO_API_KEY` in `.env`, never into source |

Re-running `scripts/dump_xano.py` will bring the real value back. Re-run the
redaction before committing, or add the file to `.gitignore`.

**This key should be rotated.** It has been sitting in plain text inside the
Xano stack, and anyone with Metadata API read access can retrieve it.
