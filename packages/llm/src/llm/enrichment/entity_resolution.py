#!/usr/bin/env python3
"""
Entity Resolution for Bronze → Production Merges

Fuzzy matching and deduplication logic for:
- Contacts (people)
- Organizations
- Bills/legislation

Uses multiple matching strategies:
1. Exact ID match (Wikidata QID, OpenStates ID, EIN)
2. Exact field match (name + jurisdiction)
3. Fuzzy text match (Levenshtein distance)
4. Phonetic match (Soundex)
"""

import re
from typing import Dict, List, Optional, Tuple
from difflib import SequenceMatcher
from loguru import logger


class NameNormalizer:
    """Normalize names for comparison"""
    
    @staticmethod
    def normalize(name: str) -> str:
        """
        Normalize a person or organization name
        
        - Lowercase
        - Remove punctuation
        - Remove titles/suffixes
        - Standardize whitespace
        """
        if not name:
            return ""
        
        # Lowercase
        name = name.lower()
        
        # Remove common titles
        titles = [
            r'\bdr\.?\b', r'\bmr\.?\b', r'\bms\.?\b', r'\bmrs\.?\b',
            r'\bjr\.?\b', r'\bsr\.?\b', r'\besq\.?\b', r'\bhon\.?\b',
            r'\bsen\.?\b', r'\brep\.?\b', r'\bcllr\.?\b', r'\bmayor\b'
        ]
        for title in titles:
            name = re.sub(title, '', name, flags=re.IGNORECASE)
        
        # Remove punctuation except hyphens (preserve hyphenated names)
        name = re.sub(r'[^\w\s\-]', ' ', name)
        
        # Standardize whitespace
        name = re.sub(r'\s+', ' ', name).strip()
        
        return name
    
    @staticmethod
    def soundex(name: str) -> str:
        """
        Generate Soundex code for phonetic matching
        
        Handles common name variations:
        - John vs Jon
        - Smith vs Smyth
        - Catherine vs Katherine
        """
        name = NameNormalizer.normalize(name).upper()
        if not name:
            return ""
        
        # Soundex mapping
        soundex_map = {
            'B': '1', 'F': '1', 'P': '1', 'V': '1',
            'C': '2', 'G': '2', 'J': '2', 'K': '2', 'Q': '2', 'S': '2', 'X': '2', 'Z': '2',
            'D': '3', 'T': '3',
            'L': '4',
            'M': '5', 'N': '5',
            'R': '6'
        }
        
        # Keep first letter
        soundex = name[0]
        
        # Convert remaining letters to digits
        for char in name[1:]:
            if char in soundex_map:
                digit = soundex_map[char]
                # Don't repeat digits
                if not soundex or soundex[-1] != digit:
                    soundex += digit
        
        # Pad with zeros or truncate to 4 characters
        soundex = (soundex + '000')[:4]
        
        return soundex


