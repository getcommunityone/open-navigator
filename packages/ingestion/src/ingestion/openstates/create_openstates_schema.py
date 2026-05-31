#!/usr/bin/env python3
"""
Create OpenStates database schema using Django migrations.

This creates all the tables needed to load the OpenStates PostgreSQL dump.
"""

import os
import sys
import django
from pathlib import Path

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'openstates_schema_settings')

# Create a minimal Django settings module
SETTINGS_CONTENT = """
import os

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'openstates',
        'USER': 'postgres',
        'PASSWORD': 'postgres',
        'HOST': 'localhost',
        'PORT': '5433',
    }
}

# Required Django settings
SECRET_KEY = 'temporary-key-for-schema-creation'
INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'openstates.data',
]
USE_TZ = True
"""

# Write settings file
settings_file = Path(__file__).parent / 'openstates_schema_settings.py'
settings_file.write_text(SETTINGS_CONTENT)

# Setup Django
django.setup()

# Import Django management
from django.core.management import call_command

print("🔧 Creating OpenStates database schema...")
print("=" * 60)

try:
    # Run migrations to create all tables
    print("\n📝 Running Django migrations...")
    call_command('migrate', '--noinput', verbosity=2)
    
    print("\n✅ Schema created successfully!")
    print("\nNext step: Load the data with:")
    print("  docker exec openstates-db pg_restore -U postgres -d openstates \\")
    print("    --data-only --no-owner --no-acl /dumps/2026-04-public.pgdump")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\nTry installing openstates-core:")
    print("  pip install openstates-core psycopg2-binary Django==3.2.14")
    sys.exit(1)
finally:
    # Clean up
    if settings_file.exists():
        settings_file.unlink()
