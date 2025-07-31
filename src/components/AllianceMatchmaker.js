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
    const response = await this.axiosInstance.post('/api/alliance-matchmaker/batch', {
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
    if (!result?.partners) return [];
    
    // Get all team numbers except your team and selected partner
    const exclude = [parseInt(teamNumber), selectedPartner?.teamNumber];
    
    // Get EPA data from the alliance matchmaker result
    const eligibleTeams = result.partners
      .filter(partner => !exclude.includes(partner.teamNumber))
      .sort((a, b) => (b.epa || 0) - (a.epa || 0));
    
    // Pick top 2 teams (assuming alliances of 2)
    return eligibleTeams.slice(0, 2).map(team => ({
      teamNumber: team.teamNumber,
      epa: team.epa || 0
    }));
  }, [teamNumber, selectedPartner, result]);

  // Handler for clicking a partner card
  const handlePartnerClick = async (match) => {
    setSelectedPartner(match);
    setWinProbResult(null);
    setWinProbError(null);
    setWinProbLoading(true);
    try {
      const yourAlliance = [parseInt(teamNumber), match.teamNumber];
      const oppAllianceTeams = getHighestEPAAlliance();
      
      // Calculate win probability using EPA data
      const yourTeamEPA = result?.teamEPA || 0;
      const partnerEPA = match.epa || 0;
      const yourAllianceEPA = yourTeamEPA + partnerEPA;
      
      const oppEPA = oppAllianceTeams.reduce((sum, team) => sum + (team.epa || 0), 0);
      const oppAlliance = oppAllianceTeams.map(team => team.teamNumber);
      
      const epaDiff = yourAllianceEPA - oppEPA;
      const winProb = 1 / (1 + Math.pow(10, -epaDiff / 400));
      
      setWinProbResult({
        yourAlliance,
        oppAlliance,
        winProb,
        yourAllianceEPA,
        oppEPA,
        matchPrediction: null // No backend prediction needed
      });
    } catch (err) {
      setWinProbError('Failed to calculate win probability');
      console.error('Win probability calculation error:', err);
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
    const team = teams.find(t => t.teamNumber === match.teamNumber);
    const teamName = match.teamName || team?.nameShort || team?.nameFull || `Team ${match.teamNumber}`;
    const teamEPA = match.epa || 0;
    
    return (
      <Card elevation={3} sx={{ mb: 2, border: index === 0 ? '2px solid #4caf50' : 'none', cursor: 'pointer' }}
        onClick={() => handlePartnerClick(match)}
      >
        <CardHeader
          title={`#${match.teamNumber} - ${teamName}`}
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
            <Typography variant="body2" color="textSecondary" gutterBottom>
              Partner EPA: {match.epa.toFixed(1)} | Total Matches: {match.totalMatches}
            </Typography>
          </Box>
          
          <Grid container spacing={2}>
            <Grid item xs={6}>
              <Typography variant="subtitle2" gutterBottom>Your Team</Typography>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography variant="body2">Auto:</Typography>
                <Typography 
                  variant="body2" 
                  sx={{ fontWeight: 'bold', color: getColorForScore(result?.teamBreakdown?.avgAutoPoints || 0) }}
                >
                  {(result?.teamBreakdown?.avgAutoPoints || 0).toFixed(1)} ({formatScoreCategory(result?.teamBreakdown?.avgAutoPoints || 0)})
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography variant="body2">Teleop:</Typography>
                <Typography 
                  variant="body2" 
                  sx={{ fontWeight: 'bold', color: getColorForScore(result?.teamBreakdown?.avgTeleopPoints || 0) }}
                >
                  {(result?.teamBreakdown?.avgTeleopPoints || 0).toFixed(1)} ({formatScoreCategory(result?.teamBreakdown?.avgTeleopPoints || 0)})
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="body2">Endgame:</Typography>
                <Typography 
                  variant="body2" 
                  sx={{ fontWeight: 'bold', color: getColorForScore(result?.teamBreakdown?.avgEndgamePoints || 0) }}
                >
                  {(result?.teamBreakdown?.avgEndgamePoints || 0).toFixed(1)} ({formatScoreCategory(result?.teamBreakdown?.avgEndgamePoints || 0)})
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={6}>
              <Typography variant="subtitle2" gutterBottom>Partner Team</Typography>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography variant="body2">Auto:</Typography>
                <Typography 
                  variant="body2" 
                  sx={{ fontWeight: 'bold', color: getColorForScore(match.breakdown?.auto || 0) }}
                >
                  {(match.breakdown?.auto || 0).toFixed(1)} ({formatScoreCategory(match.breakdown?.auto || 0)})
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography variant="body2">Teleop:</Typography>
                <Typography 
                  variant="body2" 
                  sx={{ fontWeight: 'bold', color: getColorForScore(match.breakdown?.teleop || 0) }}
                >
                  {(match.breakdown?.teleop || 0).toFixed(1)} ({formatScoreCategory(match.breakdown?.teleop || 0)})
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="body2">Endgame:</Typography>
                <Typography 
                  variant="body2" 
                  sx={{ fontWeight: 'bold', color: getColorForScore(match.breakdown?.endgame || 0) }}
                >
                  {(match.breakdown?.endgame || 0).toFixed(1)} ({formatScoreCategory(match.breakdown?.endgame || 0)})
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
    if (winProbResult) {
      winProb = winProbResult.winProb;
    }
    return (
      <Box>
        <Button onClick={handleBackToPartners} sx={{ mb: 2 }} variant="outlined">Back</Button>
        {winProbLoading && <CircularProgress />}
        {winProbError && <Alert severity="error">{winProbError}</Alert>}
        {winProbResult && (
          <Box>
            <Typography variant="h6" gutterBottom>
              Win Probability: {winProb !== null ? (winProb * 100).toFixed(1) : '?'}%
            </Typography>
            <Typography variant="body1" gutterBottom>
              Your Alliance: Teams {winProbResult.yourAlliance.join(' & ')}
            </Typography>
            <Typography variant="body2" color="textSecondary" gutterBottom>
              Your Alliance EPA: {winProbResult.yourAllianceEPA?.toFixed(1) || 'N/A'}
            </Typography>
            <Typography variant="body1" gutterBottom>
              Highest EPA Opponents: Teams {winProbResult.oppAlliance.join(' & ')}
            </Typography>
            <Typography variant="body2" color="textSecondary" gutterBottom>
              Opponent EPA: {winProbResult.oppEPA?.toFixed(1) || 'N/A'}
            </Typography>
            <Typography variant="body2" color={winProb >= 0.5 ? 'success.main' : 'error.main'} sx={{ fontWeight: 'bold', mt: 2 }}>
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
              ? `Win probability for you and Team ${selectedPartner.teamNumber} vs. highest EPA alliance:`
              : `Here are the top 3 best alliance partners for Team ${result?.team}, ordered by compatibility:`}
          </DialogContentText>
          {selectedPartner
            ? <WinProbabilityView />
            : result?.partners?.slice(0, 3).map((match, index) => (
                <CompatibilityCard key={match.teamNumber} match={match} index={index} />
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
