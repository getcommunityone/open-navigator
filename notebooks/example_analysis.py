# Databricks notebook source
# MAGIC %md
# MAGIC # CommunityOne Open Navigatory - Example Analysis
# MAGIC 
# MAGIC This notebook demonstrates how to use the CommunityOne Open Navigatory system
# MAGIC to analyze local government meeting minutes and identify advocacy opportunities.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup

# COMMAND ----------

from agents.orchestrator import OrchestratorAgent
from agents.scraper import ScraperAgent
from agents.parser import ParserAgent
from agents.classifier import ClassifierAgent
from agents.sentiment import SentimentAnalyzerAgent
from agents.advocacy import AdvocacyWriterAgent
from pipeline.delta_lake import DeltaLakePipeline
from visualization.heatmap import AdvocacyHeatmap

import pandas as pd

# COMMAND ----------

# MAGIC %md
# MAGIC ## Initialize Components

# COMMAND ----------

# Initialize pipeline
pipeline = DeltaLakePipeline()

# Initialize orchestrator
orchestrator = OrchestratorAgent()

# Register agents
orchestrator.register_agent(ScraperAgent())
orchestrator.register_agent(ParserAgent())
orchestrator.register_agent(ClassifierAgent())
orchestrator.register_agent(SentimentAnalyzerAgent())
orchestrator.register_agent(AdvocacyWriterAgent())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Define Scraping Targets

# COMMAND ----------

# Example targets across multiple cities
targets = [
    {
        "url": "https://example-city.legistar.com/Calendar.aspx",
        "municipality": "Example City",
        "state": "CA",
        "platform": "legistar"
    },
    {
        "url": "https://another-city.gov/meetings",
        "municipality": "Another City",
        "state": "NY",
        "platform": "generic"
    }
]

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run Analysis Pipeline

# COMMAND ----------

# Execute pipeline
results = await orchestrator.execute_pipeline(
    scrape_targets=targets,
    date_range={
        "start": "2024-01-01",
        "end": "2024-12-31"
    }
)

print(f"Pipeline Status: {results['success']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Query Results from Delta Lake

# COMMAND ----------

# Query advocacy opportunities
opportunities_df = spark.sql("""
    SELECT 
        municipality,
        state,
        topic,
        stance,
        urgency,
        meeting_date,
        recommended_action
    FROM oral_health.policy_analysis.advocacy_opportunities
    WHERE urgency IN ('critical', 'high')
    ORDER BY meeting_date DESC
""")

display(opportunities_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Analyze by State

# COMMAND ----------

# State-level aggregation
state_summary = spark.sql("""
    SELECT 
        state,
        COUNT(DISTINCT opportunity_id) as total_opportunities,
        COUNT(DISTINCT CASE WHEN urgency = 'critical' THEN opportunity_id END) as critical,
        COUNT(DISTINCT CASE WHEN urgency = 'high' THEN opportunity_id END) as high,
        COUNT(DISTINCT municipality) as municipalities
    FROM oral_health.policy_analysis.advocacy_opportunities
    GROUP BY state
    ORDER BY total_opportunities DESC
""")

display(state_summary)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Topic Analysis

# COMMAND ----------

# Topic distribution
topic_analysis = spark.sql("""
    SELECT 
        topic,
        COUNT(*) as count,
        AVG(CASE 
            WHEN urgency = 'critical' THEN 4
            WHEN urgency = 'high' THEN 3
            WHEN urgency = 'medium' THEN 2
            WHEN urgency = 'low' THEN 1
            ELSE 0 
        END) as avg_urgency_score
    FROM oral_health.policy_analysis.advocacy_opportunities
    GROUP BY topic
    ORDER BY count DESC
""")

display(topic_analysis)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Generate Visualizations

# COMMAND ----------

# Convert to pandas for visualization
opportunities_pd = opportunities_df.toPandas()

# Create heatmap
heatmap_gen = AdvocacyHeatmap()
m = heatmap_gen.create_folium_map(opportunities_pd.to_dict('records'))

# Display map
displayHTML(m._repr_html_())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Example: Retrieve Advocacy Materials

# COMMAND ----------

# Query generated advocacy materials
materials = spark.sql("""
    SELECT 
        opportunity_id,
        municipality,
        state,
        topic,
        email_subject,
        email_body,
        talking_points
    FROM oral_health.policy_analysis.advocacy_materials
    WHERE state = 'CA'
    LIMIT 5
""")

display(materials)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Export Results

# COMMAND ----------

# Export critical opportunities to CSV
critical_opps = opportunities_df.filter("urgency = 'critical'")
critical_opps.write.mode("overwrite").csv("/dbfs/oral-health-exports/critical-opportunities.csv")

print("Critical opportunities exported successfully")
