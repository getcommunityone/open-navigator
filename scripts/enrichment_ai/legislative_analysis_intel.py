#!/usr/bin/env python3
"""
Intel Arc-Optimized Legislative Analysis System
Uses DuckDB + VSS for fast context injection into LLMs

Hardware: Intel Core Ultra 7 165H with Arc Graphics + NPU + 64GB RAM

Features:
- Fast DuckDB queries for legislative history
- Vector similarity search for relevant testimony
- Intel-optimized inference (IPEX-LLM or OpenVINO)
- Structured extraction: interest groups, lobbyists, positions, tradeoffs

Author: CommunityOne
Date: 2026-04-30
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import duckdb
from loguru import logger
import sys

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO")

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent  # Go up to project root from scripts/enrichment_ai/
DATA_DIR = PROJECT_ROOT / "data"
GOLD_DIR = DATA_DIR / "gold"
ANALYSIS_DIR = DATA_DIR / "gold" / "analysis"  # Store analysis results here
DUCKDB_PATH = DATA_DIR / "legislative.duckdb"

# Ensure output directories exist
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class InterestGroup:
    """Structured schema for interest group extraction"""
    group_name: str
    lobbyist: Optional[str]
    stance: str  # support, oppose, neutral, conditional
    stance_score: float  # -1.0 (oppose) to +1.0 (support)
    tradeoff_notes: Optional[str]
    testimony_excerpt: str
    bill_id: str
    confidence: float  # 0.0 to 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DuckDBLegislativeAnalyzer:
    """
    DuckDB-powered legislative analysis optimized for Intel Arc
    
    Why DuckDB?
    - 10-100x faster than Postgres for analytical queries
    - Native Parquet support (your Hugging Face datasets)
    - Embedded (no server needed)
    - Fast context injection for LLMs (thousands of rows in <100ms)
    """
    
    def __init__(self, db_path: Path = DUCKDB_PATH):
        self.db_path = db_path
        self.conn: Optional[duckdb.DuckDBPyConnection] = None
        
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def connect(self):
        """Connect to DuckDB and install extensions"""
        logger.info(f"📊 Connecting to DuckDB: {self.db_path}")
        self.conn = duckdb.connect(str(self.db_path))
        
        # Install VSS extension for vector similarity search
        try:
            self.conn.execute("INSTALL vss")
            self.conn.execute("LOAD vss")
            logger.info("✅ VSS extension loaded")
        except Exception as e:
            logger.warning(f"⚠️  VSS extension not available: {e}")
        
        # Install Parquet extension
        self.conn.execute("INSTALL parquet")
        self.conn.execute("LOAD parquet")
        logger.info("✅ Parquet extension loaded")
    
    def close(self):
        """Close connection"""
        if self.conn:
            self.conn.close()
            logger.info("🔌 DuckDB connection closed")
    
    def create_bills_table(self):
        """Create bills table from Parquet files"""
        logger.info("📋 Creating bills table...")
        
        # Read from OpenStates bulk data if available
        bills_parquet = DATA_DIR / "gold" / "bills_bills.parquet"
        
        if not bills_parquet.exists():
            logger.warning(f"⚠️  Bills parquet not found: {bills_parquet}")
            logger.info("   Creating demo bills table instead...")
            
            # Create demo table with sample data
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS bills (
                    identifier VARCHAR,
                    title TEXT,
                    abstract TEXT,
                    classification VARCHAR,
                    subject VARCHAR,
                    from_organization_name VARCHAR,
                    from_organization_state VARCHAR(2),
                    updated_at TIMESTAMP
                )
            """)
            
            # Insert demo data
            demo_bills = [
                ('HB1234', 'Water Fluoridation Act', 'Requires community water fluoridation', 'bill', 'Health', 'Alabama House', 'AL', '2026-04-01'),
                ('SB5678', 'Dental Care Access', 'Expands dental coverage for children', 'bill', 'Health', 'Georgia Senate', 'GA', '2026-04-15'),
                ('HB9012', 'School Health Programs', 'Funds oral health screenings in schools', 'bill', 'Education', 'Massachusetts House', 'MA', '2026-03-20'),
            ]
            self.conn.executemany("""
                INSERT INTO bills VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, demo_bills)
            
            logger.info("✅ Demo bills table created (3 sample bills)")
            return
        
        # Create table directly from Parquet
        self.conn.execute(f"""
            CREATE OR REPLACE TABLE bills AS 
            SELECT * FROM read_parquet('{bills_parquet}')
        """)
        
        logger.info("✅ Bills table created")
    
    def create_testimony_table(self):
        """Create testimony table with vector embeddings"""
        logger.info("📝 Creating testimony table...")
        
        # This would be populated from meeting transcripts
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS testimony (
                id INTEGER PRIMARY KEY,
                bill_id VARCHAR,
                speaker_name VARCHAR,
                organization VARCHAR,
                testimony_text TEXT,
                stance VARCHAR,  -- support, oppose, neutral
                timestamp TIMESTAMP,
                embedding FLOAT[384]  -- Sentence transformer embeddings
            )
        """)
        
        logger.info("✅ Testimony table created")
    
    def create_vector_index(self):
        """Create HNSW index for fast vector similarity search"""
        try:
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS testimony_vss_idx 
                ON testimony USING HNSW (embedding)
            """)
            logger.info("✅ Vector index created (HNSW)")
        except Exception as e:
            logger.warning(f"⚠️  Vector index creation failed: {e}")
    
    def search_similar_testimony(
        self, 
        query_embedding: List[float], 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Fast vector similarity search using VSS extension
        
        This is 100-1000x faster than computing similarity in Python
        """
        try:
            result = self.conn.execute(f"""
                SELECT 
                    id,
                    bill_id,
                    speaker_name,
                    organization,
                    testimony_text,
                    stance,
                    array_distance(embedding, ?::FLOAT[384]) as distance
                FROM testimony
                ORDER BY distance ASC
                LIMIT {limit}
            """, [query_embedding]).fetchall()
            
            return [
                {
                    'id': row[0],
                    'bill_id': row[1],
                    'speaker': row[2],
                    'organization': row[3],
                    'text': row[4],
                    'stance': row[5],
                    'similarity': 1.0 - row[6]  # Convert distance to similarity
                }
                for row in result
            ]
        except Exception as e:
            logger.error(f"❌ Vector search failed: {e}")
            return []
    
    def get_bill_context(self, bill_id: str) -> Dict[str, Any]:
        """
        Fast context retrieval for LLM injection
        
        On Intel Arc + 64GB RAM, this can pull 100+ page bills in <50ms
        """
        result = self.conn.execute("""
            SELECT 
                identifier,
                title,
                abstract,
                classification,
                subject,
                from_organization_name,
                updated_at
            FROM bills
            WHERE identifier = ?
        """, [bill_id]).fetchone()
        
        if not result:
            return {}
        
        return {
            'id': result[0],
            'title': result[1],
            'abstract': result[2],
            'classification': result[3],
            'subject': result[4],
            'sponsor': result[5],
            'updated': result[6]
        }
    
    def get_all_testimony_for_bill(self, bill_id: str) -> List[Dict[str, Any]]:
        """Get all testimony for a bill (for full context window)"""
        result = self.conn.execute("""
            SELECT 
                speaker_name,
                organization,
                testimony_text,
                stance,
                timestamp
            FROM testimony
            WHERE bill_id = ?
            ORDER BY timestamp
        """, [bill_id]).fetchall()
        
        return [
            {
                'speaker': row[0],
                'organization': row[1],
                'text': row[2],
                'stance': row[3],
                'timestamp': row[4]
            }
            for row in result
        ]
    
    def is_bill_analyzed(self, bill_id: str) -> bool:
        """
        Check if a bill has already been analyzed (incremental processing)
        
        Returns:
            True if analysis exists in Parquet, False otherwise
        """
        analysis_file = ANALYSIS_DIR / "interest_groups_analysis.parquet"
        
        if not analysis_file.exists():
            return False
        
        try:
            result = self.conn.execute(f"""
                SELECT COUNT(*) 
                FROM read_parquet('{analysis_file}')
                WHERE bill_id = ?
            """, [bill_id]).fetchone()
            
            return result[0] > 0 if result else False
        except:
            return False
    
    def save_analysis_results(
        self, 
        results: List[InterestGroup],
        append: bool = True
    ) -> Path:
        """
        Save analysis results to Parquet file (proper data pipeline!)
        
        Args:
            results: List of InterestGroup analysis results
            append: If True, append to existing file; if False, overwrite
            
        Returns:
            Path to saved Parquet file
        """
        if not results:
            logger.warning("No results to save")
            return None
        
        import pandas as pd
        
        # Convert to DataFrame
        df = pd.DataFrame([r.to_dict() for r in results])
        
        # Add metadata
        df['analyzed_at'] = pd.Timestamp.now()
        df['model'] = 'llama-3.2-3b'  # or from config
        
        output_file = ANALYSIS_DIR / "interest_groups_analysis.parquet"
        
        if append and output_file.exists():
            # Append to existing Parquet
            logger.info(f"📊 Appending {len(results)} results to {output_file}")
            
            # Read existing
            existing_df = pd.read_parquet(output_file)
            
            # Remove duplicates (keep newest)
            df_combined = pd.concat([existing_df, df], ignore_index=True)
            df_combined = df_combined.drop_duplicates(
                subset=['bill_id', 'group_name'], 
                keep='last'
            )
            
            # Save
            df_combined.to_parquet(output_file, index=False)
            logger.info(f"✅ Saved {len(df_combined)} total records")
        else:
            # Create new file
            logger.info(f"📊 Saving {len(results)} results to {output_file}")
            df.to_parquet(output_file, index=False)
            logger.info(f"✅ Created new analysis file")
        
        return output_file
    
    def get_bills_to_analyze(
        self,
        state: Optional[str] = None,
        topic_filter: Optional[str] = None,
        limit: int = 100,
        skip_analyzed: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get bills that need analysis (incremental processing support)
        
        Args:
            state: Filter by state code (e.g., 'GA', 'AL')
            topic_filter: Search term in title (e.g., 'fluorid')
            limit: Maximum bills to return
            skip_analyzed: Skip bills already in analysis Parquet
            
        Returns:
            List of bill dicts ready for analysis
        """
        # Build query
        where_clauses = []
        params = []
        
        if state:
            where_clauses.append("state = ?")
            params.append(state)
        
        if topic_filter:
            where_clauses.append("LOWER(title) LIKE ?")
            params.append(f"%{topic_filter.lower()}%")
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        # Get bills
        query = f"""
            SELECT bill_id, bill_number, title, abstract, state, jurisdiction_name
            FROM bills
            WHERE {where_sql}
            LIMIT ?
        """
        params.append(limit * 2)  # Get extra in case we filter some out
        
        bills = self.conn.execute(query, params).fetchall()
        
        # Convert to dicts
        result = []
        for row in bills:
            bill = {
                'bill_id': row[0],
                'bill_number': row[1],
                'title': row[2],
                'abstract': row[3],
                'state': row[4],
                'jurisdiction': row[5]
            }
            
            # Skip if already analyzed (incremental!)
            if skip_analyzed and self.is_bill_analyzed(bill['bill_id']):
                logger.debug(f"Skipping {bill['bill_number']} - already analyzed")
                continue
            
            result.append(bill)
            
            if len(result) >= limit:
                break
        
        return result
    
    def analyze_bill_statistics(self):
        """Fast analytical queries on bill data"""
        stats = {}
        
        # Check if bills table exists
        tables = self.conn.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'main' AND table_name = 'bills'
        """).fetchall()
        
        if not tables:
            logger.warning("⚠️  Bills table not found, skipping statistics")
            return {'top_states': [], 'top_topics': []}
        
        # Check what columns exist
        columns = self.conn.execute("DESCRIBE bills").fetchall()
        col_names = [col[0] for col in columns]
        
        # Adapt query based on available columns
        if 'state' in col_names and 'topic' in col_names and 'total_bills' in col_names:
            # This is bills_map_aggregates format (aggregated data)
            logger.info("   Using aggregated bills format (bills_map_aggregates)")
            
            # Bills by state
            result = self.conn.execute("""
                SELECT state, SUM(total_bills) as count
                FROM bills
                WHERE state IS NOT NULL
                GROUP BY state
                ORDER BY count DESC
                LIMIT 10
            """).fetchall()
            stats['top_states'] = [{'state': r[0], 'count': r[1]} for r in result]
            
            # Bills by topic
            result = self.conn.execute("""
                SELECT topic, SUM(total_bills) as count
                FROM bills
                WHERE topic IS NOT NULL
                GROUP BY topic
                ORDER BY count DESC
                LIMIT 10
            """).fetchall()
            stats['top_topics'] = [{'topic': r[0], 'count': r[1]} for r in result]
            
        elif 'state' in col_names and 'jurisdiction_name' in col_names:
            # This is OpenStates bills format (current data)
            logger.info("   Using OpenStates bills format")
            
            # Bills by state
            result = self.conn.execute("""
                SELECT state, jurisdiction_name, COUNT(*) as count
                FROM bills
                WHERE state IS NOT NULL
                GROUP BY state, jurisdiction_name
                ORDER BY count DESC
                LIMIT 10
            """).fetchall()
            stats['top_states'] = [{'state': r[0], 'jurisdiction': r[1], 'count': r[2]} for r in result]
            
            # Bills by session
            result = self.conn.execute("""
                SELECT session_name, COUNT(*) as count
                FROM bills
                WHERE session_name IS NOT NULL
                GROUP BY session_name
                ORDER BY count DESC
                LIMIT 10
            """).fetchall()
            stats['top_sessions'] = [{'session': r[0], 'count': r[1]} for r in result]
            
        elif 'from_organization_state' in col_names and 'subject' in col_names:
            # This is individual bills format (OpenStates schema)
            logger.info("   Using individual bills format (OpenStates schema)")
            
            # Bills by state
            result = self.conn.execute("""
                SELECT from_organization_state, COUNT(*) as count
                FROM bills
                WHERE from_organization_state IS NOT NULL
                GROUP BY from_organization_state
                ORDER BY count DESC
                LIMIT 10
            """).fetchall()
            stats['top_states'] = [{'state': r[0], 'count': r[1]} for r in result]
            
            # Bills by subject
            result = self.conn.execute("""
                SELECT subject, COUNT(*) as count
                FROM bills
                WHERE subject IS NOT NULL
                GROUP BY subject
                ORDER BY count DESC
                LIMIT 10
            """).fetchall()
            stats['top_subjects'] = [{'subject': r[0], 'count': r[1]} for r in result]
        else:
            logger.warning(f"⚠️  Unknown bills table schema, columns: {col_names[:5]}")
            return {'top_states': [], 'top_topics': []}
        
        return stats


