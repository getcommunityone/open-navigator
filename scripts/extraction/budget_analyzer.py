"""
Budget Analysis Agent for extracting and correlating budget data with meeting decisions.

Implements the "Budget-to-Minutes Delta" framework:
- What was praised in meetings vs. what actually got funded
- Opportunity cost analysis
- Hidden priorities (quiet increases vs. loud discussion)
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from loguru import logger
import re

from openai import OpenAI
from config.settings import settings


@dataclass
class BudgetLineItem:
    """Structured budget line item."""
    category: str
    subcategory: Optional[str]
    description: str
    current_year_amount: float
    prior_year_amount: float
    change_amount: float
    change_percent: float
    department: str
    fund: str


@dataclass
class BudgetToMinutesDelta:
    """
    Analysis of the gap between rhetoric (meeting notes) and reality (budget).
    
    This is the political economy forensics framework.
    """
    line_item: BudgetLineItem
    
    # Meeting sentiment about this item
    meeting_mentions: int  # How many times discussed
    sentiment_keywords: List[str]  # "Priority", "Essential", "Critical"
    praise_level: str  # "High", "Medium", "Low", "None"
    
    # Budget reality
    funding_change: str  # "Expansion", "Stagnant", "Decreased"
    
    # The Delta
    delta_type: str  # "Expansion", "Lip Service", "Hidden Priority", "Aligned"
    delta_score: float  # -1 (rhetoric >> reality) to +1 (reality >> rhetoric)
    
    # Rationale analysis
    stated_rationale: str  # What they said in meeting
    inferred_rationale: str  # What the budget reveals
    underlying_logic: str  # "Genuine priority", "Performative", "Bureaucratic inertia"


class BudgetAnalyzer:
    """
    Extract and analyze budget data to reveal the "why" behind decisions.
    
    Implements frameworks:
    1. Budget-to-Minutes Delta
    2. Opportunity Cost Mapping
    3. Hidden Priority Detection
    """
    
    def __init__(self):
        """Initialize budget analyzer."""
        if settings.openai_api_key:
            self.client = OpenAI(api_key=settings.openai_api_key)
            self.model = "gpt-4o"
        else:
            logger.warning("No OpenAI key - budget extraction will be limited to regex")
            self.client = None
    
    def extract_budget_from_document(
        self,
        document: Dict[str, Any]
    ) -> List[BudgetLineItem]:
        """
        Extract budget line items from a meeting document or budget PDF.
        
        Args:
            document: Document containing budget data
            
        Returns:
            List of structured budget line items
        """
        content = document.get("content", "")
        
        # Try AI extraction first
        if self.client:
            return self._extract_budget_with_llm(content, document)
        else:
            return self._extract_budget_with_regex(content)
    
    def _extract_budget_with_llm(
        self,
        content: str,
        document: Dict[str, Any]
    ) -> List[BudgetLineItem]:
        """Use LLM to extract budget data from unstructured text."""
        
        prompt = f"""
Extract all budget line items from this government document.

Document: {document.get('title', 'Unknown')}
Content:
{content[:20000]}

Return a JSON object with this structure:

{{
  "line_items": [
    {{
      "category": "Education|Infrastructure|Public Safety|Health|etc",
      "subcategory": "Specific program/department",
      "description": "What this funding is for",
      "current_year_amount": 1000000,
      "prior_year_amount": 900000,
      "change_amount": 100000,
      "change_percent": 11.1,
      "department": "Department name",
      "fund": "General Fund|Special Revenue|etc"
    }}
  ]
}}

