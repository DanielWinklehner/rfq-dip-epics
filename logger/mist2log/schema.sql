-- Schema of the MIST-2 data logger (docs/emulation/LOGGER.md, "Data model"). Applied by the logger
-- at every start (store.py); every statement can run again. Life times (retention policies) and
-- chunk sizes are set by store.py from the registry's tiers, not here.
--
-- TimescaleDB features used: hypertables, time_bucket (Apache 2.0 licence); retention policies
-- and the job scheduler that runs them (Timescale Licence, "community"). Nothing else.

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- One row per logged PV, written by the logger from the registry at its start.
CREATE TABLE IF NOT EXISTS pv (
    id          serial PRIMARY KEY,
    name        text UNIQUE NOT NULL,
    tier        text NOT NULL,          -- raw, seconds, minutes, events (none: no longer logged)
    kind        text NOT NULL,          -- number, enum, text
    type        text,                   -- record type
    egu         text,
    states      text[],                 -- words of an enumeration, index = value
    device      text,
    role        text,
    connected   boolean NOT NULL DEFAULT false,
    since       timestamptz,            -- of the connection state
    severity    smallint,               -- last severity written to the event log
    value_text  text                    -- last value of an events PV written to the event log
);

-- The tiers as the plan defines them (plan/controls.yaml, software.tiers), written at the start.
CREATE TABLE IF NOT EXISTS tier (
    id        text PRIMARY KEY,
    interval  double precision,       -- seconds; NULL: as sampled or on change
    keep_days double precision        -- NULL: for ever
);

-- Tier 1 (raw PVs) and events (events PVs): every monitor update. severity NULL: a gap (no value
-- from here on). flags: 1 clock, 2 never processed, 4 resumed, 8 gap written by the logger (core.py).
CREATE TABLE IF NOT EXISTS raw (
    pv        integer NOT NULL,
    t         timestamptz NOT NULL,
    value     double precision,         -- number, or the number of an enumeration; NULL for a text
    text      text,                     -- the state word of an enumeration, or the text
    severity  smallint,
    status    smallint,
    flags     smallint NOT NULL DEFAULT 0
);
SELECT create_hypertable('raw', 't', if_not_exists => true);
CREATE INDEX IF NOT EXISTS raw_pv_t ON raw (pv, t DESC);

CREATE TABLE IF NOT EXISTS changes (LIKE raw INCLUDING DEFAULTS);
SELECT create_hypertable('changes', 't', if_not_exists => true);
CREATE INDEX IF NOT EXISTS changes_pv_t ON changes (pv, t DESC);

-- Tiers 2 and 3: one row per interval in which something happened (core.py, Interval).
CREATE TABLE IF NOT EXISTS seconds (
    pv            integer NOT NULL,
    t             timestamptz NOT NULL,   -- start of the interval
    mean          double precision,       -- over the time with a valid value; NULL: none
    min           double precision,
    max           double precision,
    valid         real NOT NULL,          -- share of the interval with a valid value
    severity      smallint,               -- worst severity (not connected counts as INVALID)
    last          double precision,       -- the valid value at its end, NULL: none
    last_severity smallint,
    PRIMARY KEY (pv, t)
);
SELECT create_hypertable('seconds', 't', if_not_exists => true);
CREATE TABLE IF NOT EXISTS minutes (LIKE seconds INCLUDING ALL);
SELECT create_hypertable('minutes', 't', if_not_exists => true);

-- The event log, kept for ever. kind: set (a written PV changed), state (another events PV
-- changed), alarm (old, new: severity), connection (lost, back), logger (its own events).
CREATE TABLE IF NOT EXISTS events (
    t         timestamptz NOT NULL,
    pv        integer,
    kind      text NOT NULL,
    old       text,
    new       text,
    value     double precision,
    severity  smallint,
    status    smallint,
    detail    text
);
CREATE INDEX IF NOT EXISTS events_t ON events (t);
CREATE INDEX IF NOT EXISTS events_pv_t ON events (pv, t);

