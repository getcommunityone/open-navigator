"""The contact-form retention rule (#456): a 181-day-old row loses its email, a 179-day-old row keeps it."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from hosting.retention import contact_submission as cs

NOW = datetime(2026, 11, 18, 12, 0, 0, tzinfo=timezone.utc)


def _row_time(days_old: float) -> str:
    return (NOW - timedelta(days=days_old)).replace(microsecond=0).isoformat(sep=" ")


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    c.execute(
        "CREATE TABLE contact_submission ("
        "contact_submission_id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, sender_name TEXT NOT NULL, "
        "sender_email TEXT, subject TEXT NOT NULL, github_issue_number INTEGER, github_issue_url TEXT)"
    )
    rows = [
        (1, _row_time(181), "Old", "old@example.test", "s1", 11, "https://github.com/x/y/issues/11"),
        (2, _row_time(179), "Recent", "recent@example.test", "s2", 12, "https://github.com/x/y/issues/12"),
        (3, _row_time(400), "Already cleared", None, "s3", 13, "https://github.com/x/y/issues/13"),
        (4, _row_time(180.5), "Just over", "over@example.test", "s4", 14, None),
        (5, _row_time(0), "New", "new@example.test", "s5", None, None),
    ]
    c.executemany("INSERT INTO contact_submission VALUES (?,?,?,?,?,?,?)", rows)
    c.commit()
    yield c
    c.close()


def _emails(c) -> dict[int, str | None]:
    return dict(c.execute("SELECT contact_submission_id, sender_email FROM contact_submission"))


def test_a_181_day_old_row_loses_its_email_and_a_179_day_old_row_keeps_it(conn):
    cleared = cs.clear_expired_emails(conn, now=NOW, param="?")
    emails = _emails(conn)
    assert cleared == 2                      # rows 1 (181 days) and 4 (180.5 days); row 3 had no email already
    assert emails[1] is None and emails[4] is None
    assert emails[2] == "recent@example.test" and emails[5] == "new@example.test"
    assert emails[3] is None


def test_only_the_email_is_cleared_and_the_rest_of_the_row_stays(conn):
    cs.clear_expired_emails(conn, now=NOW, param="?")
    row = conn.execute("SELECT sender_name, subject, github_issue_number, github_issue_url, created_at "
                       "FROM contact_submission WHERE contact_submission_id = 1").fetchone()
    assert row == ("Old", "s1", 11, "https://github.com/x/y/issues/11", _row_time(181))


def test_dry_run_counts_and_changes_nothing(conn):
    before = _emails(conn)
    assert cs.clear_expired_emails(conn, now=NOW, dry_run=True, param="?") == 2
    assert _emails(conn) == before


def test_a_second_run_clears_nothing(conn):
    cs.clear_expired_emails(conn, now=NOW, param="?")
    assert cs.clear_expired_emails(conn, now=NOW, param="?") == 0


def test_the_retention_period_is_a_parameter_and_must_be_positive(conn):
    assert cs.clear_expired_emails(conn, days=30, now=NOW, dry_run=True, param="?") == 3  # rows 1, 2 and 4
    with pytest.raises(ValueError):
        cs.cutoff_for(0)


def test_the_cutoff_is_exactly_180_days_before_now():
    assert cs.cutoff_for(180, NOW) == "2026-05-22 12:00:00+00:00"


def test_main_refuses_a_non_postgres_url_and_prints_no_credentials(capsys):
    assert cs.main(["--database-url", "sqlite:///./data/users.db"]) == 2
    assert cs.main(["--database-url", "mysql://u:pw@h/db"]) == 2
    assert "pw" not in capsys.readouterr().out


def test_describe_target_drops_the_user_and_password():
    assert cs.describe_target("postgresql://user:secret@db.example.test:5432/app") == "db.example.test:5432/app"
