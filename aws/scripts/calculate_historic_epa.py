#!/usr/bin/env python3
"""
Historic EPA Calculator for FTC Teams

Calculates historic EPA for teams based on their performance across multiple seasons.
Updates the teams JSON file with historic EPA data.

Usage:
    python calculate_historic_epa.py 2025
    python calculate_historic_epa.py 2025 --seasons 2022 2023 2024
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from collections import defaultdict
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('calculate_historic_epa.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class HistoricEPACalculator:
    """Calculate historic EPA for teams based on multiple seasons of data"""
    
    def __init__(self, target_season: int, historical_seasons: List[int], 
                 data_dir: str = ".", verbose: bool = False):
        self.target_season = target_season
        self.historical_seasons = sorted(historical_seasons)
        self.data_dir = Path(data_dir)
        self.verbose = verbose
        
        # Season weights for EPA calculation (more recent = higher weight)
        self.season_weights = {
            2024: 1.0,
            2023: 0.7,
            2022: 0.5
        }
        
        # Statistics
        self.stats = {
            'teams_processed': 0,
            'teams_with_history': 0,
            'teams_without_history': 0,
            'total_historical_records': 0,
            'seasons_analyzed': len(historical_seasons)
        }
        
        if verbose:
            logger.setLevel(logging.DEBUG)
    
    def load_teams_data(self, season: int) -> Dict[str, Any]:
        """Load teams data for a given season"""
        teams_file = self.data_dir / f"teams_{season}.json"
        
        if not teams_file.exists():
            raise FileNotFoundError(f"Teams file not found: {teams_file}")
        
        logger.info(f"📂 Loading teams data from {teams_file}")
        
        with open(teams_file, 'r') as f:
            data = json.load(f)
        
        return data
    
    def load_epa_data(self, season: int) -> Optional[Dict[int, Dict]]:
        """Load EPA data for a given season"""
        epa_file = self.data_dir / f"team_match_epa_{season}.json"
        
        if not epa_file.exists():
            logger.warning(f"⚠️  EPA file not found for season {season}: {epa_file}")
            return None
        
        logger.info(f"📂 Loading EPA data from {epa_file}")
        
        with open(epa_file, 'r') as f:
            data = json.load(f)
        
        # Build team EPA summary from team-match records
        team_epa_summary = {}
        
        for record in data.get('teamMatchRecords', []):
            team_number = record['teamNumber']
            
            if team_number not in team_epa_summary:
                team_epa_summary[team_number] = {
                    'teamNumber': team_number,
                    'season': season,
                    'totalMatches': 0,
                    'totalEPA': 0.0,
                    'averageEPA': 0.0,
                    'maxEPA': 0.0,
                    'minEPA': float('inf'),
                    'finalCumulativeEPA': 0.0,
                    'matchEPAs': []
                }
            
            team_summary = team_epa_summary[team_number]
            match_epa = record.get('matchEPA', 0.0)
            
            team_summary['totalMatches'] += 1
            team_summary['totalEPA'] += match_epa
            team_summary['matchEPAs'].append(match_epa)
            team_summary['maxEPA'] = max(team_summary['maxEPA'], match_epa)
            team_summary['minEPA'] = min(team_summary['minEPA'], match_epa)
            team_summary['finalCumulativeEPA'] = record.get('cumulativeEPA', 0.0)
        
        # Calculate averages
        for team_number, summary in team_epa_summary.items():
            if summary['totalMatches'] > 0:
                summary['averageEPA'] = round(summary['totalEPA'] / summary['totalMatches'], 2)
                summary['maxEPA'] = round(summary['maxEPA'], 2)
                summary['minEPA'] = round(summary['minEPA'], 2) if summary['minEPA'] != float('inf') else 0.0
                summary['finalCumulativeEPA'] = round(summary['finalCumulativeEPA'], 2)
            
            # Remove match EPAs list to save space
            del summary['matchEPAs']
        
        logger.info(f"✅ Loaded EPA data for {len(team_epa_summary)} teams from season {season}")
        
        return team_epa_summary
    
    def calculate_historic_epa(self, team_number: int, 
                               season_epa_data: Dict[int, Dict]) -> Dict[str, Any]:
        """
        Calculate historic EPA for a team based on multiple seasons
        
        Formula:
            historic_epa = sum(season_avg_epa * season_weight) / sum(weights)
            weighted_cumulative = sum(season_cumulative * season_weight)
        """
        historic_data = {
            'teamNumber': team_number,
            'historicEPA': 0.0,
            'weightedCumulativeEPA': 0.0,
            'totalHistoricalMatches': 0,
            'seasonsWithData': [],
            'seasonBreakdown': {},
            'calculatedAt': datetime.now(timezone.utc).isoformat(),
            'calculationMethod': 'weighted_average',
            'seasonWeights': self.season_weights
        }
        
        total_weighted_epa = 0.0
        total_weight = 0.0
        total_weighted_cumulative = 0.0
        
        for season, epa_data in season_epa_data.items():
            if team_number in epa_data:
                team_season_data = epa_data[team_number]
                weight = self.season_weights.get(season, 0.5)
                
                avg_epa = team_season_data['averageEPA']
                cumulative_epa = team_season_data['finalCumulativeEPA']
                matches = team_season_data['totalMatches']
                
                # Weighted EPA calculation
                total_weighted_epa += avg_epa * weight
                total_weight += weight
                total_weighted_cumulative += cumulative_epa * weight
                
                historic_data['totalHistoricalMatches'] += matches
                historic_data['seasonsWithData'].append(season)
                historic_data['seasonBreakdown'][str(season)] = {
                    'averageEPA': avg_epa,
                    'cumulativeEPA': cumulative_epa,
                    'totalMatches': matches,
                    'maxEPA': team_season_data['maxEPA'],
                    'minEPA': team_season_data['minEPA'],
                    'weight': weight
                }
        
        # Calculate final historic EPA
        if total_weight > 0:
            historic_data['historicEPA'] = round(total_weighted_epa / total_weight, 2)
            historic_data['weightedCumulativeEPA'] = round(total_weighted_cumulative, 2)
        
        return historic_data
    
    def process_teams(self) -> Dict[int, Dict]:
        """Process all teams and calculate historic EPA"""
        logger.info(f"🔄 Processing teams for season {self.target_season}")
        logger.info(f"📊 Using historical data from seasons: {self.historical_seasons}")
        
        # Load target season teams
        target_teams_data = self.load_teams_data(self.target_season)
        target_teams = target_teams_data.get('teams', [])
        
        logger.info(f"✅ Found {len(target_teams)} teams in season {self.target_season}")
        
        # Load EPA data for all historical seasons
        season_epa_data = {}
        for season in self.historical_seasons:
            epa_data = self.load_epa_data(season)
            if epa_data:
                season_epa_data[season] = epa_data
        
        if not season_epa_data:
            logger.error("❌ No historical EPA data found!")
            return {}
        
        logger.info(f"✅ Loaded EPA data for {len(season_epa_data)} seasons")
        
        # Calculate historic EPA for each team
        team_historic_epa = {}
        
        for idx, team in enumerate(target_teams, 1):
            team_number = team.get('teamNumber')
            
            if team_number is None:
                continue
            
            # Calculate historic EPA
            historic_epa = self.calculate_historic_epa(team_number, season_epa_data)
            
            if historic_epa['seasonsWithData']:
                self.stats['teams_with_history'] += 1
                team_historic_epa[team_number] = historic_epa
            else:
                self.stats['teams_without_history'] += 1
                # Still add entry but with zero EPA
                team_historic_epa[team_number] = {
                    'teamNumber': team_number,
                    'historicEPA': 0.0,
                    'weightedCumulativeEPA': 0.0,
                    'totalHistoricalMatches': 0,
                    'seasonsWithData': [],
                    'seasonBreakdown': {},
                    'calculatedAt': datetime.now(timezone.utc).isoformat(),
                    'note': 'No historical data available'
                }
            
            self.stats['teams_processed'] += 1
            
            if self.verbose and idx % 500 == 0:
                logger.debug(f"Processed {idx}/{len(target_teams)} teams")
        
        logger.info(f"✅ Processed {self.stats['teams_processed']} teams")
        logger.info(f"   • Teams with history: {self.stats['teams_with_history']}")
        logger.info(f"   • Teams without history: {self.stats['teams_without_history']}")
        
        return team_historic_epa
    
    def update_teams_file(self, team_historic_epa: Dict[int, Dict]) -> str:
        """Update the teams JSON file with historic EPA data"""
        teams_file = self.data_dir / f"teams_{self.target_season}.json"
        
        logger.info(f"📂 Loading teams file to update: {teams_file}")
        
        with open(teams_file, 'r') as f:
            teams_data = json.load(f)
        
        # Update each team with historic EPA
        updated_count = 0
        for team in teams_data.get('teams', []):
            team_number = team.get('teamNumber')
            if team_number in team_historic_epa:
                team['historicEPA'] = team_historic_epa[team_number]
                updated_count += 1
        
        # Update metadata
        if 'metadata' not in teams_data:
            teams_data['metadata'] = {}
        
        teams_data['metadata']['historicEPACalculated'] = True
        teams_data['metadata']['historicEPACalculatedAt'] = datetime.now(timezone.utc).isoformat()
        teams_data['metadata']['historicEPASeasons'] = self.historical_seasons
        teams_data['metadata']['historicEPASeasonWeights'] = self.season_weights
        
        # Create backup
        backup_file = self.data_dir / f"teams_{self.target_season}_backup.json"
        logger.info(f"💾 Creating backup: {backup_file}")
        
        with open(backup_file, 'w') as f:
            json.dump(teams_data, f, indent=2)
        
        # Save updated file
        logger.info(f"💾 Saving updated teams file: {teams_file}")
        
        with open(teams_file, 'w') as f:
            json.dump(teams_data, f, indent=2)
        
        file_size = teams_file.stat().st_size
        file_size_mb = file_size / (1024 * 1024)
        
        logger.info(f"✅ Updated {updated_count} teams with historic EPA")
        logger.info(f"📦 File size: {file_size_mb:.2f} MB")
        
        return str(teams_file)
    
    def generate_summary_report(self, team_historic_epa: Dict[int, Dict]) -> Dict[str, Any]:
        """Generate summary statistics for historic EPA calculations"""
        logger.info("📊 Generating summary report")
        
        # Calculate statistics
        epa_values = [data['historicEPA'] for data in team_historic_epa.values() 
                     if data['historicEPA'] > 0]
        cumulative_values = [data['weightedCumulativeEPA'] for data in team_historic_epa.values() 
                            if data['weightedCumulativeEPA'] > 0]
        
        # Season participation breakdown
        season_participation = defaultdict(int)
        for data in team_historic_epa.values():
            for season in data['seasonsWithData']:
                season_participation[season] += 1
        
        # Match count distribution
        match_counts = [data['totalHistoricalMatches'] for data in team_historic_epa.values()]
        
        summary = {
            'targetSeason': self.target_season,
            'historicalSeasons': self.historical_seasons,
            'seasonWeights': self.season_weights,
            'teamsProcessed': self.stats['teams_processed'],
            'teamsWithHistory': self.stats['teams_with_history'],
            'teamsWithoutHistory': self.stats['teams_without_history'],
            'percentageWithHistory': round(
                (self.stats['teams_with_history'] / self.stats['teams_processed'] * 100), 2
            ) if self.stats['teams_processed'] > 0 else 0,
            
            'historicEPAStatistics': {
                'min': round(min(epa_values), 2) if epa_values else 0,
                'max': round(max(epa_values), 2) if epa_values else 0,
                'mean': round(sum(epa_values) / len(epa_values), 2) if epa_values else 0,
                'median': round(sorted(epa_values)[len(epa_values) // 2], 2) if epa_values else 0,
            },
            
            'cumulativeEPAStatistics': {
                'min': round(min(cumulative_values), 2) if cumulative_values else 0,
                'max': round(max(cumulative_values), 2) if cumulative_values else 0,
                'mean': round(sum(cumulative_values) / len(cumulative_values), 2) if cumulative_values else 0,
            },
            
            'seasonParticipation': dict(season_participation),
            
            'matchCountStatistics': {
                'min': min(match_counts) if match_counts else 0,
                'max': max(match_counts) if match_counts else 0,
                'mean': round(sum(match_counts) / len(match_counts), 2) if match_counts else 0,
            },
            
            'calculatedAt': datetime.now(timezone.utc).isoformat()
        }
        
        return summary
    
    def save_summary_report(self, summary: Dict[str, Any]) -> str:
        """Save summary report to JSON file"""
        summary_file = self.data_dir / f"historic_epa_summary_{self.target_season}.json"
        
        logger.info(f"💾 Saving summary report: {summary_file}")
        
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        return str(summary_file)
    
    def run(self) -> bool:
        """Run the complete historic EPA calculation pipeline"""
        logger.info(f"🚀 Starting historic EPA calculation for season {self.target_season}")
        logger.info(f"📊 Historical seasons: {self.historical_seasons}")
        
        try:
            # Process teams and calculate historic EPA
            team_historic_epa = self.process_teams()
            
            if not team_historic_epa:
                logger.error("❌ No historic EPA data calculated")
                return False
            
            # Update teams file
            teams_file = self.update_teams_file(team_historic_epa)
            
            # Generate and save summary report
            summary = self.generate_summary_report(team_historic_epa)
            summary_file = self.save_summary_report(summary)
            
            # Print summary
            logger.info(f"\n{'='*60}")
            logger.info(f"🎉 Historic EPA Calculation Complete!")
            logger.info(f"{'='*60}")
            logger.info(f"📊 Summary:")
            logger.info(f"   • Teams processed: {summary['teamsProcessed']}")
            logger.info(f"   • Teams with history: {summary['teamsWithHistory']} ({summary['percentageWithHistory']}%)")
            logger.info(f"   • Teams without history: {summary['teamsWithoutHistory']}")
            logger.info(f"   • Average historic EPA: {summary['historicEPAStatistics']['mean']}")
            logger.info(f"   • EPA range: {summary['historicEPAStatistics']['min']} - {summary['historicEPAStatistics']['max']}")
            logger.info(f"\n📁 Files:")
            logger.info(f"   • Updated teams file: {teams_file}")
            logger.info(f"   • Summary report: {summary_file}")
            logger.info(f"   • Backup created: teams_{self.target_season}_backup.json")
            logger.info(f"{'='*60}\n")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error during historic EPA calculation: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Calculate historic EPA for FTC teams based on multiple seasons",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Calculate historic EPA for 2025 teams using 2022-2024 data
    python calculate_historic_epa.py 2025
    
    # Specify custom historical seasons
    python calculate_historic_epa.py 2025 --seasons 2023 2024
    
    # Verbose mode
    python calculate_historic_epa.py 2025 --verbose

Historic EPA Calculation:
    historic_epa = sum(season_avg_epa * season_weight) / sum(weights)
    
    Default season weights:
        2024: 1.0 (most recent)
        2023: 0.7
        2022: 0.5 (oldest)

Output:
    - Updates teams_<season>.json with historicEPA field for each team
    - Creates backup: teams_<season>_backup.json
    - Generates summary report: historic_epa_summary_<season>.json
        """
    )
    
    parser.add_argument(
        'target_season',
        type=int,
        help='Target season to calculate historic EPA for (e.g., 2025)'
    )
    
    parser.add_argument(
        '--seasons',
        nargs='+',
        type=int,
        default=[2022, 2023, 2024],
        help='Historical seasons to use for EPA calculation (default: 2022 2023 2024)'
    )
    
    parser.add_argument(
        '--data-dir',
        type=str,
        default='.',
        help='Directory containing data files (default: current directory)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Validate seasons
    if args.target_season in args.seasons:
        logger.error(f"❌ Target season {args.target_season} cannot be in historical seasons")
        sys.exit(1)
    
    if args.target_season < max(args.seasons):
        logger.warning(f"⚠️  Target season {args.target_season} is older than some historical seasons")
    
    # Create calculator and run
    calculator = HistoricEPACalculator(
        args.target_season,
        args.seasons,
        args.data_dir,
        args.verbose
    )
    
    success = calculator.run()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()



