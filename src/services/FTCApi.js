import axios from 'axios';
import { config } from '../config.js';

const BASE_URL = config.apiBaseUrl;

class FTCApi {
    constructor() {
        this.axiosInstance = axios.create({
            baseURL: BASE_URL,
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
        });
    }

    // Helper method for making requests
    async request(endpoint, params = {}) {
        try {
            const response = await this.axiosInstance.get(endpoint, { params });
            return response.data;
        } catch (error) {
            console.error('AWS API Error:', error);
            throw error;
        }
    }

    // Advancement methods
    async getEventAdvancement(season, eventCode, excludeSkipped = false) {
        return this.request(`/advancement/${season}/${eventCode}`, { excludeSkipped });
    }

    async getAdvancementSource(season, eventCode, includeDeclines = false) {
        return this.request(`/advancement/${season}/${eventCode}/source`, { includeDeclines });
    }

    // League methods
    async getLeagues(season, regionCode = null, leagueCode = null) {
        return this.request(`/leagues/${season}`, { regionCode, leagueCode });
    }

    async getLeagueMembers(season, regionCode, leagueCode) {
        return this.request(`/leagues/${season}/members/${regionCode}/${leagueCode}`);
    }

    async getLeagueRankings(season, regionCode, leagueCode) {
        return this.request(`/leagues/${season}/rankings/${regionCode}/${leagueCode}`);
    }

    // Event methods
    async getEventInfo(season, eventCode) {
        return this.request(`/events/${season}`, { eventCode });
    }

    async getEventRankings(season, eventCode) {
        return this.request(`/events/${season}/${eventCode}/rankings`);
    }

    // Season Data methods
    async getSeasonSummary(season) {
        return this.request(`/season/${season}`);
    }

    async getEvents(season, eventCode = null, teamNumber = null) {
        // Update to match AWS API endpoint format
        const queryParams = { season };
        if (eventCode) queryParams.eventCode = eventCode;
        if (teamNumber) queryParams.teamNumber = teamNumber;
        return this.request('/api/events', queryParams);
    }

    async getTeams(season, params = {}) {
        // Update to match AWS API endpoint format
        const queryParams = { season, ...params };
        return this.request('/api/teams', queryParams);
    }

    // Remove getTeamEPA as it's no longer needed
    async getTeamMatches(season, teamNumber) {
        return this.request(`/teams/${season}/${teamNumber}/matches`);
    }

    async getEventSchedule(season, eventCode, tournamentLevel = 'qual', teamNumber = 0, start = 0, end = 999) {
        const params = {
            tournamentLevel,
            teamNumber,
            start,
            end
        };
        return this.request(`/schedule/${season}/${eventCode}`, params);
    }

    async getEventMatches(season, eventCode, tournamentLevel = 'qual', teamNumber = null) {
        const params = {
            tournamentLevel,
            teamNumber
        };
        return this.request(`/matches/${season}/${eventCode}`, params);
    }

    async getTeamSeasonMatches(season, teamNumber) {
        return this.request(`/teams/${teamNumber}/matches/${season}`);
    }

    async getHistoricalMatches(teamNumber) {
        return this.request(`/teams/${teamNumber}/historical-matches`);
    }

    async getTeamEventResults(season, teamNumber) {
        try {
            const eventsResponse = await this.getEvents(season, null, teamNumber);
            const events = eventsResponse.events || [];
            
            let allMatches = [];
            
            for (const event of events) {
                const [qualMatches, playoffMatches] = await Promise.all([
                    this.getEventMatches(season, event.code, 'qual'),
                    this.getEventMatches(season, event.code, 'playoff')
                ]);

                const matches = [
                    ...(qualMatches.matches || []),
                    ...(playoffMatches.matches || [])
                ];

                // Fixed the team array access
                const processedMatches = matches
                    .filter(match => {
                        if (!match.teams || !match.teams.red || !match.teams.blue) return false;
                        const allTeams = [
                            ...(Array.isArray(match.teams.red) ? match.teams.red : [match.teams.red]),
                            ...(Array.isArray(match.teams.blue) ? match.teams.blue : [match.teams.blue])
                        ];
                        return allTeams.includes(teamNumber.toString());
                    })
                    .map(match => ({
                        matchNumber: match.matchNumber,
                        tournamentLevel: match.tournamentLevel,
                        description: match.description,
                        red: {
                            teams: Array.isArray(match.teams.red) ? match.teams.red : [match.teams.red],
                            score: match.scoreRedFinal || 0
                        },
                        blue: {
                            teams: Array.isArray(match.teams.blue) ? match.teams.blue : [match.teams.blue],
                            score: match.scoreBlueFinal || 0
                        },
                        eventCode: event.code,
                        eventName: event.name
                    }));

                allMatches = [...allMatches, ...processedMatches];
            }
            
            return { matches: allMatches };
        } catch (error) {
            console.error('Error fetching team event results:', error);
            throw error;
        }
    }

    async getHistoricalMatches(teamNumber) {
        const seasons = [2020, 2021, 2022, 2023, 2024];
        const allMatches = {};
        
        for (const season of seasons) {
            try {
                const results = await this.getTeamEventResults(season, teamNumber);
                allMatches[season] = results.matches;
            } catch (error) {
                console.warn(`No data found for season ${season}`);
                allMatches[season] = [];
            }
        }
        
        return { matches: allMatches };
    }

    async getHistoricalEPA(teamNumber) {
            return this.request(`/teams/${teamNumber}/historical-epa`);
    }

    async getMatches(season, eventCode) {
        const response = await fetch(`${this.baseUrl}/api/v2.0/${season}/matches/${eventCode}`);
        if (!response.ok) {
            throw new Error('Failed to fetch matches');
        }
        return await response.json();
    }

    async getPrediction( season, eventCode, redTeams, blueTeams, teamEpas, matchNumber) {
        try {
            const response = await this.axiosInstance.post('/match-prediction', {
                season,
                eventCode,
                redTeams,
                blueTeams,
                teamEpas,
                matchNumber,
            });

            return response.data.prediction;
        } catch (error) {
            console.error('Error getting match prediction:', error);
            return null;
        }
    }

    async getEventPredictionsAndEPA(season, eventCode) {
        try {
            const response = await this.axiosInstance.post('/event-predictions-epa', {
                season,
                eventCode
            });
            return response.data;
        } catch (error) {
            console.error('Error getting event predictions and EPA:', error);
            throw error;
        }
    }

    async getBestAlliancePartner(season, eventCode, teamNumber) {
        try {
            const response = await this.axiosInstance.post('/alliance-matchmaker', {
                season,
                eventCode,
                teamNumber
            });
            return response.data;
        } catch (error) {
            console.error('Error finding alliance partner:', error);
            throw error;
        }
    }

    // Batch alliance matchmaker with precomputed EPAs
    async getBestAlliancePartnersBatch(season, eventCode, teamNumbers, teamEPAs = {}) {
        try {
            const response = await this.axiosInstance.post('/alliance-matchmaker/batch', {
                season,
                eventCode,
                teamNumbers,
                teamEPAs
            });
            return response.data;
        } catch (error) {
            console.error('Error in batch alliance matchmaker request:', error);
            throw error;
        }
    }
}

export default FTCApi;