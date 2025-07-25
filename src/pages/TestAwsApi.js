import React, { useState } from 'react';
import {
  Container,
  Grid,
  Typography,
  Button,
  Paper,
  Box,
  Alert,
  CircularProgress,
  TextField
} from '@mui/material';
import AwsMatchesApi from '../services/awsMatchesApi';

const awsMatchesApi = new AwsMatchesApi();

function TestAwsApi() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [eventCode, setEventCode] = useState('USLAWAQ');
  const [teamNumber, setTeamNumber] = useState('19458');
  const [season, setSeason] = useState('2024');

  const testConnection = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await awsMatchesApi.testConnection();
      setResult({
        type: 'Connection Test',
        data: result,
        summary: result.success ? 'API connection successful!' : 'API connection failed'
      });
    } catch (err) {
      setError(`Connection test failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const testEventMatches = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await awsMatchesApi.getEventMatches(parseInt(season), eventCode);
      setResult({
        type: 'Event Matches',
        data: result,
        summary: `Found ${result.matches?.length || 0} matches for event ${eventCode}`
      });
    } catch (err) {
      setError(`Failed to fetch event matches: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const testTeamMatches = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await awsMatchesApi.getTeamMatches(parseInt(teamNumber), parseInt(season));
      setResult({
        type: 'Team Matches',
        data: result,
        summary: `Found ${result.matches?.length || 0} matches for team ${teamNumber}`
      });
    } catch (err) {
      setError(`Failed to fetch team matches: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const testEventStats = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await awsMatchesApi.getEventMatchStats(parseInt(season), eventCode);
      setResult({
        type: 'Event Statistics',
        data: result,
        summary: `Event stats for ${eventCode}: ${result.stats?.totalMatches || 0} total matches`
      });
    } catch (err) {
      setError(`Failed to fetch event stats: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="lg">
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <Typography variant="h4" gutterBottom>
            AWS Matches API Test
          </Typography>
          <Typography variant="body1" color="text.secondary" paragraph>
            Test the AWS matches API integration to verify it's working correctly.
          </Typography>
        </Grid>

        {/* Input Fields */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>Test Parameters</Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} md={4}>
                <TextField
                  fullWidth
                  label="Season"
                  value={season}
                  onChange={(e) => setSeason(e.target.value)}
                  variant="outlined"
                />
              </Grid>
              <Grid item xs={12} md={4}>
                <TextField
                  fullWidth
                  label="Event Code"
                  value={eventCode}
                  onChange={(e) => setEventCode(e.target.value)}
                  variant="outlined"
                />
              </Grid>
              <Grid item xs={12} md={4}>
                <TextField
                  fullWidth
                  label="Team Number"
                  value={teamNumber}
                  onChange={(e) => setTeamNumber(e.target.value)}
                  variant="outlined"
                />
              </Grid>
            </Grid>
          </Paper>
        </Grid>

        {/* Test Buttons */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>API Tests</Typography>
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              <Button
                variant="outlined"
                onClick={testConnection}
                disabled={loading}
                color="secondary"
              >
                Test Connection
              </Button>
              <Button
                variant="contained"
                onClick={testEventMatches}
                disabled={loading}
              >
                Test Event Matches
              </Button>
              <Button
                variant="contained"
                onClick={testTeamMatches}
                disabled={loading}
              >
                Test Team Matches
              </Button>
              <Button
                variant="contained"
                onClick={testEventStats}
                disabled={loading}
              >
                Test Event Stats
              </Button>
            </Box>
          </Paper>
        </Grid>

        {/* Loading */}
        {loading && (
          <Grid item xs={12}>
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
              <CircularProgress />
            </Box>
          </Grid>
        )}

        {/* Error */}
        {error && (
          <Grid item xs={12}>
            <Alert severity="error">{error}</Alert>
          </Grid>
        )}

        {/* Results */}
        {result && !loading && (
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                {result.type} Results
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                {result.summary}
              </Typography>
              <Box sx={{ 
                backgroundColor: 'grey.100', 
                p: 2, 
                borderRadius: 1,
                maxHeight: '400px',
                overflow: 'auto'
              }}>
                <pre style={{ 
                  fontSize: '12px', 
                  margin: 0,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word'
                }}>
                  {JSON.stringify(result.data, null, 2)}
                </pre>
              </Box>
            </Paper>
          </Grid>
        )}
      </Grid>
    </Container>
  );
}

export default TestAwsApi;
