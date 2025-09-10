-- ========================================
-- SCHEMA: Core Entities
-- ========================================

CREATE TABLE users (
  user_id      BIGSERIAL PRIMARY KEY,
  first_name   TEXT NOT NULL,
  last_name    TEXT NOT NULL,
  user_kind_id SMALLINT NOT NULL REFERENCES user_kinds(user_kind_id) ON DELETE RESTRICT,
  is_active    BOOLEAN NOT NULL DEFAULT TRUE,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE suppliers (
  supplier_id      BIGSERIAL PRIMARY KEY,
  supplier_name    TEXT NOT NULL,
  supplier_type_id SMALLINT NOT NULL REFERENCES supplier_types(supplier_type_id) ON DELETE RESTRICT,
  payment_terms    TEXT,
  is_active        BOOLEAN NOT NULL DEFAULT TRUE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (supplier_name)
);

CREATE TABLE contracts (
  contract_id        BIGSERIAL PRIMARY KEY,
  supplier_id        BIGINT NOT NULL REFERENCES suppliers(supplier_id) ON DELETE RESTRICT,
  payment_conditions TEXT,
  total_price        NUMERIC(12,2),
  contract_date      DATE NOT NULL,
  contract_path      TEXT,
  valid_from         DATE NOT NULL,
  valid_to           DATE,
  CHECK (valid_to IS NULL OR valid_to >= valid_from)
);

CREATE TABLE events (
  event_id   BIGSERIAL PRIMARY KEY,
  celeb_id   BIGINT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
  title      TEXT,
  location   TEXT,
  event_date DATE NOT NULL,
  event_time TIME,
  guests_num INTEGER CHECK (guests_num >= 0),
  status     TEXT NOT NULL DEFAULT 'PLANNED',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE event_venues (
  venue_id         BIGSERIAL PRIMARY KEY,
  event_id         BIGINT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
  venue_name       TEXT NOT NULL,
  max_guests       INTEGER CHECK (max_guests > 0),
  agreed_price     NUMERIC(12,2),
  include_sound    BOOLEAN NOT NULL DEFAULT FALSE,
  sound_price      NUMERIC(12,2),
  include_design   BOOLEAN NOT NULL DEFAULT FALSE,
  design_price     NUMERIC(12,2),
  include_lighting BOOLEAN NOT NULL DEFAULT FALSE,
  lighting_price   NUMERIC(12,2),
  include_bar      BOOLEAN NOT NULL DEFAULT FALSE,
  bar_price        NUMERIC(12,2),
  is_selected      BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE UNIQUE INDEX ux_event_venues_selected
  ON event_venues (event_id)
  WHERE is_selected = TRUE;

CREATE TABLE event_suppliers (
  list_id                 BIGSERIAL PRIMARY KEY,
  event_id                BIGINT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
  supplier_id             BIGINT NOT NULL REFERENCES suppliers(supplier_id) ON DELETE RESTRICT,
  contract_id             BIGINT REFERENCES contracts(contract_id) ON DELETE RESTRICT,
  supplier_name_snapshot  TEXT NOT NULL,
  supplier_agreed_price   NUMERIC(12,2) NOT NULL,
  payment_conditions_snap TEXT,
  contract_total_price    NUMERIC(12,2),
  is_confirmed            BOOLEAN NOT NULL DEFAULT FALSE,
  notes                   TEXT,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (event_id, supplier_id)
);


  CREATE TABLE tasks (
  task_id             BIGSERIAL PRIMARY KEY,
  event_id            BIGINT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
  task_text           TEXT NOT NULL,
  prev_task_id        BIGINT REFERENCES tasks(task_id) ON DELETE SET NULL,
  next_task_id        BIGINT REFERENCES tasks(task_id) ON DELETE SET NULL,
  task_category_id    SMALLINT REFERENCES task_categories(task_category_id) ON DELETE RESTRICT,
  responsible_user_id BIGINT REFERENCES users(user_id) ON DELETE SET NULL,
  task_eta            TIMESTAMPTZ,
  task_status_id      SMALLINT NOT NULL REFERENCES task_statuses(task_status_id) ON DELETE RESTRICT,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);



-- ========================================
-- SCHEMA: Preferences
-- ========================================

CREATE TABLE preference_definitions (
  pref_code      TEXT PRIMARY KEY,
  data_type      TEXT NOT NULL,
  default_value  JSONB,
  description    TEXT,
  is_active      BOOLEAN NOT NULL DEFAULT TRUE,
  display_order  INTEGER NOT NULL DEFAULT 100
);

CREATE TABLE user_preferences (
  user_id    BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  pref_code  TEXT   NOT NULL REFERENCES preference_definitions(pref_code) ON DELETE RESTRICT,
  value_json JSONB  NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, pref_code)
);

-- ========================================
-- Helpful indexes
-- ========================================

CREATE INDEX ix_events_celeb ON events (celeb_id, event_date);
CREATE INDEX ix_event_suppliers_event ON event_suppliers (event_id);
CREATE INDEX ix_event_suppliers_supplier ON event_suppliers (supplier_id);
CREATE INDEX ix_tasks_event ON tasks (event_id, task_status_id);
CREATE INDEX ix_event_venues_event ON event_venues (event_id);
CREATE INDEX ix_user_prefs_user ON user_preferences (user_id);