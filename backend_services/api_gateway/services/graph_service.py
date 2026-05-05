#!/usr/bin/env python3
"""
Graph Service Integration for ViFake Analytics
Service layer for Neo4j graph analytics communication

Tuân thủ Privacy-by-Design:
- Zero-trust RAM processing
- Graph query optimization
- No persistent storage of harmful content
"""

import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, List, Optional, Union
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError
import aiohttp
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GraphServiceIntegration:
    """Integration layer for graph analytics services"""
    
    def __init__(self):
        # Neo4j configuration
        self.neo4j_uri = "bolt://localhost:7687"
        self.neo4j_user = "neo4j"
        self.neo4j_password = "password"
        self.driver = None
        
        # Graph analytics service URL
        self.graph_service_url = "http://localhost:8005"
        
        # Connection status
        self.neo4j_connected = False
        self.graph_service_connected = False
        
        logger.info("🕸️ Graph Service Integration initialized")
    
    async def connect_neo4j(self) -> bool:
        """Connect to Neo4j database"""
        try:
            self.driver = GraphDatabase.driver(
                self.neo4j_uri,
                auth=(self.neo4j_user, self.neo4j_password)
            )
            
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            
            self.neo4j_connected = True
            logger.info("✅ Neo4j connection established")
            return True
            
        except (ServiceUnavailable, AuthError) as e:
            logger.error(f"❌ Neo4j connection failed: {e}")
            self.neo4j_connected = False
            return False
    
    async def check_graph_service_health(self) -> bool:
        """Check graph analytics service health"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.graph_service_url}/health", timeout=5) as response:
                    self.graph_service_connected = response.status == 200
                    return self.graph_service_connected
        except Exception as e:
            logger.warning(f"⚠️ Graph service health check failed: {e}")
            self.graph_service_connected = False
            return False
    
    async def get_botnet_graph(self, post_id: str, depth: int = 2) -> Dict:
        """Query Neo4j for botnet network visualization"""
        logger.info(f"🕸️ Fetching botnet graph for post: {post_id} (depth: {depth})")
        
        try:
            # Check graph service health
            if not self.graph_service_connected:
                await self.check_graph_service_health()
            
            if self.graph_service_connected:
                # Use graph service
                return await self._get_graph_via_service(post_id, depth)
            else:
                # Direct Neo4j query
                return await self._get_graph_direct_neo4j(post_id, depth)
        
        except Exception as e:
            logger.error(f"❌ Botnet graph fetch failed: {e}")
            return self._fallback_botnet_graph(post_id)
    
    async def _get_graph_via_service(self, post_id: str, depth: int) -> Dict:
        """Get graph data via graph service"""
        async with aiohttp.ClientSession() as session:
            payload = {
                "post_id": post_id,
                "depth": depth,
                "include_suspicious": True
            }
            
            async with session.post(f"{self.graph_service_url}/botnet_graph", json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"✅ Botnet graph fetched via service: {len(result.get('nodes', []))} nodes")
                    return result
                else:
                    logger.error(f"❌ Graph service error: {response.status}")
                    return await self._get_graph_direct_neo4j(post_id, depth)
    
    async def _get_graph_direct_neo4j(self, post_id: str, depth: int) -> Dict:
        """Get graph data directly from Neo4j"""
        try:
            # Ensure Neo4j connection
            if not self.neo4j_connected:
                await self.connect_neo4j()
            
            if not self.neo4j_connected:
                logger.warning("⚠️ Neo4j unavailable, using fallback")
                return self._fallback_botnet_graph(post_id)
            
            with self.driver.session() as session:
                # Query for bot network around the post
                query = f"""
                MATCH (start:CONTENT {{post_id: $post_id}})
                OPTIONAL MATCH path = (start)-[r*1..{depth}]-(related)
                WHERE related:CONTENT OR related:USER OR related:SCAMMER
                WITH start, related, relationships(path) as rels
                RETURN start, related, rels
                LIMIT 100
                """
                
                result = session.run(query, post_id=post_id)
                
                nodes = []
                edges = []
                node_ids = set()
                
                for record in result:
                    start_node = record["start"]
                    related_node = record["related"]
                    relationships = record["rels"]
                    
                    # Add start node
                    start_id = start_node.element_id
                    if start_id not in node_ids:
                        nodes.append({
                            "id": start_id,
                            "labels": list(start_node.labels),
                            "properties": dict(start_node),
                            "type": "start"
                        })
                        node_ids.add(start_id)
                    
                    # Add related node
                    related_id = related_node.element_id
                    if related_id not in node_ids:
                        nodes.append({
                            "id": related_id,
                            "labels": list(related_node.labels),
                            "properties": dict(related_node),
                            "type": "related"
                        })
                        node_ids.add(related_id)
                    
                    # Add edges
                    for rel in relationships:
                        edges.append({
                            "source": rel.start_node.element_id,
                            "target": rel.end_node.element_id,
                            "type": rel.type,
                            "properties": dict(rel)
                        })
                
                graph_data = {
                    "nodes": nodes,
                    "edges": edges,
                    "metadata": {
                        "post_id": post_id,
                        "depth": depth,
                        "total_nodes": len(nodes),
                        "total_edges": len(edges),
                        "query_method": "direct_neo4j"
                    }
                }
                
                logger.info(f"✅ Botnet graph fetched directly: {len(nodes)} nodes, {len(edges)} edges")
                return graph_data
        
        except Exception as e:
            logger.error(f"❌ Direct Neo4j query failed: {e}")
            return self._fallback_botnet_graph(post_id)
    
    async def get_community_analysis(self, post_id: str) -> Dict:
        """Get community analysis for a post"""
        logger.info(f"👥 Getting community analysis for post: {post_id}")
        
        try:
            # Check graph service health
            if not self.graph_service_connected:
                await self.check_graph_service_health()
            
            if self.graph_service_connected:
                async with aiohttp.ClientSession() as session:
                    payload = {"post_id": post_id}
                    
                    async with session.post(f"{self.graph_service_url}/community_analysis", json=payload) as response:
                        if response.status == 200:
                            result = await response.json()
                            logger.info(f"✅ Community analysis completed: {len(result.get('communities', []))} communities")
                            return result
            
            # Fallback direct Neo4j query
            return await self._fallback_community_analysis(post_id)
        
        except Exception as e:
            logger.error(f"❌ Community analysis failed: {e}")
            return self._fallback_community_analysis(post_id)
    
    async def get_pagerank_scores(self, post_id: str, limit: int = 20) -> List[Dict]:
        """Get PageRank scores for nodes around a post"""
        logger.info(f"📊 Getting PageRank scores for post: {post_id}")
        
        try:
            # Check graph service health
            if not self.graph_service_connected:
                await self.check_graph_service_health()
            
            if self.graph_service_connected:
                async with aiohttp.ClientSession() as session:
                    payload = {"post_id": post_id, "limit": limit}
                    
                    async with session.post(f"{self.graph_service_url}/pagerank", json=payload) as response:
                        if response.status == 200:
                            result = await response.json()
                            scores = result.get("scores", [])
                            logger.info(f"✅ PageRank scores retrieved: {len(scores)} nodes")
                            return scores
            
            # Fallback
            return self._fallback_pagerank_scores(post_id, limit)
        
        except Exception as e:
            logger.error(f"❌ PageRank analysis failed: {e}")
            return self._fallback_pagerank_scores(post_id, limit)
    
    async def update_graph_with_analysis(self, post_id: str, analysis_result: Dict) -> bool:
        """Update Neo4j graph with analysis results"""
        logger.info(f"🔄 Updating graph with analysis for post: {post_id}")
        
        try:
            # Ensure Neo4j connection
            if not self.neo4j_connected:
                await self.connect_neo4j()
            
            if not self.neo4j_connected:
                logger.warning("⚠️ Neo4j unavailable for graph update")
                return False
            
            with self.driver.session() as session:
                # Update content node with analysis results
                query = """
                MATCH (c:CONTENT {post_id: $post_id})
                SET c.analysis_result = $analysis_result,
                    c.analysis_timestamp = $timestamp,
                    c.risk_level = $risk_level,
                    c.is_suspicious = $is_suspicious
                RETURN c
                """
                
                result = session.run(query, 
                    post_id=post_id,
                    analysis_result=analysis_result,
                    timestamp=datetime.now().isoformat(),
                    risk_level=analysis_result.get("risk_level", "UNKNOWN"),
                    is_suspicious=analysis_result.get("needs_review", False)
                )
                
                updated = result.single() is not None
                
                if updated:
                    logger.info(f"✅ Graph updated with analysis for post: {post_id}")
                else:
                    logger.warning(f"⚠️ Post not found in graph: {post_id}")
                
                return updated
        
        except Exception as e:
            logger.error(f"❌ Graph update failed: {e}")
            return False
    
    async def get_suspicious_patterns(self, hours: int = 24) -> List[Dict]:
        """Get suspicious patterns from recent activity"""
        logger.info(f"🔍 Getting suspicious patterns from last {hours} hours")
        
        try:
            # Ensure Neo4j connection
            if not self.neo4j_connected:
                await self.connect_neo4j()
            
            if not self.neo4j_connected:
                logger.warning("⚠️ Neo4j unavailable for pattern analysis")
                return []
            
            with self.driver.session() as session:
                # Query for suspicious patterns
                query = """
                MATCH (c:CONTENT)-[r:INTERACTS_WITH]-(u:USER)
                WHERE c.analysis_timestamp > datetime() - duration({hours: $hours})
                AND c.is_suspicious = true
                WITH u, count(c) as suspicious_count
                WHERE suspicious_count >= 3
                MATCH (u)-[r2:POSTS]->(c2:CONTENT)
                RETURN u.user_id as user_id, 
                       suspicious_count,
                       collect(c2.post_id) as suspicious_posts,
                       collect(c2.scam_type) as scam_types
                ORDER BY suspicious_count DESC
                LIMIT 50
                """
                
                result = session.run(query, hours=hours)
                
                patterns = []
                for record in result:
                    patterns.append({
                        "user_id": record["user_id"],
                        "suspicious_count": record["suspicious_count"],
                        "suspicious_posts": record["suspicious_posts"],
                        "scam_types": record["scam_types"],
                        "pattern_type": "high_risk_user"
                    })
                
                logger.info(f"✅ Found {len(patterns)} suspicious patterns")
                return patterns
        
        except Exception as e:
            logger.error(f"❌ Suspicious patterns query failed: {e}")
            return []
    
    def _fallback_botnet_graph(self, post_id: str) -> Dict:
        """Fallback botnet graph when services are unavailable"""
        logger.info("🔄 Using fallback botnet graph")
        
        # Generate mock graph data
        nodes = [
            {"id": post_id, "labels": ["CONTENT"], "properties": {"post_id": post_id}, "type": "start"},
            {"id": "user_1", "labels": ["USER"], "properties": {"user_id": "user_123"}, "type": "related"},
            {"id": "user_2", "labels": ["SCAMMER"], "properties": {"user_id": "scammer_456"}, "type": "related"}
        ]
        
        edges = [
            {"source": post_id, "target": "user_1", "type": "POSTED_BY", "properties": {}},
            {"source": post_id, "target": "user_2", "type": "INTERACTS_WITH", "properties": {}}
        ]
        
        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "post_id": post_id,
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "query_method": "fallback_mock"
            }
        }
    
    def _fallback_community_analysis(self, post_id: str) -> Dict:
        """Fallback community analysis"""
        logger.info("🔄 Using fallback community analysis")
        
        return {
            "post_id": post_id,
            "communities": [
                {
                    "id": "community_1",
                    "size": 5,
                    "members": ["user_1", "user_2", "user_3", "user_4", "user_5"],
                    "suspicious_ratio": 0.4
                }
            ],
            "analysis_method": "fallback_mock"
        }
    
    def _fallback_pagerank_scores(self, post_id: str, limit: int) -> List[Dict]:
        """Fallback PageRank scores"""
        logger.info("🔄 Using fallback PageRank scores")
        
        return [
            {"node_id": post_id, "score": 0.15, "type": "CONTENT"},
            {"node_id": "user_1", "score": 0.08, "type": "USER"},
            {"node_id": "user_2", "score": 0.12, "type": "SCAMMER"}
        ][:limit]
    
    async def get_service_status(self) -> Dict:
        """Get overall graph service status"""
        # Check Neo4j connection
        if not self.neo4j_connected:
            await self.connect_neo4j()
        
        # Check graph service
        await self.check_graph_service_health()
        
        return {
            "neo4j_connected": self.neo4j_connected,
            "graph_service_connected": self.graph_service_connected,
            "neo4j_uri": self.neo4j_uri,
            "graph_service_url": self.graph_service_url,
            "last_check": datetime.now().isoformat()
        }
    
    async def cleanup_old_graph_data(self, days_old: int = 30) -> Dict:
        """Clean up old graph data from Neo4j"""
        logger.info(f"🧹 Cleaning up graph data older than {days_old} days")
        
        try:
            # Ensure Neo4j connection
            if not self.neo4j_connected:
                await self.connect_neo4j()
            
            if not self.neo4j_connected:
                logger.error("❌ Cannot cleanup: Neo4j unavailable")
                return {"success": False, "reason": "Neo4j unavailable"}
            
            with self.driver.session() as session:
                cutoff_date = datetime.now() - timedelta(days=days_old)
                
                # Delete old content nodes
                content_query = """
                MATCH (c:CONTENT)
                WHERE c.created_at < $cutoff_date
                AND c.analysis_status = 'completed'
                DETACH DELETE c
                RETURN count(c) as deleted_count
                """
                
                result = session.run(content_query, cutoff_date=cutoff_date.isoformat())
                deleted_count = result.single()["deleted_count"]
                
                cleanup_result = {
                    "success": True,
                    "cutoff_date": cutoff_date.isoformat(),
                    "nodes_deleted": deleted_count,
                    "cleanup_method": "neo4j_direct"
                }
                
                logger.info(f"✅ Graph cleanup completed: {deleted_count} nodes deleted")
                return cleanup_result
        
        except Exception as e:
            logger.error(f"❌ Graph cleanup failed: {e}")
            return {"success": False, "reason": str(e)}

# Global service instance
_graph_service = None

def get_graph_service() -> GraphServiceIntegration:
    """Get singleton graph service instance"""
    global _graph_service
    if _graph_service is None:
        _graph_service = GraphServiceIntegration()
    return _graph_service

# Convenience functions
async def get_botnet_network(post_id: str, depth: int = 2) -> Dict:
    """Get botnet network visualization"""
    service = get_graph_service()
    return await service.get_botnet_graph(post_id, depth)

async def analyze_communities(post_id: str) -> Dict:
    """Analyze communities around a post"""
    service = get_graph_service()
    return await service.get_community_analysis(post_id)

async def get_node_importance(post_id: str, limit: int = 20) -> List[Dict]:
    """Get PageRank importance scores"""
    service = get_graph_service()
    return await service.get_pagerank_scores(post_id, limit)

async def update_graph_with_result(post_id: str, result: Dict) -> bool:
    """Update graph with analysis results"""
    service = get_graph_service()
    return await service.update_graph_with_analysis(post_id, result)

if __name__ == "__main__":
    # Test graph service integration
    async def test_graph_service():
        service = get_graph_service()
        
        # Test Neo4j connection
        neo4j_ok = await service.connect_neo4j()
        print(f"Neo4j connected: {neo4j_ok}")
        
        # Test graph service health
        service_ok = await service.check_graph_service_health()
        print(f"Graph service healthy: {service_ok}")
        
        # Test botnet graph
        graph_data = await service.get_botnet_graph("test_post_123")
        print(f"Botnet graph: {len(graph_data.get('nodes', []))} nodes")
        
        # Test community analysis
        community_data = await service.get_community_analysis("test_post_123")
        print(f"Community analysis: {len(community_data.get('communities', []))} communities")
        
        # Get service status
        status = await service.get_service_status()
        print(f"Service status: {status}")
    
    # Run test
    asyncio.run(test_graph_service())
