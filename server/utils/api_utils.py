import os
from dotenv import load_dotenv
import base64
import httpx
import asyncio
import time
from fastapi import HTTPException

load_dotenv()

async def ftc_api_request(endpoint: str, params: dict | None = None, max_retries: int = 3):
    start_time = time.time()
    FTC_API_BASE_URL = "https://ftc-api.firstinspires.org/v2.0"
    FTC_USERNAME = os.getenv("FTC_API_USERNAME")
    FTC_AUTH_KEY = os.getenv("FTC_API_KEY")

    auth_string = f"{FTC_USERNAME}:{FTC_AUTH_KEY}"
    AUTH_TOKEN = base64.b64encode(auth_string.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {AUTH_TOKEN}",
        "Content-Type": "application/json"
    }
    
    full_url = f"{FTC_API_BASE_URL}{endpoint}"
    print(f"[API REQUEST] Starting: {endpoint} with params {params}")
    timeout = httpx.Timeout(30.0, connect=15.0)  # Increased from 10.0/5.0
    
    for attempt in range(max_retries):
        request_start = time.time()
        try:
            print(f"[API REQUEST] Attempt {attempt+1}/{max_retries} for {endpoint} - Started at {time.strftime('%H:%M:%S', time.localtime(request_start))}")
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    full_url,
                    headers=headers,
                    params=params
                )
                request_time = time.time() - request_start
                print(f"[API REQUEST] Response received in {request_time:.2f}s for {endpoint} (Status: {response.status_code})")
                response.raise_for_status()
                total_time = time.time() - start_time
                print(f"[API REQUEST] SUCCESS: {endpoint} completed in {total_time:.2f}s total ({request_time:.2f}s for final attempt)")
                result = response.json()
                # Log count of items if result contains a list
                if isinstance(result, dict) and any(key in result for key in ["teams", "events", "matches", "rankings"]):
                    for key in ["teams", "events", "matches", "rankings"]:
                        if key in result and isinstance(result[key], list):
                            print(f"[API REQUEST] {endpoint} returned {len(result[key])} {key}")
                return result
        except httpx.TimeoutException:
            request_time = time.time() - request_start
            print(f"[API REQUEST] TIMEOUT: {endpoint} after {request_time:.2f}s (attempt {attempt+1}/{max_retries})")
            if attempt == max_retries - 1:
                total_time = time.time() - start_time
                print(f"[API REQUEST] FAILED: {endpoint} timed out after {total_time:.2f}s total and {max_retries} attempts")
                raise HTTPException(status_code=504, detail=f"Request to {endpoint} timed out after {max_retries} attempts (total time: {total_time:.2f}s)")
            backoff_time = 2 ** attempt
            print(f"[API REQUEST] Backing off for {backoff_time}s before retry")
            await asyncio.sleep(backoff_time)
        except httpx.HTTPError as e:
            request_time = time.time() - request_start
            if isinstance(e, httpx.HTTPStatusError):
                # Log the URL and response details before raising
                print(f"[API REQUEST] HTTP ERROR: URL: {e.request.url}")
                print(f"[API REQUEST] Status code: {e.response.status_code}")
                print(f"[API REQUEST] Response text: {e.response.text}")
                print(f"[API REQUEST] Error occurred after {request_time:.2f}s (attempt {attempt+1}/{max_retries})")
                total_time = time.time() - start_time
                if attempt == max_retries - 1:
                    print(f"[API REQUEST] FAILED: {endpoint} failed after {total_time:.2f}s total and {max_retries} attempts")
                    raise HTTPException(status_code=e.response.status_code, detail=f"{str(e)} - URL: {e.request.url}")
            else:
                print(f"[API REQUEST] HTTP ERROR: {str(e)} after {request_time:.2f}s (attempt {attempt+1}/{max_retries})")
                if attempt == max_retries - 1:
                    total_time = time.time() - start_time
                    print(f"[API REQUEST] FAILED: {endpoint} failed after {total_time:.2f}s total and {max_retries} attempts")
                    raise HTTPException(status_code=500, detail=f"{str(e)} - Endpoint: {endpoint}")
            backoff_time = 2 ** attempt
            print(f"[API REQUEST] Backing off for {backoff_time}s before retry")
            await asyncio.sleep(backoff_time)