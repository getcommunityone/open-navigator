# IRS Nonprofit Data Scripts

Scripts for working with IRS Tax Exempt Organization data (Form 990).

## Data Source

- **Website**: https://www.irs.gov/charities-non-profits
- **Form 990 Data**: https://www.irs.gov/charities-non-profits/form-990-series-downloads
- **Business Master File**: https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf
- **Coverage**: 1.8M+ tax-exempt organizations
- **Data Types**: Financials, officers, governance, programs

## Scripts

- `irs_bmf_ingestion.py` - Ingest IRS Business Master File (BMF)
- `create_nonprofit_officer_contacts.py` - Extract officer contacts from Form 990
- `manage_nonprofits.py` - Manage nonprofit organization data

## Key Data

### Business Master File (BMF)
- Organization name, EIN
- Address, ruling date
- NTEE classification
- Deductibility status

### Form 990
- Revenue, expenses, assets
- Officer compensation
- Program service accomplishments
- Grants paid

## Related Scripts

See also `scripts/enrichment/` for nonprofit enrichment scripts:
- `enrich_nonprofits_form990.py`
- `enrich_nonprofits_propublica.py`
- `batch_download_990s.py`

## Usage Examples

```bash
# Ingest BMF data
python irs_bmf_ingestion.py --state MA

# Extract officer contacts
python create_nonprofit_officer_contacts.py --state MA

# Manage nonprofit data
python manage_nonprofits.py update --state MA
```

## Data License

IRS public data is in the public domain.
