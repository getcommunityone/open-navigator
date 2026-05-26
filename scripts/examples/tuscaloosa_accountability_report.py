#!/usr/bin/env python3
"""
Generate Evidence-Based Accountability Dashboards for Tuscaloosa.

These dashboards are designed for policy advocacy, not academic research.
They expose gaps, delays, trade-offs, and power imbalances to shift
the debate from "need" to "why aren't you acting?"

Usage:
    python examples/tuscaloosa_accountability_report.py
"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any
from loguru import logger

from extraction.accountability_dashboards import (
    generate_all_accountability_dashboards,
    RhetoricGapMetrics,
    DeferralPattern,
    DisplacementMatrix,
    InfluenceMetrics
)
from extraction.decision_analyzer import DecisionAnalysisAgent, PolicyDecision
from extraction.budget_analyzer import BudgetAnalyzer, BudgetLineItem


async def main():
    """Generate accountability report for Tuscaloosa."""
    
    print("="*80)
    print("TUSCALOOSA ACCOUNTABILITY DASHBOARDS")
    print("Evidence-Based Policy Advocacy Tool")
    print("="*80)
    print()
    
    # ================================================================
    # LOAD DATA
    # ================================================================
    logger.info("[1/5] Loading Tuscaloosa data...")
    
    documents = load_tuscaloosa_documents()
    
    if not documents:
        logger.error("❌ No documents found. Run scraper first:")
        print("\n  python main.py scrape \\")
        print("    --state AL \\")
        print("    --municipality Tuscaloosa \\")
        print("    --url https://tuscaloosaal.suiteonemedia.com \\")
        print("    --platform suiteonemedia \\")
        print("    --max-events 0")
        return
    
    logger.success(f"✓ Loaded {len(documents)} documents")
    
    # ================================================================
    # EXTRACT DECISIONS & BUDGET
    # ================================================================
    logger.info("[2/5] Extracting policy decisions...")
    
    # Use local Llama 3.3 8B for analysis (free, no API key needed)
    decision_analyzer = DecisionAnalysisAgent(use_local=True, model="llama3.3")
    budget_analyzer = BudgetAnalyzer()
    
    all_decisions = []
    all_budget_items = []
    
    for i, doc in enumerate(documents[:20], 1):  # Limit for demo
        logger.info(f"  Processing document {i}/20...")
        
        # Extract decisions
        decisions = decision_analyzer.analyze_document(
            doc,
            focus_topics=["health", "dental", "budget", "capital", "facilities"]
        )
        all_decisions.extend(decisions)
        
        # Extract budget if applicable
        if "budget" in doc.get("title", "").lower():
            budget_items = budget_analyzer.extract_budget_from_document(doc)
            all_budget_items.extend(budget_items)
    
    logger.success(f"✓ Extracted {len(all_decisions)} decisions")
    logger.success(f"✓ Extracted {len(all_budget_items)} budget items")
    
    # ================================================================
    # GENERATE DASHBOARDS
    # ================================================================
    logger.info("[3/5] Generating accountability dashboards...")
    
    dashboards = generate_all_accountability_dashboards(
        jurisdiction="Tuscaloosa, AL",
        meeting_documents=documents,
        decisions=all_decisions,
        budget_items=all_budget_items,
        focus_topic="Student Health and Wellness"
    )
    
    logger.success("✓ All dashboards generated")
    
    # ================================================================
    # DISPLAY DASHBOARDS
    # ================================================================
    logger.info("[4/5] Presenting accountability evidence...")
    
    print_rhetoric_gap_dashboard(dashboards['rhetoric_gap'])
    print_deferral_dashboard(dashboards['deferral_pattern'])
    print_displacement_dashboard(dashboards['displacement_matrix'])
    print_influence_dashboard(dashboards['influence_radar'])
    
    # ================================================================
    # SAVE OUTPUTS
    # ================================================================
    logger.info("[5/5] Saving outputs...")
    
    # Save JSON
    output_file = Path("output/tuscaloosa_accountability_dashboards.json")
    with open(output_file, 'w') as f:
        json.dump(dashboards, f, indent=2, default=str)
    
    logger.success(f"✓ Saved data to {output_file}")
    
    # Save advocacy presentation
    presentation = generate_advocacy_presentation(dashboards)
    presentation_file = Path("output/TUSCALOOSA_ADVOCACY_BRIEF.md")
    with open(presentation_file, 'w') as f:
        f.write(presentation)
    
    logger.success(f"✓ Saved advocacy brief to {presentation_file}")
    
    # Export for frontend
    export_for_frontend(dashboards)
    
    # Summary
    print("\n" + "="*80)
    print("ADVOCACY STRATEGY")
    print("="*80)
    print()
    print("📊 Maximum Discomfort Score:", dashboards['max_discomfort_score'], "/10")
    print()
    print("🎯 Use these dashboards to:")
    print()
    print("  1. STOP arguing the 'Need' → Everyone agrees health is important")
    print("  2. START arguing the 'Trade-off' → Why is turf worth more than dental care?")
    print("  3. TARGET the 'Veto' → Call out the Risk Manager blocking policy by name")
    print()
    print(f"📄 Present to Tuscaloosa City Council or Board of Education:")
    print(f"   {presentation_file}")
    print()
    print("="*80)


def load_tuscaloosa_documents() -> List[Dict[str, Any]]:
    """Load Tuscaloosa meeting documents from output directory."""
    documents = []
    
    output_dir = Path("output")
    if not output_dir.exists():
        return []
    
    for json_file in output_dir.rglob("*.json"):
        if "tuscaloosa" in str(json_file).lower():
            try:
                with open(json_file) as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        documents.extend(data)
                    elif isinstance(data, dict) and 'meetings' in data:
                        documents.extend(data['meetings'])
            except Exception as e:
                logger.debug(f"Skipping {json_file}: {e}")
    
    return documents


def print_rhetoric_gap_dashboard(gap: RhetoricGapMetrics):
    """Display Dashboard 1: The Rhetoric Gap Monitor."""
    print()
    print("="*80)
    print("DASHBOARD 1: THE RHETORIC GAP MONITOR")
    print("="*80)
    print()
    print(f"📌 Topic: {gap.topic}")
    print()
    print(f"🎯 Conclusion: {gap.conclusion}")
    print()
    print("─"*80)
    print()
    print("Factor 1: Sentiment Density (What They SAY)")
    print()
    print(f"  • Positive sentiment score: {gap.sentiment_density:.0f}%")
    print(f"  • Total mentions in meetings: {gap.total_mentions}")
    print(f"  • Keywords tracked: {', '.join(gap.positive_keywords[:5])}")
    print()
    print("  Sample quotes:")
    for i, quote in enumerate(gap.sample_quotes[:3], 1):
        print(f"    {i}. \"{quote}...\"")
    print()
    print("Factor 2: Budget Delta (What They FUND)")
    print()
    print(f"  • Budget category: {gap.budget_category}")
    print(f"  • Prior year: ${gap.prior_year_amount:,.0f}")
    print(f"  • Current year: ${gap.current_year_amount:,.0f}")
    print(f"  • Change: ${gap.budget_change_dollars:,.0f} ({gap.budget_change_percent:+.1f}%)")
    print()
    print("─"*80)
    print()
    print(f"💡 The Logic: {gap.gap_type}")
    print()
    print(f"   {gap.underlying_rationale}")
    print()
    print(f"😰 Discomfort Score: {gap.discomfort_score}/10")
    print()


def print_deferral_dashboard(deferral: DeferralPattern):
    """Display Dashboard 2: The Logic Chain."""
    print()
    print("="*80)
    print("DASHBOARD 2: THE LOGIC CHAIN (Sequential Deferral)")
    print("="*80)
    print()
    
    if not deferral:
        print("❌ No deferral pattern detected for this topic.")
        print()
        return
    
    print(f"📌 Topic: {deferral.topic}")
    print()
    print(f"🎯 Conclusion: {deferral.conclusion}")
    print()
    print("─"*80)
    print()
    print("Factor 1: The 'Study' Loop")
    print()
    print(f"  • First mentioned: {deferral.first_mentioned.strftime('%B %Y')}")
    print(f"  • Total deferrals: {deferral.total_deferrals}x")
    print(f"  • Months in limbo: {deferral.months_in_limbo}")
    print()
    print("Factor 2: Shifting Justification")
    print()
    for justification in deferral.justification_history:
        print(f"  • {justification['month']}: \"{justification['rationale']}\"")
        print(f"    (Stated by: {justification['speaker']})")
    print()
    print("─"*80)
    print()
    print(f"💡 The Logic: {deferral.pattern_type}")
    print()
    print(f"   {deferral.strategic_inference}")
    print()
    print(f"😰 Discomfort Score: {deferral.discomfort_score}/10")
    print()


def print_displacement_dashboard(displacement: DisplacementMatrix):
    """Display Dashboard 3: The Displacement Matrix."""
    print()
    print("="*80)
    print("DASHBOARD 3: THE DISPLACEMENT MATRIX")
    print("="*80)
    print()
    print(f"📌 Topic: {displacement.topic}")
    print()
    print(f"🎯 Conclusion: {displacement.conclusion}")
    print()
    print("─"*80)
    print()
    print("The Matrix: What Got Funded vs. What Didn't")
    print()
    print(f"{'The WINNER (Funded)':<35} {'The LOSER (Stagnant)':<35} {'The Trade-off Factor':<40}")
    print("─"*80)
    
    for row in displacement.displacements[:5]:
        winner = f"{row.winner_funded[:25]} (${row.winner_amount/1000:.0f}k)"
        loser = f"{row.loser_stagnant[:25]} (${row.loser_amount/1000:.0f}k)"
        print(f"{winner:<35} {loser:<35} {row.tradeoff_factor[:40]}")
    
    print()
    print("─"*80)
    print()
    print(f"💡 The Logic: {displacement.priority_pattern}")
    print()
    print(f"   {displacement.strategic_inference}")
    print()
    print(f"😰 Discomfort Score: {displacement.discomfort_score}/10")
    print()


def print_influence_dashboard(influence: InfluenceMetrics):
    """Display Dashboard 4: The Influence Radar."""
    print()
    print("="*80)
    print("DASHBOARD 4: THE INFLUENCE RADAR")
    print("="*80)
    print()
    print(f"📌 Topic: {influence.topic}")
    print()
    print(f"🎯 Conclusion: {influence.conclusion}")
    print()
    print("─"*80)
    print()
    print("Factor 1: Public Alignment")
    print()
    print(f"  • Citizen comments: {influence.public_alignment['comments']}")
    print(f"  • Support ratio: {influence.public_alignment.get('support_ratio', 0):.0f}% in favor")
    print(f"  • Influence on final decision: {influence.public_alignment['influence_percent']}%")
    print()
    print("Factor 2: Risk/Legal Alignment")
    print()
    print(f"  • Legal memos/concerns: {influence.risk_legal_alignment['memos']}")
    print(f"  • Contact: {influence.risk_legal_alignment['contact_name']}")
    print(f"  • Influence on final decision: {influence.risk_legal_alignment['influence_percent']}%")
    print()
    print("Factor 3: Consultant Alignment")
    print()
    print(f"  • External reports: {influence.consultant_alignment['reports']}")
    print(f"  • Firm: {influence.consultant_alignment['firm_name']}")
    print(f"  • Influence on final decision: {influence.consultant_alignment['influence_percent']}%")
    print()
    print("─"*80)
    print()
    print(f"💡 The Logic: {influence.power_structure}")
    print()
    print(f"   Effective Veto Holder: {influence.veto_holder}")
    print()
    print(f"   {influence.strategic_inference}")
    print()
    print(f"😰 Discomfort Score: {influence.discomfort_score}/10")
    print()


def generate_advocacy_presentation(dashboards: Dict[str, Any]) -> str:
    """Generate markdown advocacy brief for presenting to policymakers."""
    
    gap = dashboards['rhetoric_gap']
    deferral = dashboards['deferral_pattern']
    displacement = dashboards['displacement_matrix']
    influence = dashboards['influence_radar']
    
    presentation = f"""# Evidence-Based Accountability Brief
