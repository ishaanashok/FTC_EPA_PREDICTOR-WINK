import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import FTCApi from '../services/FTCApi';
import '../styles/TeamDetails.css';

const ftcApi = new FTCApi();

function TeamDetails() {
    const { teamNumber } = useParams();
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
                
                const [teamResponse, eventsResponse, epaResponse] = await Promise.all([
                    ftcApi.getTeams(2024, { teamNumber }),
                    ftcApi.getEvents(2024, null, teamNumber),
                    ftcApi.getHistoricalEPA(teamNumber).catch(err => {
                        console.warn('EPA fetch failed:', err);
                        return null;
                    })
                ]);

                console.log('Team response:', teamResponse);
                console.log('Events response:', eventsResponse);
                console.log('EPA response:', epaResponse);

                // Handle team data - getTeams now returns { teams: [...] }
                if (teamResponse?.teams?.length > 0) {
                    setTeamInfo(teamResponse.teams[0]);
                }

                // Handle events data
                if (eventsResponse?.events) {
                    setEvents(eventsResponse.events);
                } else if (Array.isArray(eventsResponse)) {
                    setEvents(eventsResponse);
                }

                // Handle EPA data - the actual API response structure
                if (epaResponse?.epaHistory?.length > 0) {
                    const epaData = epaResponse.epaHistory[0];
                    console.log('EPA Data from API:', epaData);
                    console.log('Season EPAs:', epaData.seasonEPAs);
                    
                    setEpa(Number(epaData.historicalEPA).toFixed(2));
                    setEpaDetails({
                        historicalEPA: Number(epaData.historicalEPA).toFixed(2),
                        currentSeasonEPA: Number(epaData.currentSeasonEPA).toFixed(2),
                        totalMatches: epaData.totalMatches,
                        dataQuality: epaData.dataQuality,
                        seasonEPAs: epaData.seasonEPAs,
                        calculatedAt: epaData.calculatedAt
                    });
                    
                    console.log('Set EPA Details:', {
                        historicalEPA: Number(epaData.historicalEPA).toFixed(2),
                        currentSeasonEPA: Number(epaData.currentSeasonEPA).toFixed(2),
                        totalMatches: epaData.totalMatches,
                        dataQuality: epaData.dataQuality,
                        seasonEPAs: epaData.seasonEPAs,
                        calculatedAt: epaData.calculatedAt
                    });
                } else if (epaResponse?.historicalEPA !== undefined) {
                    setEpa(Number(epaResponse.historicalEPA).toFixed(2));
                    setEpaDetails(null);
                } else if (epaResponse?.epa !== undefined) {
                    setEpa(Number(epaResponse.epa).toFixed(2));
                    setEpaDetails(null);
                } else if (typeof epaResponse === 'number') {
                    setEpa(Number(epaResponse).toFixed(2));
                    setEpaDetails(null);
                } else {
                    console.warn('EPA data not found in expected format:', epaResponse);
                    setEpa('N/A');
                    setEpaDetails(null);
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
                                                <p><strong>2024 Season EPA:</strong> {epaDetails.currentSeasonEPA}</p>
                                                <p><strong>Total Matches:</strong> {epaDetails.totalMatches}</p>
                                                <p><strong>Data Quality:</strong> {epaDetails.dataQuality}</p>
                                                
                                                {epaDetails.seasonEPAs && (
                                                    <div className="season-epas">
                                                        <p><strong>Season EPAs:</strong></p>
                                                        <ul>
                                                            {epaDetails.seasonEPAs['2024'] && (
                                                                <li>2024: {Number(epaDetails.seasonEPAs['2024']).toFixed(2)}</li>
                                                            )}
                                                            {epaDetails.seasonEPAs['2023'] && (
                                                                <li>2023: {Number(epaDetails.seasonEPAs['2023']).toFixed(2)}</li>
                                                            )}
                                                            {epaDetails.seasonEPAs['2022'] && (
                                                                <li>2022: {Number(epaDetails.seasonEPAs['2022']).toFixed(2)}</li>
                                                            )}
                                                            {epaDetails.seasonEPAs['2021'] && (
                                                                <li>2021: {Number(epaDetails.seasonEPAs['2021']).toFixed(2)}</li>
                                                            )}
                                                            {epaDetails.seasonEPAs['2020'] && (
                                                                <li>2020: {Number(epaDetails.seasonEPAs['2020']).toFixed(2)}</li>
                                                            )}
                                                        </ul>
                                                    </div>
                                                )}
                                            </>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    <div className="events-section">
                        <h2>Events (2024 Season)</h2>
                        <div className="events-grid">
                            {events.map((event, index) => (
                                <div key={event.eventCode || event.code || index} className="event-card">
                                    <h3>{event.eventName || event.name}</h3>
                                    <p>Date: {formatDate(event.dateStart || event.startDate)} - {formatDate(event.dateEnd || event.endDate)}</p>
                                    <p>Location: {event.venue}</p>
                                    <p>City: {event.city}</p>
                                    <p>Type: {event.eventType || event.type}</p>
                                </div>
                            ))}
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