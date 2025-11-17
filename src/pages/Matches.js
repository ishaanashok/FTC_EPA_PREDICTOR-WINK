import React, { useState, useEffect } from 'react';
import {
  Container,
  Grid,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  TextField,
  Box,
  CircularProgress,
  Alert,
  Chip,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Button,
  ButtonGroup,
} from '@mui/material';
import api from '../services/api';

function Matches() {
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchText, setSearchText] = useState('');
  const [selectedEvent, setSelectedEvent] = useState('');
  const [events, setEvents] = useState([]);
  const [tournamentLevel, setTournamentLevel] = useState(''); // 'QUALIFICATION', 'PLAYOFF', or '' for all
  const [selectedSeason, setSelectedSeason] = useState(2025);
  const [matchStats, setMatchStats] = useState(null);
  const [teamEPAs, setTeamEPAs] = useState({});
  const [epaLoading, setEpaLoading] = useState(false);
  const [showEPAData, setShowEPAData] = useState(true);
  const [showWinProbability, setShowWinProbability] = useState(true);
  const [winProbabilityLoading, setWinProbabilityLoading] = useState(false);

  const fetchEvents = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.searchEvents(selectedSeason);
      const eventsArray = Array.isArray(data) ? data : [];
      setEvents(eventsArray);
      if (eventsArray.length > 0) {
        // Look for the first event that has matches, otherwise use the first one
        const eventWithMatches = eventsArray.find(event => event.matchCount && event.matchCount > 0);
        setSelectedEvent(eventWithMatches ? eventWithMatches.code : eventsArray[0].code);
      }
    } catch (err) {
      setError('Failed to fetch events. Please try again later.');
      setEvents([]); // Ensure events is always an array
      console.error('Error fetching events:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchEPAData = async () => {
    if (!selectedEvent) return;

    try {
      setEpaLoading(true);
      console.log('Fetching EPA data for event:', selectedEvent);
      
      const epaData = await api.getEventEPACalculations(selectedSeason, selectedEvent);
      setTeamEPAs(epaData.teamEPAs || {});
      
      if (epaData.source === 'mock-data') {
        console.log('Using mock EPA data');
      }
      
    } catch (err) {
      console.error('Error fetching EPA data:', err);
      setTeamEPAs({});
    } finally {
      setEpaLoading(false);
    }
  };

  const fetchMatches = async () => {
    if (!selectedEvent) return;

    try {
      setLoading(true);
      setWinProbabilityLoading(true);
      setError(null);
      
      console.log('Fetching matches for:', {
        season: selectedSeason,
        eventCode: selectedEvent,
        tournamentLevel: tournamentLevel || 'all',
        includeWinProbability: showWinProbability
      });
      
      const data = await api.getEventMatches(
        selectedSeason, 
        selectedEvent, 
        tournamentLevel || null,
        showWinProbability
      );
      
      console.log('Received matches data:', data);
      
      // Ensure matches is an array before calling map
      const matchesArray = data?.matches || [];
      
      // Format matches for display
      const formattedMatches = matchesArray.map((match, index) => {
        const formatted = api.formatMatchForDisplay(match);
        return formatted;
      });
      setMatches(formattedMatches);
      
      // Show info if using mock data
      if (data.metadata && data.metadata.source === 'mock-data') {
        setError('Note: Showing mock data. AWS API may not be configured correctly.');
      }
      
    } catch (err) {
      console.error('Error fetching matches:', err);
      setError(`Failed to fetch matches: ${err.message}. Using mock data for demonstration.`);
      
      // Try to get mock data as fallback
      try {
        const mockResult = await api.awsMatchesApi?.getMockEventMatches?.(selectedSeason, selectedEvent, tournamentLevel);
        if (mockResult && mockResult.matches) {
          const matchesArray = mockResult.matches || [];
          const formattedMatches = matchesArray.map(match => api.formatMatchForDisplay(match));
          setMatches(formattedMatches);
        } else {
          setMatches([]);
        }
      } catch (mockError) {
        console.error('Even mock data failed:', mockError);
        setMatches([]);
      }
    } finally {
      setLoading(false);
      setWinProbabilityLoading(false);
    }
  };

  const fetchMatchStats = async () => {
    if (!selectedEvent) return;

    try {
      const stats = await api.getEventMatchStats(selectedSeason, selectedEvent);
      setMatchStats(stats.stats);
    } catch (err) {
      console.error('Error fetching match statistics:', err);
      setMatchStats(null);
    }
  };

  useEffect(() => {
    fetchEvents();
  }, [selectedSeason]);

  useEffect(() => {
    if (selectedEvent) {
      fetchEPAData();
      fetchMatches();
      fetchMatchStats();
    }
  }, [selectedEvent, tournamentLevel, selectedSeason, showWinProbability]);

  const handleEventChange = (event) => {
    setSelectedEvent(event.target.value);
  };

  const handleSeasonChange = (event) => {
    setSelectedSeason(event.target.value);
  };

  const handleSearch = (event) => {
    setSearchText(event.target.value);
  };

  const handleTournamentLevelChange = (level) => {
    setTournamentLevel(level);
  };

  const filteredMatches = matches.filter(match => {
    if (!searchText) return true;
    
    const searchLower = searchText.toLowerCase();
    return (
      match.redTeams?.some(team => team.toString().includes(searchLower)) ||
      match.blueTeams?.some(team => team.toString().includes(searchLower)) ||
      match.description?.toLowerCase().includes(searchLower) ||
      match.number?.toString().includes(searchLower)
    );
  });

  const formatTime = (timeString) => {
    if (!timeString) return 'TBD';
    return new Date(timeString).toLocaleTimeString([], { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  const getScoreDisplay = (match) => {
    if (match.redScore !== null && match.blueScore !== null) {
      return `${match.redScore} - ${match.blueScore}`;
    }
    return 'Not Played';
  };

  const getWinnerChip = (match) => {
    if (!match.completed) {
      return <Chip label="Pending" color="default" size="small" />;
    }

    const winner = match.winner;
    return (
      <Chip
        label={winner || 'TIE'}
        color={
          winner === 'RED' ? 'error' : 
          winner === 'BLUE' ? 'primary' : 
          'default'
        }
        size="small"
      />
    );
  };

  const getWinProbabilityDisplay = (match) => {
    console.log('getWinProbabilityDisplay called with match:', match);
    console.log('match.winProbability:', match.winProbability);
    
    // Check if match has win probability data from the API
    if (match.winProbability && match.winProbability.redWinProbability !== undefined && match.winProbability.blueWinProbability !== undefined) {
      console.log('Found winProbability data from API!');
      const { redWinProbability, blueWinProbability, predictedWinner, confidenceLevel } = match.winProbability;
      
      console.log('Extracted values:', { redWinProbability, blueWinProbability, predictedWinner, confidenceLevel });
      console.log('Red percentage:', (redWinProbability * 100).toFixed(1));
      console.log('Blue percentage:', (blueWinProbability * 100).toFixed(1));
      
      // Ensure we have valid numbers
      const redPercentage = typeof redWinProbability === 'number' ? (redWinProbability * 100).toFixed(1) : 'N/A';
      const bluePercentage = typeof blueWinProbability === 'number' ? (blueWinProbability * 100).toFixed(1) : 'N/A';
      
      return (
        <Box>
          <Typography variant="body2" sx={{ fontWeight: 'bold', color: 'error.main' }}>
            Red: {redPercentage}%
          </Typography>
          <Typography variant="body2" sx={{ fontWeight: 'bold', color: 'primary.main' }}>
            Blue: {bluePercentage}%
          </Typography>
          <Typography variant="caption" color="text.secondary" display="block">
            Predicted: {predictedWinner || 'Unknown'}
          </Typography>
          {confidenceLevel && typeof confidenceLevel === 'number' && (
            <Typography variant="caption" color="text.secondary" display="block">
              Confidence: {(confidenceLevel * 100).toFixed(0)}%
            </Typography>
          )}
        </Box>
      );
    }
    
    console.log('No winProbability found, trying fallback...');
    
    // Fallback to local EPA calculation if no API data
    const prediction = getMatchPrediction(match);
    if (prediction) {
      console.log('Found prediction from getMatchPrediction!');
      const { redWinProbability, blueWinProbability } = prediction;
      const predictedWinner = redWinProbability > 0.5 ? 'Red' : 'Blue';
      
      return (
        <Box>
          <Typography variant="body2" sx={{ fontWeight: 'bold', color: 'error.main' }}>
            Red: {(redWinProbability * 100).toFixed(1)}%
          </Typography>
          <Typography variant="body2" sx={{ fontWeight: 'bold', color: 'primary.main' }}>
            Blue: {(blueWinProbability * 100).toFixed(1)}%
          </Typography>
          <Typography variant="caption" color="text.secondary" display="block">
            Predicted: {predictedWinner}
          </Typography>
          <Typography variant="caption" color="text.secondary" display="block">
            Local EPA calculation
          </Typography>
        </Box>
      );
    }
    
    console.log('No prediction data available, returning No EPA data');
    
    return (
      <Typography variant="caption" color="text.secondary">
        No EPA data
      </Typography>
    );
  };

  const getTeamEPADisplay = (teamNumber) => {
    const epa = teamEPAs[teamNumber?.toString()];
    if (epa) {
      return ` (${Math.round(epa)})`;
    }
    return '';
  };

  const getMatchPrediction = (match) => {
    if (!match.redTeams || !match.blueTeams || Object.keys(teamEPAs).length === 0) {
      return null;
    }

    // Calculate alliance EPAs
    const redEPA = match.redTeams.reduce((sum, team) => sum + (teamEPAs[team?.toString()] || 0), 0);
    const blueEPA = match.blueTeams.reduce((sum, team) => sum + (teamEPAs[team?.toString()] || 0), 0);
    
    if (redEPA === 0 && blueEPA === 0) return null;

    // Simple win probability calculation
    const epaDiff = redEPA - blueEPA;
    const redWinProb = 1 / (1 + Math.exp(-epaDiff / 12));
    
    return {
      redWinProbability: redWinProb,
      blueWinProbability: 1 - redWinProb,
      redTotalEPA: redEPA,
      blueTotalEPA: blueEPA
    };
  };

  return (
    <Container maxWidth="xl">
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <Typography variant="h4" gutterBottom>
            Matches
          </Typography>
        </Grid>

        {/* Season Selector */}
        <Grid item xs={12} md={3}>
          <FormControl fullWidth>
            <InputLabel>Season</InputLabel>
            <Select
              value={selectedSeason}
              onChange={handleSeasonChange}
              label="Season"
            >
              <MenuItem value={2025}>2025</MenuItem>
              <MenuItem value={2024}>2024</MenuItem>
              <MenuItem value={2023}>2023</MenuItem>
              <MenuItem value={2022}>2022</MenuItem>
            </Select>
          </FormControl>
        </Grid>

        {/* Event Selector */}
        <Grid item xs={12} md={6}>
          <FormControl fullWidth>
            <InputLabel>Select Event</InputLabel>
            <Select
              value={selectedEvent}
              onChange={handleEventChange}
              label="Select Event"
            >
              {events.map((event) => (
                <MenuItem key={event.code} value={event.code}>
                  {event.name} ({event.dateStart})
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Grid>

        {/* Search Bar */}
        <Grid item xs={12} md={3}>
          <TextField
            fullWidth
            variant="outlined"
            placeholder="Search teams/matches..."
            size="small"
            value={searchText}
            onChange={handleSearch}
          />
        </Grid>

        {/* Tournament Level Filter */}
        <Grid item xs={12}>
          <Box sx={{ mb: 2 }}>
            <ButtonGroup variant="outlined" size="small">
              <Button 
                variant={tournamentLevel === '' ? 'contained' : 'outlined'}
                onClick={() => handleTournamentLevelChange('')}
              >
                All Matches
              </Button>
              <Button 
                variant={tournamentLevel === 'QUALIFICATION' ? 'contained' : 'outlined'}
                onClick={() => handleTournamentLevelChange('QUALIFICATION')}
              >
                Qualification
              </Button>
              <Button 
                variant={tournamentLevel === 'PLAYOFF' ? 'contained' : 'outlined'}
                onClick={() => handleTournamentLevelChange('PLAYOFF')}
              >
                Playoffs
              </Button>
            </ButtonGroup>
          </Box>
        </Grid>

        {/* EPA Information Panel */}
        {showEPAData && Object.keys(teamEPAs).length > 0 && (
          <Grid item xs={12}>
            <Paper sx={{ p: 2, bgcolor: 'primary.50' }}>
              <Typography variant="h6" gutterBottom>
                EPA Information
                {epaLoading && <CircularProgress size={20} sx={{ ml: 2 }} />}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                EPA (Estimated Performance Average) calculated for {Object.keys(teamEPAs).length} teams. 
                Numbers in parentheses show team EPA ratings.
              </Typography>
              <Button 
                size="small" 
                onClick={() => setShowEPAData(!showEPAData)}
                sx={{ mt: 1 }}
              >
                Hide EPA Data
              </Button>
            </Paper>
          </Grid>
        )}

        {/* Toggle EPA Display */}
        {!showEPAData && Object.keys(teamEPAs).length > 0 && (
          <Grid item xs={12}>
            <Button 
              variant="outlined" 
              onClick={() => setShowEPAData(true)}
              size="small"
            >
              Show EPA Data ({Object.keys(teamEPAs).length} teams)
            </Button>
          </Grid>
        )}

        {/* Win Probability Toggle */}
        <Grid item xs={12}>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
            <Button
              variant={showWinProbability ? 'contained' : 'outlined'}
              onClick={() => setShowWinProbability(!showWinProbability)}
              size="small"
              disabled={winProbabilityLoading}
            >
              {showWinProbability ? 'Hide Win Probabilities' : 'Show Win Probabilities'}
            </Button>
            {winProbabilityLoading && <CircularProgress size={20} />}
            {showWinProbability && (
              <Typography variant="caption" color="text.secondary">
                Win probabilities calculated using EPA values from FTC_EPA_stage table
              </Typography>
            )}
          </Box>
        </Grid>

        {/* Match Statistics */}
        {matchStats && (
          <Grid item xs={12}>
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography variant="h6" gutterBottom>Event Statistics</Typography>
              <Grid container spacing={2}>
                <Grid item xs={6} md={3}>
                  <Typography variant="body2" color="text.secondary">Total Matches</Typography>
                  <Typography variant="h6">{matchStats.totalMatches}</Typography>
                </Grid>
                <Grid item xs={6} md={3}>
                  <Typography variant="body2" color="text.secondary">Completed</Typography>
                  <Typography variant="h6">{matchStats.completedMatches}</Typography>
                </Grid>
                <Grid item xs={6} md={3}>
                  <Typography variant="body2" color="text.secondary">Average Red Score</Typography>
                  <Typography variant="h6">{matchStats.averageRedScore}</Typography>
                </Grid>
                <Grid item xs={6} md={3}>
                  <Typography variant="body2" color="text.secondary">Average Blue Score</Typography>
                  <Typography variant="h6">{matchStats.averageBlueScore}</Typography>
                </Grid>
              </Grid>
            </Paper>
          </Grid>
        )}

        {/* Error/Info Message */}
        {error && (
          <Grid item xs={12}>
            <Alert 
              severity={error.includes('mock data') || error.includes('Note:') ? 'info' : 'error'}
              action={
                error.includes('AWS API') && (
                  <Button color="inherit" size="small" onClick={() => window.open('/test-aws-api', '_blank')}>
                    Test API
                  </Button>
                )
              }
            >
              {error}
              {error.includes('AWS API') && (
                <Typography variant="caption" display="block" sx={{ mt: 1 }}>
                  This may be due to API Gateway authentication requirements or missing endpoint configuration.
                </Typography>
              )}
            </Alert>
          </Grid>
        )}

        {/* Debug Information - only show if there are issues */}
        {(error || matches.length === 0) && !loading && (
          <Grid item xs={12}>
            <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
              <Typography variant="h6" gutterBottom>Debug Information</Typography>
              <Typography variant="body2" paragraph>
                <strong>API Base URL:</strong> {api.awsMatchesApi?.baseUrl || 'Not configured'}
              </Typography>
              <Typography variant="body2" paragraph>
                <strong>Current Request:</strong> Season {selectedSeason}, Event {selectedEvent}, Tournament Level: {tournamentLevel || 'All'}
              </Typography>
              <Typography variant="body2" paragraph>
                <strong>Expected Endpoint:</strong> GET /api/matches?season={selectedSeason}&eventCode={selectedEvent}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                If you're seeing this, the AWS matches API may need to be deployed or configured. 
                The app will show mock data for testing purposes.
              </Typography>
            </Paper>
          </Grid>
        )}

        {/* Loading Spinner */}
        {loading ? (
          <Grid item xs={12} sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
            <CircularProgress />
          </Grid>
        ) : (
          /* Matches Table */
          <Grid item xs={12}>
            <TableContainer component={Paper}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Match</TableCell>
                    <TableCell>Description</TableCell>
                    <TableCell>Red Alliance</TableCell>
                    <TableCell>Blue Alliance</TableCell>
                    {showWinProbability && <TableCell>Win Probability</TableCell>}
                    <TableCell>Score</TableCell>
                    <TableCell>Winner</TableCell>
                    <TableCell>Start Time</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filteredMatches.map((match) => (
                    <TableRow key={match.id}>
                      <TableCell>
                        <Box>
                          <Typography variant="body2" fontWeight="bold">
                            {match.number}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {match.tournamentLevel}
                          </Typography>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {match.description}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Box sx={{ color: 'error.main' }}>
                          {showEPAData 
                            ? match.redTeams?.map(team => `${team}${getTeamEPADisplay(team)}`).join(', ') || 'TBD'
                            : match.redTeams?.join(', ') || 'TBD'
                          }
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Box sx={{ color: 'primary.main' }}>
                          {showEPAData 
                            ? match.blueTeams?.map(team => `${team}${getTeamEPADisplay(team)}`).join(', ') || 'TBD'
                            : match.blueTeams?.join(', ') || 'TBD'
                          }
                        </Box>
                      </TableCell>
                      {showWinProbability && (
                        <TableCell>
                          {getWinProbabilityDisplay(match)}
                        </TableCell>
                      )}
                      <TableCell>
                        <Typography variant="body2">
                          {getScoreDisplay(match)}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        {getWinnerChip(match)}
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {formatTime(match.startTime)}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
            
            {filteredMatches.length === 0 && !loading && (
              <Box sx={{ textAlign: 'center', p: 3 }}>
                <Typography color="text.secondary">
                  No matches found for the selected criteria.
                </Typography>
              </Box>
            )}
          </Grid>
        )}
      </Grid>
    </Container>
  );
}

export default Matches;