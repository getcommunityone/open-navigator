---
sidebar_position: 5
---

# Enterprise Tech Integration Guide

This guide documents the enterprise technology platforms and programs that support Open Navigator's data infrastructure.

## Implementation Status Legend

- ✅ **Active** - Fully implemented and in production use
- 🔄 **Recommended** - Implementation recommended for enhancement
- 📚 **Reference** - Used as inspiration for data modeling
- 🔍 **Evaluation** - Under consideration for future adoption

## 1. Cloud & Data Platforms

### ✅ Microsoft: Tech for Social Impact

**Status:** ACTIVE - Nonprofit CDM fully implemented

**What we use:**
- Nonprofit Common Data Model (CDM) for constituent management
- 8 core entities: CONSTITUENT, DONATION, CAMPAIGN, DESIGNATION, MEMBERSHIP, VOLUNTEER_ACTIVITY, PROGRAM_DELIVERY, PROGRAM_OUTCOME

**Files:**
- See [Nonprofit & Philanthropy](/docs/data-sources/citations#nonprofit--philanthropy) section
- ERD: [Data Model](/data-sources/data-model-erd)

**Resources:**
- GitHub: https://github.com/microsoft/Industry-Accelerator-Nonprofit
- License: MIT

---

### 🔄 Google: Data Commons

**Status:** RECOMMENDED - Implementation available, not yet deployed

**What we use:**
- Knowledge Graph API for jurisdiction demographics
- 100+ variables per jurisdiction (income, education, health, housing)
- Simplifies Census Bureau data access

**Implementation:**
- Code: `discovery/google_data_commons.py`
- Install: `pip install datacommons datacommons-pandas`
- Documentation: https://docs.datacommons.org/api/

**Next Steps:**
1. Install dependencies: `pip install datacommons datacommons-pandas`
2. Update `discovery/census_ingestion.py` to use Data Commons client
3. Replace manual Census API calls with simplified DC API
4. Add time-series enrichment for historical trends

**Example Usage:**
```python
from discovery.google_data_commons import DataCommonsClient

client = DataCommonsClient()

# Enrich a single jurisdiction
data = client.enrich_jurisdiction("01073")  # Jefferson County, AL
print(data["Median_Income_Household"])  # $65,000

# Bulk enrich multiple jurisdictions
fips_codes = ["01073", "01089", "01097"]
df = client.enrich_jurisdictions_bulk(fips_codes)

# Get time series
df_ts = client.get_time_series("01073", start_year=2015)
```

**Benefits:**
- ✅ Simpler API than raw Census Bureau
- ✅ 100+ pre-integrated variables
- ✅ Automatic data quality validation
- ✅ Time series support
- ✅ No API key required (free tier)

---

### 🔄 AWS: Open Data for Good

**Status:** PLANNED - Best practices for dataset exports

**What we use:**
- Parquet format best practices
- S3 storage patterns
- AWS Glue Data Catalog

**Recommendations for `/exports` folder:**
1. **Format:** Use Parquet with Snappy compression
2. **Partitioning:** Partition by `state/county/year`
3. **Versioning:** Enable S3 versioning for lineage
4. **Catalog:** Use AWS Glue for schema management
5. **Querying:** Athena for SQL without ETL

**Next Steps:**
1. Review AWS Registry examples: https://registry.opendata.aws
2. Update export scripts to generate Parquet
3. Document partitioning strategy
4. Consider AWS Glue for metadata

---

## 2. Data Engineering Platforms

### ✅ Databricks: Databricks for Good

**Status:** ACTIVE - Full implementation

**What we use:**
- **Unity Catalog:** Model registry and data governance
- **Delta Lake:** Bronze/Silver/Gold lakehouse architecture
- **MLflow:** Agent deployment and experiment tracking
- **Model Serving:** Auto-scaling REST endpoints for agents
- **Agent Bricks:** Mosaic AI Agent Framework

**Files:**
- `pipeline/delta_lake.py` - Delta Lake pipeline
- `agents/mlflow_classifier.py` - Policy classifier agent
- `agents/mlflow_base.py` - Base MLflow agent class
- `databricks/deployment.py` - Unity Catalog deployment
- `databricks/evaluation.py` - Agent evaluation framework
- `databricks/notebooks/01_agent_bricks_quickstart.py` - Quickstart notebook

**Resources:**
- Documentation: https://docs.databricks.com/
- Unity Catalog: https://docs.databricks.com/en/data-governance/unity-catalog/
- Solution Accelerators: https://www.databricks.com/solutions/accelerators

**Delta Sharing for Public Exports:**
```python
from databricks import delta_sharing

# Share Gold layer tables
share = delta_sharing.SharingClient()
share.create_share(
    name="one_civic_data",
    tables=["gold.jurisdictions", "gold.meetings", "gold.nonprofits"]
)
```

---

### 🔍 Snowflake: Snowflake for Good

**Status:** EVALUATION - Consider for enterprise data sharing

**What we use:**
- Data Marketplace for Census/ESG data
- Data sharing capabilities

**Evaluation Criteria:**
- Cost vs. Databricks
- Data Marketplace value-add
- Enterprise collaboration needs

---

### 📚 Oracle: NetSuite Social Impact

**Status:** REFERENCE - Inspiration for nonprofit accounting

**What we use:**
- Fund accounting model patterns
- Grant tracking workflows

**Resources:**
- https://netsuite.com/social-impact

---

### 📚 Salesforce: Nonprofit Success Pack (NPSP)

**Status:** REFERENCE - Inspiration for constituent management

**What we use:**
- Household accounts model
- Recurring donations pattern
- Program engagement tracking

**NPSP → ONE Mappings:**

| NPSP Object | Our Entity | Use Case |
|-------------|------------|----------|
| Contact | CONSTITUENT | Donor, volunteer, beneficiary |
| Opportunity | DONATION | Financial contributions |
| Campaign | CAMPAIGN | Fundraising campaigns |
| Engagement Plan | VOLUNTEER_ACTIVITY | Volunteer tracking |
| Program Cohort | PROGRAM_DELIVERY | Program participants |

**Resources:**
- GitHub: https://github.com/SalesforceFoundation/NPSP
- License: BSD-3-Clause

---

## 3. Infrastructure & AI

### 📚 Cisco: Crisis Response

**Status:** REFERENCE - Inspiration for platform resilience

**Focus:**
- Network connectivity during emergencies
- System resilience patterns

**Resources:**
- https://cisco.com/crisis-response

---

### 📚 IBM: Science for Social Good

**Status:** REFERENCE - AI/ML use case patterns

**Focus:**
- Watson AI for civic applications
- Blockchain for transparency
- Quantum computing potential

**Resources:**
- https://ibm.com/social-good

---

### 🔍 Meta: Data for Good

**Status:** EVALUATION - Population mapping potential

**What we use:**
- High-Resolution Population Density Maps
- Social Connectedness Index

**Evaluation:**
- Integration with demographics
- Use for underserved area identification

**Resources:**
- https://dataforgood.facebook.com

---

## Summary: Current vs. Planned Integrations

| Platform | Status | Priority | Effort | Value |
|----------|--------|----------|--------|-------|
| Microsoft CDM | ✅ Active | - | - | HIGH |
| Databricks | ✅ Active | - | - | HIGH |
| Google Data Commons | 🔄 Recommended | HIGH | Low | HIGH |
| AWS Best Practices | 🔄 Planned | MEDIUM | Medium | MEDIUM |
| Snowflake | 🔍 Evaluation | LOW | Medium | MEDIUM |
| Meta Data for Good | 🔍 Evaluation | LOW | Medium | MEDIUM |
| Salesforce NPSP | 📚 Reference | - | - | - |
| Oracle NetSuite | 📚 Reference | - | - | - |
| Cisco | 📚 Reference | - | - | - |
| IBM | 📚 Reference | - | - | - |

## Recommended Implementation Order

1. **Google Data Commons** (Immediate - Low effort, High value)
   - Install dependencies
   - Update census ingestion
   - Test with sample jurisdictions
   - Deploy to production

2. **AWS Export Optimization** (Next sprint - Medium effort, Medium value)
   - Convert exports to Parquet
   - Implement partitioning
   - Document patterns

3. **Databricks Delta Sharing** (Future - Medium effort, Medium value)
   - Configure sharing
   - Create public share
   - Document access

4. **Snowflake/Meta Evaluation** (Backlog - TBD)
   - POC evaluation
   - Cost-benefit analysis
   - Decision by end of quarter

---

## How to Cite These Partnerships

All enterprise technology partnerships are properly cited in:

**[Citations & Data Sources - Enterprise Tech for Social Good](/docs/data-sources/citations#-enterprise-tech-for-social-good)**

Includes:
- Full program URLs
- Implementation status
- License information
- BibTeX citations (where applicable)
- Code examples
