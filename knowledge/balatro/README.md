# Balatro Knowledge Library

This directory contains the local, machine-readable Balatro knowledge used by the play helpers.

## Files

- `balatro-*-verified.json`: generated verified lookup tables used by `tools/play/know.py`.
- `balatro-rules-verified.json`: hand-curated universal mechanics rules with source references. Prefer this for scoring/order/capacity rules that are not tied to one card name.
- `balatro-*-overrides.json`: hand-written factual notes and corrections merged into generated data.
- `build_knowledge.py`: regenerates the verified JSON files from `docs/api.md` plus overrides.

## Regenerate

From the repository root:

```powershell
.\.venv\Scripts\python.exe knowledge\balatro\build_knowledge.py
```

The play helper defaults to this directory, but it can be overridden with `BALATROBOT_KNOWLEDGE_DIR`.

## Rule Sources

The generic rule file should stay source-backed. Prefer primary evidence from the installed game Lua bundled in `Balatro.exe` for exact mechanics, and use public references such as Wikipedia or Balatro wiki pages only for high-level category checks or player-facing wording.
