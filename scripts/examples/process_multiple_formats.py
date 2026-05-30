#!/usr/bin/env python3
"""
Example: Process multiple document formats and save to Parquet.

This demonstrates how to handle PDFs, PowerPoint, Word, Excel, etc.
from government websites and store them efficiently.
"""

import asyncio
import pandas as pd
from pathlib import Path
from scripts.extraction.universal_extractor import UniversalDocumentExtractor
from loguru import logger


async def process_jurisdiction_all_formats(jurisdiction_name: str, document_urls: list) -> pd.DataFrame:
    """
    Process all document formats from a jurisdiction.
    
    Args:
        jurisdiction_name: Name of jurisdiction
        document_urls: List of document URLs (any format)
        
    Returns:
        DataFrame with extracted text
    """
    logger.info(f"Processing {len(document_urls)} documents from {jurisdiction_name}")
    
    extractor = UniversalDocumentExtractor()
    results = []
    
    for i, url in enumerate(document_urls, 1):
        logger.info(f"  [{i}/{len(document_urls)}] Processing {url}")
        
        # Extract text (works for any format!)
        result = extractor.extract_from_url(url)
        
        if result['success']:
            logger.success(f"    ✅ {result['format']}: {result['text_length']} characters")
            
            results.append({
                'jurisdiction': jurisdiction_name,
                'url': result['url'],
                'format': result['format'],
                'text': result['text'],
                'file_size_kb': result['file_size_kb'],
                'text_length': result['text_length']
            })
        else:
            logger.warning(f"    ❌ Failed: {result.get('error', 'Unknown error')}")
    
    extractor.close()
    
    return pd.DataFrame(results)


async def example_tuscaloosa():
    """Example: Process Tuscaloosa documents (mixed formats)."""
    
    # Example URLs (these are fictional - replace with real URLs)
    document_urls = [
        # PDFs (most common)
        "https://tuscaloosaal.suiteonemedia.com/agenda_2025_03_15.pdf",
        "https://tuscaloosaal.suiteonemedia.com/minutes_2025_03_01.pdf",
        
        # PowerPoint presentations
        "https://tuscaloosaal.suiteonemedia.com/budget_presentation.pptx",
        
        # Word documents
        "https://tuscaloosaal.suiteonemedia.com/policy_draft.docx",
        
        # Excel spreadsheets
        "https://tuscaloosaal.suiteonemedia.com/financial_report.xlsx",
        
        # HTML pages
        "https://tuscaloosaal.suiteonemedia.com/public_notice.html",
    ]
    
    # Process all formats
    df = await process_jurisdiction_all_formats("Tuscaloosa, AL", document_urls)
    
    # Save to Parquet (all formats in one file!)
    output_file = "data/tuscaloosa_all_formats.parquet"
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_file, compression='snappy', index=False)
    
    # Show results
    logger.success(f"\n✅ Processed {len(df)} documents from Tuscaloosa")
    logger.success(f"   Saved to: {output_file}")
    logger.success(f"   File size: {Path(output_file).stat().st_size / 1024:.1f} KB")
    
    # Show format breakdown
    format_counts = df['format'].value_counts()
    logger.info("\nFormat breakdown:")
    for fmt, count in format_counts.items():
        logger.info(f"  {fmt}: {count} documents")
    
    return df


async def example_multiple_jurisdictions():
    """Example: Process multiple jurisdictions with mixed formats."""
    
    jurisdictions = {
        "Tuscaloosa, AL": [
            "https://example.com/tuscaloosa_agenda.pdf",
            "https://example.com/tuscaloosa_presentation.pptx",
        ],
        "Birmingham, AL": [
            "https://example.com/birmingham_minutes.docx",
            "https://example.com/birmingham_budget.xlsx",
        ],
        "Mobile, AL": [
            "https://example.com/mobile_agenda.pdf",
            "https://example.com/mobile_policy.html",
        ]
    }
    
    all_data = []
    
    for jurisdiction, urls in jurisdictions.items():
        df = await process_jurisdiction_all_formats(jurisdiction, urls)
        all_data.append(df)
    
    # Combine all jurisdictions
    combined = pd.concat(all_data, ignore_index=True)
    
    # Save to single Parquet file
    output_file = "data/alabama_cities_all_formats.parquet"
    combined.to_parquet(output_file, compression='snappy', index=False)
    
    logger.success(f"\n✅ Processed {len(combined)} total documents")
    logger.success(f"   Jurisdictions: {combined['jurisdiction'].nunique()}")
    logger.success(f"   Formats: {', '.join(combined['format'].unique())}")
    logger.success(f"   Saved to: {output_file}")
    
    return combined


if __name__ == "__main__":
    import sys
    
    # Choose example
    if len(sys.argv) > 1 and sys.argv[1] == "multi":
        print("Running multiple jurisdictions example...")
        df = asyncio.run(example_multiple_jurisdictions())
    else:
        print("Running Tuscaloosa example...")
        print("(Use 'python examples/process_multiple_formats.py multi' for multiple jurisdictions)")
        print()
        df = asyncio.run(example_tuscaloosa())
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Total documents: {len(df)}")
    print(f"Total text: {df['text_length'].sum():,} characters")
    print(f"Average per doc: {df['text_length'].mean():.0f} characters")
    print()
    print("Format distribution:")
    print(df['format'].value_counts())
