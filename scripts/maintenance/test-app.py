"""
Helper script to test Databricks Apps deployment locally.
Simulates the Databricks Apps environment.
"""
import os
import sys
import subprocess
from pathlib import Path

def main():
    """Run local test of Databricks App."""
    print("🧪 Testing Databricks App locally...\n")
    
    # Check if frontend is built
    static_dir = Path("api/static")
    if not static_dir.exists():
        print("❌ Frontend not built. Building now...")
        subprocess.run(["npm", "run", "build"], cwd="frontend", check=True)
        print("✅ Frontend built successfully\n")
    
    # Set environment variables
    env = os.environ.copy()
    env.update({
        "DATABRICKS_HOST": os.getenv("DATABRICKS_HOST", "http://localhost:8001"),
        "LOG_LEVEL": "INFO"
    })
    
    # Run uvicorn
    print("🚀 Starting application on http://localhost:8001\n")
    print("   API docs: http://localhost:8001/api/docs")
    print("   Web UI:   http://localhost:8001\n")
    
    subprocess.run(
        ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8001", "--reload"],
        env=env
    )

if __name__ == "__main__":
    main()
