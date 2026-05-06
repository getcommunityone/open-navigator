#!/usr/bin/env python3
"""
Clear outputs from Jupyter notebooks to prevent sensitive data leaks.

Usage:
    python scripts/maintenance/clear_notebook_outputs.py [notebook_path ...]
    
    If no paths provided, clears all notebooks in scripts/datasources/
"""
import json
import sys
from pathlib import Path
from typing import List


def clear_notebook_outputs(notebook_path: Path) -> bool:
    """Clear all cell outputs from a Jupyter notebook.
    
    Returns:
        True if outputs were cleared, False if already clean
    """
    try:
        with open(notebook_path, 'r', encoding='utf-8') as f:
            notebook = json.load(f)
        
        outputs_found = False
        
        # Clear outputs from all cells
        for cell in notebook.get('cells', []):
            if cell.get('cell_type') == 'code':
                # Check if cell has outputs
                if cell.get('outputs') or cell.get('execution_count'):
                    outputs_found = True
                
                # Clear outputs and execution count
                cell['outputs'] = []
                cell['execution_count'] = None
        
        # Only write if we found outputs to clear
        if outputs_found:
            with open(notebook_path, 'w', encoding='utf-8') as f:
                json.dump(notebook, f, indent=1, ensure_ascii=False)
                f.write('\n')  # Add trailing newline
            
            print(f"✅ Cleared outputs: {notebook_path}")
            return True
        else:
            print(f"✓  Already clean:   {notebook_path}")
            return False
            
    except Exception as e:
        print(f"❌ Error processing {notebook_path}: {e}")
        return False


def find_notebooks(base_dir: Path) -> List[Path]:
    """Find all .ipynb files in directory (excluding checkpoints)."""
    return [
        nb for nb in base_dir.rglob('*.ipynb')
        if '.ipynb_checkpoints' not in str(nb)
    ]


def main():
    """Clear outputs from notebooks."""
    if len(sys.argv) > 1:
        # Clear specific notebooks provided as arguments
        notebooks = [Path(arg) for arg in sys.argv[1:]]
    else:
        # Clear all notebooks in scripts/datasources/
        project_root = Path(__file__).parent.parent.parent
        notebooks = find_notebooks(project_root / 'scripts' / 'datasources')
    
    if not notebooks:
        print("No notebooks found.")
        return 0
    
    print(f"🔍 Found {len(notebooks)} notebook(s)")
    print()
    
    cleared_count = 0
    for nb in notebooks:
        if not nb.exists():
            print(f"⚠️  Not found: {nb}")
            continue
        
        if clear_notebook_outputs(nb):
            cleared_count += 1
    
    print()
    print(f"{'='*60}")
    print(f"✅ Cleared {cleared_count}/{len(notebooks)} notebook(s)")
    
    if cleared_count > 0:
        print()
        print("⚠️  IMPORTANT: Stage the cleaned notebooks before committing:")
        for nb in notebooks:
            if nb.exists():
                print(f"    git add {nb}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