-- How far the data is complete, written with every batch: what lies after it is not known yet
-- (or never, when the logger stopped). One row.
CREATE TABLE IF NOT EXISTS state (
    id               integer PRIMARY KEY CHECK (id = 1),
    started          timestamptz,
    alive            timestamptz,
    raw_through      timestamptz,
    seconds_through  timestamptz,
    minutes_through  timestamptz
);

CREATE OR REPLACE VIEW event_log AS
    SELECT e.t, e.kind, p.name AS pv, p.device, e.old, e.new, e.value,
           (ARRAY['NO_ALARM', 'MINOR', 'MAJOR', 'INVALID'])[e.severity + 1] AS severity, e.detail
    FROM events e LEFT JOIN pv p ON p.id = e.pv;

-- ----------------------------------------------------------------------------------------------
-- Reading. These functions hide how constant values and gaps are stored: they return the value
-- at each time, or a gap. kind: 'value' (a stored row), 'held' (the value in effect, repeated
-- where the reader needs it), 'gap' (no valid value: not connected, INVALID, the logger not
-- running, rows lost, or not written yet).

-- Tier raw (table raw) or events (table changes): the value in effect at `from` (held), every
-- row in [from, to), and the end: the value held at `to`, or a gap where the data ends.
CREATE OR REPLACE FUNCTION log_rows(p_pv integer, p_table text, p_from timestamptz, p_to timestamptz)
RETURNS TABLE (t timestamptz, value double precision, text text, severity smallint, kind text)
LANGUAGE plpgsql STABLE AS $$
#variable_conflict use_column
DECLARE
    through timestamptz;
BEGIN
    SELECT s.raw_through INTO through FROM state s;
    RETURN QUERY EXECUTE format($q$
        WITH r AS (
            (SELECT $2::timestamptz AS t, x.value, x.text, x.severity, 'held'::text AS kind, 0 AS o
               FROM %1$I x WHERE x.pv = $1 AND x.t < $2 ORDER BY x.t DESC LIMIT 1)
            UNION ALL
            SELECT x.t, x.value, x.text, x.severity, 'value', 1
              FROM %1$I x WHERE x.pv = $1 AND x.t >= $2 AND x.t < $3),
        k AS (SELECT r.t, r.value, r.text, r.severity,
                     CASE WHEN r.severity IS NULL OR r.severity >= 3 THEN 'gap' ELSE r.kind END AS kind, r.o
                FROM r),
        z AS (SELECT * FROM k ORDER BY k.t DESC, k.o DESC LIMIT 1),
        out AS (
            SELECT k.t, k.value, k.text, k.severity, k.kind, k.o FROM k   -- a row at `from` itself wins
             WHERE NOT (k.o = 0 AND EXISTS (SELECT 1 FROM k AS k2 WHERE k2.o = 1 AND k2.t = $2))
            UNION ALL
            SELECT CASE WHEN $4 < $3 THEN greatest($4, z.t) ELSE $3 END,
                   CASE WHEN $4 < $3 THEN NULL ELSE z.value END,
                   CASE WHEN $4 < $3 THEN NULL ELSE z.text END,
                   CASE WHEN $4 < $3 THEN NULL ELSE z.severity END,
                   CASE WHEN $4 < $3 THEN 'gap' ELSE 'held' END, 2
              FROM z WHERE $4 < $3 OR z.kind <> 'gap'
            UNION ALL
            SELECT $2, NULL, NULL, NULL, 'gap', 0 WHERE NOT EXISTS (SELECT 1 FROM k))
        SELECT out.t, out.value, out.text, out.severity, out.kind FROM out ORDER BY out.t, out.o
    $q$, p_table)
    USING p_pv, p_from, p_to, coalesce(through, '-infinity'::timestamptz);
END $$;

-- Tier seconds or minutes: one row per interval that starts in [from, to): its own row, or the
-- end state of the row before it (a valid value: mean = min = max = it, valid 1), or a gap.
-- Intervals after the last one written are gaps.
CREATE OR REPLACE FUNCTION log_buckets(p_pv integer, p_tier text, p_from timestamptz, p_to timestamptz)
RETURNS TABLE (t timestamptz, mean double precision, min double precision, max double precision,
               valid real, severity smallint, kind text)
