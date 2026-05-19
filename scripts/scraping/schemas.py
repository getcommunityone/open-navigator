"""Pydantic schemas for structured jurisdiction page extraction."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class MeetingRow(BaseModel):
    title: str = Field(description="Meeting or hearing title")
    meeting_date: Optional[str] = Field(
        default=None,
        description="Primary meeting date in YYYY-MM-DD when clear; else ISO or human text",
    )
    agenda_url: Optional[str] = Field(default=None, description="Link to agenda PDF or page")
    minutes_url: Optional[str] = Field(default=None, description="Link to minutes PDF or page")
    location: Optional[str] = Field(default=None, description="Meeting location if stated")


class ContactRow(BaseModel):
    name: Optional[str] = Field(default=None, description="Person or office name")
    role: Optional[str] = Field(default=None, description="Title or role")
    email: Optional[str] = Field(default=None, description="Email address")
    phone: Optional[str] = Field(default=None, description="Phone number")


class JurisdictionPageExtraction(BaseModel):
    """Structured fields extracted from a government web page."""

    jurisdiction_name: Optional[str] = Field(
        default=None,
        description="City, county, board, or department name on the page",
    )
    page_summary: Optional[str] = Field(
        default=None,
        description="One-sentence summary of what this page is about",
    )
    meetings: List[MeetingRow] = Field(
        default_factory=list,
        description="Public meetings, hearings, or agendas listed on the page",
    )
    contacts: List[ContactRow] = Field(
        default_factory=list,
        description="Official contacts found on the page",
    )
    contact_email: Optional[str] = Field(
        default=None,
        description="Primary general contact email if one is prominent",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Caveats, ambiguous dates, or missing data",
    )
