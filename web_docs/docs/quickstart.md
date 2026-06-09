---
sidebar_position: 3
displayed_sidebar: developersSidebar
---

# Quick Start Guide

## Installation

### Option 1: Automated Installation (Recommended)

Run the installation script:

```bash
chmod +x install.sh
./install.sh
```

This will:
- Create a virtual environment
- Install all dependencies
- Create .env file from template
- Set up the project structure

### Option 2: Manual Installation

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
```

### Option 3: Using Makefile

```bash
make install
```

## Configuration

Edit the `.env` file and add your API keys:

```bash
# Required
OPENAI_API_KEY=your_openai_api_key_here

# For production (Databricks)
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=your_databricks_token_here
DATABRICKS_WAREHOUSE_ID=your_warehouse_id_here

# Optional: HuggingFace (for publishing datasets)
HF_TOKEN=hf_your_write_token_here  # Needs Write permissions
HF_ORGANIZATION=YourOrgName  # Optional
```

## Running the System

### Start the API Server

```bash
# Using the virtual environment
source venv/bin/activate
python main.py serve

# Or using make
make run
```

Visit http://localhost:8000 for the API and http://localhost:8000/docs for interactive documentation.

### Run Example Workflow

```bash
# Activate venv first
source venv/bin/activate

# Run example
python examples/example_workflow.py

# Or using make
make example
```

### Generate Heatmap

```bash
# Activate venv first
source venv/bin/activate

# Generate heatmap
python main.py generate-heatmap --output heatmap.html

# Or using make
make heatmap
```

## Docker Deployment

```bash
# Start all services
make docker-up

# Stop all services
make docker-down
```

This starts:
- API server on http://localhost:8000
- Qdrant vector DB on http://localhost:6333
- Jupyter notebook on http://localhost:8888

## Common Commands

```bash
# Activate virtual environment (required for all commands)
source venv/bin/activate

# Start API server
python main.py serve

# Run with auto-reload (development)
python main.py serve --reload

# Check system status
python main.py status

# Run tests
pytest

# Or using make
make test
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'click'"

You need to activate the virtual environment first:

```bash
source venv/bin/activate
```

### "Tesseract binary not found" or OCR errors

The `install.sh` script automatically installs tesseract-ocr on Linux (via apt) and macOS (via brew). If it failed or you're on a different system, install manually:

**Linux (Debian/Ubuntu):**
```bash
sudo apt-get update && sudo apt-get install -y tesseract-ocr
```

**macOS:**
```bash
brew install tesseract
```

**Verify installation:**
```bash
tesseract --version
```

OCR is optional but enables text extraction from scanned PDFs and images.

### "error: externally-managed-environment"

Don't use `pip install` directly. Use the virtual environment:

```bash
# Create venv if not exists
python3 -m venv venv

# Activate it
source venv/bin/activate

# Now install
pip install -r requirements.txt
```

### Permission denied when running install.sh

```bash
chmod +x install.sh
./install.sh
```

## Next Steps

1. Configure your `.env` file with API keys
2. Run the example workflow: `make example`
3. Start the API server: `make run`
4. Check out the interactive docs: http://localhost:8000/docs
5. Generate a heatmap: `make heatmap`

For more details, see the main [README.md](https://github.com/getcommunityone/open-navigator/blob/main/README.md).
