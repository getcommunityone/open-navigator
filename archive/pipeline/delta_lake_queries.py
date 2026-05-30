"""
Additional helper methods for DeltaLakePipeline to support web app.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta


async def get_dashboard_stats(self) -> Dict[str, Any]:
    """Get statistics for dashboard."""
    # Count total documents
    total_docs = self.spark.sql(f"""
        SELECT COUNT(*) as count
        FROM {self.catalog}.{self.schema}.raw_documents
    """).collect()[0]['count']
    
    # Count opportunities
    total_opps = self.spark.sql(f"""
        SELECT COUNT(*) as count
        FROM {self.catalog}.{self.schema}.advocacy_opportunities
        WHERE urgency IN ('critical', 'high')
    """).collect()[0]['count']
    
    # Count unique states
    states = self.spark.sql(f"""
        SELECT COUNT(DISTINCT state) as count
        FROM {self.catalog}.{self.schema}.raw_documents
    """).collect()[0]['count']
    
    # Topic distribution
    topics = self.spark.sql(f"""
        SELECT topic, COUNT(*) as count
        FROM {self.catalog}.{self.schema}.classified_documents
        GROUP BY topic
        ORDER BY count DESC
    """).collect()
    
    topic_dict = {row['topic']: row['count'] for row in topics}
    
    # Recent opportunities
    recent = self.spark.sql(f"""
        SELECT state, municipality, topic, urgency, meeting_date
        FROM {self.catalog}.{self.schema}.advocacy_opportunities
        ORDER BY meeting_date DESC
        LIMIT 10
    """).collect()
    
    recent_opps = [
        {
            "state": row['state'],
            "municipality": row['municipality'],
            "topic": row['topic'],
            "urgency": row['urgency'],
            "date": row['meeting_date'].isoformat() if row['meeting_date'] else None
        }
        for row in recent
    ]
    
    return {
        "total_documents": total_docs,
        "total_opportunities": total_opps,
        "states_monitored": states,
        "topics": topic_dict,
        "recent_opportunities": recent_opps
    }


async def query_opportunities(
    self,
    state: Optional[str] = None,
    topic: Optional[str] = None,
    urgency: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Query advocacy opportunities with filters."""
    conditions = []
    if state:
        conditions.append(f"state = '{state}'")
    if topic:
        conditions.append(f"topic = '{topic}'")
    if urgency:
        conditions.append(f"urgency = '{urgency}'")
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    query = f"""
        SELECT
            opportunity_id as id,
            state,
            municipality,
            topic,
            urgency,
            confidence,
            meeting_date,
            next_meeting,
            latitude,
            longitude,
            talking_points,
            contact_info
        FROM {self.catalog}.{self.schema}.advocacy_opportunities
        WHERE {where_clause}
        ORDER BY meeting_date DESC
        LIMIT {limit}
    """
    
    results = self.spark.sql(query).collect()
    
    return [
        {
            "id": row['id'],
            "state": row['state'],
            "municipality": row['municipality'],
            "topic": row['topic'],
            "urgency": row['urgency'],
            "confidence": float(row['confidence']),
            "meeting_date": row['meeting_date'].isoformat() if row['meeting_date'] else None,
            "next_meeting": row['next_meeting'].isoformat() if row['next_meeting'] else None,
            "latitude": float(row['latitude']) if row['latitude'] else None,
            "longitude": float(row['longitude']) if row['longitude'] else None,
            "talking_points": row['talking_points'] or [],
            "contact_info": row['contact_info'] or {}
        }
        for row in results
    ]


async def query_documents(
    self,
    search: Optional[str] = None,
    limit: int = 20,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Query analyzed documents with optional search."""
    where_clause = "1=1"
    if search:
        where_clause = f"LOWER(title) LIKE LOWER('%{search}%') OR LOWER(text) LIKE LOWER('%{search}%')"
    
    query = f"""
        SELECT
            r.document_id as id,
            r.state,
            r.municipality,
            r.title,
            r.meeting_date,
            r.url,
            c.topics,
            s.stance as sentiment
        FROM {self.catalog}.{self.schema}.raw_documents r
        LEFT JOIN {self.catalog}.{self.schema}.classified_documents c ON r.document_id = c.document_id
        LEFT JOIN {self.catalog}.{self.schema}.sentiment_analysis s ON r.document_id = s.document_id
        WHERE {where_clause}
        ORDER BY r.meeting_date DESC
        LIMIT {limit}
        OFFSET {offset}
    """
    
    results = self.spark.sql(query).collect()
    
    return [
        {
            "id": row['id'],
            "state": row['state'],
            "municipality": row['municipality'],
            "title": row['title'],
            "meeting_date": row['meeting_date'].isoformat() if row['meeting_date'] else None,
            "url": row['url'],
            "topics": row['topics'] or [],
            "sentiment": row['sentiment']
        }
        for row in results
    ]


async def count_documents(self, search: Optional[str] = None) -> int:
    """Count total documents matching search."""
    where_clause = "1=1"
    if search:
        where_clause = f"LOWER(title) LIKE LOWER('%{search}%') OR LOWER(text) LIKE LOWER('%{search}%')"
    
    count = self.spark.sql(f"""
        SELECT COUNT(*) as count
        FROM {self.catalog}.{self.schema}.raw_documents
        WHERE {where_clause}
    """).collect()[0]['count']
    
    return count


async def get_opportunity(self, opportunity_id: str) -> Optional[Dict[str, Any]]:
    """Get a single opportunity by ID."""
    result = self.spark.sql(f"""
        SELECT *
        FROM {self.catalog}.{self.schema}.advocacy_opportunities
        WHERE opportunity_id = '{opportunity_id}'
    """).collect()
    
    if not result:
        return None
    
    row = result[0]
    return {
        "id": row['opportunity_id'],
        "state": row['state'],
        "municipality": row['municipality'],
        "topic": row['topic'],
        "urgency": row['urgency'],
        "talking_points": row['talking_points'] or []
    }
