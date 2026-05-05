#!/usr/bin/env python3
"""
Extract structured AI analysis data to Bronze tables in local PostgreSQL.

This script:
1. Reads from events_text_ai table (structured_analysis JSONB column)
2. Extracts entities: people, organizations, decisions, bills, topics, causes
3. Loads into Bronze tables in local PostgreSQL database

Usage:
    # Create tables and load all data
    python scripts/datasources/gemini/load_meeting_transcripts_bronze.py
    
    # Just create tables (no data load)
    python scripts/datasources/gemini/load_meeting_transcripts_bronze.py --create-tables-only
    
    # Load data without recreating tables
    python scripts/datasources/gemini/load_meeting_transcripts_bronze.py --skip-create-tables
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
import argparse
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import psycopg2
from psycopg2.extras import execute_batch
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from loguru import logger

# Load environment variables (optional)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not available, use environment variables directly

# Database URLs
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'password')
NEON_DATABASE_URL = os.getenv('NEON_DATABASE_URL_DEV', f'postgresql://postgres:{POSTGRES_PASSWORD}@localhost:5433/open_navigator')
LOCAL_DATABASE_URL = os.getenv('LOCAL_BRONZE_DATABASE_URL', f'postgresql://postgres:{POSTGRES_PASSWORD}@localhost:5433/open_navigator_bronze')


class BronzeExtractor:
    """Extract AI analysis data to Bronze tables."""
    
    def __init__(self, source_db_url: str, target_db_url: str):
        self.source_db_url = source_db_url
        self.target_db_url = target_db_url
    
    def ensure_database_exists(self):
        """Create the target database if it doesn't exist."""
        
        # Parse database name from URL
        # Format: postgresql://user:pass@host:port/dbname
        parts = self.target_db_url.split('/')
        db_name = parts[-1]
        base_url = '/'.join(parts[:-1]) + '/postgres'  # Connect to default postgres DB
        
        logger.info(f"Checking if database '{db_name}' exists...")
        
        try:
            # Connect to default postgres database
            conn = psycopg2.connect(base_url)
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            
            with conn.cursor() as cur:
                # Check if database exists
                cur.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s",
                    (db_name,)
                )
                exists = cur.fetchone()
                
                if exists:
                    logger.info(f"✅ Database '{db_name}' already exists")
                else:
                    logger.info(f"Creating database '{db_name}'...")
                    cur.execute(f'CREATE DATABASE "{db_name}"')
                    logger.info(f"✅ Database '{db_name}' created successfully")
            
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to ensure database exists: {e}")
            raise
    
    def create_bronze_tables(self):
        """Create Bronze tables in local PostgreSQL."""
        
        logger.info("Creating Bronze tables in local PostgreSQL...")
        
        create_tables_sql = """
        -- Bronze Contacts (People from AI analysis)
        CREATE TABLE IF NOT EXISTS bronze_contacts (
            id SERIAL PRIMARY KEY,
            source_event_id INTEGER,
            source_ai_model VARCHAR(100),
            person_id VARCHAR(255),
            full_name VARCHAR(255),
            role VARCHAR(255),
            org_id VARCHAR(255),
            party_affiliation VARCHAR(100),
            is_lobbyist BOOLEAN DEFAULT FALSE,
            lobbyist_registration_number VARCHAR(100),
            lobbyist_clients JSONB,
            wikidata_qid VARCHAR(50),
            appeared_as VARCHAR(100),
            extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_event_id, person_id)
        );
        
        -- Bronze Organizations
        CREATE TABLE IF NOT EXISTS bronze_organizations (
            id SERIAL PRIMARY KEY,
            source_event_id INTEGER,
            source_ai_model VARCHAR(100),
            org_id VARCHAR(255),
            org_name VARCHAR(255),
            org_type VARCHAR(100),
            org_subtype VARCHAR(100),
            is_lobbyist_entity BOOLEAN DEFAULT FALSE,
            lobbying_clients JSONB,
            party_affiliation VARCHAR(100),
            ein VARCHAR(50),
            wikidata_qid VARCHAR(50),
            ntee_major_group VARCHAR(10),
            ntee_category_label VARCHAR(255),
            ntee_code VARCHAR(20),
            role_in_meeting TEXT,
            financial_interest TEXT,
            extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_event_id, org_id)
        );
        
        -- Bronze Bills/Legislation
        CREATE TABLE IF NOT EXISTS bronze_bills (
            id SERIAL PRIMARY KEY,
            source_event_id INTEGER,
            source_ai_model VARCHAR(100),
            leg_id VARCHAR(255),
            leg_type VARCHAR(100),
            official_number VARCHAR(100),
            title TEXT,
            jurisdiction VARCHAR(255),
            year INTEGER,
            status VARCHAR(50),
            relevance TEXT,
            url TEXT,
            extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_event_id, leg_id)
        );
        
        -- Bronze Decisions
        CREATE TABLE IF NOT EXISTS bronze_decisions (
            id SERIAL PRIMARY KEY,
            source_event_id INTEGER,
            source_ai_model VARCHAR(100),
            decision_id VARCHAR(255),
            subject_id VARCHAR(255),
            agenda_item TEXT,
            timestamp_start VARCHAR(10),
            timestamp_end VARCHAR(10),
            decision_date DATE,
            topic VARCHAR(255),
            headline TEXT,
            decision_statement TEXT,
            decision_method VARCHAR(50),
            lineage_type VARCHAR(50),
            lineage_note TEXT,
            primary_theme VARCHAR(100),
            primary_theme_cofog VARCHAR(20),
            secondary_theme VARCHAR(100),
            secondary_theme_cofog VARCHAR(20),
            primary_org_ids JSONB,
            ntee_code VARCHAR(10),
            ntee_major_group VARCHAR(100),
            ntee_category_label VARCHAR(255),
            secondary_ntee_code VARCHAR(10),
            secondary_ntee_major_group VARCHAR(100),
            secondary_ntee_category_label VARCHAR(255),
            outcome VARCHAR(50),
            vote_tally JSONB,
            timeline JSONB,
            arguments_for JSONB,
            arguments_against JSONB,
            tradeoffs JSONB,
            underlying_causes JSONB,
            power_map JSONB,
            frame_analysis JSONB,
            legislation_refs JSONB,
            financial_item_refs JSONB,
            extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_event_id, decision_id)
        );
        
        -- Bronze Topics (extracted from decisions)
        CREATE TABLE IF NOT EXISTS bronze_topics (
            id SERIAL PRIMARY KEY,
            source_event_id INTEGER,
            source_ai_model VARCHAR(100),
            decision_id VARCHAR(255),
            primary_theme VARCHAR(100),
            primary_theme_cofog VARCHAR(20),
            secondary_theme VARCHAR(100),
            secondary_theme_cofog VARCHAR(20),
            ntee_code VARCHAR(10),
            ntee_major_group VARCHAR(100),
            ntee_category_label VARCHAR(255),
            secondary_ntee_code VARCHAR(10),
            secondary_ntee_major_group VARCHAR(100),
            secondary_ntee_category_label VARCHAR(255),
            primary_org_ids JSONB,
            topic VARCHAR(255),
            headline TEXT,
            extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Bronze Causes (underlying causes from decisions)
        CREATE TABLE IF NOT EXISTS bronze_causes (
            id SERIAL PRIMARY KEY,
            source_event_id INTEGER,
            source_ai_model VARCHAR(100),
            decision_id VARCHAR(255),
            cause_headline VARCHAR(255),
            cause_detail TEXT,
            extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Bronze Financial Items
        CREATE TABLE IF NOT EXISTS bronze_financial_items (
            id SERIAL PRIMARY KEY,
            source_event_id INTEGER,
            source_ai_model VARCHAR(100),
            financial_item_id VARCHAR(255),
            decision_id VARCHAR(255),
            subject_id VARCHAR(255),
            event_description TEXT,
            item_description TEXT,
            amount NUMERIC,
            amount_type VARCHAR(100),
            amount_qualifier VARCHAR(50),
            currency VARCHAR(10),
            item_date DATE,
            item_date_type VARCHAR(50),
            org_id VARCHAR(255),
            org_role TEXT,
            authorized_by_person_id VARCHAR(255),
            funding_source TEXT,
            notes TEXT,
            extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_event_id, financial_item_id)
        );
        
        -- Create indexes
        CREATE INDEX IF NOT EXISTS idx_bronze_contacts_event ON bronze_contacts(source_event_id);
        CREATE INDEX IF NOT EXISTS idx_bronze_contacts_person ON bronze_contacts(person_id);
        CREATE INDEX IF NOT EXISTS idx_bronze_orgs_event ON bronze_organizations(source_event_id);
        CREATE INDEX IF NOT EXISTS idx_bronze_orgs_org ON bronze_organizations(org_id);
        CREATE INDEX IF NOT EXISTS idx_bronze_bills_event ON bronze_bills(source_event_id);
        CREATE INDEX IF NOT EXISTS idx_bronze_decisions_event ON bronze_decisions(source_event_id);
        CREATE INDEX IF NOT EXISTS idx_bronze_decisions_decision ON bronze_decisions(decision_id);
        CREATE INDEX IF NOT EXISTS idx_bronze_topics_event ON bronze_topics(source_event_id);
        CREATE INDEX IF NOT EXISTS idx_bronze_causes_event ON bronze_causes(source_event_id);
        CREATE INDEX IF NOT EXISTS idx_bronze_financial_event ON bronze_financial_items(source_event_id);
        """
        
        with psycopg2.connect(self.target_db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(create_tables_sql)
            conn.commit()
        
        logger.info("✅ Bronze tables created successfully")
    
    def extract_and_load(self):
        """Extract data from events_text_ai and load to Bronze tables."""
        
        logger.info("Extracting data from events_text_ai...")
        
        # Fetch all records with structured_analysis
        query = """
        SELECT 
            id,
            event_id,
            ai_model,
            structured_analysis,
            summary_text,
            created_at
        FROM events_text_ai
        WHERE structured_analysis IS NOT NULL
          AND raw_response IS NOT NULL
        ORDER BY created_at DESC
        """
        
        with psycopg2.connect(self.source_db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                records = cur.fetchall()
        
        if not records:
            logger.warning("No records found with structured_analysis")
            return
        
        logger.info(f"Found {len(records)} records to process")
        
        # Process each record
        contacts_data = []
        orgs_data = []
        bills_data = []
        decisions_data = []
        topics_data = []
        causes_data = []
        financial_data = []
        
        for row in records:
            row_id, event_id, ai_model, structured_analysis, summary_text, created_at = row
            
            if not structured_analysis:
                continue
            
            # Parse JSON
            try:
                data = structured_analysis if isinstance(structured_analysis, dict) else json.loads(structured_analysis)
            except Exception as e:
                logger.warning(f"Failed to parse JSON for event {event_id}: {e}")
                continue
            
            # Extract people
            for person in data.get('people', []):
                contacts_data.append((
                    event_id,
                    ai_model,
                    person.get('person_id'),
                    person.get('full_name'),
                    person.get('role'),
                    person.get('org_id'),
                    person.get('party_affiliation'),
                    person.get('is_lobbyist', False),
                    person.get('lobbyist_registration_number'),
                    json.dumps(person.get('lobbyist_clients', [])),
                    person.get('wikidata_qid'),
                    person.get('appeared_as')
                ))
            
            # Extract organizations
            for org in data.get('organizations', []):
                orgs_data.append((
                    event_id,
                    ai_model,
                    org.get('org_id'),
                    org.get('org_name'),
                    org.get('org_type'),
                    org.get('org_subtype'),
                    org.get('is_lobbyist_entity', False),
                    json.dumps(org.get('lobbying_clients', [])),
                    org.get('party_affiliation'),
                    org.get('ein'),
                    org.get('wikidata_qid'),
                    org.get('ntee_major_group'),
                    org.get('ntee_category_label'),
                    org.get('ntee_code'),
                    org.get('role_in_meeting'),
                    org.get('financial_interest')
                ))
            
            # Extract legislation
            for leg in data.get('legislation', []):
                bills_data.append((
                    event_id,
                    ai_model,
                    leg.get('leg_id'),
                    leg.get('leg_type'),
                    leg.get('official_number'),
                    leg.get('title'),
                    leg.get('jurisdiction'),
                    leg.get('year'),
                    leg.get('status'),
                    leg.get('relevance'),
                    leg.get('url')
                ))
            
            # Extract decisions
            for decision in data.get('decisions', []):
                # Main decision record
                decisions_data.append((
                    event_id,
                    ai_model,
                    decision.get('decision_id'),
                    decision.get('subject_id'),
                    decision.get('agenda_item'),
                    decision.get('timestamp_start'),
                    decision.get('timestamp_end'),
                    decision.get('decision_date'),
                    decision.get('topic'),
                    decision.get('headline'),
                    decision.get('decision_statement'),
                    decision.get('decision_method'),
                    decision.get('lineage_type'),
                    decision.get('lineage_note'),
                    decision.get('primary_theme'),
                    decision.get('primary_theme_cofog'),
                    decision.get('secondary_theme'),
                    decision.get('secondary_theme_cofog'),
                    json.dumps(decision.get('primary_org_ids', [])),
                    decision.get('ntee_code'),
                    decision.get('ntee_major_group'),
                    decision.get('ntee_category_label'),
                    decision.get('secondary_ntee_code'),
                    decision.get('secondary_ntee_major_group'),
                    decision.get('secondary_ntee_category_label'),
                    decision.get('outcome'),
                    json.dumps(decision.get('vote_tally', {})),
                    json.dumps(decision.get('timeline', {})),
                    json.dumps(decision.get('arguments_for', [])),
                    json.dumps(decision.get('arguments_against', [])),
                    json.dumps(decision.get('tradeoffs', [])),
                    json.dumps(decision.get('underlying_causes', [])),
                    json.dumps(decision.get('power_map', {})),
                    json.dumps(decision.get('frame_analysis', {})),
                    json.dumps(decision.get('legislation_refs', [])),
                    json.dumps(decision.get('financial_item_refs', []))
                ))
                
                # Extract topic
                topics_data.append((
                    event_id,
                    ai_model,
                    decision.get('decision_id'),
                    decision.get('primary_theme'),
                    decision.get('primary_theme_cofog'),
                    decision.get('secondary_theme'),
                    decision.get('secondary_theme_cofog'),
                    decision.get('ntee_code'),
                    decision.get('ntee_major_group'),
                    decision.get('ntee_category_label'),
                    decision.get('secondary_ntee_code'),
                    decision.get('secondary_ntee_major_group'),
                    decision.get('secondary_ntee_category_label'),
                    json.dumps(decision.get('primary_org_ids', [])),
                    decision.get('topic'),
                    decision.get('headline')
                ))
                
                # Extract underlying causes
                for cause in decision.get('underlying_causes', []):
                    causes_data.append((
                        event_id,
                        ai_model,
                        decision.get('decision_id'),
                        cause.get('headline'),
                        cause.get('detail')
                    ))
            
            # Extract financial items
            for fin_item in data.get('financial_items', []):
                financial_data.append((
                    event_id,
                    ai_model,
                    fin_item.get('financial_item_id'),
                    fin_item.get('decision_id'),
                    fin_item.get('subject_id'),
                    fin_item.get('event_description'),
                    fin_item.get('item_description'),
                    fin_item.get('amount'),
                    fin_item.get('amount_type'),
                    fin_item.get('amount_qualifier'),
                    fin_item.get('currency', 'USD'),
                    fin_item.get('item_date'),
                    fin_item.get('item_date_type'),
                    fin_item.get('org_id'),
                    fin_item.get('org_role'),
                    fin_item.get('authorized_by_person_id'),
                    fin_item.get('funding_source'),
                    fin_item.get('notes')
                ))
        
        # Insert data
        logger.info("Loading data to Bronze tables...")
        
        with psycopg2.connect(self.target_db_url) as conn:
            with conn.cursor() as cur:
                # Insert contacts
                if contacts_data:
                    execute_batch(cur, """
                        INSERT INTO bronze_contacts (
                            source_event_id, source_ai_model, person_id, full_name, role,
                            org_id, party_affiliation, is_lobbyist, lobbyist_registration_number,
                            lobbyist_clients, wikidata_qid, appeared_as
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (source_event_id, person_id, source_ai_model) 
                        DO UPDATE SET
                            full_name = EXCLUDED.full_name,
                            role = EXCLUDED.role,
                            org_id = EXCLUDED.org_id,
                            party_affiliation = EXCLUDED.party_affiliation,
                            is_lobbyist = EXCLUDED.is_lobbyist,
                            lobbyist_registration_number = EXCLUDED.lobbyist_registration_number,
                            lobbyist_clients = EXCLUDED.lobbyist_clients,
                            wikidata_qid = EXCLUDED.wikidata_qid,
                            appeared_as = EXCLUDED.appeared_as,
                            extracted_at = CURRENT_TIMESTAMP
                    """, contacts_data)
                    logger.info(f"✅ Inserted/updated {len(contacts_data)} contacts")
                
                # Insert organizations
                if orgs_data:
                    execute_batch(cur, """
                        INSERT INTO bronze_organizations (
                            source_event_id, source_ai_model, org_id, org_name, org_type,
                            org_subtype, is_lobbyist_entity, lobbying_clients, party_affiliation,
                            ein, wikidata_qid, ntee_major_group, ntee_category_label,
                            ntee_code, role_in_meeting, financial_interest
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (source_event_id, org_id, source_ai_model) 
                        DO UPDATE SET
                            org_name = EXCLUDED.org_name,
                            org_type = EXCLUDED.org_type,
                            org_subtype = EXCLUDED.org_subtype,
                            is_lobbyist_entity = EXCLUDED.is_lobbyist_entity,
                            lobbying_clients = EXCLUDED.lobbying_clients,
                            party_affiliation = EXCLUDED.party_affiliation,
                            ein = EXCLUDED.ein,
                            wikidata_qid = EXCLUDED.wikidata_qid,
                            ntee_major_group = EXCLUDED.ntee_major_group,
                            ntee_category_label = EXCLUDED.ntee_category_label,
                            ntee_code = EXCLUDED.ntee_code,
                            role_in_meeting = EXCLUDED.role_in_meeting,
                            financial_interest = EXCLUDED.financial_interest,
                            extracted_at = CURRENT_TIMESTAMP
                    """, orgs_data)
                    logger.info(f"✅ Inserted/updated {len(orgs_data)} organizations")
                
                # Insert bills
                if bills_data:
                    execute_batch(cur, """
                        INSERT INTO bronze_bills (
                            source_event_id, source_ai_model, leg_id, leg_type, official_number,
                            title, jurisdiction, year, status, relevance, url
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (source_event_id, leg_id, source_ai_model) 
                        DO UPDATE SET
                            leg_type = EXCLUDED.leg_type,
                            official_number = EXCLUDED.official_number,
                            title = EXCLUDED.title,
                            jurisdiction = EXCLUDED.jurisdiction,
                            year = EXCLUDED.year,
                            status = EXCLUDED.status,
                            relevance = EXCLUDED.relevance,
                            url = EXCLUDED.url,
                            extracted_at = CURRENT_TIMESTAMP
                    """, bills_data)
                    logger.info(f"✅ Inserted/updated {len(bills_data)} bills/legislation")
                
                # Insert decisions
                if decisions_data:
                    execute_batch(cur, """
                        INSERT INTO bronze_decisions (
                            source_event_id, source_ai_model, decision_id, subject_id, agenda_item,
                            timestamp_start, timestamp_end, decision_date, topic, headline,
                            decision_statement, decision_method, lineage_type, lineage_note,
                            primary_theme, primary_theme_cofog, secondary_theme, secondary_theme_cofog,
                            primary_org_ids, ntee_code, ntee_major_group, ntee_category_label,
                            secondary_ntee_code, secondary_ntee_major_group, secondary_ntee_category_label,
                            outcome, vote_tally, timeline, arguments_for, arguments_against,
                            tradeoffs, underlying_causes, power_map, frame_analysis,
                            legislation_refs, financial_item_refs
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (source_event_id, decision_id, source_ai_model) 
                        DO UPDATE SET
                            subject_id = EXCLUDED.subject_id,
                            agenda_item = EXCLUDED.agenda_item,
                            timestamp_start = EXCLUDED.timestamp_start,
                            timestamp_end = EXCLUDED.timestamp_end,
                            decision_date = EXCLUDED.decision_date,
                            topic = EXCLUDED.topic,
                            headline = EXCLUDED.headline,
                            decision_statement = EXCLUDED.decision_statement,
                            decision_method = EXCLUDED.decision_method,
                            lineage_type = EXCLUDED.lineage_type,
                            lineage_note = EXCLUDED.lineage_note,
                            primary_theme = EXCLUDED.primary_theme,
                            primary_theme_cofog = EXCLUDED.primary_theme_cofog,
                            secondary_theme = EXCLUDED.secondary_theme,
                            secondary_theme_cofog = EXCLUDED.secondary_theme_cofog,
                            primary_org_ids = EXCLUDED.primary_org_ids,
                            ntee_code = EXCLUDED.ntee_code,
                            ntee_major_group = EXCLUDED.ntee_major_group,
                            ntee_category_label = EXCLUDED.ntee_category_label,
                            secondary_ntee_code = EXCLUDED.secondary_ntee_code,
                            secondary_ntee_major_group = EXCLUDED.secondary_ntee_major_group,
                            secondary_ntee_category_label = EXCLUDED.secondary_ntee_category_label,
                            outcome = EXCLUDED.outcome,
                            vote_tally = EXCLUDED.vote_tally,
                            timeline = EXCLUDED.timeline,
                            arguments_for = EXCLUDED.arguments_for,
                            arguments_against = EXCLUDED.arguments_against,
                            tradeoffs = EXCLUDED.tradeoffs,
                            underlying_causes = EXCLUDED.underlying_causes,
                            power_map = EXCLUDED.power_map,
                            frame_analysis = EXCLUDED.frame_analysis,
                            legislation_refs = EXCLUDED.legislation_refs,
                            financial_item_refs = EXCLUDED.financial_item_refs,
                            extracted_at = CURRENT_TIMESTAMP
                    """, decisions_data)
                    logger.info(f"✅ Inserted/updated {len(decisions_data)} decisions")
                
                # Insert topics
                if topics_data:
                    execute_batch(cur, """
                        INSERT INTO bronze_topics (
                            source_event_id, source_ai_model, decision_id, primary_theme,
                            primary_theme_cofog, secondary_theme, secondary_theme_cofog,
                            ntee_code, ntee_major_group, ntee_category_label,
                            secondary_ntee_code, secondary_ntee_major_group, secondary_ntee_category_label,
                            primary_org_ids, topic, headline
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (source_event_id, decision_id, source_ai_model)
                        DO UPDATE SET
                            primary_theme = EXCLUDED.primary_theme,
                            primary_theme_cofog = EXCLUDED.primary_theme_cofog,
                            secondary_theme = EXCLUDED.secondary_theme,
                            secondary_theme_cofog = EXCLUDED.secondary_theme_cofog,
                            ntee_code = EXCLUDED.ntee_code,
                            ntee_major_group = EXCLUDED.ntee_major_group,
                            ntee_category_label = EXCLUDED.ntee_category_label,
                            secondary_ntee_code = EXCLUDED.secondary_ntee_code,
                            secondary_ntee_major_group = EXCLUDED.secondary_ntee_major_group,
                            secondary_ntee_category_label = EXCLUDED.secondary_ntee_category_label,
                            primary_org_ids = EXCLUDED.primary_org_ids,
                            topic = EXCLUDED.topic,
                            headline = EXCLUDED.headline,
                            extracted_at = CURRENT_TIMESTAMP
                    """, topics_data)
                    logger.info(f"✅ Inserted/updated {len(topics_data)} topics")
                
                # Insert causes
                if causes_data:
                    execute_batch(cur, """
                        INSERT INTO bronze_causes (
                            source_event_id, source_ai_model, decision_id,
                            cause_headline, cause_detail
                        ) VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (source_event_id, decision_id, cause_headline, source_ai_model)
                        DO UPDATE SET
                            cause_detail = EXCLUDED.cause_detail,
                            extracted_at = CURRENT_TIMESTAMP
                    """, causes_data)
                    logger.info(f"✅ Inserted/updated {len(causes_data)} underlying causes")
                
                # Insert financial items
                if financial_data:
                    execute_batch(cur, """
                        INSERT INTO bronze_financial_items (
                            source_event_id, source_ai_model, financial_item_id, decision_id,
                            subject_id, event_description, item_description, amount, amount_type,
                            amount_qualifier, currency, item_date, item_date_type, org_id,
                            org_role, authorized_by_person_id, funding_source, notes
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (source_event_id, financial_item_id, source_ai_model) 
                        DO UPDATE SET
                            decision_id = EXCLUDED.decision_id,
                            subject_id = EXCLUDED.subject_id,
                            event_description = EXCLUDED.event_description,
                            item_description = EXCLUDED.item_description,
                            amount = EXCLUDED.amount,
                            amount_type = EXCLUDED.amount_type,
                            amount_qualifier = EXCLUDED.amount_qualifier,
                            currency = EXCLUDED.currency,
                            item_date = EXCLUDED.item_date,
                            item_date_type = EXCLUDED.item_date_type,
                            org_id = EXCLUDED.org_id,
                            org_role = EXCLUDED.org_role,
                            authorized_by_person_id = EXCLUDED.authorized_by_person_id,
                            funding_source = EXCLUDED.funding_source,
                            notes = EXCLUDED.notes,
                            extracted_at = CURRENT_TIMESTAMP
                    """, financial_data)
                    logger.info(f"✅ Inserted/updated {len(financial_data)} financial items")
            
            conn.commit()
        
        logger.info("✅ Data extraction complete!")
    
    def show_summary(self):
        """Show summary statistics of Bronze tables."""
        
        query = """
        SELECT 
            'bronze_contacts' as table_name, COUNT(*) as count FROM bronze_contacts
        UNION ALL
        SELECT 'bronze_organizations', COUNT(*) FROM bronze_organizations
        UNION ALL
        SELECT 'bronze_bills', COUNT(*) FROM bronze_bills
        UNION ALL
        SELECT 'bronze_decisions', COUNT(*) FROM bronze_decisions
        UNION ALL
        SELECT 'bronze_topics', COUNT(*) FROM bronze_topics
        UNION ALL
        SELECT 'bronze_causes', COUNT(*) FROM bronze_causes
        UNION ALL
        SELECT 'bronze_financial_items', COUNT(*) FROM bronze_financial_items
        """
        
        with psycopg2.connect(self.target_db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                results = cur.fetchall()
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("BRONZE TABLES SUMMARY")
        logger.info("=" * 70)
        for table, count in results:
            logger.info(f"{table:<30} {count:>10,} records")


def main():
    parser = argparse.ArgumentParser(
        description='Extract AI analysis data to Bronze tables'
    )
    
    parser.add_argument(
        '--create-tables-only',
        action='store_true',
        help='Only create tables, do not load data'
    )
    
    parser.add_argument(
        '--skip-create-tables',
        action='store_true',
        help='Skip table creation, only load data'
    )
    
    parser.add_argument(
        '--source-db',
        type=str,
        default=NEON_DATABASE_URL,
        help='Source database URL (where events_text_ai is)'
    )
    
    parser.add_argument(
        '--target-db',
        type=str,
        default=LOCAL_DATABASE_URL,
        help='Target database URL (where Bronze tables will be created)'
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 70)
    logger.info("EXTRACT AI ANALYSIS TO BRONZE TABLES")
    logger.info("=" * 70)
    logger.info(f"Source DB: {args.source_db[:50]}...")
    logger.info(f"Target DB: {args.target_db[:50]}...")
    logger.info("")
    
    extractor = BronzeExtractor(
        source_db_url=args.source_db,
        target_db_url=args.target_db
    )
    
    try:
        # Ensure database exists
        extractor.ensure_database_exists()
        
        # Create tables
        if not args.skip_create_tables:
            extractor.create_bronze_tables()
        
        # Load data
        if not args.create_tables_only:
            extractor.extract_and_load()
        
        # Show summary
        extractor.show_summary()
        
        return 0
        
    except Exception as e:
        logger.error(f"✗ Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
