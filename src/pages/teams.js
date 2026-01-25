import React, { useState, useEffect } from 'react';
import FTCApi from '../services/FTCApi';  // Fixed import path
import '../styles/Teams.css';
import { Button } from '@mui/material';
import { useNavigate } from 'react-router-dom';

const ftcApi = new FTCApi();

function Teams() {
    const navigate = useNavigate();
    const [teams, setTeams] = useState([]);
    const [filteredTeams, setFilteredTeams] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [teamNumber, setTeamNumber] = useState('');
    const [currentPage, setCurrentPage] = useState(1);
    const [allTeams, setAllTeams] = useState([]);

    const handleKeyPress = (e) => {
        if (e.key === 'Enter') {
            handleSearch();
        }
    };

    const handleSearch = async () => {
        const searchParams = {};
        if (teamNumber) {
            searchParams.teamNumber = teamNumber;
        }
        await fetchTeams(searchParams);
    };

    const fetchTeams = async (searchParams = {}) => {
        try {
            setLoading(true);
            if (searchParams.teamNumber) {
                const params = { page: currentPage, ...searchParams };
                const response = await ftcApi.getTeams(2025, params);
                const teamsData = response?.teams || [];
                setTeams(teamsData);
                setFilteredTeams(teamsData);
            } else if (searchParams.search) {
                const response = await ftcApi.getTeams(2025, {});
                const allTeamsData = response?.teams || [];
                setAllTeams(allTeamsData);
                const filtered = allTeamsData.filter(team =>
                    team.nameShort && team.nameShort.toLowerCase().includes(searchParams.search.toLowerCase())
                );
                setFilteredTeams(filtered);
                setTeams(filtered);
            } else {
                const params = { page: currentPage };
                const response = await ftcApi.getTeams(2025, params);
                const teamsData = response?.teams || [];
                setTeams(teamsData);
                setFilteredTeams(teamsData);
            }
        } catch (err) {
            setError('Failed to fetch teams');
            console.error('Error fetching teams:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchTeams();
    }, [currentPage]);

    return (
        <div className="teams-container">
            <div className="teams-header">
                <h2>FTC Teams</h2>
                <div className="search-filters">
                    <div className="search-bar">
                        <input
                            type="number"
                            placeholder="Search by team number"
                            value={teamNumber}
                            onChange={(e) => {
                                setTeamNumber(e.target.value);
                            }}
                            onKeyPress={handleKeyPress}
                            className="search-filter"
                        />
                        <Button
                            variant="contained"
                            onClick={handleSearch}
                            disabled={!teamNumber}
                            className="search-button"
                        >
                            Search
                        </Button>
                    </div>
                </div>
            </div>

            {loading && <div className="loading">Loading teams...</div>}
            {error && <div className="error">{error}</div>}
            
            {!loading && !error && (
                <>
                    <div className="teams-grid">
                        {filteredTeams.map(team => (
                            <div 
                                key={team.teamNumber} 
                                className="team-card"
                                onClick={() => navigate(`/team/${team.teamNumber}`)}
                            >
                                <h3>Team {team.teamNumber}</h3>
                                <p className="team-name">{team.nameShort}</p>
                                <p className="team-location">{team.city}{team.state && `, ${team.state}`}</p>
                                <p className="team-country">{team.country}</p>
                            </div>
                        ))}
                    </div>

                    <div className="pagination">
                        <button 
                            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                            disabled={currentPage === 1 || loading}
                        >
                            Previous
                        </button>
                        <span>Page {currentPage}</span>
                        <button 
                            onClick={() => setCurrentPage(p => p + 1)}
                            disabled={teams.length === 0 || loading}
                        >
                            Next
                        </button>
                    </div>
                </>
            )}
        </div>
    );
}

export default Teams;