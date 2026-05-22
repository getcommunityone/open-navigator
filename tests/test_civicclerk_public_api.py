"""CivicClerk tenant detection and OData helpers."""

from scripts.discovery.civicclerk_public_api import (
    civicclerk_doc_type,
    civicclerk_portal_file_url,
    detect_civicclerk_tenant,
    event_needs_civicclerk_detail,
)


def test_detect_tenant_from_embed_props():
    html = '<script>window.clerkEmbedProps = {"tenant": "northportal"};</script>'
    assert detect_civicclerk_tenant(html=html) == "northportal"


def test_detect_tenant_from_portal_url():
    assert (
        detect_civicclerk_tenant(
            extra_urls=["https://northportal.portal.civicclerk.com/event/3539/files"]
        )
        == "northportal"
    )


def test_civicclerk_doc_type_mapping():
    assert civicclerk_doc_type("Agenda Packet", "Planning Commission Packet") == "agenda_packet"
    assert civicclerk_doc_type("Agenda", "Council Agenda") == "agenda"
    assert civicclerk_doc_type("Minutes", "") == "minutes"


def test_civicclerk_portal_file_url():
    pf = {"fileId": 3290, "type": "Agenda"}
    assert (
        civicclerk_portal_file_url("northportal", 3545, pf)
        == "https://northportal.portal.civicclerk.com/event/3545/files/agenda/3290"
    )


def test_event_needs_detail_from_published_files():
    ev = {
        "hasAgenda": False,
        "hasMedia": False,
        "agendaId": 0,
        "publishedFiles": [{"fileId": 1, "type": "Minutes", "name": "m"}],
    }
    assert event_needs_civicclerk_detail(ev) is True
