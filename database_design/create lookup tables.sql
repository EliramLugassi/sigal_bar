-- ========================================
-- SCHEMA: Lookup Tables (programmable lists)
-- ========================================

CREATE TABLE user_kinds (
  user_kind_id   SMALLSERIAL PRIMARY KEY,
  code           TEXT NOT NULL UNIQUE,
  label          TEXT NOT NULL,
  is_active      BOOLEAN NOT NULL DEFAULT TRUE,
  display_order  INTEGER NOT NULL DEFAULT 100
);

CREATE TABLE supplier_types (
  supplier_type_id SMALLSERIAL PRIMARY KEY,
  code             TEXT NOT NULL UNIQUE,
  label            TEXT NOT NULL,
  is_active        BOOLEAN NOT NULL DEFAULT TRUE,
  display_order    INTEGER NOT NULL DEFAULT 100
);

CREATE TABLE task_statuses (
  task_status_id SMALLSERIAL PRIMARY KEY,
  code           TEXT NOT NULL UNIQUE,
  label          TEXT NOT NULL,
  is_active      BOOLEAN NOT NULL DEFAULT TRUE,
  display_order  INTEGER NOT NULL DEFAULT 100
);

CREATE TABLE task_categories (
  task_category_id SMALLSERIAL PRIMARY KEY,
  code             TEXT NOT NULL UNIQUE,
  label            TEXT NOT NULL,
  is_active        BOOLEAN NOT NULL DEFAULT TRUE,
  display_order    INTEGER NOT NULL DEFAULT 100);