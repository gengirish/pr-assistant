"""Bitbucket integration client for the Intelligent PR Assistant."""

import asyncio
import hashlib
import hmac
from typing import Dict, List, Optional, Any
import logging

import aiohttp
from requests_oauthlib import OAuth2Session

from config.config import config

logger = logging.getLogger(__name__)


class PullRequest:
    """Data model for Bitbucket pull request information."""
    
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get('id')
        self.title = data.get('title', '')
        self.description = data.get('description', '')
        self.state = data.get('state', '')
        self.created_on = data.get('created_on', '')
        self.updated_on = data.get('updated_on', '')
        self.merge_commit = data.get('merge_commit')
        self.close_source_branch = data.get('close_source_branch', False)
        
        # Author information
        author_data = data.get('author', {})
        self.author_username = author_data.get('username', '')
        self.author_display_name = author_data.get('display_name', '')
        
        # Branch information
        source_data = data.get('source', {})
        destination_data = data.get('destination', {})
        
        self.source_branch = source_data.get('branch', {}).get('name', '')
        self.source_commit = source_data.get('commit', {}).get('hash', '')
        self.destination_branch = destination_data.get('branch', {}).get('name', '')
        self.destination_commit = destination_data.get('commit', {}).get('hash', '')
        
        # Repository information
        repo_data = data.get('destination', {}).get('repository', {})
        self.repository_name = repo_data.get('name', '')
        self.repository_full_name = repo_data.get('full_name', '')
        
        # Links
        links_data = data.get('links', {})
        self.html_url = links_data.get('html', {}).get('href', '')
        self.diff_url = links_data.get('diff', {}).get('href', '')
        
        # Additional metadata
        self.comment_count = data.get('comment_count', 0)
        self.task_count = data.get('task_count', 0)
        self.reviewers = [r.get('username', '') for r in data.get('reviewers', [])]
        self.participants = [p.get('username', '') for p in data.get('participants', [])]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'state': self.state,
            'author': self.author_username,
            'source_branch': self.source_branch,
            'destination_branch': self.destination_branch,
            'repository': self.repository_full_name,
            'html_url': self.html_url,
            'reviewers': self.reviewers,
            'created_on': self.created_on,
            'updated_on': self.updated_on
        }


class BitbucketFile:
    """Data model for Bitbucket file change information."""
    
    def __init__(self, data: Dict[str, Any]):
        self.filename = data.get('new', {}).get('path', '') or data.get('old', {}).get('path', '')
        self.status = data.get('status', '')  # added, modified, removed
        self.changes = data.get('changes', 0)
        self.additions = data.get('additions', 0)
        self.deletions = data.get('deletions', 0)
        self.binary = data.get('binary', False)
        
        # File type detection
        self.is_test_file = self._is_test_file()
        self.is_doc_file = self._is_doc_file()
    
    def _is_test_file(self) -> bool:
        """Check if this is a test file."""
        test_patterns = ['test_', '_test.', '/tests/', 'spec_', '_spec.']
        filename_lower = self.filename.lower()
        return any(pattern in filename_lower for pattern in test_patterns)
    
    def _is_doc_file(self) -> bool:
        """Check if this is a documentation file."""
        doc_patterns = ['.md', '.rst', '.txt', 'readme', 'docs/', 'documentation']
        filename_lower = self.filename.lower()
        return any(pattern in filename_lower for pattern in doc_patterns)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'filename': self.filename,
            'status': self.status,
            'changes': self.changes,
            'additions': self.additions,
            'deletions': self.deletions,
            'is_test_file': self.is_test_file,
            'is_doc_file': self.is_doc_file
        }


class BitbucketClient:
    """Async Bitbucket API client with OAuth 2.0 authentication."""
    
    def __init__(self):
        """Initialize Bitbucket client with configuration."""
        self.base_url = config.atlassian.bitbucket_base_url
        self.webhook_secret = config.atlassian.bitbucket_webhook_secret
        
        # OAuth configuration
        self.oauth_client_id = config.atlassian.oauth_client_id
        self.oauth_client_secret = config.atlassian.oauth_client_secret
        self.oauth_scopes = config.atlassian.oauth_scopes
        
        # Session management
        self._session: Optional[aiohttp.ClientSession] = None
        self._access_token: Optional[str] = None
    
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
    
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify Bitbucket webhook signature.
        
        Args:
            payload: Raw webhook payload
            signature: Signature from webhook headers
            
        Returns:
            True if signature is valid, False otherwise
        """
        if not self.webhook_secret:
            logger.warning("No webhook secret configured")
            return False
        
        try:
            expected_signature = hmac.new(
                self.webhook_secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            # Remove 'sha256=' prefix if present
            if signature.startswith('sha256='):
                signature = signature[7:]
            
            return hmac.compare_digest(expected_signature, signature)
            
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {str(e)}")
            return False
    
    async def get_pull_request(self, workspace: str, repo_slug: str, pr_id: int) -> Optional[PullRequest]:
        """
        Get pull request information.
        
        Args:
            workspace: Bitbucket workspace name
            repo_slug: Repository slug
            pr_id: Pull request ID
            
        Returns:
            PullRequest object or None if not found
        """
        try:
            await self._ensure_session()
            
            if not self._access_token:
                logger.warning("No access token available for Bitbucket API")
                return None
            
            headers = {
                'Authorization': f'Bearer {self._access_token}',
                'Accept': 'application/json'
            }
            
            url = f"{self.base_url}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}"
            
            async with self._session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    pr = PullRequest(data)
                    logger.info(f"Retrieved PR {pr_id} from {workspace}/{repo_slug}")
                    return pr
                elif response.status == 404:
                    logger.warning(f"PR {pr_id} not found in {workspace}/{repo_slug}")
                    return None
                else:
                    logger.error(f"Failed to get PR {pr_id}: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error retrieving PR {pr_id}: {str(e)}")
            return None
    
    async def get_pull_request_diff(self, workspace: str, repo_slug: str, pr_id: int) -> List[BitbucketFile]:
        """
        Get pull request file changes.
        
        Args:
            workspace: Bitbucket workspace name
            repo_slug: Repository slug
            pr_id: Pull request ID
            
        Returns:
            List of BitbucketFile objects
        """
        try:
            await self._ensure_session()
            
            if not self._access_token:
                logger.warning("No access token available for Bitbucket API")
                return []
            
            headers = {
                'Authorization': f'Bearer {self._access_token}',
                'Accept': 'application/json'
            }
            
            url = f"{self.base_url}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/diffstat"
            
            async with self._session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    files = [BitbucketFile(file_data) for file_data in data.get('values', [])]
                    logger.info(f"Retrieved {len(files)} file changes for PR {pr_id}")
                    return files
                else:
                    logger.error(f"Failed to get PR {pr_id} diff: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error retrieving PR {pr_id} diff: {str(e)}")
            return []
    
    async def get_pull_request_comments(self, workspace: str, repo_slug: str, pr_id: int) -> List[Dict[str, Any]]:
        """
        Get pull request comments.
        
        Args:
            workspace: Bitbucket workspace name
            repo_slug: Repository slug
            pr_id: Pull request ID
            
        Returns:
            List of comment dictionaries
        """
        try:
            await self._ensure_session()
            
            if not self._access_token:
                logger.warning("No access token available for Bitbucket API")
                return []
            
            headers = {
                'Authorization': f'Bearer {self._access_token}',
                'Accept': 'application/json'
            }
            
            url = f"{self.base_url}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/comments"
            
            async with self._session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    comments = data.get('values', [])
                    logger.info(f"Retrieved {len(comments)} comments for PR {pr_id}")
                    return comments
                else:
                    logger.error(f"Failed to get PR {pr_id} comments: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error retrieving PR {pr_id} comments: {str(e)}")
            return []
    
    async def add_pull_request_comment(
        self, 
        workspace: str, 
        repo_slug: str, 
        pr_id: int, 
        content: str,
        inline: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add a comment to a pull request.
        
        Args:
            workspace: Bitbucket workspace name
            repo_slug: Repository slug
            pr_id: Pull request ID
            content: Comment content
            inline: Optional inline comment data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            await self._ensure_session()
            
            if not self._access_token:
                logger.warning("No access token available for Bitbucket API")
                return False
            
            headers = {
                'Authorization': f'Bearer {self._access_token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'content': {
                    'raw': content
                }
            }
            
            if inline:
                payload['inline'] = inline
            
            url = f"{self.base_url}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/comments"
            
            async with self._session.post(url, headers=headers, json=payload) as response:
                if response.status == 201:
                    logger.info(f"Added comment to PR {pr_id}")
                    return True
                else:
                    logger.error(f"Failed to add comment to PR {pr_id}: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error adding comment to PR {pr_id}: {str(e)}")
            return False
    
    async def update_pull_request_status(
        self, 
        workspace: str, 
        repo_slug: str, 
        pr_id: int, 
        state: str
    ) -> bool:
        """
        Update pull request state.
        
        Args:
            workspace: Bitbucket workspace name
            repo_slug: Repository slug
            pr_id: Pull request ID
            state: New state ('OPEN', 'MERGED', 'DECLINED')
            
        Returns:
            True if successful, False otherwise
        """
        try:
            await self._ensure_session()
            
            if not self._access_token:
                logger.warning("No access token available for Bitbucket API")
                return False
            
            headers = {
                'Authorization': f'Bearer {self._access_token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'state': state
            }
            
            url = f"{self.base_url}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}"
            
            async with self._session.put(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    logger.info(f"Updated PR {pr_id} state to {state}")
                    return True
                else:
                    logger.error(f"Failed to update PR {pr_id} state: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error updating PR {pr_id} state: {str(e)}")
            return False
    
    async def get_repository_info(self, workspace: str, repo_slug: str) -> Optional[Dict[str, Any]]:
        """
        Get repository information.
        
        Args:
            workspace: Bitbucket workspace name
            repo_slug: Repository slug
            
        Returns:
            Repository information dictionary or None
        """
        try:
            await self._ensure_session()
            
            if not self._access_token:
                logger.warning("No access token available for Bitbucket API")
                return None
            
            headers = {
                'Authorization': f'Bearer {self._access_token}',
                'Accept': 'application/json'
            }
            
            url = f"{self.base_url}/repositories/{workspace}/{repo_slug}"
            
            async with self._session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Retrieved repository info for {workspace}/{repo_slug}")
                    return data
                else:
                    logger.error(f"Failed to get repository info: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error retrieving repository info: {str(e)}")
            return None
    
    def parse_webhook_payload(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse Bitbucket webhook payload.
        
        Args:
            payload: Webhook payload dictionary
            
        Returns:
            Parsed webhook data or None
        """
        try:
            event_key = payload.get('eventKey', '')
            
            if event_key == 'pullrequest:created':
                pr_data = payload.get('pullRequest', {})
                return {
                    'event': 'pr_created',
                    'pull_request': PullRequest(pr_data),
                    'repository': payload.get('repository', {}),
                    'actor': payload.get('actor', {})
                }
            elif event_key == 'pullrequest:updated':
                pr_data = payload.get('pullRequest', {})
                return {
                    'event': 'pr_updated',
                    'pull_request': PullRequest(pr_data),
                    'repository': payload.get('repository', {}),
                    'actor': payload.get('actor', {})
                }
            elif event_key == 'pullrequest:approved':
                pr_data = payload.get('pullRequest', {})
                return {
                    'event': 'pr_approved',
                    'pull_request': PullRequest(pr_data),
                    'repository': payload.get('repository', {}),
                    'actor': payload.get('actor', {})
                }
            else:
                logger.info(f"Unhandled webhook event: {event_key}")
                return None
                
        except Exception as e:
            logger.error(f"Error parsing webhook payload: {str(e)}")
            return None


# Factory function for easy instantiation
def create_bitbucket_client() -> BitbucketClient:
    """Create and return a new Bitbucket client instance."""
    return BitbucketClient()
