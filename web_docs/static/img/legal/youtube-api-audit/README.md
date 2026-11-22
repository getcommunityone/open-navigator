# YouTube Data API audit screenshots (one file per form field)

Captured from the live site after #723 / #724. **One JPEG per upload.**

| Upload this file | Form field | What’s in the image |
|------------------|------------|---------------------|
| `Privacy-Policy-Screenshots.jpeg` | Privacy Policy Screenshots | §9 YouTube API Services, Google Privacy Policy link, §9.1–9.3 including deletion |
| `Homepage-Screenshot.jpeg` | Homepage Screenshot | Live product home (`https://www.communityone.com/`) — current Open Navigator hero |
| `Homepage-Docs-Footer-Privacy-YouTube.jpeg` | *(optional companion)* | Docs site footer with **Privacy Policy** + **YouTube** highlighted |
| `Homepage-App-Footer.jpeg` | *(optional companion)* | Product home footer (social YouTube + site nav) |
| `Terms-of-Service-Documentation.jpeg` | Terms of Service Documentation | YouTube API Services + agreement to YouTube Terms of Service |
| `architecture-diagram.png` | Architecture Diagram | YouTube Data API v3 → scrapers → warehouse → embed (no uploads) |
| `user-flow-diagram.png` | User Flow Diagrams | Citizen watch path; OAuth/upload explicitly out of scope |
| `other-supporting-no-youtube-upload.png` | Other Supporting Materials | Statement that upload script/screencast is N/A |

Editable draw.io sources (HTL / milliman helper pattern): `yt1_architecture.drawio`, `yt2_user_flow.drawio`
(also under `diagrams/youtube-api-audit/`). Rebuild with `diagrams/youtube-api-audit/_build/render_png.py`.

**Upload script / YouTube upload screencast:** not applicable — CommunityOne does not upload videos.

Live URLs:

- https://www.communityone.com/
- https://www.communityone.com/docs/legal/privacy-policy/#9-youtube-api-services
- https://www.communityone.com/docs/
- https://www.communityone.com/docs/legal/terms-of-service

Recapture homepage shots after UI changes with Playwright against the live URLs (see PR history for #725 / #726).
