#!/usr/bin/env python3
"""
Consolidate partitioned datasets back into single Parquet files.

This script reads partitioned datasets (state=AL/, state=CA/, etc.) and 
combines them into single consolidated files that work with HuggingFace datasets.

Usage:
    python scripts/consolidate_partitioned_datasets.py
"""

import pyarrow.parquet as pq
import pyarrow as pa
from pathlib import Path
import shutil
import sys

def consolidate_dataset(partitioned_dir: Path, output_file: Path) -> None:
    """
    Read a partitioned dataset and write it as a single consolidated file.
    
    Args:
        partitioned_dir: Path to partitioned dataset directory
        output_file: Path to output consolidated parquet file
    """
    print(f"\n{'='*70}")
    print(f"Consolidating: {partitioned_dir.name}")
    print(f"{'='*70}")
    
    if not partitioned_dir.exists():
        print(f"⚠️  Directory not found: {partitioned_dir}")
        return
    
    try:
        # Read the entire partitioned dataset using PyArrow
        # This will handle any schema inconsistencies by taking the union of schemas
        print(f"📖 Reading partitioned data from {partitioned_dir}...")
        dataset = pq.ParquetDataset(str(partitioned_dir), use_legacy_dataset=False)
        table = dataset.read()
        
        print(f"✅ Loaded {len(table):,} rows")
        print(f"📊 Schema: {table.schema}")
        print(f"💾 Memory size: {table.nbytes / 1024 / 1024:.1f} MB")
        
        # Write consolidated file
        print(f"💾 Writing consolidated file to {output_file}...")
        pq.write_table(
            table,
            output_file,
            compression='snappy',
            use_dictionary=True,
            write_statistics=True
        )
        
        file_size = output_file.stat().st_size / 1024 / 1024
        print(f"✅ Wrote {output_file.name} ({file_size:.1f} MB)")
        
    except Exception as e:
        print(f"❌ Error consolidating {partitioned_dir.name}: {e}")
        print(f"   Will try reading with schema unification...")
        
        try:
            # Alternative approach: read all parquet files and concatenate
            parquet_files = list(partitioned_dir.rglob("*.parquet"))
            if not parquet_files:
                print(f"   No parquet files found in {partitioned_dir}")
                return
            
            print(f"   Found {len(parquet_files)} partition files")
            
            # Read all tables
            tables = []
            for i, pq_file in enumerate(parquet_files):
                if i % 10 == 0:
                    print(f"   Reading partition {i+1}/{len(parquet_files)}...")
                tables.append(pq.read_table(pq_file))
            
            # Concatenate with schema promotion
            print(f"   Concatenating {len(tables)} tables...")
            combined_table = pa.concat_tables(tables, promote=True)
            
            print(f"✅ Combined {len(combined_table):,} rows")
            print(f"📊 Unified schema: {combined_table.schema}")
            
            # Write consolidated file
            print(f"💾 Writing consolidated file to {output_file}...")
            pq.write_table(
                combined_table,
                output_file,
                compression='snappy',
                use_dictionary=True,
                write_statistics=True
            )
            
            file_size = output_file.stat().st_size / 1024 / 1024
            print(f"✅ Wrote {output_file.name} ({file_size:.1f} MB)")
            
        except Exception as e2:
            print(f"❌ Failed with alternative approach too: {e2}")
            sys.exit(1)


def main():
    """Main consolidation process."""
    gold_dir = Path("data/gold")
    
    # Partitioned datasets to consolidate
    partitioned_datasets = [
        "nonprofits_organizations",
        "nonprofits_locations", 
        "nonprofits_financials",
        "nonprofits_programs",
        "jurisdictions_cities",
        "jurisdictions_counties",
        "jurisdictions_school_districts",
        "jurisdictions_townships",
        "domains_gsa_domains"
    ]
    
    print("🔄 Consolidating Partitioned Datasets to Single Files")
    print("="*70)
    print(f"Gold directory: {gold_dir.absolute()}")
    print(f"Datasets to consolidate: {len(partitioned_datasets)}")
    print()
    
    # Create backup directory
    backup_dir = gold_dir / "partitioned_backup"
    backup_dir.mkdir(exist_ok=True)
    print(f"📦 Backup directory: {backup_dir}")
    print()
    
    consolidated_count = 0
    failed_count = 0
    
    for dataset_name in partitioned_datasets:
        partitioned_dir = gold_dir / dataset_name
        output_file = gold_dir / f"{dataset_name}.parquet"
        
        if not partitioned_dir.exists():
            print(f"⚠️  Skipping {dataset_name} (directory not found)")
            continue
        
        if not partitioned_dir.is_dir():
            print(f"⚠️  Skipping {dataset_name} (not a directory)")
            continue
            
        try:
            consolidate_dataset(partitioned_dir, output_file)
            
            # Move partitioned dir to backup
            backup_path = backup_dir / dataset_name
            if backup_path.exists():
                shutil.rmtree(backup_path)
            shutil.move(str(partitioned_dir), str(backup_path))
            print(f"📦 Moved partitioned dir to backup: {backup_path}")
            
            consolidated_count += 1
            
        except Exception as e:
            print(f"❌ Failed to consolidate {dataset_name}: {e}")
            failed_count += 1
    
    print(f"\n{'='*70}")
    print("✅ CONSOLIDATION COMPLETE")
    print(f"{'='*70}")
    print(f"✅ Consolidated: {consolidated_count} datasets")
    print(f"❌ Failed: {failed_count} datasets")
    print(f"📦 Partitioned directories backed up to: {backup_dir}")
    print()
    print("Next steps:")
    print("  1. Verify the consolidated files work with HuggingFace datasets")
    print("  2. Upload to HuggingFace Hub")
    print("  3. Remove backup directory once confirmed")
    print()


if __name__ == "__main__":
    main()
