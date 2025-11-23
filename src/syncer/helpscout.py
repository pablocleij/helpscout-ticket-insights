"""HelpScout API client for syncing tickets and conversations."""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from sqlalchemy.orm import Session
from src.config import settings
from src.models import Ticket, Thread, SyncState

logger = logging.getLogger(__name__)


class HelpScoutAPIError(Exception):
    """HelpScout API error."""

    pass


class HelpScoutClient:
    """Client for HelpScout API v2."""

    BASE_URL = "https://api.helpscout.net/v2"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create requests session with retry logic."""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update({"Authorization": f"Bearer {self.api_key}"})
        return session

    def _make_request(
        self, method: str, endpoint: str, params: Optional[Dict] = None, json: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make API request with error handling."""
        url = f"{self.BASE_URL}/{endpoint}"
        try:
            response = self.session.request(method, url, params=params, json=json)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"HelpScout API error: {e}")
            raise HelpScoutAPIError(f"API request failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in API request: {e}")
            raise HelpScoutAPIError(f"Unexpected error: {e}")

    def get_mailboxes(self) -> List[Dict[str, Any]]:
        """Get all mailboxes."""
        response = self._make_request("GET", "mailboxes")
        return response.get("_embedded", {}).get("mailboxes", [])

    def get_conversations(
        self,
        mailbox_id: Optional[int] = None,
        status: Optional[str] = None,
        modified_since: Optional[datetime] = None,
        page: int = 1,
    ) -> Dict[str, Any]:
        """Get conversations with pagination."""
        params = {"page": page}
        if mailbox_id:
            params["mailbox"] = mailbox_id
        if status:
            params["status"] = status
        if modified_since:
            params["modifiedSince"] = modified_since.isoformat()

        return self._make_request("GET", "conversations", params=params)

    def get_conversation(self, conversation_id: int) -> Dict[str, Any]:
        """Get single conversation details."""
        return self._make_request("GET", f"conversations/{conversation_id}")

    def get_conversation_threads(self, conversation_id: int) -> List[Dict[str, Any]]:
        """Get all threads for a conversation."""
        response = self._make_request("GET", f"conversations/{conversation_id}/threads")
        return response.get("_embedded", {}).get("threads", [])


