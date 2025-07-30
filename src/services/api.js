import axios from 'axios';
import { config } from '../config';
import AwsMatchesApi from './awsMatchesApi.js';

// Use AWS API Gateway for all data - no more localhost backend
const AWS_BASE_URL = config.apiBaseUrl;

const awsAxiosInstance = axios.create({
    baseURL: AWS_BASE_URL,
    headers: {
        'Content-Type': 'application/json'
    }
});

// Initialize AWS services
const awsMatchesApi = new AwsMatchesApi();

const api = {
    // Teams API - now using AWS Lambda
    getTeam: async (number, season = config.currentSeason) => {
        try {
            const response = await awsAxiosInstance.get('/teams', {
                params: { teamNumber: number, season: season }
            });
            return response.data;
        } catch (error) {
            console.error('Error fetching team from AWS:', error);
            throw error;
        }
    },

    getTeamEvents: async (number, season = config.currentSeason) => {
        try {
            const response = await awsAxiosInstance.get('/events', {
                params: { teamNumber: number, season: season }
            });
            return response.data;
        } catch (error) {
            console.error('Error fetching team events from AWS:', error);
            throw error;
        }
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
            // Return empty result instead of trying localhost fallback
            return {
                matches: [],
                total: 0,
                teamNumber: number,
                season: season,
                eventCode: eventCode,
                tournamentLevel: tournamentLevel,
                lastUpdated: new Date().toISOString(),
                error: error.message
            };
        }
    },

    // New method for getting event matches using AWS
    getEventMatches: async (season = config.currentSeason, eventCode, tournamentLevel = null, includeWinProbability = false) => {
        try {
            console.log('API: getEventMatches called with:', { season, eventCode, tournamentLevel, includeWinProbability });
            
            const result = await awsMatchesApi.getEventMatches(season, eventCode, tournamentLevel, includeWinProbability);
            
            console.log('API: awsMatchesApi.getEventMatches result:', result);
            
            if (!result.success) {
                throw new Error(result.error);
            }

            console.log('API: result.matches length:', result.matches?.length || 0);
            if (result.matches && result.matches.length > 0) {
                console.log('API: First match winProbability:', result.matches[0].winProbability);
            }

            return {
                matches: result.matches,
                total: result.total,
                eventCode: result.eventCode,
                season: season,
                tournamentLevel: result.tournamentLevel,
                lastUpdated: result.metadata?.lastUpdated
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
        try {
            const params = { season };
            if (state) params.state = state;
            if (search) {
                const isNumber = !isNaN(search) && !isNaN(parseFloat(search));
                if (isNumber) {
                    params.teamNumber = parseInt(search);
                } else {
                    params.search = search;
                }
            }
            
            const response = await awsAxiosInstance.get('/teams', { params });
            return response.data;
        } catch (error) {
            console.error('Error searching teams from AWS:', error);
            throw error;
        }
    },

    searchEvents: async (params = { season: config.currentSeason }) => {
        try {
            // If params is just a number, treat it as the season
            const season = typeof params === 'number' ? params : (params.season || config.currentSeason);
            const queryParams = { season };
            
            // Add other filters if they exist
            if (typeof params === 'object') {
                if (params.eventCode) queryParams.eventCode = params.eventCode;
                if (params.teamNumber) queryParams.teamNumber = params.teamNumber;
                if (params.limit) queryParams.limit = params.limit;
            }
            
            const response = await awsAxiosInstance.get('/events', { params: queryParams });
            const data = response.data;
            
            // Ensure we always return an array for filtering
            if (data && data.success && Array.isArray(data.events)) {
                return data.events;
            } else if (data && Array.isArray(data)) {
                return data;
            } else {
                console.warn('Events data is not in expected format:', data);
                return [];
            }
        } catch (error) {
            console.error('Error searching events from AWS:', error);
            // Return empty array instead of throwing to prevent UI crashes
            return [];
        }
    },

    getEvent: async (season = config.currentSeason, eventCode) => {
        try {
            const response = await awsAxiosInstance.get('/events', {
                params: { season, eventCode }
            });
            const data = response.data;
            
            if (data && data.success && data.events && data.events.length > 0) {
                return data.events[0];
            } else {
                throw new Error(`Event ${eventCode} not found for season ${season}`);
            }
        } catch (error) {
            console.error('Error fetching event from AWS:', error);
            throw error;
        }
    },

    getEventDetails: async (season = config.currentSeason, eventCode) => {
        try {
            const [eventData, rankings] = await Promise.all([
                awsAxiosInstance.get('/events', { params: { season, eventCode } }),
                // Note: Rankings might need a separate endpoint or be included in event data
                awsAxiosInstance.get('/events', { params: { season, eventCode } })
            ]);
            return {
                ...eventData.data,
                rankings: rankings.data
            };
        } catch (error) {
            console.error('Error fetching event details from AWS:', error);
            throw error;
        }
    }
};

export default api;