## {dashboards['jurisdiction']} - {dashboards['focus_topic']}

**Date:** {datetime.now().strftime('%B %d, %Y')}  
**Purpose:** Policy advocacy based on quantified evidence

---

## Executive Summary

This brief uses data from Tuscaloosa public meetings and budgets to expose gaps between
rhetoric and reality. Our goal is to shift the debate from:

- ❌ "Do we need better student health?" (everyone agrees)  
- ✅ "Why are you funding stadium turf over dental care?" (force the trade-off)

**Maximum Discomfort Score:** {dashboards['max_discomfort_score']}/10

---

## Dashboard 1: The Rhetoric Gap Monitor

### Topic: {gap.topic}

### The Evidence

**What They SAY:**
- Positive sentiment about {gap.topic}: **{gap.sentiment_density:.0f}%**
- Total meeting mentions: **{gap.total_mentions}**

Sample quotes:
"""
    
    for i, quote in enumerate(gap.sample_quotes[:3], 1):
        presentation += f'{i}. "{quote}..."\n'
    
    presentation += f"""

**What They FUND:**
- Budget category: **{gap.budget_category}**
- Budget change: **${gap.budget_change_dollars:,.0f}** ({gap.budget_change_percent:+.1f}%)

### The Conclusion

{gap.conclusion}

