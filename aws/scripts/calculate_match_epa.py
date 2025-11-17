#!/usr/bin/env python3
"""
FTC Match EPA Calculator

Calculates EPA (Expected Points Added) for each team in each match, with cumulative EPA tracking.
Processes match data and generates detailed per-match statistics including score breakdowns.

Usage:
    python calculate_match_epa.py 2024
    python calculate_match_epa.py 2022 2023 2024
    python calculate_match_epa.py --all
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import time
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('calculate_epa.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MatchEPACalculator:
    """Calculate EPA per match for all teams with cumulative tracking"""
    
    def __init__(self, season: int, data_dir: str = ".", verbose: bool = False):
        self.season = season
        self.data_dir = Path(data_dir)
        self.verbose = verbose
        
        # EPA calculation parameters (matching existing logic)
        self.match_type_multipliers = {
            'QUALIFICATION': 1.0,
            'PLAYOFF': 1.3,
            'ELIMINATION': 1.3,
            'FINAL': 1.3
        }
        
        # Endgame estimation (20% of teleop score)
        self.endgame_teleop_ratio = 0.2
        
        # Statistics tracking
        self.stats = {
            'total_matches': 0,
            'total_team_records': 0,
            'matches_with_scores': 0,
            'matches_without_scores': 0,
            'teams_processed': set(),
            'events_processed': set(),
            'processing_errors': 0
        }
        
        # Cumulative EPA tracking per team (within season)
        self.team_cumulative_epa: Dict[int, List[float]] = defaultdict(list)
        self.team_match_history: Dict[int, List[Dict]] = defaultdict(list)
        
        # Running score averages per team
        self.team_auto_scores: Dict[int, List[float]] = defaultdict(list)
        self.team_teleop_scores: Dict[int, List[float]] = defaultdict(list)
        self.team_endgame_scores: Dict[int, List[float]] = defaultdict(list)
        
        if verbose:
            logger.setLevel(logging.DEBUG)
    
    def load_matches_data(self) -> Dict[str, List[Dict]]:
        """Load matches data from JSON file"""
        matches_file = self.data_dir / f"matches_{self.season}.json"
        
        if not matches_file.exists():
            raise FileNotFoundError(f"Matches file not found: {matches_file}")
        
        logger.info(f"📂 Loading matches data from {matches_file}")
        start_time = time.time()
        
        with open(matches_file, 'r') as f:
            data = json.load(f)
        
        load_time = time.time() - start_time
        
        # Extract matches by event - handle both old and new formats
        matches_by_event = data.get('matchesByEvent', data.get('matches', {}))
        
        # Convert to simplified format: {eventCode: [matches]}
        simplified_matches = {}
        for event_code, event_data in matches_by_event.items():
            if isinstance(event_data, dict) and 'matches' in event_data:
                simplified_matches[event_code] = event_data['matches']
            elif isinstance(event_data, list):
                simplified_matches[event_code] = event_data
        
        logger.info(f"✅ Loaded {len(simplified_matches)} events in {load_time:.2f}s")
        
        return simplified_matches
    
    def load_events_data(self) -> Dict[str, Dict]:
        """Load events data for metadata"""
        events_file = self.data_dir / f"events_{self.season}.json"
        
        if not events_file.exists():
            logger.warning(f"Events file not found: {events_file}, continuing without event metadata")
            return {}
        
        logger.info(f"📂 Loading events metadata from {events_file}")
        
        with open(events_file, 'r') as f:
            data = json.load(f)
        
        # Create event code to event data mapping
        events_map = {}
        for event in data.get('events', []):
            event_code = event.get('eventCode')
            if event_code:
                events_map[event_code] = {
                    'eventName': event.get('eventName'),
                    'eventType': event.get('eventType'),
                    'dateStart': event.get('dateStart'),
                    'city': event.get('city'),
                    'state': event.get('state'),
                    'country': event.get('country')
                }
        
        logger.info(f"✅ Loaded metadata for {len(events_map)} events")
        return events_map
    
    def calculate_score_breakdown(self, match: Dict, alliance: str) -> Dict[str, float]:
        """
        Calculate detailed score breakdown for an alliance
        
        Returns:
            {
                'final': total final score,
                'auto': autonomous score,
                'teleop': teleoperated score (derived),
                'endgame': endgame score (estimated),
                'foul': foul penalty points
            }
        """
        prefix = f"score{alliance}"
        
        final_score = float(match.get(f"{prefix}Final", 0))
        auto_score = float(match.get(f"{prefix}Auto", 0))
        foul_score = float(match.get(f"{prefix}Foul", 0))
        
        # Derive teleop score: Final - Auto - Foul
        teleop_score = max(0, final_score - auto_score - foul_score)
        
        # Estimate endgame as 20% of teleop
        endgame_score = teleop_score * self.endgame_teleop_ratio
        
        # Adjust teleop to account for endgame estimation
        teleop_only_score = teleop_score * (1 - self.endgame_teleop_ratio)
        
        return {
            'final': final_score,
            'auto': auto_score,
            'teleop': round(teleop_only_score, 2),
            'endgame': round(endgame_score, 2),
            'foul': foul_score
        }
    
    def calculate_match_epa(self, alliance_score: float, opponent_score: float, 
                           alliance_team_count: int, tournament_level: str) -> Tuple[float, Dict]:
        """
        Calculate EPA for a single match using existing formula
        
        Returns:
            (match_epa, epa_components)
        """
        if alliance_score == 0 and opponent_score == 0:
            return 0.0, {
                'baseContribution': 0.0,
                'opponentStrengthMultiplier': 1.0,
                'matchTypeMultiplier': 1.0
            }
        
        # Base contribution (team's share of alliance score)
        base_contribution = alliance_score / max(alliance_team_count, 1)
        
        # Opponent strength adjustment
        opponent_strength_multiplier = 1 + (opponent_score / max(alliance_score, 1))
        
        # Match type multiplier
        match_type_multiplier = self.match_type_multipliers.get(
            tournament_level.upper(), 
            1.0
        )
        
        # Calculate final EPA
        match_epa = base_contribution * opponent_strength_multiplier * match_type_multiplier
        
        components = {
            'baseContribution': round(base_contribution, 2),
            'opponentStrengthMultiplier': round(opponent_strength_multiplier, 3),
            'matchTypeMultiplier': match_type_multiplier
        }
        
        return round(match_epa, 2), components
    
    def extract_team_from_match(self, team_data: Dict) -> Optional[int]:
        """Extract team number from team data"""
        team_number = team_data.get('teamNumber')
        if team_number is None:
            return None
        
        try:
            return int(team_number)
        except (ValueError, TypeError):
            return None
    
    def process_match(self, event_code: str, match: Dict, event_metadata: Dict) -> List[Dict]:
        """
        Process a single match and create team-match records for all participating teams
        
        Returns:
            List of team-match records
        """
        team_records = []
        
        try:
            # Extract match metadata
            match_number = match.get('matchNumber', 0)
            tournament_level = match.get('tournamentLevel', 'QUALIFICATION')
            series = match.get('series', 0)
            actual_start_time = match.get('actualStartTime')
            post_result_time = match.get('postResultTime')
            description = match.get('description', '')
            
            # Create match ID
            match_id = f"{self.season}-{event_code}-{tournament_level}-{series}-{match_number}"
            
            # Extract teams by alliance
            teams = match.get('teams', [])
            if not teams:
                logger.debug(f"No teams found in match {match_id}")
                return []
            
            red_teams = []
            blue_teams = []
            team_stations = {}
            
            for team_data in teams:
                team_number = self.extract_team_from_match(team_data)
                if team_number is None:
                    continue
                
                station = team_data.get('station', '')
                team_stations[team_number] = station
                
                if 'Red' in station:
                    red_teams.append(team_number)
                elif 'Blue' in station:
                    blue_teams.append(team_number)
            
            if not red_teams and not blue_teams:
                logger.debug(f"No valid teams found in match {match_id}")
                return []
            
            # Calculate score breakdowns
            red_scores = self.calculate_score_breakdown(match, 'Red')
            blue_scores = self.calculate_score_breakdown(match, 'Blue')
            
            # Check if match has valid scores
            has_scores = red_scores['final'] > 0 or blue_scores['final'] > 0
            if has_scores:
                self.stats['matches_with_scores'] += 1
            else:
                self.stats['matches_without_scores'] += 1
            
            # Process red alliance teams
            for team_number in red_teams:
                match_epa, epa_components = self.calculate_match_epa(
                    red_scores['final'],
                    blue_scores['final'],
                    len(red_teams),
                    tournament_level
                )
                
                # Update cumulative EPA for this team
                self.team_cumulative_epa[team_number].append(match_epa)
                cumulative_epa = sum(self.team_cumulative_epa[team_number])
                match_count = len(self.team_cumulative_epa[team_number])
                
                # Calculate team's share of alliance scores (divide by team count)
                team_auto = red_scores['auto'] / len(red_teams) if has_scores else 0
                team_teleop = red_scores['teleop'] / len(red_teams) if has_scores else 0
                team_endgame = red_scores['endgame'] / len(red_teams) if has_scores else 0
                
                # Update running score averages
                if has_scores:
                    self.team_auto_scores[team_number].append(team_auto)
                    self.team_teleop_scores[team_number].append(team_teleop)
                    self.team_endgame_scores[team_number].append(team_endgame)
                
                # Calculate running averages
                auto_scores_list = self.team_auto_scores[team_number]
                teleop_scores_list = self.team_teleop_scores[team_number]
                endgame_scores_list = self.team_endgame_scores[team_number]
                
                running_avg_auto = sum(auto_scores_list) / len(auto_scores_list) if auto_scores_list else 0
                running_avg_teleop = sum(teleop_scores_list) / len(teleop_scores_list) if teleop_scores_list else 0
                running_avg_endgame = sum(endgame_scores_list) / len(endgame_scores_list) if endgame_scores_list else 0
                
                team_record = {
                    'eventCode': event_code,
                    'eventName': event_metadata.get('eventName', ''),
                    'matchId': match_id,
                    'matchNumber': match_number,
                    'tournamentLevel': tournament_level,
                    'series': series,
                    'description': description,
                    'teamNumber': team_number,
                    'alliance': 'Red',
                    'station': team_stations.get(team_number, ''),
                    
                    # EPA Calculations
                    'matchEPA': match_epa,
                    'cumulativeEPA': round(cumulative_epa, 2),
                    'averageEPA': round(cumulative_epa / match_count, 2) if match_count > 0 else 0,
                    'matchCount': match_count,
                    'epaComponents': epa_components,
                    
                    # Team Score Contribution (share of alliance score)
                    'teamScoreContribution': {
                        'auto': round(team_auto, 2),
                        'teleop': round(team_teleop, 2),
                        'endgame': round(team_endgame, 2)
                    },
                    
                    # Running Score Averages
                    'runningAverages': {
                        'auto': round(running_avg_auto, 2),
                        'teleop': round(running_avg_teleop, 2),
                        'endgame': round(running_avg_endgame, 2),
                        'matchesWithScores': len(auto_scores_list)
                    },
                    
                    # Alliance Scores
                    'allianceScore': red_scores,
                    
                    # Opponent Scores
                    'opponentScore': blue_scores,
                    
                    # Team Context
                    'allianceTeamCount': len(red_teams),
                    'allianceTeamNumbers': sorted(red_teams),
                    'opponentTeamNumbers': sorted(blue_teams),
                    
                    # Match Metadata
                    'actualStartTime': actual_start_time,
                    'postResultTime': post_result_time,
                    'hasScores': has_scores
                }
                
                team_records.append(team_record)
                self.stats['teams_processed'].add(team_number)
            
            # Process blue alliance teams
            for team_number in blue_teams:
                match_epa, epa_components = self.calculate_match_epa(
                    blue_scores['final'],
                    red_scores['final'],
                    len(blue_teams),
                    tournament_level
                )
                
                # Update cumulative EPA for this team
                self.team_cumulative_epa[team_number].append(match_epa)
                cumulative_epa = sum(self.team_cumulative_epa[team_number])
                match_count = len(self.team_cumulative_epa[team_number])
                
                # Calculate team's share of alliance scores (divide by team count)
                team_auto = blue_scores['auto'] / len(blue_teams) if has_scores else 0
                team_teleop = blue_scores['teleop'] / len(blue_teams) if has_scores else 0
                team_endgame = blue_scores['endgame'] / len(blue_teams) if has_scores else 0
                
                # Update running score averages
                if has_scores:
                    self.team_auto_scores[team_number].append(team_auto)
                    self.team_teleop_scores[team_number].append(team_teleop)
                    self.team_endgame_scores[team_number].append(team_endgame)
                
                # Calculate running averages
                auto_scores_list = self.team_auto_scores[team_number]
                teleop_scores_list = self.team_teleop_scores[team_number]
                endgame_scores_list = self.team_endgame_scores[team_number]
                
                running_avg_auto = sum(auto_scores_list) / len(auto_scores_list) if auto_scores_list else 0
                running_avg_teleop = sum(teleop_scores_list) / len(teleop_scores_list) if teleop_scores_list else 0
                running_avg_endgame = sum(endgame_scores_list) / len(endgame_scores_list) if endgame_scores_list else 0
                
                team_record = {
                    'eventCode': event_code,
                    'eventName': event_metadata.get('eventName', ''),
                    'matchId': match_id,
                    'matchNumber': match_number,
                    'tournamentLevel': tournament_level,
                    'series': series,
                    'description': description,
                    'teamNumber': team_number,
                    'alliance': 'Blue',
                    'station': team_stations.get(team_number, ''),
                    
                    # EPA Calculations
                    'matchEPA': match_epa,
                    'cumulativeEPA': round(cumulative_epa, 2),
                    'averageEPA': round(cumulative_epa / match_count, 2) if match_count > 0 else 0,
                    'matchCount': match_count,
                    'epaComponents': epa_components,
                    
                    # Team Score Contribution (share of alliance score)
                    'teamScoreContribution': {
                        'auto': round(team_auto, 2),
                        'teleop': round(team_teleop, 2),
                        'endgame': round(team_endgame, 2)
                    },
                    
                    # Running Score Averages
                    'runningAverages': {
                        'auto': round(running_avg_auto, 2),
                        'teleop': round(running_avg_teleop, 2),
                        'endgame': round(running_avg_endgame, 2),
                        'matchesWithScores': len(auto_scores_list)
                    },
                    
                    # Alliance Scores
                    'allianceScore': blue_scores,
                    
                    # Opponent Scores
                    'opponentScore': red_scores,
                    
                    # Team Context
                    'allianceTeamCount': len(blue_teams),
                    'allianceTeamNumbers': sorted(blue_teams),
                    'opponentTeamNumbers': sorted(red_teams),
                    
                    # Match Metadata
                    'actualStartTime': actual_start_time,
                    'postResultTime': post_result_time,
                    'hasScores': has_scores
                }
                
                team_records.append(team_record)
                self.stats['teams_processed'].add(team_number)
            
            self.stats['total_matches'] += 1
            self.stats['total_team_records'] += len(team_records)
            
        except Exception as e:
            logger.error(f"Error processing match {event_code}/{match_number}: {e}")
            self.stats['processing_errors'] += 1
        
        return team_records
    
    def process_all_matches(self) -> List[Dict]:
        """Process all matches and generate team-match records"""
        logger.info(f"🔄 Processing matches for season {self.season}")
        start_time = time.time()
        
        # Load data
        matches_by_event = self.load_matches_data()
        events_metadata = self.load_events_data()
        
        # Reset cumulative EPA tracking (season boundary)
        self.team_cumulative_epa.clear()
        self.team_match_history.clear()
        
        # Reset running score averages (season boundary)
        self.team_auto_scores.clear()
        self.team_teleop_scores.clear()
        self.team_endgame_scores.clear()
        
        all_team_records = []
        
        # Process each event
        event_codes = sorted(matches_by_event.keys())
        logger.info(f"📊 Processing {len(event_codes)} events")
        
        for idx, event_code in enumerate(event_codes, 1):
            matches = matches_by_event[event_code]
            event_metadata = events_metadata.get(event_code, {})
            
            if self.verbose:
                logger.debug(f"Processing event {idx}/{len(event_codes)}: {event_code} ({len(matches)} matches)")
            
            self.stats['events_processed'].add(event_code)
            
            # Sort matches by match number to ensure chronological order
            sorted_matches = sorted(matches, key=lambda m: (
                m.get('tournamentLevel', ''),
                m.get('series', 0),
                m.get('matchNumber', 0)
            ))
            
            # Process each match in the event
            for match in sorted_matches:
                team_records = self.process_match(event_code, match, event_metadata)
                all_team_records.extend(team_records)
            
            # Progress update every 50 events
            if idx % 50 == 0:
                logger.info(f"Progress: {idx}/{len(event_codes)} events processed "
                          f"({self.stats['total_team_records']} team records)")
        
        processing_time = time.time() - start_time
        logger.info(f"✅ Processed all matches in {processing_time:.2f}s")
        
        return all_team_records
    
    def calculate_summary_statistics(self, team_records: List[Dict]) -> Dict[str, Any]:
        """Calculate summary statistics for the dataset"""
        logger.info("📊 Calculating summary statistics")
        
        if not team_records:
            return {}
        
        # EPA statistics
        epa_values = [r['matchEPA'] for r in team_records if r.get('hasScores', False)]
        cumulative_epa_values = [r['cumulativeEPA'] for r in team_records if r.get('hasScores', False)]
        
        # Score statistics
        alliance_finals = [r['allianceScore']['final'] for r in team_records if r.get('hasScores', False)]
        alliance_autos = [r['allianceScore']['auto'] for r in team_records if r.get('hasScores', False)]
        alliance_teleops = [r['allianceScore']['teleop'] for r in team_records if r.get('hasScores', False)]
        
        # Tournament level breakdown
        level_counts = defaultdict(int)
        for record in team_records:
            level_counts[record['tournamentLevel']] += 1
        
        # Team participation
        team_match_counts = defaultdict(int)
        for record in team_records:
            team_match_counts[record['teamNumber']] += 1
        
        summary = {
            'totalMatches': self.stats['total_matches'],
            'totalTeamMatchRecords': len(team_records),
            'uniqueTeams': len(self.stats['teams_processed']),
            'uniqueEvents': len(self.stats['events_processed']),
            'matchesWithScores': self.stats['matches_with_scores'],
            'matchesWithoutScores': self.stats['matches_without_scores'],
            'processingErrors': self.stats['processing_errors'],
            
            'epaStatistics': {
                'min': round(min(epa_values), 2) if epa_values else 0,
                'max': round(max(epa_values), 2) if epa_values else 0,
                'mean': round(sum(epa_values) / len(epa_values), 2) if epa_values else 0,
                'median': round(sorted(epa_values)[len(epa_values) // 2], 2) if epa_values else 0,
            },
            
            'cumulativeEPAStatistics': {
                'min': round(min(cumulative_epa_values), 2) if cumulative_epa_values else 0,
                'max': round(max(cumulative_epa_values), 2) if cumulative_epa_values else 0,
                'mean': round(sum(cumulative_epa_values) / len(cumulative_epa_values), 2) if cumulative_epa_values else 0,
            },
            
            'scoreStatistics': {
                'averageFinalScore': round(sum(alliance_finals) / len(alliance_finals), 2) if alliance_finals else 0,
                'averageAutoScore': round(sum(alliance_autos) / len(alliance_autos), 2) if alliance_autos else 0,
                'averageTeleopScore': round(sum(alliance_teleops) / len(alliance_teleops), 2) if alliance_teleops else 0,
            },
            
            'tournamentLevelBreakdown': dict(level_counts),
            
            'teamParticipation': {
                'minMatchesPerTeam': min(team_match_counts.values()) if team_match_counts else 0,
                'maxMatchesPerTeam': max(team_match_counts.values()) if team_match_counts else 0,
                'averageMatchesPerTeam': round(sum(team_match_counts.values()) / len(team_match_counts), 2) if team_match_counts else 0,
            }
        }
        
        return summary
    
    def save_results(self, team_records: List[Dict], output_file: Optional[str] = None) -> str:
        """Save team-match records to JSON file"""
        if output_file is None:
            output_file = self.data_dir / f"team_match_epa_{self.season}.json"
        else:
            output_file = Path(output_file)
        
        logger.info(f"💾 Saving results to {output_file}")
        
        # Sort records: event -> match -> team
        sorted_records = sorted(team_records, key=lambda r: (
            r['eventCode'],
            r['tournamentLevel'],
            r['series'],
            r['matchNumber'],
            r['teamNumber']
        ))
        
        # Calculate summary statistics
        summary = self.calculate_summary_statistics(sorted_records)
        
        # Create output structure
        output_data = {
            'season': self.season,
            'totalMatches': self.stats['total_matches'],
            'totalTeamMatchRecords': len(sorted_records),
            'generatedAt': datetime.now(timezone.utc).isoformat(),
            'metadata': {
                'epaCalculationVersion': '1.0',
                'scoringMethod': 'derived_teleop_estimated_endgame',
                'endgameTeleopRatio': self.endgame_teleop_ratio,
                'matchTypeMultipliers': self.match_type_multipliers,
                'cumulativeEPABoundary': 'season',
                'sortOrder': 'event_match_team'
            },
            'summary': summary,
            'teamMatchRecords': sorted_records
        }
        
        # Write to file
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        file_size = output_file.stat().st_size
        file_size_mb = file_size / (1024 * 1024)
        
        logger.info(f"✅ Saved {len(sorted_records)} records to {output_file}")
        logger.info(f"📦 File size: {file_size_mb:.2f} MB")
        
        return str(output_file)
    
    def run(self) -> str:
        """Run the complete EPA calculation pipeline"""
        logger.info(f"🚀 Starting EPA calculation for season {self.season}")
        start_time = time.time()
        
        try:
            # Process all matches
            team_records = self.process_all_matches()
            
            if not team_records:
                logger.error("❌ No team records generated")
                return None
            
            # Save results
            output_file = self.save_results(team_records)
            
            total_time = time.time() - start_time
            
            logger.info(f"🎉 EPA calculation completed successfully!")
            logger.info(f"⏱️  Total processing time: {total_time:.2f}s")
            logger.info(f"📊 Statistics:")
            logger.info(f"   • Events: {len(self.stats['events_processed'])}")
            logger.info(f"   • Matches: {self.stats['total_matches']}")
            logger.info(f"   • Teams: {len(self.stats['teams_processed'])}")
            logger.info(f"   • Team-Match Records: {self.stats['total_team_records']}")
            logger.info(f"   • Matches with scores: {self.stats['matches_with_scores']}")
            logger.info(f"   • Matches without scores: {self.stats['matches_without_scores']}")
            
            return output_file
            
        except Exception as e:
            logger.error(f"❌ Error during EPA calculation: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Calculate EPA per match for FTC teams",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python calculate_match_epa.py 2024
    python calculate_match_epa.py 2022 2023 2024
    python calculate_match_epa.py --all
    python calculate_match_epa.py 2024 --verbose
    python calculate_match_epa.py 2024 --output-dir ./output

Output:
    Creates team_match_epa_<season>.json files with:
    - Match-by-match EPA calculations
    - Cumulative EPA tracking (within season)
    - Detailed score breakdowns (auto, teleop, endgame)
    - Individual team statistics
    - Summary statistics

EPA Calculation:
    match_epa = (alliance_score / team_count) * opponent_strength * match_type
    cumulative_epa = sum of all match EPAs in season (chronologically)
        """
    )
    
    parser.add_argument(
        'seasons',
        nargs='*',
        type=int,
        help='Season years to process (e.g., 2024 2023)'
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help='Process all available seasons'
    )
    
    parser.add_argument(
        '--data-dir',
        type=str,
        default='.',
        help='Directory containing match data files (default: current directory)'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='Output directory for results (default: same as data-dir)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Determine seasons to process
    if args.all:
        # Find all available match files
        data_dir = Path(args.data_dir)
        match_files = list(data_dir.glob('matches_*.json'))
        seasons = sorted([int(f.stem.split('_')[1]) for f in match_files])
        if not seasons:
            logger.error("❌ No match files found in data directory")
            sys.exit(1)
        logger.info(f"📂 Found match files for seasons: {seasons}")
    elif args.seasons:
        seasons = args.seasons
    else:
        parser.print_help()
        sys.exit(1)
    
    # Process each season
    output_dir = Path(args.output_dir) if args.output_dir else Path(args.data_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    total_start_time = time.time()
    
    for season in seasons:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing Season {season}")
        logger.info(f"{'='*60}\n")
        
        calculator = MatchEPACalculator(season, args.data_dir, args.verbose)
        output_file = calculator.run()
        
        if output_file:
            results.append((season, output_file))
        else:
            logger.error(f"❌ Failed to process season {season}")
    
    total_time = time.time() - total_start_time
    
    # Final summary
    logger.info(f"\n{'='*60}")
    logger.info(f"🎉 All Seasons Processed!")
    logger.info(f"{'='*60}")
    logger.info(f"⏱️  Total time: {total_time:.2f}s")
    logger.info(f"📁 Output files:")
    for season, output_file in results:
        logger.info(f"   • Season {season}: {output_file}")
    logger.info(f"{'='*60}\n")


if __name__ == "__main__":
    main()

