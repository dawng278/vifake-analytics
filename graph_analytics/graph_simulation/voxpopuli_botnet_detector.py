#!/usr/bin/env python3
"""
Graph Simulation - VoxPopuli Dataset for Neo4j Botnet Detection
Sử dụng tập dữ liệu voxpopuli để trích xuất cấu trúc mạng lưới và phát hiện botnet

Tuân thủ Privacy-by-Design:
- Chỉ sử dụng cấu trúc mạng, không lưu nội dung cá nhân
- Neo4j graph simulation với scam node injection
- PageRank và Louvain algorithms cho botnet detection
"""

import os
import sys
import json
import logging
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from enum import Enum
import networkx as nx
import numpy as np
from neo4j import GraphDatabase
from pymongo import MongoClient
from datasets import load_dataset
import pandas as pd
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class NodeType(Enum):
    """Các loại node trong graph"""
    USER = "user"
    CONTENT = "content"
    INTERACTION = "interaction"
    SCAMMER = "scammer"
    VICTIM = "victim"
    PLATFORM = "platform"

class RelationType(Enum):
    """Các loại relationship trong graph"""
    POSTS = "POSTS"
    LIKES = "LIKES"
    SHARES = "SHARES"
    COMMENTS = "COMMENTS"
    MENTIONS = "MENTIONS"
    FOLLOWS = "FOLLOWS"
    SCAM_TARGETS = "SCAM_TARGETS"
    PROPAGATES_TO = "PROPAGATES_TO"

@dataclass
class GraphSimulationConfig:
    """Cấu hình cho Graph Simulation"""
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "password")
    mongo_uri: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_name: str = "vifake_analytics"
    
    # VoxPopuli processing
    voxpopuli_sample_size: int = 10000
    min_interaction_threshold: int = 5
    
    # Botnet detection parameters
    pagerank_threshold: float = 0.01
    community_size_threshold: int = 10
    scam_injection_ratio: float = 0.15  # 15% of nodes as scam nodes
    
    # Graph analysis
    max_propagation_depth: int = 5
    centrality_threshold: float = 0.05

