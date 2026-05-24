"""WordPress figure.wp-caption commissioner roster extraction."""

from scripts.discovery.contact_extract_from_html import (
    extract_structured_contacts_from_html,
    extract_wp_caption_figure_contacts_from_html,
)
from scripts.discovery.contact_profile_images import extract_profile_image_jobs


def test_choctaw_county_commission_wp_captions():
    html = """
    <figure class="wp-caption alignnone">
      <img src="https://www.choctawcountyal.org/wp-content/uploads/2023/05/TonyCherry.jpg"
           alt="Tony L. Cherry" class="wp-image-223" />
      <figcaption class="wp-caption-text">
        <strong>Tony L. Cherry</strong><br />District 1<br />
        <a href="mailto:mr_tc1@yahoo.com">mr_tc1@yahoo.com</a>
      </figcaption>
    </figure>
    <figure class="wp-caption alignnone">
      <img src="https://www.choctawcountyal.org/wp-content/uploads/2023/05/VictorJackson.jpg"
           alt="Victor Jackson" />
      <figcaption class="wp-caption-text">
        <strong>Victor Jackson</strong><br />District 2<br />
        <a href="mailto:jacksondistrict2@outlook.com">jacksondistrict2@outlook.com</a><br />
        1-334-643-7990
      </figcaption>
    </figure>
    """
    url = "https://www.choctawcountyal.org/board-of-commissioners/"
    rows = extract_wp_caption_figure_contacts_from_html(html, url)
    assert len(rows) == 2
    tony = next(r for r in rows if r["person_name"] == "Tony L. Cherry")
    assert tony["email"] == "mr_tc1@yahoo.com"
    assert tony["department"] == "District 1"
    assert "TonyCherry.jpg" in (tony.get("profile_image_url") or "")

    victor = next(r for r in rows if r["person_name"] == "Victor Jackson")
    assert victor["phone"] == "1-334-643-7990"

    jobs = extract_profile_image_jobs(html, url)
    assert len(jobs) == 2
    assert all(j["match_method"] == "wp_caption_figure" for j in jobs)
    assert {j["person_name"] for j in jobs} == {"Tony L. Cherry", "Victor Jackson"}

    all_rows = extract_structured_contacts_from_html(html, url)
    assert len(all_rows) == 2
    assert not any("Notice of Intent" in str(r.get("person_name") or "") for r in all_rows)
