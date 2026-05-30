---
sidebar_position: 2
---

# Combining Data Sources

Each integration is useful on its own, but the distinctive value of Open Navigator
comes from **joining them**. Federal grant opportunities, political contributions,
IRS Form 990 filings, and jurisdiction/meeting data link together into a single
political-financial picture.

```
┌────────────────────────────────────────────────────────┐
│            OPEN NAVIGATOR DATA ECOSYSTEM                 │
├────────────────────────────────────────────────────────┤
│                                                          │
│  EXISTING DATA           NEW INTEGRATIONS                │
│  ──────────────          ────────────────                │
│                                                          │
│  IRS Form 990            Grants.gov API                  │
│  • 3M+ nonprofits   ───> • Grant opportunities           │
│  • Officers              • Deadlines                     │
│  • Financials            • Eligibility                   │
│  • Past grants                │                          │
│                               │                          │
│  Jurisdictions                │      FEC API             │
│  • 90k+ cities      ──────────┴───> • Political $$$      │
│  • Meetings                         • Donor networks     │
│  • Contacts                         • Influence          │
│                                                          │
│  UNIQUE VALUE: Complete political-financial picture      │
│  • Who donated → Which campaigns → Grant awards          │
│  • Timeline analysis: Donation → Policy → Funding        │
└────────────────────────────────────────────────────────┘
```

## How the sources connect

| Join                                   | Key                          | Reveals                                              |
| -------------------------------------- | ---------------------------- | ---------------------------------------------------- |
| IRS 990 officers → FEC contributions   | contributor name / employer  | Political engagement of nonprofit leadership         |
| Nonprofits → Grants.gov opportunities  | NTEE code / eligibility      | Funding a nonprofit is eligible to apply for         |
| FEC contributions → grant awards       | nonprofit EIN                | Whether political activity correlates with funding   |
| Jurisdictions → meetings → policy      | `state_code` / jurisdiction  | Where a policy is being debated and by whom          |

For the per-source clients, schemas, and worked code examples, see the dedicated
integration guides:

- **[Grants.gov API](./grants-gov-api.md)** — federal grant opportunities and matching
- **[FEC Political Contributions](./fec-political-contributions.md)** — donations and influence analysis
- **[FEC Campaign Finance](./fec-campaign-finance.md)** — bulk campaign-finance data

## Runnable demos

End-to-end demonstration scripts live in [`scripts/examples/`](https://github.com/) of the repository:

| Script                                  | What it shows                                                       |
| --------------------------------------- | ------------------------------------------------------------------- |
| `example_workflow.py`                   | The full policy-analysis pipeline across all agents                 |
| `full_demo.py`                          | A complete system demonstration                                     |
| `integration_demo.py`                   | Integration across multiple components                              |
| `legislative_map_demo.py`               | Legislative tracking and mapping                                    |
| `process_multiple_formats.py`           | Processing several document formats                                 |
| `tuscaloosa_accountability_report.py`   | Evidence-based accountability dashboard (case study)                |
| `tuscaloosa_decision_analysis.py`       | Decision-making pattern analysis (case study)                       |
| `tuscaloosa_political_economy.py`       | Political-economy analysis (case study)                             |

Before running a demo:

1. Activate the environment (`source .venv/bin/activate`).
2. Set the required API keys / environment variables (an FEC key from
   [api.data.gov/signup](https://api.data.gov/signup/) is needed for political-contribution demos).
3. Download any source data via the loaders in `scripts/datasources/`.
