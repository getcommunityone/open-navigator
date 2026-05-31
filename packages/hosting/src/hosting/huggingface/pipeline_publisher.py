"""
HuggingFace Dataset Publisher

Publishes jurisdiction discovery datasets and run outputs to HuggingFace Hub
for public sharing and collaboration.

Datasets published:
- census-gid: Census Bureau Government Integrated Directory data
- gov-domains: CISA .gov domain master list
- nces-schools: NCES school district data
- discovered-urls: Discovered government URLs with metadata
- scraping-targets: Prioritized scraping targets
- policy-documents: Analyzed meeting minutes and policy documents
"""
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path
import pandas as pd
from loguru import logger

try:
    from datasets import Dataset, DatasetDict
    from huggingface_hub import HfApi, login, create_repo
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False
    logger.warning("HuggingFace libraries not installed. Run: pip install datasets huggingface-hub")

try:
    from pyspark.sql import SparkSession, DataFrame
    PYSPARK_AVAILABLE = True
except ImportError:
    PYSPARK_AVAILABLE = False
    SparkSession = None
    DataFrame = None
    logger.warning("PySpark not available. Will use pandas DataFrames only.")

from config import settings


class HuggingFacePublisher:
    """
    Publisher for sharing datasets on HuggingFace Hub.
    
    Usage:
        publisher = HuggingFacePublisher(token="hf_your_token")
        publisher.publish_census_data()
        publisher.publish_discovered_urls()
    """
    
    def __init__(self, token: Optional[str] = None):
        """
        Initialize HuggingFace publisher.
        
        Args:
            token: HuggingFace API token (or use HF_TOKEN env var)
        """
        if not HF_AVAILABLE:
            raise ImportError("HuggingFace libraries required. Install with: pip install datasets huggingface-hub")
        
        self.token = token or settings.huggingface_token
        self.organization = settings.hf_organization
        self.dataset_prefix = settings.hf_dataset_prefix
        
        if not self.token:
            raise ValueError(
                "HuggingFace token required. Set HF_TOKEN in .env or pass token parameter."
            )
        
        # Login to HuggingFace
        login(token=self.token)
        self.api = HfApi()
        
        # Initialize Spark (optional - only if available)
        if PYSPARK_AVAILABLE:
            try:
                # Use Delta Lake's helper to configure Spark with Delta JARs
                from delta import configure_spark_with_delta_pip
                
                builder = SparkSession.builder \
                    .appName("HFPublisher") \
                    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
                    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
                
                self.spark = configure_spark_with_delta_pip(builder).getOrCreate()
                logger.info("✅ HuggingFace publisher initialized with Delta Lake support")
            except Exception as e:
                logger.warning(f"PySpark/Delta initialization failed: {e}. Will use pandas only.")
                self.spark = None
        else:
            self.spark = None
            logger.info("✅ HuggingFace publisher initialized (pandas mode - no PySpark)")
    
    def _get_repo_id(self, dataset_name: str) -> str:
        """
        Get full repository ID for dataset.
        
        Args:
            dataset_name: Name of the dataset
            
        Returns:
            Full repo ID (e.g., "CommunityOne/open-navigator-census-gid")
        """
        full_name = f"{self.dataset_prefix}-{dataset_name}"
        
        if self.organization:
            return f"{self.organization}/{full_name}"
        else:
            return full_name
    
    def _create_dataset_repo(self, dataset_name: str, private: bool = False) -> str:
        """
        Create dataset repository on HuggingFace Hub.
        
        Args:
            dataset_name: Name of the dataset
            private: Whether to make the dataset private
            
        Returns:
            Repository ID
        """
        repo_id = self._get_repo_id(dataset_name)
        
        try:
            create_repo(
                repo_id=repo_id,
                repo_type="dataset",
                private=private,
                exist_ok=True
            )
            logger.info(f"✅ Created/verified dataset repo: {repo_id}")
            return repo_id
        except Exception as e:
            logger.error(f"Failed to create repo {repo_id}: {e}")
            raise
    
    def _spark_to_pandas(self, df: DataFrame, limit: Optional[int] = None) -> pd.DataFrame:
        """
        Convert Spark DataFrame to Pandas for HuggingFace upload.
        
        Args:
            df: Spark DataFrame
            limit: Optional row limit for sampling
            
        Returns:
            Pandas DataFrame
        """
        if limit:
            df = df.limit(limit)
        
        return df.toPandas()
    
    def publish_census_data(
        self,
        private: bool = False,
        sample_size: Optional[int] = None
    ) -> Dict[str, str]:
        """
        Publish Census Bureau GID data to HuggingFace.
        
        Args:
            private: Whether to make dataset private
            sample_size: Optional sample size per jurisdiction type
            
        Returns:
            Dictionary with dataset URLs
        """
        logger.info("Publishing Census Bureau GID data to HuggingFace...")
        
        repo_id = self._create_dataset_repo("census-gid", private=private)
        
        # Load jurisdiction data from Bronze layer
        jurisdiction_types = ["counties", "municipalities", "townships", "school_districts", "special_districts"]
        
        datasets = {}
        for jtype in jurisdiction_types:
            try:
                bronze_path = f"{settings.delta_lake_path}/bronze/jurisdictions/{jtype}"
                df = self.spark.read.format("delta").load(bronze_path)
                
                # Convert to Pandas
                pdf = self._spark_to_pandas(df, limit=sample_size)
                
                # Create HF Dataset
                datasets[jtype] = Dataset.from_pandas(pdf)
                logger.info(f"  ✓ {jtype}: {len(pdf):,} records")
                
            except Exception as e:
                logger.warning(f"  ⚠ Skipping {jtype}: {e}")
        
        if not datasets:
            logger.warning("No census data found to publish")
            return {"error": "No census data found to publish"}
        
        # Create DatasetDict and push
        dataset_dict = DatasetDict(datasets)
        
        dataset_dict.push_to_hub(
            repo_id=repo_id,
            private=private,
            commit_message=f"Update Census GID data - {datetime.now().strftime('%Y-%m-%d')}"
        )
        
        url = f"https://huggingface.co/datasets/{repo_id}"
        logger.success(f"✅ Published census data to: {url}")
        
        return {"repo_id": repo_id, "url": url, "splits": list(datasets.keys())}
    
    def publish_gov_domains(
        self,
        private: bool = False
    ) -> Dict[str, str]:
        """
        Publish CISA .gov domain list to HuggingFace.
        
        Args:
            private: Whether to make dataset private
            
        Returns:
            Dictionary with dataset URL
        """
        logger.info("Publishing CISA .gov domains to HuggingFace...")
        
        repo_id = self._create_dataset_repo("gov-domains", private=private)
        
        # Load from Bronze layer
        bronze_path = f"{settings.delta_lake_path}/bronze/gov_domains"
        df = self.spark.read.format("delta").load(bronze_path)
        
        # Convert to Pandas
        pdf = self._spark_to_pandas(df)
        
        # Create HF Dataset
        dataset = Dataset.from_pandas(pdf)
        
        dataset.push_to_hub(
            repo_id=repo_id,
            private=private,
            commit_message=f"Update .gov domains - {datetime.now().strftime('%Y-%m-%d')}"
        )
        
        url = f"https://huggingface.co/datasets/{repo_id}"
        logger.success(f"✅ Published {len(pdf):,} .gov domains to: {url}")
        
        return {"repo_id": repo_id, "url": url, "records": len(pdf)}
    
    def publish_nces_schools(
        self,
        private: bool = False
    ) -> Dict[str, str]:
        """
        Publish NCES school district data to HuggingFace.
        
        Args:
            private: Whether to make dataset private
            
        Returns:
            Dictionary with dataset URL
        """
        logger.info("Publishing NCES school districts to HuggingFace...")
        
        repo_id = self._create_dataset_repo("nces-schools", private=private)
        
        # Load from Bronze layer
        bronze_path = f"{settings.delta_lake_path}/bronze/nces_school_districts"
        df = self.spark.read.format("delta").load(bronze_path)
        
        # Convert to Pandas
        pdf = self._spark_to_pandas(df)
        
        # Create HF Dataset
        dataset = Dataset.from_pandas(pdf)
        
        dataset.push_to_hub(
            repo_id=repo_id,
            private=private,
            commit_message=f"Update NCES school districts - {datetime.now().strftime('%Y-%m-%d')}"
        )
        
        url = f"https://huggingface.co/datasets/{repo_id}"
        logger.success(f"✅ Published {len(pdf):,} school districts to: {url}")
        
        return {"repo_id": repo_id, "url": url, "records": len(pdf)}
    
    def publish_discovered_urls(
        self,
        private: bool = False,
        min_confidence: float = 0.6
    ) -> Dict[str, str]:
        """
        Publish discovered government URLs to HuggingFace.
        
        Args:
            private: Whether to make dataset private
            min_confidence: Minimum confidence score to include
            
        Returns:
            Dictionary with dataset URL
        """
        logger.info("Publishing discovered URLs to HuggingFace...")
        
        repo_id = self._create_dataset_repo("discovered-urls", private=private)
        
        # Load from Silver layer
        silver_path = f"{settings.delta_lake_path}/silver/discovered_urls"
        df = self.spark.read.format("delta").load(silver_path)
        
        # Filter by confidence
        df = df.filter(df.confidence_score >= min_confidence)
        
        # Convert to Pandas
        pdf = self._spark_to_pandas(df)
        
        # Create HF Dataset
        dataset = Dataset.from_pandas(pdf)
        
        dataset.push_to_hub(
            repo_id=repo_id,
            private=private,
            commit_message=f"Update discovered URLs (min confidence: {min_confidence}) - {datetime.now().strftime('%Y-%m-%d')}"
        )
        
        url = f"https://huggingface.co/datasets/{repo_id}"
        logger.success(f"✅ Published {len(pdf):,} discovered URLs to: {url}")
        
        return {"repo_id": repo_id, "url": url, "records": len(pdf)}
    
    def publish_scraping_targets(
        self,
        private: bool = False
    ) -> Dict[str, str]:
        """
        Publish prioritized scraping targets to HuggingFace.
        
        Args:
            private: Whether to make dataset private
            
        Returns:
            Dictionary with dataset URL
        """
        logger.info("Publishing scraping targets to HuggingFace...")
        
        repo_id = self._create_dataset_repo("scraping-targets", private=private)
        
        # Load from Gold layer
        gold_path = f"{settings.delta_lake_path}/gold/scraping_targets"
        df = self.spark.read.format("delta").load(gold_path)
        
        # Convert to Pandas
        pdf = self._spark_to_pandas(df)
        
        # Create HF Dataset
        dataset = Dataset.from_pandas(pdf)
        
        dataset.push_to_hub(
            repo_id=repo_id,
            private=private,
            commit_message=f"Update scraping targets - {datetime.now().strftime('%Y-%m-%d')}"
        )
        
        url = f"https://huggingface.co/datasets/{repo_id}"
        logger.success(f"✅ Published {len(pdf):,} scraping targets to: {url}")
        
        return {"repo_id": repo_id, "url": url, "records": len(pdf)}
    
    def publish_all(
        self,
        private: bool = False,
        sample_census: bool = False
    ) -> Dict[str, Dict[str, str]]:
        """
        Publish all datasets to HuggingFace.
        
        Args:
            private: Whether to make datasets private
            sample_census: Whether to sample census data (faster for testing)
            
        Returns:
            Dictionary with all dataset URLs
        """
        logger.info("🚀 Publishing all datasets to HuggingFace...")
        
        results = {}
        
        # Publish each dataset
        try:
            results["census"] = self.publish_census_data(
                private=private,
                sample_size=1000 if sample_census else None
            )
        except Exception as e:
            logger.error(f"Failed to publish census data: {e}")
            results["census"] = {"error": str(e)}
        
        try:
            results["gov_domains"] = self.publish_gov_domains(private=private)
        except Exception as e:
            logger.error(f"Failed to publish .gov domains: {e}")
            results["gov_domains"] = {"error": str(e)}
        
        try:
            results["nces_schools"] = self.publish_nces_schools(private=private)
        except Exception as e:
            logger.error(f"Failed to publish NCES schools: {e}")
            results["nces_schools"] = {"error": str(e)}
        
        try:
            results["discovered_urls"] = self.publish_discovered_urls(private=private)
        except Exception as e:
            logger.error(f"Failed to publish discovered URLs: {e}")
            results["discovered_urls"] = {"error": str(e)}
        
        try:
            results["scraping_targets"] = self.publish_scraping_targets(private=private)
        except Exception as e:
            logger.error(f"Failed to publish scraping targets: {e}")
            results["scraping_targets"] = {"error": str(e)}
        
        logger.success("✅ Dataset publishing complete!")
        
        return results


async def main():
    """Test HuggingFace publisher."""
    publisher = HuggingFacePublisher()
    
    # Publish all datasets
    results = publisher.publish_all(private=False, sample_census=True)
    
    print("\n📊 Published Datasets:")
    for name, info in results.items():
        if "url" in info:
            print(f"  ✓ {name}: {info['url']}")
        else:
            print(f"  ✗ {name}: {info.get('error', 'Unknown error')}")


if __name__ == "__main__":
    asyncio.run(main())
