# TCGdex fixture corpus

Payloads served to the TCGdex client by `tests/helpers.py` through `httpx2.MockTransport`.
Each file is named after its endpoint path under `https://api.tcgdex.net/v2/pt/`.

The files were recorded on 2026-10-11 and trimmed to the fields the client reads: `series.json`
keeps `sv` and the Pocket series `tcgp`, `series/sv.json` keeps `sv01`, and `sets/sv01.json`
keeps its first two cards. `series/sv.with-failures.json` is hand-made: it adds `sv02`, which
the route table answers with 500.
