#!/usr/bin/env python3
"""
RAG Vector Database Setup for ViFake Analytics
Vietnamese scam pattern indexing and retrieval

Tuân thủ Privacy-by-Design:
- Zero-trust RAM processing
- Synthetic data indexing only
- No personal information storage
"""

import os
import json
import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import chromadb
from chromadb.config import Settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class RAGConfig:
    """Cấu hình cho RAG System"""
    collection_name: str = "vifake_scam_patterns"
    embedding_model: str = "vinai/phobert-base"
    max_documents: int = 10000
    similarity_threshold: float = 0.7
    
    # Vector database settings
    persist_directory: str = "ai_engine/nlp_worker/chroma_db"
    distance_metric: str = "cosine"

class VietnameseRAGSetup:
    """RAG setup for Vietnamese scam pattern detection"""
    
    def __init__(self, config: RAGConfig):
        self.config = config
        self.client = None
        self.collection = None
        self.embedding_model = None
        
        # Initialize components
        self._setup_chroma()
        self._load_embedding_model()
    
    def _setup_chroma(self):
        """Setup Chroma vector database"""
        logger.info("🗄️ Setting up Chroma vector database...")
        
        try:
            # Create persist directory
            os.makedirs(self.config.persist_directory, exist_ok=True)
            
            # Initialize Chroma client
            self.client = chromadb.PersistentClient(
                path=self.config.persist_directory,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Get or create collection
            try:
                self.collection = self.client.get_collection(self.config.collection_name)
                logger.info(f"✅ Using existing collection: {self.config.collection_name}")
            except Exception:
                self.collection = self.client.create_collection(
                    name=self.config.collection_name,
                    metadata={"description": "Vietnamese scam patterns for ViFake Analytics"}
                )
                logger.info(f"✅ Created new collection: {self.config.collection_name}")
            
            logger.info(f"📊 Collection count: {self.collection.count()}")
            
        except Exception as e:
            logger.error(f"❌ Chroma setup failed: {e}")
            raise
    
    def _load_embedding_model(self):
        """Load Vietnamese embedding model"""
        logger.info("🤖 Loading Vietnamese embedding model...")
        
        try:
            from transformers import AutoTokenizer, AutoModel
            import torch
            
            # Load model and tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.config.embedding_model)
            self.embedding_model = AutoModel.from_pretrained(self.config.embedding_model)
            self.embedding_model.eval()
            
            logger.info(f"✅ Loaded embedding model: {self.config.embedding_model}")
            
        except Exception as e:
            logger.error(f"❌ Failed to load embedding model: {e}")
            # Fallback to simple embeddings
            logger.warning("⚠️ Using fallback embedding method")
            self.embedding_model = None
    
    def _get_embedding(self, text: str) -> List[float]:
        """Get text embedding"""
        try:
            if self.embedding_model is not None:
                # Use PhoBERT for embeddings
                inputs = self.tokenizer(
                    text,
                    return_tensors="pt",
                    truncation=True,
                    max_length=256,
                    padding=True
                )
                
                with torch.no_grad():
                    outputs = self.embedding_model(**inputs)
                    # Use mean pooling of last hidden state
                    embeddings = outputs.last_hidden_state.mean(dim=1).squeeze().numpy()
                
                return embeddings.tolist()
            else:
                # Fallback: simple character-based embedding
                import hashlib
                hash_obj = hashlib.md5(text.encode())
                hash_hex = hash_obj.hexdigest()
                
                # Convert to numeric vector
                embedding = []
                for i in range(0, len(hash_hex), 2):
                    byte_val = int(hash_hex[i:i+2], 16)
                    embedding.append(byte_val / 255.0)
                
                # Pad/truncate to consistent size
                target_size = 768  # PhoBERT embedding size
                while len(embedding) < target_size:
                    embedding.append(0.0)
                return embedding[:target_size]
                
        except Exception as e:
            logger.error(f"❌ Embedding failed: {e}")
            # Return zero embedding
            return [0.0] * 768
    
    def index_synthetic_data(self, data_file: str):
        """Index synthetic scam data"""
        logger.info(f"📚 Indexing synthetic data from: {data_file}")
        
        try:
            # Load synthetic data
            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"📊 Loaded {len(data)} synthetic samples")
            
            # Prepare documents for indexing
            documents = []
            metadatas = []
            ids = []
            
            for i, sample in enumerate(data):
                # Extract conversation text
                conversation_text = " ".join([
                    turn['text'] for turn in sample.get('conversation', [])
                ])
                
                # Create document
                document = conversation_text
                
                # Create metadata
                metadata = {
                    'synthetic_id': sample.get('synthetic_id', f'synth_{i}'),
                    'scenario': sample.get('scenario', 'unknown'),
                    'age_group': sample.get('age_group', 'unknown'),
                    'realism_score': sample.get('realism_score', 0.0),
                    'label': sample.get('label', 'unknown'),
                    'severity': sample.get('severity', 'unknown'),
                    'risk_indicators': sample.get('risk_indicators', {}),
                    'language_variant': sample.get('language_variant', 'unknown'),
                    'conversation_turns': sample.get('conversation_turns', 0),
                    'indexed_at': datetime.now().isoformat()
                }
                
                documents.append(document)
                metadatas.append(metadata)
                ids.append(sample.get('synthetic_id', f'synth_{i}'))
            
            # Add to collection in batches
            batch_size = 100
            for i in range(0, len(documents), batch_size):
                batch_docs = documents[i:i + batch_size]
                batch_metas = metadatas[i:i + batch_size]
                batch_ids = ids[i:i + batch_size]
                
                # Get embeddings for batch
                embeddings = [self._get_embedding(doc) for doc in batch_docs]
                
                # Add to collection
                self.collection.add(
                    documents=batch_docs,
                    metadatas=batch_metas,
                    ids=batch_ids,
                    embeddings=embeddings
                )
                
                logger.info(f"📊 Indexed batch {i//batch_size + 1}/{(len(documents)-1)//batch_size + 1}")
            
            logger.info(f"✅ Successfully indexed {len(documents)} documents")
            logger.info(f"📊 Collection count: {self.collection.count()}")
            
        except Exception as e:
            logger.error(f"❌ Indexing failed: {e}")
            raise
    
    def search_similar_patterns(self, query_text: str, n_results: int = 5) -> List[Dict]:
        """Search for similar scam patterns"""
        logger.info(f"🔍 Searching patterns similar to: {query_text[:50]}...")
        
        try:
            # Get query embedding
            query_embedding = self._get_embedding(query_text)
            
            # Search in collection
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                include=["documents", "metadatas", "distances"]
            )
            
            # Format results
            formatted_results = []
            for i in range(len(results['ids'][0])):
                result = {
                    'id': results['ids'][0][i],
                    'document': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'similarity_score': 1 - results['distances'][0][i],  # Convert distance to similarity
                    'distance': results['distances'][0][i]
                }
                formatted_results.append(result)
            
            logger.info(f"✅ Found {len(formatted_results)} similar patterns")
            return formatted_results
            
        except Exception as e:
            logger.error(f"❌ Search failed: {e}")
            return []
    
    def get_pattern_statistics(self) -> Dict:
        """Get statistics about indexed patterns"""
        try:
            # Get all documents count
            total_count = self.collection.count()
            
            if total_count == 0:
                return {
                    'total_patterns': 0,
                    'scenario_distribution': {},
                    'age_group_distribution': {},
                    'severity_distribution': {},
                    'average_realism': 0.0
                }
            
            # Get sample of metadata for statistics
            sample_results = self.collection.get(
                limit=min(1000, total_count),
                include=["metadatas"]
            )
            
            # Analyze distributions
            scenario_dist = {}
            age_dist = {}
            severity_dist = {}
            realism_scores = []
            
            for metadata in sample_results['metadatas']:
                scenario = metadata.get('scenario', 'unknown')
                age = metadata.get('age_group', 'unknown')
                severity = metadata.get('severity', 'unknown')
                realism = metadata.get('realism_score', 0.0)
                
                scenario_dist[scenario] = scenario_dist.get(scenario, 0) + 1
                age_dist[age] = age_dist.get(age, 0) + 1
                severity_dist[severity] = severity_dist.get(severity, 0) + 1
                realism_scores.append(realism)
            
            avg_realism = sum(realism_scores) / len(realism_scores) if realism_scores else 0.0
            
            return {
                'total_patterns': total_count,
                'scenario_distribution': scenario_dist,
                'age_group_distribution': age_dist,
                'severity_distribution': severity_dist,
                'average_realism': avg_realism,
                'sample_size': len(sample_results['metadatas'])
            }
            
        except Exception as e:
            logger.error(f"❌ Statistics failed: {e}")
            return {}
    
    def update_pattern(self, pattern_id: str, new_text: str, new_metadata: Dict):
        """Update an existing pattern"""
        logger.info(f"🔄 Updating pattern: {pattern_id}")
        
        try:
            # Get new embedding
            new_embedding = self._get_embedding(new_text)
            
            # Update metadata
            new_metadata['updated_at'] = datetime.now().isoformat()
            
            # Update in collection
            self.collection.update(
                ids=[pattern_id],
                documents=[new_text],
                metadatas=[new_metadata],
                embeddings=[new_embedding]
            )
            
            logger.info(f"✅ Pattern updated: {pattern_id}")
            
        except Exception as e:
            logger.error(f"❌ Pattern update failed: {e}")
            raise
    
    def delete_pattern(self, pattern_id: str):
        """Delete a pattern from the database"""
        logger.info(f"🗑️ Deleting pattern: {pattern_id}")
        
        try:
            self.collection.delete(ids=[pattern_id])
            logger.info(f"✅ Pattern deleted: {pattern_id}")
            
        except Exception as e:
            logger.error(f"❌ Pattern deletion failed: {e}")
            raise
    
    def reset_database(self):
        """Reset the entire database"""
        logger.warning("🗑️ Resetting entire database...")
        
        try:
            # Delete collection
            self.client.delete_collection(self.config.collection_name)
            
            # Recreate collection
            self.collection = self.client.create_collection(
                name=self.config.collection_name,
                metadata={"description": "Vietnamese scam patterns for ViFake Analytics"}
            )
            
            logger.info("✅ Database reset completed")
            
        except Exception as e:
            logger.error(f"❌ Database reset failed: {e}")
            raise
    
    def export_patterns(self, output_file: str):
        """Export all patterns to file"""
        logger.info(f"📤 Exporting patterns to: {output_file}")
        
        try:
            # Get all patterns
            all_results = self.collection.get(
                include=["documents", "metadatas", "embeddings"]
            )
            
            # Format for export
            export_data = {
                'export_info': {
                    'total_patterns': len(all_results['ids']),
                    'export_date': datetime.now().isoformat(),
                    'collection_name': self.config.collection_name
                },
                'patterns': []
            }
            
            for i in range(len(all_results['ids'])):
                pattern = {
                    'id': all_results['ids'][i],
                    'document': all_results['documents'][i],
                    'metadata': all_results['metadatas'][i],
                    'embedding': all_results['embeddings'][i] if 'embeddings' in all_results else None
                }
                export_data['patterns'].append(pattern)
            
            # Save to file
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ Exported {len(export_data['patterns'])} patterns")
            
        except Exception as e:
            logger.error(f"❌ Export failed: {e}")
            raise