LANGUAGE plpgsql STABLE AS $$
#variable_conflict use_column
DECLARE
    w interval := CASE p_tier WHEN 'seconds' THEN interval '1 second' ELSE interval '1 minute' END;
    through timestamptz;
BEGIN
    SELECT CASE p_tier WHEN 'seconds' THEN s.seconds_through ELSE s.minutes_through END INTO through FROM state s;
    RETURN QUERY EXECUTE format($q$
        WITH g AS (SELECT gs AS t FROM generate_series(time_bucket($4, $2), $3 - interval '1 microsecond', $4) gs),
        r AS (
            (SELECT x.* FROM %1$I x WHERE x.pv = $1 AND x.t < time_bucket($4, $2) ORDER BY x.t DESC LIMIT 1)
            UNION ALL
            SELECT x.* FROM %1$I x WHERE x.pv = $1 AND x.t >= time_bucket($4, $2) AND x.t < $3),
        j AS (SELECT coalesce(g.t, r.t) AS t, g.t IS NOT NULL AS ing, r.pv IS NOT NULL AS stored,
                     r.mean, r.min, r.max, r.valid, r.severity, r.last, r.last_severity
                FROM g FULL JOIN r ON r.t = g.t),
        k AS (SELECT j.*, count(*) FILTER (WHERE j.stored) OVER (ORDER BY j.t) AS grp FROM j),
        m AS (SELECT k.*, first_value(k.last) OVER c AS c_last, first_value(k.last_severity) OVER c AS c_sev,
                     first_value(k.stored) OVER c AS c_has
                FROM k WINDOW c AS (PARTITION BY k.grp ORDER BY k.t)),
        n AS (SELECT m.*, CASE WHEN m.t >= $5 THEN 'gap'
                               WHEN m.stored THEN CASE WHEN m.valid > 0 THEN 'value' ELSE 'gap' END
                               WHEN m.c_has AND m.c_last IS NOT NULL AND m.c_sev < 3 THEN 'held'
                               ELSE 'gap' END AS kind
                FROM m WHERE m.ing)
        SELECT n.t,
               CASE n.kind WHEN 'value' THEN n.mean WHEN 'held' THEN n.c_last END,
               CASE n.kind WHEN 'value' THEN n.min WHEN 'held' THEN n.c_last END,
               CASE n.kind WHEN 'value' THEN n.max WHEN 'held' THEN n.c_last END,
               CASE n.kind WHEN 'value' THEN n.valid WHEN 'held' THEN 1::real ELSE 0::real END,
               CASE WHEN n.t >= $5 THEN NULL WHEN n.stored THEN n.severity WHEN n.c_has THEN n.c_sev
                    ELSE NULL END::smallint,
               n.kind
          FROM n ORDER BY n.t
    $q$, p_tier)
    USING p_pv, p_from, p_to, w, coalesce(through, '-infinity'::timestamptz);
END $$;

-- The tier a reader gets for 'best': the finest one the PV is kept in whose life time covers
-- `from` and that gives at most p_max_points rows (raw counted at 10 per second, the fastest PVs).
CREATE OR REPLACE FUNCTION log_best(p_pv integer, p_from timestamptz, p_to timestamptz, p_max_points integer)
RETURNS text LANGUAGE sql STABLE AS $$
    WITH p AS (SELECT tier FROM pv WHERE id = p_pv),
    span AS (SELECT extract(epoch FROM p_to - p_from) AS s),
    k AS (SELECT id, keep_days FROM tier)
    SELECT CASE
        WHEN p.tier = 'events' THEN 'events'
        WHEN p.tier = 'raw' AND span.s * 10 <= p_max_points
             AND (SELECT keep_days IS NULL OR p_from >= now() - keep_days * interval '1 day' FROM k WHERE id = 'raw')
             THEN 'raw'
        WHEN p.tier IN ('raw', 'seconds') AND span.s <= p_max_points
             AND (SELECT keep_days IS NULL OR p_from >= now() - keep_days * interval '1 day' FROM k WHERE id = 'seconds')
             THEN 'seconds'
        ELSE 'minutes' END
    FROM p, span
$$;

