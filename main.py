"""
Main entry point for running the Oral Health Policy Pulse system.
"""
import asyncio
import sys
from pathlib import Path
from typing import List, Optional
import click
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from agents.orchestrator import OrchestratorAgent
from agents.scraper import ScraperAgent
from agents.parser import ParserAgent
from agents.classifier import ClassifierAgent
from agents.sentiment import SentimentAnalyzerAgent
from agents.advocacy import AdvocacyWriterAgent
from pipeline.delta_lake import DeltaLakePipeline
# Lazy import for visualization to avoid requiring folium in local mode
# from visualization.heatmap import AdvocacyHeatmap
from config import settings


# Configure logging
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level=settings.log_level
)
logger.add(
    settings.log_file,
    rotation="500 MB",
    retention="10 days",
    level=settings.log_level
)


@click.group()
def cli():
    """Oral Health Policy Pulse - Multi-agent policy analysis system."""
    pass


@cli.command()
@click.option('--host', default='0.0.0.0', help='API host')
@click.option('--port', default=8000, help='API port')
@click.option('--reload', is_flag=True, help='Enable auto-reload')
def serve(host: str, port: int, reload: bool):
    """Start the API server."""
    import uvicorn
    from api.main import app
    
    logger.info(f"Starting API server on {host}:{port}")
    
    uvicorn.run(
        "api.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=1 if reload else settings.api_workers
    )


@cli.command()
@click.option('--state', help='State to analyze')
@click.option('--municipality', help='Municipality to analyze')
@click.option('--url', required=True, help='URL to scrape')
@click.option('--platform', default='generic', help='Platform type (legistar, granicus, suiteonemedia, generic)')
@click.option('--max-events', default=500, show_default=True, help='Max events to scrape (0=unlimited, SuiteOne only)')
@click.option('--start-year', default=0, show_default=True, help='Only include events on/after this year (0=all, SuiteOne only)')
@click.option('--include-social/--no-include-social', default=True, show_default=True,
              help='Also scrape discovered YouTube transcripts and Facebook post text')
@click.option('--output', default=None, help='Output JSON file path (default: output/<municipality>_<platform>.json)')
def scrape(state: str, municipality: str, url: str, platform: str, max_events: int, start_year: int,
           include_social: bool, output: str):
    """Scrape meeting minutes from a single source."""
    import json
    from datetime import datetime
    logger.info(f"Scraping {url} for {municipality}, {state}")
    
    async def run_scrape():
        scraper = ScraperAgent()
        
        async with scraper:
            targets = [{
                "url": url,
                "municipality": municipality,
                "state": state,
                "platform": platform,
                "max_events": max_events,
                "start_year": start_year,
            }]
            
            documents = await scraper._scrape_targets(targets, {})

            if include_social:
                social_docs = await scraper.scrape_social_sources(
                    municipality=municipality,
                    state=state,
                    seed_url=url,
                )
                documents.extend(social_docs)
                logger.info(f"Scraped {len(social_docs)} social media documents")
            
            logger.info(f"Scraped {len(documents)} documents")
            
            # Save to pipeline
            pipeline = DeltaLakePipeline()
            pipeline.write_raw_documents(documents)

            # Persist to JSON
            out_path = output
            if not out_path:
                safe_name = (municipality or "unknown").replace(" ", "_").lower()
                out_dir = Path("output") / safe_name
                out_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                out_path = str(out_dir / f"{platform}_{timestamp}.json")

            # Make metadata JSON-serializable
            serializable = []
            for doc in documents:
                d = dict(doc)
                if "metadata" in d and isinstance(d["metadata"], dict):
                    d["metadata"] = {k: (str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v)
                                     for k, v in d["metadata"].items()}
                serializable.append(d)

            Path(out_path).write_text(json.dumps(serializable, indent=2, default=str))
            logger.info(f"Saved {len(serializable)} documents to {out_path}")
    
    asyncio.run(run_scrape())


@cli.command()
@click.option('--targets-file', required=True, help='JSON file with scrape targets')
def analyze(targets_file: str):
    """Run full analysis pipeline on targets."""
    import json
    
    logger.info(f"Starting analysis pipeline with targets from {targets_file}")
    
    # Load targets
    with open(targets_file, 'r') as f:
        targets = json.load(f)
    
    async def run_pipeline():
        # Initialize orchestrator and agents
        orchestrator = OrchestratorAgent()
        orchestrator.register_agent(ScraperAgent())
        orchestrator.register_agent(ParserAgent())
        orchestrator.register_agent(ClassifierAgent())
        orchestrator.register_agent(SentimentAnalyzerAgent())
        orchestrator.register_agent(AdvocacyWriterAgent())
        
        # Execute pipeline
        results = await orchestrator.execute_pipeline(targets)
        
        logger.info(f"Pipeline completed: {results}")
    
    asyncio.run(run_pipeline())