# Global RAG instance
_rag_instance = None

def get_rag_instance() -> VietnameseRAGSetup:
    """Get singleton RAG instance"""
    global _rag_instance
    if _rag_instance is None:
        config = RAGConfig()
        _rag_instance = VietnameseRAGSetup(config)
    return _rag_instance

# Convenience functions
def index_synthetic_scams(data_file: str):
    """Index synthetic scam data"""
    rag = get_rag_instance()
    return rag.index_synthetic_data(data_file)

def search_similar_scams(query: str, n_results: int = 5) -> List[Dict]:
    """Search for similar scam patterns"""
    rag = get_rag_instance()
    return rag.search_similar_patterns(query, n_results)

def get_pattern_stats() -> Dict:
    """Get pattern statistics"""
    rag = get_rag_instance()
    return rag.get_pattern_statistics()

if __name__ == "__main__":
    # Test RAG setup
    logger.info("🧪 Testing Vietnamese RAG Setup...")
    
    try:
        rag = get_rag_instance()
        logger.info("✅ RAG setup initialized")
        
        # Test with synthetic data if available
        synthetic_file = "data/synthetic/vietnamese_child_scams_labeled.json"
        if os.path.exists(synthetic_file):
            logger.info("📚 Indexing synthetic data...")
            rag.index_synthetic_data(synthetic_file)
            
            # Get statistics
            stats = rag.get_pattern_statistics()
            logger.info(f"📊 Pattern statistics: {stats}")
            
            # Test search
            test_query = "free robux giveaway"
            results = rag.search_similar_scams(test_query, n_results=3)
            logger.info(f"🔍 Search results for '{test_query}': {len(results)} patterns found")
        
        logger.info("✅ RAG setup test completed")
        
    except Exception as e:
        logger.error(f"❌ RAG setup test failed: {e}")
        raise