class ContactMatcher:
    """Match contacts (people) between bronze and production"""
    
    @staticmethod
    def similarity_score(name1: str, name2: str) -> float:
        """
        Calculate similarity between two names
        
        Returns:
            float: 0.0 (completely different) to 1.0 (identical)
        """
        norm1 = NameNormalizer.normalize(name1)
        norm2 = NameNormalizer.normalize(name2)
        
        if not norm1 or not norm2:
            return 0.0
        
        # Use SequenceMatcher for character-level similarity
        return SequenceMatcher(None, norm1, norm2).ratio()
    
    @staticmethod
    def match_by_id(bronze_contact: Dict, production_contacts: List[Dict]) -> Optional[Dict]:
        """
        Try to match by ID (Wikidata QID, OpenStates person_id)
        
        Returns:
            Matching contact from production or None
        """
        wikidata_qid = bronze_contact.get('wikidata_qid')
        person_id = bronze_contact.get('person_id')
        
        for prod_contact in production_contacts:
            # Match on Wikidata QID
            if wikidata_qid and prod_contact.get('datasource_id') == wikidata_qid:
                return prod_contact
            
            # Match on person_id (OpenStates ID)
            if person_id and person_id.startswith('ocd-person/'):
                if prod_contact.get('datasource_id') == person_id:
                    return prod_contact
        
        return None
    
    @staticmethod
    def match_by_name_jurisdiction(
        bronze_contact: Dict,
        production_contacts: List[Dict],
        threshold: float = 0.95
    ) -> Optional[Dict]:
        """
        Match by name + jurisdiction (exact)
        
        Args:
            threshold: Minimum similarity score (default 0.95 = 95%)
        """
        bronze_name = NameNormalizer.normalize(bronze_contact.get('full_name', ''))
        bronze_jurisdiction = (bronze_contact.get('jurisdiction', '') or '').lower()
        
        for prod_contact in production_contacts:
            prod_name = NameNormalizer.normalize(prod_contact.get('name', ''))
            prod_org = (prod_contact.get('organization_name', '') or '').lower()
            
            # Name similarity check
            name_sim = ContactMatcher.similarity_score(bronze_name, prod_name)
            
            # Jurisdiction/organization match
            jurisdiction_match = (
                bronze_jurisdiction in prod_org or
                prod_org in bronze_jurisdiction
            )
            
            if name_sim >= threshold and jurisdiction_match:
                return prod_contact
        
        return None
    
    @staticmethod
    def fuzzy_match(
        bronze_contact: Dict,
        production_contacts: List[Dict],
        threshold: float = 0.85
    ) -> List[Tuple[Dict, float]]:
        """
        Find potential fuzzy matches
        
        Returns:
            List of (contact, similarity_score) tuples, sorted by score
        """
        bronze_name = bronze_contact.get('full_name', '')
        candidates = []
        
        for prod_contact in production_contacts:
            prod_name = prod_contact.get('name', '')
            
            # Text similarity
            text_sim = ContactMatcher.similarity_score(bronze_name, prod_name)
            
            # Phonetic similarity (bonus points)
            soundex1 = NameNormalizer.soundex(bronze_name)
            soundex2 = NameNormalizer.soundex(prod_name)
            phonetic_bonus = 0.1 if soundex1 == soundex2 else 0.0
            
            total_score = min(text_sim + phonetic_bonus, 1.0)
            
            if total_score >= threshold:
                candidates.append((prod_contact, total_score))
        
        # Sort by similarity (highest first)
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        return candidates


class BillMatcher:
    """Match bills/legislation between bronze and production"""
    
    @staticmethod
    def normalize_bill_number(bill_num: str) -> str:
        """
        Normalize bill number
        
        Examples:
            'HB 123' -> 'HB123'
            'House Bill 123' -> 'HB123'
            'S.B. 456' -> 'SB456'
        """
        if not bill_num:
            return ""
        
        bill_num = bill_num.upper().strip()
        
        # Expand abbreviations
        bill_num = bill_num.replace('HOUSE BILL', 'HB')
        bill_num = bill_num.replace('SENATE BILL', 'SB')
        bill_num = bill_num.replace('ASSEMBLY BILL', 'AB')
        bill_num = bill_num.replace('RESOLUTION', 'R')
        
        # Remove dots and spaces
        bill_num = bill_num.replace('.', '').replace(' ', '')
        
        return bill_num
    
    @staticmethod
    def match_by_id(bronze_bill: Dict, production_bills: List[Dict]) -> Optional[Dict]:
        """
        Match by OpenStates bill ID
        
        Format: ocd-bill/{jurisdiction}/{session}/{bill_number}
        Example: ocd-bill/alabama/2024rs/HB123
        """
        leg_id = bronze_bill.get('leg_id', '')
        
        if not leg_id or not leg_id.startswith('ocd-bill/'):
            return None
        
        for prod_bill in production_bills:
            if prod_bill.get('bill_id') == leg_id:
                return prod_bill
        
        return None
    
    @staticmethod
    def match_by_number(
        bronze_bill: Dict,
        production_bills: List[Dict]
    ) -> Optional[Dict]:
        """
        Match by jurisdiction + session + bill number
        """
        bronze_jurisdiction = (bronze_bill.get('jurisdiction', '') or '').lower()
        bronze_year = bronze_bill.get('year')
        bronze_number = BillMatcher.normalize_bill_number(
            bronze_bill.get('official_number', '') or ''
        )
        
        if not bronze_number:
            return None
        
        for prod_bill in production_bills:
            prod_jurisdiction = (prod_bill.get('state', '') or '').lower()
            prod_session = prod_bill.get('session', '')
            prod_number = BillMatcher.normalize_bill_number(
                prod_bill.get('bill_number', '')
            )
            
            # Check jurisdiction match
            jurisdiction_match = (
                bronze_jurisdiction in prod_jurisdiction or
                prod_jurisdiction in bronze_jurisdiction
            )
            
            # Check year match (session usually contains year)
            year_match = str(bronze_year) in prod_session if bronze_year else False
            
            # Check bill number match
            number_match = bronze_number == prod_number
            
            if jurisdiction_match and year_match and number_match:
                return prod_bill
        
        return None
    
    @staticmethod
    def fuzzy_match_title(
        bronze_bill: Dict,
        production_bills: List[Dict],
        threshold: float = 0.80
    ) -> List[Tuple[Dict, float]]:
        """
        Match by title similarity (for bills without clear identifiers)
        """
        bronze_title = (bronze_bill.get('title', '') or '').lower()
        bronze_jurisdiction = (bronze_bill.get('jurisdiction', '') or '').lower()
        
        if not bronze_title:
            return []
        
        candidates = []
        
        for prod_bill in production_bills:
            prod_title = (prod_bill.get('title', '') or '').lower()
            prod_jurisdiction = (prod_bill.get('state', '') or '').lower()
            
            # Must be same jurisdiction
            if bronze_jurisdiction not in prod_jurisdiction:
                continue
            
            # Title similarity
            title_sim = SequenceMatcher(None, bronze_title, prod_title).ratio()
            
            if title_sim >= threshold:
                candidates.append((prod_bill, title_sim))
        
        # Sort by similarity
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        return candidates