@cli.command()
@click.option('--output', default='heatmap.html', help='Output file path')
@click.option('--urgency', help='Filter by urgency level')
def generate_heatmap(output: str, urgency: Optional[str]):
    """Generate advocacy heatmap visualization."""
    logger.info(f"Generating heatmap (urgency={urgency})")
    
    # Lazy import - only load when generating heatmap
    try:
        from visualization.heatmap import AdvocacyHeatmap
    except ImportError:
        click.echo("❌ Visualization dependencies not installed!")
        click.echo("   Install with: pip install folium plotly")
        return
    
    # Query opportunities
    pipeline = DeltaLakePipeline()
    opportunities = pipeline.query_opportunities_by_state(None, urgency)
    
    # Generate map
    heatmap = AdvocacyHeatmap()
    m = heatmap.create_folium_map(opportunities)
    
    # Save
    heatmap.export_map_html(m, output)
    
    logger.info(f"Heatmap saved to {output}")


@cli.command()
def init():
    """Initialize the system (create database tables, etc.)."""
    logger.info("Initializing Oral Health Policy Pulse system")
    
    try:
        pipeline = DeltaLakePipeline()
        pipeline.initialize_tables()
        
        logger.info("System initialized successfully")
        
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        sys.exit(1)


@cli.command()
def status():
    """Show system status."""
    logger.info("Checking system status")
    
    # Check configuration
    click.echo(f"Catalog: {settings.catalog_name}")
    click.echo(f"Schema: {settings.schema_name}")
    click.echo(f"Delta Lake Path: {settings.delta_lake_path}")
    click.echo(f"Log Level: {settings.log_level}")
    
    # Check connections
    click.echo("\nSystem Status: OK")


@cli.command()
@click.option('--limit', default=None, type=int, help='Limit number of jurisdictions to discover')
@click.option('--state', help='Discover only jurisdictions in this state')
@click.option('--type', 'jurisdiction_type', help='Filter by type (county, municipality, school_district)')
def discover_jurisdictions(limit: Optional[int], state: Optional[str], jurisdiction_type: Optional[str]):
    """Run jurisdiction discovery pipeline to identify government websites."""
    logger.info(f"Starting jurisdiction discovery (limit={limit}, state={state}, type={jurisdiction_type})")
    
    try:
        from scripts.discovery.discovery_pipeline import DiscoveryPipeline
    except ImportError:
        click.echo("❌ Discovery modules not available!")
        return

    async def run_discovery():
        pipeline = DiscoveryPipeline()
        try:
            results = await pipeline.run_full_pipeline(
                discovery_limit=limit,
                state_filter=state,
                type_filter=jurisdiction_type,
            )
            logger.info(f"Discovery completed: {results}")
            click.echo(f"\n✅ Discovery Complete!")
            click.echo(f"   Bronze records: {results.get('bronze_records', 0)}")
            click.echo(f"   URLs discovered: {results.get('urls_discovered', 0)}")
            click.echo(f"   Scraping targets: {results.get('scraping_targets', 0)}")
        finally:
            pipeline.close()

    asyncio.run(run_discovery())


@cli.command()
def discovery_stats():
    """Show jurisdiction discovery statistics."""
    logger.info("Fetching discovery statistics")
    
    from pyspark.sql import SparkSession
    from pyspark.sql.functions import col, count, avg, when
    
    spark = SparkSession.builder.getOrCreate()
    
    click.echo("\n📊 Jurisdiction Discovery Statistics\n")
    
    try:
        # Bronze layer stats
        bronze_df = spark.read.format("delta").load(f"{settings.delta_lake_path}/bronze/jurisdictions/unified")
        total_jurisdictions = bronze_df.count()
        click.echo(f"Bronze Layer (Raw Data):")
        click.echo(f"  Total jurisdictions: {total_jurisdictions:,}")
        
        by_type = bronze_df.groupBy("jurisdiction_type").count().collect()
        for row in by_type:
            click.echo(f"    - {row['jurisdiction_type']}: {row['count']:,}")
        
        # Silver layer stats
        silver_df = spark.read.format("delta").load(f"{settings.delta_lake_path}/silver/discovered_urls")
        urls_discovered = silver_df.count()
        homepages_found = silver_df.filter(col("homepage_url").isNotNull()).count()
        minutes_found = silver_df.filter(col("minutes_url").isNotNull()).count()
        avg_confidence = silver_df.select(avg("confidence_score")).collect()[0][0]
        
        click.echo(f"\nSilver Layer (Discovered URLs):")
        click.echo(f"  Total discoveries: {urls_discovered:,}")
        click.echo(f"  Homepages found: {homepages_found:,} ({homepages_found/urls_discovered*100:.1f}%)")
        click.echo(f"  Minutes URLs found: {minutes_found:,} ({minutes_found/urls_discovered*100:.1f}%)")
        click.echo(f"  Avg confidence: {avg_confidence:.2f}")
        
        # Gold layer stats
        gold_df = spark.read.format("delta").load(f"{settings.delta_lake_path}/gold/scraping_targets")
        scraping_targets = gold_df.count()
        high_priority = gold_df.filter(col("priority_score") > 150).count()
        
        click.echo(f"\nGold Layer (Scraping Targets):")
        click.echo(f"  Total targets: {scraping_targets:,}")
        click.echo(f"  High priority: {high_priority:,}")
        
        by_status = gold_df.groupBy("scraping_status").count().collect()
        for row in by_status:
            click.echo(f"    - {row['scraping_status']}: {row['count']:,}")
        
    except Exception as e:
        click.echo(f"❌ Error: {e}")
        click.echo("(Run 'python main.py discover-jurisdictions' first)")