class HelpScoutSyncer:
    """Syncs HelpScout tickets to local database."""

    def __init__(self, db: Session, client: Optional[HelpScoutClient] = None):
        self.db = db
        self.client = client or HelpScoutClient(settings.helpscout_api_key)

    def sync_all_mailboxes(self, full_sync: bool = False) -> Dict[str, int]:
        """Sync all mailboxes."""
        logger.info("Starting sync for all mailboxes")
        mailboxes = self.client.get_mailboxes()
        stats = {"mailboxes": 0, "tickets": 0, "threads": 0}

        for mailbox in mailboxes:
            mailbox_id = mailbox["id"]
            logger.info(f"Syncing mailbox: {mailbox['name']} (ID: {mailbox_id})")
            result = self.sync_mailbox(mailbox_id, mailbox["name"], full_sync=full_sync)
            stats["mailboxes"] += 1
            stats["tickets"] += result["tickets"]
            stats["threads"] += result["threads"]

        logger.info(f"Sync complete: {stats}")
        return stats

    def sync_mailbox(
        self, mailbox_id: int, mailbox_name: str, full_sync: bool = False
    ) -> Dict[str, int]:
        """Sync a specific mailbox with robust error handling and duplicate prevention."""
        stats = {
            "tickets": 0,
            "threads": 0,
            "updated": 0,
            "created": 0,
            "skipped": 0,
            "errors": 0,
        }

        # Get sync state
        sync_state = self.db.query(SyncState).filter_by(mailbox_id=mailbox_id).first()

        # Determine if we need incremental or full sync
        modified_since = None
        if not full_sync and sync_state and sync_state.last_modified_at:
            modified_since = sync_state.last_modified_at
            logger.info(f"Incremental sync since {modified_since}")
        else:
            logger.info("Full sync")

        # Get start date filter if configured
        start_date_filter = None
        if settings.sync_start_date:
            try:
                start_date_filter = datetime.fromisoformat(
                    settings.sync_start_date.replace("Z", "+00:00")
                )
                logger.info(f"Filtering tickets from {start_date_filter}")
            except Exception as e:
                logger.warning(f"Invalid SYNC_START_DATE: {e}")

        page = 1
        total_synced = 0
        batch_size = 10  # Commit every N tickets

        while True:
            # Fetch conversations
            try:
                response = self.client.get_conversations(
                    mailbox_id=mailbox_id, modified_since=modified_since, page=page
                )
            except Exception as e:
                logger.error(f"Error fetching conversations page {page}: {e}")
                break

            conversations = response.get("_embedded", {}).get("conversations", [])
            if not conversations:
                break

            for i, conv in enumerate(conversations):
                # Filter by start date if configured
                if start_date_filter:
                    created_at = self._parse_datetime(conv.get("createdAt"))
                    if created_at and created_at < start_date_filter:
                        logger.debug(f"Skipping ticket {conv.get('id')} - before start date")
                        stats["skipped"] += 1
                        continue

                try:
                    # Check if ticket already exists (duplicate detection)
                    helpscout_id = conv.get("id")
                    existing = (
                        self.db.query(Ticket).filter_by(helpscout_id=helpscout_id).first()
                    )

                    # Sync conversation and threads
                    self._sync_conversation(conv, mailbox_id, mailbox_name)

                    if existing:
                        stats["updated"] += 1
                        logger.debug(f"Updated ticket {helpscout_id}")
                    else:
                        stats["created"] += 1
                        logger.debug(f"Created ticket {helpscout_id}")

                    stats["tickets"] += 1
                    total_synced += 1

                    # Batch commits for performance
                    if (i + 1) % batch_size == 0:
                        self.db.commit()
                        logger.debug(f"Committed batch of {batch_size} tickets")

                    # Respect rate limits
                    if total_synced >= settings.max_tickets_per_sync:
                        logger.warning(
                            f"Reached max tickets limit: {settings.max_tickets_per_sync}"
                        )
                        break

                except Exception as e:
                    logger.error(
                        f"Error syncing conversation {conv.get('id')}: {e}", exc_info=True
                    )
                    stats["errors"] += 1
                    self.db.rollback()  # Rollback failed transaction
                    continue

            # Commit remaining tickets in batch
            try:
                self.db.commit()
            except Exception as e:
                logger.error(f"Error committing batch: {e}")
                self.db.rollback()

            # Check if there are more pages
            page_info = response.get("page", {})
            if page >= page_info.get("totalPages", 1):
                break

            page += 1

            # Check max tickets limit
            if total_synced >= settings.max_tickets_per_sync:
                break

        # Update sync state
        try:
            if not sync_state:
                sync_state = SyncState(mailbox_id=mailbox_id)
                self.db.add(sync_state)

            sync_state.last_sync_at = datetime.utcnow()
            sync_state.last_modified_at = datetime.utcnow()
            sync_state.total_tickets_synced = (
                sync_state.total_tickets_synced or 0
            ) + total_synced
            self.db.commit()
        except Exception as e:
            logger.error(f"Error updating sync state: {e}")
            self.db.rollback()

        logger.info(
            f"Mailbox {mailbox_id} sync complete - "
            f"Created: {stats['created']}, Updated: {stats['updated']}, "
            f"Skipped: {stats['skipped']}, Errors: {stats['errors']}"
        )
        return stats

    def _sync_conversation(
        self, conv_data: Dict[str, Any], mailbox_id: int, mailbox_name: str
    ) -> None:
        """Sync a single conversation and its threads."""
        helpscout_id = conv_data["id"]

        # Check if ticket exists
        ticket = self.db.query(Ticket).filter_by(helpscout_id=helpscout_id).first()

        # Parse dates
        created_at = self._parse_datetime(conv_data.get("createdAt"))
        updated_at = self._parse_datetime(conv_data.get("userUpdatedAt"))
        closed_at = self._parse_datetime(conv_data.get("closedAt"))

        # Extract customer info
        customer = conv_data.get("primaryCustomer", {})
        customer_email = customer.get("email")
        customer_name = (
            f"{customer.get('first', '')} {customer.get('last', '')}".strip()
            or customer_email
        )

        # Extract tags
        tags = [tag for tag in conv_data.get("tags", [])]

        if ticket:
            # Update existing ticket
            ticket.subject = conv_data.get("subject")
            ticket.status = conv_data.get("status")
            ticket.type = conv_data.get("type")
            ticket.customer_email = customer_email
            ticket.customer_name = customer_name
            ticket.updated_at = updated_at
            ticket.closed_at = closed_at
            ticket.tags = tags
            ticket.raw_data = conv_data
        else:
            # Create new ticket
            ticket = Ticket(
                helpscout_id=helpscout_id,
                number=conv_data.get("number"),
                subject=conv_data.get("subject"),
                status=conv_data.get("status"),
                type=conv_data.get("type"),
                mailbox_id=mailbox_id,
                mailbox_name=mailbox_name,
                customer_email=customer_email,
                customer_name=customer_name,
                created_at=created_at,
                updated_at=updated_at,
                closed_at=closed_at,
                tags=tags,
                raw_data=conv_data,
            )
            self.db.add(ticket)
            self.db.flush()  # Get ticket.id

        # Sync threads
        threads_data = self.client.get_conversation_threads(helpscout_id)
        self._sync_threads(ticket.id, threads_data)

    def _sync_threads(self, ticket_id: int, threads_data: List[Dict[str, Any]]) -> None:
        """Sync threads for a ticket."""
        for thread_data in threads_data:
            helpscout_id = thread_data["id"]

            # Check if thread exists
            thread = self.db.query(Thread).filter_by(helpscout_id=helpscout_id).first()

            # Parse thread data
            created_at = self._parse_datetime(thread_data.get("createdAt"))
            created_by = thread_data.get("createdBy", {})
            body = thread_data.get("body", "")
            body_plain = self._strip_html(body)

            if thread:
                # Update existing thread
                thread.body = body
                thread.body_plain = body_plain
            else:
                # Create new thread
                thread = Thread(
                    helpscout_id=helpscout_id,
                    ticket_id=ticket_id,
                    type=thread_data.get("type"),
                    body=body,
                    body_plain=body_plain,
                    created_by_email=created_by.get("email"),
                    created_by_name=(
                        f"{created_by.get('first', '')} {created_by.get('last', '')}".strip()
                    ),
                    created_at=created_at,
                    is_customer=(thread_data.get("type") == "customer"),
                )
                self.db.add(thread)

    @staticmethod
    def _parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO datetime string."""
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except Exception:
            return None

    @staticmethod
    def _strip_html(html: str) -> str:
        """Simple HTML stripping (you may want to use BeautifulSoup for production)."""
        import re

        # Remove HTML tags
        clean = re.sub(r"<[^>]+>", "", html)
        # Remove extra whitespace
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean
