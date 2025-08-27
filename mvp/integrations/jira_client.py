"""Jira integration client for the Intelligent PR Assistant."""

import asyncio
import re
from typing import Dict, List, Optional, Any
import logging

import aiohttp
from requests_oauthlib import OAuth2Session

from config.config import config

logger = logging.getLogger(__name__)


class JiraTicket:
    """Data model for Jira ticket information."""
    
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get('id')
        self.key = data.get('key')
        self.summary = data.get('fields', {}).get('summary', '')
        self.description = data.get('fields', {}).get('description', '')
        self.status = data.get('fields', {}).get('status', {}).get('name', '')
        self.issue_type = data.get('fields', {}).get('issuetype', {}).get('name', '')
        self.priority = data.get('fields', {}).get('priority', {}).get('name', '')
        self.assignee = data.get('fields', {}).get('assignee', {}).get('displayName', '')
        self.reporter = data.get('fields', {}).get('reporter', {}).get('displayName', '')
        self.created = data.get('fields', {}).get('created', '')
        self.updated = data.get('fields', {}).get('updated', '')
        self.labels = data.get('fields', {}).get('labels', [])
        self.components = [comp.get('name', '') for comp in data.get('fields', {}).get('components', [])]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'ticket_id': self.key,
            'ticket_status': self.status,
            'ticket_type': self.issue_type,
            'priority': self.priority,
            'summary': self.summary,
            'assignee': self.assignee,
            'labels': self.labels,
            'components': self.components
        }


