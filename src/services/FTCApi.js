import axios from 'axios';
import { config } from '../config.js';
import { fetchAuthSession } from 'aws-amplify/auth';

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

    // Helper method to get authentication headers
    async getAuthHeaders() {
        try {
            const session = await fetchAuthSession();
            const idToken = session.tokens?.idToken?.toString();
            
            if (idToken) {
                return {
                    'Authorization': `Bearer ${idToken}`,
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                };
            }
            
            return {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            };
        } catch (error) {
            console.warn('Failed to get auth session:', error);
            return {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            };
        }
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
        try {
            // Call AWS Events API for event details - using /api/events path
            const response = await this.axiosInstance.get(`/api/events/${eventCode}`, {
                params: { season: season }
            });
            
            if (response.data && response.data.success && response.data.event) {
                // Return in the expected format for the EventDetails component
                return {
                    events: [response.data.event]
                };
            } else {
                throw new Error('Event not found or invalid response format');
            }
        } catch (error) {
            console.error(`Failed to get event info for ${eventCode}:`, error);
            throw error;
        }
    }

    async getEventRankings(season, eventCode) {
        return this.request(`/events/${season}/${eventCode}/rankings`);
    }

    // Season Data methods
    async getSeasonSummary(season) {
        return this.request(`/season/${season}`);
    }

    async getEvents(season, eventCode = null, teamNumber = null) {
        try {
            console.log('Calling AWS events API with params:', { season, eventCode, teamNumber });
            
            // Call AWS Events API directly - using /api/events path as defined in CloudFormation
            const queryParams = { season };
            if (eventCode) queryParams.eventCode = eventCode;
            if (teamNumber) queryParams.teamNumber = teamNumber;
            
            const response = await this.axiosInstance.get('/api/events', { params: queryParams });
            
            console.log('AWS API response:', response);
            console.log('AWS API response.data:', response.data);
            console.log('AWS API response.data type:', typeof response.data);
            
            // Handle different possible response structures
            if (response.data) {
                // Check if the response data is directly an array of events
                if (Array.isArray(response.data)) {
                    console.log('Response data is array, returning:', response.data.length, 'events');
                    return { events: response.data };
                }
                
                // Check if response.data.success exists and events are nested
                if (response.data.success !== undefined) {
                    const events = response.data.events || [];
                    console.log('Response has success field, returning:', events.length, 'events');
                    return { events: events };
                }
                
                // Check if events are directly in response.data
                if (response.data.events) {
                    console.log('Response has events field, returning:', response.data.events.length, 'events');
                    return { events: response.data.events };
                }
                
                // If response.data itself looks like an events object
                if (response.data.code || response.data.name) {
                    console.log('Response data looks like a single event, wrapping in array');
                    return { events: [response.data] };
                }
                
                // Last resort - return the whole response.data as events
                console.log('Using whole response.data as events');
                return { events: response.data };
            } else {
                throw new Error('No data in response');
            }
        } catch (error) {
            console.error('AWS API Error Details:', {
                message: error.message,
                status: error.response?.status,
                statusText: error.response?.statusText,
                data: error.response?.data,
                config: error.config
            });
            
            // Check if it's an authentication error and provide helpful message
            if (error.response && error.response.status === 401) {
                throw new Error('AWS API authentication failed. Check if API Gateway requires authentication or if credentials are needed.');
            }
            
            if (error.response && error.response.status === 403) {
                throw new Error('AWS API access forbidden. Check if API Gateway methods are properly configured.');
            }
            
            throw error;
        }
    }

    async getTeams(season, params = {}) {
        try {
            // Call AWS Teams API directly - using /api/teams path
            const queryParams = { season, ...params };
            const response = await this.axiosInstance.get('/api/teams', { params: queryParams });
            
            if (response.data && response.data.success) {
                return response.data.teams || [];
            } else {
                throw new Error('Failed to get teams or invalid response format');
            }
        } catch (error) {
            console.error('Failed to get teams:', error);
            throw error;
        }
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
        console.log(`Getting real data for event ${eventCode}, season ${season}`);
        
        // Get event details from AWS
        let eventDetails = null;
        try {
            eventDetails = await this.getEventInfo(season, eventCode);
            console.log('Event info fetched from AWS:', eventDetails);
        } catch (eventError) {
            console.error('Failed to get event info from AWS:', eventError);
            // Create minimal event details if API fails
            eventDetails = {
                events: [{
                    code: eventCode,
                    name: `Event ${eventCode}`,
                    dateStart: '2024-03-15',
                    venue: 'Event Venue',
                    city: 'Event City',
                    stateProv: 'Unknown'
                }]
            };
        }
        
        // Get teams from the teams API that we just fixed
        console.log('Fetching teams from AWS Teams API...');
        const teamsResponse = await this.getTeams(season, { eventCode });
        const teams = teamsResponse || [];
        console.log('Teams fetched from real API:', teams.length, 'teams');
        
        // Get matches for the event
        let matches = [];
        try {
            const matchesResponse = await this.axiosInstance.get(`/api/matches`, {
                params: { season, eventCode }
            });
            matches = matchesResponse.data?.matches || [];
            console.log('Matches fetched:', matches.length, 'matches');
        } catch (matchError) {
            console.warn('Failed to get matches:', matchError);
            matches = [];
        }
        
        // Get EPAs from EPA API
        const teamEPAs = {};
        try {
            const epaResponse = await this.axiosInstance.get(`/api/epa`, {
                params: { season, eventCode }
            });
            if (epaResponse.data && epaResponse.data.success) {
                Object.assign(teamEPAs, epaResponse.data.epas || {});
            }
        } catch (epaError) {
            console.warn('Failed to get EPAs, using defaults:', epaError);
            // Set default EPAs for teams
            teams.forEach(team => {
                teamEPAs[team.teamNumber.toString()] = 50.0;
            });
        }
        
        console.log('Final result - Teams:', teams.length, 'Matches:', matches.length, 'EPAs:', Object.keys(teamEPAs).length);
        
        return {
            success: true,
            eventDetails: eventDetails,
            eventCode,
            season,
            teams: teams,
            matches: matches,
            predictions: [], // Predictions would need a separate endpoint
            teamEPAs: teamEPAs,
            teamCount: teams.length,
            lastUpdated: new Date().toISOString(),
            source: 'aws-real-data'
        };
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

    // Admin Methods
    async addMatches(matches, season, eventCode) {
        try {
            console.log('Adding matches to database via AWS Lambda:', { matches, season, eventCode });
            
            // Get authentication headers with JWT token
            const headers = await this.getAuthHeaders();
            console.log('Using auth headers for admin request');
            
            // Use the AWS API Gateway endpoint for admin functions with auth headers
            const response = await this.axiosInstance.post('/admin/matches', {
                matches,
                season,
                eventCode
            }, {
                headers
            });
            
            return response.data;
        } catch (error) {
            console.error('Error adding matches via AWS Lambda:', error);
            
            // Provide more specific error information
            if (error.response?.status === 403) {
                throw new Error('Admin authorization required. Please ensure you are logged in as an administrator.');
            } else if (error.response?.status === 404) {
                throw new Error('Admin API endpoint not found. The Lambda function may not be deployed yet.');
            } else {
                throw new Error(error.response?.data?.message || error.message || 'Failed to add matches');
            }
        }
    }

    // Admin method to delete a match
    async deleteMatch(matchId, season, eventCode) {
        try {
            const headers = await this.getAuthHeaders();
            
            const response = await this.axiosInstance.delete(`/admin/matches/${matchId}`, {
                headers,
                data: {
                    season,
                    eventCode
                }
            });
            
            return response.data;
        } catch (error) {
            console.error('Error deleting match via AWS Lambda:', error);
            
            // Provide more specific error information
            if (error.response?.status === 403) {
                throw new Error('Admin authorization required. Please ensure you are logged in as an administrator.');
            } else if (error.response?.status === 404) {
                throw new Error('Match not found or admin API endpoint not available.');
            } else {
                throw new Error(error.response?.data?.message || error.message || 'Failed to delete match');
            }
        }
    }

    // Admin method to get existing matches for an event
    async getEventMatches(season, eventCode) {
        try {
            const headers = await this.getAuthHeaders();
            
            const response = await this.axiosInstance.get(`/admin/matches/${season}/${eventCode}`, {
                headers
            });
            
            return response.data;
        } catch (error) {
            console.error('Error fetching event matches:', error);
            
            if (error.response?.status === 403) {
                throw new Error('Admin authorization required. Please ensure you are logged in as an administrator.');
            } else if (error.response?.status === 404) {
                throw new Error('No matches found for this event or admin API endpoint not available.');
            } else {
                throw new Error(error.response?.data?.message || error.message || 'Failed to fetch event matches');
            }
        }
    }

    // Admin method to update an existing match
    async updateMatch(matchId, matchData, season, eventCode) {
        try {
            const headers = await this.getAuthHeaders();
            
            const response = await this.axiosInstance.put(`/admin/matches/${matchId}`, {
                match: matchData,
                season,
                eventCode
            }, {
                headers
            });
            
            return response.data;
        } catch (error) {
            console.error('Error updating match:', error);
            
            if (error.response?.status === 403) {
                throw new Error('Admin authorization required. Please ensure you are logged in as an administrator.');
            } else if (error.response?.status === 404) {
                throw new Error('Match not found or admin API endpoint not available.');
            } else {
                throw new Error(error.response?.data?.message || error.message || 'Failed to update match');
            }
        }
    }
}

export default FTCApi;