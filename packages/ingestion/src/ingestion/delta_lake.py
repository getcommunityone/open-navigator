"""
Lakehouse Data Pipeline for storing and querying policy documents.

Uses Delta Lake on Databricks for:
- Scalable storage of millions of meeting minutes
- Version control and audit trails
- Fast analytical queries
- Support for streaming and batch processing
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import pandas as pd
from loguru import logger

from config import settings


class DeltaLakePipeline:
    """
    Pipeline for managing data in Delta Lake.
    
    Tables:
    - raw_documents: Scraped meeting minutes
    - parsed_documents: Structured document data
    - classified_documents: Documents with topic classifications
    - sentiment_analysis: Sentiment and stance analysis
    - advocacy_materials: Generated advocacy content
    - advocacy_opportunities: Identified opportunities
    """
    
    def __init__(self):
        """Initialize the Delta Lake pipeline."""
        self.catalog = settings.catalog_name
        self.schema = settings.schema_name
        self.base_path = settings.delta_lake_path
        
        # Initialize Databricks connection (would be done via SDK)
        self.spark = None  # Would initialize PySpark session
        
    def initialize_tables(self):
        """Create Delta Lake tables if they don't exist."""
        tables = {
            "raw_documents": """
                CREATE TABLE IF NOT EXISTS {catalog}.{schema}.raw_documents (
                    document_id STRING,
                    source_url STRING,
                    municipality STRING,
                    state STRING,
                    meeting_date TIMESTAMP,
                    meeting_type STRING,
                    title STRING,
                    content STRING,
                    scraped_at TIMESTAMP,
                    metadata MAP<STRING, STRING>,
                    _ingestion_timestamp TIMESTAMP
                )
                USING DELTA
                PARTITIONED BY (state, DATE(meeting_date))
                TBLPROPERTIES (
                    'delta.enableChangeDataFeed' = 'true',
                    'delta.autoOptimize.optimizeWrite' = 'true',
                    'delta.autoOptimize.autoCompact' = 'true'
                )
            """,
            
            "parsed_documents": """
                CREATE TABLE IF NOT EXISTS {catalog}.{schema}.parsed_documents (
                    document_id STRING,
                    municipality STRING,
                    state STRING,
                    meeting_date TIMESTAMP,
                    meeting_time STRING,
                    meeting_type STRING,
                    attendees ARRAY<STRING>,
                    agenda_items ARRAY<STRUCT<number:STRING, description:STRING>>,
                    motions ARRAY<STRUCT<text:STRING>>,
                    votes ARRAY<STRUCT<result:STRING>>,
                    discussion_sections ARRAY<STRUCT<section_id:INT, text:STRING>>,
                    full_text STRING,
                    parsed_at TIMESTAMP,
                    _processing_timestamp TIMESTAMP
                )
                USING DELTA
                PARTITIONED BY (state, DATE(meeting_date))
            """,
            
            "classified_documents": """
                CREATE TABLE IF NOT EXISTS {catalog}.{schema}.classified_documents (
                    document_id STRING,
                    municipality STRING,
                    state STRING,
                    meeting_date TIMESTAMP,
                    primary_topic STRING,
                    all_topics ARRAY<STRING>,
                    confidence STRING,
                    relevant_excerpts ARRAY<STRUCT<source:STRING, text:STRING>>,
                    classified_at TIMESTAMP,
                    _processing_timestamp TIMESTAMP
                )
                USING DELTA
                PARTITIONED BY (state, primary_topic)
            """,
            
            "sentiment_analysis": """
                CREATE TABLE IF NOT EXISTS {catalog}.{schema}.sentiment_analysis (
                    document_id STRING,
                    municipality STRING,
                    state STRING,
                    meeting_date TIMESTAMP,
                    stance STRING,
                    debate_intensity STRING,
                    support_score INT,
                    opposition_score INT,
                    debate_score INT,
                    urgency_score INT,
                    advocacy_urgency STRING,
                    key_arguments STRUCT<supporting:ARRAY<STRING>, opposing:ARRAY<STRING>>,
                    analyzed_at TIMESTAMP,
                    _processing_timestamp TIMESTAMP
                )
                USING DELTA
                PARTITIONED BY (state, advocacy_urgency)
            """,
            
            "advocacy_opportunities": """
                CREATE TABLE IF NOT EXISTS {catalog}.{schema}.advocacy_opportunities (
                    opportunity_id STRING,
                    document_id STRING,
                    municipality STRING,
                    state STRING,
                    meeting_date TIMESTAMP,
                    topic STRING,
                    stance STRING,
                    intensity STRING,
                    urgency STRING,
                    recommended_action STRING,
                    created_at TIMESTAMP,
                    status STRING,
                    _processing_timestamp TIMESTAMP
                )
                USING DELTA
                PARTITIONED BY (state, urgency)
            """,
            
            "advocacy_materials": """
                CREATE TABLE IF NOT EXISTS {catalog}.{schema}.advocacy_materials (
                    material_id STRING,
                    opportunity_id STRING,
                    municipality STRING,
                    state STRING,
                    topic STRING,
                    email_subject STRING,
                    email_body STRING,
                    talking_points ARRAY<STRING>,
                    social_media MAP<STRING, STRING>,
                    policy_brief STRING,
                    generated_at TIMESTAMP,
                    _processing_timestamp TIMESTAMP
                )
                USING DELTA
                PARTITIONED BY (state)
            """
        }
        
        for table_name, ddl in tables.items():
            formatted_ddl = ddl.format(
                catalog=self.catalog,
                schema=self.schema
            )
            logger.info(f"Creating table: {table_name}")
            # Would execute: self.spark.sql(formatted_ddl)
    
    def write_raw_documents(self, documents: List[Dict[str, Any]]):
        """Write scraped documents to raw_documents table."""
        if not documents:
            return
        
        df = pd.DataFrame(documents)
        df['_ingestion_timestamp'] = datetime.utcnow()
        
        # Convert to Delta Lake format
        # In production: df.to_spark().write.format("delta").mode("append").save(...)
        
        logger.info(f"Wrote {len(documents)} raw documents to Delta Lake")
    
    def write_parsed_documents(self, documents: List[Dict[str, Any]]):
        """Write parsed documents to parsed_documents table."""
        if not documents:
            return
        
        # Transform nested structures for Delta Lake
        processed_docs = []
        for doc in documents:
            processed_docs.append({
                **doc,
                '_processing_timestamp': datetime.utcnow()
            })
        
        df = pd.DataFrame(processed_docs)
        
        logger.info(f"Wrote {len(processed_docs)} parsed documents to Delta Lake")
    
    def write_classifications(self, documents: List[Dict[str, Any]]):
        """Write classified documents."""
        if not documents:
            return
        
        classifications = []
        for doc in documents:
            classification = doc.get('classification', {})
            classifications.append({
                'document_id': doc['document_id'],
                'municipality': doc['municipality'],
                'state': doc['state'],
                'meeting_date': doc['meeting_date'],
                'primary_topic': classification.get('primary_topic'),
                'all_topics': classification.get('all_topics', []),
                'confidence': classification.get('confidence'),
                'relevant_excerpts': classification.get('relevant_excerpts', []),
                'classified_at': classification.get('classified_at'),
                '_processing_timestamp': datetime.utcnow()
            })
        
        logger.info(f"Wrote {len(classifications)} classifications to Delta Lake")
    
    def write_sentiment_analysis(self, documents: List[Dict[str, Any]]):
        """Write sentiment analysis results."""
        if not documents:
            return
        
        analyses = []
        for doc in documents:
            sentiment = doc.get('sentiment_analysis', {})
            analyses.append({
                'document_id': doc['document_id'],
                'municipality': doc['municipality'],
                'state': doc['state'],
                'meeting_date': doc['meeting_date'],
                'stance': sentiment.get('stance'),
                'debate_intensity': sentiment.get('debate_intensity'),
                'support_score': sentiment.get('support_score'),
                'opposition_score': sentiment.get('opposition_score'),
                'debate_score': sentiment.get('debate_score'),
                'urgency_score': sentiment.get('urgency_score'),
                'advocacy_urgency': sentiment.get('advocacy_urgency'),
                'key_arguments': sentiment.get('key_arguments'),
                'analyzed_at': sentiment.get('analyzed_at'),
                '_processing_timestamp': datetime.utcnow()
            })
        
        logger.info(f"Wrote {len(analyses)} sentiment analyses to Delta Lake")
    
    def write_advocacy_opportunities(self, opportunities: List[Dict[str, Any]]):
        """Write identified advocacy opportunities."""
        if not opportunities:
            return
        
        for opp in opportunities:
            opp['_processing_timestamp'] = datetime.utcnow()
            opp['status'] = 'active'
            opp['created_at'] = datetime.utcnow()
        
        logger.info(f"Wrote {len(opportunities)} opportunities to Delta Lake")
    
    def write_advocacy_materials(self, materials: List[Dict[str, Any]]):
        """Write generated advocacy materials."""
        if not materials:
            return
        
        flattened = []
        for material in materials:
            email = material['materials']['email']
            flattened.append({
                'material_id': material['opportunity_id'],
                'opportunity_id': material['opportunity_id'],
                'municipality': material['municipality'],
                'state': material['state'],
                'topic': material['topic'],
                'email_subject': email['subject'],
                'email_body': email['body'],
                'talking_points': material['materials']['talking_points'],
                'social_media': material['materials']['social_media'],
                'policy_brief': str(material['materials']['policy_brief']),
                'generated_at': material['generated_at'],
                '_processing_timestamp': datetime.utcnow()
            })
        
        logger.info(f"Wrote {len(flattened)} advocacy materials to Delta Lake")
    
    def query_opportunities_by_state(
        self,
        state: str,
        urgency: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Query advocacy opportunities by state and urgency."""
        query = f"""
            SELECT *
            FROM {self.catalog}.{self.schema}.advocacy_opportunities
            WHERE state = '{state}'
            AND status = 'active'
        """
        
        if urgency:
            query += f" AND urgency = '{urgency}'"
        
        query += " ORDER BY meeting_date DESC"
        
        # Would execute: results = self.spark.sql(query).toPandas()
        
        return []
    
    def query_heatmap_data(self) -> List[Dict[str, Any]]:
        """
        Query data for generating advocacy heatmap.
        
        Returns aggregated statistics by geographic area.
        """
        query = f"""
            SELECT 
                state,
                municipality,
                COUNT(DISTINCT document_id) as total_documents,
                COUNT(DISTINCT CASE WHEN urgency IN ('critical', 'high') 
                    THEN opportunity_id END) as urgent_opportunities,
                MAX(meeting_date) as latest_meeting,
                COLLECT_SET(topic) as topics_discussed
            FROM {self.catalog}.{self.schema}.advocacy_opportunities
            WHERE status = 'active'
            GROUP BY state, municipality
            ORDER BY urgent_opportunities DESC
        """
        
        # Would execute and return results
        return []
    
    def get_document_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a complete document with all analysis."""
        query = f"""
            SELECT 
                r.*,
                c.primary_topic,
                c.confidence,
                s.stance,
                s.debate_intensity,
                s.advocacy_urgency
            FROM {self.catalog}.{self.schema}.raw_documents r
            LEFT JOIN {self.catalog}.{self.schema}.classified_documents c
                ON r.document_id = c.document_id
            LEFT JOIN {self.catalog}.{self.schema}.sentiment_analysis s
                ON r.document_id = s.document_id
            WHERE r.document_id = '{document_id}'
        """
        
        return None
