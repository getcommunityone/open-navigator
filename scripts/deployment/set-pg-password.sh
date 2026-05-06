#!/bin/bash
# Set PostgreSQL password once for all commands
export PGPASSWORD=password

echo "
✅ PostgreSQL credentials configured for passwordless access

You can now run psql commands without password prompts:

  psql -h localhost -p 5433 -U postgres -d open_navigator
  
Or use commands like:

  psql -h localhost -p 5433 -U postgres -d open_navigator -c 'SELECT version();'

The password is set via PGPASSWORD environment variable and ~/.pgpass file.
"
