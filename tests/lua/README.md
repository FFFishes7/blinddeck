# Lua integration tests

Requires Balatro installed; pytest starts instances on ports from `BALATROBOT_PORTS`.

```bash
pytest tests/lua/endpoints/test_health.py -v
pytest -n 6 tests/lua   # parallel (not with estimate_live — OOM risk)
```

## Fixed seeds for scenario live tests

Tests that need a specific blind tag or multi-blind layout **must not** loop random seeds. Workflow:

1. **Find** — `python scripts/find_<scenario>_seed.py` from repo root (starts Balatro, scans `S00000`…).
2. **Commit** — add the constant to [`tag_seeds.py`](tag_seeds.py).
3. **Use** — import in the test; assert tags at start so version drift fails loudly.

| Script                          | Constant           |
| ------------------------------- | ------------------ |
| `scripts/find_charm_seed.py`    | `CHARM_SMALL`      |
| `scripts/find_foil_seed.py`     | `FOIL_SMALL`       |
| `scripts/find_economy_seed.py`  | `ECONOMY_SMALL`    |
| `scripts/find_boss_seed.py`     | `BOSS_SMALL`       |
| `scripts/find_tag_pair_seed.py` | `DOUBLE_THEN_FOIL` |

Example consumer: [`endpoints/test_skip_pack_tag.py`](endpoints/test_skip_pack_tag.py).

New scenario → new `scripts/find_*_seed.py`, not env-var hacks on an existing finder.

Full contributor notes: [`docs/contributing.md`](../../docs/contributing.md).
