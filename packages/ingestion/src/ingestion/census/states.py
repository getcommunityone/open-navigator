#!/usr/bin/env python3
"""
Census states pipeline: load all US states into bronze_jurisdictions.

Ported from load_census_states.py to the core_lib DataSourcePipeline contract:
- Extract: the hardcoded US_STATES roster (50 states + DC + PR).
- Validate: each row through the StateRow pydantic schema.
- Load: framework-managed async session upserts into bronze_jurisdictions.

Run:
    python -m ingestion.census.states
    # or:
    python scripts/datasources/census/states_pipeline.py

Configuration:
    Connection target comes from NEON_DATABASE_URL_DEV / NEON_DATABASE_URL /
    DATABASE_URL (resolved by core_lib.db.engine), replacing the previous
    hardcoded localhost:5433 / open_navigator_bronze credentials.
"""
from __future__ import annotations

import asyncio
from typing import AsyncIterator

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


# All 50 states + DC + PR with FIPS codes
US_STATES: list[tuple[str, str, str]] = [
    ('AL', 'Alabama', '01'),
    ('AK', 'Alaska', '02'),
    ('AZ', 'Arizona', '04'),
    ('AR', 'Arkansas', '05'),
    ('CA', 'California', '06'),
    ('CO', 'Colorado', '08'),
    ('CT', 'Connecticut', '09'),
    ('DE', 'Delaware', '10'),
    ('DC', 'District of Columbia', '11'),
    ('FL', 'Florida', '12'),
    ('GA', 'Georgia', '13'),
    ('HI', 'Hawaii', '15'),
    ('ID', 'Idaho', '16'),
    ('IL', 'Illinois', '17'),
    ('IN', 'Indiana', '18'),
    ('IA', 'Iowa', '19'),
    ('KS', 'Kansas', '20'),
    ('KY', 'Kentucky', '21'),
    ('LA', 'Louisiana', '22'),
    ('ME', 'Maine', '23'),
    ('MD', 'Maryland', '24'),
    ('MA', 'Massachusetts', '25'),
    ('MI', 'Michigan', '26'),
    ('MN', 'Minnesota', '27'),
    ('MS', 'Mississippi', '28'),
    ('MO', 'Missouri', '29'),
    ('MT', 'Montana', '30'),
    ('NE', 'Nebraska', '31'),
    ('NV', 'Nevada', '32'),
    ('NH', 'New Hampshire', '33'),
    ('NJ', 'New Jersey', '34'),
    ('NM', 'New Mexico', '35'),
    ('NY', 'New York', '36'),
    ('NC', 'North Carolina', '37'),
    ('ND', 'North Dakota', '38'),
    ('OH', 'Ohio', '39'),
    ('OK', 'Oklahoma', '40'),
    ('OR', 'Oregon', '41'),
    ('PA', 'Pennsylvania', '42'),
    ('PR', 'Puerto Rico', '72'),
    ('RI', 'Rhode Island', '44'),
    ('SC', 'South Carolina', '45'),
    ('SD', 'South Dakota', '46'),
    ('TN', 'Tennessee', '47'),
    ('TX', 'Texas', '48'),
    ('UT', 'Utah', '49'),
    ('VT', 'Vermont', '50'),
    ('VA', 'Virginia', '51'),
    ('WA', 'Washington', '53'),
    ('WV', 'West Virginia', '54'),
    ('WI', 'Wisconsin', '55'),
    ('WY', 'Wyoming', '56'),
]


class StateRow(RawRow):
    """One US state, validated before upsert into bronze_jurisdictions."""

    state_code: str = Field(min_length=2, max_length=2)
    state_name: str = Field(min_length=1)
    fips_code: str = Field(min_length=2, max_length=2)
    geoid: str = Field(min_length=2, max_length=2)  # = fips_code for states


_UPSERT_SQL = text(
    """
    INSERT INTO bronze_jurisdictions (
        name, type, state_code, state, county, geoid, fips_code,
        ncsid, ansicode, population, area_sq_miles, source
    )
    VALUES (
        :state_name, 'state', :state_code, :state_name, 'All',
        :geoid, :fips_code, NULL, NULL, NULL, NULL, 'census_fips'
    )
    ON CONFLICT (name, type, state_code, county) DO UPDATE
    SET geoid = EXCLUDED.geoid,
        fips_code = EXCLUDED.fips_code,
        source = EXCLUDED.source
    """
)


class CensusStatesPipeline(DataSourcePipeline[StateRow]):
    source = "census_states"
    batch_size = 100  # 52 rows total; one batch comfortably
    row_schema = StateRow

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        for state_code, state_name, fips in US_STATES:
            yield {
                "source": self.source,
                "source_version": "2024",
                "natural_key": f"state:{state_code}",
                "state_code": state_code,
                "state_name": state_name,
                "fips_code": fips,
                "geoid": fips,
            }

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[StateRow],
        ctx: PipelineContext,
    ) -> None:
        params = [
            {
                "state_code": r.state_code,
                "state_name": r.state_name,
                "fips_code": r.fips_code,
                "geoid": r.geoid,
            }
            for r in rows
        ]
        await session.execute(_UPSERT_SQL, params)


if __name__ == "__main__":
    setup_logging()
    asyncio.run(CensusStatesPipeline().run())