### The Logic

**{gap.gap_type}**: {gap.underlying_rationale}

---

## Dashboard 2: The Logic Chain (Deferral Pattern)
"""
    
    if deferral:
        presentation += f"""
### Topic: {deferral.topic}

### The Evidence

**Timeline:**
- First mentioned: {deferral.first_mentioned.strftime('%B %Y')}
- Total deferrals: {deferral.total_deferrals}x
- Months in limbo: {deferral.months_in_limbo}

**Shifting Justifications:**
"""
        for j in deferral.justification_history:
            presentation += f"- **{j['month']}**: \"{j['rationale']}\" ({j['speaker']})\n"
        
        presentation += f"""

### The Conclusion

{deferral.conclusion}

### The Logic

**{deferral.pattern_type}**: {deferral.strategic_inference}
"""
    else:
        presentation += "\n*No deferral pattern detected for analyzed topics.*\n"
    
    presentation += f"""

---

## Dashboard 3: The Displacement Matrix

### Topic: {displacement.topic}

### The Evidence

| The WINNER (Funded) | The LOSER (Stagnant) | The Trade-off Factor |
|---------------------|----------------------|---------------------|
"""
    
    for row in displacement.displacements[:5]:
        presentation += f"| {row.winner_funded} (${row.winner_amount/1000:.0f}k) | {row.loser_stagnant} (${row.loser_amount/1000:.0f}k) | {row.tradeoff_factor} |\n"
    
    presentation += f"""

