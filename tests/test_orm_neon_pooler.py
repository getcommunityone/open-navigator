"""The ORM engine must not send a startup search_path to Neon's pooler (#367)."""

from __future__ import annotations

from api import database


def test_pooled_neon_host_sends_no_startup_options():
    url = "postgresql://u:p@ep-noisy-fire-abc-pooler.c-6.us-east-1.aws.neon.tech/db?sslmode=require"
    assert database.orm_connect_args(url) == {}


def test_unpooled_host_keeps_the_search_path_pin():
    url = "postgresql://u:p@ep-noisy-fire-abc.c-6.us-east-1.aws.neon.tech/db?sslmode=require"
    args = database.orm_connect_args(url)
    assert args == {"options": f"-csearch_path={database._ORM_SEARCH_PATH}"}


def test_local_host_keeps_the_search_path_pin():
    args = database.orm_connect_args("postgresql://postgres:postgres@localhost:5433/open_navigator")
    assert "options" in args
