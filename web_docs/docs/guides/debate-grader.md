---
title: Debate Grader Guide
---

# Debate Grader Feature

The **Debate Grader** evaluates government decisions using a debate framework, making complex policy analysis accessible to laypeople and advocates.

## Overview

The debate grader analyzes decisions across three dimensions:

1. **Harms (The Problem)**: "Why is this a crisis in our community?"
2. **Solvency (The Fix)**: "How does this solution actually work?"
3. **Topicality (The Scope)**: "Does the government have authority to do this?"

Each dimension is scored 0-5 and graded as:
- **Excellent** (4-5/5)
- **Good** (3-4/5)
- **Fair** (2-3/5)
- **Weak** (1-2/5)
- **Missing** (0-1/5)

## Architecture

### Backend Agent

The `DebateGraderAgent` is located at `/agents/debate_grader.py` and implements:

```python
from agents.debate_grader import DebateGraderAgent

grader = DebateGraderAgent()
grade = await grader._grade_document(document)
```

**Evaluation Criteria:**

#### Harms (Problem Identification)
- Problem identification keywords (0-2 points)
- Data/evidence citations (0-2 points)
- Affected population (0-1 point)

#### Solvency (Solution Effectiveness)
- Solution clarity (0-1 point)
- Implementation mechanism (0-2 points)
- Evidence of effectiveness (0-1 point)
- Implementation plan (0-1 point)

#### Topicality (Jurisdictional Authority)
- Legal authority cited (0-2 points)
- Precedent referenced (0-2 points)
- Scope appropriateness (0-1 point)

### API Endpoints

#### Single Document Grading

```bash
POST /api/debate-grade?text=<document_text>&title=<optional_title>
```

**Example:**
```bash
curl -X POST "http://localhost:8000/api/debate-grade?text=The%20city%20council%20approved%20funding..." \
  -H "Content-Type: application/json"
```

**Response:**
```json
{
  "document_id": "custom_text",
  "title": "",
  "debate_grade": {
    "dimensions": {
      "harms": {
        "score": 3,
        "grade": "good",
        "explanation": "Strong problem identification; Some evidence mentioned",
        "layperson_label": "The Problem",
        "layperson_question": "Why is this a crisis in our community?"
      },
      "solvency": {
        "score": 4,
        "grade": "good",
        "explanation": "Clear solution proposed; Implementation mechanism described",
        "layperson_label": "The Fix",
        "layperson_question": "How does this solution actually work?"
      },
      "topicality": {
        "score": 2,
        "grade": "fair",
        "explanation": "Authority mentioned; Some precedent referenced",
        "layperson_label": "The Scope",
        "layperson_question": "Does the government have authority to do this?"
      }
    },
    "overall": {
      "score": 3.2,
      "grade": "good",
      "summary": "Strong problem identification; clear solution; questionable scope"
    }
  }
}
```

#### Batch Grading

```bash
POST /api/debate-grade/batch?state=AL&limit=50
```

**Response includes aggregate insights:**
```json
{
  "graded_count": 50,
  "documents": [...],
  "insights": {
    "total_documents": 50,
    "average_scores": {
      "harms": 3.2,
      "solvency": 2.8,
      "topicality": 2.1,
      "overall": 2.8
    },
    "strongest_dimension": "harms",
    "weakest_dimension": "topicality"
  }
}
```

### Frontend Component

The Debate Grader page is available at `/debate-grader` in the React app.

**Features:**
- Text input for decision content
- Real-time grading
- Visual grade display with color coding
- Detailed explanation for each dimension
- Educational content about the framework

**Usage:**
1. Navigate to Debate Grader from the sidebar
2. Enter decision text (e.g., from meeting minutes)
3. Click "Grade This Decision"
4. Review scores and explanations

## Integration Examples

### For Dashboard Users

Add debate grades to document cards:

