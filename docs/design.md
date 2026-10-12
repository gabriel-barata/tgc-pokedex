# Visual Direction: TCG Pokédex

Recorded 2026-10-11 (PTCG-011) from a long interview with the owners. It sets the
visual direction, its pillars and the key UI behaviors. Feature cards follow it when
they build screens. The mockups in [`design/mockups/`](design/mockups/index.html)
show one possible path along this direction. They are not the final design: layouts,
values and details may still change in feature work, as long as the pillars and
invariants below hold.

## Revision history

- **2026-10-11 (PTCG-011, initial):** first version, from the visual-direction
  interview. Scope changed from the original card. This PR delivers the direction
  document and reference mockups. Installing the component library, coding the tokens
  and building the app shell move to PTCG-035.
- **2026-10-12 (PTCG-035):** the tokens are now code. `frontend/src/ui/theme.css` is the
  source of truth for every color, type, radius, shadow, spacing, breakpoint and motion
  value. The Typography and Tokens sections now point to it instead of listing values.
  The contrast pairs stay here as measured evidence. shadcn/ui, Tailwind CSS, the
  motifs, the favicon and the app shell are in place (decisions 8, 9, 11, 22, 23).
- **2026-10-12 (PTCG-015):** the sets page is built and is the home page. Decision 16
  gains the card-count rule, the tracking copy and the cover's content until the spine
  bar exists (PTCG-019). Decision 16b: no set tint for now, so every cover uses plain
  paper. The PTCG-015 open item is closed.
- **2026-10-12 (PTCG-017):** the ownership rule is settled. Owning any version of a card
  owns it; "só normal" is information only. A set is complete when every card is owned,
  so the spine bar has no track left, light segments included (decisions 13 and 14).
  The PTCG-017 open item is closed; which cards make up the total moves to PTCG-039.

## Context

TCG Pokédex tracks which Pokémon TCG cards (Portuguese prints) we own or are missing
in each set, with card images and prices. Its users are two people, a couple who
collect together. Collecting is a **cozy** hobby for them ("aconchegante"): calm,
comforting, done side by side. It is **not** competitive, financial or harsh.

- **Main moment:** a laptop or desktop while sorting the binder, which means wide
  grids, a pointer and a keyboard. A phone is used to check things now and then, and
  the UI adapts to it gracefully (decision 23).
- **Favorite Pokémon:** Torchic and Popplio. The UI is built around the two of them.
  They appear through palette roles, original motifs, the logo, state screens and
  small celebrations.
- **Language:** UI copy in pt-BR (CLAUDE.md); this document in English.

### References