Only extract actual budget numbers - ignore general discussion.
If amounts are not specified, use null.
"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a budget analyst extracting structured financial data."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            import json
            parsed = json.loads(response.choices[0].message.content)
            
            return [
                BudgetLineItem(
                    category=item.get("category", "Unknown"),
                    subcategory=item.get("subcategory"),
                    description=item.get("description", ""),
                    current_year_amount=item.get("current_year_amount", 0) or 0,
                    prior_year_amount=item.get("prior_year_amount", 0) or 0,
                    change_amount=item.get("change_amount", 0) or 0,
                    change_percent=item.get("change_percent", 0) or 0,
                    department=item.get("department", ""),
                    fund=item.get("fund", "")
                )
                for item in parsed.get("line_items", [])
            ]
            
        except Exception as e:
            logger.error(f"LLM budget extraction failed: {e}")
            return self._extract_budget_with_regex(content)
    
    def _extract_budget_with_regex(self, content: str) -> List[BudgetLineItem]:
        """Fallback: Extract budget data using regex patterns."""
        line_items = []
        
        # Pattern: "Department: $XXX,XXX"
        pattern = r'([A-Za-z\s]+):\s*\$?([\d,]+(?:\.\d{2})?)'
        matches = re.findall(pattern, content)
        
        for category, amount_str in matches:
            try:
                amount = float(amount_str.replace(',', ''))
                if amount > 1000:  # Filter noise
                    line_items.append(
                        BudgetLineItem(
                            category=category.strip(),
                            subcategory=None,
                            description=category.strip(),
                            current_year_amount=amount,
                            prior_year_amount=0,
                            change_amount=0,
                            change_percent=0,
                            department=category.strip(),
                            fund="Unknown"
                        )
                    )
            except:
                continue
        
        return line_items
    
    def calculate_budget_to_minutes_delta(
        self,
        budget_items: List[BudgetLineItem],
        meeting_documents: List[Dict[str, Any]]
    ) -> List[BudgetToMinutesDelta]:
        """
        Calculate the delta between meeting rhetoric and budget reality.
        
        This is the core political economy analysis.
        """
        deltas = []
        
        for budget_item in budget_items:
            # Analyze meeting mentions
            mentions = 0
            sentiment_keywords = []
            
            search_terms = [
                budget_item.category.lower(),
                budget_item.subcategory.lower() if budget_item.subcategory else "",
                budget_item.description.lower()
            ]
            
            for doc in meeting_documents:
                content = doc.get("content", "").lower()
                for term in search_terms:
                    if term and term in content:
                        mentions += content.count(term)
                        
                        # Extract sentiment keywords nearby
                        for keyword in ["priority", "essential", "critical", "important", 
                                      "necessary", "urgent", "fundamental"]:
                            if keyword in content:
                                sentiment_keywords.append(keyword)
            
            # Determine praise level
            if mentions > 10 or len(sentiment_keywords) > 5:
                praise_level = "High"
            elif mentions > 3 or len(sentiment_keywords) > 2:
                praise_level = "Medium"
            elif mentions > 0:
                praise_level = "Low"
            else:
                praise_level = "None"
            
            # Determine funding change
            if budget_item.change_percent > 5:
                funding_change = "Expansion"
            elif budget_item.change_percent < -5:
                funding_change = "Decreased"
            else:
                funding_change = "Stagnant"
            
            # Calculate delta type
            delta_type, underlying_logic = self._classify_delta(
                praise_level, funding_change, mentions
            )
            
            # Calculate delta score
            praise_score = {"High": 1.0, "Medium": 0.5, "Low": 0.25, "None": 0}[praise_level]
            funding_score = {"Expansion": 1.0, "Stagnant": 0, "Decreased": -1.0}[funding_change]
            delta_score = funding_score - praise_score
            
            delta = BudgetToMinutesDelta(
                line_item=budget_item,
                meeting_mentions=mentions,
                sentiment_keywords=list(set(sentiment_keywords)),
                praise_level=praise_level,
                funding_change=funding_change,
                delta_type=delta_type,
                delta_score=delta_score,
                stated_rationale=self._extract_stated_rationale(
                    budget_item, meeting_documents
                ),
                inferred_rationale=self._infer_rationale(
                    delta_type, funding_change, mentions
                ),
                underlying_logic=underlying_logic
            )
            
            deltas.append(delta)
        
        return deltas
    
    def _classify_delta(
        self,
        praise_level: str,
        funding_change: str,
        mentions: int
    ) -> tuple[str, str]:
        """
        Classify the type of delta and underlying governance logic.
        
        Returns: (delta_type, underlying_logic)
        """
        if praise_level == "High" and funding_change == "Expansion":
            return ("Expansion", "Genuine political priority")
        
        elif praise_level in ["High", "Medium"] and funding_change in ["Stagnant", "Decreased"]:
            return ("Lip Service", "Performative politics - low actual priority")
        
        elif praise_level in ["None", "Low"] and funding_change == "Expansion":
            return ("Hidden Priority", "Bureaucratic inertia or avoiding public scrutiny")
        
        else:
            return ("Aligned", "Rhetoric matches resource allocation")
    
    def _extract_stated_rationale(
        self,
        budget_item: BudgetLineItem,
        meeting_documents: List[Dict[str, Any]]
    ) -> str:
        """Extract what was said about this budget item in meetings."""
        search_term = budget_item.category.lower()
        
        for doc in meeting_documents:
            content = doc.get("content", "")
            if search_term in content.lower():
                # Extract sentence containing the term
                sentences = content.split('.')
                for sentence in sentences:
                    if search_term in sentence.lower():
                        return sentence.strip()[:200]
        
        return "Not explicitly discussed in available meeting notes"
    
    def _infer_rationale(
        self,
        delta_type: str,
        funding_change: str,
        mentions: int
    ) -> str:
        """Infer the real rationale based on the delta pattern."""
        rationales = {
            "Expansion": "Budget follows stated priorities - alignment between rhetoric and resources",
            "Lip Service": "Rhetoric serves political optics, but actual funding priorities lie elsewhere",
            "Hidden Priority": "Quiet bureaucratic decision-making; may indicate staff recommendations or grant requirements",
            "Aligned": "Standard operational funding with appropriate level of discussion"
        }
        
        return rationales.get(delta_type, "Unclear rationale")
    
    def generate_opportunity_cost_map(
        self,
        budget_items: List[BudgetLineItem],
        decisions: List[Any]  # PolicyDecision objects
    ) -> Dict[str, Any]:
        """
        Map what was NOT funded (opportunity costs).
        
        Analyzes:
        - Options discussed but rejected
        - Budget items that decreased
        - Trade-offs made explicit in meetings
        """
        opportunity_costs = []
        
        # Find decreases
        for item in budget_items:
            if item.change_amount < 0:
                opportunity_costs.append({
                    "category": item.category,
                    "amount_lost": abs(item.change_amount),
                    "could_have_funded": f"Lost ${abs(item.change_amount):,.0f} in {item.category}",
                    "type": "budget_cut"
                })
        
        # Find rejected options from decisions
        for decision in decisions:
            for rejected in decision.rejected_options:
                opportunity_costs.append({
                    "option": rejected.get("option", ""),
                    "reason_rejected": rejected.get("reason_rejected", ""),
                    "type": "rejected_alternative"
                })
        
        return {
            "total_opportunity_costs": len(opportunity_costs),
            "total_dollars_lost": sum(oc.get("amount_lost", 0) for oc in opportunity_costs),
            "costs": opportunity_costs
        }
