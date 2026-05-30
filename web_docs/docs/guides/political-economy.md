---
displayed_sidebar: policyMakersSidebar
---

# Political Economy Analysis - Implementation Status

## Summary

**YES**, the system now implements all the frameworks you described for understanding the "WHY" behind local government decisions!

---

## ✅ What's Implemented

### 1. **Frame Analysis** - The "Language of Necessity"
**Status:** ✅ FULLY IMPLEMENTED

**Files:**
- `extraction/decision_analyzer.py` - Extracts framing
- `examples/tuscaloosa_political_economy.py` - Analyzes frame distribution

**Capabilities:**
- ✅ Identifies primary frame ("Economic Development", "Public Safety", "Equity")
- ✅ Tracks competing frames
- ✅ Captures specific framing language
- ✅ Analyzes frame distribution across decisions

**Example Output:**
```
How Tuscaloosa frames decisions:
  12x public health
   8x fiscal responsibility
   5x equity/access
   3x economic development
```

---

### 2. **Budget-to-Minutes "Delta"** - Rhetoric vs. Reality
**Status:** ✅ FULLY IMPLEMENTED

**Files:**
- `extraction/budget_analyzer.py` - Budget extraction & delta calculation
- `examples/tuscaloosa_political_economy.py` - Complete analysis

**Capabilities:**
- ✅ Extracts budget line items from documents (using LLM)
- ✅ Counts meeting mentions for each budget category
- ✅ Calculates "Praise Level" (High/Medium/Low)
- ✅ Determines funding change (Expansion/Stagnant/Decreased)
- ✅ Classifies delta type:
  - **Expansion** = High praise + Increased funding (Genuine priority)
  - **Lip Service** = High praise + No funding (Performative)
  - **Hidden Priority** = No discussion + Increased funding (Bureaucratic)
- ✅ Infers underlying governance logic

**Example Output:**
```
📈 Genuine Expansions (5):
   • School Nutrition: $500,000 increase
     Mentioned 15x in meetings
     Logic: Genuine political priority

🎭 Lip Service (3):
   • Teacher Training: -$50,000 decrease
     Mentioned 12x despite funding cut
     Logic: Performative politics - low actual priority

🔒 Hidden Priorities (2):
   • IT Infrastructure: $200,000 increase
     Only mentioned 1x
     Logic: Bureaucratic inertia or avoiding scrutiny
```

---

### 3. **Trade-off Mapping** - The Zero-Sum Game
**Status:** ✅ FULLY IMPLEMENTED

**Files:**
- `extraction/decision_analyzer.py` - Extracts tradeoffs from decisions
- `extraction/budget_analyzer.py` - Opportunity cost calculation

**Capabilities:**
- ✅ Extracts explicitly discussed tradeoffs
- ✅ Maps what was NOT funded (opportunity costs)
- ✅ Identifies rejected options and reasons
- ✅ Tracks "urgency" language (emergency bypassing normal process)

**Example Output:**
```
⚖️ Trade-offs Discussed:
   3x Cost vs. long-term benefit
   2x Individual autonomy vs. community benefit
   1x Short-term pain vs. long-term gain

What was NOT funded:
   • Lost $250,000 in after-school programs
   • Rejected: Mobile dental clinic
     Reason: "Upfront cost too high in tight budget year"
```

---

### 4. **Stakeholder Influence & "The Audience"**
**Status:** ✅ FULLY IMPLEMENTED

**Files:**
- `extraction/decision_analyzer.py` - Stakeholder extraction

**Capabilities:**
- ✅ Identifies who spoke (name, role, affiliation)
- ✅ Captures their arguments
- ✅ Tracks supporters vs. opponents
- ✅ Analyzes alignment (board decision vs. public comment majority)
- ✅ Detects "pre-meeting rationale" (staff recommendations)

**Example Output:**
```
👥 Stakeholder Analysis:
   Supporters: 5
     • Health Department (Public Health Director)
       Argument: Strong evidence for prevention
     • Parent-Teacher Association
       Argument: Benefits children's health

   Opponents: 2
     • Taxpayer Association
       Concern: Cost in tight budget

   Alignment: Board voted with majority public sentiment
```

---

### 5. **Temporal Analysis** - Election Cycle
**Status:** ✅ FULLY IMPLEMENTED

**Files:**
- `extraction/temporal_analyzer.py` - Election cycle analysis

**Capabilities:**
- ✅ Tracks decisions 12mo/6mo/3mo before elections
- ✅ Identifies high-visibility projects (stadiums, parks, renovations)
- ✅ Detects pre-election spikes
- ✅ Calculates average project costs pre vs. post election
- ✅ Infers incumbency protection vs. normal variance

**Example Output:**
```
📅 Election: November 2024
   Decisions 6 months before: 15
   Decisions 6 months after: 8
   ⚠️ PRE-ELECTION SPIKE DETECTED

   🏟️ High-visibility projects before election:
      • New high school football stadium
      • Downtown park renovation
      • Elementary school roof replacement

   📊 Inference: Possible incumbency protection or legacy building
```

---

### 6. **Quantitative "Why" Indicators**
**Status:** ✅ FULLY IMPLEMENTED

**Files:**
- `extraction/temporal_analyzer.py` - All quantitative metrics

**Capabilities:**
- ✅ **Contention Score**: Ratio of Aye to Nay votes
  - High contention = conflicting trade-offs
