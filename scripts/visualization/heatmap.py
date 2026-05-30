"""
Advocacy Heatmap Visualization for displaying policy activity geographically.

Creates interactive maps showing:
- Where oral health policies are being debated
- Urgency levels by location
- Topic concentration by region
- Timeline of policy discussions
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import folium
from folium import plugins
import plotly.graph_objects as go
import plotly.express as px
from loguru import logger


class AdvocacyHeatmap:
    """
    Generate interactive heatmaps showing advocacy opportunities.
    
    Features:
    - Geographic heatmap of policy activity
    - Topic-based filtering
    - Urgency color coding
    - Clickable markers with details
    - Timeline animation
    """
    
    def __init__(self):
        """Initialize the heatmap generator."""
        self.us_center = (39.8283, -98.5795)  # Geographic center of US
        
        # Color coding by urgency
        self.urgency_colors = {
            "critical": "#d32f2f",  # Red
            "high": "#f57c00",      # Orange
            "medium": "#fbc02d",    # Yellow
            "low": "#689f38",       # Green
            "none": "#1976d2"       # Blue
        }
        
        # US state coordinates (simplified - would use geocoding in production)
        self.state_coords = self._load_state_coordinates()
    
    def _load_state_coordinates(self) -> Dict[str, Tuple[float, float]]:
        """Load approximate state center coordinates."""
        return {
            "AL": (32.806671, -86.791130),
            "AK": (61.370716, -152.404419),
            "AZ": (33.729759, -111.431221),
            "AR": (34.969704, -92.373123),
            "CA": (36.116203, -119.681564),
            "CO": (39.059811, -105.311104),
            "CT": (41.597782, -72.755371),
            "DE": (39.318523, -75.507141),
            "FL": (27.766279, -81.686783),
            "GA": (33.040619, -83.643074),
            "HI": (21.094318, -157.498337),
            "ID": (44.240459, -114.478828),
            "IL": (40.349457, -88.986137),
            "IN": (39.849426, -86.258278),
            "IA": (42.011539, -93.210526),
            "KS": (38.526600, -96.726486),
            "KY": (37.668140, -84.670067),
            "LA": (31.169546, -91.867805),
            "ME": (44.693947, -69.381927),
            "MD": (39.063946, -76.802101),
            "MA": (42.230171, -71.530106),
            "MI": (43.326618, -84.536095),
            "MN": (45.694454, -93.900192),
            "MS": (32.741646, -89.678696),
            "MO": (38.456085, -92.288368),
            "MT": (46.921925, -110.454353),
            "NE": (41.125370, -98.268082),
            "NV": (38.313515, -117.055374),
            "NH": (43.452492, -71.563896),
            "NJ": (40.298904, -74.521011),
            "NM": (34.840515, -106.248482),
            "NY": (42.165726, -74.948051),
            "NC": (35.630066, -79.806419),
            "ND": (47.528912, -99.784012),
            "OH": (40.388783, -82.764915),
            "OK": (35.565342, -96.928917),
            "OR": (44.572021, -122.070938),
            "PA": (40.590752, -77.209755),
            "RI": (41.680893, -71.511780),
            "SC": (33.856892, -80.945007),
            "SD": (44.299782, -99.438828),
            "TN": (35.747845, -86.692345),
            "TX": (31.054487, -97.563461),
            "UT": (40.150032, -111.862434),
            "VT": (44.045876, -72.710686),
            "VA": (37.769337, -78.169968),
            "WA": (47.400902, -121.490494),
            "WV": (38.491226, -80.954453),
            "WI": (44.268543, -89.616508),
            "WY": (42.755966, -107.302490)
        }
    
    def create_folium_map(
        self,
        opportunities: List[Dict[str, Any]],
        title: str = "Oral Health Policy Advocacy Heatmap"
    ) -> folium.Map:
        """
        Create an interactive Folium map with advocacy opportunities.
        
        Args:
            opportunities: List of advocacy opportunities
            title: Map title
            
        Returns:
            Folium map object
        """
        # Create base map
        m = folium.Map(
            location=self.us_center,
            zoom_start=4,
            tiles='OpenStreetMap'
        )
        
        # Add title
        title_html = f'''
            <div style="position: fixed; 
                        top: 10px; left: 50px; width: 500px; height: 50px; 
                        background-color: white; border:2px solid grey; z-index:9999; 
                        font-size:16px; font-weight: bold; padding: 10px">
                {title}
            </div>
        '''
        m.get_root().html.add_child(folium.Element(title_html))
        
        # Group markers by urgency
        urgency_groups = {
            "critical": folium.FeatureGroup(name="Critical Urgency"),
            "high": folium.FeatureGroup(name="High Urgency"),
            "medium": folium.FeatureGroup(name="Medium Urgency"),
            "low": folium.FeatureGroup(name="Low Urgency")
        }
        
        # Add markers for each opportunity
        for opp in opportunities:
            state = opp.get("state")
            coords = self.state_coords.get(state)
            
            if not coords:
                continue
            
            # Create popup content
            popup_html = self._create_popup_html(opp)
            
            urgency = opp.get("urgency", "medium")
            color = self.urgency_colors.get(urgency, "#1976d2")
            
            # Create marker
            marker = folium.CircleMarker(
                location=coords,
                radius=10,
                popup=folium.Popup(popup_html, max_width=400),
                color=color,
                fill=True,
                fillColor=color,
                fillOpacity=0.7,
                weight=2
            )
            
            # Add to appropriate group
            if urgency in urgency_groups:
                marker.add_to(urgency_groups[urgency])
        
        # Add all groups to map
        for group in urgency_groups.values():
            group.add_to(m)
        
        # Add layer control
        folium.LayerControl().add_to(m)
        
        # Add legend
        self._add_legend(m)
        
        return m
    
    def _create_popup_html(self, opportunity: Dict[str, Any]) -> str:
        """Create HTML content for marker popup."""
        html = f"""
        <div style="font-family: Arial, sans-serif; width: 350px;">
            <h4 style="margin: 0 0 10px 0; color: #1976d2;">
                {opportunity.get('municipality', 'Unknown')}, {opportunity.get('state', 'Unknown')}
            </h4>
            
            <p style="margin: 5px 0;">
                <strong>Topic:</strong> {self._format_topic(opportunity.get('topic'))}
            </p>
            
            <p style="margin: 5px 0;">
                <strong>Meeting Date:</strong> {opportunity.get('meeting_date', 'Unknown')}
            </p>
            
            <p style="margin: 5px 0;">
                <strong>Stance:</strong> {opportunity.get('stance', 'Unknown')}
            </p>
            
            <p style="margin: 5px 0;">
                <strong>Urgency:</strong> 
                <span style="color: {self.urgency_colors.get(opportunity.get('urgency', 'medium'))}; font-weight: bold;">
                    {opportunity.get('urgency', 'Unknown').upper()}
                </span>
            </p>
            
            <p style="margin: 10px 0 5px 0; font-style: italic;">
                {opportunity.get('recommended_action', '')}
            </p>
            
            <p style="margin: 10px 0 0 0;">
                <a href="{opportunity.get('source_url', '#')}" target="_blank">View Source</a>
            </p>
        </div>
        """
        return html
    
    def _add_legend(self, m: folium.Map):
        """Add legend to the map."""
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 50px; left: 50px; width: 200px; height: 180px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px">
            <p style="margin: 0 0 10px 0; font-weight: bold;">Urgency Levels</p>
            <p style="margin: 5px 0;">
                <span style="color: #d32f2f;">●</span> Critical
            </p>
            <p style="margin: 5px 0;">
                <span style="color: #f57c00;">●</span> High
            </p>
            <p style="margin: 5px 0;">
                <span style="color: #fbc02d;">●</span> Medium
            </p>
            <p style="margin: 5px 0;">
                <span style="color: #689f38;">●</span> Low
            </p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
    
    def create_plotly_choropleth(
        self,
        aggregated_data: pd.DataFrame
    ) -> go.Figure:
        """
        Create a Plotly choropleth map showing opportunity density by state.
        
        Args:
            aggregated_data: DataFrame with state-level aggregates
            
        Returns:
            Plotly figure
        """
        fig = go.Figure(data=go.Choropleth(
            locations=aggregated_data['state'],
            z=aggregated_data['urgent_opportunities'],
            locationmode='USA-states',
            colorscale='Reds',
            colorbar_title="Urgent<br>Opportunities",
            hovertemplate=(
                '<b>%{location}</b><br>' +
                'Urgent Opportunities: %{z}<br>' +
                '<extra></extra>'
            )
        ))
        
        fig.update_layout(
            title_text='Advocacy Opportunities by State',
            geo_scope='usa',
            height=600
        )
        
        return fig
    
    def create_topic_distribution_chart(
        self,
        opportunities: List[Dict[str, Any]]
    ) -> go.Figure:
        """
        Create a chart showing distribution of topics.
        
        Args:
            opportunities: List of opportunities
            
        Returns:
            Plotly figure
        """
        # Count topics
        topic_counts = {}
        for opp in opportunities:
            topic = self._format_topic(opp.get('topic'))
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
        
        # Create bar chart
        fig = go.Figure(data=[
            go.Bar(
                x=list(topic_counts.keys()),
                y=list(topic_counts.values()),
                marker_color='#1976d2'
            )
        ])
        
        fig.update_layout(
            title='Oral Health Policy Topics in Discussion',
            xaxis_title='Policy Topic',
            yaxis_title='Number of Opportunities',
            height=400
        )
        
        return fig
    
    def create_timeline_chart(
        self,
        opportunities: List[Dict[str, Any]]
    ) -> go.Figure:
        """
        Create a timeline showing when opportunities emerge.
        
        Args:
            opportunities: List of opportunities
            
        Returns:
            Plotly figure
        """
        # Convert to DataFrame
        df = pd.DataFrame(opportunities)
        
        if 'meeting_date' not in df.columns:
            return go.Figure()
        
        # Convert dates
        df['meeting_date'] = pd.to_datetime(df['meeting_date'])
        
        # Group by date and urgency
        timeline = df.groupby([df['meeting_date'].dt.date, 'urgency']).size().reset_index(name='count')
        
        # Create line chart
        fig = px.line(
            timeline,
            x='meeting_date',
            y='count',
            color='urgency',
            title='Advocacy Opportunities Timeline',
            labels={
                'meeting_date': 'Meeting Date',
                'count': 'Number of Opportunities',
                'urgency': 'Urgency Level'
            },
            color_discrete_map=self.urgency_colors
        )
        
        fig.update_layout(height=400)
        
        return fig
    
    def create_dashboard(
        self,
        opportunities: List[Dict[str, Any]],
        aggregated_data: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        Create a complete dashboard with multiple visualizations.
        
        Args:
            opportunities: List of opportunities
            aggregated_data: Optional pre-aggregated state data
            
        Returns:
            Dictionary containing all visualizations
        """
        dashboard = {
            "interactive_map": self.create_folium_map(opportunities),
            "topic_distribution": self.create_topic_distribution_chart(opportunities),
            "timeline": self.create_timeline_chart(opportunities),
        }
        
        if aggregated_data is not None:
            dashboard["choropleth"] = self.create_plotly_choropleth(aggregated_data)
        
        # Summary statistics
        dashboard["statistics"] = self._calculate_statistics(opportunities)
        
        return dashboard
    
    def _calculate_statistics(
        self,
        opportunities: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate summary statistics."""
        df = pd.DataFrame(opportunities)
        
        stats = {
            "total_opportunities": len(opportunities),
            "critical_count": len(df[df['urgency'] == 'critical']) if 'urgency' in df.columns else 0,
            "high_count": len(df[df['urgency'] == 'high']) if 'urgency' in df.columns else 0,
            "states_affected": df['state'].nunique() if 'state' in df.columns else 0,
            "municipalities_affected": df['municipality'].nunique() if 'municipality' in df.columns else 0,
            "topics": df['topic'].value_counts().to_dict() if 'topic' in df.columns else {}
        }
        
        return stats
    
    def _format_topic(self, topic: str) -> str:
        """Format topic string for display."""
        if not topic:
            return "Unknown"
        
        return topic.replace('_', ' ').title()
    
    def export_map_html(
        self,
        m: folium.Map,
        output_path: str
    ):
        """Export Folium map to HTML file."""
        m.save(output_path)
        logger.info(f"Exported map to {output_path}")