-- One PV by name, one tier ('raw', 'events', 'seconds', 'minutes' or 'best'). value is the
-- value (raw, events) or the mean (seconds, minutes); a gap has value NULL.
CREATE OR REPLACE FUNCTION log_read(p_name text, p_from timestamptz, p_to timestamptz,
                                    p_tier text DEFAULT 'best', p_max_points integer DEFAULT 20000)
RETURNS TABLE (t timestamptz, value double precision, min double precision, max double precision,
               text text, severity smallint, valid real, kind text, tier text)
LANGUAGE plpgsql STABLE AS $$
#variable_conflict use_column
DECLARE
    p pv%ROWTYPE;
    use text;
BEGIN
    SELECT * INTO p FROM pv WHERE name = p_name;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'PV % is not logged', p_name;
    END IF;
    use := CASE WHEN p_tier = 'best' THEN log_best(p.id, p_from, p_to, p_max_points) ELSE p_tier END;
    IF use NOT IN ('raw', 'events', 'seconds', 'minutes')
       OR (use = 'events') <> (p.tier = 'events')
       OR (use = 'raw' AND p.tier <> 'raw') OR (use = 'seconds' AND p.tier NOT IN ('raw', 'seconds')) THEN
        RAISE EXCEPTION 'PV % is logged in tier %, it has no tier %', p_name, p.tier, use;
    END IF;
    IF use IN ('raw', 'events') THEN
        RETURN QUERY SELECT r.t, v.v, v.v, v.v, CASE WHEN r.kind = 'gap' THEN NULL ELSE r.text END, r.severity,
                            CASE r.kind WHEN 'gap' THEN 0::real ELSE 1::real END, r.kind, use
                       FROM log_rows(p.id, CASE use WHEN 'raw' THEN 'raw' ELSE 'changes' END, p_from, p_to) r,
                            LATERAL (SELECT CASE WHEN r.kind = 'gap' THEN NULL ELSE r.value END AS v) v;
    ELSE
        RETURN QUERY SELECT b.t, b.mean, b.min, b.max, NULL::text, b.severity, b.valid, b.kind, use
                       FROM log_buckets(p.id, use, p_from, p_to) b;
    END IF;
END $$;

-- For Grafana: several PVs as (time, metric, value), the tier chosen by the panel's interval,
-- intervals merged to the panel's step (mean weighted by the valid time). A gap is a NULL value.
CREATE OR REPLACE FUNCTION log_trend(p_names text[], p_from timestamptz, p_to timestamptz, p_step_ms bigint)
RETURNS TABLE ("time" timestamptz, metric text, value double precision)
LANGUAGE plpgsql STABLE AS $$
#variable_conflict use_column
DECLARE
    pv_name text;
    p pv%ROWTYPE;
    step double precision := greatest(p_step_ms, 1) / 1000.0;
    use text;
    w interval;
BEGIN
    FOREACH pv_name IN ARRAY p_names LOOP
        SELECT * INTO p FROM pv WHERE pv.name = pv_name;
        CONTINUE WHEN NOT FOUND OR p.tier = 'none';
        use := log_best(p.id, p_from, p_to, greatest(1, (extract(epoch FROM p_to - p_from) / step)::integer));
        IF use IN ('raw', 'events') THEN
            RETURN QUERY SELECT r.t, pv_name, CASE WHEN r.kind = 'gap' THEN NULL ELSE r.value END
                           FROM log_rows(p.id, CASE use WHEN 'raw' THEN 'raw' ELSE 'changes' END, p_from, p_to) r;
        ELSE
            w := CASE use WHEN 'seconds' THEN greatest(1, floor(step)) * interval '1 second'
                          ELSE greatest(1, floor(step / 60)) * interval '1 minute' END;
            RETURN QUERY SELECT time_bucket(w, b.t) AS tt, pv_name,
                                sum(b.mean * b.valid) / nullif(sum(b.valid) FILTER (WHERE b.mean IS NOT NULL), 0)
                           FROM log_buckets(p.id, use, p_from, p_to) b GROUP BY tt ORDER BY tt;
        END IF;
    END LOOP;
END $$;