class VoxPopuliProcessor:
    """Xử lý VoxPopuli dataset để trích xuất cấu trúc mạng lưới"""
    
    def __init__(self, config: GraphSimulationConfig):
        self.config = config
        self.user_interactions = {}
        self.content_interactions = {}
        self.network_structure = {}
        
    def load_voxpopuli_dataset(self) -> List[Dict]:
        """Load và xử lý VoxPopuli dataset"""
        logger.info("📥 Loading VoxPopuli dataset for network structure extraction...")
        
        try:
            # Load VoxPopuli dataset (streaming mode for large dataset)
            dataset = load_dataset("facebook/voxpopuli", split="train", streaming=True)
            
            network_data = []
            processed_count = 0
            
            for sample in tqdm(dataset, desc="Processing VoxPopuli"):
                if processed_count >= self.config.voxpopuli_sample_size:
                    break
                
                # Extract network structure information
                network_sample = self._extract_network_structure(sample)
                if network_sample:
                    network_data.append(network_sample)
                    processed_count += 1
                
                # Log progress
                if processed_count % 1000 == 0:
                    logger.info(f"📊 Processed {processed_count} network samples")
            
            logger.info(f"✅ Extracted network structure from {len(network_data)} samples")
            return network_data
            
        except Exception as e:
            logger.error(f"❌ Failed to load VoxPopuli dataset: {e}")
            # Fallback to synthetic network generation
            logger.info("🔄 Falling back to synthetic network generation...")
            return self._generate_synthetic_network()
    
    def _extract_network_structure(self, sample: Dict) -> Optional[Dict]:
        """Trích xuất cấu trúc mạng từ sample VoxPopuli"""
        try:
            # Extract user interactions
            user_id = sample.get('speaker_id', f"user_{uuid.uuid4().hex[:8]}")
            
            # Extract content and interaction patterns
            content_id = sample.get('utterance_id', f"content_{uuid.uuid4().hex[:8]}")
            
            # Extract interaction metadata
            interaction_data = {
                'user_id': user_id,
                'content_id': content_id,
                'timestamp': sample.get('start_time', 0),
                'interaction_type': 'utterance',
                'context_length': len(sample.get('text', '')),
                'speaker_role': sample.get('speaker_role', 'unknown')
            }
            
            return interaction_data
            
        except Exception as e:
            logger.warning(f"⚠️ Error extracting network structure: {e}")
            return None
    
    def _generate_synthetic_network(self) -> List[Dict]:
        """Tạo mạng lưới tổng hợp nếu VoxPopuli không available"""
        logger.info("🔄 Generating synthetic network structure...")
        
        network_data = []
        num_users = 1000
        num_contents = 500
        
        # Generate users
        users = [f"user_{i:04d}" for i in range(num_users)]
        contents = [f"content_{i:04d}" for i in range(num_contents)]
        
        # Generate interactions (power law distribution)
        for i in range(self.config.voxpopuli_sample_size):
            user_id = random.choice(users)
            content_id = random.choice(contents)
            
            # Power law distribution for interaction frequency
            interaction_weight = np.random.pareto(1.5) + 1
            
            network_data.append({
                'user_id': user_id,
                'content_id': content_id,
                'timestamp': random.uniform(0, 1000000),
                'interaction_type': random.choice(['like', 'share', 'comment']),
                'interaction_weight': interaction_weight,
                'speaker_role': random.choice(['regular', 'influencer', 'new'])
            })
        
        logger.info(f"✅ Generated synthetic network with {len(network_data)} interactions")
        return network_data
    
    def build_network_graph(self, network_data: List[Dict]) -> nx.Graph:
        """Xây dựng NetworkX graph từ dữ liệu mạng lưới"""
        logger.info("🕸️ Building network graph...")
        
        G = nx.Graph()
        
        # Add nodes and edges
        for interaction in network_data:
            user_id = interaction['user_id']
            content_id = interaction['content_id']
            
            # Add nodes with attributes
            if not G.has_node(user_id):
                G.add_node(user_id, node_type=NodeType.USER.value)
            
            if not G.has_node(content_id):
                G.add_node(content_id, node_type=NodeType.CONTENT.value)
            
            # Add edge with interaction weight
            edge_weight = interaction.get('interaction_weight', 1.0)
            if G.has_edge(user_id, content_id):
                G[user_id][content_id]['weight'] += edge_weight
                G[user_id][content_id]['interactions'] += 1
            else:
                G.add_edge(user_id, content_id, 
                          weight=edge_weight,
                          interactions=1,
                          interaction_type=interaction['interaction_type'])
        
        logger.info(f"✅ Built graph with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
        return G

class ScamNodeInjector:
    """Tiêm scam node vào graph để mô phỏng botnet"""
    
    def __init__(self, config: GraphSimulationConfig):
        self.config = config
        
        # Scam node templates
        self.scammer_templates = {
            'gaming_scam': ['robux_free', 'game_hack', 'account_theft'],
            'phishing': ['password_steal', 'otp_theft', 'verify_account'],
            'gift_scam': ['free_gift', 'giveaway', 'prize_claim'],
            'malware': ['download_link', 'click_bait', 'virus_spread']
        }
    
    def inject_scam_nodes(self, G: nx.Graph) -> nx.Graph:
        """Tiêm scam node vào graph"""
        logger.info("🚨 Injecting scam nodes into network graph...")
        
        num_nodes_to_inject = int(G.number_of_nodes() * self.config.scam_injection_ratio)
        
        for i in range(num_nodes_to_inject):
            # Create scammer node
            scammer_id = f"scammer_{i:04d}"
            scam_type = random.choice(list(self.scammer_templates.keys()))
            scam_subtype = random.choice(self.scammer_templates[scam_type])
            
            G.add_node(scammer_id, 
                      node_type=NodeType.SCAMMER.value,
                      scam_type=scam_type,
                      scam_subtype=scam_subtype,
                      is_malicious=True)
            
            # Connect to existing nodes (simulate targeting)
            target_nodes = random.sample(list(G.nodes()), 
                                       min(10, G.number_of_nodes() - 1))
            
            for target_id in target_nodes:
                if G.nodes[target_id]['node_type'] == NodeType.USER.value:
                    # Mark as victim
                    G.nodes[target_id]['node_type'] = NodeType.VICTIM.value
                    
                    # Add scam relationship
                    G.add_edge(scammer_id, target_id,
                              relation_type=RelationType.SCAM_TARGETS.value,
                              weight=random.uniform(0.5, 1.0),
                              scam_probability=random.uniform(0.7, 1.0))
        
        logger.info(f"✅ Injected {num_nodes_to_inject} scam nodes")
        return G

class Neo4jGraphManager:
    """Quản lý Neo4j graph operations"""
    
    def __init__(self, config: GraphSimulationConfig):
        self.config = config
        self.driver = None
        self._init_neo4j()
    
    def _init_neo4j(self):
        """Initialize Neo4j connection"""
        try:
            self.driver = GraphDatabase.driver(
                self.config.neo4j_uri,
                auth=(self.config.neo4j_user, self.config.neo4j_password)
            )
            
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            
            logger.info("✅ Neo4j connection established")
            
        except Exception as e:
            logger.error(f"❌ Neo4j connection failed: {e}")
            raise
    
    def clear_database(self):
        """Clear existing database"""
        logger.info("🗑️ Clearing Neo4j database...")
        
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        
        logger.info("✅ Database cleared")
    
    def import_networkx_graph(self, G: nx.Graph):
        """Import NetworkX graph to Neo4j"""
        logger.info("📥 Importing graph to Neo4j...")
        
        with self.driver.session() as session:
            # Create nodes
            for node_id, node_data in G.nodes(data=True):
                node_type = node_data.get('node_type', NodeType.USER.value)
                
                # Prepare node properties
                properties = {
                    'id': node_id,
                    'node_type': node_type,
                    'created_at': datetime.utcnow().isoformat()
                }
                
                # Add scam-specific properties
                if node_type == NodeType.SCAMMER.value:
                    properties.update({
                        'scam_type': node_data.get('scam_type', 'unknown'),
                        'scam_subtype': node_data.get('scam_subtype', 'unknown'),
                        'is_malicious': node_data.get('is_malicious', True)
                    })
                
                # Create node with appropriate label
                label = node_type.upper()
                cypher = f"CREATE (n:{label} $properties)"
                session.run(cypher, properties=properties)
            
            # Create relationships
            for source, target, edge_data in G.edges(data=True):
                relation_type = edge_data.get('relation_type', 'INTERACTS_WITH')
                weight = edge_data.get('weight', 1.0)
                
                cypher = """
                MATCH (a), (b) 
                WHERE a.id = $source AND b.id = $target
                CREATE (a)-[r:RELATIONSHIP]->(b)
                SET r.type = $relation_type, r.weight = $weight, r.created_at = $timestamp
                """
                
                session.run(cypher, 
                          source=source, 
                          target=target,
                          relation_type=relation_type,
                          weight=weight,
                          timestamp=datetime.utcnow().isoformat())
        
        logger.info(f"✅ Imported {G.number_of_nodes()} nodes and {G.number_of_edges()} edges to Neo4j")
    
    def run_pagerank_analysis(self) -> List[Dict]:
        """Chạy PageRank algorithm để detect influential nodes"""
        logger.info("📊 Running PageRank analysis...")
        
        with self.driver.session() as session:
            # Run PageRank algorithm
            cypher = """
            CALL gds.pageRank.stream({
                nodeProjection: '*',
                relationshipProjection: '*'
            })
            YIELD nodeId, score
            RETURN gds.util.asNode(nodeId).id AS node_id, 
                   gds.util.asNode(nodeId).node_type AS node_type,
                   score
            ORDER BY score DESC
            LIMIT 100
            """
            
            result = session.run(cypher)
            pagerank_results = []
            
            for record in result:
                pagerank_results.append({
                    'node_id': record['node_id'],
                    'node_type': record['node_type'],
                    'pagerank_score': record['score']
                })
        
        logger.info(f"✅ PageRank analysis completed for {len(pagerank_results)} nodes")
        return pagerank_results
    
    def run_community_detection(self) -> List[Dict]:
        """Chạy Louvain algorithm để detect communities"""
        logger.info("👥 Running community detection...")
        
        with self.driver.session() as session:
            # Run Louvain algorithm
            cypher = """
            CALL gds.louvain.stream({
                nodeProjection: '*',
                relationshipProjection: '*'
            })
            YIELD nodeId, communityId
            RETURN gds.util.asNode(nodeId).id AS node_id,
                   gds.util.asNode(nodeId).node_type AS node_type,
                   communityId
            ORDER BY communityId
            """
            
            result = session.run(cypher)
            community_results = []
            
            for record in result:
                community_results.append({
                    'node_id': record['node_id'],
                    'node_type': record['node_type'],
                    'community_id': record['communityId']
                })
        
        logger.info(f"✅ Community detection completed for {len(community_results)} nodes")
        return community_results
    
    def detect_botnet_patterns(self, pagerank_results: List[Dict], 
                             community_results: List[Dict]) -> List[Dict]:
        """Phát hiện botnet patterns dựa trên PageRank và community analysis"""
        logger.info("🤖 Detecting botnet patterns...")
        
        # Analyze high PageRank nodes
        high_pagerank_nodes = [
            node for node in pagerank_results 
            if node['pagerank_score'] > self.config.pagerank_threshold
        ]
        
        # Analyze communities
        community_sizes = {}
        for node in community_results:
            comm_id = node['community_id']
            community_sizes[comm_id] = community_sizes.get(comm_id, 0) + 1
        
        # Find large communities (potential botnets)
        large_communities = [
            comm_id for comm_id, size in community_sizes.items()
            if size > self.config.community_size_threshold
        ]
        
        # Identify botnet patterns
        botnet_patterns = []
        
        for community_id in large_communities:
            community_nodes = [
                node for node in community_results 
                if node['community_id'] == community_id
            ]
            
            # Count node types in community
            scammer_count = sum(1 for node in community_nodes 
                              if node['node_type'] == NodeType.SCAMMER.value)
            victim_count = sum(1 for node in community_nodes 
                             if node['node_type'] == NodeType.VICTIM.value)
            total_count = len(community_nodes)
            
            # Botnet detection criteria
            scammer_ratio = scammer_count / total_count if total_count > 0 else 0
            victim_ratio = victim_count / total_count if total_count > 0 else 0
            
            if scammer_ratio > 0.1 or victim_ratio > 0.3:  # Threshold for botnet detection
                botnet_patterns.append({
                    'community_id': community_id,
                    'total_nodes': total_count,
                    'scammer_count': scammer_count,
                    'victim_count': victim_count,
                    'scammer_ratio': scammer_ratio,
                    'victim_ratio': victim_ratio,
                    'botnet_probability': max(scammer_ratio, victim_ratio),
                    'detection_timestamp': datetime.utcnow().isoformat()
                })
        
        logger.info(f"✅ Detected {len(botnet_patterns)} potential botnet patterns")
        return botnet_patterns
    
    def save_analysis_results(self, pagerank_results: List[Dict], 
                            community_results: List[Dict],
                            botnet_patterns: List[Dict]):
        """Lưu kết quả analysis vào MongoDB"""
        logger.info("💾 Saving analysis results to MongoDB...")
        
        try:
            client = MongoClient(self.config.mongo_uri)
            db = client[self.config.db_name]
            
            # Save PageRank results
            pagerank_collection = db.pagerank_analysis_collection
            pagerank_collection.insert_many(pagerank_results)
            
            # Save community results
            community_collection = db.community_analysis_collection
            community_collection.insert_many(community_results)
            
            # Save botnet patterns
            botnet_collection = db.botnet_detection_collection
            botnet_collection.insert_many(botnet_patterns)
            
            logger.info("✅ Analysis results saved to MongoDB")
            client.close()
            
        except Exception as e:
            logger.error(f"❌ Failed to save analysis results: {e}")
            raise
    
    def close(self):
        """Close Neo4j connection"""
        if self.driver:
            self.driver.close()
            logger.info("🔌 Neo4j connection closed")

class GraphSimulationEngine:
    """Main Graph Simulation Engine"""
    
    def __init__(self, config: GraphSimulationConfig):
        self.config = config
        self.voxpopuli_processor = VoxPopuliProcessor(config)
        self.scam_injector = ScamNodeInjector(config)
        self.neo4j_manager = Neo4jGraphManager(config)
    
    def run_complete_simulation(self):
        """Chạy complete graph simulation pipeline"""
        logger.info("🚀 Starting complete graph simulation pipeline...")
        
        try:
            # Step 1: Load VoxPopuli network structure
            network_data = self.voxpopuli_processor.load_voxpopuli_dataset()
            
            # Step 2: Build NetworkX graph
            G = self.voxpopuli_processor.build_network_graph(network_data)
            
            # Step 3: Inject scam nodes
            G = self.scam_injector.inject_scam_nodes(G)
            
            # Step 4: Clear and import to Neo4j
            self.neo4j_manager.clear_database()
            self.neo4j_manager.import_networkx_graph(G)
            
            # Step 5: Run graph analysis
            pagerank_results = self.neo4j_manager.run_pagerank_analysis()
            community_results = self.neo4j_manager.run_community_detection()
            
            # Step 6: Detect botnet patterns
            botnet_patterns = self.neo4j_manager.detect_botnet_patterns(
                pagerank_results, community_results
            )
            
            # Step 7: Save results
            self.neo4j_manager.save_analysis_results(
                pagerank_results, community_results, botnet_patterns
            )
            
            # Step 8: Generate report
            self._generate_simulation_report(
                G, pagerank_results, community_results, botnet_patterns
            )
            
            logger.info("🎉 Graph simulation completed successfully!")
            
        except Exception as e:
            logger.error(f"❌ Graph simulation failed: {e}")
            raise
        finally:
            self.neo4j_manager.close()
    
    def _generate_simulation_report(self, G: nx.Graph, 
                                  pagerank_results: List[Dict],
                                  community_results: List[Dict],
                                  botnet_patterns: List[Dict]):
        """Tạo báo cáo simulation results"""
        logger.info("📋 Generating simulation report...")
        
        report = {
            "simulation_summary": {
                "graph_nodes": G.number_of_nodes(),
                "graph_edges": G.number_of_edges(),
                "scam_nodes_injected": sum(1 for _, data in G.nodes(data=True) 
                                        if data.get('node_type') == NodeType.SCAMMER.value),
                "victim_nodes": sum(1 for _, data in G.nodes(data=True) 
                                  if data.get('node_type') == NodeType.VICTIM.value),
                "simulation_timestamp": datetime.now().isoformat(),
                "config": {
                    "scam_injection_ratio": self.config.scam_injection_ratio,
                    "pagerank_threshold": self.config.pagerank_threshold,
                    "community_size_threshold": self.config.community_size_threshold
                }
            },
            "pagerank_analysis": {
                "top_influential_nodes": pagerank_results[:10],
                "scammer_in_top_rank": sum(1 for node in pagerank_results[:50] 
                                         if node['node_type'] == NodeType.SCAMMER.value),
                "avg_pagerank_score": sum(node['pagerank_score'] for node in pagerank_results) / len(pagerank_results)
            },
            "community_analysis": {
                "total_communities": len(set(node['community_id'] for node in community_results)),
                "avg_community_size": len(community_results) / len(set(node['community_id'] for node in community_results)),
                "largest_community_size": max(
                    list(set(node['community_id'] for node in community_results)).count(comm_id)
                    for comm_id in set(node['community_id'] for node in community_results)
                )
            },
            "botnet_detection": {
                "potential_botnets": len(botnet_patterns),
                "high_confidence_botnets": len([b for b in botnet_patterns if b['botnet_probability'] > 0.7]),
                "botnet_patterns": botnet_patterns[:5]  # Top 5 patterns
            }
        }
        
        # Save report
        report_file = f"data/graph_simulation/simulation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"📋 Simulation report saved to: {report_file}")
        
        # Print summary
        logger.info("📊 SIMULATION SUMMARY:")
        logger.info(f"   Graph nodes: {report['simulation_summary']['graph_nodes']}")
        logger.info(f"   Scam nodes: {report['simulation_summary']['scam_nodes_injected']}")
        logger.info(f"   Botnets detected: {report['botnet_detection']['potential_botnets']}")
        logger.info(f"   High confidence botnets: {report['botnet_detection']['high_confidence_botnets']}")

def main():
    """Main execution function"""
    logger.info("🚀 Starting ViFake Graph Simulation Engine")
    logger.info("🎯 Purpose: Neo4j botnet detection using VoxPopuli network structure")
    logger.info("🔧 Technology: NetworkX + Neo4j Graph Algorithms")
    logger.info("🔒 Compliance: Network structure only - No personal content")
    
    # Initialize engine
    config = GraphSimulationConfig()
    engine = GraphSimulationEngine(config)
    
    try:
        # Run complete simulation
        engine.run_complete_simulation()
        
    except Exception as e:
        logger.error(f"❌ Graph simulation failed: {e}")
        raise

if __name__ == "__main__":
    main()
