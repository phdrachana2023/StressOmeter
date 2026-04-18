-- ============================================================
--  OSI Stress Assessment — PostgreSQL Schema for Supabase
--  Run this in: Supabase Dashboard → SQL Editor → New Query
-- ============================================================


-- ── 1. USERS ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    username    TEXT        PRIMARY KEY,
    password    TEXT        NOT NULL,           -- SHA-256 hashed
    fullname    TEXT        NOT NULL,
    email       TEXT        NOT NULL,
    registered  TEXT        NOT NULL            -- 'YYYY-MM-DD HH:MM:SS'
);


-- ── 2. DEMOGRAPHICS ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS demographics (
    username        TEXT    PRIMARY KEY REFERENCES users(username) ON DELETE CASCADE,
    timestamp       TEXT,                       -- last updated
    full_name       TEXT,
    email           TEXT,
    contact         TEXT,
    institute       TEXT,
    teaching_level  TEXT,                       -- 'UG' | 'PG'
    gender          TEXT,                       -- 'Male' | 'Female'
    marital_status  TEXT,                       -- 'Married' | 'Unmarried'
    age_group       TEXT,                       -- '24-34' | '35-44' | '45-60 and above'
    education       TEXT,                       -- 'Graduate' | 'Post-Graduate' | 'MPhil' | 'PhD' | 'Others'
    designation     TEXT,                       -- 'Professor' | 'Associate Professor' etc.
    employment_type TEXT,                       -- 'Regular' | 'Contractual'
    experience      TEXT,                       -- '1-5 years' | '6-10 years' etc.
    tenure          TEXT                        -- 'Less than one year' | '1-5 years' etc.
);


-- ── 3. STRESS RESULTS ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stress_results (
    username         TEXT    PRIMARY KEY REFERENCES users(username) ON DELETE CASCADE,
    timestamp        TEXT,                      -- last assessed
    total_score      TEXT,                      -- 46–230
    overall_level    TEXT,                      -- 'Low' | 'Moderate' | 'High'
    assessment_type  TEXT,                      -- 'advanced' | 'basic'

    -- Sub-Scale I: Role Overload
    sub1        TEXT,   sub1_score  TEXT,   sub1_level  TEXT,
    -- Sub-Scale II: Role Ambiguity
    sub2        TEXT,   sub2_score  TEXT,   sub2_level  TEXT,
    -- Sub-Scale III: Role Conflict
    sub3        TEXT,   sub3_score  TEXT,   sub3_level  TEXT,
    -- Sub-Scale IV: Group & Political Pressure
    sub4        TEXT,   sub4_score  TEXT,   sub4_level  TEXT,
    -- Sub-Scale V: Responsibility for Persons
    sub5        TEXT,   sub5_score  TEXT,   sub5_level  TEXT,
    -- Sub-Scale VI: Under Participation
    sub6        TEXT,   sub6_score  TEXT,   sub6_level  TEXT,
    -- Sub-Scale VII: Powerlessness
    sub7        TEXT,   sub7_score  TEXT,   sub7_level  TEXT,
    -- Sub-Scale VIII: Poor Peer Relations
    sub8        TEXT,   sub8_score  TEXT,   sub8_level  TEXT,
    -- Sub-Scale IX: Intrinsic Impoverishment
    sub9        TEXT,   sub9_score  TEXT,   sub9_level  TEXT,
    -- Sub-Scale X: Low Status
    sub10       TEXT,   sub10_score TEXT,   sub10_level TEXT,
    -- Sub-Scale XI: Strenuous Working Conditions
    sub11       TEXT,   sub11_score TEXT,   sub11_level TEXT,
    -- Sub-Scale XII: Unprofitability
    sub12       TEXT,   sub12_score TEXT,   sub12_level TEXT,

    -- User's personal top 3 highest scoring subscales
    top1_subscale TEXT,  top1_label TEXT,  top1_score TEXT,  top1_level TEXT,
    top2_subscale TEXT,  top2_label TEXT,  top2_score TEXT,  top2_level TEXT,
    top3_subscale TEXT,  top3_label TEXT,  top3_score TEXT,  top3_level TEXT,

    -- ML model's fixed top 3 (from Random Forest feature importances)
    model_top1  TEXT,
    model_top2  TEXT,
    model_top3  TEXT
);


-- ── 4. FEEDBACK ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS feedback (
    username        TEXT    PRIMARY KEY REFERENCES users(username) ON DELETE CASCADE,
    feedback_text   TEXT    NOT NULL,
    rating          INTEGER CHECK (rating BETWEEN 1 AND 5),
    timestamp       TEXT    NOT NULL            -- 'YYYY-MM-DD HH:MM:SS'
);


-- ============================================================
--  VERIFY: run this after creation to confirm all 4 tables
-- ============================================================
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
