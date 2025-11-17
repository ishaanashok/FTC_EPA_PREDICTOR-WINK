import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import FTCApi from '../services/FTCApi';
import '../styles/TeamDetails.css';

const ftcApi = new FTCApi();

function TeamDetails() {
    const { teamNumber } = useParams();
    const navigate = useNavigate();
    const [events, setEvents] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [teamInfo, setTeamInfo] = useState(null);
    const [epa, setEpa] = useState(null);
    const [epaDetails, setEpaDetails] = useState(null);

    useEffect(() => {
        const fetchTeamData = async () => {
            try {
                setLoading(true);
                console.log('Fetching data for team:', teamNumber);
                
                // Fetch team data (which includes embedded historicEPA) and events
                const [teamResponse, eventsResponse] = await Promise.all([
                    ftcApi.getTeams(2025, { teamNumber }),
                    ftcApi.getEvents(2025, null, teamNumber)
                ]);

                console.log('Team response:', teamResponse);
                console.log('Events response:', eventsResponse);

                // Handle team data - getTeams now returns { teams: [...] }
                if (teamResponse?.teams?.length > 0) {
                    const team = teamResponse.teams[0];
                    setTeamInfo(team);
                    
                    // NEW: Extract historicEPA from team data (embedded)
                    if (team.historicEPA) {
                        const historicEPA = team.historicEPA;
                        console.log('Historic EPA from team:', historicEPA);
                        
                        setEpa(Number(historicEPA.historicEPA).toFixed(2));
                        
                        // Build EPA details from new structure
                        const seasonEPAs = {};
                        if (historicEPA.seasonBreakdown) {
                            Object.keys(historicEPA.seasonBreakdown).forEach(season => {
                                const seasonData = historicEPA.seasonBreakdown[season];
                                seasonEPAs[season] = seasonData.averageEPA;
                            });
                        }
                        
                        setEpaDetails({
                            historicalEPA: Number(historicEPA.historicEPA).toFixed(2),
                            currentSeasonEPA: team.currentSeasonEPA ? 
                                Number(team.currentSeasonEPA.averageEPA).toFixed(2) : 'N/A',
                            totalMatches: historicEPA.totalHistoricalMatches || 0,
                            dataQuality: historicEPA.calculationMethod || 'weighted_average',
                            seasonEPAs: seasonEPAs,
                            seasonBreakdown: historicEPA.seasonBreakdown,
                            calculatedAt: historicEPA.calculatedAt,
                            seasonsWithData: historicEPA.seasonsWithData
                        });
                        
                        console.log('Set EPA Details from new structure:', {
                            historicalEPA: Number(historicEPA.historicEPA).toFixed(2),
                            totalMatches: historicEPA.totalHistoricalMatches,
                            seasonEPAs: seasonEPAs
                        });
                    } else {
                        console.warn('No historicEPA found in team data');
                        setEpa('N/A');
                        setEpaDetails(null);
                    }
                } else {
                    console.warn('No team data found');
                    setEpa('N/A');
                    setEpaDetails(null);
                }

                // Handle events data
                if (eventsResponse?.events) {
                    setEvents(eventsResponse.events);
                } else if (Array.isArray(eventsResponse)) {
                    setEvents(eventsResponse);
                }
            } catch (err) {
                setError('Failed to fetch team data');
                console.error('Error fetching team data:', err);
            } finally {
                setLoading(false);
            }
        };

        if (teamNumber) {
            fetchTeamData();
        }
    }, [teamNumber]);

    const formatDate = (dateString) => {
        if (!dateString) return 'N/A';
        try {
            const date = new Date(dateString);
            return date.toLocaleDateString();
        } catch (err) {
            return 'Invalid Date';
        }
    };

    return (
        <div className="team-details-container">
            {loading && <div className="loading">Loading team details...</div>}
            {error && <div className="error">{error}</div>}
            
            {!loading && !error && (
                <>
                    {teamInfo && (
                        <div className="team-header">
                            <h1>Team {teamInfo.teamNumber}</h1>
                            <h2>{teamInfo.teamName || teamInfo.nameShort || teamInfo.teamNameShort}</h2>
                            <p>{teamInfo.city}, {teamInfo.state || teamInfo.stateProv}, {teamInfo.country}</p>
                            <p>School: {teamInfo.schoolName}</p>
                            <p>Rookie Year: {teamInfo.rookieYear}</p>
                            {epa && epa !== 'N/A' && (
                                <div className="team-epa">
                                    <h3>EPA Statistics</h3>
                                    <div className="epa-details">
                                        <p><strong>Historical EPA:</strong> {epa}</p>
                                        {epaDetails && (
                                            <>
                                                <p><strong>Current Season EPA (2025):</strong> {epaDetails.currentSeasonEPA}</p>
                                                <p><strong>Total Historical Matches:</strong> {epaDetails.totalMatches}</p>
                                                <p><strong>Calculation Method:</strong> {epaDetails.dataQuality}</p>
                                                {epaDetails.seasonsWithData && (
                                                    <p><strong>Seasons with Data:</strong> {epaDetails.seasonsWithData.join(', ')}</p>
                                                )}
                                                
                                                {epaDetails.seasonBreakdown && (
                                                    <div className="season-epas">
                                                        <p><strong>Season Breakdown:</strong></p>
                                                        <ul>
                                                            {Object.keys(epaDetails.seasonBreakdown)
                                                                .sort((a, b) => b - a) // Sort descending (newest first)
                                                                .map(season => {
                                                                    const data = epaDetails.seasonBreakdown[season];
                                                                    return (
                                                                        <li key={season}>
                                                                            <strong>{season}:</strong> Avg {Number(data.averageEPA).toFixed(2)} 
                                                                            {' '}(Min: {Number(data.minEPA).toFixed(2)}, 
                                                                            Max: {Number(data.maxEPA).toFixed(2)}, 
                                                                            Matches: {data.totalMatches})
                                                                        </li>
                                                                    );
                                                                })}
                                                        </ul>
                                                    </div>
                                                )}
                                                
                                                {epaDetails.calculatedAt && (
                                                    <p><strong>Last Calculated:</strong> {new Date(epaDetails.calculatedAt).toLocaleString()}</p>
                                                )}
                                            </>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    <div className="events-section">
                        <h2>Events (2025 Season)</h2>
                        <div className="events-grid">
                            {events.map((event, index) => {
                                const eventCode = event.eventCode || event.code;
                                const eventSeason = event.season || 2025;
                                
                                return (
                                    <div 
                                        key={eventCode || index} 
                                        className="event-card clickable"
                                        onClick={() => navigate(`/events/${eventSeason}/${eventCode}`)}
                                        style={{ cursor: 'pointer' }}
                                    >
                                        <h3>{event.eventName || event.name}</h3>
                                        <p className="event-code"><strong>Code:</strong> {eventCode}</p>
                                        <p><strong>Date:</strong> {formatDate(event.dateStart || event.startDate)} - {formatDate(event.dateEnd || event.endDate)}</p>
                                        <p><strong>Location:</strong> {event.venue}</p>
                                        <p><strong>City:</strong> {event.city}, {event.stateprov || event.stateProv || event.state}</p>
                                        <p><strong>Type:</strong> {event.typeName || event.eventType || event.type}</p>
                                    </div>
                                );
                            })}
                        </div>
                        {events.length === 0 && (
                            <p className="no-events">No events found for this team in the current season.</p>
                        )}
                    </div>
                </>
            )}
        </div>
    );
}

export default TeamDetails;