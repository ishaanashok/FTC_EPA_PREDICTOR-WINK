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

    // Remove the calculateEPA function as it's now handled by the backend

    useEffect(() => {
        const fetchTeamData = async () => {
            try {
                setLoading(true);
                const [teamResponse, eventsResponse, epaResponse] = await Promise.all([
                    ftcApi.getTeams(2024, { teamNumber }),
                    ftcApi.getEvents(2024, null, teamNumber),
                    ftcApi.getHistoricalEPA(teamNumber)  // Uncomment this line
                ]);

                if (teamResponse.teams?.length > 0) {
                    setTeamInfo(teamResponse.teams[0]);
                }
                setEvents(eventsResponse.events || []);
                // Add null check for EPA response
                setEpa(epaResponse?.historicalEPA?.toFixed(2) || '0.00');
            } catch (err) {
                setError('Failed to fetch team data');
                console.error('Error:', err);
            } finally {
                setLoading(false);
            }
        };

        fetchTeamData();
    }, [teamNumber]);

    return (
        <div className="team-details-container">
            {loading && <div className="loading">Loading team details...</div>}
            {error && <div className="error">{error}</div>}
            
            {!loading && !error && (
                <>
                    {teamInfo && (
                        <div className="team-header">
                            <h1>Team {teamInfo.teamNumber}</h1>
                            <h2>{teamInfo.nameShort}</h2>
                            <p>{teamInfo.city}, {teamInfo.stateProv}, {teamInfo.country}</p>
                            {epa !== null && (
                                <div className="team-epa">
                                    <h3>EPA: {epa}</h3>
                                </div>
                            )}
                        </div>
                    )}

                    <div className="events-section">
                        <h2>Events (2024 Season)</h2>
                        <div className="events-grid">
                            {events.map(event => (
                                <div key={event.code} className="event-card">
                                    <h3>{event.name}</h3>
                                    <p>Date: {new Date(event.startDate).toLocaleDateString()} - {new Date(event.endDate).toLocaleDateString()}</p>
                                    <p>Location: {event.venue}</p>
                                    <p>Type: {event.type}</p>
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