| Reference | What we keep (the mechanism) | What we reject |
|---|---|---|
| [PokéCottage set list](https://pokecottage.com/sets/chaos-rising-card-list/) | Set header with code, release date and total cards; card number + name under each image; a clear grid in number order. | Too simple and static: no owned state, no interaction. Its loud palette (vivid greens, purples, blues) and its "chase cards" / price hype. |
| Physical collecting: binder pages, sleeves, stickers | Cards resting in sleeves on a page; empty pockets that show the gap; sticker-like labels; the binder spine as a progress metaphor. | Literal skeuomorphism such as stitched leather or plastic glare textures. |
| Torchic and Popplio (the owners' favorites) | Color roles (warm orange and crest yellow, sky blue, deep-sea navy, pink nose) and simple shapes (three-point crest, nose bubble, scalloped white ruff). | Official artwork and sprites in the UI (decision 9). |

The rules in this document take precedence over every reference.

## Direction thesis

> **A shared craft desk:** cards rest in soft sleeves on warm cream paper, Torchic's
> warmth marks what we have and Popplio's calm guides where we go, and every
> interaction feels like handling a real card gently, never like keeping score.

## Pillars

1. **Cozy, not competitive.** Calm tones, soft materials, unhurried motion. Nothing
   ranks, races or pressures: no leaderboards, streaks, value deltas, "chase" badges
   or urgency copy.
2. **Two friends, two jobs.** Torchic (warm) and Popplio (calm) are always both
   present, and each has a clear role. Neither is decoration only.
3. **The binder tells the truth.** What the grid shows matches the physical
   collection: missing is missing, and an owned Reverse looks like a Reverse. You can
   trust the UI without opening the binder.
4. **Tactile, with a few treats.** Interactions feel physical (lift, press, slide into
   a sleeve). Delight comes from a few deliberate moments, not constant movement.
5. **Quiet data, loud cards.** The card art is the star. Chrome, numbers and prices
   stay calm and neutral around it.

## Visual grammar

### Invariants (hold on every screen)

- A warm cream "paper" base covers about 85% of the area. Accents are deliberate, never
  washes.
- Torchic orange means *collection*: owned state, primary actions, progress.
  Popplio blue means *navigation and attention*: links, selection, focus, information,
  and the "wanted version missing" ribbon.
- Missing cards are empty dashed sleeves. Owned cards are full art in a sleeve.
- Every state is shown by more than color: shape, label or pattern too.
- Corners are rounded and shadows are warm. Nothing is sharp-edged, and nothing has a
  grey or black drop shadow.
- Copy is neutral and concise (decision 17).

### Controlled variables (may change within a range)

- Set tint on the binder cover and set header: 0–16% mix into paper (decision 16b).
- Grid column count, by viewport (decisions 12 and 23).
- Motion duration within the tokens' ranges. Every motion has a reduced-motion
  fallback.
- How often motifs appear: at most one mascot moment on screen at a time.

### Anti-patterns (tempting, and they break the direction)

- Gold or glowing frames for rare cards, "CHASE!" or "RARO!" badges, rarity-sorted
  "best pulls".
- Red/green price deltas, up/down arrows, "valorizou", "top cards by value", value
  leaderboards.
- Percent-first framing ("62%!"), streaks, "only 3 left!", countdowns.
- Neon or vivid official-sprite saturation; dark "gamer" UI; Pokédex-red device
  chrome.
- Full-page confetti or bouncing layouts; motion with no meaning.
- Pure white (#FFF) page backgrounds or cold grey borders and shadows.
- Official Pokémon artwork used as UI decoration.

## Decisions

### Scope and process

#### 1. This document is the direction; mockups only show a path

`docs/design.md` is the authority for visual direction. The mockups in
`docs/design/mockups/` are static, dependency-free HTML that show one possible
execution of it. They are reference material, not app code: they are not linted,
tested or imported by `frontend/`.

**Why:** the owners want a durable direction that survives redesigns, not a frozen
pixel spec. Keeping the mockups out of `frontend/` keeps them clearly throwaway
(Principle I spike exemption).

#### 2. One direction, built through the interview

The original card imagined 2–3 competing directions (binder / holo-foil /
Pokédex red). Instead, the interview converged on one direction, choosing between
contrasting options one decision at a time. The rejected options are kept per
decision below as history.

#### 3. Follow-up work leaves this card

Installing the component library (decision 22), turning the tokens into code and
building the app shell (decision 11) move to **PTCG-035**. Feature cards that
build screens (PTCG-014, PTCG-015 and later) also depend on that card.

### Identity: color, characters, logo

#### 4. Palette strategy: duo accents with roles

Warm-neutral cream base (about 85%), plus two accent families, each with a job:

| Family | Role | Used for |
|---|---|---|
| **Torchic** (apricot orange) | *Collection* | Owned state, primary buttons, progress bar, set-complete moments |
| **Popplio** (dusty sky blue + deep-sea navy) | *Navigation and attention* | Links, selected filter chips, focus ring, info, the "wanted version missing" ribbon |
| **Highlights** (crest yellow, nose pink) | *Celebration only* | Celebration particles, the logo badge, rare decorative touches |

**Rejected:** light theme = Torchic and dark theme = Popplio; one accent with the other
as decoration only (this would make one partner's favorite second-class); blended
coral and teal (too abstract).

#### 5. Saturation: warm and muted, slightly deepened

Both families are pulled toward earthy and dusty tones (the "algo para escurecer" note):
Torchic leans burnt apricot, Popplio leans dusty sky and deep-sea navy. Never neon,
never the vivid sprite colors. Text and thin strokes use the deeper shades so they pass
contrast on cream (see [Tokens](#tokens)).

#### 6. Light theme only for the MVP

The cream light theme ships alone. Tokens are named by role (`surface.page`, not
`cream`), so a dark theme can be added later without renaming. A cozy dark theme
(warm charcoal or deep-sea navy, never pure black) is a possible post-MVP card.

**Why:** YAGNI (Principle VII). One theme halves the visual QA while the direction
settles.

#### 7. Torchic and Popplio are a shared duo now, per-person later

In the MVP both Pokémon stand for "us": the collection is shared. When per-person
profiles arrive (PTCG-031), each profile may get one of them as its avatar and accent
tint. The role-based palette does not change.

#### 8. Logo: duo badge + "TCG Pokédex" wordmark

A round cream badge in which Torchic's three-point crest-feather (orange, crest-yellow
tip) and Popplio's nose bubble (sky blue, pink highlight) sit side by side, slightly
overlapping, like two friends. The wordmark "TCG Pokédex" is set in Fredoka 600 in
`text.primary`, with "TCG" in the Torchic ink color. The badge alone is the favicon and
the compact mark on small screens. `frontend/public/favicon.svg` is a static export of the
`Badge` motif with the token colors written out, so re-export it whenever the badge or
its colors change.

#### 9. Character imagery: original, simplified SVG motifs

We do not use official Pokémon artwork or sprites in the UI. We draw our own minimal,
flat motifs inspired by the two Pokémon:

| Motif | Shape | Typical use |
|---|---|---|
| `motif.crest` | Torchic's three-point feather/flame tuft | Logo, loading, owned celebration puff |
| `motif.bubble` | Popplio's round nose bubble with a highlight | Logo, empty states, celebration puff |
| `motif.ruff` | Popplio's scalloped white collar, as a repeatable edge | Decorative divider under section titles, bottom edge of the binder cover |
| `motif.ember` | Small rounded ember/spark dots | Celebration particles |

The motifs are React components in `frontend/src/ui/motifs/`, one file each, so they can
be swapped. They are always decorative (hidden from assistive tech); meaning comes from
the text next to them.

Motif style: flat fills from the palette, no outlines (or a 1.5px `text.primary`
outline only at sizes up to 24px), rounded joins, no gradients except the bubble's
single highlight.

Card images, set logos and set symbols are *content*, not decoration. They are shown
as delivered by the catalog (Principle IV: synced into our own store).

**Rights note:** Torchic, Popplio, card images and set logos are IP of Nintendo / The
Pokémon Company / Creatures / GAME FREAK. The app is a private, LAN-only hobby tool.
Our motifs are original simplified shapes, kept in their own files so they can be
swapped. This is not legal advice; revisit it if the app is ever exposed publicly.

#### 10. Where the duo appears

The motifs appear in exactly these places:

1. **Logo / app mark** (decision 8).
2. **Empty, loading and error states** (decision 20).
3. **Celebrations:** card marked owned, and set completed (decision 21).
4. **Progress and status iconography:** the owned sticker, the completion bar's end
   cap, and the wanted-version ribbon.

Nowhere else. In particular there are no mascots in the page chrome, as backgrounds,
or in tooltips. At most one mascot moment is on screen at a time.

### Layout and screens

#### 11. App shell: a slim top bar

A 64px top bar on `surface.raised` with a hairline bottom border: logo on the left,
global search in the center ("Buscar carta…", up to 480px wide), and text links on the
right (Coleções · Status; later Lista de desejos). Content gets the full width under it
(max 1440px, 32px side gutters). There is no sidebar.

**Rejected:** a left sidebar (it takes about 240px from the grid); binder tabs per
tracked set (they don't scale).

#### 12. Set grid: one continuous grid with a binder feel

The set page is a sticky header plus one continuous grid in set-number order.

- **Sticky header** (on the set tint band, decision 16b): set logo, name, series and
  year, the spine bar (decision 14), and the filter chips: *Todas · Possuídas ·
  Faltando · Versão pendente*, then rarity ▾, variant ▾, a search-in-set field, and the
  "Mostrar preços" toggle (decision 18).
- **Grid:** sits on a `surface.raised` "binder page" with a 16px radius and a soft
  shadow. Columns adapt to width with tiles about 168–188px wide, which gives 6
  columns at 1440px. The gap is 16px horizontal and 20px vertical.
- **Tile:** a sleeve (12px radius, hairline border) holding the card image (card
  aspect ratio 63:88, image radius 8px). Under the sleeve: the number, in tabular
  `text.secondary` (`022/159`), the name in `text.primary`, and the variant dots and
  duplicate count (decision 13).

**Rejected:** literal 3×3 binder pages (charming, but clunky with filters and large
sets); a binder-view toggle (two views to maintain).

#### 13. Card tile states: the binder tells the truth

| State | Tile | Not-color-only cue |
|---|---|---|
| **Missing** | Empty sleeve: `surface.sunken` fill, 1.5px dashed `border.sleeve` outline, number and name centered inside. **No art.** | Dashed outline + no image + accessible name "… — faltando" |
| **Owned, wanted version missing** | Full art, plus a Popplio-blue corner ribbon naming the wanted version ("Reverse" / "Holo") | Ribbon text + hollow variant dot |
| **Owned (wanted version)** | Full art with a foil overlay that matches the best owned version (below) | Variant dots + label in detail |

- **Wanted version:** we prefer a card's Reverse or Holo over its Normal. When a card
  has a Reverse or Holo version and we own only the Normal, the wanted version is
  still missing. *Settled in PTCG-017:* owning any version owns the card. The wanted
  version is missing when only the Normal is owned and the card has any other
  version. This is information only: the card still counts as owned, for the album
  and for completion. A card with a single version never has a wanted version
  missing.
- **Foil honesty:** the catalog usually has one image per card, the same for all
  versions. The tile shows the **best owned version** (Holo > Reverse > Normal) with a
  CSS foil layer that mimics the physical finish. *Reverse* puts a soft rainbow sheen
  on the card frame and background, with the art window clear. *Holo* puts the sheen
  on the art window only. *Normal* has no foil. On the grid the sheen is static and
  subtle. In the detail tilt (decision 15) it moves with the pointer.
- **Variant dots:** below the name, one 8px dot per version the card has, in
  Normal → Reverse → Holo order. A filled `torchic` dot means owned and a hollow one
  means not owned. Each dot has a tooltip and an accessible label, e.g.
  "Normal: 1, Reverse: 0".
- **Duplicate count:** a small `×N` sticker next to the dots when the total copies
  across versions are 2 or more.

**Rejected:** faded art for missing cards; full art for all cards with an owned stamp;
half-faded art for owned-Normal-only cards (it would make a card we own look "less
owned").

#### 14. Completion: a two-tone binder-spine bar, count first

Set completion is a horizontal bar styled as a binder spine: a pill with a 10px track
on `surface.sunken`, a hairline border and a rounded end cap.

- The **deep segment** (`torchic.600`) counts cards owned in the wanted version.
- The **light segment** (`torchic.200` with `torchic.600` diagonal stripes) counts
  cards owned only in Normal while a wanted version exists.
- The **track** is missing cards.
- **Label, count first:** "43 de 159 · 7 só normal". A percent is optional,
  secondary and small. The set is complete when every card is owned in any version,
  that is when the bar has no track left, light segments included.
- When complete, the bar's end cap becomes the duo badge and the set-complete
  celebration runs once (decision 21).
- No sorting or ranking of sets by percent, and no streaks.

The domain (PTCG-017) owns the counts and the bar only displays them. The total is
the set's printed card count, or every card when none is printed, the same number the
sets page shows. Until PTCG-039 decides which cards count (secret rares beyond the
printed count, catalog gaps), owned cards are capped at that total.

**Rejected:** completion rings (the original card wording); a Poké Ball fill.

#### 15. Card detail: a side panel over the grid

Clicking any tile opens a right-hand panel (440px, `surface.raised`, 16px radius on
the leading edge, `shadow.lg`). The grid stays visible behind it under a 6% `ink`
scrim. The panel holds:

- the big card image with the **3D tilt** (up to 8° following the pointer) and the
  foil sheen of the best owned version. A missing card shows its art **faded** (35%
  opacity, desaturated) inside the dashed sleeve, with "Ainda não possuída", so the
  faded art appears only here, on request;
- the name, number, rarity (decision 19), illustrator and type;
- one row per version: label, quantity stepper `[− n +]`, and the quiet price
  (decision 18) when known;
- the wanted-version ribbon text when it applies;
- prev/next (‹ ›) to move through the current filtered list.

The panel has its own URL (Back closes it). Keyboard: Esc closes it, ←/→ move to the
previous/next card, and focus returns to the tile on close.

**Rejected:** a centered modal (hides the grid); a full page (loses your place in the
binder).

#### 16. Sets page: binder covers for tracked sets, a calm catalog for the rest

- **"Acompanhando"** (tracked sets) appear first, as **binder-cover tiles**: a
  `surface.raised` cover with the set tint (decision 16b) and a `motif.ruff` bottom
  edge. Each shows the set logo, name, series and year, and the spine bar with its
  count label. The whole cover is the link into the set.
- **"Todas as coleções"** follows, grouped by series, newest first: compact quiet rows
  with the set symbol, name, year, card count, and an "Acompanhar" button (secondary
  style). Tracked sets also appear here with "Acompanhando ✓".
- **Card count** is the number printed on the cards ("182 cartas"), so secret rares
  are not added. A set with no printed number, such as a promo set, shows its
  distinct-card total. Variants (normal, reverse, holo) never count separately.
- **Tracking copy:** "Acompanhar" tracks; a tracked set's button reads "Acompanhando"
  with a check and untracks on press, with no confirmation, since untracking deletes
  nothing. It is a toggle button (`aria-pressed`) whose name includes the set name.
- **Until the spine bar exists** (PTCG-019), a cover shows the logo (or the set name
  when there is no logo), name, series, year and card count, plus a quiet "Imagens
  sendo sincronizadas" while its images download. With no tracked set, the section
  shows the decision 20 empty state, whose link moves focus to "Todas as coleções".

**Rejected:** a bookshelf of vertical spines (hard to read); one uniform list.

#### 16b. Set tint (controlled exception to the duo palette)

A set may tint **only** its binder cover and its set-page header band. The tint is a
color derived from the set (its source, e.g. extracted from the logo at sync time or
stored manually, is decided in PTCG-015), mixed **at most 16% into `surface.page`**
and clamped to OKLCH L ≥ 0.92, so text keeps using the standard ink tokens and still
passes contrast. When there is no tint, the plain paper is used. Buttons, chips, the
bar and focus always keep the duo colors.

**Decided in PTCG-015:** no tint for now. Every cover uses the plain paper. Many older
sets have no logo to extract a tint from, and a manual color needs upkeep. A later
card can add a source within the rule above.

### Behavior and feel

#### 17. Voice: neutral and concise

Copy is impersonal and short. Labels say what things are: "Coleções", "Acompanhando",
"Possuídas", "Faltando", "Versão pendente", "Ainda não possuída", "Coleção completa".
Warmth comes from the visuals, not from the copy. Mascots never speak. Copy never
pressures: no "apenas 3 restantes!", "raro!" or "valorizou". Errors are kind and
actionable: "Não foi possível carregar as cartas. Tentar novamente".

The wording here is illustrative. The final strings live in `frontend/src/strings/`.

**Rejected:** a warm "nós" voice ("Nossos fichários", "Ainda não temos"); a mascot
narrator.

#### 18. Prices: quiet and on demand

- The grid shows **no prices by default**. A "Mostrar preços" toggle in the set header
  adds one small `text.secondary` line under each tile ("≈ R$ 0,15").
- The detail panel shows one muted price per version, with the source and date line
  required by PTCG-022.
- Prices have no red/green colors, no deltas or arrows, no "valorizou", and no
  rankings by value. Future totals (collection value, cost to complete) use neutral
  ink, never an accent.

#### 19. Rarity: neutral information

Rarity looks the way the printed card shows it: a small neutral symbol (● ◆ ★) plus the
text label, in the detail panel and in the rarity filter. Every tile gets the same
treatment, whatever its rarity. No glow, no gold, no "chase" wording, no
rarity-based emphasis. The only finish-related effect is the foil honesty layer
(decision 13), which follows *what we own*, not what is rare.

#### 20. Empty, loading and error states

| State | Visual | Copy (illustrative) |
|---|---|---|
| Loading grid / images syncing | Skeleton sleeves (dashed sleeves with a slow paper-tone shimmer; static under reduced motion), plus a small `motif.crest` gently bobbing beside "Carregando cartas…" | "Carregando cartas…" / "Imagens sendo sincronizadas" |
| Empty filter result | `motif.bubble` (64px) centered on the binder page | "Nenhuma carta encontrada" + "Limpar filtros" |
| No tracked sets | Crest and bubble side by side, with an arrow-free hint | "Nenhuma coleção acompanhada" + "Ver todas as coleções" |
| Error | `motif.bubble`, deflated (a flatter shape) | "Não foi possível carregar as cartas." + "Tentar novamente" |
| Image unavailable | A sleeve with `surface.sunken` and the card name, like a missing card but with a solid border | "Imagem indisponível" |

#### 21. Motion: soft and tactile, with three treats

**Base layer (functional):**

| Class | What | Duration / easing |
|---|---|---|
| Hover lift | Tile rises 2px, shadow `sm` → `md` | `motion.fast` 140ms, `ease.out` |
| Press | Sticker and buttons scale to 0.96 | 100ms, `ease.out` |
| Panel | Detail panel slides 24px + fades in | `motion.panel` 260ms, `ease.out`; closes in 200ms |
| Filter | Grid items fade/reflow | 180ms; no movement under reduced motion |

No bounce on layout. A small overshoot (`ease.sticker`) is allowed only on stickers.

**Treats (deliberate, rare):**

1. **Tilt:** in the detail panel the card tilts up to 8° toward the pointer, and the
   foil sheen follows it.
2. **Into the sleeve:** marking a card owned turns the dashed sleeve solid, the art
   fades in (300ms), and a tiny puff of 3–5 crest and bubble particles rises from the
   sticker (600ms).
3. **Set complete:** once per set, when the bar becomes fully deep, the end cap blooms
   into the duo badge and a ring of ember and bubble particles rises around it
   (about 1.2s). Then a "Coleção completa" chip stays on the cover. It never replays
   on later visits.

**Reduced motion** (`prefers-reduced-motion: reduce`): no tilt, no particles, no
shimmer, no lift; state changes become instant or 120ms opacity changes. Meaning is
never carried by motion alone. Nothing flashes.

#### 22. Component library: shadcn/ui + Tailwind CSS

shadcn/ui (Radix-based components copied into our repo) with Tailwind CSS, whose theme
is the [Tokens](#tokens) file. Components live in `frontend/src/ui/` (see
`frontend/components.json`) and are restyled with our tokens when added. Icons come from
Lucide (rounded 2px stroke), plus our motifs (decision 9).

**Why:** the craft-desk look is distinctive. Owning the component code makes it easy to
style fully, and Radix provides accessible keyboard and ARIA behavior. Mantine was
rejected because its default look is harder to bend this far. The dependency
justifications (Quality Gate 4) are in the PTCG-035 pull request.

#### 23. Small screens: graceful adaptation

Desktop is the primary target, and the same direction recomposes on small screens:

| Element | ≥ 1024px | 640–1023px | < 640px |
|---|---|---|---|
| Top bar | Logo + search + links | Logo + search + menu | Badge + search icon + menu |
| Grid columns | auto, ~180px tiles (6 at 1440) | 4–5 | 3 (2 below 380px) |
| Detail | Right side panel 440px | Right side panel 400px | Bottom sheet, 92% height, drag handle |
| Filter chips | One row | One row | Horizontal scroll, no wrapping |
| Binder covers | 3–4 per row | 2 per row | 1 per row (compact) |
| Touch targets | n/a | ≥ 44px | ≥ 44px; the owned sticker gets a 44px hit area |

#### 24. Accessibility baseline

- Text contrast meets WCAG 2.2 AA: ≥ 4.5:1 for normal text, ≥ 3:1 for large text, and
  ≥ 3:1 for UI and graphic boundaries. Pairs are listed with the tokens.
- No state is shown by color alone (decisions 13 and 14).
- Focus is always visible: a 2px `focus.ring` outline with a 2px offset, on every
  interactive element, including tiles.
- Every tile is keyboard-operable: Enter opens the detail panel and Space toggles
  owned. Accessible names include the card name, set, number and state (constitution:
  Accessibility).
- The reduced-motion behavior in decision 21 applies everywhere.
- Fonts are self-hosted: the app never requests external origins (the e2e harness
  enforces this).

## Typography

Two families, both SIL OFL and self-hosted:

- **Fredoka** (display): titles, the wordmark, set names on covers. Soft, round and
  friendly, without being childish.
- **Nunito** (text): everything else. Card numbers and counts use tabular figures
  (`font-variant-numeric: tabular-nums`).

The scale is defined in [`frontend/src/ui/theme.css`](../frontend/src/ui/theme.css) as
`--text-*` (size, line height and weight together). Use it through the matching classes:

| Token / class | Family | Use |
|---|---|---|
| `text-display` | Fredoka | Page titles ("Coleções") |
| `text-title` | Fredoka | Set name in the set header, detail card name |
| `text-heading` | Fredoka | Section titles ("Acompanhando", series names) |
| `text-body` | Nunito | Body text, buttons (with `font-semibold`) |
| `text-label` | Nunito | Tile name, chips, form labels |
| `text-caption` | Nunito, `tabular-nums` | Card number, counts, price lines, dots legend |

`h1`–`h3` get Fredoka from the base styles; elsewhere add `font-display`.

The minimum rendered text size is 12px. Never use all-caps for more than two words.

## Tokens

**Source of truth: [`frontend/src/ui/theme.css`](../frontend/src/ui/theme.css)** (Tailwind
`@theme`, emitted as CSS custom properties). This section does not repeat its values
(Principle II). Values may be tuned in feature work within this direction. Re-measure any
contrast pair that a change touches.

Names map one to one: the role `surface.page` is the custom property
`--color-surface-page` and the classes `bg-surface-page`, `text-…`, `border-…`. Likewise
`radius.md` is `rounded-md`, `shadow.lg` is `shadow-lg`, `ease.sticker` is `ease-sticker`,
and `motion.panel` is `var(--motion-panel)` (e.g. `duration-(--motion-panel)`). Tailwind's
default palette, radii, shadows, type sizes and easings are switched off, so only our
tokens exist.

### Color roles

Primitives (`cream`, `bark`, `torchic`, `crest`, `popplio`, `nose`, `clay`) are for the
roles below and for motif fills. Components use the roles.

| Role | Allowed use | Never |
|---|---|---|
| `surface.page` | Page background, with faint paper grain (≤ 3% opacity noise) | Pure white |
| `surface.raised` | Binder page, panels, tiles, top bar | Under body text without a border |
| `surface.sunken` | Empty sleeves, bar track, skeletons | Large areas |
| `border.hairline` | 1px borders on raised surfaces | As the only state cue |
| `border.sleeve` | 1.5px dashed missing-sleeve outline | Solid borders of owned tiles |
| `text.primary` | All primary text | n/a |
| `text.secondary` | Numbers, metadata, price lines | Disabled text |
| `text.accent` | "TCG" in the wordmark, small emphasis on cream | Long text |
| `action.primary.bg` / `.fg` | Primary buttons, owned sticker | Large fills |
| `action.primary.hover` | Hover/pressed primary | n/a |
| `owned.mark` | Owned sticker, filled variant dot, deep bar | Decoration |
| `progress.partial` + `progress.partial.stripe` | Normal-only bar segment | Without stripes |
| `link` | Links, text buttons | Body text |
| `focus.ring` | 2px focus outline, 2px offset | n/a |
| `selected.bg` / `.fg` | Active filter chip, selected item, current nav link | Owned state |
| `ribbon.bg` / `.fg` | Wanted-version ribbon, info | n/a |
| `danger` | Error text and icons | Prices, deltas |
| `highlight.crest`, `highlight.nose` | Celebrations, logo | UI states |

### Contrast pairs (WCAG 2.2, measured)

| Foreground on background | Ratio | Passes |
|---|---|---|
| `text.primary` on `surface.page` | 12.2 | AA text |
| `text.primary` on `surface.sunken` | 10.8 | AA text |
| `text.secondary` on `surface.page` | 6.0 | AA text |
| `text.secondary` on `surface.sunken` | 5.3 | AA text |
| `text.accent` on `surface.page` | 5.9 | AA text |
| white on `action.primary.bg` | 4.6 | AA text |
| white on `action.primary.hover` | 6.4 | AA text |
| `link` on `surface.page` | 5.4 | AA text |
| `selected.fg` on `selected.bg` | 10.0 | AA text |
| `ribbon.fg` on `ribbon.bg` | 6.5 | AA text |
| `danger` on `surface.page` | 5.9 | AA text |
| `border.sleeve` on `surface.page` | 3.4 | AA non-text (3:1) |
| `owned.mark` on `surface.sunken` (bar) | 3.8 | AA non-text |
| `torchic.600` stripes on `torchic.200` | 3.2 | AA non-text |
| `bark.500` on `surface.page` | 3.9 | Large text / decorative only |
| `torchic.500` on `surface.page` | 2.8 | **Fails**: motif fill only, never text or essential strokes |
| `popplio.400` on `surface.page` | 2.2 | **Fails**: motif fill only |

### Shape, depth, spacing, motion

| Token | Use |
|---|---|
| `radius.sm` | Card image inside a sleeve, small stickers |
| `radius.md` | Tiles (sleeves), inputs, binder covers |
| `radius.lg` | Binder page, panels, sheets |
| `radius.pill` | Buttons, chips, the spine bar |
| `shadow.sm` | Tiles at rest |
| `shadow.md` | Tile hover, stickers |
| `shadow.lg` | Detail panel, sheets |
| `spacing` | 4px base; use the steps 4 · 8 · 12 · 16 · 20 · 24 · 32 · 48 · 64 px |
| `breakpoint.sm` / `.lg` | The 640px and 1024px steps of decision 23 |
| `motion.fast` | Hover, press |
| `motion.base` | Fades, chip changes |
| `motion.panel` | Detail panel / sheet in |
| `motion.celebrate.puff` / `.set` | Owned puff, set complete |
| `motion.reduced` | The only transition length under reduced motion |
| `ease.out` | Default |
| `ease.sticker` | Stickers only (small overshoot) |

The reduced-motion baseline (decision 21) and the focus ring (decision 24) are global
rules in the same file.

Stickers (the owned button, `×N`, ribbons) have a 2px `surface.raised` edge and
`shadow.md`, so they look slightly raised, like real stickers.

## Mockups

Open [`design/mockups/index.html`](design/mockups/index.html) in a browser. The pages
load fonts from Google Fonts and card images from TCGdex for realism. The app itself
must not do either (decision 24).

| Mockup | Shows |
|---|---|
| `sets.html` | Sets page: "Acompanhando" binder covers with set tint and spine bars; "Todas as coleções" catalog rows |
| `set.html` | Set grid for *Amigos de Jornada* (sv09): every tile state, foil overlays, variant dots, filters, price toggle, clickable owned sticker |
| `set.html?card=022` | Card detail panel (Torchic 022) over the grid: tilt, versions, steppers, quiet price |
| `states.html` | Loading (skeleton sleeves), empty filter result, no tracked sets, error |
| `brand.html` | Logo, favicon, motifs, stickers, ribbon, spine bar, palette swatches |

Owned and missing data in the mockups is fictional. Prices are illustrative.

## Acceptance checklist (for any screen built under this direction)

- [ ] About 85% of the area is warm neutral. Torchic and Popplio each appear in their
      role and not as washes.
- [ ] Missing, owned-with-version-pending, and owned tiles are distinguishable in
      grayscale.
- [ ] The tile's foil matches the best owned version. No foil appears on missing or
      Normal-only tiles.
- [ ] Nothing ranks, races or pressures: no deltas, no rarity glow, no percent-first
      framing, no urgency copy.
- [ ] Prices are hidden on the grid unless toggled; when shown they are muted.
- [ ] Every interactive element is keyboard-operable, with a visible Popplio focus ring
      and an accessible name.
- [ ] Under reduced motion: no tilt, particles, shimmer or lift, and no meaning is lost.
- [ ] Every text/background pair is in the contrast table, or measured and added to it.
- [ ] Mascot motifs appear only in the four places of decision 10, at most one at a
      time.
- [ ] No official Pokémon artwork is used as UI decoration; no external font or image
      requests come from the app.

## Open items for feature cards

- **PTCG-039 (Completion total):** which cards make up a set's total (secret rares,
  odd numbering, catalog gaps); until then owned cards are capped at the printed count.
- **PTCG-018 (Mark owned):** the default variant toggled by the sticker (assumed:
  Normal, or the only version the card has).
- **PTCG-022 (Show price):** the price line formats within decision 18.
- **Post-MVP:** a cozy dark theme (decision 6); per-person duo mapping (PTCG-031).
