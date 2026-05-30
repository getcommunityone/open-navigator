#!/usr/bin/env python3
"""
Complete Political Economy Analysis for Tuscaloosa.

Implements all frameworks:
1. Frame Analysis - How issues are presented
2. Budget-to-Minutes Delta - Rhetoric vs. reality
3. Trade-off Mapping - What wasn't funded
4. Stakeholder Influence - Who shaped decisions
5. Temporal Analysis - Election cycles
6. Keyword Density - Governance drivers

Usage:
    python examples/tuscaloosa_political_economy.py
"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import json
from datetime import datetime
from loguru import logger

from scripts.extraction.decision_analyzer import DecisionAnalysisAgent
from scripts.extraction.budget_analyzer import BudgetAnalyzer
from scripts.extraction.temporal_analyzer import TemporalAnalyzer


async def run_complete_analysis():
    """Run all political economy analyses for Tuscaloosa."""
    
    logger.info("="*70)
    logger.info("TUSCALOOSA POLITICAL ECONOMY FORENSICS")
    logger.info("="*70)
    logger.info("\nMoving beyond record-keeping into understanding the 'WHY'")
    logger.info("behind local government decisions.\n")
    
    # Load data
    logger.info("[1/6] Loading Tuscaloosa meeting data...")
    documents = load_tuscaloosa_documents()
    
    if not documents:
        logger.error("No documents found. Run scraper first.")
        return
    
    logger.success(f"✓ Loaded {len(documents)} documents")
    
    # ================================================================
    # ANALYSIS 1: DECISION FRAMING & STAKEHOLDER INFLUENCE
    # ================================================================
    logger.info("\n[2/6] Analyzing decision frames and stakeholder influence...")
    
    # Use local Llama 3.3 8B for analysis (free, no API key needed)
    decision_analyzer = DecisionAnalysisAgent(use_local=True, model="llama3.3")
    all_decisions = []
    
    for i, doc in enumerate(documents[:10], 1):  # Limit for demo
        logger.info(f"  Processing document {i}/10...")
        decisions = decision_analyzer.analyze_document(
            doc,
            focus_topics=["health", "education", "budget", "water"]
        )
        all_decisions.extend(decisions)
    
    logger.success(f"✓ Extracted {len(all_decisions)} policy decisions")
    
    # Frame analysis
    frame_distribution = {}
    for decision in all_decisions:
        frame = decision.primary_frame or "unspecified"
        frame_distribution[frame] = frame_distribution.get(frame, 0) + 1
    
    print("\n" + "="*70)
    print("FRAMEWORK 1: FRAME ANALYSIS - The 'Language of Necessity'")
    print("="*70)
    print("\nHow Tuscaloosa frames decisions:")
    for frame, count in sorted(frame_distribution.items(), key=lambda x: x[1], reverse=True):
        print(f"  {count:2d}x {frame}")
    
    print("\n📊 Interpretation:")
    top_frame = max(frame_distribution.items(), key=lambda x: x[1])
    print(f"  Primary framing: '{top_frame[0]}' appears in {top_frame[1]} decisions")
    print(f"  This suggests Tuscaloosa prioritizes {top_frame[0].lower()} rhetoric")
    
    # ================================================================
    # ANALYSIS 2: BUDGET-TO-MINUTES DELTA
    # ================================================================
    logger.info("\n[3/6] Analyzing budget-to-minutes delta...")
    
    budget_analyzer = BudgetAnalyzer()
    
    # Extract budget data from documents
    all_budget_items = []
    for doc in documents:
        if "budget" in doc.get("title", "").lower():
            budget_items = budget_analyzer.extract_budget_from_document(doc)
            all_budget_items.extend(budget_items)
    
    if all_budget_items:
        logger.success(f"✓ Extracted {len(all_budget_items)} budget line items")
        
        # Calculate deltas
        deltas = budget_analyzer.calculate_budget_to_minutes_delta(
            all_budget_items,
            documents
        )
        
        print("\n" + "="*70)
        print("FRAMEWORK 2: BUDGET-TO-MINUTES DELTA - Rhetoric vs. Reality")
        print("="*70)
        
        # Categorize deltas
        expansions = [d for d in deltas if d.delta_type == "Expansion"]
        lip_service = [d for d in deltas if d.delta_type == "Lip Service"]
        hidden_priorities = [d for d in deltas if d.delta_type == "Hidden Priority"]
        
        print(f"\n📈 Genuine Expansions ({len(expansions)}):")
        print("   (High praise + Increased funding = Real priority)")
        for delta in expansions[:3]:
            print(f"   • {delta.line_item.category}: ${delta.line_item.change_amount:,.0f} increase")
            print(f"     Mentioned {delta.meeting_mentions}x in meetings")
            print(f"     Logic: {delta.underlying_logic}")
        
        print(f"\n🎭 Lip Service ({len(lip_service)}):")
        print("   (High praise + No/negative funding = Performative)")
        for delta in lip_service[:3]:
            print(f"   • {delta.line_item.category}: ${delta.line_item.change_amount:,.0f}")
            print(f"     Mentioned {delta.meeting_mentions}x despite funding cut")
            print(f"     Logic: {delta.underlying_logic}")
        
        print(f"\n🔒 Hidden Priorities ({len(hidden_priorities)}):")
        print("   (Little discussion + Increased funding = Quiet decisions)")
        for delta in hidden_priorities[:3]:
            print(f"   • {delta.line_item.category}: ${delta.line_item.change_amount:,.0f} increase")
            print(f"     Only mentioned {delta.meeting_mentions}x")
            print(f"     Logic: {delta.underlying_logic}")
    
    else:
        logger.warning("No budget documents found - budget analysis skipped")
    
    # ================================================================
    # ANALYSIS 3: TRADE-OFF MAPPING
    # ================================================================
    print("\n" + "="*70)
    print("FRAMEWORK 3: TRADE-OFF MAPPING - The Zero-Sum Game")
    print("="*70)
    
    # Opportunity cost analysis
    if all_budget_items:
        opp_cost_map = budget_analyzer.generate_opportunity_cost_map(
            all_budget_items,
            all_decisions
        )
        
        print(f"\n⚖️  Total Opportunity Costs Identified: {opp_cost_map['total_opportunity_costs']}")
        if opp_cost_map['total_dollars_lost']:
            print(f"   Total dollars lost/rejected: ${opp_cost_map['total_dollars_lost']:,.0f}")
        
        print("\n   What was NOT funded:")
        for cost in opp_cost_map['costs'][:5]:
            if cost['type'] == 'budget_cut':
                print(f"   • {cost['could_have_funded']}")
            else:
                print(f"   • Rejected: {cost['option']}")
                print(f"     Reason: {cost['reason_rejected']}")
    
    # Explicit tradeoffs from decisions
    print("\n   Explicit trade-offs discussed:")
    all_tradeoffs = []
    for decision in all_decisions:
        all_tradeoffs.extend(decision.tradeoffs_discussed)
    
    from collections import Counter
    tradeoff_types = Counter(t.get('tradeoff', '') for t in all_tradeoffs)
    
    for tradeoff, count in tradeoff_types.most_common(5):
        print(f"   {count}x {tradeoff}")
    
    # ================================================================
    # ANALYSIS 4: STAKEHOLDER INFLUENCE
    # ================================================================
    print("\n" + "="*70)
    print("FRAMEWORK 4: STAKEHOLDER INFLUENCE - Who Shapes Decisions")
    print("="*70)
    
    # Aggregate stakeholder data
    all_supporters = []
    all_opponents = []
    
    for decision in all_decisions:
        all_supporters.extend(decision.supporters)
        all_opponents.extend(decision.opponents)
    
    print(f"\n👥 Total supporters across all decisions: {len(all_supporters)}")
    print(f"   Total opponents: {len(all_opponents)}")
    
    # Most influential supporters
    supporter_names = [s.get('name', 'Unknown') for s in all_supporters]
    supporter_counts = Counter(supporter_names)
    
    print("\n   Most active supporters:")
    for name, count in supporter_counts.most_common(5):
        print(f"   • {name}: appeared {count}x")
    
    # Alignment scoring
    decisions_with_public_input = [d for d in all_decisions 
                                  if len(d.supporters) + len(d.opponents) > 0]
    
    if decisions_with_public_input:
        print(f"\n📊 Alignment Analysis:")
        print(f"   {len(decisions_with_public_input)} decisions had public input")
        print(f"   Analyzing whether boards follow public sentiment...")
        
        # This would require comparing final vote to public comment ratio
        # Simplified version:
        aligned = sum(1 for d in decisions_with_public_input 
                     if len(d.supporters) > len(d.opponents) and d.outcome == "approved")
        
        print(f"   {aligned} decisions aligned with majority public sentiment")
    
    # ================================================================
    # ANALYSIS 5: TEMPORAL / ELECTION CYCLE
    # ================================================================
    logger.info("\n[4/6] Analyzing temporal patterns...")
    
    temporal_analyzer = TemporalAnalyzer()
    
    # Define election dates for Tuscaloosa (example - would need real data)
    election_dates = [
        datetime(2024, 11, 5),  # 2024 election
        datetime(2022, 11, 8),  # 2022 election
    ]
    
    election_patterns = temporal_analyzer.analyze_election_cycle(
        all_decisions,
        "Tuscaloosa",
        election_dates
    )
    
    print("\n" + "="*70)
    print("FRAMEWORK 5: TEMPORAL ANALYSIS - Election Cycle Influence")
    print("="*70)
    
    for pattern in election_patterns:
        print(f"\n📅 Election: {pattern.election_date.strftime('%B %Y')}")
        print(f"   Decisions 6 months before: {pattern.decisions_6mo_before}")
        print(f"   Decisions 6 months after: {pattern.decisions_post_election}")
        
        if pattern.pre_election_spike:
            print(f"   ⚠️  PRE-ELECTION SPIKE DETECTED")
        
        if pattern.stadium_or_parks_pre_election:
            print(f"   🏟️  High-visibility projects before election:")
            for project in pattern.stadium_or_parks_pre_election:
                print(f"      • {project}")
        
        print(f"   📊 Inference: {pattern.inference}")
    
    # Contention scores
    contention_metrics = temporal_analyzer.calculate_contention_scores(all_decisions)
    
    high_contention = [c for c in contention_metrics if c.contention_level == "High"]
    
    print(f"\n⚔️  Contentious Decisions:")
    print(f"   {len(high_contention)} decisions had high contention (>30% nays)")
    
    for metric in high_contention[:5]:
        print(f"   • {metric.decision_summary[:60]}...")
        print(f"     Vote: {metric.ayes}-{metric.nays} (Score: {metric.contention_score:.1%})")
        print(f"     {metric.public_comments} public comments")
    
    # ================================================================
    # ANALYSIS 6: KEYWORD DENSITY & GOVERNANCE LOGIC
    # ================================================================
    logger.info("\n[5/6] Analyzing keyword density and governance logic...")
    
    keyword_densities = temporal_analyzer.analyze_keyword_density(documents)
    
    print("\n" + "="*70)
    print("FRAMEWORK 6: KEYWORD DENSITY - What Drives Governance")
    print("="*70)
    
    print("\n🔑 Top keywords (per 1000 words):")
    for keyword, density in list(keyword_densities.items())[:15]:
        category, term = keyword.split(':')
        print(f"   {density:5.2f}x  {term:20s} ({category})")
    
    # Infer governance logic
    governance_logic = temporal_analyzer.infer_governance_logic(
        keyword_densities,
        contention_metrics,
        election_patterns
    )
    
    print("\n" + "="*70)
    print("SYNTHESIS: TUSCALOOSA'S GOVERNANCE LOGIC")
    print("="*70)
    
    print(f"\n🎯 Primary Driver:")
    print(f"   {governance_logic['primary_driver']}")
    
    print(f"\n⚡ Decision Style:")
    print(f"   {governance_logic['decision_style']}")
    
    print(f"\n📊 Urgency Pattern:")
    print(f"   {governance_logic['urgency_pattern']}")
    
    print(f"\n🗳️  Election Influence:")
    print(f"   {governance_logic['election_influence']}")
    
    print(f"\n📝 Overall Summary:")
    print(f"   {governance_logic['summary']}")
    
    # ================================================================
    # SAVE RESULTS
    # ================================================================
    logger.info("\n[6/6] Saving analysis results...")
    
    output = {
        "analysis_date": datetime.now().isoformat(),
        "jurisdiction": "Tuscaloosa, AL",
        "documents_analyzed": len(documents),
        "decisions_extracted": len(all_decisions),
        "frame_distribution": frame_distribution,
        "budget_deltas": len(deltas) if all_budget_items else 0,
        "contention_metrics": {
            "high_contention": len(high_contention),
            "avg_contention_score": governance_logic['avg_contention_score']
        },
        "governance_logic": governance_logic,
        "keyword_densities": keyword_densities
    }
    
    output_file = Path("output/tuscaloosa_political_economy_analysis.json")
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    logger.success(f"✓ Saved complete analysis to {output_file}")
    
    # Save markdown report
    report_file = Path("output/TUSCALOOSA_GOVERNANCE_REPORT.md")
    with open(report_file, 'w') as f:
        f.write(generate_markdown_report(
            frame_distribution,
            deltas if all_budget_items else [],
            contention_metrics,
            governance_logic
        ))
    
    logger.success(f"✓ Saved markdown report to {report_file}")
    
    print("\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70)
    print(f"\nYou now understand:")
    print(f"  ✅ How Tuscaloosa frames decisions (rhetoric)")
    print(f"  ✅ What actually gets funded (resource reality)")
    print(f"  ✅ What trade-offs were made (opportunity costs)")
    print(f"  ✅ Who influences decisions (stakeholder power)")
    print(f"  ✅ When decisions happen (temporal patterns)")
    print(f"  ✅ WHY decisions are made (governance logic)")
    print(f"\nThis is political economy forensics in action! 🔍")


def load_tuscaloosa_documents() -> List[Dict[str, Any]]:
    """Load all Tuscaloosa meeting documents."""
    documents = []
    
    # Load from output directory
    for json_file in Path("output").rglob("*.json"):
        if "tuscaloosa" in str(json_file).lower():
            try:
                with open(json_file) as f:
                    docs = json.load(f)
                    if isinstance(docs, list):
                        documents.extend(docs)
            except:
                pass
    
    return documents


def generate_markdown_report(
    frame_dist: Dict,
    deltas: List,
    contention: List,
    governance: Dict
) -> str:
    """Generate human-readable markdown report."""
    
    report = f"""# Tuscaloosa Governance Analysis Report

