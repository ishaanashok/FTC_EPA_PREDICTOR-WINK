import asyncio
import time
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from epa_calculator import EPACalculator

class ParallelEPAProcessor:
    def __init__(self, concurrency_limit: int = 20, cache_dir: str = "cache", cache_ttl: int = 24):
        self.calculator = EPACalculator()
        self.concurrency_limit = concurrency_limit
        self.cache_dir = cache_dir
        self.cache_ttl = cache_ttl  # Cache TTL in hours
        
        # Ensure cache directory exists
        if not os.path.exists(cache_dir):
            try:
                os.makedirs(cache_dir)
                print(f"Created cache directory: {cache_dir}")
            except Exception as e:
                print(f"Warning: Could not create cache directory: {str(e)}")
                
        # Cache stats for diagnostics
        self.cache_hits = 0
        self.cache_misses = 0
    
    async def calculate_team_epa(self, team_number: int, event_start_date: Optional[str] = None) -> Dict[str, Any]:
        """Calculate EPA for a single team with caching."""
        print(f"[EPA DEBUG] calculate_team_epa called for team {team_number}")
        
        try:
            # Check cache first
            cache_file = self._get_cache_filename(team_number, event_start_date)
            
            if self._is_cache_valid(cache_file):
                cached_data = self._load_from_cache(cache_file)
                if cached_data:
                    print(f"[EPA CACHE] Cache hit for team {team_number}")
                    self.cache_hits += 1
                    return cached_data
            
            # Cache miss, calculate EPA
            self.cache_misses += 1
            print(f"[EPA CACHE] Cache miss for team {team_number}, calculating EPA")
            
            team_start_time = time.time()
            
            matches = await self.calculator.get_team_matches(team_number, event_start_date if event_start_date is not None else "")
            epa = self.calculator.calculate_historical_epa(matches, team_number)
            
            process_time = time.time() - team_start_time
            print(f"Processed team {team_number} in {process_time:.2f} seconds")
            
            result = {"teamNumber": team_number, "historicalEPA": epa, "matches": matches, "cached_at": time.time()}
            
            # Save to cache
            self._save_to_cache(result, cache_file)
            
            return result
        except Exception as e:
            print(f"Error processing team {team_number}: {str(e)}")
            return {"teamNumber": team_number, "historicalEPA": 0.0, "error": str(e)}
    
    async def calculate_multiple_team_epas(self, team_numbers: List[int], event_start_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Calculate EPAs for multiple teams in parallel with concurrency limit and batch API calls."""
        semaphore = asyncio.Semaphore(self.concurrency_limit)
        results: List[Optional[Dict[str, Any]]] = [None] * len(team_numbers)

        async def limited_process_team(idx: int, team_num: int):
            async with semaphore:
                result = await self.calculate_team_epa(team_num, event_start_date)
                results[idx] = result

        # Launch all tasks at once, but with concurrency control
        tasks = [limited_process_team(idx, team_num) for idx, team_num in enumerate(team_numbers)]
        await asyncio.gather(*tasks)
        # Filter out any None results (shouldn't happen, but for safety)
        return [r for r in results if r is not None]
    
    def _get_cache_filename(self, team_number: int, event_start_date: Optional[str] = None) -> str:
        """Generate a cache filename for a team's EPA data."""
        date_part = f"_before_{event_start_date}" if event_start_date else ""
        return os.path.join(self.cache_dir, f"team_{team_number}{date_part}.json")
    
    def _is_cache_valid(self, cache_file: str) -> bool:
        """Check if cache file exists and is not expired."""
        if not os.path.exists(cache_file):
            return False
            
        # Check if modified within TTL
        file_modified_time = os.path.getmtime(cache_file)
        file_modified_date = datetime.fromtimestamp(file_modified_time)
        now = datetime.now()
        
        # Cache is valid if it's less than TTL hours old
        return now - file_modified_date < timedelta(hours=self.cache_ttl)
        
    def _save_to_cache(self, data: Dict[str, Any], cache_file: str) -> bool:
        """Save EPA data to cache."""
        try:
            os.makedirs(os.path.dirname(cache_file), exist_ok=True)
            with open(cache_file, 'w') as f:
                json.dump(data, f)
            return True
        except Exception as e:
            print(f"Error saving to cache: {str(e)}")
            return False
            
    def _load_from_cache(self, cache_file: str) -> Optional[Dict[str, Any]]:
        """Load EPA data from cache."""
        try:
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading from cache: {str(e)}")
        return None
        
    def get_epa_mapping(self, epa_results: List[Dict[str, Any]]) -> Dict[str, float]:
        """Convert EPA results list to a mapping of team numbers to EPA values."""
        mapping = {str(result['teamNumber']): result.get('historicalEPA', 0.0) for result in epa_results}
        
        # Print cache stats
        total = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total) * 100 if total > 0 else 0
        print(f"[EPA CACHE] Stats: {self.cache_hits} hits, {self.cache_misses} misses ({hit_rate:.1f}% hit rate)")
        
        return mapping
    
    async def calculate_match_predictions(self, 
                                         matches: List[Dict[str, Any]], 
                                         team_epas: Dict[str, float]) -> List[Dict[str, Any]]:
        """Calculate predictions for all matches in parallel."""
        async def process_match(match):
            red_teams = [team['teamNumber'] for team in match['teams'] if 'Red' in team['station']]
            blue_teams = [team['teamNumber'] for team in match['teams'] if 'Blue' in team['station']]
            
            prediction = self.calculator.calculate_match_win_probability(
                red_teams, blue_teams, team_epas
            )
            
            return {
                'matchNumber': match['matchNumber'],
                'prediction': prediction
            }
        
        # Process all match predictions concurrently
        tasks = [process_match(match) for match in matches]
        return await asyncio.gather(*tasks)
