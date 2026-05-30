---
sidebar_position: 1
sidebar_label: Terms of Service
---

# Terms of Service

**Effective Date:** April 28, 2026  
**Last Updated:** April 28, 2026

:::info[Important Legal Agreement]
By accessing or using Open Navigator ("the Service"), you agree to be bound by these Terms of Service. If you do not agree to these terms, do not use the Service.
:::

## 1. Acceptance of Terms

These Terms of Service ("Terms") govern your access to and use of Open Navigator, a civic engagement platform operated by CommunityOne ("we," "us," or "our"). By accessing or using the Service, you agree to comply with these Terms and all applicable laws and regulations.

## 2. Description of Service

Open Navigator provides access to aggregated public data from government sources, nonprofit organizations, and civic engagement platforms to support informed democratic participation. The Service includes:

- Public meeting data and transcripts
- Nonprofit organization information
- Government jurisdiction data
- Election and ballot measure information
- Fact-checking resources
- Legislative tracking

## 3. Data Sources & Third-Party Terms

### 3.1 Incorporation of Third-Party Terms

Our Service aggregates data from multiple third-party sources, each with their own terms of service and use policies. **By using our Service, you agree to comply with all applicable third-party terms of service**, including but not limited to those listed in [Data Provider Terms of Service](./data-provider-terms.md).

### 3.2 Most Restrictive Terms Apply

Where our Terms conflict with third-party provider terms, **the most restrictive terms apply**. You are responsible for understanding and complying with all applicable terms.

### 3.3 Key Third-Party Restrictions

The following restrictions from our data providers apply to your use of the Service:

