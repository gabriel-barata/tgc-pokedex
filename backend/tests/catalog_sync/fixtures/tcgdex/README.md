# TCGdex fixture corpus

Payloads served to the TCGdex adapter by `tcgdex_fixtures.py` through `httpx2.MockTransport`.
Each file is named after its endpoint path under `https://api.tcgdex.net/v2/pt/`. Tests never
reach the real API: every request needs an explicit route, with no catch-all.

Recorded files were fetched on 2026-10-11 and pretty-printed with `jq`. Their content is
verbatim except for the trims listed below. There is no recording script.

## Recorded

| File | Endpoint | Trimmed | Covers |
|---|---|---|---|
| `series.json` | `/series` | Only `base`, `xy`, `swsh`, `sv` and `tcgp` kept, in provider order | Series index, Pocket series listed |
| `series/base.json` | `/series/base` | `sets` kept to `base1` | Series whose only set is empty (not stored) |
| `series/xy.json` | `/series/xy` | `sets` kept to `xy0` | |
| `series/swsh.json` | `/series/swsh` | `sets` kept to `swshp`, `swsh4.5` | Series with two stored sets |
| `series/sv.json` | `/series/sv` | `sets` kept to `sv01` | |
| `series/tcgp.json` | `/series/tcgp` | `sets` kept to `A1` | Pocket series; never requested |
| `sets/base1.json` | `/sets/base1` | none (`cards` is `[]` live) | Empty physical set, no logo or symbol |
| `sets/xy0.json` | `/sets/xy0` | `cards` kept to `xy0-1`, `xy0-2` | Set with no logo |
| `sets/swshp.json` | `/sets/swshp` | `cards` kept to `swshp-SWSH032`, `swshp-SWSH158` | Promo set, non-numeric collector numbers, card briefs with no `image` |
| `sets/swsh4.5.json` | `/sets/swsh4.5` | `cards` kept to `swsh4.5-1` | Live padded name `"Destinos Brilhantes "` |
| `sets/sv01.json` | `/sets/sv01` | `cards` kept to the first 9 | Modern set; 9 cards for the in-flight limit test |
| `cards/sv01-001.json` … `cards/sv01-009.json` | `/cards/{id}` | none | Variants `{normal, reverse}` |
| `cards/xy0-1.json`, `cards/xy0-2.json` | `/cards/{id}` | none | Rarity `"None"` |
| `cards/swshp-SWSH032.json`, `cards/swshp-SWSH158.json` | `/cards/{id}` | none | Collector numbers `SWSH032`, `SWSH158`; no `image`; holo only |
| `cards/swsh4.5-1.json` | `/cards/{id}` | none | |

## Hand-made

| File | Case |
|---|---|
| `series/sv.with-failures.json` | `series/sv.json` plus two set briefs: `sv02` (answered 500 three times by the route table, no file) and `fail01` |
| `sets/fail01.json` | Set whose card list holds the failure cards `fail01-001` … `fail01-004` |
| `cards/fail01-001.json` | Copy of `sv01-001` with no `name` (invalid card) |
| `cards/fail01-002.json` | Copy of `sv01-002` with all five variant flags `false` (`no variants`) |
| `cards/fail01-004.json` | Copy of `sv01-004`, served after one 500 (retried, then stored) |

`fail01-003` has no file: the route table answers it with 404. The "series index answered 500
three times" case is also a route table entry only (`INDEX_DOWN`).
