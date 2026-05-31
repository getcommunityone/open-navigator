"""
Legislative Tracking System

Download and track state legislation across multiple social issues,
categorizing bills by type (ban/restriction/protection) and status 
(introduced/enacted/failed).

Creates choropleth maps showing legislative activity by state.

Data Sources:
- Open States API (state legislation)
- Ballotpedia (ballot measures)
- LegiScan (additional tracking)

Usage:
    # Track fluoridation legislation
    python scripts/legislative_tracker.py --issue fluoridation --year 2024
    
    # Track multiple issues
    python scripts/legislative_tracker.py --issue abortion,marijuana,voting --year 2024
    
    # Generate map visualization
    python scripts/legislative_tracker.py --issue fluoridation --visualize
"""

import asyncio
import os
from typing import List, Dict, Optional
from datetime import datetime
import json
from pathlib import Path

import httpx
import pandas as pd
from loguru import logger
from dotenv import load_dotenv

# Visualization libraries
try:
    import plotly.graph_objects as go
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    logger.warning("Plotly not installed. Run: pip install plotly")

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("Matplotlib not installed. Run: pip install matplotlib")


load_dotenv()


class LegislativeTracker:
    """
    Track state legislation across multiple social issues.
    
    Categorizes bills by:
    - Type: Outright Ban, Restriction, Protection
    - Status: Introduced, Enacted, Failed
    
    Creates visualizations similar to legislative tracking maps.
    """
    
    def __init__(
        self,
        openstates_api_key: Optional[str] = None,
        cache_dir: str = "data/cache/legislation"
    ):
        self.api_key = openstates_api_key or os.getenv("OPENSTATES_API_KEY")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.base_url = "https://v3.openstates.org"
        
        # Issue-specific keywords for categorization
        self.issue_keywords = {
            "fluoridation": {
                "ban": ["prohibit fluoridation", "ban fluoride", "remove fluoride", "prohibit fluoride"],
                "restriction": ["limit fluoridation", "restrict fluoride", "opt-out fluoride", "fluoride disclosure"],
                "protection": ["require fluoridation", "mandate fluoride", "fluoride protection", "fluoride funding"]
            },
            "abortion": {
                "ban": ["ban abortion", "prohibit abortion", "criminalize abortion", "abortion ban"],
                "restriction": ["abortion restriction", "parental consent", "waiting period", "gestational limit"],
                "protection": ["abortion access", "protect abortion", "abortion rights", "reproductive freedom"]
            },
            "marijuana": {
                "ban": ["prohibit marijuana", "cannabis ban", "marijuana criminal"],
                "restriction": ["marijuana restriction", "cannabis regulation", "limited medical"],
                "protection": ["legalize marijuana", "cannabis legalization", "marijuana rights", "decriminalize"]
            },
            "voting": {
                "ban": ["voter id requirement", "restrict voting", "purge voter rolls"],
                "restriction": ["voting restriction", "ballot access", "registration deadline"],
                "protection": ["expand voting", "voter protection", "automatic registration", "early voting"]
            },
            "lgbtq": {
                "ban": ["ban transgender", "prohibit gender", "bathroom ban", "sports ban"],
                "restriction": ["transgender restriction", "gender therapy limit", "parental consent gender"],
                "protection": ["lgbtq protection", "transgender rights", "nondiscrimination", "gender identity protection"]
            },
            "education": {
                "ban": ["ban critical race theory", "prohibit teaching", "book ban"],
                "restriction": ["curriculum restriction", "parental rights education", "opt-out"],
                "protection": ["education funding", "school protection", "teacher rights"]
            }
        }
    
    async def search_bills(
        self,
        issue: str,
        year: Optional[int] = None,
        state: Optional[str] = None
    ) -> List[Dict]:
        """
        Search for bills related to specific issue.
        
        Args:
            issue: Issue keyword (e.g., 'fluoridation', 'abortion')
            year: Legislative session year (default: current year)
            state: State code (e.g., 'AL') or None for all states
            
        Returns:
            List of bill dictionaries
        """
        if not self.api_key:
            raise ValueError("OPENSTATES_API_KEY required. Get one at https://openstates.org/accounts/signup/")
        
        year = year or datetime.now().year
        search_query = issue
        
        logger.info(f"Searching Open States API for '{issue}' bills in {year}")
        
        params = {
            "q": search_query,
            "page": 1,
            "per_page": 100
        }
        
        if state:
            params["jurisdiction"] = state
        
        headers = {
            "X-API-Key": self.api_key
        }
        
        all_bills = []
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                try:
                    response = await client.get(
                        f"{self.base_url}/bills",
                        params=params,
                        headers=headers
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    bills = data.get("results", [])
                    all_bills.extend(bills)
                    
                    logger.info(f"  Fetched page {params['page']}: {len(bills)} bills")
                    
                    # Check if there are more pages
                    if not data.get("pagination", {}).get("next"):
                        break
                    
                    params["page"] += 1
                    
                    # Rate limiting
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"Error fetching bills: {e}")
                    break
        
        logger.info(f"✅ Total bills found: {len(all_bills)}")
        return all_bills
    
    def categorize_bill(self, bill: Dict, issue: str) -> Dict:
        """
        Categorize bill by type and status.
        
        Args:
            bill: Bill dictionary from Open States API
            issue: Issue keyword
            
        Returns:
            Dictionary with categorization
        """
        title = bill.get("title", "").lower()
        summary = bill.get("abstracts", [{}])[0].get("abstract", "").lower()
        text = f"{title} {summary}"
        
        # Determine bill type
        bill_type = "unknown"
        keywords = self.issue_keywords.get(issue, {})
        
        for keyword in keywords.get("ban", []):
            if keyword.lower() in text:
                bill_type = "ban"
                break
        
        if bill_type == "unknown":
            for keyword in keywords.get("restriction", []):
                if keyword.lower() in text:
                    bill_type = "restriction"
                    break
        
        if bill_type == "unknown":
            for keyword in keywords.get("protection", []):
                if keyword.lower() in text:
                    bill_type = "protection"
                    break
        
        # Determine status
        latest_action = bill.get("latest_action_description", "").lower()
        status = "introduced"
        
        if any(word in latest_action for word in ["signed", "enacted", "passed", "approved"]):
            status = "enacted"
        elif any(word in latest_action for word in ["failed", "defeated", "vetoed", "withdrawn"]):
            status = "failed"
        elif any(word in latest_action for word in ["introduced", "referred", "committee"]):
            status = "introduced"
        
        return {
            "bill_id": bill.get("identifier"),
            "state": bill.get("jurisdiction", {}).get("name"),
            "state_code": bill.get("jurisdiction", {}).get("id", "").replace("ocd-jurisdiction/country:us/state:", "").upper(),
            "title": bill.get("title"),
            "type": bill_type,
            "status": status,
            "url": bill.get("openstates_url"),
            "session": bill.get("session", {}).get("identifier"),
            "latest_action": bill.get("latest_action_description"),
            "latest_action_date": bill.get("latest_action_date"),
            "created_at": bill.get("created_at")
        }
    
    async def track_issue(
        self,
        issue: str,
        year: Optional[int] = None,
        states: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Track legislation for specific issue across all states.
        
        Args:
            issue: Issue keyword
            year: Year to track
            states: List of state codes (None = all states)
            
        Returns:
            DataFrame with categorized bills
        """
        logger.info(f"Tracking '{issue}' legislation for {year or 'current year'}")
        
        # Search all bills
        all_bills = await self.search_bills(issue, year)
        
        # Categorize each bill
        categorized = []
        for bill in all_bills:
            cat = self.categorize_bill(bill, issue)
            categorized.append(cat)
        
        df = pd.DataFrame(categorized)
        
        # Filter by states if specified
        if states:
            df = df[df['state_code'].isin(states)]
        
        # Save to cache
        cache_file = self.cache_dir / f"{issue}_{year or 'current'}.csv"
        df.to_csv(cache_file, index=False)
        logger.info(f"✅ Saved {len(df)} bills to {cache_file}")
        
        return df
    
    def generate_state_summary(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate state-level summary of legislation.
        
        Args:
            df: DataFrame with categorized bills
            
        Returns:
            DataFrame with one row per state
        """
        # Count bills by state, type, and status
        summary = df.groupby(['state_code', 'type', 'status']).size().reset_index(name='count')
        
        # Pivot to wide format
        state_summary = []
        
        for state in summary['state_code'].unique():
            state_data = summary[summary['state_code'] == state]
            
            # Determine dominant legislation type
            type_counts = state_data.groupby('type')['count'].sum()
            if len(type_counts) > 0:
                dominant_type = type_counts.idxmax()
            else:
                continue
            
            # Determine dominant status for that type
            type_status = state_data[state_data['type'] == dominant_type]
            status_counts = type_status.groupby('status')['count'].sum()
            dominant_status = status_counts.idxmax() if len(status_counts) > 0 else "introduced"
            
            state_summary.append({
                'state_code': state,
                'dominant_type': dominant_type,
                'dominant_status': dominant_status,
                'total_bills': state_data['count'].sum(),
                'ban_count': state_data[state_data['type'] == 'ban']['count'].sum() if 'ban' in state_data['type'].values else 0,
                'restriction_count': state_data[state_data['type'] == 'restriction']['count'].sum() if 'restriction' in state_data['type'].values else 0,
                'protection_count': state_data[state_data['type'] == 'protection']['count'].sum() if 'protection' in state_data['type'].values else 0,
            })
        
        return pd.DataFrame(state_summary)
    
    def create_choropleth_map(
        self,
        df: pd.DataFrame,
        issue: str,
        output_file: Optional[str] = None
    ):
        """
        Create choropleth map showing legislative activity by state.
        
        Similar to the fluoridation map visualization.
        
        Args:
            df: DataFrame with categorized bills
            issue: Issue name for title
            output_file: Path to save HTML file (default: data/visualizations/{issue}_map.html)
        """
        if not PLOTLY_AVAILABLE:
            logger.error("Plotly not installed. Run: pip install plotly")
            return
        
        # Generate state summary
        state_summary = self.generate_state_summary(df)
        
        # Define color scheme
        color_map = {
            ('ban', 'enacted'): '#D2691E',  # Brown (ban enacted - solid)
            ('ban', 'introduced'): '#FFA500',  # Orange (ban introduced - lighter)
            ('ban', 'failed'): '#FFE4B5',  # Moccasin (ban failed - lightest)
            ('restriction', 'enacted'): '#DAA520',  # Goldenrod (restriction enacted)
            ('restriction', 'introduced'): '#FFD700',  # Gold (restriction introduced)
            ('restriction', 'failed'): '#FFFFE0',  # Light yellow (restriction failed)
            ('protection', 'enacted'): '#00008B',  # Dark blue (protection enacted)
            ('protection', 'introduced'): '#4169E1',  # Royal blue (protection introduced)
            ('protection', 'failed'): '#87CEEB',  # Sky blue (protection failed)
            ('unknown', 'introduced'): '#D3D3D3',  # Light gray (unknown)
        }
        
        # Map state codes to colors
        state_summary['color'] = state_summary.apply(
            lambda row: color_map.get((row['dominant_type'], row['dominant_status']), '#FFFFFF'),
            axis=1
        )
        
        # Create hover text
        state_summary['hover_text'] = state_summary.apply(
            lambda row: f"<b>{row['state_code']}</b><br>" +
                       f"Type: {row['dominant_type'].title()}<br>" +
                       f"Status: {row['dominant_status'].title()}<br>" +
                       f"Total Bills: {row['total_bills']}<br>" +
                       f"Bans: {row['ban_count']}<br>" +
                       f"Restrictions: {row['restriction_count']}<br>" +
                       f"Protections: {row['protection_count']}",
            axis=1
        )
        
        # Create choropleth
        fig = go.Figure(data=go.Choropleth(
            locations=state_summary['state_code'],
            z=state_summary['total_bills'],  # Color intensity by bill count
            locationmode='USA-states',
            colorscale='Blues',
            marker_line_color='white',
            marker_line_width=0.5,
            text=state_summary['hover_text'],
            hoverinfo='text',
            showscale=True
        ))
        
        fig.update_layout(
            title_text=f'{issue.title()} Legislation Tracker',
            geo_scope='usa',
            height=600,
            width=1000
        )
        
        # Save to file
        output_file = output_file or f"data/visualizations/{issue}_map.html"
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        fig.write_html(output_file)
        
        logger.info(f"✅ Map saved to {output_file}")
        
        # Also save legend as separate image
        self._create_legend(issue)
        
        return fig
    
    def _create_legend(self, issue: str):
        """Create a separate legend image showing bill types and statuses."""
        if not MATPLOTLIB_AVAILABLE:
            return
        
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.axis('off')
        
        # Define patches for legend
        legend_elements = [
            mpatches.Patch(color='#D2691E', label='Outright Ban (Enacted)'),
            mpatches.Patch(color='#FFA500', label='Outright Ban (Introduced)'),
            mpatches.Patch(color='#FFE4B5', label='Outright Ban (Failed)'),
            mpatches.Patch(color='#DAA520', label='Restriction (Enacted)'),
            mpatches.Patch(color='#FFD700', label='Restriction (Introduced)'),
            mpatches.Patch(color='#FFFFE0', label='Restriction (Failed)'),
            mpatches.Patch(color='#00008B', label='Protection (Enacted)'),
            mpatches.Patch(color='#4169E1', label='Protection (Introduced)'),
            mpatches.Patch(color='#87CEEB', label='Protection (Failed)'),
        ]
        
        ax.legend(handles=legend_elements, loc='center', fontsize=12, title=f'{issue.title()} Legislation Types')
        
        output_file = f"data/visualizations/{issue}_legend.png"
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        logger.info(f"✅ Legend saved to {output_file}")
        plt.close()


async def main():
    """Main CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Track state legislation across social issues")
    parser.add_argument("--issue", required=True, help="Issue to track (e.g., 'fluoridation', 'abortion')")
    parser.add_argument("--year", type=int, help="Year to track (default: current year)")
    parser.add_argument("--visualize", action="store_true", help="Generate map visualization")
    parser.add_argument("--output", help="Output file path for visualization")
    
    args = parser.parse_args()
    
    tracker = LegislativeTracker()
    
    # Track legislation
    df = await tracker.track_issue(args.issue, args.year)
    
    logger.info(f"\n📊 Summary for {args.issue}:")
    logger.info(f"  Total bills: {len(df)}")
    logger.info(f"  Bans: {len(df[df['type'] == 'ban'])}")
    logger.info(f"  Restrictions: {len(df[df['type'] == 'restriction'])}")
    logger.info(f"  Protections: {len(df[df['type'] == 'protection'])}")
    logger.info(f"  Enacted: {len(df[df['status'] == 'enacted'])}")
    logger.info(f"  Failed: {len(df[df['status'] == 'failed'])}")
    
    # Generate visualization
    if args.visualize:
        tracker.create_choropleth_map(df, args.issue, args.output)


if __name__ == "__main__":
    asyncio.run(main())
