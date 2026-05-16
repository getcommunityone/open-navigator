---
sidebar_position: 5
---

# AI Policy Analysis

AI-powered analysis to understand **WHY** policy decisions were made, not just **WHAT** happened.

## 🎯 Overview

The AI Policy Analysis system uses local LLMs (Llama 3) to extract:

- **Bill Summaries**: Concise, accessible summaries of complex legislation
- **Topics**: Automatic categorization (health, education, infrastructure, etc.)
- **Primary Rationale**: Why was this bill introduced?
- **Stakeholder Arguments**: Who supported/opposed and why?
- **Tradeoffs**: What competing interests were balanced?
- **Decision Factors**: What evidence actually swayed the outcome?
- **Compromises**: How did the bill evolve through amendments?
- **Outcome Reasoning**: Why did it pass or fail?

## � Quick Start

### 1. Install Ollama (Local LLM)

```bash
# Install Ollama
curl https://ollama.ai/install.sh | sh

# Pull Llama 3.3 model (choose one):
ollama pull llama3.3:70b  # Best quality (requires 48GB+ VRAM)
ollama pull llama3.3:8b   # Faster, lower memory (8GB VRAM)
ollama pull llama3.1:70b  # Alternative with 128K context window
```

### 2. Test the Analyzer

```bash
# Run test script
.venv/bin/python agents/test_policy_analyzer.py
```

This will:
1. Load a sample fluoride bill from Georgia
2. Run AI analysis using Llama 3.3
3. Display summary, topics, and policy reasoning

**Expected output:**
```
📋 SUMMARY:
   This bill allows communities to decide on water fluoridation through local referenda...

🏷️  TOPICS:
   Primary: health
   Specific: water_fluoridation, public_health, local_control, referendum

💡 PRIMARY RATIONALE:
   Allow communities to decide on water fluoridation via referendum

⚖️  TRADEOFFS:
   1. Public health benefits vs. individual choice
      Resolution: Local referenda balance both interests
```

### 3. Analyze Your Own Bills

```python
from agents.policy_reasoning_analyzer import PolicyReasoningAnalyzer

# Initialize with local Llama 3.3
analyzer = PolicyReasoningAnalyzer(model="llama3.3:70b", local=True)

# Analyze a bill
analysis = analyzer.analyze_bill(
    bill_id="ocd-bill/12345",
    bill_text="Full bill text here...",
    bill_abstract="Brief summary..."
)

print(f"Summary: {analysis.summary}")
print(f"Topics: {', '.join(analysis.topics)}")
print(f"Primary Rationale: {analysis.primary_rationale}")
```

## �📊 Current Status

### ✅ Implemented

- [x] AI analysis framework (`agents/policy_reasoning_analyzer.py`)
- [x] Local LLM integration (Llama 3.3)
- [x] Bill text and abstracts available (151,130 bills)
- [x] Bill versions data (3.3M versions with PDFs)
- [x] Structured output schema
### ⚡ Performance Status

**Two LLM Options Available:**

| Method | Status | Performance | Notes |
|--------|--------|-------------|-------|
| **Ollama llama3.2** | ✅ Working | ~2 min/bill | Subprocess call, slower but reliable |
| **HuggingFace Transformers** | ⏳ Pending Access | ~30 sec/bill | Intel GPU optimized, 4x faster |

**Current Recommendation:**
- Use **Ollama** for now (working but slower)
- **HuggingFace access pending** - will be significantly faster with Intel Arc GPU optimization
- Both use the same analysis pipeline (`scripts/enrichment_ai/batch_analyze_bills.py`)

**Usage:**
```bash
# Using Ollama (current, slower)
python scripts/enrichment_ai/batch_analyze_bills.py --state GA --topic fluoride --limit 10

# Using HuggingFace (once access granted, faster)
export HF_TOKEN=your_token_here
python scripts/enrichment_ai/batch_analyze_bills.py --state GA --topic fluoride --limit 10
```
### 🔨 In Progress

- [x] **Collect additional data sources**
  - [x] Legislative testimony export script (`scripts/datasources/openstates/export_testimony.py`)
  - [x] Committee reports export script (`scripts/datasources/openstates/export_committee_reports.py`)
  - [ ] Hearing transcripts export (similar to testimony)
  - [ ] Floor debate transcripts (if available)
