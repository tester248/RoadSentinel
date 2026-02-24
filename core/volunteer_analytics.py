"""Volunteer and incident management analytics for RoadSentinel."""

import logging
from typing import Dict, List, Optional, Tuple
from collections import Counter
import pandas as pd

logger = logging.getLogger(__name__)


class VolunteerAnalytics:
    """Analytics for volunteer management and incident assignment."""
    
    def __init__(self, supabase_client):
        """
        Initialize volunteer analytics.
        
        Args:
            supabase_client: Supabase client instance
        """
        self.client = supabase_client
    
    def get_incidents_summary(self) -> Dict:
        """
        Get comprehensive summary of incidents.
        
        Returns:
            Dictionary with incident statistics
        """
        try:
            # Fetch all incidents
            response = self.client.table('incidents').select('*').execute()
            incidents = response.data if response.data else []
            
            if not incidents:
                return {
                    'total': 0,
                    'by_status': {},
                    'by_priority': {},
                    'unassigned': 0,
                    'partially_assigned': 0,
                    'fully_assigned': 0,
                    'total_assignments': 0
                }
            
            # Count by status
            status_counts = Counter(inc.get('status', 'unknown') for inc in incidents)
            
            # Count by priority
            priority_counts = Counter(inc.get('priority', 'unknown') for inc in incidents)
            
            # Assignment statistics
            unassigned = sum(1 for inc in incidents if inc.get('status') == 'unassigned')
            partially_assigned = sum(1 for inc in incidents if inc.get('status') == 'partially_assigned')
            fully_assigned = sum(1 for inc in incidents if inc.get('status') in ['assigned', 'resolved'])
            
            # Total volunteer assignments
            total_assignments = sum(inc.get('assigned_count', 0) for inc in incidents)
            
            return {
                'total': len(incidents),
                'by_status': dict(status_counts),
                'by_priority': dict(priority_counts),
                'unassigned': unassigned,
                'partially_assigned': partially_assigned,
                'fully_assigned': fully_assigned,
                'total_assignments': total_assignments,
                'incidents': incidents
            }
            
        except Exception as e:
            logger.error(f"Failed to get incidents summary: {e}")
            return {
                'total': 0,
                'by_status': {},
                'by_priority': {},
                'unassigned': 0,
                'partially_assigned': 0,
                'fully_assigned': 0,
                'total_assignments': 0
            }
    
    def get_skills_analysis(self) -> Dict:
        """
        Analyze skills demand vs availability.
        
        Returns:
            Dictionary with skills analysis
        """
        try:
            # Get incidents with required skills
            incidents_response = self.client.table('incidents').select('required_skills, status, priority').execute()
            incidents = incidents_response.data if incidents_response.data else []
            
            # Get available skills from skills table
            skills_response = self.client.table('skills').select('*').execute()
            available_skills = skills_response.data if skills_response.data else []
            
            # Get user skills from users table
            users_response = self.client.table('users').select('skills').execute()
            users = users_response.data if users_response.data else []
            
            # Count required skills (only for unassigned and partially assigned incidents)
            required_skills_counter = Counter()
            for incident in incidents:
                if incident.get('status') in ['unassigned', 'partially_assigned']:
                    skills = incident.get('required_skills', [])
                    if skills:
                        required_skills_counter.update(skills)
            
            # Count available skills from users
            available_skills_counter = Counter()
            for user in users:
                skills = user.get('skills', [])
                if skills:
                    available_skills_counter.update(skills)
            
            # Calculate gaps
            all_skills = set(required_skills_counter.keys()) | set(available_skills_counter.keys())
            skills_gap = {}
            
            for skill in all_skills:
                required = required_skills_counter.get(skill, 0)
                available = available_skills_counter.get(skill, 0)
                gap = required - available
                skills_gap[skill] = {
                    'required': required,
                    'available': available,
                    'gap': gap,
                    'shortage': gap > 0
                }
            
            return {
                'total_users': len(users),
                'total_unique_skills': len(all_skills),
                'skills_gap': skills_gap,
                'most_needed_skills': required_skills_counter.most_common(10),
                'most_available_skills': available_skills_counter.most_common(10)
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze skills: {e}")
            return {
                'total_users': 0,
                'total_unique_skills': 0,
                'skills_gap': {},
                'most_needed_skills': [],
                'most_available_skills': []
            }
    
    def get_volunteer_engagement(self) -> Dict:
        """
        Get volunteer engagement statistics.
        
        Returns:
            Dictionary with engagement metrics
        """
        try:
            # Get volunteer history
            history_response = self.client.table('volunteer_history').select('*').execute()
            history = history_response.data if history_response.data else []
            
            # Get users
            users_response = self.client.table('users').select('*').execute()
            users = users_response.data if users_response.data else []
            
            # Get current assignments
            incidents_response = self.client.table('incidents').select('assigned_to, status').execute()
            incidents = incidents_response.data if incidents_response.data else []
            
            # Calculate active volunteers (those currently assigned)
            active_volunteers = set()
            for incident in incidents:
                assigned = incident.get('assigned_to', [])
                if assigned and incident.get('status') not in ['resolved', 'cancelled']:
                    active_volunteers.update(assigned)
            
            # Calculate volunteers by activity level
            volunteer_assignments = Counter()
            for incident in incidents:
                assigned = incident.get('assigned_to', [])
                if assigned:
                    for vol_id in assigned:
                        volunteer_assignments[vol_id] += 1
            
            # Top volunteers
            top_volunteers = volunteer_assignments.most_common(10)
            
            # Average assignments per volunteer
            avg_assignments = (len(volunteer_assignments) and 
                             sum(volunteer_assignments.values()) / len(volunteer_assignments)) or 0
            
            return {
                'total_users': len(users),
                'active_volunteers': len(active_volunteers),
                'inactive_volunteers': len(users) - len(active_volunteers),
                'top_volunteers': top_volunteers,
                'avg_assignments_per_volunteer': round(avg_assignments, 2),
                'volunteer_assignments': dict(volunteer_assignments)
            }
            
        except Exception as e:
            logger.error(f"Failed to get volunteer engagement: {e}")
            return {
                'total_users': 0,
                'active_volunteers': 0,
                'inactive_volunteers': 0,
                'top_volunteers': [],
                'avg_assignments_per_volunteer': 0,
                'volunteer_assignments': {}
            }
    
    def get_priority_distribution(self) -> Dict:
        """
        Get distribution of incidents by priority and assignment status.
        
        Returns:
            Dictionary with priority distribution
        """
        try:
            incidents_response = self.client.table('incidents').select('priority, status, assigned_count').execute()
            incidents = incidents_response.data if incidents_response.data else []
            
            distribution = {}
            for priority in ['critical', 'high', 'medium', 'low']:
                priority_incidents = [i for i in incidents if i.get('priority') == priority]
                
                distribution[priority] = {
                    'total': len(priority_incidents),
                    'unassigned': sum(1 for i in priority_incidents if i.get('status') == 'unassigned'),
                    'partially_assigned': sum(1 for i in priority_incidents if i.get('status') == 'partially_assigned'),
                    'fully_assigned': sum(1 for i in priority_incidents if i.get('status') not in ['unassigned', 'partially_assigned']),
                    'total_volunteers': sum(i.get('assigned_count', 0) for i in priority_incidents)
                }
            
            return distribution
            
        except Exception as e:
            logger.error(f"Failed to get priority distribution: {e}")
            return {}
    
    def get_skill_matching_recommendations(self, max_recommendations: int = 20) -> List[Dict]:
        """
        Get recommendations for matching volunteers to incidents based on skills.
        
        Args:
            max_recommendations: Maximum number of recommendations to return
        
        Returns:
            List of recommendations with incident and volunteer matches
        """
        try:
            # Get unassigned incidents
            incidents_response = self.client.table('incidents').select('*').execute()
            incidents = [i for i in (incidents_response.data or []) 
                        if i.get('status') in ['unassigned', 'partially_assigned']]
            
            # Get users with their skills
            users_response = self.client.table('users').select('id, name, skills').execute()
            users = users_response.data or []
            
            recommendations = []
            
            for incident in incidents[:max_recommendations]:
                required_skills = set(incident.get('required_skills', []))
                priority = incident.get('priority', 'medium')
                
                if not required_skills:
                    continue
                
                # Find users with matching skills
                matching_users = []
                for user in users:
                    user_skills = set(user.get('skills', []))
                    matching_skills = required_skills & user_skills
                    
                    if matching_skills:
                        match_percentage = len(matching_skills) / len(required_skills) * 100
                        matching_users.append({
                            'user_id': user['id'],
                            'user_name': user.get('name', 'Unknown'),
                            'matching_skills': list(matching_skills),
                            'match_percentage': round(match_percentage, 1)
                        })
                
                # Sort by match percentage
                matching_users.sort(key=lambda x: x['match_percentage'], reverse=True)
                
                if matching_users:
                    recommendations.append({
                        'incident_id': incident['id'],
                        'incident_title': incident.get('title', 'Untitled'),
                        'priority': priority,
                        'required_skills': list(required_skills),
                        'matching_volunteers': matching_users[:5],  # Top 5 matches
                        'best_match_percentage': matching_users[0]['match_percentage']
                    })
            
            # Sort recommendations by priority and match quality
            priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
            recommendations.sort(key=lambda x: (
                priority_order.get(x['priority'], 4),
                -x['best_match_percentage']
            ))
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Failed to get skill matching recommendations: {e}")
            return []
    
    def get_incident_details_by_priority(self) -> pd.DataFrame:
        """
        Get detailed incident information grouped by priority.
        
        Returns:
            DataFrame with incident details
        """
        try:
            incidents_response = self.client.table('incidents').select('*').execute()
            incidents = incidents_response.data if incidents_response.data else []
            
            if not incidents:
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(incidents)
            
            # Select relevant columns
            columns = ['id', 'title', 'priority', 'status', 'assigned_count', 
                      'required_skills', 'actions_needed', 'estimated_volunteers', 'created_at']
            
            # Keep only columns that exist
            columns = [col for col in columns if col in df.columns]
            df_filtered = df[columns]
            
            return df_filtered
            
        except Exception as e:
            logger.error(f"Failed to get incident details: {e}")
            return pd.DataFrame()
