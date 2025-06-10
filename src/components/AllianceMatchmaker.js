import React, { useState, useCallback } from 'react';
import { 
  Box, 
  Paper, 
  Typography, 
  TextField, 
  Button, 
  CircularProgress, 
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Card,
  CardContent,
  CardHeader,
  Alert,
  Grid,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  Stack,
  Tabs,
  Tab,
  Tooltip
} from '@mui/material';
import Confetti from 'react-confetti';
import FTCApi from '../services/ftcapi';

// Add method to FTCApi to handle batch processing
FTCApi.prototype.getBestAlliancePartnersBatch = async function(season, eventCode, teamNumbers, teamEPAs = {}) {
  try {
    const response = await fetch(`${this.apiBaseUrl}/api/alliance-matchmaker/batch`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        season,
        eventCode,
        teamNumbers,
        teamEPAs
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`API Error: ${response.status} - ${errorText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error in batch alliance matchmaker request:', error);
    throw error;
  }
};

const AllianceMatchmaker = ({ season, eventCode, teams, teamEPAs }) => {
  const [teamNumber, setTeamNumber] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [batchResults, setBatchResults] = useState(null);
  const [openDialog, setOpenDialog] = useState(false);
  const [showConfetti, setShowConfetti] = useState(false);
  const [selectedTeams, setSelectedTeams] = useState([]);
  const [mode, setMode] = useState('single'); // 'single' or 'batch'
  const [activeResultTab, setActiveResultTab] = useState(0);
  const [selectedPartner, setSelectedPartner] = useState(null);
  const [winProbResult, setWinProbResult] = useState(null);
  const [winProbLoading, setWinProbLoading] = useState(false);
  const [winProbError, setWinProbError] = useState(null);
  
  const ftcApi = new FTCApi();
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (mode === 'single') {
      if (!teamNumber) return;
      
      try {
        setLoading(true);
        setError(null);
        
        // Check if the team is part of the event
        const isTeamInEvent = teams.some(team => team.teamNumber === parseInt(teamNumber));
        if (!isTeamInEvent) {
          setError(`Team ${teamNumber} is not participating in this event.`);
          setLoading(false);
          return;
        }
        
        const matchResult = await ftcApi.getBestAlliancePartner(
          season, 
          eventCode, 
          parseInt(teamNumber)
        );
        
        setResult(matchResult);
        setOpenDialog(true);
        setShowConfetti(true);
        setTimeout(() => setShowConfetti(false), 5000);
      } catch (err) {
        setError(err.message || 'Failed to find alliance partners');
        console.error(err);
      } finally {
        setLoading(false);
      }
    } else {
      // Batch mode
      if (selectedTeams.length === 0) {
        setError("Please select at least one team for batch processing");
        return;
      }
      
      try {
        setLoading(true);
        setError(null);
        
        const batchResult = await ftcApi.getBestAlliancePartnersBatch(
          season,
          eventCode,
          selectedTeams.map(t => parseInt(t)),
          teamEPAs
        );
        
        setBatchResults(batchResult);
        setOpenDialog(true);
        setShowConfetti(true);
        setTimeout(() => setShowConfetti(false), 5000);
      } catch (err) {
        setError(err.message || 'Failed to process batch alliance partners');
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
  };
  
  const handleTeamSelect = (event) => {
    setSelectedTeams(event.target.value);
  };
  
  const handleModeChange = (event, newMode) => {
    setMode(newMode);
    setError(null); // Clear any previous errors
  };
  
  const handleResultTabChange = (event, newValue) => {
    setActiveResultTab(newValue);
  };
  
  const handleCloseDialog = () => {
    setOpenDialog(false);
  };
  
  const formatScoreCategory = (score) => {
    if (score <= 5) return 'Low';
    if (score <= 15) return 'Average';
    if (score <= 25) return 'Good';
    return 'Excellent';
  };
  
  const getColorForScore = (score) => {
    if (score <= 5) return '#f44336';  // Red
    if (score <= 15) return '#ff9800';  // Orange
    if (score <= 25) return '#2196f3';  // Blue
    return '#4caf50';  // Green
  };
  
  // Helper to get the highest-EPA alliance (excluding your team and partner)
  const getHighestEPAAlliance = useCallback(() => {
    // Get all team numbers except your team and selected partner
    const exclude = [parseInt(teamNumber), selectedPartner?.teamNumber2];
    const eligible = Object.keys(teamEPAs)
      .map(Number)
      .filter(tn => !exclude.includes(tn));
    // Sort by EPA descending
    eligible.sort((a, b) => (teamEPAs[b] || 0) - (teamEPAs[a] || 0));
    // Pick top 2 (assuming alliances of 2)
    return eligible.slice(0, 2);
  }, [teamNumber, selectedPartner, teamEPAs]);

  // Handler for clicking a partner card
  const handlePartnerClick = async (match) => {
    setSelectedPartner(match);
    setWinProbResult(null);
    setWinProbError(null);
    setWinProbLoading(true);
    try {
      const yourAlliance = [parseInt(teamNumber), match.teamNumber2];
      const oppAlliance = getHighestEPAAlliance();
      // Calculate win probability for these alliances using the formula
      const yourEPA = yourAlliance.reduce((sum, tn) => sum + (teamEPAs[tn] || 0), 0);
      const oppEPA = oppAlliance.reduce((sum, tn) => sum + (teamEPAs[tn] || 0), 0);
      const epaDiff = yourEPA - oppEPA;
      const winProb = 1 / (1 + Math.pow(10, -epaDiff / 400));
      // Also, get the backend prediction for the actual match (if available)
      let matchPrediction = null;
      try {
        matchPrediction = await ftcApi.getPrediction(
          season,
          eventCode,
          yourAlliance,
          oppAlliance,
          teamEPAs,
          null // matchNumber not needed
        );
      } catch (e) {
        // Ignore backend error, just show frontend calc
      }
      setWinProbResult({
        yourAlliance,
        oppAlliance,
        winProb,
        matchPrediction
      });
    } catch (err) {
      setWinProbError('Failed to get win probability');
    } finally {
      setWinProbLoading(false);
    }
  };

  // Handler for back button
  const handleBackToPartners = () => {
    setSelectedPartner(null);
    setWinProbResult(null);
    setWinProbError(null);
  };

  const CompatibilityCard = ({ match, index }) => {
    const team = teams.find(t => t.teamNumber === match.teamNumber2);
    const teamName = team ? (team.nameShort || team.nameFull || `Team ${match.teamNumber2}`) : `Team ${match.teamNumber2}`;
    const teamEPA = teamEPAs[match.teamNumber2] || 0;
    
    return (
      <Card elevation={3} sx={{ mb: 2, border: index === 0 ? '2px solid #4caf50' : 'none', cursor: 'pointer' }}
        onClick={() => handlePartnerClick(match)}
      >
        <CardHeader
          title={`#${match.teamNumber2} - ${teamName}`}
          subheader={`Compatibility Score: ${(match.compatibilityScore * 100).toFixed(1)}%`}
          sx={{
            backgroundColor: index === 0 ? '#e8f5e9' : 'inherit',
            '& .MuiCardHeader-title': { fontWeight: 'bold' }
          }}
        />
        <CardContent>
          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle1" gutterBottom>
              Combined EPA: {match.combinedEPA.toFixed(1)}
            </Typography>
          </Box>
          
          <Grid container spacing={2}>
            <Grid item xs={6}>
              <Typography variant="subtitle2" gutterBottom>Your Team</Typography>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography variant="body2">Auto:</Typography>
                <Typography 
                  variant="body2" 
                  sx={{ fontWeight: 'bold', color: getColorForScore(match.team1Stats.auto) }}
                >
                  {match.team1Stats.auto.toFixed(1)} ({formatScoreCategory(match.team1Stats.auto)})
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography variant="body2">Teleop:</Typography>
                <Typography 
                  variant="body2" 
                  sx={{ fontWeight: 'bold', color: getColorForScore(match.team1Stats.teleop) }}
                >
                  {match.team1Stats.teleop.toFixed(1)} ({formatScoreCategory(match.team1Stats.teleop)})
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="body2">Endgame:</Typography>
                <Typography 
                  variant="body2" 
                  sx={{ fontWeight: 'bold', color: getColorForScore(match.team1Stats.endgame) }}
                >
                  {match.team1Stats.endgame.toFixed(1)} ({formatScoreCategory(match.team1Stats.endgame)})
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={6}>
              <Typography variant="subtitle2" gutterBottom>Partner Team</Typography>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography variant="body2">Auto:</Typography>
                <Typography 
                  variant="body2" 
                  sx={{ fontWeight: 'bold', color: getColorForScore(match.team2Stats.auto) }}
                >
                  {match.team2Stats.auto.toFixed(1)} ({formatScoreCategory(match.team2Stats.auto)})
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography variant="body2">Teleop:</Typography>
                <Typography 
                  variant="body2" 
                  sx={{ fontWeight: 'bold', color: getColorForScore(match.team2Stats.teleop) }}
                >
                  {match.team2Stats.teleop.toFixed(1)} ({formatScoreCategory(match.team2Stats.teleop)})
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="body2">Endgame:</Typography>
                <Typography 
                  variant="body2" 
                  sx={{ fontWeight: 'bold', color: getColorForScore(match.team2Stats.endgame) }}
                >
                  {match.team2Stats.endgame.toFixed(1)} ({formatScoreCategory(match.team2Stats.endgame)})
                </Typography>
              </Box>
            </Grid>
          </Grid>
          
          {index === 0 && (
            <Alert severity="success" sx={{ mt: 2 }}>
              Perfect Match! This team complements your strengths and weaknesses.
            </Alert>
          )}
        </CardContent>
      </Card>
    );
  };
  
  // Win probability view
  const WinProbabilityView = () => {
    let winProb = null;
    let backendProb = null;
    if (winProbResult) {
      winProb = winProbResult.winProb;
      if (winProbResult.matchPrediction && typeof winProbResult.matchPrediction.red_win_probability === 'number') {
        backendProb = winProbResult.matchPrediction.red_win_probability;
      }
    }
    return (
      <Box>
        <Button onClick={handleBackToPartners} sx={{ mb: 2 }} variant="outlined">Back</Button>
        {winProbLoading && <CircularProgress />}
        {winProbError && <Alert severity="error">{winProbError}</Alert>}
        {winProbResult && (
          <Box>
            <Typography variant="h6" gutterBottom>
              Win Probability (EPA Formula): {winProb !== null ? (winProb * 100).toFixed(1) : '?'}% (You &amp; Partner)
            </Typography>
            {backendProb !== null && (
              <Typography variant="h6" gutterBottom>
                Win Probability (Backend/Actual Match): {(backendProb * 100).toFixed(1)}%
              </Typography>
            )}
            <Typography variant="body1" gutterBottom>
              Your Alliance: {winProbResult.yourAlliance.join(' & ')} (EPA: {winProbResult.yourAlliance.map(tn => teamEPAs[tn] || 0).join(' + ')} = {winProbResult.yourAlliance.reduce((sum, tn) => sum + (teamEPAs[tn] || 0), 0).toFixed(1)})
            </Typography>
            <Typography variant="body1" gutterBottom>
              Highest EPA Opponents: {winProbResult.oppAlliance.join(' & ')} (EPA: {winProbResult.oppAlliance.map(tn => teamEPAs[tn] || 0).join(' + ')} = {winProbResult.oppAlliance.reduce((sum, tn) => sum + (teamEPAs[tn] || 0), 0).toFixed(1)})
            </Typography>
            <Typography variant="body2" color="textSecondary">
              Predicted Winner: {winProb >= 0.5 ? 'Your Alliance' : 'Opponents'}
            </Typography>
          </Box>
        )}
      </Box>
    );
  };
  
  return (
    <Paper elevation={3} sx={{ p: 3, mb: 4, position: 'relative', overflow: 'hidden' }}>
      <Typography variant="h5" gutterBottom>Alliance Matchmaker</Typography>
      <Typography variant="body1" paragraph>
        Find your perfect alliance partner based on complementary strengths and weaknesses.
      </Typography>
      
      {showConfetti && <Confetti width={window.innerWidth} height={window.innerHeight} recycle={false} />}
      
      <Box component="form" onSubmit={handleSubmit} sx={{ mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <TextField
            label="Your Team Number"
            variant="outlined"
            size="small"
            value={teamNumber}
            onChange={(e) => setTeamNumber(e.target.value)}
            disabled={loading}
            placeholder="Enter your team number"
            type="number"
            required
            sx={{ flexGrow: 1 }}
          />
          <Button
            variant="contained"
            color="primary"
            type="submit"
            disabled={loading || !teamNumber}
          >
            {loading ? <CircularProgress size={24} /> : 'Find Partners'}
          </Button>
        </Box>
        
        {error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        )}
      </Box>
      
      <Dialog
        open={openDialog}
        onClose={handleCloseDialog}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          Alliance Matchmaker Results
        </DialogTitle>
        <DialogContent>
          <DialogContentText paragraph>
            {selectedPartner
              ? `Win probability for you and Team ${selectedPartner.teamNumber2} vs. highest EPA alliance:`
              : `Here are the best alliance partners for Team ${result?.teamNumber}, ordered by compatibility:`}
          </DialogContentText>
          {selectedPartner
            ? <WinProbabilityView />
            : result?.bestMatches?.map((match, index) => (
                <CompatibilityCard key={match.teamNumber2} match={match} index={index} />
              ))}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Close</Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
};

export default AllianceMatchmaker;
