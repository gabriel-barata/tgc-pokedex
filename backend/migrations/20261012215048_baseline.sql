-- Create "series" table
CREATE TABLE "series" (
  "id" text NOT NULL,
  "name" text NOT NULL,
  "source" text NOT NULL,
  "fetched_at" timestamptz NOT NULL,
  CONSTRAINT "pk_series" PRIMARY KEY ("id")
);
-- Create "sync_runs" table
CREATE TABLE "sync_runs" (
  "id" uuid NOT NULL,
  "kind" text NOT NULL,
  "source" text NOT NULL,
  "status" text NOT NULL,
  "started_at" timestamptz NOT NULL,
  "finished_at" timestamptz NULL,
  "duration_ms" integer NULL,
  "result" jsonb NULL,
  "error" text NULL,
  CONSTRAINT "pk_sync_runs" PRIMARY KEY ("id")
);
-- Create "sets" table
CREATE TABLE "sets" (
  "id" text NOT NULL,
  "series_id" text NOT NULL,
  "name" text NOT NULL,
  "release_date" date NOT NULL,
  "official_count" integer NOT NULL,
  "total_count" integer NOT NULL,
  "logo_url" text NULL,
  "symbol_url" text NULL,
  "source" text NOT NULL,
  "fetched_at" timestamptz NOT NULL,
  CONSTRAINT "pk_sets" PRIMARY KEY ("id"),
  CONSTRAINT "fk_sets_series_id_series" FOREIGN KEY ("series_id") REFERENCES "series" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create index "ix_sets_series_id" to table: "sets"
CREATE INDEX "ix_sets_series_id" ON "sets" ("series_id");
-- Create "cards" table
CREATE TABLE "cards" (
  "id" text NOT NULL,
  "set_id" text NOT NULL,
  "collector_number" text NOT NULL,
  "name" text NOT NULL,
  "rarity" text NULL,
  "illustrator" text NULL,
  "image_url" text NULL,
  "variants" text[] NOT NULL,
  "source" text NOT NULL,
  "fetched_at" timestamptz NOT NULL,
  CONSTRAINT "pk_cards" PRIMARY KEY ("id"),
  CONSTRAINT "fk_cards_set_id_sets" FOREIGN KEY ("set_id") REFERENCES "sets" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT "ck_cards_variants_not_empty" CHECK (cardinality(variants) > 0)
);
-- Create index "ix_cards_set_id" to table: "cards"
CREATE INDEX "ix_cards_set_id" ON "cards" ("set_id");
-- Create "card_images" table
CREATE TABLE "card_images" (
  "card_id" text NOT NULL,
  "language" text NULL,
  "source" text NOT NULL,
  "fetched_at" timestamptz NOT NULL,
  CONSTRAINT "pk_card_images" PRIMARY KEY ("card_id"),
  CONSTRAINT "fk_card_images_card_id_cards" FOREIGN KEY ("card_id") REFERENCES "cards" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT "ck_card_images_language_known" CHECK (language = ANY (ARRAY['pt'::text, 'en'::text]))
);
-- Create "owners" table
CREATE TABLE "owners" (
  "id" uuid NOT NULL,
  "name" text NOT NULL,
  "created_at" timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT "pk_owners" PRIMARY KEY ("id"),
  CONSTRAINT "uq_owners_name" UNIQUE ("name")
);
-- Create "ownership" table
CREATE TABLE "ownership" (
  "owner_id" uuid NOT NULL,
  "card_id" text NOT NULL,
  "variant" text NOT NULL,
  "quantity" integer NOT NULL,
  CONSTRAINT "pk_ownership" PRIMARY KEY ("owner_id", "card_id", "variant"),
  CONSTRAINT "fk_ownership_card_id_cards" FOREIGN KEY ("card_id") REFERENCES "cards" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT "fk_ownership_owner_id_owners" FOREIGN KEY ("owner_id") REFERENCES "owners" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT "ck_ownership_quantity_in_range" CHECK ((quantity >= 0) AND (quantity <= 999))
);
-- Create "set_artwork" table
CREATE TABLE "set_artwork" (
  "set_id" text NOT NULL,
  "kind" text NOT NULL,
  "source" text NOT NULL,
  "fetched_at" timestamptz NOT NULL,
  CONSTRAINT "pk_set_artwork" PRIMARY KEY ("set_id", "kind"),
  CONSTRAINT "fk_set_artwork_set_id_sets" FOREIGN KEY ("set_id") REFERENCES "sets" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT "ck_set_artwork_kind_known" CHECK (kind = ANY (ARRAY['logo'::text, 'symbol'::text]))
);
-- Create "tracked_sets" table
CREATE TABLE "tracked_sets" (
  "owner_id" uuid NOT NULL,
  "set_id" text NOT NULL,
  "tracked_at" timestamptz NOT NULL,
  CONSTRAINT "pk_tracked_sets" PRIMARY KEY ("owner_id", "set_id"),
  CONSTRAINT "fk_tracked_sets_owner_id_owners" FOREIGN KEY ("owner_id") REFERENCES "owners" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT "fk_tracked_sets_set_id_sets" FOREIGN KEY ("set_id") REFERENCES "sets" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create index "ix_tracked_sets_set_id" to table: "tracked_sets"
CREATE INDEX "ix_tracked_sets_set_id" ON "tracked_sets" ("set_id");

-- Seed the household owner
INSERT INTO "owners" ("id", "name") VALUES ('9fb0c458-5ccf-477a-945e-276438b0f310', 'Casa');