- [x] **Bill Summarization**: Generates 2-3 sentence summaries and detailed paragraphs
- [x] **Topic Extraction**: Primary topic category + specific topics list
- [x] **Test Script**: `agents/test_policy_analyzer.py` demonstrates usage
- [ ] Database schema for storing AI analysis results
- [ ] Batch processing pipeline for bulk analysis
- [ ] Frontend UI for viewing analysis

### 📋 Planned

- [ ] Comparison view (compare reasoning across states/bills)
- [ ] Topic modeling and clustering
- [ ] Stakeholder network analysis
- [ ] Predictive modeling (what arguments work?)

## 🚀 Usage

### Analyze a Single Bill

```bash
python agents/policy_reasoning_analyzer.py \
  --bill-id ocd-bill/f6a789f9-d464-4f74-887a-ac01e6e927f1 \
  --local
```

### Analyze All Bills for a Topic

```bash
python agents/policy_reasoning_analyzer.py \
  --state GA \
  --topic fluoride \
  --local \
  --output analysis_results.json
```

### Batch Analysis

```python
from agents.policy_reasoning_analyzer import PolicyReasoningAnalyzer

analyzer = PolicyReasoningAnalyzer(local=True)

# Analyze all fluoride bills
bills = fetch_bills(topic='fluoride')
for bill in bills:
    analysis = analyzer.analyze_bill(
        bill_id=bill.id,
        bill_text=bill.abstract,
        bill_abstract=bill.abstract
    )
    save_analysis(analysis)
```

## 🧠 LLM Configuration

### Local LLM (Recommended)

Using **Llama 3.3 70B** for best quality reasoning:

```python
# Uses Ollama for local inference
analyzer = PolicyReasoningAnalyzer(
    model="llama3.3:70b",
    local=True
)
```

**Benefits:**
- Free (no API costs)
- Private (data stays local)
- Fast (with GPU)
- Better reasoning than earlier versions
- Improved structured output following

**Requirements:**
- GPU with 48GB+ VRAM (for 70B model)
- Or use quantized version (8-bit/4-bit) for lower memory

### Alternative Models

```python
# Llama 3.3 8B (faster, less accurate)
analyzer = PolicyReasoningAnalyzer(model="llama3.3:8b", local=True)

# Llama 3.1 70B (128K context window)
analyzer = PolicyReasoningAnalyzer(model="llama3.1:70b", local=True)

# Mistral Large (good balance)
analyzer = PolicyReasoningAnalyzer(model="mistral-large", local=True)

# DeepSeek Coder (good for legal text)
analyzer = PolicyReasoningAnalyzer(model="deepseek-coder:33b", local=True)
```

## 📚 Data Sources

### Currently Available

1. **Bill Text** (`bills_bills.parquet`)
   - 151,130 bills across all states
   - Abstracts (56% coverage)
   - Source URLs (100% coverage)

2. **Bill Versions** (`bills_versions.parquet`)
   - 3.3M versions with document links
   - Shows evolution through amendments

3. **Bill Actions** (`bills_bill_actions.parquet`)
   - Legislative action history
   - Committee assignments

### 🔨 TODO: Additional Data Needed

**High Priority:**

- [x] **Legislative Testimony**
  - Source: OpenStates database (`opencivicdata_eventagendaitem`, `opencivicdata_eventdocument`)
  - Tables: `opencivicdata_event`, `opencivicdata_eventparticipant`
  - ~500K testimony records available
  - **Script**: `scripts/datasources/openstates/export_testimony.py`
  - **Usage**: `python scripts/datasources/openstates/export_testimony.py --states GA,MA,WA`
  - **Output**: `data/gold/bills_testimony.parquet`

- [x] **Committee Reports**
  - Source: Bill documents with classification='committee-report'
  - Table: `opencivicdata_billdocument` + `opencivicdata_billdocumentlink`
  - **Script**: `scripts/datasources/openstates/export_committee_reports.py`
  - **Usage**: `python scripts/datasources/openstates/export_committee_reports.py`
  - **Output**: `data/gold/bills_committee_reports.parquet`

- [ ] **Hearing Transcripts**
  - Source: Event documents with note='hearing'
  - Table: `opencivicdata_eventdocument`
  - **Action**: Create export script similar to testimony export
  - **Output**: `data/gold/hearings.parquet`

