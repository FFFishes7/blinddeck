"""Known RED/WHITE seeds for live tag integration tests.

Workflow: find seed with scripts/find_*_seed.py, commit here, import in live tests.
See tests/lua/README.md and docs/contributing.md § Live test seeds.

Re-discover:

    python scripts/find_charm_seed.py      → CHARM_SMALL
    python scripts/find_foil_seed.py       → FOIL_SMALL
    python scripts/find_economy_seed.py    → ECONOMY_SMALL
    python scripts/find_boss_seed.py       → BOSS_SMALL
    python scripts/find_tag_pair_seed.py   → DOUBLE_THEN_FOIL
"""

from __future__ import annotations

# ante 1: small=Charm Tag (opens pack on skip)
CHARM_SMALL = "S00001"

# ante 1: small=Boss Tag (deferred; non-pack skip smoke)
BOSS_SMALL = "S00002"

# ante 1: small=Foil Tag (deferred until shop)
FOIL_SMALL = "S00010"

# ante 1: small=Economy Tag (consumed immediately on skip)
ECONOMY_SMALL = "S00011"

# ante 1: small=Double Tag, big=Foil Tag
DOUBLE_THEN_FOIL = "S00062"
