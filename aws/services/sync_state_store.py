import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError


class SyncStateStore:
    """
    Persist sync state in DynamoDB for incremental jobs.

    Table schema (recommended):
    - PK: syncKey (string)
    - Attributes: season (number), lastStart (string), lastEnd (string), updatedAt (string)
    """

    def __init__(
        self,
        environment: str,
        table_name: Optional[str] = None,
        region: Optional[str] = None,
    ) -> None:
        self.environment = environment
        self.table_name = table_name or f"FTC_SyncState_{environment}"
        self.region = region or os.environ.get("AWS_REGION")
        self.dynamodb = boto3.resource("dynamodb", region_name=self.region)
        self.table = self.dynamodb.Table(self.table_name)

    def get_last_range(self, sync_key: str) -> Optional[Dict[str, Any]]:
        try:
            response = self.table.get_item(Key={"syncKey": sync_key})
            return response.get("Item")
        except ClientError:
            return None

    def save_last_range(
        self,
        sync_key: str,
        season: int,
        start_date: str,
        end_date: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        try:
            updated_at = datetime.now(timezone.utc).isoformat()
            item: Dict[str, Any] = {
                "syncKey": sync_key,
                "season": season,
                "lastStart": start_date,
                "lastEnd": end_date,
                "updatedAt": updated_at,
            }
            if metadata:
                item["metadata"] = metadata

            self.table.put_item(Item=item)
            return True
        except ClientError:
            return False
