#!/usr/bin/env python3
"""
Load OpenStates People Data

OpenStates maintains legislator data in a separate repository:
https://github.com/openstates/people

This script clones that repo and imports the YAML data into PostgreSQL.

Usage:
    python scripts/load_openstates_people.py
    
    # Or specify custom database connection
    python scripts/load_openstates_people.py --db-url postgresql://user:pass@host/db
"""

import argparse
import subprocess
import yaml
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, date

import psycopg2
from psycopg2.extras import execute_values
from loguru import logger


class DateEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles date objects."""
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)


class PeopleDataLoader:
    """
    Load OpenStates people data from GitHub repo into PostgreSQL.
    """
    
    PEOPLE_REPO = "https://github.com/openstates/people.git"
    
    def __init__(
        self,
        db_url: str = "postgresql://postgres:postgres@localhost:5433/openstates",
        cache_dir: str = "data/cache/openstates_people"
    ):
        self.db_url = db_url
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.repo_path = self.cache_dir / "people"
        
    def clone_or_update_repo(self) -> Path:
        """
        Clone the people repository or update if it exists.
        
        Returns:
            Path to the cloned repository
        """
        if self.repo_path.exists():
            logger.info(f"Updating existing repo at {self.repo_path}")
            subprocess.run(
                ["git", "pull"],
                cwd=self.repo_path,
                check=True,
                capture_output=True
            )
        else:
            logger.info(f"Cloning people repo to {self.repo_path}")
            subprocess.run(
                ["git", "clone", self.PEOPLE_REPO, str(self.repo_path)],
                check=True,
                capture_output=True
            )
        
        return self.repo_path
    
    def find_all_people_files(self) -> List[Path]:
        """
        Find all YAML files containing people data.
        
        Returns:
            List of YAML file paths
        """
        data_dir = self.repo_path / "data"
        
        # Find all .yml files in legislature, executive, municipalities directories
        people_files = []
        for pattern in ["*/legislature/*.yml", "*/executive/*.yml", "*/municipalities/*.yml"]:
            people_files.extend(data_dir.glob(pattern))
        
        logger.info(f"Found {len(people_files)} people data files")
        return people_files
    
    def load_yaml_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Load and parse a YAML file.
        
        Args:
            file_path: Path to YAML file
            
        Returns:
            Parsed YAML data
        """
        with open(file_path, 'r') as f:
            return yaml.safe_load(f)
    
    def insert_person(self, conn, person_data: Dict[str, Any], state: str) -> Optional[str]:
        """
        Insert a person record into the database.
        
        Args:
            conn: Database connection
            person_data: Person data from YAML
            state: State abbreviation
            
        Returns:
            Person ID if successful
        """
        cursor = conn.cursor()
        
        # Extract basic info
        person_id = person_data.get('id')
        name = person_data.get('name')
        party = person_data.get('party', [{}])[0].get('name') if person_data.get('party') else None
        image = person_data.get('image')
        
        # Get current role
        roles = person_data.get('roles', [])
        current_role = roles[0] if roles else {}
        role_type = current_role.get('type')
        district = current_role.get('district')
        jurisdiction = current_role.get('jurisdiction')
        
        # Get contact info
        contact_details = person_data.get('contact_details', [])
        email = None
        phone = None
        address = None
        for contact in contact_details:
            if contact.get('note') == 'Capitol Office':
                email = contact.get('email')
                phone = contact.get('voice')
                address = contact.get('address')
        
        # Insert into a simple people table (we'll create if not exists)
        try:
            cursor.execute("""
                INSERT INTO openstates_people (
                    id, name, state, party, role_type, district,
                    jurisdiction, email, phone, address, image,
                    data, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    state = EXCLUDED.state,
                    party = EXCLUDED.party,
                    role_type = EXCLUDED.role_type,
                    district = EXCLUDED.district,
                    jurisdiction = EXCLUDED.jurisdiction,
                    email = EXCLUDED.email,
                    phone = EXCLUDED.phone,
                    address = EXCLUDED.address,
                    image = EXCLUDED.image,
                    data = EXCLUDED.data,
                    updated_at = NOW()
                RETURNING id
            """, (
                person_id, name, state.upper(), party, role_type, district,
                jurisdiction, email, phone, address, image,
                json.dumps(person_data, cls=DateEncoder), datetime.now()
            ))
            
            result = cursor.fetchone()
            conn.commit()
            return result[0] if result else None
            
        except Exception as e:
            logger.error(f"Error inserting person {name}: {e}")
            conn.rollback()
            return None
    
    def create_people_table(self, conn):
        """
        Create the openstates_people table if it doesn't exist.
        
        Args:
            conn: Database connection
        """
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS openstates_people (
                id VARCHAR(255) PRIMARY KEY,
                name VARCHAR(500) NOT NULL,
                state VARCHAR(2),
                party VARCHAR(100),
                role_type VARCHAR(50),
                district VARCHAR(50),
                jurisdiction VARCHAR(100),
                email VARCHAR(255),
                phone VARCHAR(50),
                address TEXT,
                image VARCHAR(500),
                data JSONB,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_people_state 
            ON openstates_people(state)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_people_party 
            ON openstates_people(party)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_people_role_type 
            ON openstates_people(role_type)
        """)
        
        conn.commit()
        logger.info("✅ Created openstates_people table")
    
    def load_all_people(self):
        """
        Load all people data from the repository into the database.
        """
        logger.info("=" * 80)
        logger.info("LOADING OPENSTATES PEOPLE DATA")
        logger.info("=" * 80)
        
        # Clone/update repo
        self.clone_or_update_repo()
        
        # Connect to database
        logger.info(f"Connecting to database...")
        conn = psycopg2.connect(self.db_url)
        
        # Create table
        self.create_people_table(conn)
        
        # Find all people files
        people_files = self.find_all_people_files()
        
        # Load each file
        total_people = 0
        for file_path in people_files:
            # Extract state from path: data/{state}/legislature/filename.yml
            state = file_path.parts[-3]
            
            logger.info(f"Loading {file_path.name} ({state.upper()})...")
            
            try:
                person_data = self.load_yaml_file(file_path)
                
                if self.insert_person(conn, person_data, state):
                    total_people += 1
                    
            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")
                continue
        
        # Summary
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM openstates_people")
        db_count = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT state, COUNT(*) as count 
            FROM openstates_people 
            GROUP BY state 
            ORDER BY count DESC
            LIMIT 10
        """)
        top_states = cursor.fetchall()
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("✅ PEOPLE DATA LOADED SUCCESSFULLY")
        logger.info("=" * 80)
        logger.info(f"Total people in database: {db_count:,}")
        logger.info(f"Processed files: {len(people_files):,}")
        logger.info("")
        logger.info("Top 10 states by legislator count:")
        for state, count in top_states:
            logger.info(f"  {state}: {count:,}")
        
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Load OpenStates people data from GitHub into PostgreSQL"
    )
    parser.add_argument(
        "--db-url",
        default="postgresql://postgres:postgres@localhost:5433/openstates",
        help="PostgreSQL connection URL"
    )
    parser.add_argument(
        "--cache-dir",
        default="data/cache/openstates_people",
        help="Directory to clone the people repository"
    )
    
    args = parser.parse_args()
    
    loader = PeopleDataLoader(
        db_url=args.db_url,
        cache_dir=args.cache_dir
    )
    
    loader.load_all_people()


if __name__ == "__main__":
    main()