**Medium Priority:**

- [ ] **Floor Debates**
  - Source: State legislature video/transcript APIs
  - Requires custom scrapers per state
  - **Action**: Research state-specific APIs

- [ ] **Fiscal Notes**
  - Source: Bill documents with classification='fiscal-note'
  - Shows cost-benefit analysis
  - **Action**: Export to `gold/bills_fiscal_notes.parquet`

- [ ] **Voting Records**
  - Source: OpenStates `opencivicdata_vote` table
  - Shows who voted how
  - **Action**: Already available, needs integration

## 🗄️ Database Schema

### Proposed Schema for Analysis Results

```sql
-- Store AI analysis results
CREATE TABLE bills_ai_analysis (
    bill_id TEXT PRIMARY KEY REFERENCES bills_bills(bill_id),
    
    -- Summaries
    summary TEXT,  -- 2-3 sentence summary
    detailed_summary TEXT,  -- 1-2 paragraph summary
    
    -- Topics (automatic categorization)
    primary_topic TEXT,  -- e.g., 'health', 'education'
    topics TEXT[],  -- e.g., ['fluoridation', 'public_health', 'local_control']
    
    -- Policy reasoning
    primary_rationale TEXT,
    problem_statement TEXT,
    
    -- Stakeholder analysis
    supporting_arguments JSONB,  -- [{stakeholder, argument, evidence, motivation}]
    opposing_arguments JSONB,
    
    -- Decision analysis
    tradeoffs_identified JSONB,  -- [{tradeoff, resolution, beneficiaries, losers}]
    key_decision_factors TEXT[],
    compromises_made TEXT[],
    
    -- Outcomes
    final_outcome TEXT,  -- 'passed', 'failed', 'pending'
    outcome_explanation TEXT,
    
    -- Meta
    confidence_score FLOAT,  -- AI confidence in analysis (0-1)
    data_sources TEXT[],  -- What was analyzed
    model_version TEXT,  -- LLM model used
    analyzed_at TIMESTAMP DEFAULT NOW(),
    
    -- Indexes
    INDEX idx_topic (primary_topic),
    INDEX idx_topics_gin (topics) USING gin
);

-- Store extracted topics for clustering
CREATE TABLE bills_topics (
    topic_id SERIAL PRIMARY KEY,
    topic_name TEXT UNIQUE,
    description TEXT,
    category TEXT,  -- 'health', 'education', etc.
    bill_count INTEGER DEFAULT 0
);

-- Many-to-many relationship
CREATE TABLE bills_topic_assignments (
    bill_id TEXT REFERENCES bills_bills(bill_id),
    topic_id INTEGER REFERENCES bills_topics(topic_id),
    relevance_score FLOAT,  -- How relevant is this topic (0-1)
    PRIMARY KEY (bill_id, topic_id)
);
```

## 🔍 Analysis Examples

### Example 1: Georgia Fluoride Bill

```json
{
  "bill_id": "ocd-bill/xxx",
  "summary": "Allows communities to decide on water fluoridation through local referenda rather than state mandate.",
  
  "topics": ["fluoridation", "public_health", "local_control", "referendum"],
  "primary_topic": "health",
  
  "primary_rationale": "Enable local control over public health decisions affecting community water systems",
  
  "tradeoffs_identified": [
    {
      "tradeoff": "Centralized public health policy vs. local democratic control",
      "resolution": "Allowed local referenda but maintained state equipment funding",
      "beneficiaries": "Anti-fluoride activists, local government autonomy advocates",
      "losers": "State health department's centralized authority"
    }
  ],
  
  "key_decision_factors": [
    "Growing constituent pressure (42% of emails opposed fluoridation)",
    "Similar bills passing in neighboring states (precedent)",
    "Compromise amendment securing moderate votes"
  ],
  
  "outcome_explanation": "Passed 32-24 due to effective coalition between local control advocates and anti-fluoride activists, with key compromise on maintaining state funding"
}
```

### Example 2: Cross-State Comparison

```bash
# Compare fluoride bills across states
python agents/policy_reasoning_analyzer.py \
  --compare \
  --topic fluoride \
  --states GA,MA,WA,AL
```