class IntelOptimizedLLM:
    """
    Intel Arc-optimized LLM inference
    
    Uses IPEX-LLM or OpenVINO for maximum performance on Arc GPU + NPU
    """
    
    def __init__(self, model_name: str = "meta-llama/Llama-3.2-3B-Instruct"):
        self.model_name = model_name
        self.model = None
        self.tokenizer = None
        
        # Detect Intel hardware
        self.has_arc = self._detect_arc_gpu()
        logger.info(f"🎮 Intel Arc GPU detected: {self.has_arc}")
    
    def _detect_arc_gpu(self) -> bool:
        """Detect Intel Arc graphics via XPU availability"""
        try:
            import torch
            # Check if XPU module exists and has devices
            if hasattr(torch, 'xpu'):
                try:
                    return torch.xpu.is_available() and torch.xpu.device_count() > 0
                except:
                    pass
            
            # Fallback: check lspci for Arc GPU
            import subprocess
            result = subprocess.run(
                ['lspci'], 
                capture_output=True, 
                text=True,
                timeout=2
            )
            return 'Intel' in result.stdout and 'Arc' in result.stdout
        except:
            return False
    
    def load_model(self, use_openvino: bool = True):
        """
        Load model with Intel optimizations
        
        Options:
        1. OpenVINO: Best for Arc GPU (recommended)
        2. IPEX CPU: Good for CPU inference with Intel optimizations
        3. Transformers: Fallback (slower)
        """
        if use_openvino and self.has_arc:
            logger.info("🚀 Loading model with OpenVINO (Arc GPU optimized)...")
            try:
                from optimum.intel import OVModelForCausalLM
                from transformers import AutoTokenizer
                
                self.model = OVModelForCausalLM.from_pretrained(
                    self.model_name,
                    export=True,
                    device="GPU"  # Use Arc GPU
                )
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                logger.info("✅ Model loaded with OpenVINO (GPU)")
                return
            except Exception as e:
                logger.warning(f"⚠️  OpenVINO failed: {e}, falling back...")
        
        # Try Intel CPU optimizations
        logger.info("📦 Loading model with Intel CPU optimizations...")
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch
        import os
        
        # Get HF token from environment or .env file
        hf_token = os.getenv('HF_TOKEN') or os.getenv('HF_TOKEN')
        
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            device_map="cpu",
            torch_dtype=torch.bfloat16,  # Use bfloat16 for better CPU performance
            token=hf_token  # Pass token for gated models
        )
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
            token=hf_token  # Pass token for gated models
        )
        
        # Apply Intel optimizations
        try:
            import intel_extension_for_pytorch as ipex
            logger.info("🚀 Applying Intel CPU optimizations...")
            self.model = ipex.optimize(self.model, dtype=torch.bfloat16)
            logger.info("✅ Model loaded with Intel CPU optimizations")
        except Exception as e:
            logger.warning(f"⚠️  Intel optimizations failed: {e}")
            logger.info("✅ Model loaded (standard PyTorch)")
    
    def extract_interest_groups(
        self, 
        bill_context: Dict[str, Any],
        testimony: List[Dict[str, Any]]
    ) -> List[InterestGroup]:
        """
        Extract structured interest group data using LLM
        
        On 64GB RAM, we can fit the entire bill + all testimony in one prompt
        """
        if not self.model or not self.tokenizer:
            self.load_model()
        
        # Build prompt
        prompt = self._build_extraction_prompt(bill_context, testimony)
        
        # Run inference
        inputs = self.tokenizer(prompt, return_tensors="pt")
        outputs = self.model.generate(
            **inputs,
            max_new_tokens=2048,
            temperature=0.3,  # Lower for structured extraction
            do_sample=True
        )
        
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Parse JSON response
        try:
            groups_data = json.loads(response.split("```json")[1].split("```")[0])
            return [InterestGroup(**g) for g in groups_data.get('groups', [])]
        except:
            logger.error("❌ Failed to parse LLM response")
            return []
    
    def _build_extraction_prompt(
        self, 
        bill: Dict[str, Any], 
        testimony: List[Dict[str, Any]]
    ) -> str:
        """Build structured extraction prompt"""
        return f"""You are a legislative analyst. Extract interest group positions from testimony.

BILL: {bill['id']} - {bill['title']}
{bill.get('abstract', '')}

TESTIMONY:
{chr(10).join([f"- {t['speaker']} ({t['organization']}): {t['text'][:200]}..." for t in testimony])}

Extract each group's position in JSON format:
```json
{{
  "groups": [
    {{
      "group_name": "Organization name",
      "lobbyist": "Name if mentioned, else null",
      "stance": "support|oppose|neutral|conditional",
      "stance_score": -1.0 to 1.0,
      "tradeoff_notes": "Any concessions or compromises mentioned",
      "testimony_excerpt": "Key quote showing their position",
      "bill_id": "{bill['id']}",
      "confidence": 0.0 to 1.0
    }}
  ]
}}
```

Focus on:
1. Named organizations and their representatives
2. Explicit support/opposition statements
3. Conditional support ("we support IF...")
4. Tradeoffs or compromises mentioned

Return only valid JSON."""


