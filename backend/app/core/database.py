"""Database engine & session dependency."""

from collections.abc import Generator

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
)

# pgvector is required by the Resolution Copilot chunk store. Create the extension
# before create_all so vector columns can be defined. Idempotent and safe to re-run.
with engine.begin() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

import app.models  # noqa: F401, E402 — ensures all models are registered before create_all
SQLModel.metadata.create_all(engine)

# create_all only creates missing tables; it never ALTERs an existing one. Add
# columns introduced after a table first shipped here, idempotently, so an
# already-provisioned database picks them up on the next boot.
with engine.begin() as conn:
    conn.execute(
        text(
            "ALTER TABLE correlation_rules "
            "ADD COLUMN IF NOT EXISTS actions jsonb NOT NULL DEFAULT '[\"aggregate\"]'::jsonb"
        )
    )
    conn.execute(
        text(
            "ALTER TABLE correlation_rules "
            "ADD COLUMN IF NOT EXISTS email_recipients jsonb NOT NULL DEFAULT '[]'::jsonb"
        )
    )
    conn.execute(
        text(
            "ALTER TABLE correlation_rules "
            "ADD COLUMN IF NOT EXISTS slack_channels jsonb NOT NULL DEFAULT '[]'::jsonb"
        )
    )
    conn.execute(
        text(
            "ALTER TABLE correlation_rules "
            "ADD COLUMN IF NOT EXISTS last_triggered_at timestamptz"
        )
    )
    conn.execute(
        text(
            "ALTER TABLE incidents "
            "ADD COLUMN IF NOT EXISTS linked_alert_ids jsonb NOT NULL DEFAULT '[]'::jsonb"
        )
    )
    # Links an aggregate to the alerts-feed row that mirrors it.
    conn.execute(
        text(
            "ALTER TABLE aggregated_alerts "
            "ADD COLUMN IF NOT EXISTS summary_alert_id uuid"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_aggregated_alerts_summary_alert_id "
            "ON aggregated_alerts (summary_alert_id)"
        )
    )
    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS email varchar"))
    conn.execute(
        text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)")
    )
    conn.execute(
        text(
            "UPDATE users SET email = username "
            "WHERE email IS NULL AND username LIKE '%@%'"
        )
    )
    # Backfill pre-existing incidents so their single link shows up in the list.
    conn.execute(
        text(
            "UPDATE incidents SET linked_alert_ids = jsonb_build_array(linked_alert_id::text) "
            "WHERE linked_alert_ids = '[]'::jsonb AND linked_alert_id IS NOT NULL"
        )
    )
    # aggregated_alerts.rule_id originally blocked deleting any rule that had
    # ever grouped something (raw 500). Deleting a rule now nulls the link and
    # keeps the aggregate, which already snapshots rule_name.
    conn.execute(
        text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'aggregated_alerts_rule_id_fkey'
                      AND confdeltype <> 'n'
                ) THEN
                    ALTER TABLE aggregated_alerts
                        DROP CONSTRAINT aggregated_alerts_rule_id_fkey;
                    ALTER TABLE aggregated_alerts
                        ALTER COLUMN rule_id DROP NOT NULL;
                    ALTER TABLE aggregated_alerts
                        ADD CONSTRAINT aggregated_alerts_rule_id_fkey
                        FOREIGN KEY (rule_id) REFERENCES correlation_rules (id)
                        ON DELETE SET NULL;
                END IF;
            END $$;
            """
        )
    )
    # Incident timestamps were naive UTC; convert to timestamptz (values were
    # already UTC). Guarded so it only runs once.
    conn.execute(
        text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'incidents'
                      AND column_name = 'created_at'
                      AND data_type = 'timestamp without time zone'
                ) THEN
                    ALTER TABLE incidents
                        ALTER COLUMN created_at TYPE timestamptz
                            USING created_at AT TIME ZONE 'UTC',
                        ALTER COLUMN updated_at TYPE timestamptz
                            USING updated_at AT TIME ZONE 'UTC';
                    ALTER TABLE incidents
                        ALTER COLUMN created_at SET DEFAULT now(),
                        ALTER COLUMN updated_at SET DEFAULT now();
                END IF;
            END $$;
            """
        )
    )

# Indexes backing the feed's filter dropdowns, so each filter's DISTINCT runs as
# an index-only scan instead of a full table scan. Built CONCURRENTLY (which
# cannot run inside a transaction) so they never lock the alerts table for writes
# while building on an already-large database.
with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
    conn.execute(
        text("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_alerts_region ON alerts (region)")
    )
    conn.execute(
        text("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_alerts_severity ON alerts (severity)")
    )
    conn.execute(
        text("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_alerts_status ON alerts (status)")
    )
    conn.execute(
        text(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_alerts_source "
            "ON alerts ((extra_fields->>'source'))"
        )
    )


def get_session() -> Generator[Session, None, None]:
    """Yield a database session."""
    with Session(engine) as session:
        yield session