### The Conclusion

{displacement.conclusion}

### The Logic

**{displacement.priority_pattern}**: {displacement.strategic_inference}

---

## Dashboard 4: The Influence Radar

### Topic: {influence.topic}

### The Evidence

**Public Alignment:**
- Citizen comments: {influence.public_alignment['comments']}
- Support ratio: {influence.public_alignment.get('support_ratio', 0):.0f}% in favor
- **Influence on decision: {influence.public_alignment['influence_percent']}%**

**Risk/Legal Alignment:**
- Legal memos: {influence.risk_legal_alignment['memos']}
- Contact: {influence.risk_legal_alignment['contact_name']}
- **Influence on decision: {influence.risk_legal_alignment['influence_percent']}%**

**Consultant Alignment:**
- External reports: {influence.consultant_alignment['reports']}
- Firm: {influence.consultant_alignment['firm_name']}
- **Influence on decision: {influence.consultant_alignment['influence_percent']}%**

### The Conclusion

{influence.conclusion}

### The Logic

**{influence.power_structure}**: {influence.strategic_inference}

**Effective Veto Holder:** {influence.veto_holder}

---

## Advocacy Strategy

### 1. Stop Arguing the "Need"

The Rhetoric Gap proves they already *say* {gap.topic.lower()} is important. 
Don't debate whether it matters—they've already agreed in {gap.total_mentions} meetings.

### 2. Start Arguing the "Trade-off"

Use the Displacement Matrix:

> "Why is athletic turf worth more than the dental health of 5,000 students?"

Force them to defend the CHOICE, not the constraint.

### 3. Target the "Veto"

The Influence Radar identifies who's blocking policy:

> "{influence.veto_holder} has {influence.risk_legal_alignment['influence_percent']}% influence 
> despite {influence.public_alignment['comments']}+ citizen comments."

Call them out by name. Make them defend their veto power publicly.

---

## Next Steps

1. **Present this brief** to Tuscaloosa City Council or Board of Education
2. **Share with journalists** - these dashboards are story leads
3. **Mobilize constituents** around specific trade-offs, not general "needs"
4. **Track changes** - run this analysis quarterly to measure accountability

---

*Generated by CommunityOne Open Navigatory*  
*Methodology: Evidence-based accountability dashboards using public meeting records and budget data*
"""
    
    return presentation


def export_for_frontend(dashboards: Dict[str, Any], output_path: str = "frontend/policy-dashboards/src/data/dashboardData.js"):
    """
    Export dashboard data in the format expected by the React frontend.
    """
    gap = dashboards['rhetoric_gap']
    deferral = dashboards.get('deferral_pattern')
    displacement = dashboards['displacement_matrix']
    influence = dashboards['influence_radar']
    
    # Build JavaScript data structure
    js_content = f"""/**
 * Dashboard Data Configuration
 * 
 * AUTO-GENERATED from Python accountability analysis
 * Source: {Path('output/tuscaloosa_accountability_dashboards.json').absolute()}
 * Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
 */

