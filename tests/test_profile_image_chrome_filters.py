"""Reject accessibility-plugin flags and other non-person profile image jobs."""

from scripts.discovery.contact_profile_images import extract_profile_image_jobs


def test_onetap_language_flags_not_profile_jobs():
    html = """
    <img alt="flag" src="https://dalecountyal.org/wp-content/plugins/accessibility-plugin-onetap-pro/assets/images/english.png" />
    <img alt="flag" src="https://dalecountyal.org/wp-content/plugins/accessibility-plugin-onetap-pro/assets/images/german.png" />
    <img alt="icon-drop-down-menu" src="https://dalecountyal.org/wp-content/plugins/accessibility-plugin-onetap-pro/assets/images/icon-drop-down-menu.png" />
    """
    jobs = extract_profile_image_jobs(html, "https://dalecountyal.org/")
    assert jobs == []


def test_real_commissioner_portrait_still_extracted():
    html = """
    <figure class="wp-caption alignnone">
      <img alt="Adam Enfinger" src="https://dalecountyal.org/wp-content/uploads/adam.jpg" class="wp-image-99" />
      <figcaption><strong>Adam Enfinger</strong><br />District 1</figcaption>
    </figure>
    """
    jobs = extract_profile_image_jobs(html, "https://dalecountyal.org/commissioners/")
    assert len(jobs) == 1
    assert jobs[0]["person_name"] == "Adam Enfinger"
