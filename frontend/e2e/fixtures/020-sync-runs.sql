INSERT INTO sync_runs (
    id, kind, source, status, started_at, finished_at, duration_ms, result, error
) VALUES
    ('7a1c0e2e-0000-4000-8000-000000000001', 'catalog', 'tcgdex', 'partial',
        '2026-10-05T07:00:00Z', '2026-10-05T07:02:05Z', 125000,
        '{"counts": {"series": {"fetched": 2, "created": 0, "updated": 0, "unchanged": 2},
          "sets": {"fetched": 3, "created": 0, "updated": 1, "unchanged": 2, "skipped": 0, "failed": 1},
          "cards": {"fetched": 120, "created": 2, "updated": 3, "unchanged": 115, "failed": 0}},
          "failures": [{"kind": "set", "provider_id": "sv02", "reason": "HTTP 500 after 3 attempts"}]}',
        NULL),
    ('7a1c0e2e-0000-4000-8000-000000000002', 'images', 'tcgdex', 'succeeded',
        '2026-10-05T07:02:05Z', '2026-10-05T07:02:47Z', 42000,
        '{"set_id": null,
          "counts": {"cards": {"downloaded": 10, "cached": 0, "unavailable": 2, "failed": 0},
          "artwork": {"downloaded": 4, "cached": 0, "unavailable": 0, "failed": 0}},
          "failures": []}',
        NULL)
ON CONFLICT (id) DO NOTHING;