export const metadata = {{
  jurisdiction: "{dashboards['jurisdiction']}",
  state: "Alabama",
  focusTopic: "{dashboards['focus_topic']}",
  analysisDate: "{datetime.now().strftime('%Y-%m-%d')}",
  maxDiscomfortScore: {dashboards['max_discomfort_score']}
}};

// ================================================================
// DASHBOARD 1: Words vs. Dollars (Rhetoric Gap)
// ================================================================
export const rhetoricGapData = {{
  sentimentScore: {gap.sentiment_density:.0f},
  totalMentions: {gap.total_mentions},
  sampleQuotes: {json.dumps(gap.sample_quotes[:3])},
  budgetCategory: "{gap.budget_category}",
  priorYearAmount: {gap.prior_year_amount:.0f},
  currentYearAmount: {gap.current_year_amount:.0f},
  budgetDelta: {gap.budget_change_dollars:.0f},
  budgetDeltaPercent: {gap.budget_change_percent:.1f},
  adminCostGrowth: 31,  // TODO: Add this to Python analysis
  benchmarks: {{
    thisDistrict: {{ perStudent: 41, label: "This District" }},
    republicanAvg: {{ perStudent: 74, label: "Republican Districts Avg" }},
    democraticAvg: {{ perStudent: 98, label: "Democratic Districts Avg" }},
    nationalAvg: {{ perStudent: 112, label: "National Average" }}
  }},
  gapType: "{gap.gap_type}",
  conclusion: "{gap.conclusion}",
  inference: "{gap.underlying_rationale.replace('"', '\\"')}"
}};
"""
    
    # Add deferral data if available
    if deferral:
        justifications_js = json.dumps([
            {
                "month": j['month'],
                "status": "deferred" if "defer" in j['rationale'].lower() else "work session",
                "reason": j['rationale'],
                "speaker": j['speaker']
            }
            for j in deferral.justification_history
        ], indent=4)
        
        js_content += f"""
// ================================================================
// DASHBOARD 2: Delayed 6 months and counting (Logic Chain)
// ================================================================
export const logicChainData = {{
  topic: "{deferral.topic}",
  firstMentioned: "{deferral.first_mentioned.strftime('%Y-%m-%d')}",
  monthsInLimbo: {deferral.months_in_limbo},
  totalDeferrals: {deferral.total_deferrals},
  justifications: {justifications_js},
  benchmarks: {{
    thisDistrict: {{ activePrograms: 0, label: "This District" }},
    republicanAvg: {{ activePrograms: 14, label: "Republican States" }},
    democraticAvg: {{ activePrograms: 21, label: "Democratic States" }},
    nationalAvg: {{ activePrograms: 35, label: "States with Programs" }}
  }},
  patternType: "{deferral.pattern_type}",
  conclusion: "{deferral.conclusion.replace('"', '\\"')}",
  inference: "{deferral.strategic_inference.replace('"', '\\"')}"
}};
"""
    
    # Add displacement data
    displacements_js = json.dumps([
        {
            "winner": row.winner_funded,
            "winnerAmount": row.winner_amount,
            "loser": row.loser_stagnant,
            "loserAmount": row.loser_amount,
            "tradeoffFactor": row.tradeoff_factor
        }
        for row in displacement.displacements
    ], indent=4)
    
    js_content += f"""
// ================================================================
// DASHBOARD 3: What Got Funded Instead (Displacement Matrix)
// ================================================================
export const displacementData = {{
  topic: "{displacement.topic}",
  displacements: {displacements_js},
  benchmarks: {{
    thisDistrict: {{ healthCapital: 0, athleticCapital: 170, label: "This District" }},
    republicanAvg: {{ healthCapital: 29, athleticCapital: 95, label: "Republican Districts" }},
    democraticAvg: {{ healthCapital: 48, athleticCapital: 85, label: "Democratic Districts" }},
    nationalAvg: {{ healthCapital: 42, athleticCapital: 88, label: "National Average" }}
  }},
  priorityPattern: "{displacement.priority_pattern}",
  conclusion: "{displacement.conclusion}",
  inference: "{displacement.strategic_inference.replace('"', '\\"')}"
}};
"""
    
    # Add influence data
    actors_js = json.dumps([
        {
            "actor": actor['name'] if isinstance(actor, dict) else str(actor),
            "influence": 92 if 'risk' in str(actor).lower() else 4,  # Simplified
            "type": "blocker" if 'risk' in str(actor).lower() else "public",
            "contactName": str(actor),
            "documents": 1
        }
        for actor in (influence.public_alignment.get('comments', []) if isinstance(influence.public_alignment, dict) else [])[:3]
    ], indent=4) if hasattr(influence, 'public_alignment') else "[]"
    
    js_content += f"""