```tsx
import { CheckCircleIcon, XCircleIcon } from '@heroicons/react/24/outline'

function DocumentCard({ document }) {
  const grade = document.debate_grade?.overall?.grade
  
  return (
    <div className="card">
      <h3>{document.title}</h3>
      
      {grade && (
        <div className="flex items-center gap-2 mt-2">
          {grade === 'excellent' || grade === 'good' ? 
            <CheckCircleIcon className="h-5 w-5 text-green-600" /> :
            <XCircleIcon className="h-5 w-5 text-red-600" />
          }
          <span>Debate Grade: {grade.toUpperCase()}</span>
        </div>
      )}
    </div>
  )
}
```

### For Data Analysis

Query documents by debate quality:

```python
# Get documents with excellent problem identification
documents = pipeline.query_documents()
excellent_harms = [
    doc for doc in documents
    if doc.get('debate_grade', {}).get('dimensions', {}).get('harms', {}).get('grade') == 'excellent'
]

# Find weak solutions
weak_fixes = [
    doc for doc in documents
    if doc.get('debate_grade', {}).get('dimensions', {}).get('solvency', {}).get('grade') in ['weak', 'missing']
]
```

### For Advocates

**Use Case: Identify policy gaps**

1. **Weak Harms** → Government hasn't documented the problem well
   - *Action*: Collect your own data, present evidence at next meeting
   
2. **Weak Solvency** → Proposed solution is unclear
   - *Action*: Find working examples from other cities, propose specific implementation
   
3. **Weak Topicality** → Unclear if they have authority
   - *Action*: Research legal precedents, cite other jurisdictions

## Customization

### Modify Evaluation Criteria

Edit `/agents/debate_grader.py` to adjust weights or add new indicators:

```python
def _calculate_overall_score(self, harms, solvency, topicality):
    # Current: Harms 40%, Solvency 40%, Topicality 20%
    # Adjust weights as needed:
    harms_weight = 0.4
    solvency_weight = 0.4
    topicality_weight = 0.2
    
    overall = (
        (harms["score"] / harms["max_score"] * 5 * harms_weight) +
        (solvency["score"] / solvency["max_score"] * 5 * solvency_weight) +
        (topicality["score"] / topicality["max_score"] * 5 * topicality_weight)
    )
    return round(overall, 2)
```

### Add New Keywords

```python
def _initialize_criteria(self):
    # Add domain-specific keywords
    self.harms_indicators["dental_specific"] = [
        "tooth decay", "oral health crisis", "dental emergency",
        "children without dental care", "preventable cavities"
    ]
```

## Roadmap

### Future Enhancements

1. **LLM-Based Grading**: Use GPT-4 for more nuanced analysis
2. **Comparative Analysis**: Compare decisions across jurisdictions
3. **Trend Analysis**: Track grade improvements over time
4. **Auto-Alerts**: Notify when weak decisions are proposed
5. **Advocacy Templates**: Generate counter-proposals for weak solutions

## Technical Details

### Agent Integration

The debate grader integrates into the existing agent pipeline:

```
Documents → Classifier → Sentiment Analyzer → Debate Grader → Advocacy Writer
```

To add debate grading to your pipeline:

```python
from agents.debate_grader import DebateGraderAgent
from agents.base import AgentMessage, MessageType, AgentRole

# Initialize
grader = DebateGraderAgent()

# Create message
message = AgentMessage(
    message_id="grade_001",
    sender=AgentRole.ORCHESTRATOR,
    recipient=AgentRole.DEBATE_GRADER,
    message_type=MessageType.COMMAND,
    payload={"documents": documents}
)

# Process
result = await grader.process(message)
graded_documents = result[0].payload.get("documents", [])
```

### Database Schema

Debate grades can be stored in Delta Lake:

```sql
CREATE TABLE IF NOT EXISTS debate_grades (
    document_id STRING,
    harms_score INT,
    harms_grade STRING,
    solvency_score INT,
    solvency_grade STRING,
    topicality_score INT,
    topicality_grade STRING,
    overall_score DECIMAL(3,2),
    overall_grade STRING,
    timestamp TIMESTAMP
);
```

## Support

For questions or issues:
- Check API docs: http://localhost:8000/docs
- Review agent code: `/agents/debate_grader.py`
- Frontend component: `/frontend/src/pages/DebateGrader.tsx`