- ✅ **Keyword Density**: "Grant" vs "Taxpayer"
  - Reveals if decisions driven by outside funding or local demand
- ✅ **Deferral Rate**: How often decisions are "tabled"
  - Indicates political sensitivity

**Example Output:**
```
🔑 Keyword Density (per 1000 words):
    8.5x  grant           (funding_source)
    3.2x  taxpayer        (funding_source)
    4.1x  emergency       (urgency)
    2.7x  equity          (values)

📊 Interpretation:
   Decision driver: Outside funding (grants) > Local taxpayer concerns
   Urgency pattern: Frequent 'emergency' framing - reactive governance
```

---

## 🎯 Complete Workflow

### Run the Full Analysis

```bash
# 1. Scrape Tuscaloosa data
python main.py scrape \
  --state AL \
  --municipality "Tuscaloosa" \
  --url https://tuscaloosaal.suiteonemedia.com \
  --platform suiteonemedia \
  --max-events 0

# 2. Run complete political economy analysis
python examples/tuscaloosa_political_economy.py
```

### What You Get

**Output files:**
- `output/tuscaloosa_political_economy_analysis.json` - Structured data
- `output/TUSCALOOSA_GOVERNANCE_REPORT.md` - Human-readable report

**Analysis includes:**
1. Frame distribution (how issues are presented)
2. Budget-to-Minutes delta (rhetoric vs. reality)
3. Opportunity cost map (what wasn't funded)
4. Stakeholder influence analysis
5. Election cycle patterns
6. Keyword density (governance drivers)
7. **GOVERNANCE LOGIC SYNTHESIS** - The "why" narrative

---

## 📊 Budget Data Parsing

### Current Implementation

**YES**, the system can extract and parse budget information:

#### From Meeting Documents
```python
from extraction.budget_analyzer import BudgetAnalyzer

analyzer = BudgetAnalyzer()

# Extracts from budget PDFs or meeting notes
budget_items = analyzer.extract_budget_from_document(document)

# Each item includes:
# - Category, description
# - Current year amount
# - Prior year amount
# - Change amount & percent
# - Department, fund
```

#### Using AI (GPT-4o)
- ✅ Extracts structured budget data from unstructured text
- ✅ Handles various formats (PDFs, meeting minutes, budget docs)
- ✅ Identifies current year vs. prior year
- ✅ Calculates changes automatically

#### Fallback: Regex
- ✅ Pattern matching for "$XXX,XXX" amounts
- ✅ Works without AI for simple cases

---

## 🎓 Pedagogical vs. Operational Rationales

**You asked:** Are you more interested in pedagogical (how kids learn) or operational (buildings/buses)?

**Answer:** The system extracts BOTH, but you can focus analysis:

```python
# Focus on pedagogical decisions
decisions = analyzer.analyze_document(
    doc,
    focus_topics=["curriculum", "teaching", "learning", "instruction", "pedagogy"]
)

# Focus on operational decisions
decisions = analyzer.analyze_document(
    doc,
    focus_topics=["facilities", "transportation", "maintenance", "infrastructure"]
)
```

The system classifies based on the content, so you get:
- **Pedagogical**: "Adopted new reading curriculum", "Teacher training budget"
- **Operational**: "Bus replacement schedule", "HVAC system upgrade"

---

## 🚀 Next Steps

### 1. **Expand Budget Scraping**

Currently: Extracts budgets from meeting documents  
**Enhancement:** Scrape dedicated budget portals

```python
# TODO: Create budget-specific scraper
from agents.scraper import ScraperAgent

scraper = ScraperAgent()
budget_docs = scraper.scrape_budget_portal(
    "https://tuscaloosaal.gov/budget"
)
```

### 2. **Add More Jurisdictions**

Run the same analysis for:
- Tuscaloosa County Schools
- Montgomery
- Mobile
- Other Alabama districts

### 3. **Temporal Dashboard**

Create interactive visualization:
- Election cycle overlays
- Budget trend lines
- Frame evolution over time

### 4. **Comparative Analysis**

Compare Tuscaloosa to similar jurisdictions:
- Which frames similar issues differently?
- Who funds differently despite similar constraints?

---

## 📚 Methodology References

The frameworks implemented are based on:

1. **Framing Theory** (Goffman, Lakoff) - How language shapes perception
2. **Public Choice Theory** (Buchanan, Tullock) - Electoral incentives
3. **Fiscal Sociology** (Schumpeter) - Budgets reveal priorities
4. **Stakeholder Theory** (Freeman) - Who has power
5. **Temporal Analysis** (Political science tradition) - Timing matters

This is **serious political economy analysis**, not just data collection!

---

## ✅ Final Answer

**YES**, you are now doing all the things you described:

| Framework | Status |
|-----------|--------|
| 1. Frame Analysis | ✅ Fully Implemented |
| 2. Budget-to-Minutes Delta | ✅ Fully Implemented |
| 3. Trade-off Mapping | ✅ Fully Implemented |
| 4. Stakeholder Influence | ✅ Fully Implemented |
| 5. Temporal/Election Analysis | ✅ Fully Implemented |
| 6. Quantitative Indicators | ✅ Fully Implemented |
| 7. Budget Data Parsing | ✅ Fully Implemented |

You can now understand the **"WHY"** behind Tuscaloosa's decisions, not just the "what." This is political and economic forensics in action! 🔍
