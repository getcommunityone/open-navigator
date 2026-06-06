#!/usr/bin/env python3
"""
Merge Bronze AI Extractions to Production Tables

Merges AI-extracted data from Bronze tables (meeting transcript analysis)
into production search tables with deduplication and entity resolution.

Bronze Tables (Source):
- bronze_contacts
- bronze_organizations_meetings  
- bronze_bills
- bronze_financial_items

Production Tables (Target):
- contact
- organization_nonprofit
- bills_search
- bills_meetings (junction)
- contacts_meeting_attendance (junction)

Usage:
    # Dry run (show what would be merged)
    python -m llm.enrichment.merge_bronze_to_production --dry-run

    # Merge contacts only
    python -m llm.enrichment.merge_bronze_to_production --entity contacts

    # Merge all entities
    python -m llm.enrichment.merge_bronze_to_production --all

    # Generate deduplication report
    python -m llm.enrichment.merge_bronze_to_production --report-duplicates
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import argparse
import uuid
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parents[5]))

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from loguru import logger

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Import entity resolution
from llm.enrichment.entity_resolution import (
    ContactMatcher,
    BillMatcher,
    OrganizationMatcher
)

# Database URLs
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'password')
BRONZE_DB_URL = os.getenv('LOCAL_BRONZE_DATABASE_URL', f'postgresql://postgres:{POSTGRES_PASSWORD}@localhost:5433/open_navigator_bronze')
NEON_DB_URL = os.getenv('NEON_DATABASE_URL_DEV', f'postgresql://postgres:{POSTGRES_PASSWORD}@localhost:5433/open_navigator')


class BronzeToProductionMerger:
    """Merge bronze tables to production with entity resolution"""
    
    def __init__(self, bronze_db_url: str, production_db_url: str, dry_run: bool = False):
        self.bronze_db_url = bronze_db_url
        self.production_db_url = production_db_url
        self.dry_run = dry_run
        self.merge_run_id = uuid.uuid4()
        
        # Stats
        self.stats = {
            'contacts': {'inserted': 0, 'updated': 0, 'skipped': 0, 'needs_review': 0},
            'organizations': {'inserted': 0, 'updated': 0, 'skipped': 0, 'needs_review': 0},
            'bills': {'inserted': 0, 'updated': 0, 'skipped': 0, 'needs_review': 0},
            'bills_meetings': {'inserted': 0},
            'attendance': {'inserted': 0}
        }
    
    def merge_contacts(self):
        """Merge bronze_contacts → contact"""
        logger.info("=" * 70)
        logger.info("MERGING CONTACTS")
        logger.info("=" * 70)
        
        # Fetch bronze contacts
        with psycopg2.connect(self.bronze_db_url) as bronze_conn:
            with bronze_conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM bronze_contacts
                    WHERE extracted_at > NOW() - INTERVAL '7 days'  -- Only recent extractions
                    ORDER BY extracted_at DESC
                """)
                bronze_contacts = cur.fetchall()
        
        logger.info(f"Found {len(bronze_contacts):,} bronze contacts to process")
        
        if not bronze_contacts:
            logger.warning("No bronze contacts found")
            return
        
        # Process each bronze contact
        with psycopg2.connect(self.production_db_url) as prod_conn:
            for bronze_contact in bronze_contacts:
                self._merge_single_contact(bronze_contact, prod_conn)
            
            if not self.dry_run:
                prod_conn.commit()
                logger.success(f"✅ Committed {sum(self.stats['contacts'].values())} contact operations")
        
        # Show stats
        logger.info("")
        logger.info("📊 CONTACT MERGE STATS:")
        for action, count in self.stats['contacts'].items():
            logger.info(f"  {action:15} {count:>6,}")
    
    def _merge_single_contact(self, bronze_contact: Dict, prod_conn):
        """Merge one contact with entity resolution"""
        
        # Step 1: Fetch candidates from production (same state for performance)
        with prod_conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get state from bronze contact's jurisdiction or org
            # This is a simplification - you might need more sophisticated state extraction
            cur.execute("""
                SELECT * FROM contact
                WHERE name ILIKE %s
                LIMIT 100
            """, (f"%{bronze_contact['full_name']}%",))
            prod_candidates = cur.fetchall()
        
        # Step 2: Try exact ID match (Wikidata QID, OpenStates ID)
        exact_match = ContactMatcher.match_by_id(
            dict(bronze_contact),
            [dict(c) for c in prod_candidates]
        )
        
        if exact_match:
            # Update existing record if AI has newer info
            action = self._update_contact_from_bronze(
                prod_conn,
                exact_match['id'],
                bronze_contact
            )
            self.stats['contacts'][action] += 1
            self._log_merge(
                'contact',
                bronze_contact['id'],
                exact_match['id'],
                'exact_id',
                1.0,
                action
            )
            return
        
        # Step 3: Try exact name + jurisdiction match
        name_match = ContactMatcher.match_by_name_jurisdiction(
            dict(bronze_contact),
            [dict(c) for c in prod_candidates],
            threshold=0.95
        )
        
        if name_match:
            # Decide whether to update
            action = self._decide_contact_update(
                prod_conn,
                name_match,
                bronze_contact
            )
            self.stats['contacts'][action] += 1
            self._log_merge(
                'contact',
                bronze_contact['id'],
                name_match['id'],
                'name_jurisdiction',
                0.95,
                action
            )
            return
        
        # Step 4: Try fuzzy match
        fuzzy_matches = ContactMatcher.fuzzy_match(
            dict(bronze_contact),
            [dict(c) for c in prod_candidates],
            threshold=0.85
        )
        
        if fuzzy_matches:
            # Multiple potential matches - flag for review
            best_match, score = fuzzy_matches[0]
            logger.warning(f"⚠️  Fuzzy match found for '{bronze_contact['full_name']}' → '{best_match['name']}' (score: {score:.2f})")
            
            # Insert but flag for manual review
            action = self._insert_contact_from_bronze(
                prod_conn,
                bronze_contact,
                needs_review=True
            )
            self.stats['contacts'][action] += 1
            self._log_merge(
                'contact',
                bronze_contact['id'],
                None,
                'fuzzy',
                score,
                action
            )
            return
        
        # Step 5: No match - insert as new
        action = self._insert_contact_from_bronze(
            prod_conn,
            bronze_contact,
            needs_review=False
        )
        self.stats['contacts'][action] += 1
        self._log_merge(
            'contact',
            bronze_contact['id'],
            None,
            'none',
            0.0,
            action
        )
    
    def _decide_contact_update(self, prod_conn, existing_contact: Dict, bronze_contact: Dict) -> str:
        """Decide whether to update existing contact with bronze data"""
        
        existing_datasource = existing_contact.get('datasource', 'unknown')
        existing_confidence = existing_contact.get('confidence_score', 0.5)
        
        # Don't override authoritative sources
        if existing_datasource in ['openstates_api', 'irs_990']:
            logger.debug(f"Skipping update - authoritative source: {existing_datasource}")
            return 'skipped'
        
        # Replace low-confidence records
        if existing_confidence < 0.70:
            logger.info(f"Updating low-confidence record: {existing_contact['name']}")
            self._update_contact_from_bronze(
                prod_conn,
                existing_contact['id'],
                bronze_contact
            )
            return 'updated'
        
        # Otherwise skip
        return 'skipped'
    
    def _update_contact_from_bronze(self, prod_conn, contact_id: int, bronze_contact: Dict) -> str:
        """Update existing contact with bronze data"""
        
        if self.dry_run:
            logger.info(f"[DRY RUN] Would update contact {contact_id} with bronze data")
            return 'updated'
        
        with prod_conn.cursor() as cur:
            cur.execute("""
                UPDATE contact
                SET 
                    title = COALESCE(%s, title),
                    organization_name = COALESCE(%s, organization_name),
                    email = COALESCE(%s, email),
                    phone = COALESCE(%s, phone),
                    datasource = 'gemini_ai_extraction',
                    datasource_id = %s,
                    confidence_score = 0.60,
                    last_updated = NOW()
                WHERE id = %s
            """, (
                bronze_contact.get('role'),
                bronze_contact.get('org_id'),
                None,  # Email not in bronze
                None,  # Phone not in bronze
                bronze_contact.get('wikidata_qid') or bronze_contact.get('person_id'),
                contact_id
            ))
        
        return 'updated'
    
    def _insert_contact_from_bronze(self, prod_conn, bronze_contact: Dict, needs_review: bool = False) -> str:
        """Insert new contact from bronze data"""
        
        if self.dry_run:
            logger.info(f"[DRY RUN] Would insert contact: {bronze_contact['full_name']}")
            return 'needs_review' if needs_review else 'inserted'
        
        with prod_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO contact (
                    name, title, organization_name, organization_ein,
                    email, phone, street_address, city, state_code, state, zip_code,
                    role_type, compensation, hours_per_week,
                    datasource, datasource_id, confidence_score,
                    verified, needs_review, last_updated
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s
                )
                RETURNING id
            """, (
                bronze_contact.get('full_name'),
                bronze_contact.get('role'),
                bronze_contact.get('org_id'),
                None,  # EIN not in bronze_contacts
                None,  # Email not extracted yet
                None,  # Phone not extracted yet
                None,  # Address not in bronze
                None,  # City not in bronze
                None,  # State code - need to extract
                None,  # State name - need to extract
                None,  # ZIP not in bronze
                'government_official' if not bronze_contact.get('is_lobbyist') else 'lobbyist',
                None,  # Compensation
                None,  # Hours per week
                'gemini_ai_extraction',
                bronze_contact.get('wikidata_qid') or bronze_contact.get('person_id'),
                0.60,  # AI extraction confidence
                False,  # Not verified
                needs_review,
                datetime.now()
            ))
        
        return 'needs_review' if needs_review else 'inserted'
    
    def _log_merge(self, entity_type: str, bronze_id: int, prod_id: Optional[int], 
                   match_type: str, confidence: float, action: str):
        """Log merge operation for debugging"""
        
        if self.dry_run:
            return
        
        with psycopg2.connect(self.production_db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO bronze_merge_log (
                        merge_run_id, entity_type, bronze_table, bronze_record_id,
                        production_table, production_record_id,
                        match_type, match_confidence, action_taken
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    str(self.merge_run_id),
                    entity_type,
                    f'bronze_{entity_type}s',
                    str(bronze_id) if bronze_id else None,
                    f'{entity_type}s_search',
                    str(prod_id) if prod_id else None,
                    match_type,
                    confidence,
                    action
                ))
            conn.commit()
    
    def merge_organizations(self):
        """Merge bronze_organizations_meetings → organization_nonprofit"""
        logger.info("=" * 70)
        logger.info("MERGING ORGANIZATIONS")
        logger.info("=" * 70)
        
        # Fetch bronze organizations
        with psycopg2.connect(self.bronze_db_url) as bronze_conn:
            with bronze_conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM bronze_organizations_meetings
                    WHERE extracted_at > NOW() - INTERVAL '7 days'
                    ORDER BY extracted_at DESC
                """)
                bronze_orgs = cur.fetchall()
        
        logger.info(f"Found {len(bronze_orgs):,} bronze organizations to process")
        
        if not bronze_orgs:
            logger.warning("No bronze organizations found")
            return
        
        # Process each bronze organization
        with psycopg2.connect(self.production_db_url) as prod_conn:
            for bronze_org in bronze_orgs:
                self._merge_single_organization(bronze_org, prod_conn)
            
            if not self.dry_run:
                prod_conn.commit()
                logger.success(f"✅ Committed {sum(self.stats['organizations'].values())} organization operations")
        
        # Show stats
        logger.info("")
        logger.info("📊 ORGANIZATION MERGE STATS:")
        for action, count in self.stats['organizations'].items():
            logger.info(f"  {action:15} {count:>6,}")
    
    def _merge_single_organization(self, bronze_org: Dict, prod_conn):
        """Merge one organization with entity resolution"""
        
        # Step 1: Try exact EIN match
        if bronze_org.get('ein'):
            with prod_conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM organization_nonprofit
                    WHERE ein = %s
                    LIMIT 1
                """, (bronze_org['ein'].replace('-', ''),))
                exact_match = cur.fetchone()
            
            if exact_match:
                # Organization already exists from IRS BMF - enhance with meeting context
                self._add_organization_meeting_context(
                    prod_conn,
                    exact_match['ein'],
                    bronze_org
                )
                self.stats['organizations']['skipped'] += 1
                self._log_merge('organization', bronze_org['id'], None, 'exact_ein', 1.0, 'enhanced')
                return
        
        # Step 2: Try Wikidata QID match
        if bronze_org.get('wikidata_qid'):
            with prod_conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM organization_nonprofit
                    WHERE datasource_id = %s
                    LIMIT 1
                """, (bronze_org['wikidata_qid'],))
                wikidata_match = cur.fetchone()
            
            if wikidata_match:
                self._add_organization_meeting_context(
                    prod_conn,
                    wikidata_match['ein'],
                    bronze_org
                )
                self.stats['organizations']['skipped'] += 1
                self._log_merge('organization', bronze_org['id'], None, 'wikidata_qid', 1.0, 'enhanced')
                return
        
        # Step 3: Try fuzzy name match (limited candidates)
        with prod_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM organization_nonprofit
                WHERE name ILIKE %s
                LIMIT 50
            """, (f"%{bronze_org['org_name']}%",))
            prod_candidates = cur.fetchall()
        
        fuzzy_matches = OrganizationMatcher.fuzzy_match_name(
            dict(bronze_org),
            [dict(c) for c in prod_candidates],
            threshold=0.85
        )
        
        if fuzzy_matches:
            best_match, score = fuzzy_matches[0]
            logger.warning(f"⚠️  Fuzzy match: '{bronze_org['org_name']}' → '{best_match['name']}' (score: {score:.2f})")
            
            # Add meeting context but flag for review
            self._add_organization_meeting_context(
                prod_conn,
                best_match['ein'],
                bronze_org,
                needs_review=True
            )
            self.stats['organizations']['needs_review'] += 1
            self._log_merge('organization', bronze_org['id'], None, 'fuzzy', score, 'needs_review')
            return
        
        # Step 4: No match - this is likely a local organization not in IRS BMF
        # Just record the meeting context without creating a new org record
        logger.info(f"📝 No match for '{bronze_org['org_name']}' - local organization (no EIN)")
        self.stats['organizations']['skipped'] += 1
    
    def _add_organization_meeting_context(self, prod_conn, org_ein: str, bronze_org: Dict, needs_review: bool = False):
        """Add entry to organizations_meetings junction table"""
        
        if self.dry_run:
            logger.info(f"[DRY RUN] Would link org {org_ein} to event {bronze_org['source_event_id']}")
            return
        
        with prod_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO organizations_meetings (
                    organization_ein, event_id, role_in_meeting, financial_interest,
                    is_lobbyist_entity, datasource, confidence_score
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (organization_ein, event_id) DO UPDATE SET
                    role_in_meeting = EXCLUDED.role_in_meeting,
                    financial_interest = EXCLUDED.financial_interest,
                    is_lobbyist_entity = EXCLUDED.is_lobbyist_entity
            """, (
                org_ein,
                bronze_org['source_event_id'],
                bronze_org.get('role_in_meeting'),
                bronze_org.get('financial_interest'),
                bronze_org.get('is_lobbyist_entity', False),
                'gemini_ai_extraction',
                0.60 if not needs_review else 0.50
            ))
    
    def merge_bills(self):
        """Merge bronze_bills → bills_search"""
        logger.info("=" * 70)
        logger.info("MERGING BILLS")
        logger.info("=" * 70)
        
        # Fetch bronze bills
        with psycopg2.connect(self.bronze_db_url) as bronze_conn:
            with bronze_conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM bronze_bills
                    WHERE extracted_at > NOW() - INTERVAL '7 days'
                    ORDER BY extracted_at DESC
                """)
                bronze_bills = cur.fetchall()
        
        logger.info(f"Found {len(bronze_bills):,} bronze bills to process")
        
        if not bronze_bills:
            logger.warning("No bronze bills found")
            return
        
        # Process each bronze bill
        with psycopg2.connect(self.production_db_url) as prod_conn:
            for bronze_bill in bronze_bills:
                self._merge_single_bill(bronze_bill, prod_conn)
            
            if not self.dry_run:
                prod_conn.commit()
                logger.success(f"✅ Committed {sum(self.stats['bills'].values())} bill operations")
        
        # Show stats
        logger.info("")
        logger.info("📊 BILL MERGE STATS:")
        for action, count in self.stats['bills'].items():
            logger.info(f"  {action:15} {count:>6,}")
    
    def _merge_single_bill(self, bronze_bill: Dict, prod_conn):
        """Merge one bill with entity resolution"""
        
        # Step 1: Try exact OpenStates ID match
        if bronze_bill.get('leg_id') and bronze_bill['leg_id'].startswith('ocd-bill/'):
            with prod_conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM bills_search
                    WHERE bill_id = %s
                    LIMIT 1
                """, (bronze_bill['leg_id'],))
                exact_match = cur.fetchone()
            
            if exact_match:
                # Bill already in DB from OpenStates - add meeting context
                self._add_bill_meeting_context(
                    prod_conn,
                    exact_match['id'],
                    bronze_bill
                )
                self.stats['bills']['skipped'] += 1
                self._log_merge('bill', bronze_bill['id'], exact_match['id'], 'exact_id', 1.0, 'enhanced')
                return
        
        # Step 2: Try jurisdiction + session + bill number match
        with prod_conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Try to match on state and session
            cur.execute("""
                SELECT * FROM bills_search
                WHERE state_code = %s
                  AND session = %s
                  AND bill_number ILIKE %s
                LIMIT 10
            """, (
                bronze_bill.get('jurisdiction', '')[:2].upper(),  # First 2 chars as state code
                str(bronze_bill.get('year', '')) + 'rs',  # Guess session format
                f"%{bronze_bill.get('official_number', '')}%"
            ))
            prod_candidates = cur.fetchall()
        
        if prod_candidates:
            # Try bill number matching
            for candidate in prod_candidates:
                if BillMatcher.normalize_bill_number(bronze_bill.get('official_number', '')) == \
                   BillMatcher.normalize_bill_number(candidate.get('bill_number', '')):
                    # Found match - add meeting context
                    self._add_bill_meeting_context(
                        prod_conn,
                        candidate['id'],
                        bronze_bill
                    )
                    self.stats['bills']['updated'] += 1
                    self._log_merge('bill', bronze_bill['id'], candidate['id'], 'number_match', 0.95, 'enhanced')
                    return
        
        # Step 3: No match - this is a LOCAL ordinance/resolution not in OpenStates
        action = self._insert_local_bill(prod_conn, bronze_bill)
        self.stats['bills'][action] += 1
        self._log_merge('bill', bronze_bill['id'], None, 'none', 0.0, action)
    
    def _add_bill_meeting_context(self, prod_conn, bill_id: int, bronze_bill: Dict):
        """Add entry to bills_meetings junction table"""
        
        if self.dry_run:
            logger.info(f"[DRY RUN] Would link bill {bill_id} to event {bronze_bill['source_event_id']}")
            return
        
        with prod_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO bills_meetings (
                    bill_id, event_id, relevance, action_taken,
                    datasource, confidence_score
                ) VALUES (
                    %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (bill_id, event_id) DO UPDATE SET
                    relevance = EXCLUDED.relevance,
                    action_taken = EXCLUDED.action_taken
            """, (
                bill_id,
                bronze_bill['source_event_id'],
                bronze_bill.get('relevance'),
                'discussed',  # Default action
                'gemini_ai_extraction',
                0.60
            ))
    
    def _insert_local_bill(self, prod_conn, bronze_bill: Dict) -> str:
        """Insert local ordinance/resolution not tracked by OpenStates"""
        
        if self.dry_run:
            logger.info(f"[DRY RUN] Would insert local bill: {bronze_bill['title']}")
            return 'inserted'
        
        # Generate a bill number for local ordinances
        # Use official_number if available, otherwise generate from ID
        bill_number = bronze_bill.get('official_number')
        if not bill_number or bill_number.strip() == '':
            bill_number = f"LOCAL-ORD-{bronze_bill['id']}"
        
        bill_id = f"local-{bronze_bill['id']}"
        
        # Check if this bill already exists
        with prod_conn.cursor() as cur:
            cur.execute("SELECT id FROM bills_search WHERE bill_id = %s", (bill_id,))
            existing = cur.fetchone()
        
        action = 'updated' if existing else 'inserted'
        
        with prod_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO bills_search (
                    bill_id, bill_number, title, classification,
                    session, jurisdiction_name, state_code, state,
                    latest_action_description,
                    datasource, datasource_id, confidence_score,
                    is_local_ordinance, verified, last_synced
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (bill_id) DO UPDATE SET
                    title = COALESCE(EXCLUDED.title, bills_search.title),
                    latest_action_description = EXCLUDED.latest_action_description,
                    last_synced = EXCLUDED.last_synced
                RETURNING id
            """, (
                bill_id,
                bill_number,
                bronze_bill.get('title'),
                bronze_bill.get('leg_type', 'ordinance'),
                str(bronze_bill.get('year', '')) + 'rs',
                bronze_bill.get('jurisdiction'),
                bronze_bill.get('jurisdiction', '')[:2].upper(),  # State code guess
                None,  # State full name
                f"Discussed in meeting (event {bronze_bill['source_event_id']})",
                'gemini_ai_extraction',
                None,
                0.60,
                True,  # Mark as local ordinance
                False,
                datetime.now()
            ))
            
            new_bill_id = cur.fetchone()[0]
            
            # Add meeting context
            self._add_bill_meeting_context(prod_conn, new_bill_id, bronze_bill)
        
        logger.info(f"📝 {action.capitalize()} local ordinance: {bronze_bill['title'][:50]}...")
        return action
    
    def generate_duplicate_report(self):
        """Generate report of potential duplicates for manual review"""
        logger.info("=" * 70)
        logger.info("DUPLICATE DETECTION REPORT")
        logger.info("=" * 70)
        
        # Query contacts that need review
        with psycopg2.connect(self.production_db_url) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        id, name, title, organization_name,
                        datasource, confidence_score, needs_review, review_notes,
                        last_updated
                    FROM contact
                    WHERE needs_review = TRUE
                    ORDER BY last_updated DESC
                    LIMIT 100
                """)
                needs_review = cur.fetchall()
        
        if not needs_review:
            logger.info("✅ No contacts flagged for review")
            return
        
        logger.info(f"\n⚠️  {len(needs_review)} contacts need manual review:\n")
        
        for contact in needs_review:
            logger.info(f"ID {contact['id']}: {contact['name']}")
            logger.info(f"  Title: {contact['title']}")
            logger.info(f"  Org: {contact['organization_name']}")
            logger.info(f"  Datasource: {contact['datasource']} (confidence: {contact['confidence_score']:.2f})")
            logger.info(f"  Last updated: {contact['last_updated']}")
            logger.info("")


def main():
    parser = argparse.ArgumentParser(
        description='Merge Bronze AI extractions to Production tables'
    )
    
    parser.add_argument(
        '--entity',
        type=str,
        choices=['contacts', 'organizations', 'bills', 'all'],
        default='all',
        help='Which entity type to merge'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be merged without committing'
    )
    
    parser.add_argument(
        '--report-duplicates',
        action='store_true',
        help='Generate duplicate detection report'
    )
    
    parser.add_argument(
        '--bronze-db',
        type=str,
        default=BRONZE_DB_URL,
        help='Bronze database URL'
    )
    
    parser.add_argument(
        '--production-db',
        type=str,
        default=NEON_DB_URL,
        help='Production database URL'
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 70)
    logger.info("BRONZE → PRODUCTION MERGE")
    logger.info("=" * 70)
    logger.info(f"Entity: {args.entity}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info(f"Bronze DB: {args.bronze_db[:50]}...")
    logger.info(f"Production DB: {args.production_db[:50]}...")
    logger.info("")
    
    merger = BronzeToProductionMerger(
        bronze_db_url=args.bronze_db,
        production_db_url=args.production_db,
        dry_run=args.dry_run
    )
    
    try:
        if args.report_duplicates:
            merger.generate_duplicate_report()
            return 0
        
        if args.entity in ['contacts', 'all']:
            merger.merge_contacts()
        
        if args.entity in ['organizations', 'all']:
            merger.merge_organizations()
        
        if args.entity in ['bills', 'all']:
            merger.merge_bills()
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("✅ MERGE COMPLETE")
        logger.info("=" * 70)
        
        return 0
        
    except Exception as e:
        logger.error(f"✗ Merge failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
