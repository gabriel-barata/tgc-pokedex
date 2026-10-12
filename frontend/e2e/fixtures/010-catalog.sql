INSERT INTO series (id, name, source, fetched_at) VALUES
    ('me', 'Megaevolução', 'tcgdex', '2026-10-12T12:00:00Z'),
    ('sv', 'Escarlate e Violeta', 'tcgdex', '2026-10-12T12:00:00Z')
ON CONFLICT (id) DO NOTHING;

INSERT INTO sets (
    id, series_id, name, release_date, official_count, total_count,
    logo_url, symbol_url, source, fetched_at
) VALUES
    ('me02', 'me', 'Fogo Fantasmagórico', '2025-11-14', 94, 130, NULL, NULL,
        'tcgdex', '2026-10-12T12:00:00Z'),
    ('mep', 'me', 'MEP Black Star Promos', '2025-09-26', 0, 88, NULL, NULL,
        'tcgdex', '2026-10-12T12:00:00Z'),
    ('sv10', 'sv', 'Rivais Predestinados', '2025-05-30', 182, 244, NULL, NULL,
        'tcgdex', '2026-10-12T12:00:00Z')
ON CONFLICT (id) DO NOTHING;

DELETE FROM tracked_sets WHERE set_id IN ('me02', 'mep', 'sv10');
