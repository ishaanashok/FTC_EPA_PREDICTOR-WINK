import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Grid,
  Alert,
  CircularProgress,
  IconButton,
  Divider,
  Tooltip
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Save as SaveIcon
} from '@mui/icons-material';
import { getCurrentUser } from 'aws-amplify/auth';
import FTCApi from '../services/FTCApi';

const AddMatches = ({ season, eventCode, teams, onMatchesAdded }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [loadingMatches, setLoadingMatches] = useState(false);
  const ftcApi = new FTCApi();
  const [matches, setMatches] = useState([]);

  // Load existing matches when component mounts or season/eventCode changes
  useEffect(() => {
    if (season && eventCode) {
      loadExistingMatches();
    }
  }, [season, eventCode]);

  const loadExistingMatches = async () => {
    try {
      setLoadingMatches(true);
      setError(null);
      
      const result = await ftcApi.getAdminEventMatches(season, eventCode);
      
      if (result.success && result.matches) {
        // Convert DynamoDB matches to form format
        const formMatches = result.matches.map((match, index) => ({
          id: index,
          matchNumber: match.matchNumber || '',
          red1: match.redTeams?.[0] || '',
          red2: match.redTeams?.[1] || '',
          blue1: match.blueTeams?.[0] || '',
          blue2: match.blueTeams?.[1] || '',
          redScore: match.redScore || '',
          blueScore: match.blueScore || '',
          savedToDynamoDB: true,
          matchId: match.matchId
        }));
        
        // Add a few empty rows for new matches
        const emptyRows = [];
        for (let i = 0; i < 3; i++) {
          emptyRows.push({
            id: formMatches.length + i,
            matchNumber: '',
            red1: '',
            red2: '',
            blue1: '',
            blue2: '',
            redScore: '',
            blueScore: '',
            savedToDynamoDB: false,
            matchId: null
          });
        }
        
        setMatches([...formMatches, ...emptyRows]);
        console.log(`Loaded ${formMatches.length} existing matches for ${eventCode}`);
      } else {
        // No existing matches, start with empty rows
        initializeEmptyMatches();
      }
    } catch (error) {
      console.warn('Failed to load existing matches:', error);
      // Initialize with empty matches if loading fails
      initializeEmptyMatches();
    } finally {
      setLoadingMatches(false);
    }
  };

  const initializeEmptyMatches = () => {
    const initialMatches = [];
    for (let i = 0; i < 5; i++) {
      initialMatches.push({
        id: i,
        matchNumber: '',
        red1: '',
        red2: '',
        blue1: '',
        blue2: '',
        redScore: '',
        blueScore: '',
        savedToDynamoDB: false,
        matchId: null
      });
    }
    setMatches(initialMatches);
  };

  const addRow = () => {
    // Get the highest ID and add 1, handle edge cases
    const maxId = matches.length > 0 ? Math.max(...matches.map(m => m.id)) : -1;
    const newId = Math.max(maxId + 1, matches.length);
    
    const newMatch = {
      id: newId,
      matchNumber: '',
      red1: '',
      red2: '',
      blue1: '',
      blue2: '',
      redScore: '',
      blueScore: '',
      savedToDynamoDB: false,
      matchId: null
    };
    setMatches([...matches, newMatch]);
  };

  const removeRow = async (id) => {
    if (matches.length > 1) {
      const matchToRemove = matches.find(match => match.id === id);
      
      // If the match was saved to DynamoDB, delete it from there too
      if (matchToRemove && matchToRemove.savedToDynamoDB && matchToRemove.matchId) {
        try {
          setLoading(true);
          await ftcApi.deleteMatch(matchToRemove.matchId, season, eventCode);
          console.log(`Deleted match ${matchToRemove.matchId} from DynamoDB`);
        } catch (error) {
          console.error('Error deleting match from DynamoDB:', error);
          setError(`Failed to delete match from database: ${error.message}`);
          setLoading(false);
          return; // Don't remove from UI if DynamoDB delete failed
        } finally {
          setLoading(false);
        }
      }
      
      // Remove from local state
      setMatches(matches.filter(match => match.id !== id));
    }
  };

  const updateMatch = async (id, field, value) => {
    console.log(`updateMatch called: id=${id}, field=${field}, value=${value}`);
    
    const updatedMatches = matches.map(match => 
      match.id === id ? { ...match, [field]: value } : match
    );
    setMatches(updatedMatches);

    // If this is a saved match, update it in DynamoDB
    const match = matches.find(m => m.id === id);
    if (match && match.savedToDynamoDB && match.matchId) {
      try {
        // Debounce the update to avoid too many API calls
        clearTimeout(window.updateTimeout);
        window.updateTimeout = setTimeout(async () => {
          const updatedMatch = updatedMatches.find(m => m.id === id);
          await updateMatchInDynamoDB(updatedMatch);
        }, 1000); // Wait 1 second after user stops typing
      } catch (error) {
        console.error('Error updating match in DynamoDB:', error);
        setError(`Failed to update match: ${error.message}`);
      }
    }
  };

  const updateMatchInDynamoDB = async (match) => {
    try {
      const matchData = {
        matchNumber: parseInt(match.matchNumber) || 0,
        redTeams: [parseInt(match.red1) || 0, parseInt(match.red2) || 0].filter(t => t > 0),
        blueTeams: [parseInt(match.blue1) || 0, parseInt(match.blue2) || 0].filter(t => t > 0),
        redScore: match.redScore ? parseInt(match.redScore) : null,
        blueScore: match.blueScore ? parseInt(match.blueScore) : null
      };

      const result = await ftcApi.updateMatch(match.matchId, matchData, season, eventCode);
      console.log('Match updated in DynamoDB:', result);
    } catch (error) {
      console.error('Error updating match in DynamoDB:', error);
      throw error;
    }
  };

  const validateMatch = (match) => {
    const errors = [];
    
    if (!match.matchNumber || isNaN(match.matchNumber) || parseInt(match.matchNumber) <= 0) {
      errors.push('Match number must be a positive integer');
    }
    
    if (!match.red1 || isNaN(match.red1)) {
      errors.push('Red 1 team number is required and must be a number');
    }
    
    if (!match.red2 || isNaN(match.red2)) {
      errors.push('Red 2 team number is required and must be a number');
    }
    
    if (!match.blue1 || isNaN(match.blue1)) {
      errors.push('Blue 1 team number is required and must be a number');
    }
    
    if (!match.blue2 || isNaN(match.blue2)) {
      errors.push('Blue 2 team number is required and must be a number');
    }
    
    if (match.redScore !== '' && (isNaN(match.redScore) || parseInt(match.redScore) < 0)) {
      errors.push('Red score must be a non-negative number or empty');
    }
    
    if (match.blueScore !== '' && (isNaN(match.blueScore) || parseInt(match.blueScore) < 0)) {
      errors.push('Blue score must be a non-negative number or empty');
    }
    
    return errors;
  };

  const convertToDbFormat = (match) => {
    // Use match number directly as the qualification number in the match ID
    const matchId = `${season}-${eventCode}-QUALIFICATION-1-${match.matchNumber}`;
    const currentTime = new Date().toISOString();
    
    // Create teams array
    const teams = [
      { teamNumber: parseInt(match.red1), station: 'Red1' },
      { teamNumber: parseInt(match.red2), station: 'Red2' },
      { teamNumber: parseInt(match.blue1), station: 'Blue1' },
      { teamNumber: parseInt(match.blue2), station: 'Blue2' }
    ];

    // Create score objects if scores are provided
    let redScore = null;
    let blueScore = null;
    
    if (match.redScore !== '') {
      redScore = {
        alliance: 'Red',
        totalPoints: parseInt(match.redScore),
        autoPoints: 0,
        teleopPoints: parseInt(match.redScore),
        endgamePoints: 0,
        penaltyPoints: 0
      };
    }
    
    if (match.blueScore !== '') {
      blueScore = {
        alliance: 'Blue',
        totalPoints: parseInt(match.blueScore),
        autoPoints: 0,
        teleopPoints: parseInt(match.blueScore),
        endgamePoints: 0,
        penaltyPoints: 0
      };
    }

    return {
      matchId: matchId,
      season: parseInt(season),
      eventCode: eventCode,
      matchNumber: parseInt(match.matchNumber),
      description: `Qualification ${match.matchNumber}`,
      tournamentLevel: 'QUALIFICATION',
      series: 1,
      teams: teams,
      redTeams: [parseInt(match.red1), parseInt(match.red2)],
      blueTeams: [parseInt(match.blue1), parseInt(match.blue2)],
      allTeams: [parseInt(match.red1), parseInt(match.red2), parseInt(match.blue1), parseInt(match.blue2)],
      redScore: redScore,
      blueScore: blueScore,
      lastUpdated: currentTime,
      startTime: currentTime,
      actualStartTime: null,
      postResultTime: redScore && blueScore ? currentTime : null
    };
  };

  const saveMatches = async () => {
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      // Check if user is authenticated
      const user = await getCurrentUser();
      if (!user) {
        throw new Error('You must be logged in as an administrator to add matches');
      }

      // Filter out empty matches and matches already saved to DynamoDB
      const filledMatches = matches.filter(match => 
        match.matchNumber && match.red1 && match.red2 && match.blue1 && match.blue2 && !match.savedToDynamoDB
      );

      if (filledMatches.length === 0) {
        throw new Error('Please fill in at least one complete match');
      }

      // Validate all matches
      const allErrors = [];
      filledMatches.forEach((match, index) => {
        const errors = validateMatch(match);
        if (errors.length > 0) {
          allErrors.push(`Row ${index + 1}: ${errors.join(', ')}`);
        }
      });

      if (allErrors.length > 0) {
        throw new Error('Validation errors:\n' + allErrors.join('\n'));
      }

      // Convert to database format
      const dbMatches = filledMatches.map(convertToDbFormat);

      // Save matches using the API
      try {
        const result = await ftcApi.addMatches(dbMatches, season, eventCode);
        console.log('API Response:', result);
        
        setSuccess(`Successfully saved ${filledMatches.length} matches to the database`);
        
        // Mark saved matches as saved in DynamoDB and store their match IDs
        const matchIds = result.matchIds || [];
        setMatches(matches.map((match, index) => {
          // Find if this match was in the filled matches array
          const filledIndex = filledMatches.findIndex(fm => 
            fm.matchNumber === match.matchNumber && 
            fm.red1 === match.red1 && 
            fm.red2 === match.red2 &&
            fm.blue1 === match.blue1 && 
            fm.blue2 === match.blue2
          );
          
          if (filledIndex >= 0 && matchIds[filledIndex]) {
            // This match was saved to DynamoDB
            return {
              ...match,
              savedToDynamoDB: true,
              matchId: matchIds[filledIndex]
            };
          }
          
          return match;
        }));

        // Notify parent component if callback provided
        if (onMatchesAdded) {
          onMatchesAdded(dbMatches);
        }
        
      } catch (apiError) {
        // Handle different types of API errors
        if (apiError.message.includes('Admin authorization required')) {
          throw new Error('You must be logged in as an administrator to add matches. Please log in and try again.');
        } else if (apiError.message.includes('not found') || apiError.message.includes('404')) {
          // Lambda function not deployed yet
          console.log('Lambda endpoint not available, showing demo data structure:', dbMatches);
          throw new Error('Admin API not yet deployed. This is a demonstration of the frontend functionality. Check the console for the match data structure that would be sent to DynamoDB.');
        } else {
          console.log('API error occurred, match data would be:', dbMatches);
          throw apiError;
        }
      }

    } catch (err) {
      console.error('Error saving matches:', err);
      setError(err.message || 'Failed to save matches');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        Add Matches for {eventCode} ({season})
      </Typography>
      
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Fill in the match details below. Match numbers should be unique within the tournament level.
        Scores are optional - leave blank for unplayed matches.
      </Typography>

      {loadingMatches && (
        <Alert severity="info" sx={{ mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <CircularProgress size={20} />
            Loading existing matches...
          </Box>
        </Alert>
      )}

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error.split('\n').map((line, index) => (
            <div key={index}>{line}</div>
          ))}
        </Alert>
      )}

      {success && (
        <Alert severity="success" sx={{ mb: 3 }}>
          {success}
        </Alert>
      )}

      <Paper sx={{ p: 3, mb: 3 }}>
        {/* Header Row */}
        <Grid container spacing={2} sx={{ mb: 2, fontWeight: 'bold' }}>
          <Grid item xs={1}>
            <Typography variant="subtitle2">Match</Typography>
          </Grid>
          <Grid item xs={1.5}>
            <Typography variant="subtitle2">Red 1</Typography>
          </Grid>
          <Grid item xs={1.5}>
            <Typography variant="subtitle2">Red 2</Typography>
          </Grid>
          <Grid item xs={1.5}>
            <Typography variant="subtitle2">Blue 1</Typography>
          </Grid>
          <Grid item xs={1.5}>
            <Typography variant="subtitle2">Blue 2</Typography>
          </Grid>
          <Grid item xs={1.5}>
            <Typography variant="subtitle2">Red Score</Typography>
          </Grid>
          <Grid item xs={1.5}>
            <Typography variant="subtitle2">Blue Score</Typography>
          </Grid>
          <Grid item xs={1}>
            <Typography variant="subtitle2">Actions</Typography>
          </Grid>
        </Grid>

        <Divider sx={{ mb: 2 }} />

        {/* Data Rows */}
        {matches.map((match, index) => (
          <Grid 
            container 
            spacing={2} 
            key={match.id} 
            sx={{ 
              mb: 1,
              p: 1,
              backgroundColor: match.savedToDynamoDB ? '#e8f5e8' : 'transparent',
              borderRadius: 1,
              border: match.savedToDynamoDB ? '1px solid #4caf50' : 'none'
            }}
          >
            <Grid item xs={1}>
              <TextField
                size="small"
                fullWidth
                value={match.matchNumber}
                onChange={(e) => updateMatch(match.id, 'matchNumber', e.target.value)}
                placeholder="1"
                type="number"
                InputProps={{ inputProps: { min: 1 } }}
              />
            </Grid>
            <Grid item xs={1.5}>
              <TextField
                size="small"
                fullWidth
                value={match.red1}
                onChange={(e) => updateMatch(match.id, 'red1', e.target.value)}
                placeholder="Team #"
                type="number"
                InputProps={{ inputProps: { min: 1 } }}
              />
            </Grid>
            <Grid item xs={1.5}>
              <TextField
                size="small"
                fullWidth
                value={match.red2}
                onChange={(e) => updateMatch(match.id, 'red2', e.target.value)}
                placeholder="Team #"
                type="number"
                InputProps={{ inputProps: { min: 1 } }}
              />
            </Grid>
            <Grid item xs={1.5}>
              <TextField
                size="small"
                fullWidth
                value={match.blue1}
                onChange={(e) => updateMatch(match.id, 'blue1', e.target.value)}
                placeholder="Team #"
                type="number"
                InputProps={{ inputProps: { min: 1 } }}
              />
            </Grid>
            <Grid item xs={1.5}>
              <TextField
                size="small"
                fullWidth
                value={match.blue2}
                onChange={(e) => updateMatch(match.id, 'blue2', e.target.value)}
                placeholder="Team #"
                type="number"
                InputProps={{ inputProps: { min: 1 } }}
              />
            </Grid>
            <Grid item xs={1.5}>
              <TextField
                size="small"
                fullWidth
                value={match.redScore}
                onChange={(e) => updateMatch(match.id, 'redScore', e.target.value)}
                placeholder="Score"
                type="number"
                InputProps={{ inputProps: { min: 0 } }}
              />
            </Grid>
            <Grid item xs={1.5}>
              <TextField
                size="small"
                fullWidth
                value={match.blueScore}
                onChange={(e) => updateMatch(match.id, 'blueScore', e.target.value)}
                placeholder="Score"
                type="number"
                InputProps={{ inputProps: { min: 0 } }}
              />
            </Grid>
            <Grid item xs={1}>
              <Tooltip 
                title={match.savedToDynamoDB 
                  ? `Saved to database. Click to delete from DynamoDB (ID: ${match.matchId})` 
                  : "Remove row from form"
                }
              >
                <IconButton
                  size="small"
                  onClick={() => removeRow(match.id)}
                  disabled={matches.length <= 1}
                  color={match.savedToDynamoDB ? "warning" : "error"}
                >
                  <DeleteIcon />
                </IconButton>
              </Tooltip>
            </Grid>
          </Grid>
        ))}

        <Box sx={{ mt: 3, display: 'flex', gap: 2, justifyContent: 'space-between' }}>
          <Button
            variant="outlined"
            startIcon={<AddIcon />}
            onClick={addRow}
          >
            Add Row
          </Button>

          <Button
            variant="contained"
            startIcon={loading ? <CircularProgress size={20} /> : <SaveIcon />}
            onClick={saveMatches}
            disabled={loading}
          >
            {loading ? 'Saving...' : 'Save Matches'}
          </Button>
        </Box>
      </Paper>

      <Alert severity="info" sx={{ mt: 2 }}>
        <Typography variant="body2">
          <strong>Implementation Status:</strong> The frontend interface is complete and the AWS Lambda function has been created. 
          The matches are formatted according to the DynamoDB schema. To complete the setup:
          <br />• Deploy the Lambda function at `aws/lambda/admin-matches/`
          <br />• Add the API Gateway endpoint `/admin/matches` 
          <br />• Configure proper admin authentication (Cognito integration)
          <br />• The matches will then be saved to the FTC_Matches_stage DynamoDB table
        </Typography>
      </Alert>
    </Box>
  );
};

export default AddMatches;
