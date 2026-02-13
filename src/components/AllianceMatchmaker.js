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

const AllianceMatchmaker = ({ season, eventCode, teams, teamEPAs, matches = [] }) => {
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
  
  // Calculate team performance stats from EPA and match data
  const calculateTeamStats = (teamNum) => {
    // Get EPA for this team - try multiple key formats
    let epa = 0;
    if (teamEPAs) {
      epa = teamEPAs[teamNum.toString()] || 
            teamEPAs[teamNum] || 
            teamEPAs[`${teamNum}.0`] || 
            0;
    }
    
    const teamMatches = matches.filter(match => 
      match.teams && match.teams.some(t => t.teamNumber === teamNum)
    );
    
    if (teamMatches.length === 0) {
      // Use EPA data as fallback - estimate stats from EPA
      // If no EPA, use a baseline of 50
      const baseEPA = Number(epa) || 50;
      return { 
        auto: Math.round(baseEPA * 0.25 * 10) / 10, 
        teleop: Math.round(baseEPA * 0.55 * 10) / 10, 
        endgame: Math.round(baseEPA * 0.20 * 10) / 10, 
        totalMatches: 0,
        fromEPA: true,
        epaBased: baseEPA
      };
    }
    
    let autoTotal = 0, teleopTotal = 0, endgameTotal = 0;
    
    teamMatches.forEach(match => {
      const isRed = match.teams.find(t => t.teamNumber === teamNum)?.station?.includes('Red');
      
      if (isRed) {
        autoTotal += match.scoreRedAuto || 0;
        endgameTotal += match.scoreRedEnd || 0;
        // Teleop = Final - Auto - Endgame - Foul
        const teleop = (match.scoreRedFinal || 0) - (match.scoreRedAuto || 0) - (match.scoreRedEnd || 0) - (match.scoreRedFoul || 0);
        teleopTotal += Math.max(0, teleop);
      } else {
        autoTotal += match.scoreBlueAuto || 0;
        endgameTotal += match.scoreBlueEnd || 0;
        const teleop = (match.scoreBlueFinal || 0) - (match.scoreBlueAuto || 0) - (match.scoreBlueEnd || 0) - (match.scoreBlueFoul || 0);
        teleopTotal += Math.max(0, teleop);
      }
    });
    
    // Average per match, divided by alliance size (2) for per-team contribution
    const avgAuto = (autoTotal / teamMatches.length) / 2;
    const avgTeleop = (teleopTotal / teamMatches.length) / 2;
    const avgEndgame = (endgameTotal / teamMatches.length) / 2;
    
    return {
      auto: Math.round(avgAuto * 10) / 10,
      teleop: Math.round(avgTeleop * 10) / 10,
      endgame: Math.round(avgEndgame * 10) / 10,
      totalMatches: teamMatches.length,
      fromEPA: false,
      epaBased: epa
    };
  };
  
  // Categorize score levels
  const categorizeScore = (score) => {
    if (score < 5) return 'Low';
    if (score < 15) return 'Average';
    if (score < 25) return 'Good';
    return 'Excellent';
  };

  // Calculate best alliance partners based on complementary strengths
  const calculateBestPartners = (targetTeamNumber) => {
    const targetTeam = teams.find(t => t.teamNumber === targetTeamNumber);
    if (!targetTeam) return null;
    
    // Get EPA for target team - try multiple key formats
    let targetEPA = 0;
    if (teamEPAs) {
      targetEPA = Number(teamEPAs[targetTeamNumber.toString()] || 
                        teamEPAs[targetTeamNumber] || 
                        teamEPAs[`${targetTeamNumber}.0`] || 
                        0);
    }
    if (!targetEPA) targetEPA = 50; // Default baseline
    
    // Get target team's performance stats
    const targetStats = calculateTeamStats(targetTeamNumber);
    
    // Calculate scores for all potential partners
    const partners = teams
      .filter(t => t.teamNumber !== targetTeamNumber)
      .map(partner => {
        // Get partner EPA - try multiple key formats
        let partnerEPA = 0;
        if (teamEPAs) {
          partnerEPA = Number(teamEPAs[partner.teamNumber.toString()] || 
                             teamEPAs[partner.teamNumber] || 
                             teamEPAs[`${partner.teamNumber}.0`] || 
                             0);
        }
        if (!partnerEPA) partnerEPA = 50; // Default baseline
        
        const partnerStats = calculateTeamStats(partner.teamNumber);
        
        // Calculate complementary strength score
        // Identify weak areas in your team and reward partner strength there
        const targetTotal = targetStats.auto + targetStats.teleop + targetStats.endgame;
        
        // Determine target team's weak areas (below 40% of total)
        const targetAutoRatio = targetTotal > 0 ? targetStats.auto / targetTotal : 0;
        const targetTeleopRatio = targetTotal > 0 ? targetStats.teleop / targetTotal : 0;
        const targetEndgameRatio = targetTotal > 0 ? targetStats.endgame / targetTotal : 0;
        
        // Score partner strength in each category
        // Heavily reward partners strong where target is weak
        const autoComplementScore = targetAutoRatio < 0.25 ? 
          (partnerStats.auto * 1.5) : 
          partnerStats.auto * 0.5;
        
        const teleopComplementScore = targetTeleopRatio < 0.45 ? 
          (partnerStats.teleop * 1.5) : 
          partnerStats.teleop * 0.5;
        
        const endgameComplementScore = targetEndgameRatio < 0.25 ? 
          (partnerStats.endgame * 1.5) : 
          partnerStats.endgame * 0.5;
        
        // Overall compatibility = complementary strength + combined EPA
        const complementScore = (autoComplementScore + teleopComplementScore + endgameComplementScore) / 3;
        const combinedEPA = targetEPA + partnerEPA;
        
        // Weighted score: 70% on EPA difference (to differentiate), 30% complementary fit
        // Use both EPA values to create differentiation
        const epaDifferential = Math.abs(targetEPA - partnerEPA); // Teams with different EPAs score higher
        const compatibilityScore = (complementScore * 0.3) + ((combinedEPA / 100) * 50) + (epaDifferential * 0.3);
        
        return {
          teamNumber: partner.teamNumber,
          teamName: partner.nameShort || partner.nameFull || partner.teamName,
          epa: Math.round(partnerEPA * 10) / 10,
          combinedEPA: Math.round(combinedEPA * 10) / 10,
          compatibilityScore: Math.round(compatibilityScore * 100) / 100,
          // Partner stats - all detailed
          partnerAuto: partnerStats.auto,
          partnerTeleop: partnerStats.teleop,
          partnerEndgame: partnerStats.endgame,
          partnerMatches: partnerStats.totalMatches,
          // Categorized for display
          autoCategory: categorizeScore(partnerStats.auto),
          teleopCategory: categorizeScore(partnerStats.teleop),
          endgameCategory: categorizeScore(partnerStats.endgame),
          // Complementary bonus explanation
          complementBonus: {
            auto: targetAutoRatio < 0.25 ? 'HIGH' : 'NORMAL',
            teleop: targetTeleopRatio < 0.45 ? 'HIGH' : 'NORMAL',
            endgame: targetEndgameRatio < 0.25 ? 'HIGH' : 'NORMAL'
          }
        };
      })
      .sort((a, b) => b.compatibilityScore - a.compatibilityScore);
    
    return {
      team: targetTeamNumber,
      teamEPA: Math.round(targetEPA * 10) / 10,
      teamStats: targetStats,
      teamAutoCategory: categorizeScore(targetStats.auto),
      teamTeleopCategory: categorizeScore(targetStats.teleop),
      teamEndgameCategory: categorizeScore(targetStats.endgame),
      partners: partners,
      totalPartners: partners.length
    };
  };

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
        
        // Calculate best partners locally
        const matchResult = calculateBestPartners(parseInt(teamNumber));
        
        if (!matchResult) {
          setError(`Could not find team ${teamNumber}`);
          setLoading(false);
          return;
        }
        
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
        
        // Calculate for each selected team
        const batchResult = {
          results: selectedTeams.map(teamNum => ({
            teamNumber: parseInt(teamNum),
            ...calculateBestPartners(parseInt(teamNum))
          }))
        };
        
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
    
    // Determine if this is a top match
    const isTopMatch = index === 0;
    
    // Calculate the "synergy" bonus text
    const synergyItems = [];
    if (match.complementBonus?.auto === 'HIGH') {
      synergyItems.push('Strong in Auto (your weak area)');
    }
    if (match.complementBonus?.teleop === 'HIGH') {
      synergyItems.push('Strong in Teleop (your weakness)');
    }
    if (match.complementBonus?.endgame === 'HIGH') {
      synergyItems.push('Strong in Endgame (your weak area)');
    }
    
    return (
      <Card 
        elevation={isTopMatch ? 6 : 3} 
        sx={{ 
          mb: 2, 
          border: isTopMatch ? '3px solid #4caf50' : '1px solid #e0e0e0',
          cursor: 'pointer',
          transition: 'all 0.3s ease',
          '&:hover': {
            transform: 'translateY(-2px)',
            boxShadow: 6
          }
        }}
        onClick={() => handlePartnerClick(match)}
      >
        <CardHeader
          title={`#${match.teamNumber} - ${teamName}`}
          subheader={
            <Box sx={{ mt: 1 }}>
              <Typography variant="body2" sx={{ fontWeight: 'bold', color: '#2196f3' }}>
                Compatibility Score: {match.compatibilityScore.toFixed(2)}
              </Typography>
              <Typography variant="caption" color="textSecondary">
                Combined EPA: {match.combinedEPA.toFixed(1)} | Partner EPA: {match.epa.toFixed(1)}
              </Typography>
            </Box>
          }
          sx={{
            backgroundColor: isTopMatch ? '#e8f5e9' : '#f5f5f5',
            '& .MuiCardHeader-title': { fontWeight: 'bold', color: isTopMatch ? '#2e7d32' : 'inherit' }
          }}
        />
        <CardContent>
          {/* Your Team Stats */}
          <Box sx={{ mb: 3 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1, textDecoration: 'underline' }}>
              Your Team (#{result?.team})
            </Typography>
            <Grid container spacing={1}>
              <Grid item xs={4}>
                <Box sx={{ p: 1, backgroundColor: '#f0f0f0', borderRadius: 1, textAlign: 'center' }}>
                  <Typography variant="caption" display="block" sx={{ fontWeight: 'bold' }}>Auto</Typography>
                  <Typography variant="body2" sx={{ color: getColorForScore(result?.teamStats?.auto || 0), fontWeight: 'bold' }}>
                    {(result?.teamStats?.auto || 0).toFixed(1)}
                  </Typography>
                  <Typography variant="caption" display="block">{result?.teamAutoCategory || 'N/A'}</Typography>
                </Box>
              </Grid>
              <Grid item xs={4}>
                <Box sx={{ p: 1, backgroundColor: '#f0f0f0', borderRadius: 1, textAlign: 'center' }}>
                  <Typography variant="caption" display="block" sx={{ fontWeight: 'bold' }}>Teleop</Typography>
                  <Typography variant="body2" sx={{ color: getColorForScore(result?.teamStats?.teleop || 0), fontWeight: 'bold' }}>
                    {(result?.teamStats?.teleop || 0).toFixed(1)}
                  </Typography>
                  <Typography variant="caption" display="block">{result?.teamTeleopCategory || 'N/A'}</Typography>
                </Box>
              </Grid>
              <Grid item xs={4}>
                <Box sx={{ p: 1, backgroundColor: '#f0f0f0', borderRadius: 1, textAlign: 'center' }}>
                  <Typography variant="caption" display="block" sx={{ fontWeight: 'bold' }}>Endgame</Typography>
                  <Typography variant="body2" sx={{ color: getColorForScore(result?.teamStats?.endgame || 0), fontWeight: 'bold' }}>
                    {(result?.teamStats?.endgame || 0).toFixed(1)}
                  </Typography>
                  <Typography variant="caption" display="block">{result?.teamEndgameCategory || 'N/A'}</Typography>
                </Box>
              </Grid>
            </Grid>
          </Box>

          {/* Partner Team Stats */}
          <Box sx={{ mb: 3 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1, textDecoration: 'underline' }}>
              Partner Team (#{match.teamNumber})
            </Typography>
            <Grid container spacing={1}>
              <Grid item xs={4}>
                <Box sx={{ 
                  p: 1, 
                  backgroundColor: match.complementBonus?.auto === 'HIGH' ? '#fff3e0' : '#f0f0f0',
                  borderRadius: 1, 
                  textAlign: 'center',
                  border: match.complementBonus?.auto === 'HIGH' ? '2px solid #ff9800' : 'none'
                }}>
                  <Typography variant="caption" display="block" sx={{ fontWeight: 'bold' }}>Auto</Typography>
                  <Typography variant="body2" sx={{ color: getColorForScore(match.partnerAuto || 0), fontWeight: 'bold' }}>
                    {(match.partnerAuto || 0).toFixed(1)}
                  </Typography>
                  <Typography variant="caption" display="block">{match.autoCategory || 'N/A'}</Typography>
                  {match.complementBonus?.auto === 'HIGH' && (
                    <Typography variant="caption" display="block" sx={{ color: '#ff9800', fontWeight: 'bold', mt: 0.5 }}>
                      ⭐ Bonus
                    </Typography>
                  )}
                </Box>
              </Grid>
              <Grid item xs={4}>
                <Box sx={{ 
                  p: 1, 
                  backgroundColor: match.complementBonus?.teleop === 'HIGH' ? '#fff3e0' : '#f0f0f0',
                  borderRadius: 1, 
                  textAlign: 'center',
                  border: match.complementBonus?.teleop === 'HIGH' ? '2px solid #ff9800' : 'none'
                }}>
                  <Typography variant="caption" display="block" sx={{ fontWeight: 'bold' }}>Teleop</Typography>
                  <Typography variant="body2" sx={{ color: getColorForScore(match.partnerTeleop || 0), fontWeight: 'bold' }}>
                    {(match.partnerTeleop || 0).toFixed(1)}
                  </Typography>
                  <Typography variant="caption" display="block">{match.teleopCategory || 'N/A'}</Typography>
                  {match.complementBonus?.teleop === 'HIGH' && (
                    <Typography variant="caption" display="block" sx={{ color: '#ff9800', fontWeight: 'bold', mt: 0.5 }}>
                      ⭐ Bonus
                    </Typography>
                  )}
                </Box>
              </Grid>
              <Grid item xs={4}>
                <Box sx={{ 
                  p: 1, 
                  backgroundColor: match.complementBonus?.endgame === 'HIGH' ? '#fff3e0' : '#f0f0f0',
                  borderRadius: 1, 
                  textAlign: 'center',
                  border: match.complementBonus?.endgame === 'HIGH' ? '2px solid #ff9800' : 'none'
                }}>
                  <Typography variant="caption" display="block" sx={{ fontWeight: 'bold' }}>Endgame</Typography>
                  <Typography variant="body2" sx={{ color: getColorForScore(match.partnerEndgame || 0), fontWeight: 'bold' }}>
                    {(match.partnerEndgame || 0).toFixed(1)}
                  </Typography>
                  <Typography variant="caption" display="block">{match.endgameCategory || 'N/A'}</Typography>
                  {match.complementBonus?.endgame === 'HIGH' && (
                    <Typography variant="caption" display="block" sx={{ color: '#ff9800', fontWeight: 'bold', mt: 0.5 }}>
                      ⭐ Bonus
                    </Typography>
                  )}
                </Box>
              </Grid>
            </Grid>
          </Box>

          {/* Synergy Info */}
          {synergyItems.length > 0 && (
            <Alert severity="info" sx={{ mb: 2 }}>
              <Typography variant="caption" sx={{ display: 'block', fontWeight: 'bold', mb: 0.5 }}>
                Why this match works:
              </Typography>
              {synergyItems.map((item, idx) => (
                <Typography key={idx} variant="caption" display="block">
                  ✓ {item}
                </Typography>
              ))}
            </Alert>
          )}

          {isTopMatch && (
            <Alert severity="success">
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                🏆 PERFECT MATCH! This team's strengths complement your weaknesses perfectly.
              </Typography>
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
