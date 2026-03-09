"""
Graph Builder - Build candidate-job graphs using NetworkX.
"""
import logging
from typing import Dict, List, Optional
from pathlib import Path
import json

try:
    import networkx as nx
except ImportError:
    raise ImportError("NetworkX is required. Install with: pip install networkx")

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Build and analyze candidate-job relationship graphs using NetworkX."""
    
    def __init__(self, jobs_file: str = None):
        """
        Initialize the graph builder.
        
        Args:
            jobs_file: Path to jobs JSON file
        """
        if jobs_file is None:
            base_dir = Path(__file__).parent.parent
            jobs_file = base_dir / "data" / "jobs.json"
        
        self.jobs_file = jobs_file
        self.jobs_data = []
        self._load_jobs()
        
    def _load_jobs(self):
        """Load jobs from the database file."""
        try:
            with open(self.jobs_file, 'r') as f:
                self.jobs_data = json.load(f)
            
            if isinstance(self.jobs_data, dict):
                self.jobs_data = self.jobs_data.get('jobs', self.jobs_data.get('job_roles', []))
            elif not isinstance(self.jobs_data, list):
                self.jobs_data = []
            
            logger.info(f"Loaded {len(self.jobs_data)} job profiles for graph building")
            
        except FileNotFoundError:
            logger.error(f"Jobs file not found: {self.jobs_file}")
            self.jobs_data = []
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing jobs JSON: {e}")
            self.jobs_data = []
    
    def build_candidate_graph(self, candidate_name: str, job_matches: List[Dict],
                             similarity_threshold: float = 0.3) -> nx.Graph:
        """
        Build a graph connecting candidate to jobs based on similarity.
        
        Args:
            candidate_name: Name of the candidate
            job_matches: List of job match results with similarity scores
            similarity_threshold: Minimum similarity to create an edge
            
        Returns:
            NetworkX graph object
        """
        graph = nx.Graph()
        
        # Add candidate node
        graph.add_node(candidate_name, node_type='candidate')
        
        # Add job nodes and edges
        for job_match in job_matches:
            role = job_match.get('role', 'Unknown')
            similarity = job_match.get('similarity_score', 0)
            
            # Add job node
            graph.add_node(role, node_type='job')
            
            # Add edge if above threshold
            if similarity >= similarity_threshold:
                graph.add_edge(
                    candidate_name, 
                    role, 
                    weight=similarity,
                    matched_skills=job_match.get('matched_skills', []),
                    missing_skills=job_match.get('missing_skills', [])
                )
        
        logger.info(f"Built graph with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges")
        return graph
    
    def build_skill_graph(self, candidate_skills: List[str], 
                         job_matches: List[Dict]) -> nx.Graph:
        """
        Build a more detailed skill-based graph.
        
        Args:
            candidate_skills: List of candidate's skills
            job_matches: List of job match results
            
        Returns:
            NetworkX graph with candidate, skills, and jobs
        """
        graph = nx.Graph()
        
        candidate_name = "Candidate"
        
        # Add candidate node
        graph.add_node(candidate_name, node_type='candidate')
        
        # Add skill nodes and connect to candidate
        for skill in candidate_skills:
            skill_node = f"skill_{skill}"
            graph.add_node(skill_node, node_type='skill', skill_name=skill)
            graph.add_edge(candidate_name, skill_node, edge_type='has_skill')
        
        # Add job nodes and connect via matched/missing skills
        for job_match in job_matches:
            role = job_match.get('role', 'Unknown')
            job_node = f"job_{role}"
            graph.add_node(job_node, node_type='job', role=role)
            
            # Connect matched skills to job
            for skill in job_match.get('matched_skills', []):
                skill_node = f"skill_{skill}"
                if skill_node in graph:
                    graph.add_edge(skill_node, job_node, edge_type='matched_to', weight=1.0)
            
            # Connect missing skills to job
            for skill in job_match.get('missing_skills', []):
                skill_node = f"skill_{skill}"
                if skill_node in graph:
                    graph.add_edge(skill_node, job_node, edge_type='missing_from', weight=0.5)
        
        return graph
    
    def build_learning_graph(self, skill_gaps: List[str], 
                            learning_resources: Dict) -> nx.Graph:
        """
        Build a learning recommendation graph.
        
        Args:
            skill_gaps: List of missing skills
            learning_resources: Dictionary of learning resources by skill
            
        Returns:
            NetworkX graph connecting skills to learning resources
        """
        graph = nx.Graph()
        
        # Add skill nodes
        for skill in skill_gaps:
            graph.add_node(skill, node_type='skill_gap')
        
        # Add learning resource nodes and connect to skills
        for skill, resources in learning_resources.items():
            skill_node = skill
            if skill_node not in graph:
                graph.add_node(skill_node, node_type='skill_gap')
            
            for resource in resources:
                resource_node = f"resource_{resource.get('title', 'Unknown')}"
                graph.add_node(resource_node, node_type='resource', 
                             title=resource.get('title'),
                             url=resource.get('url'),
                             difficulty=resource.get('difficulty'))
                graph.add_edge(skill_node, resource_node, edge_type='recommends')
        
        return graph
    
    def get_graph_data(self, graph: nx.Graph) -> Dict:
        """
        Extract graph data for visualization.
        
        Args:
            graph: NetworkX graph
            
        Returns:
            Dictionary with nodes and edges for visualization
        """
        data = {
            'nodes': [],
            'edges': []
        }
        
        # Get nodes
        for node, attrs in graph.nodes(data=True):
            node_data = {
                'id': node,
                'type': attrs.get('node_type', 'unknown'),
                'label': node
            }
            
            # Add additional attributes based on type
            if attrs.get('node_type') == 'skill':
                node_data['skill'] = attrs.get('skill_name', node)
            elif attrs.get('node_type') == 'job':
                node_data['role'] = attrs.get('role', node)
            elif attrs.get('node_type') == 'resource':
                node_data['title'] = attrs.get('title', node)
                node_data['url'] = attrs.get('url', '')
            
            data['nodes'].append(node_data)
        
        # Get edges
        for source, target, attrs in graph.edges(data=True):
            edge_data = {
                'source': source,
                'target': target,
                'type': attrs.get('edge_type', 'connected'),
                'weight': attrs.get('weight', 1.0)
            }
            data['edges'].append(edge_data)
        
        # Add graph metadata
        data['metadata'] = {
            'total_nodes': graph.number_of_nodes(),
            'total_edges': graph.number_of_edges(),
            'is_connected': nx.is_connected(graph) if graph.number_of_nodes() > 1 else True,
            'density': nx.density(graph) if graph.number_of_nodes() > 1 else 0
        }
        
        return data
    
    def get_path_analysis(self, graph: nx.Graph, source: str, target: str) -> List:
        """
        Find shortest path between two nodes.
        
        Args:
            graph: NetworkX graph
            source: Source node
            target: Target node
            
        Returns:
            List of nodes in the path
        """
        try:
            if source in graph and target in graph:
                return nx.shortest_path(graph, source, target)
        except nx.NetworkXNoPath:
            logger.warning(f"No path found between {source} and {target}")
        
        return []
    
    def rank_candidates_by_graph_centrality(self, candidates: List[Dict]) -> List[Dict]:
        """
        Rank candidates using graph centrality measures.
        
        Args:
            candidates: List of candidate job match results
            
        Returns:
            Ranked list of candidates
        """
        ranked = []
        
        for candidate in candidates:
            job_matches = candidate.get('job_matches', [])
            
            if not job_matches:
                continue
            
            # Build temporary graph for this candidate
            graph = self.build_candidate_graph(
                candidate.get('name', 'Unknown'),
                job_matches
            )
            
            # Calculate centrality
            degree_centrality = nx.degree_centrality(graph)
            betweenness_centrality = nx.betweenness_centrality(graph)
            
            candidate['degree_centrality'] = degree_centrality.get(candidate.get('name'), 0)
            candidate['betweenness_centrality'] = betweenness_centrality.get(candidate.get('name'), 0)
            
            # Composite score
            candidate['graph_score'] = (
                candidate['degree_centrality'] * 0.5 + 
                candidate['betweenness_centrality'] * 0.5
            )
            
            ranked.append(candidate)
        
        # Sort by graph score
        ranked.sort(key=lambda x: x.get('graph_score', 0), reverse=True)
        
        return ranked


def build_resume_job_graph(candidate_name: str, job_matches: List[Dict],
                           similarity_threshold: float = 0.3) -> nx.Graph:
    """
    Standalone function to build candidate-job graph.
    
    Args:
        candidate_name: Name of candidate
        job_matches: Job match results
        similarity_threshold: Minimum similarity for edge
        
    Returns:
        NetworkX graph
    """
    builder = GraphBuilder()
    return builder.build_candidate_graph(candidate_name, job_matches, similarity_threshold)


if __name__ == "__main__":
    # Test the graph builder
    print("Testing Graph Builder...")
    
    builder = GraphBuilder()
    
    # Test job matches
    test_job_matches = [
        {
            'role': 'Data Scientist',
            'similarity_score': 0.85,
            'matched_skills': ['python', 'machine learning', 'sql'],
            'missing_skills': ['tensorflow', 'pytorch']
        },
        {
            'role': 'Machine Learning Engineer',
            'similarity_score': 0.72,
            'matched_skills': ['python', 'machine learning'],
            'missing_skills': ['docker', 'kubernetes']
        },
        {
            'role': 'Backend Developer',
            'similarity_score': 0.45,
            'matched_skills': ['python', 'sql'],
            'missing_skills': ['django', 'docker']
        }
    ]
    
    test_skills = ['python', 'machine learning', 'sql', 'tensorflow']
    
    # Build candidate graph
    graph = builder.build_candidate_graph("John Doe", test_job_matches, 0.3)
    print(f"\nCandidate Graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")
    
    # Get graph data for visualization
    graph_data = builder.get_graph_data(graph)
    print(f"Graph metadata: {graph_data['metadata']}")
    
    # Build skill graph
    skill_graph = builder.build_skill_graph(test_skills, test_job_matches)
    print(f"\nSkill Graph: {skill_graph.number_of_nodes()} nodes, {skill_graph.number_of_edges()} edges")