**Output:**
```
📊 Fluoride Bill Reasoning Comparison

Georgia (PASSED):
  - Key argument: Local control + individual choice
  - Winning coalition: Libertarians + health skeptics
  - Compromise: Maintained state funding for equipment

Massachusetts (FAILED):
  - Key argument: Public health mandate
  - Opposition: Strong dental/medical lobby
  - Failure point: No compromise on local control

Washington (PASSED):
  - Key argument: Cost savings for small communities
  - Winning coalition: Rural advocates + fiscal conservatives
  - Compromise: Grandfathered existing programs
```

## 🎨 Frontend Integration

### Bill Detail View

```tsx
// Add AI Analysis tab to bill details
{bill.ai_analysis && (
  <div className="mt-4 p-4 bg-blue-50 rounded-lg">
    <h4 className="font-semibold mb-2">🤖 AI Policy Analysis</h4>
    
    {/* Summary */}
    <div className="mb-3">
      <p className="text-sm">{bill.ai_analysis.summary}</p>
    </div>
    
    {/* Topics */}
    <div className="mb-3">
      <p className="text-xs text-gray-600">Topics:</p>
      <div className="flex gap-2 flex-wrap mt-1">
        {bill.ai_analysis.topics.map(topic => (
          <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded">
            {topic}
          </span>
        ))}
      </div>
    </div>
    
    {/* Reasoning */}
    <details>
      <summary className="cursor-pointer text-sm font-medium">
        Why This Bill Exists
      </summary>
      <p className="text-sm mt-2">{bill.ai_analysis.primary_rationale}</p>
    </details>
    
    {/* Tradeoffs */}
    <details className="mt-2">
      <summary className="cursor-pointer text-sm font-medium">
        Key Tradeoffs
      </summary>
      {bill.ai_analysis.tradeoffs.map(t => (
        <div className="text-sm mt-2 ml-2">
          <strong>{t.tradeoff}</strong>
          <p className="text-gray-600">{t.resolution}</p>
        </div>
      ))}
    </details>
  </div>
)}
```

## 🚦 Next Steps

### Phase 1: Data Collection ✅ (Scripts Ready)

1. **Export testimony from OpenStates**
   ```bash
   python scripts/datasources/openstates/export_testimony.py
   # Or for specific states:
   python scripts/datasources/openstates/export_testimony.py --states GA,MA,WA
   ```

2. **Export committee reports**
   ```bash
   python scripts/datasources/openstates/export_committee_reports.py
   # Or for specific states:
   python scripts/datasources/openstates/export_committee_reports.py --states GA,MA
   ```

3. **Export hearing transcripts** (TODO: Create script similar to testimony export)
   ```bash
   # Coming soon
   python scripts/datasources/openstates/export_hearings.py
   ```

### Phase 2: LLM Setup ✅ (Ready to Use)

1. Install Ollama and Llama 3.3:
   ```bash
   curl https://ollama.ai/install.sh | sh
   ollama pull llama3.3:70b  # or llama3.3:8b for faster/lower memory
   ```

2. Test analysis:
   ```bash
   python agents/policy_reasoning_analyzer.py --bill-id xxx --local
   ```

### Phase 3: Batch Processing

1. Create batch processing script
2. Analyze high-priority bills first (recent, high-impact)
3. Store results in database

### Phase 4: Frontend Integration

1. Add API endpoint for analysis results
2. Build analysis display components
3. Add comparison views

## 💡 Use Cases

### For Policy Advocates

**Understand what arguments work:**
- Compare successful vs. failed bills
- Identify effective coalitions
- Learn from other states

### For Researchers

**Analyze policy dynamics:**
- Map stakeholder networks
- Identify patterns in decision-making
- Study compromise strategies

### For Journalists

**Tell better stories:**
- Understand the "why" behind votes
- Identify key decision points
- Explain complex tradeoffs

### For Citizens

**Make informed decisions:**
- Understand bill impacts
- See who benefits/loses
- Follow the reasoning, not just outcomes

## 📖 References

- [OpenStates Data Schema](https://docs.openstates.org/en/latest/data/index.html)
- [Llama 3.3 Documentation](https://github.com/meta-llama/llama-models)
- [Ollama Setup Guide](https://ollama.ai)
