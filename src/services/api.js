import axios from 'axios';
import { config } from '../config';
import AwsMatchesApi from './awsMatchesApi.js';

// Use AWS API Gateway for matches, localhost backend for other data
const BASE_URL = 'http://localhost:8000/api';
const AUTH_TOKEN = btoa(`${config.ftcApi.username}:${config.ftcApi.key}`);

const axiosInstance = axios.create({
    baseURL: BASE_URL,
    headers: {
        'Authorization': `Basic ${AUTH_TOKEN}`,
        'Content-Type': 'application/json'
    }
});

// Initialize AWS Matches API service
const awsMatchesApi = new AwsMatchesApi();

const api = {
    // Teams API
    getTeam: async (number, season = config.currentSeason) => {
        const response = await axiosInstance.get(`/teams/${season}`, {
            params: { teamNumber: number }
        });
        return response.data;
    },

    getTeamEvents: async (number, season = config.currentSeason) => {
        const response = await axiosInstance.get(`/events/${season}`, {
            params: { teamNumber: number }
        });
        return response.data;
    },

    // Updated to use AWS matches API
    getTeamMatches: async (number, season = config.currentSeason, eventCode = null, tournamentLevel = null) => {
        try {
            const result = await awsMatchesApi.getTeamMatches(number, season, tournamentLevel);
            
            if (!result.success) {
                throw new Error(result.error);
            }

            // Filter by event if eventCode is provided
            let matches = result.matches;
            if (eventCode) {
                matches = matches.filter(match => match.eventCode === eventCode);
            }

            return {
                matches: matches,
                total: matches.length,
                teamNumber: result.teamNumber,
                season: season,
                eventCode: eventCode,
                tournamentLevel: result.tournamentLevel,
                lastUpdated: result.metadata.lastUpdated
            };
        } catch (error) {
            console.error('Error fetching team matches from AWS:', error);
            // Fallback to localhost backend if AWS fails
            console.log('Falling back to localhost backend for team matches');
            const response = await axiosInstance.get(`/schedule/${season}/${eventCode}/${config.defaultTournamentLevel}`, {
                params: {
                    teamNumber: number
                }
            });
            return response.data;
        }
    },

    // New method for getting event matches using AWS
    getEventMatches: async (season = config.currentSeason, eventCode, tournamentLevel = null) => {
        try {
            const result = await awsMatchesApi.getEventMatches(season, eventCode, tournamentLevel);
            
            if (!result.success) {
                throw new Error(result.error);
            }

            return {
                matches: result.matches,
                total: result.total,
                eventCode: result.eventCode,
                season: season,
                tournamentLevel: result.tournamentLevel,
                lastUpdated: result.metadata.lastUpdated
            };
        } catch (error) {
            console.error('Error fetching event matches from AWS:', error);
            
            // Return a safe structure with empty matches array instead of throwing
            return {
                matches: [],
                total: 0,
                eventCode: eventCode,
                season: season,
                tournamentLevel: tournamentLevel,
                lastUpdated: new Date().toISOString(),
                error: error.message
            };
        }
    },

    // New method for getting match details with EPA data
    getMatchDetails: async (matchId) => {
        try {
            const result = await awsMatchesApi.getMatchDetails(matchId);
            
            if (!result.success) {
                throw new Error(result.error);
            }

            return {
                match: result.match,
                teamEPAs: result.teamEPAs,
                lastUpdated: result.metadata.lastUpdated
            };
        } catch (error) {
            console.error('Error fetching match details from AWS:', error);
            throw error;
        }
    },

    // New method for getting match predictions
    getMatchPredictions: async (matchId) => {
        try {
            const result = await awsMatchesApi.getMatchPredictions(matchId);
            
            if (!result.success) {
                throw new Error(result.error);
            }

            return {
                match: result.match,
                predictions: result.predictions,
                lastUpdated: result.metadata.lastUpdated
            };
        } catch (error) {
            console.error('Error fetching match predictions from AWS:', error);
            throw error;
        }
    },

    // New method for getting event match statistics
    getEventMatchStats: async (season = config.currentSeason, eventCode) => {
        try {
            const result = await awsMatchesApi.getEventMatchStats(season, eventCode);
            
            if (!result.success) {
                throw new Error(result.error);
            }

            return {
                eventCode: result.eventCode,
                season: result.season,
                stats: result.stats,
                matches: result.matches
            };
        } catch (error) {
            console.error('Error fetching event match statistics from AWS:', error);
            throw error;
        }
    },

    // Helper method to format matches for display
    formatMatchForDisplay: (match) => {
        return awsMatchesApi.formatMatchForDisplay(match);
    },

    // EPA endpoints using AWS
    getEventEPACalculations: async (season, eventCode, eventStartDate = null) => {
        try {
            const result = await awsMatchesApi.getEventEPACalculations(season, eventCode, eventStartDate);
            
            return {
                success: result.success,
                eventCode: result.eventCode,
                season: result.season,
                teamEPAs: result.teamEPAs,
                teamCount: result.teamCount,
                lastUpdated: result.metadata.lastUpdated,
                source: result.metadata.source
            };
        } catch (error) {
            console.error('Error fetching event EPA calculations:', error);
            throw error;
        }
    },

    calculateTeamEPA: async (teamNumber, eventStartDate = null) => {
        try {
            const result = await awsMatchesApi.calculateTeamEPA(teamNumber, eventStartDate);
            
            return {
                success: result.success,
                teamNumber: result.teamNumber,
                historicalEPA: result.historicalEPA,
                epaData: result.epaData,
                lastUpdated: result.metadata.lastUpdated,
                source: result.metadata.source
            };
        } catch (error) {
            console.error('Error calculating team EPA:', error);
            throw error;
        }
    },

    getMatchPredictionWithEPA: async (redTeams, blueTeams, teamEpas = {}) => {
        try {
            const result = await awsMatchesApi.getMatchPredictionWithEPA(redTeams, blueTeams, teamEpas);
            
            return {
                success: result.success,
                redTeams: result.redTeams,
                blueTeams: result.blueTeams,
                prediction: result.prediction,
                teamEpas: result.teamEpas,
                lastUpdated: result.metadata.lastUpdated,
                source: result.metadata.source
            };
        } catch (error) {
            console.error('Error getting match prediction with EPA:', error);
            throw error;
        }
    },

    batchCalculateTeamEPAs: async (teamNumbers, eventStartDate = null) => {
        try {
            const result = await awsMatchesApi.batchCalculateTeamEPAs(teamNumbers, eventStartDate);
            
            return {
                success: result.success,
                teamEPAs: result.teamEPAs,
                lastUpdated: result.metadata.lastUpdated,
                source: result.metadata.source
            };
        } catch (error) {
            console.error('Error batch calculating team EPAs:', error);
            throw error;
        }
    },

    // Expose the AWS matches API instance for debugging
    awsMatchesApi: awsMatchesApi,

    // Legacy EPA endpoints (for backward compatibility)

    searchTeams: async (season = config.currentSeason, state = '', search = '') => {
        const params = {};
        if (state) params.state = state;
        if (search) {
            const isNumber = !isNaN(search) && !isNaN(parseFloat(search));
            if (isNumber) {
                params.teamNumber = parseInt(search);
            } else {
                params.search = search;
            }
        }
        
        const response = await axiosInstance.get(`/teams/${season}`, { params });
        return response.data;
    },

    searchEvents: async (params = { season: config.currentSeason }) => {
        // If params is just a number, treat it as the season
        const season = typeof params === 'number' ? params : (params.season || config.currentSeason);
        const response = await axiosInstance.get(`/events/${season}`, { params: typeof params === 'object' ? params : {} });
        // Ensure we always return an array for filtering
        if (response.data && Array.isArray(response.data)) {
            return response.data;
        } else if (response.data && response.data.events && Array.isArray(response.data.events)) {
            return response.data.events;
        } else {
            console.warn('Events data is not in expected format:', response.data);
            return [];
        }
    },

    getEvent: async (season = config.currentSeason, eventCode) => {
        const response = await axiosInstance.get(`/events/${season}/${eventCode}`);
        return response.data;
    },

    getEventDetails: async (season = config.currentSeason, eventCode) => {
        const [eventData, rankings] = await Promise.all([
            axiosInstance.get(`/events/${season}/${eventCode}`),
            axiosInstance.get(`/rankings/${season}/${eventCode}`)
        ]);
        return {
            ...eventData.data,
            rankings: rankings.data
        };
    }
};

export default api;