**Generated:** {datetime.now().strftime('%B %d, %Y')}

## Executive Summary

{governance.get('summary', 'Analysis complete.')}

---

## 1. Decision Framing Analysis

How Tuscaloosa presents policy choices:

"""
    
    for frame, count in sorted(frame_dist.items(), key=lambda x: x[1], reverse=True):
        report += f"- **{frame}**: {count} decisions\n"
    
    report += f"""

---

## 2. Budget-to-Minutes Delta

Comparing rhetoric to resource allocation:

**Genuine Priorities:** {len([d for d in deltas if d.delta_type == "Expansion"])}  
**Lip Service:** {len([d for d in deltas if d.delta_type == "Lip Service"])}  
**Hidden Priorities:** {len([d for d in deltas if d.delta_type == "Hidden Priority"])}

---

## 3. Contention Analysis

Decision-making consensus:

- **Average contention score:** {governance.get('avg_contention_score', 0):.1%}
- **High contention decisions:** {len([c for c in contention if c.contention_level == "High"])}

---

## 4. Governance Logic

**Primary Driver:** {governance.get('primary_driver', 'Unknown')}

**Decision Style:** {governance.get('decision_style', 'Unknown')}

**Election Influence:** {governance.get('election_influence', 'Unknown')}

---

## Methodology

This analysis uses political economy frameworks to understand the "why" behind
decisions, not just the "what." We analyze:

1. **Frame Analysis** - How issues are presented
2. **Budget Delta** - Rhetoric vs. funding reality
3. **Trade-off Mapping** - What wasn't funded
4. **Stakeholder Influence** - Who shaped outcomes
5. **Temporal Patterns** - Election cycle effects
6. **Keyword Density** - Governance drivers

For questions or methodology details, see the project documentation.
"""
    
    return report


if __name__ == "__main__":
    asyncio.run(run_complete_analysis())