@cli.command()
@click.option('--source', type=click.Choice(['manual', 'discovered']), default='discovered', 
              help='Source of scraping targets')
@click.option('--limit', default=100, type=int, help='Max number of sites to scrape')
@click.option('--priority', default=100, type=int, help='Min priority score (for discovered sources)')
def scrape_batch(source: str, limit: int, priority: int):
    """Scrape multiple sites in batch mode."""
    logger.info(f"Starting batch scrape (source={source}, limit={limit}, priority={priority})")
    
    async def run_batch_scrape():
        from pyspark.sql import SparkSession
        from pyspark.sql.functions import col
        
        spark = SparkSession.builder.getOrCreate()
        
        if source == 'discovered':
            # Load from gold scraping targets
            targets_df = spark.read.format("delta").load(
                f"{settings.delta_lake_path}/gold/scraping_targets"
            ).filter(
                (col("priority_score") >= priority) & 
                (col("scraping_status") == "pending")
            ).limit(limit)
            
            targets = [
                {
                    "url": row.minutes_url,
                    "municipality": row.jurisdiction_name,
                    "state": row.state,
                    "platform": row.cms_platform or "generic",
                    "jurisdiction_id": row.jurisdiction_id
                }
                for row in targets_df.collect()
            ]
        else:
            click.echo("Manual source not yet implemented")
            return
        
        click.echo(f"Scraping {len(targets)} targets...")
        
        scraper = ScraperAgent()
        async with scraper:
            documents = await scraper._scrape_targets(targets, {})
            
            logger.info(f"Scraped {len(documents)} documents")
            click.echo(f"✅ Scraped {len(documents)} documents")
            
            # Save to pipeline
            pipeline = DeltaLakePipeline()
            pipeline.write_raw_documents(documents)
            click.echo(f"✅ Documents saved to Delta Lake")
    
    asyncio.run(run_batch_scrape())


@cli.command()
@click.option('--dataset', type=click.Choice(['census', 'gov-domains', 'nces-schools', 'discovered-urls', 'scraping-targets', 'all']), default='all', help='Dataset to publish')
@click.option('--private', is_flag=True, help='Make dataset private')
@click.option('--sample', is_flag=True, help='Sample census data (faster for testing)')
def publish_to_hf(dataset: str, private: bool, sample: bool):
    """
    Publish datasets to HuggingFace Hub for sharing.
    
    Examples:
        python main.py publish-to-hf --dataset all
        python main.py publish-to-hf --dataset discovered-urls --private
        python main.py publish-to-hf --dataset census --sample
    """
    from pipeline.huggingface_publisher import HuggingFacePublisher, HF_AVAILABLE
    
    if not HF_AVAILABLE:
        click.echo("❌ HuggingFace libraries not installed!")
        click.echo("   Install with: pip install datasets huggingface-hub")
        return
    
    click.echo("🚀 Publishing datasets to HuggingFace Hub...")
    
    try:
        publisher = HuggingFacePublisher()
        
        if dataset == 'all':
            results = publisher.publish_all(private=private, sample_census=sample)
            
            click.echo("\n📊 Published Datasets:")
            for name, info in results.items():
                if "url" in info:
                    click.echo(f"  ✓ {name}: {info['url']}")
                else:
                    click.echo(f"  ✗ {name}: {info.get('error', 'Unknown error')}")
        
        elif dataset == 'census':
            result = publisher.publish_census_data(private=private, sample_size=1000 if sample else None)
            click.echo(f"✅ Published to: {result['url']}")
        
        elif dataset == 'gov-domains':
            result = publisher.publish_gov_domains(private=private)
            click.echo(f"✅ Published {result['records']:,} domains to: {result['url']}")
        
        elif dataset == 'nces-schools':
            result = publisher.publish_nces_schools(private=private)
            click.echo(f"✅ Published {result['records']:,} schools to: {result['url']}")
        
        elif dataset == 'discovered-urls':
            result = publisher.publish_discovered_urls(private=private)
            click.echo(f"✅ Published {result['records']:,} URLs to: {result['url']}")
        
        elif dataset == 'scraping-targets':
            result = publisher.publish_scraping_targets(private=private)
            click.echo(f"✅ Published {result['records']:,} targets to: {result['url']}")
        
        click.echo("\n🎉 Publishing complete!")
        
    except ValueError as e:
        click.echo(f"❌ Configuration error: {e}")
        click.echo("   Set HF_TOKEN in .env file")
    except Exception as e:
        click.echo(f"❌ Publishing failed: {e}")
        logger.exception("HuggingFace publishing error")


if __name__ == "__main__":
    cli()
