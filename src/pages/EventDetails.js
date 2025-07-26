import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { 
  Typography, 
  Container, 
  Paper, 
  Grid, 
  CircularProgress, 
  Box, 
  Table, 
  TableBody, 
  TableCell, 
  TableContainer, 
  TableHead, 
  TableRow,
  Tabs,
  Tab,
  TableSortLabel
} from '@mui/material';
import FTCApi from '../services/FTCApi';
import { IconButton } from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import VerifiedIcon from '@mui/icons-material/Verified';
import Link from '@mui/material/Link';
import AllianceMatchmaker from '../components/AllianceMatchmaker';

const EventDetails = () => {
  const { season, eventCode } = useParams();
  const [eventDetails, setEventDetails] = useState(null);
  const [teams, setTeams] = useState([]);
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState(0);
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });
  const [teamEPAs, setTeamEPAs] = useState({});
  const ftcApi = new FTCApi();

  const fetchEventData = async () => {
        try {
            setLoading(true);
            setError(null); // Reset error state
            console.log('Fetching data for season:', season, 'event:', eventCode);
            
            const eventData = await ftcApi.getEventPredictionsAndEPA(Number(season), eventCode);
            
            if (!eventData) {
                throw new Error('No data received from server');
            }
            
            console.log('Received event data:', eventData);
            setEventDetails(eventData.eventDetails);
            setTeams(eventData.teams || []);
            setTeamEPAs(eventData.teamEPAs || {});
            
            const matchesArray = eventData.matches || [];
            const predictionsArray = eventData.predictions || [];
            
            const matchesWithPredictions = matchesArray.map(match => ({
                ...match,
                prediction: predictionsArray.find(p => p.matchNumber === match.matchNumber)?.prediction
            }));
            
            setMatches(matchesWithPredictions);
        } catch (err) {
            const errorMessage = err.response?.data?.detail || err.message || 'Failed to fetch event details';
            setError(errorMessage);
            console.error('Error in fetchEventData:', err);
        } finally {
            setLoading(false);
        }
    };

  useEffect(() => {
    if (season && eventCode) {
      fetchEventData();
    }
  }, [season, eventCode]);

  const sortedMatches = React.useMemo(() => {
    // Filter for qualification matches and sort by match number
    const qualificationMatches = matches.filter(match => 
      match.tournamentLevel?.toUpperCase() === "QUALIFICATION"
    );
    
    return [...qualificationMatches].sort((a, b) => {
      const matchNumA = parseInt(a.matchNumber);
      const matchNumB = parseInt(b.matchNumber);
      return matchNumA - matchNumB;
    });
  }, [matches]);

  const [loadingMessage, setLoadingMessage] = useState('Calculating EPAs...');
  const loadingMessages = [
    'Give it a second...',
    'Analyzing your brainwaves...',
    'Decrypting your thoughts...',
    'Crunching the numbers...',
    'Reading the crystal ball...',
    'Consulting the robot overlords...',
  ];
  
  useEffect(() => {
    if (loading) {
      const interval = setInterval(() => {
        setLoadingMessage(prevMessage => {
          const currentIndex = loadingMessages.indexOf(prevMessage);
          const nextIndex = (currentIndex + 1) % loadingMessages.length;
          return loadingMessages[nextIndex];
        });
      }, 2000);
      return () => clearInterval(interval);
    }
  }, [loading]);

  if (loading) return (
    <Box display="flex" flexDirection="column" justifyContent="center" alignItems="center" minHeight="80vh">
      <CircularProgress sx={{ mb: 2 }} />
      <Typography variant="h6" color="text.secondary">
        {loadingMessage}
      </Typography>
    </Box>
  );

  if (error) return <Container><Typography color="error">{error}</Typography></Container>;

  const handleRefresh = async () => {
    if (season && eventCode) {
      setLoading(true);
      await fetchEventData();
    }
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 4 }}>
      <Paper elevation={3} sx={{ p: 3, mb: 4 }}>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Typography variant="h4">
            {eventDetails?.events[0]?.name || 'Event Details'}
          </Typography>
          <IconButton 
            onClick={handleRefresh} 
            disabled={loading}
            sx={{ ml: 2 }}
          >
            <RefreshIcon />
          </IconButton>
        </Box>

        <Tabs value={activeTab} onChange={(e, newValue) => setActiveTab(newValue)} sx={{ mb: 3 }}>
          <Tab label="Event Details" />
          <Tab label="Matches" />
          <Tab label="Alliance Matchmaker" />
        </Tabs>
  
        {activeTab === 0 ? (
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Typography variant="h6">Event Information</Typography>
              <Typography>Date: {eventDetails?.events[0]?.dateStart}</Typography>
              <Typography>Location: {eventDetails?.events[0]?.venue}</Typography>
              <Typography>City: {eventDetails?.events[0]?.city}</Typography>
              <Typography>State: {eventDetails?.events[0]?.stateProv}</Typography>
              <Typography><a href="https://ftc-events.firstinspires.org/services/API">✓ Data Verified by FIRST</a></Typography>
            </Grid>
            
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom>Participating Teams</Typography>
              <TableContainer component={Paper}>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Team Number</TableCell>
                      <TableCell>Team Name</TableCell>
                      <TableCell>Organization</TableCell>
                      <TableCell>Location</TableCell>
                      <TableCell>EPA</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {teams.map((team) => (
                      <TableRow key={team.teamNumber} hover>
                        <TableCell>{team.teamNumber}</TableCell>
                        <TableCell>{team.nameShort || team.nameFull}</TableCell>
                        <TableCell>{team.schoolName}</TableCell>
                        <TableCell>{`${team.city}, ${team.stateProv}`}</TableCell>
                        <TableCell>{teamEPAs[team.teamNumber]?.toFixed(1) || '0.0'}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Grid>
          </Grid>
        ) : activeTab === 1 ? (
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Match</TableCell>
                  <TableCell>Red Alliance</TableCell>
                  <TableCell>Blue Alliance</TableCell>
                  <TableCell>Predicted Winner</TableCell>
                  <TableCell>Win Probability</TableCell>
                  <TableCell align="right">Red Score</TableCell>
                  <TableCell align="right">Blue Score</TableCell>
                  <TableCell>Actual Winner</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {sortedMatches.map((match) => {
                  const redWon = match.scoreRedFinal > match.scoreBlueFinal;
                  const blueWon = match.scoreBlueFinal > match.scoreRedFinal;
                  const prediction = match.prediction || {};
                  const winProb = prediction.predicted_winner === 'Red' ? 
                    prediction.red_win_probability : prediction.blue_win_probability;
                  // Determine predicted winner color
                  const predictedWinnerBg = prediction.predicted_winner === 'Red'
                    ? 'rgba(255, 0, 0, 0.08)'
                    : prediction.predicted_winner === 'Blue'
                    ? 'rgba(0, 0, 255, 0.08)'
                    : undefined;
                  // Determine if prediction was correct
                  const actualWinner = redWon ? 'Red' : blueWon ? 'Blue' : 'Tie';
                  const winProbColor = prediction.predicted_winner && actualWinner !== 'Tie'
                    ? (prediction.predicted_winner === actualWinner ? 'success.main' : 'error.main')
                    : undefined;
                  return (
                    <TableRow key={match.matchNumber}>
                      <TableCell>{match.description || `Match ${match.matchNumber}`}</TableCell>
                      <TableCell>
                        {match.teams && match.teams.length > 0 
                          ? match.teams
                              .filter(team => team.station && team.station.includes('Red'))
                              .map(team => team.teamNumber)
                              .join(', ')
                          : 'N/A'}
                      </TableCell>
                      <TableCell>
                        {match.teams && match.teams.length > 0 
                          ? match.teams
                              .filter(team => team.station && team.station.includes('Blue'))
                              .map(team => team.teamNumber)
                              .join(', ')
                          : 'N/A'}
                      </TableCell>
                      <TableCell sx={predictedWinnerBg ? { backgroundColor: predictedWinnerBg } : {}}>
                        {prediction.predicted_winner || 'N/A'}
                      </TableCell>
                      <TableCell sx={winProbColor ? { color: winProbColor, fontWeight: 600 } : {}}>
                        {winProb ? `${(winProb * 100).toFixed(1)}%` : 'N/A'}
                      </TableCell>
                      <TableCell align="right" sx={{ color: redWon ? 'success.main' : 'inherit' }}>
                        {match.scoreRedFinal}
                      </TableCell>
                      <TableCell align="right" sx={{ color: blueWon ? 'success.main' : 'inherit' }}>
                        {match.scoreBlueFinal}
                      </TableCell>
                      <TableCell>
                        {actualWinner}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        ) : activeTab === 2 ? (
          <AllianceMatchmaker 
            season={Number(season)}
            eventCode={eventCode}
            teams={teams}
            teamEPAs={teamEPAs}
          />
        ) : null}
      </Paper>
    </Container>
  );
};

export default EventDetails;