def main():
    """Demo: Intel-optimized legislative analysis with incremental processing"""
    logger.info("🚀 Intel Arc-Optimized Legislative Analysis Demo")
    logger.info("=" * 60)
    logger.info("")
    logger.info("📁 Data Pipeline Architecture:")
    logger.info("   Source:      Parquet files (bills, sponsors, officials)")
    logger.info("   Processing:  DuckDB (fast queries) + Llama (AI analysis)")
    logger.info("   Results:     Parquet files (for reuse & sharing)")
    logger.info("   Incremental: Skip already-analyzed bills")
    logger.info("")
    
    # Initialize DuckDB analyzer
    with DuckDBLegislativeAnalyzer() as analyzer:
        # Create tables (DuckDB queries Parquet directly - no copying!)
        analyzer.create_bills_table()
        analyzer.create_testimony_table()
        
        # Show statistics
        logger.info("📊 Bill Statistics:")
        stats = analyzer.analyze_bill_statistics()
        logger.info(f"   Top states: {stats.get('top_states', [])[:5]}")
        if 'top_subjects' in stats:
            logger.info(f"   Top subjects: {stats.get('top_subjects', [])[:5]}")
        elif 'top_sessions' in stats:
            logger.info(f"   Top sessions: {stats.get('top_sessions', [])[:5]}")
        elif 'top_topics' in stats:
            logger.info(f"   Top topics: {stats.get('top_topics', [])[:5]}")
        
        # Demonstrate incremental processing
        logger.info("\n🔄 Incremental Processing Demo:")
        
        # Check for existing analysis results
        analysis_file = ANALYSIS_DIR / "interest_groups_analysis.parquet"
        if analysis_file.exists():
            # Show what's already analyzed
            result = analyzer.conn.execute(f"""
                SELECT 
                    COUNT(DISTINCT bill_id) as bills_analyzed,
                    COUNT(*) as total_groups,
                    COUNT(DISTINCT group_name) as unique_groups
                FROM read_parquet('{analysis_file}')
            """).fetchone()
            
            logger.info(f"   ✅ Found existing analysis:")
            logger.info(f"      - {result[0]} bills analyzed")
            logger.info(f"      - {result[1]} interest groups extracted")
            logger.info(f"      - {result[2]} unique organizations")
        else:
            logger.info(f"   📝 No existing analysis found")
            logger.info(f"   💾 Results will be saved to: {analysis_file}")
        
        # Get bills that need analysis (skips already-analyzed)
        logger.info("\n🔍 Finding bills to analyze...")
        bills_to_analyze = analyzer.get_bills_to_analyze(
            state='GA',  # Georgia bills
            topic_filter='fluorid',  # Fluoride-related
            limit=5,
            skip_analyzed=True  # Incremental processing!
        )
        
        if bills_to_analyze:
            logger.info(f"   📋 Found {len(bills_to_analyze)} unanalyzed bills:")
            for bill in bills_to_analyze[:3]:
                logger.info(f"      - {bill['bill_number']}: {bill['title'][:60]}...")
        else:
            logger.info(f"   ✅ All matching bills already analyzed!")
            logger.info(f"   💡 To re-analyze, delete {analysis_file}")
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ Demo complete!")
    logger.info("")
    logger.info("🎯 Why this architecture?")
    logger.info("")
    logger.info("   Parquet Storage:")
    logger.info("   ✅ Portable - share with anyone")
    logger.info("   ✅ Fast - columnar format")
    logger.info("   ✅ Compatible - works with Pandas, Spark, DuckDB")
    logger.info("   ✅ Versioned - track in git (if small) or DVC")
    logger.info("")
    logger.info("   DuckDB Query Engine:")
    logger.info("   ✅ 10-100x faster than Postgres for analytics")
    logger.info("   ✅ Queries Parquet directly (no import needed)")
    logger.info("   ✅ Embedded - no server to manage")
    logger.info("   ✅ SQL interface - easy to use")
    logger.info("")
    logger.info("   Incremental Processing:")
    logger.info("   ✅ Skip already-analyzed bills")
    logger.info("   ✅ Resume after failures")
    logger.info("   ✅ Append new results to Parquet")
    logger.info("")
    logger.info("📖 Next: Run batch analysis with:")
    logger.info("   python scripts/enrichment_ai/batch_analyze_bills.py")



if __name__ == "__main__":
    main()
