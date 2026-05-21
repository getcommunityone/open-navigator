"""CivicClerk tenant detection and OData helpers."""

from scripts.discovery.civicclerk_public_api import (
    civicclerk_doc_type,
    detect_civicclerk_tenant,
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
    assert civicclerk_doc_type("Agenda Packet", "Planning Commission Packet") == "agenda"
    assert civicclerk_doc_type("Minutes", "") == "minutes"