class JiraClient:
    """Async Jira API client with OAuth 2.0 authentication."""
    
    def __init__(self):
        """Initialize Jira client with configuration."""
        self.base_url = config.atlassian.jira_base_url
        self.api_version = config.atlassian.jira_api_version
        self.api_url = f"{self.base_url}/rest/api/{self.api_version}"
        
        # OAuth configuration
        self.oauth_client_id = config.atlassian.oauth_client_id
        self.oauth_client_secret = config.atlassian.oauth_client_secret
        self.oauth_scopes = config.atlassian.oauth_scopes
        
        # Session management
        self._session: Optional[aiohttp.ClientSession] = None
        self._access_token: Optional[str] = None
        
        # Ticket key patterns
        self.ticket_patterns = [
            r'[A-Z]+-\d+',  # Standard Jira ticket format (e.g., PROJ-123)
            r'#[A-Z]+-\d+',  # With hash prefix
            r'\b[A-Z]{2,10}-\d{1,6}\b'  # More specific pattern
        ]
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def _ensure_session(self):
        """Ensure aiohttp session is created."""
        if not self._session:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
    
    async def close(self):
        """Close the aiohttp session."""
        if self._session:
            await self._session.close()
            self._session = None
    
    def set_access_token(self, token: str):
        """Set the OAuth access token for API requests."""
        self._access_token = token
    
    async def get_ticket(self, ticket_key: str) -> Optional[JiraTicket]:
        """
        Get Jira ticket information by key.
        
        Args:
            ticket_key: Jira ticket key (e.g., 'PROJ-123')
            
        Returns:
            JiraTicket object or None if not found
        """
        try:
            await self._ensure_session()
            
            if not self._access_token:
                logger.warning("No access token available for Jira API")
                return None
            
            headers = {
                'Authorization': f'Bearer {self._access_token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            url = f"{self.api_url}/issue/{ticket_key}"
            
            async with self._session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    ticket = JiraTicket(data)
                    logger.info(f"Retrieved Jira ticket: {ticket_key}")
                    return ticket
                elif response.status == 404:
                    logger.warning(f"Jira ticket not found: {ticket_key}")
                    return None
                else:
                    logger.error(f"Failed to get Jira ticket {ticket_key}: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error retrieving Jira ticket {ticket_key}: {str(e)}")
            return None
    
    async def search_tickets(self, jql: str, max_results: int = 50) -> List[JiraTicket]:
        """
        Search for Jira tickets using JQL.
        
        Args:
            jql: Jira Query Language string
            max_results: Maximum number of results to return
            
        Returns:
            List of JiraTicket objects
        """
        try:
            await self._ensure_session()
            
            if not self._access_token:
                logger.warning("No access token available for Jira API")
                return []
            
            headers = {
                'Authorization': f'Bearer {self._access_token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'jql': jql,
                'maxResults': max_results,
                'fields': [
                    'summary', 'description', 'status', 'issuetype',
                    'priority', 'assignee', 'reporter', 'created',
                    'updated', 'labels', 'components'
                ]
            }
            
            url = f"{self.api_url}/search"
            
            async with self._session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    tickets = [JiraTicket(issue) for issue in data.get('issues', [])]
                    logger.info(f"Found {len(tickets)} tickets for JQL: {jql}")
                    return tickets
                else:
                    logger.error(f"Failed to search Jira tickets: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error searching Jira tickets: {str(e)}")
            return []
    
    def extract_ticket_keys(self, text: str) -> List[str]:
        """
        Extract Jira ticket keys from text using regex patterns.
        
        Args:
            text: Text to search for ticket keys
            
        Returns:
            List of unique ticket keys found
        """
        if not text:
            return []
        
        ticket_keys = set()
        
        for pattern in self.ticket_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Clean up the match (remove # prefix if present)
                clean_key = match.lstrip('#').upper()
                ticket_keys.add(clean_key)
        
        return list(ticket_keys)
    
    async def get_tickets_from_text(self, text: str) -> List[JiraTicket]:
        """
        Extract ticket keys from text and fetch their details.
        
        Args:
            text: Text containing potential Jira ticket references
            
        Returns:
            List of JiraTicket objects for found tickets
        """
        ticket_keys = self.extract_ticket_keys(text)
        
        if not ticket_keys:
            return []
        
        tickets = []
        for key in ticket_keys:
            ticket = await self.get_ticket(key)
            if ticket:
                tickets.append(ticket)
        
        return tickets
    
    async def link_pr_to_ticket(self, ticket_key: str, pr_url: str, pr_title: str) -> bool:
        """
        Add a comment to Jira ticket linking it to a PR.
        
        Args:
            ticket_key: Jira ticket key
            pr_url: Pull request URL
            pr_title: Pull request title
            
        Returns:
            True if successful, False otherwise
        """
        try:
            await self._ensure_session()
            
            if not self._access_token:
                logger.warning("No access token available for Jira API")
                return False
            
            headers = {
                'Authorization': f'Bearer {self._access_token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            comment_body = f"Pull Request created: [{pr_title}]({pr_url})"
            
            payload = {
                'body': comment_body
            }
            
            url = f"{self.api_url}/issue/{ticket_key}/comment"
            
            async with self._session.post(url, headers=headers, json=payload) as response:
                if response.status == 201:
                    logger.info(f"Linked PR to Jira ticket {ticket_key}")
                    return True
                else:
                    logger.error(f"Failed to link PR to Jira ticket {ticket_key}: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error linking PR to Jira ticket {ticket_key}: {str(e)}")
            return False
    
    async def update_ticket_status(self, ticket_key: str, transition_id: str) -> bool:
        """
        Update Jira ticket status using transition.
        
        Args:
            ticket_key: Jira ticket key
            transition_id: ID of the transition to execute
            
        Returns:
            True if successful, False otherwise
        """
        try:
            await self._ensure_session()
            
            if not self._access_token:
                logger.warning("No access token available for Jira API")
                return False
            
            headers = {
                'Authorization': f'Bearer {self._access_token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'transition': {
                    'id': transition_id
                }
            }
            
            url = f"{self.api_url}/issue/{ticket_key}/transitions"
            
            async with self._session.post(url, headers=headers, json=payload) as response:
                if response.status == 204:
                    logger.info(f"Updated Jira ticket {ticket_key} status")
                    return True
                else:
                    logger.error(f"Failed to update Jira ticket {ticket_key} status: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error updating Jira ticket {ticket_key} status: {str(e)}")
            return False
    
    async def get_ticket_transitions(self, ticket_key: str) -> List[Dict[str, Any]]:
        """
        Get available transitions for a Jira ticket.
        
        Args:
            ticket_key: Jira ticket key
            
        Returns:
            List of available transitions
        """
        try:
            await self._ensure_session()
            
            if not self._access_token:
                logger.warning("No access token available for Jira API")
                return []
            
            headers = {
                'Authorization': f'Bearer {self._access_token}',
                'Accept': 'application/json'
            }
            
            url = f"{self.api_url}/issue/{ticket_key}/transitions"
            
            async with self._session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    transitions = data.get('transitions', [])
                    logger.info(f"Retrieved {len(transitions)} transitions for {ticket_key}")
                    return transitions
                else:
                    logger.error(f"Failed to get transitions for {ticket_key}: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error getting transitions for {ticket_key}: {str(e)}")
            return []


# Factory function for easy instantiation
def create_jira_client() -> JiraClient:
    """Create and return a new Jira client instance."""
    return JiraClient()
