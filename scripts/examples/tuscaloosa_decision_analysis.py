#!/usr/bin/env python3
"""
Example: Deep decision analysis for Tuscaloosa meetings.

This script demonstrates how to extract:
- How decisions were framed
- What options were evaluated  
- What tradeoffs were discussed
- What rationales were provided

Usage:
    python examples/tuscaloosa_decision_analysis.py
"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import json
from loguru import logger

from scripts.extraction.decision_analyzer import DecisionAnalysisAgent, PolicyDecision


async def analyze_tuscaloosa_decisions():
    """
    Analyze decision-making in Tuscaloosa meetings.
    """
    logger.info("="*60)
    logger.info("TUSCALOOSA DECISION ANALYSIS")
    logger.info("="*60)
    
    # Initialize decision analyzer
    analyzer = DecisionAnalysisAgent()
    
    # Load Tuscaloosa documents
    output_dir = Path("output/tuscaloosa")
    all_documents = []
    
    if output_dir.exists():
        for json_file in output_dir.glob("*.json"):
            try:
                with open(json_file) as f:
                    docs = json.load(f)
                    if isinstance(docs, list):
                        all_documents.extend(docs)
            except Exception as e:
                logger.warning(f"Could not load {json_file}: {e}")
    
    if not all_documents:
        logger.error("No Tuscaloosa documents found in output/tuscaloosa/")
        logger.info("Run the scraper first:")
        logger.info("  python main.py scrape --state AL --municipality Tuscaloosa \\")
        logger.info("    --url https://tuscaloosaal.suiteonemedia.com --platform suiteonemedia")
        return
    
    logger.info(f"Analyzing {len(all_documents)} Tuscaloosa documents")
    
    # Analyze decisions in each document
    all_decisions = []
    
    for i, doc in enumerate(all_documents[:10], 1):  # Limit to 10 for demo
        logger.info(f"\n[{i}/{min(10, len(all_documents))}] Analyzing: {doc.get('title', 'Unknown')[:60]}...")
        
        # Focus on health-related topics
        decisions = analyzer.analyze_document(
            document=doc,
            focus_topics=["health", "dental", "water", "fluoride", "public health"]
        )
        
        if decisions:
            logger.success(f"  Found {len(decisions)} decisions")
            all_decisions.extend(decisions)
            
            # Show summary
            for decision in decisions:
                logger.info(f"    • {decision.decision_summary[:80]}...")
                logger.info(f"      Frame: {decision.primary_frame}")
                logger.info(f"      Outcome: {decision.outcome}")
        else:
            logger.info(f"  No decisions found")
    
    # Save results
    logger.info(f"\n{'='*60}")
    logger.info(f"ANALYSIS COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Total decisions extracted: {len(all_decisions)}")
    
    if all_decisions:
        # Save as JSON
        json_output = Path("output/tuscaloosa_decisions_analysis.json")
        with open(json_output, 'w') as f:
            json.dump(
                [analyzer._decision_to_dict(d) for d in all_decisions],
                f,
                indent=2,
                default=str
            )
        logger.success(f"✓ Saved detailed analysis to {json_output}")
        
        # Save as Markdown report
        md_output = Path("output/tuscaloosa_decisions_report.md")
        with open(md_output, 'w') as f:
            f.write(analyzer.export_decision_analysis(all_decisions, format="markdown"))
        logger.success(f"✓ Saved markdown report to {md_output}")
        
        # Print sample
        logger.info("\n" + "="*60)
        logger.info("SAMPLE DECISION ANALYSIS")
        logger.info("="*60)
        
        sample = all_decisions[0]
        
        print(f"\n📋 Decision: {sample.decision_summary}")
        print(f"\n🎯 Outcome: {sample.outcome}")
        
        print(f"\n🔍 How was this framed?")
        print(f"   Primary frame: {sample.primary_frame}")
        if sample.competing_frames:
            print(f"   Competing frames: {', '.join(sample.competing_frames)}")
        
        print(f"\n⚖️  What options were considered?")
        if sample.options_considered:
            for i, opt in enumerate(sample.options_considered, 1):
                print(f"   {i}. {opt.get('option', 'Unknown')}")
                if opt.get('pros'):
                    print(f"      Pros: {', '.join(opt['pros'])}")
                if opt.get('cons'):
                    print(f"      Cons: {', '.join(opt['cons'])}")
        else:
            print("   (No options explicitly listed)")
        
        print(f"\n   Chosen: {sample.chosen_option}")
        
        print(f"\n🔄 What tradeoffs were discussed?")
        if sample.tradeoffs_discussed:
            for tradeoff in sample.tradeoffs_discussed:
                print(f"   • {tradeoff.get('tradeoff', 'Unknown')}")
                print(f"     {tradeoff.get('discussion', '')[:100]}...")
        else:
            print("   (No explicit tradeoffs mentioned)")
        
        print(f"\n💡 Primary rationale:")
        print(f"   {sample.primary_rationale}")
        
        if sample.supporting_rationales:
            print(f"\n   Supporting reasons:")
            for reason in sample.supporting_rationales:
                print(f"   • {reason}")
        
        print(f"\n📊 Evidence cited:")
        if sample.evidence_cited:
            for evidence in sample.evidence_cited:
                print(f"   • {evidence.get('type', 'Unknown')}: {evidence.get('description', '')}")
        else:
            print("   (No evidence explicitly cited)")
        
        print(f"\n👥 Stakeholder positions:")
        print(f"   Supporters: {len(sample.supporters)}")
        for supporter in sample.supporters[:3]:
            print(f"     • {supporter.get('name', 'Unknown')} ({supporter.get('role', '')})")
            print(f"       Argument: {supporter.get('argument', '')[:80]}...")
        
        print(f"   Opponents: {len(sample.opponents)}")
        for opponent in sample.opponents[:3]:
            print(f"     • {opponent.get('name', 'Unknown')} ({opponent.get('role', '')})")
            print(f"       Concern: {opponent.get('argument', '')[:80]}...")
        
        if sample.vote_result:
            print(f"\n🗳️  Vote: {sample.vote_result}")
        
        print(f"\n✅ Confidence: {sample.confidence_score:.1%}")
        
        print("\n" + "="*60)
        
        # Analysis by frame type
        logger.info("\nDECISION FRAMING ANALYSIS")
        logger.info("="*60)
        
        frame_counts = {}
        for decision in all_decisions:
            frame = decision.primary_frame or "unspecified"
            frame_counts[frame] = frame_counts.get(frame, 0) + 1
        
        print("\nHow Tuscaloosa frames policy decisions:")
        for frame, count in sorted(frame_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {count:2d}x {frame}")
        
        # Evidence usage analysis
        logger.info("\nEVIDENCE USAGE ANALYSIS")
        logger.info("="*60)
        
        evidence_types = {}
        for decision in all_decisions:
            for evidence in decision.evidence_cited:
                ev_type = evidence.get('type', 'unknown')
                evidence_types[ev_type] = evidence_types.get(ev_type, 0) + 1
        
        if evidence_types:
            print("\nTypes of evidence cited:")
            for ev_type, count in sorted(evidence_types.items(), key=lambda x: x[1], reverse=True):
                print(f"  {count:2d}x {ev_type}")
        else:
            print("\n(No explicit evidence citations found)")
        
        # Tradeoff analysis
        logger.info("\nTRADEOFF ANALYSIS")
        logger.info("="*60)
        
        all_tradeoffs = []
        for decision in all_decisions:
            for tradeoff in decision.tradeoffs_discussed:
                all_tradeoffs.append(tradeoff.get('tradeoff', ''))
        
        if all_tradeoffs:
            print(f"\nCommon tradeoffs in Tuscaloosa decision-making:")
            from collections import Counter
            tradeoff_counts = Counter(all_tradeoffs)
            for tradeoff, count in tradeoff_counts.most_common(5):
                print(f"  {count}x {tradeoff}")
        else:
            print("\n(No explicit tradeoffs documented)")
        
    else:
        logger.warning("No decisions were extracted from the documents")
        logger.info("This could mean:")
        logger.info("  1. Documents don't contain explicit decisions/votes")
        logger.info("  2. Documents are agendas (not minutes with outcomes)")
        logger.info("  3. More specific meeting minutes are needed")


if __name__ == "__main__":
    asyncio.run(analyze_tuscaloosa_decisions())
