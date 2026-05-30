"""
Example usage script demonstrating the complete workflow.
"""
import asyncio
import json
from pathlib import Path

from agents.orchestrator import OrchestratorAgent
from agents.scraper import ScraperAgent
from agents.parser import ParserAgent
from agents.classifier import ClassifierAgent
from agents.sentiment import SentimentAnalyzerAgent
from agents.advocacy import AdvocacyWriterAgent
from pipeline.delta_lake import DeltaLakePipeline
from scripts.visualization.heatmap import AdvocacyHeatmap
from loguru import logger


async def run_example_workflow():
    """
    Example workflow demonstrating the complete policy analysis pipeline.
    """
    logger.info("Starting example workflow")
    
    # 1. Initialize orchestrator and register agents
    logger.info("Initializing orchestrator and agents")
    orchestrator = OrchestratorAgent()
    
    # Register all agents
    orchestrator.register_agent(ScraperAgent())
    orchestrator.register_agent(ParserAgent())
    orchestrator.register_agent(ClassifierAgent())
    orchestrator.register_agent(SentimentAnalyzerAgent())
    orchestrator.register_agent(AdvocacyWriterAgent())
    
    # 2. Define scraping targets
    logger.info("Defining scraping targets")
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
        },
        {
            "url": "https://third-city.granicus.com/meetings",
            "municipality": "Third City",
            "state": "TX",
            "platform": "granicus"
        }
    ]
    
    # 3. Execute the pipeline
    logger.info(f"Executing pipeline with {len(targets)} targets")
    results = await orchestrator.execute_pipeline(
        scrape_targets=targets,
        date_range={
            "start": "2024-01-01",
            "end": "2024-12-31"
        }
    )
    
    logger.info(f"Pipeline results: {results}")
    
    # 4. Query results (simulated - would query from Delta Lake)
    logger.info("Querying results")
    pipeline = DeltaLakePipeline()
    
    # Example: Query opportunities by state
    ca_opportunities = pipeline.query_opportunities_by_state("CA", urgency="critical")
    logger.info(f"Found {len(ca_opportunities)} critical opportunities in California")
    
    # 5. Generate visualizations
    logger.info("Generating heatmap visualization")
    heatmap_gen = AdvocacyHeatmap()
    
    # Create example opportunities for visualization
    example_opportunities = [
        {
            "document_id": "doc-001",
            "municipality": "San Francisco",
            "state": "CA",
            "meeting_date": "2024-03-15",
            "source_url": "https://example.com/meeting-1",
            "topic": "water_fluoridation",
            "stance": "debated",
            "intensity": "high",
            "urgency": "critical",
            "recommended_action": "Contact officials immediately. Vote imminent."
        },
        {
            "document_id": "doc-002",
            "municipality": "Los Angeles",
            "state": "CA",
            "meeting_date": "2024-03-20",
            "source_url": "https://example.com/meeting-2",
            "topic": "school_dental_screening",
            "stance": "supportive",
            "intensity": "moderate",
            "urgency": "medium",
            "recommended_action": "Provide supporting materials."
        },
        {
            "document_id": "doc-003",
            "municipality": "New York City",
            "state": "NY",
            "meeting_date": "2024-03-18",
            "source_url": "https://example.com/meeting-3",
            "topic": "medicaid_dental",
            "stance": "opposed",
            "intensity": "high",
            "urgency": "high",
            "recommended_action": "Address concerns with decision-makers."
        }
    ]
    
    # Generate map
    m = heatmap_gen.create_folium_map(
        example_opportunities,
        title="Oral Health Policy Advocacy Heatmap - Example"
    )
    
    # Export map
    output_path = Path("example_heatmap.html")
    heatmap_gen.export_map_html(m, str(output_path))
    logger.info(f"Heatmap exported to {output_path}")
    
    # 6. Generate dashboard
    logger.info("Generating dashboard")
    dashboard = heatmap_gen.create_dashboard(example_opportunities)
    
    logger.info(f"Dashboard statistics: {dashboard['statistics']}")
    
    # 7. Export results
    logger.info("Exporting results")
    results_data = {
        "workflow_completed": True,
        "targets_processed": len(targets),
        "opportunities_found": len(example_opportunities),
        "critical_count": dashboard['statistics']['critical_count'],
        "high_count": dashboard['statistics']['high_count'],
        "states_affected": dashboard['statistics']['states_affected']
    }
    
    output_file = Path("example_results.json")
    with open(output_file, 'w') as f:
        json.dump(results_data, f, indent=2)
    
    logger.info(f"Results exported to {output_file}")
    logger.info("Example workflow completed successfully!")
    
    return results_data


if __name__ == "__main__":
    # Run the example workflow
    results = asyncio.run(run_example_workflow())
    
    print("\n" + "="*60)
    print("WORKFLOW SUMMARY")
    print("="*60)
    print(f"Targets Processed: {results['targets_processed']}")
    print(f"Opportunities Found: {results['opportunities_found']}")
    print(f"Critical Priority: {results['critical_count']}")
    print(f"High Priority: {results['high_count']}")
    print(f"States Affected: {results['states_affected']}")
    print("="*60)
    print("\nCheck 'example_heatmap.html' for the interactive visualization!")
