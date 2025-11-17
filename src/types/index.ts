export interface Event {
    eventId: string;  // NEW - primary key
    code: string;
    name: string;
    type: string;
    city: string;
    stateProv: string;
    country: string;
    dateStart: string;
    dateEnd: string;
    venue: string;
    regionCode?: string;
}

export interface SeasonBreakdown {
    averageEPA: number;
    cumulativeEPA: number;
    totalMatches: number;
    maxEPA: number;
    minEPA: number;
    weight: number;
}

export interface HistoricEPA {
    teamNumber: number;
    historicEPA: number;
    weightedCumulativeEPA: number;
    totalHistoricalMatches: number;
    seasonsWithData: number[];
    seasonBreakdown: {
        [season: number]: SeasonBreakdown;
    };
    calculatedAt: string;
    calculationMethod: string;
    seasonWeights: {
        [season: number]: number;
    };
}

export interface Team {
    teamNumber: number;
    season: number;
    nameShort: string;
    nameFull: string;
    city: string;
    stateProv: string;
    country: string;
    homeRegion?: string;
    website?: string;
    rookieYear?: number;
    displayTeamNumber?: string;
    displayLocation?: string;
    schoolName?: string;
    robotName?: string;
    districtCode?: string;
    homeCMP?: string;
    historicEPA?: HistoricEPA;  // NEW - embedded historic EPA
}

export interface EPAComponents {
    baseContribution: number;
    opponentStrengthMultiplier: number;
    matchTypeMultiplier: number;
}

export interface TeamScoreContribution {
    auto: number;
    teleop: number;
    endgame: number;
}

export interface RunningAverages {
    auto: number;
    teleop: number;
    endgame: number;
    matchesWithScores: number;
}

export interface AllianceScore {
    final: number;
    auto: number;
    teleop: number;
    endgame: number;
    foul: number;
}

export interface TeamMatchEPA {
    teamNumber_matchId: string;
    teamNumber: number;
    matchId: string;
    season: number;
    eventCode: string;
    matchNumber: number;
    tournamentLevel: string;
    alliance: string;
    station: string;
    matchEPA: number;
    cumulativeEPA: number;
    averageEPA: number;
    matchCount: number;
    epaComponents: EPAComponents;
    teamScoreContribution: TeamScoreContribution;
    runningAverages: RunningAverages;
    allianceScore: AllianceScore;
    opponentScore: AllianceScore;
    allianceTeamNumbers: number[];
    opponentTeamNumbers: number[];
    actualStartTime: string;
    postResultTime?: string;
    hasScores: boolean;
}

export interface CurrentSeasonEPA {
    averageEPA: number;
    matchCount: number;
    latestMatchEPA: number;
    cumulativeEPA: number;
}

export interface TeamEPASummary {
    teamNumber: number;
    historicEPA?: number;
    eventEPA?: number;
    eventMatches?: number;
}

export interface EPAComparison {
    teamNumber: number;
    name: string;
    historicEPA?: number;
    totalMatches?: number;
    seasonsWithData?: number[];
}

export interface EPAStatistics {
    maxEPA: number;
    minEPA: number;
    averageEPA: number;
    totalTeams: number;
}

// API Response Types
export interface TeamDetailsResponse {
    success: boolean;
    team: Team;
    matches: any[];
    historicEPA?: HistoricEPA;
    currentSeasonEPA?: CurrentSeasonEPA;
    totalMatches: number;
}

export interface TeamEPAResponse {
    success: boolean;
    teamNumber: number;
    historicEPA?: HistoricEPA;
}

export interface TeamSeasonEPAResponse {
    success: boolean;
    teamNumber: number;
    season: number;
    epaRecords: TeamMatchEPA[];
    summary?: CurrentSeasonEPA;
    totalMatches: number;
}

export interface EventTeamEPAsResponse {
    success: boolean;
    eventCode: string;
    season: number;
    teamEPAs: {
        [teamNumber: string]: TeamEPASummary;
    };
    totalTeams: number;
}

export interface EPAComparisonResponse {
    success: boolean;
    comparison: EPAComparison[];
    statistics: EPAStatistics;
}