#### Google Services (BigQuery, Civic API, Data Commons)
- Must comply with [Google Cloud Terms of Service](https://cloud.google.com/terms)
- Must comply with [Google APIs Terms of Service](https://developers.google.com/terms)
- API quotas and rate limits apply
- Must display attribution: "Data provided by Google" where applicable
- Cannot cache Google Civic API data beyond 30 days

#### Charity Navigator
- Maximum 1,000 API calls per day (rate limit enforced)
- **MUST display attribution:** "Powered by Charity Navigator" on all pages using their data
- **MUST link** all charity names to their Charity Navigator profile pages
- **MUST include trademark notice:** "CHARITY NAVIGATOR and the CHARITY NAVIGATOR logo are registered trademarks of Charity Navigator. All rights reserved. Used with permission."
- Cannot redistribute Charity Navigator data
- Cannot create competing rating systems
- Caching permitted for performance only, not redistribution

#### ProPublica APIs (Nonprofit Explorer, Congress, Campaign Finance, Vital Signs)
- **MUST provide attribution** to ProPublica on all pages using their data
- Respectful rate limiting required (~1-5 requests/second depending on API)
- **FEC Campaign Finance Data:** Cannot use contributor information for commercial solicitation or fundraising
- Free for commercial and non-commercial use with attribution
- Rate limits: 5,000 requests/day (Congress API, Campaign Finance API)

#### Open States API
- Free tier: 50,000 requests/month
- **MUST display attribution:** "Powered by Open States" or similar
- API key required (free registration)
- Data licenses vary by state jurisdiction
- Must comply with API rate limits

#### Wikidata & DBpedia
- **Must respect rate limits** (1 request/second for Wikidata, 1-2 requests/second for DBpedia)
- **Must set descriptive User-Agent** header identifying your application
- Wikidata: CC0 Public Domain (attribution appreciated but not required)
- DBpedia: CC BY-SA 3.0 and GFDL (must provide attribution and share-alike)

#### Harvard Dataverse & Academic Datasets
- MeetingBank, LocalView: Research use licenses apply
- Must cite original research publications
- Cannot redistribute without permission
- Must comply with Harvard Dataverse terms of use

## 4. Acceptable Use

### 4.1 Permitted Uses

You may use the Service for:
- Personal civic engagement and research
- Academic and educational purposes
- Journalism and public interest reporting
- Non-commercial advocacy and organizing
- Commercial applications that comply with all provider terms

### 4.2 Prohibited Uses

You may NOT:
- Use FEC campaign finance data for commercial solicitation or fundraising
- Redistribute Charity Navigator data or create competing rating systems
- Exceed API rate limits or attempt to circumvent usage restrictions
- Scrape, download, or harvest data in violation of provider terms
- Cache Google Civic API data beyond 30 days
- Use the Service for any unlawful purpose
- Impersonate any person or entity
- Transmit malicious code, viruses, or harmful content
- Attempt to gain unauthorized access to the Service or related systems
- Remove or obscure required attribution or trademark notices
- Violate intellectual property rights of data providers

## 5. Intellectual Property

### 5.1 Third-Party Data

All data provided through the Service remains the intellectual property of the respective data providers. You acknowledge that:

- **U.S. Government data** (IRS, Census, NCES, FEC, Grants.gov): Public domain
- **Charity Navigator data**: Proprietary to Charity Navigator, Inc.
- **ProPublica data**: Mixed (IRS data is public domain, ProPublica analysis may have copyright)
- **Wikidata**: CC0 Public Domain
- **DBpedia**: CC BY-SA 3.0 and GFDL
- **Academic datasets**: Subject to research licenses and citation requirements

### 5.2 Our Content

The Service interface, compilation, organization, and presentation of data is © 2026 CommunityOne. Our software is licensed under the MIT License. See our [GitHub repository](https://github.com/getcommunityone/open-navigator-for-engagement) for details.

### 5.3 User Contributions

By submitting content to the Service (feedback, corrections, etc.), you grant us a worldwide, royalty-free license to use, modify, and distribute such content.

## 6. Attribution Requirements

### 6.1 Mandatory Attributions

When using or redistributing data from our Service, you MUST include the following attributions:

**For Charity Navigator data:**
```
Powered by Charity Navigator
[Link to: https://www.charitynavigator.org/ein/[EIN]]
CHARITY NAVIGATOR and the CHARITY NAVIGATOR logo are registered 
trademarks of Charity Navigator. All rights reserved. Used with permission.
```

**For ProPublica data:**
```
Data provided by ProPublica
[Link to: https://projects.propublica.org/nonprofits/]
```

**For Open States data:**
```
Powered by Open States
[Link to: https://openstates.org/]
```

**For Google services:**
```
Data provided by Google
[Link to applicable Google service]
```

**For DBpedia data:**
```
Data from DBpedia and Wikipedia
[Link to: https://www.dbpedia.org/]
License: CC BY-SA 3.0
```

### 6.2 General Attribution

For all other data sources, see our [Citations & Data Sources](../data-sources/citations.md) page for complete attribution requirements.

## 7. Privacy

### 7.1 Public Data Only

We only collect and display publicly available information from government sources, tax filings, and public records. We do not collect:
- Private citizen information not in public records
- Personal financial information
- Health information
- Social Security numbers
- Any data requiring authentication to access

### 7.2 Your Privacy

See our [Privacy Policy](./privacy-policy.md) for details on how we handle user information.

### 7.3 Right to Request Removal

If your information appears in public records and you believe it should be removed, please contact us. We will evaluate requests on a case-by-case basis.

## 8. Disclaimers

### 8.1 No Government Endorsement

This Service is not affiliated with, endorsed by, or sponsored by:
- U.S. Internal Revenue Service
- U.S. Census Bureau  
- Any state or local government
- Any data source provider

### 8.2 Data Accuracy

While we strive for accuracy:
- Data is sourced from authoritative public sources
- Data is provided "as is" without warranties
- Users should verify critical information with original sources
- Errors in source data may be present in our datasets
- We are not responsible for inaccuracies in third-party data

### 8.3 No Professional Advice

This Service provides information only. It does not provide:
- Legal advice
- Medical or health advice
- Financial advice
- Professional consultation services

**For specific advice, consult qualified professionals in the relevant field.**

## 9. Limitation of Liability

### 9.1 AS-IS Provision

THE SERVICE IS PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, OR NON-INFRINGEMENT.

### 9.2 Limitation of Damages

TO THE MAXIMUM EXTENT PERMITTED BY LAW, WE SHALL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, OR ANY LOSS OF PROFITS OR REVENUES, WHETHER INCURRED DIRECTLY OR INDIRECTLY, OR ANY LOSS OF DATA, USE, GOODWILL, OR OTHER INTANGIBLE LOSSES RESULTING FROM:

- Your use or inability to use the Service
- Errors, inaccuracies, or omissions in the data
- Unauthorized access to or alteration of your transmissions or data
- Third-party conduct or content on the Service
- Any other matter related to the Service

### 9.3 Maximum Liability Cap

OUR TOTAL LIABILITY TO YOU FOR ALL CLAIMS ARISING FROM OR RELATED TO THE SERVICE SHALL NOT EXCEED $100 USD.

## 10. Indemnification

You agree to indemnify, defend, and hold harmless CommunityOne, its officers, directors, employees, and agents from any claims, liabilities, damages, losses, and expenses (including reasonable attorneys' fees) arising from:

- Your use of the Service
- Your violation of these Terms
- Your violation of third-party rights, including data provider terms of service
- Any misuse of data obtained through the Service

## 11. Rate Limiting & API Usage

### 11.1 Fair Use

You agree to:
- Respect all API rate limits imposed by data providers
- Implement appropriate caching to minimize redundant requests
- Use descriptive User-Agent headers identifying your application
- Not attempt to circumvent rate limiting or usage restrictions

### 11.2 Rate Limit Violations

Violations of rate limits may result in:
- Temporary suspension of access
- Permanent termination of access
- Reporting to upstream data providers
- Legal action if abuse is severe

## 12. Termination

### 12.1 Our Right to Terminate

We reserve the right to suspend or terminate your access to the Service at any time, without notice, for:
- Violation of these Terms
- Violation of third-party provider terms
- Abusive or harmful behavior
- Any reason or no reason

### 12.2 Effect of Termination

Upon termination:
- Your right to access the Service immediately ceases
- You must cease all use of data obtained from the Service
- You must delete all cached data subject to deletion requirements
- Provisions that by their nature should survive termination will survive

## 13. Changes to Terms

We reserve the right to modify these Terms at any time. Changes will be effective immediately upon posting to the Service. Your continued use of the Service after changes constitutes acceptance of the modified Terms.

**Material changes** will be announced through:
- Prominent notice on the Service
- Email notification (if you have an account)
- GitHub repository update log

## 14. Governing Law & Dispute Resolution

### 14.1 Governing Law

These Terms shall be governed by and construed in accordance with the laws of the United States and the State of Alabama, without regard to conflict of law principles.

### 14.2 Dispute Resolution

Any disputes arising from these Terms or the Service shall be resolved through:
1. Good faith negotiation
2. Mediation (if negotiation fails)
3. Binding arbitration or small claims court (if mediation fails)

### 14.3 Class Action Waiver

You agree to resolve disputes with us on an individual basis and waive your right to participate in class actions or class arbitrations.

## 15. Severability

If any provision of these Terms is found to be unenforceable or invalid, that provision will be limited or eliminated to the minimum extent necessary, and the remaining provisions will remain in full force and effect.

## 16. Entire Agreement

These Terms, together with our [Privacy Policy](./privacy-policy.md) and [Data Provider Terms](./data-provider-terms.md), constitute the entire agreement between you and CommunityOne regarding the Service.

## 17. Contact Information

For questions about these Terms of Service:

- **Email:** johnbowyer@communityone.com
- **GitHub Issues:** [Report issues](https://github.com/getcommunityone/open-navigator-for-engagement/issues)
- **Mail:** 5617 Lakeridge Court, Tuscaloosa, AL 35406

## 18. Acknowledgments

Open Navigator is built on publicly available data from:

- U.S. Government agencies (IRS, Census Bureau, NCES, FEC)
- ProPublica, Inc.
- Charity Navigator, Inc.
- Open States Foundation
- Google (BigQuery, Civic Information API, Data Commons)
- Wikimedia Foundation (Wikidata)
- DBpedia
- Academic institutions (Harvard, MIT, Cornell)
- Open source civic tech projects

We are grateful for their commitment to open data and democratic participation.

**Full citations:** See [Citations & Data Sources](../data-sources/citations.md)

---

## Quick Reference: Key Restrictions

| Data Source | Key Restrictions |
|-------------|------------------|
| **Charity Navigator** | ✅ MUST attribute "Powered by Charity Navigator"<br/>✅ MUST link to CN profiles<br/>✅ MUST include trademark notice<br/>❌ Max 1,000 calls/day<br/>❌ No redistribution |
| **Google Services** | ✅ MUST attribute "Data provided by Google"<br/>❌ Cannot cache Civic API data >30 days<br/>❌ Subject to API quotas |
| **ProPublica** | ✅ MUST attribute to ProPublica<br/>❌ FEC data: No commercial solicitation |
| **Open States** | ✅ MUST display "Powered by Open States"<br/>❌ 50k requests/month free tier |
| **DBpedia** | ✅ MUST attribute to DBpedia & Wikipedia<br/>✅ CC BY-SA 3.0 (share-alike applies) |

---

:::tip[Stay Compliant]
These Terms incorporate the most restrictive requirements from all our data providers. When in doubt, provide attribution and respect rate limits. For detailed provider-specific terms, see [Data Provider Terms of Service](./data-provider-terms.md).
:::