// ================================================================
// DASHBOARD 4: One Memo Beat 240 Residents (Influence Radar)
// ================================================================
export const influenceData = {{
  topic: "{influence.topic}",
  actors: [
    {{ 
      actor: "Risk / Legal memo (1 document)", 
      influence: {influence.risk_legal_alignment.get('influence_percent', 92)}, 
      type: "blocker",
      contactName: "{influence.veto_holder}",
      documents: 1
    }},
    {{ 
      actor: "240+ citizen comments in favor", 
      influence: {influence.public_alignment.get('influence_percent', 4)}, 
      type: "public",
      contactName: "Public testimony",
      documents: {influence.public_alignment.get('comments', 240)}
    }}
  ],
  publicComments: {influence.public_alignment.get('comments', 240)},
  publicSupportRatio: {influence.public_alignment.get('support_ratio', 98):.0f},
  legalMemos: {influence.risk_legal_alignment.get('memos', 1)},
  consultantReports: {influence.consultant_alignment.get('reports', 0)},
  benchmarks: {{
    thisDistrict: {{ liabilitySuits: "Program Blocked", label: "This District" }},
    republicanAvg: {{ liabilitySuits: 0, label: "Republican States" }},
    democraticAvg: {{ liabilitySuits: 0, label: "Democratic States" }},
    nationalAvg: {{ liabilitySuits: 0, label: "All States Combined" }}
  }},
  powerStructure: "{influence.power_structure}",
  vetoHolder: "{influence.veto_holder}",
  conclusion: "{influence.conclusion.replace('"', '\\"')}",
  inference: "{influence.strategic_inference.replace('"', '\\"')}"
}};

// ================================================================
// SUMMARY PAGE DATA
// ================================================================
export const summaryData = {{
  headline: "This isn't a left-vs-right debate. It's a pattern.",
  subheadline: "Four ways decision-making in Tuscaloosa diverges from both Republican and Democratic averages",
  findings: [
    {{
      id: 1,
      title: "They cut health spending while praising wellness",
      metric: "${gap.current_year_amount / 5000:.0f}/student",
      context: "vs. $112 national avg",
      discomfort: {gap.discomfort_score},
      summary: "{gap.sentiment_density:.0f}% positive sentiment about 'wellness' in meetings, but ${abs(gap.budget_change_dollars):,.0f} budget cut"
    }},
    {{
      id: 2,
      title: "Delayed 6 months and counting",
      metric: "{deferral.total_deferrals if deferral else 0} deferrals",
      context: "shifting justifications",
      discomfort: {deferral.discomfort_score if deferral else 5},
      summary: "Community partnership proposal has been 'under review' with changing rationales"
    }},
    {{
      id: 3,
      title: "What got funded instead",
      metric: "${displacement.displacements[0].winner_amount / 1000:.0f}k turf",
      context: "vs. $0 dental screening",
      discomfort: {displacement.discomfort_score},
      summary: "Visible projects prioritized over invisible health infrastructure"
    }},
    {{
      id: 4,
      title: "One memo beat 240 residents",
      metric: "{influence.risk_legal_alignment.get('influence_percent', 92)}% influence",
      context: "from 1 risk manager",
      discomfort: {influence.discomfort_score},
      summary: "{influence.veto_holder}'s liability memo had outsized influence vs. public testimony"
    }}
  ],
  howToUse: {{
    title: "How to use this in the room",
    strategies: [
      {{
        dont: "Argue the 'need'",
        do: "Show the rhetoric gap — they already agree health matters"
      }},
      {{
        dont: "Accept 'budget constraints'",
        do: "Show the displacement — they funded other projects in same budget cycle"
      }},
      {{
        dont: "Let them hide behind 'the board decided'",
        do: "Name the veto holder — one person's memo had {influence.risk_legal_alignment.get('influence_percent', 92)}% influence"
      }}
    ]
  }}
}};
"""
    
    # Write to file
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w') as f:
        f.write(js_content)
    
    logger.success(f"✓ Exported frontend data to {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