class OrganizationMatcher:
    """Match organizations between bronze and production"""
    
    @staticmethod
    def normalize_org_name(name: str) -> str:
        """
        Normalize organization name
        
        - Remove legal suffixes (Inc., LLC, Corp.)
        - Lowercase
        - Remove punctuation
        """
        if not name:
            return ""
        
        name = name.lower()
        
        # Remove legal suffixes
        suffixes = [
            r'\binc\.?$', r'\billc\.?$', r'\bcorp\.?$', r'\bltd\.?$',
            r'\bco\.?$', r'\bcompany$', r'\bcorporation$'
        ]
        for suffix in suffixes:
            name = re.sub(suffix, '', name, flags=re.IGNORECASE)
        
        # Remove punctuation
        name = re.sub(r'[^\w\s]', ' ', name)
        
        # Standardize whitespace
        name = re.sub(r'\s+', ' ', name).strip()
        
        return name
    
    @staticmethod
    def match_by_ein(bronze_org: Dict, production_orgs: List[Dict]) -> Optional[Dict]:
        """Match by EIN (Employer Identification Number)"""
        ein = (bronze_org.get('ein', '') or '').replace('-', '')
        
        if not ein:
            return None
        
        for prod_org in production_orgs:
            prod_ein = (prod_org.get('ein', '') or '').replace('-', '')
            if ein == prod_ein:
                return prod_org
        
        return None
    
    @staticmethod
    def match_by_wikidata(bronze_org: Dict, production_orgs: List[Dict]) -> Optional[Dict]:
        """Match by Wikidata QID"""
        qid = bronze_org.get('wikidata_qid')
        
        if not qid:
            return None
        
        for prod_org in production_orgs:
            if prod_org.get('datasource_id') == qid:
                return prod_org
        
        return None
    
    @staticmethod
    def fuzzy_match_name(
        bronze_org: Dict,
        production_orgs: List[Dict],
        threshold: float = 0.85
    ) -> List[Tuple[Dict, float]]:
        """
        Fuzzy match by organization name
        """
        bronze_name = OrganizationMatcher.normalize_org_name(
            bronze_org.get('org_name', '')
        )
        
        if not bronze_name:
            return []
        
        candidates = []
        
        for prod_org in production_orgs:
            prod_name = OrganizationMatcher.normalize_org_name(
                prod_org.get('name', '')
            )
            
            # Name similarity
            name_sim = SequenceMatcher(None, bronze_name, prod_name).ratio()
            
            if name_sim >= threshold:
                candidates.append((prod_org, name_sim))
        
        # Sort by similarity
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        return candidates


# Export main classes
__all__ = [
    'NameNormalizer',
    'ContactMatcher',
    'BillMatcher',
    'OrganizationMatcher'
]
