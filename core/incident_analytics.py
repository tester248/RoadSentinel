"""Incident Analytics Module for High-Risk Location Identification."""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import numpy as np
from sklearn.cluster import DBSCAN


class IncidentAnalytics:
    """Analyze incident patterns to identify high-risk locations."""
    
    def analyze_incident_distribution(self, incident_data: Dict) -> Dict:
        """
        Analyze incident distribution across categories, sources, and priorities.
        
        Args:
            incident_data: Dictionary of categorized incidents
            
        Returns:
            Dictionary with distribution statistics
        """
        stats = {
            'total': 0,
            'by_category': {},
            'by_source': {},
            'by_priority': {},
            'mobile_app_count': 0,
            'news_count': 0,
            'official_count': 0
        }
        
        for category, incidents in incident_data.items():
            stats['by_category'][category] = len(incidents)
            stats['total'] += len(incidents)
            
            for incident in incidents:
                # Count by source
                source = incident.get('source', 'unknown')
                if source == 'mobile_upload':
                    stats['mobile_app_count'] += 1
                    stats['by_source']['Mobile App'] = stats['by_source'].get('Mobile App', 0) + 1
                elif source == 'tomtom':
                    stats['official_count'] += 1
                    stats['by_source']['TomTom Official'] = stats['by_source'].get('TomTom Official', 0) + 1
                elif source == 'news_scraper' or (isinstance(source, str) and source.startswith('http')):
                    # Recognize news_scraper as well as URL-based sources
                    stats['news_count'] += 1
                    stats['by_source']['News Sources'] = stats['by_source'].get('News Sources', 0) + 1
                else:
                    stats['by_source'][source] = stats['by_source'].get(source, 0) + 1
                
                # Count by priority/severity
                priority = incident.get('priority', incident.get('severity', 'medium'))
                if isinstance(priority, int):
                    # Convert severity (1-5) to priority labels
                    priority_map = {1: 'low', 2: 'low', 3: 'medium', 4: 'high', 5: 'critical'}
                    priority = priority_map.get(priority, 'medium')
                
                stats['by_priority'][str(priority).lower()] = stats['by_priority'].get(str(priority).lower(), 0) + 1
        
        return stats
    
    def identify_high_risk_clusters(self, incident_data: Dict, eps_km: float = 0.5, min_samples: int = 2) -> List[Dict]:
        """
        Use DBSCAN clustering to identify high-risk zones with multiple incidents.
        
        Args:
            incident_data: Dictionary of categorized incidents
            eps_km: Maximum distance between incidents in a cluster (in km)
            min_samples: Minimum number of incidents to form a cluster
            
        Returns:
            List of cluster dictionaries with location, count, and risk factors
        """
        # Collect all incident locations
        locations = []
        incident_details = []
        
        for category, incidents in incident_data.items():
            for incident in incidents:
                coords = incident.get('coordinates', [])
                if coords and len(coords) >= 2:
                    if isinstance(coords[0], list):
                        lat, lon = coords[0][1], coords[0][0]
                    else:
                        lat, lon = coords[1], coords[0]
                    
                    locations.append([lat, lon])
                    incident_details.append({
                        'category': category,
                        'lat': lat,
                        'lon': lon,
                        'source': incident.get('source', 'unknown'),
                        'priority': incident.get('priority', 'medium'),
                        'description': incident.get('description', '')[:100]
                    })
        
        if len(locations) < min_samples:
            return []
        
        # Convert to numpy array
        coords_array = np.array(locations)
        
        # DBSCAN clustering (eps in degrees, roughly 0.01 degree ≈ 1 km at equator)
        # For better accuracy, we convert km to degrees
        eps_degrees = eps_km / 111.0  # 1 degree ≈ 111 km
        
        clustering = DBSCAN(eps=eps_degrees, min_samples=min_samples).fit(coords_array)
        labels = clustering.labels_
        
        # Analyze clusters
        clusters = []
        unique_labels = set(labels)
        
        for label in unique_labels:
            if label == -1:  # Noise points
                continue
            
            # Get incidents in this cluster
            cluster_mask = labels == label
            cluster_incidents = [incident_details[i] for i in range(len(incident_details)) if cluster_mask[i]]
            cluster_coords = coords_array[cluster_mask]
            
            # Calculate center
            center_lat = np.mean(cluster_coords[:, 0])
            center_lon = np.mean(cluster_coords[:, 1])
            
            # Analyze cluster
            categories = {}
            sources = {}
            priorities = {}
            
            for inc in cluster_incidents:
                categories[inc['category']] = categories.get(inc['category'], 0) + 1
                sources[inc['source']] = sources.get(inc['source'], 0) + 1
                priorities[inc['priority']] = priorities.get(inc['priority'], 0) + 1
            
            clusters.append({
                'cluster_id': int(label),
                'center': {'lat': center_lat, 'lon': center_lon},
                'incident_count': len(cluster_incidents),
                'categories': categories,
                'sources': sources,
                'priorities': priorities,
                'incidents': cluster_incidents,
                'risk_level': self._calculate_cluster_risk(cluster_incidents)
            })
        
        # Sort by incident count
        clusters.sort(key=lambda x: x['incident_count'], reverse=True)
        
        return clusters
    
    def _calculate_cluster_risk(self, incidents: List[Dict]) -> str:
        """Calculate risk level for a cluster based on incident count and priorities."""
        count = len(incidents)
        
        # Count high-priority incidents
        high_priority_count = sum(1 for inc in incidents if inc['priority'] in ['high', 'critical'])
        
        if count >= 5 or high_priority_count >= 3:
            return 'critical'
        elif count >= 3 or high_priority_count >= 2:
            return 'high'
        elif count >= 2:
            return 'medium'
        else:
            return 'low'
    
    def get_incident_heatmap_data(self, incident_data: Dict) -> List[Tuple[float, float, float]]:
        """
        Prepare incident data for heatmap visualization.
        
        Args:
            incident_data: Dictionary of categorized incidents
            
        Returns:
            List of [latitude, longitude, weight] tuples
        """
        heatmap_data = []
        
        for category, incidents in incident_data.items():
            for incident in incidents:
                coords = incident.get('coordinates', [])
                if coords and len(coords) >= 2:
                    if isinstance(coords[0], list):
                        lat, lon = coords[0][1], coords[0][0]
                    else:
                        lat, lon = coords[1], coords[0]
                    
                    # Weight by priority/severity
                    priority = incident.get('priority', incident.get('severity', 3))
                    if isinstance(priority, str):
                        priority_map = {'low': 2, 'medium': 3, 'high': 4, 'critical': 5}
                        weight = priority_map.get(priority.lower(), 3)
                    else:
                        weight = priority
                    
                    heatmap_data.append([lat, lon, weight])
        
        return heatmap_data
    
    def create_incident_timeline(self, raw_incidents: List[Dict], hours_back: int = 72) -> pd.DataFrame:
        """
        Create timeline data for incident trends.
        
        Args:
            raw_incidents: List of raw incident dictionaries from Supabase
            hours_back: How many hours back to analyze
            
        Returns:
            DataFrame with time-series data
        """
        if not raw_incidents:
            return pd.DataFrame()
        
        timeline_data = []
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        for incident in raw_incidents:
            created_at = incident.get('created_at')
            if not created_at:
                continue
            
            # Parse timestamp
            if isinstance(created_at, str):
                try:
                    created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                except:
                    continue
            else:
                created_dt = created_at
            
            if created_dt < cutoff_time:
                continue
            
            timeline_data.append({
                'timestamp': created_dt,
                'reason': incident.get('reason', 'unknown'),
                'priority': incident.get('priority', 'medium'),
                'source': incident.get('source', 'unknown')
            })
        
        if not timeline_data:
            return pd.DataFrame()
        
        df = pd.DataFrame(timeline_data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        
        return df
