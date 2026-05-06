"""
Utility functions for formatting database values into human-readable labels.
"""

import re


def format_organization_id(org_id: str) -> str:
    """
    Convert organization ID to human-readable name.
    
    Examples:
        org_board_of_health_douglas_al -> Board of Health - Douglas, AL
        org_hamilton_city_council_al -> Hamilton City Council, AL
        org_scottsboro_board_of_education_al -> Scottsboro Board of Education, AL
    """
    if not org_id:
        return "Unknown Organization"
    
    # Remove 'org_' prefix if present
    if org_id.startswith('org_'):
        org_id = org_id[4:]
    
    # Split by underscores
    parts = org_id.split('_')
    
    # Extract state code (last part, should be 2 letters)
    state_code = parts[-1].upper() if len(parts) > 0 and len(parts[-1]) == 2 else None
    
    # Remove state code from parts
    if state_code:
        parts = parts[:-1]
    
    # Capitalize each word
    words = [word.capitalize() for word in parts]
    
    # Join words
    readable_name = ' '.join(words)
    
    # Add state code if present
    if state_code:
        readable_name = f"{readable_name}, {state_code}"
    
    return readable_name


def format_role_type(role_type: str) -> str:
    """
    Convert role_type to human-readable label.
    
    Examples:
        government_official -> Government Official
        board_member -> Board Member
        executive_director -> Executive Director
    """
    if not role_type:
        return "Contact"
    
    # Replace underscores with spaces and capitalize each word
    return role_type.replace('_', ' ').title()


def format_title(title: str) -> str:
    """
    Format title to be more readable.
    
    Examples:
        government_official -> Government Official
        board_member -> Board Member
        MAYOR -> Mayor
    """
    if not title:
        return "Official"
    
    # If already properly formatted, return as-is
    if title[0].isupper() and ' ' in title:
        return title
    
    # Replace underscores with spaces and capitalize
    return title.replace('_', ' ').title()
