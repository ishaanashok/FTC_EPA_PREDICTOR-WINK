import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Paper,
  Grid,
  Card,
  CardContent,
  Button,
  Alert,
  Chip,
  IconButton,
} from '@mui/material';
import {
  Refresh,
  Storage,
  Api,
  People,
  Event,
  SportsSoccer,
  Dashboard,
} from '@mui/icons-material';
import { getCurrentUser, signOut } from 'aws-amplify/auth';
import { useNavigate } from 'react-router-dom';

const AdminDashboard = () => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [syncStatus, setSyncStatus] = useState({
    teams: 'unknown',
    events: 'unknown',
    matches: 'unknown'
  });
  const navigate = useNavigate();

  useEffect(() => {
    checkAuthState();
  }, []);

  const checkAuthState = async () => {
    try {
      const currentUser = await getCurrentUser();
      setUser(currentUser);
    } catch (error) {
      navigate('/admin');
    } finally {
      setLoading(false);
    }
  };

  const handleSignOut = async () => {
    try {
      await signOut();
      navigate('/admin');
    } catch (error) {
      console.error('Sign out error:', error);
    }
  };

  const triggerDataSync = async (syncType) => {
    try {
      setSyncStatus(prev => ({ ...prev, [syncType]: 'syncing' }));
      
      // Call your data sync API
      const response = await fetch(`https://emgquhzu1f.execute-api.us-east-1.amazonaws.com/stage/data-sync`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ sync_type: syncType })
      });

      if (response.ok) {
        setSyncStatus(prev => ({ ...prev, [syncType]: 'success' }));
      } else {
        setSyncStatus(prev => ({ ...prev, [syncType]: 'error' }));
      }
    } catch (error) {
      console.error(`Error syncing ${syncType}:`, error);
      setSyncStatus(prev => ({ ...prev, [syncType]: 'error' }));
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'success': return 'success';
      case 'error': return 'error';
      case 'syncing': return 'warning';
      default: return 'default';
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'success': return 'Synced';
      case 'error': return 'Error';
      case 'syncing': return 'Syncing...';
      default: return 'Unknown';
    }
  };

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Typography>Loading dashboard...</Typography>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
        <Box>
          <Typography variant="h4" gutterBottom>
            Admin Dashboard
          </Typography>
          <Typography variant="subtitle1" color="text.secondary">
            Welcome, {user?.username}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            variant="outlined"
            onClick={() => navigate('/')}
            startIcon={<Dashboard />}
          >
            Main App
          </Button>
          <Button
            variant="outlined"
            onClick={handleSignOut}
            color="error"
          >
            Sign Out
          </Button>
        </Box>
      </Box>

      {/* Quick Stats */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <People sx={{ fontSize: 40, color: 'primary.main', mb: 1 }} />
              <Typography variant="h6">Teams</Typography>
              <Typography variant="body2" color="text.secondary">
                Manage team data
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Event sx={{ fontSize: 40, color: 'secondary.main', mb: 1 }} />
              <Typography variant="h6">Events</Typography>
              <Typography variant="body2" color="text.secondary">
                Manage event data
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <SportsSoccer sx={{ fontSize: 40, color: 'success.main', mb: 1 }} />
              <Typography variant="h6">Matches</Typography>
              <Typography variant="body2" color="text.secondary">
                Manage match data
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Api sx={{ fontSize: 40, color: 'warning.main', mb: 1 }} />
              <Typography variant="h6">API Status</Typography>
              <Typography variant="body2" color="text.secondary">
                Monitor system health
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Data Sync Controls */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
          <Storage sx={{ mr: 2 }} />
          <Typography variant="h6">Data Synchronization</Typography>
        </Box>
        
        <Alert severity="info" sx={{ mb: 3 }}>
          Use these controls to manually sync data from the FTC API to the database.
          Monitor the status indicators to track sync progress.
        </Alert>

        <Grid container spacing={3}>
          <Grid item xs={12} md={4}>
            <Card variant="outlined">
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                  <Typography variant="h6">Teams</Typography>
                  <Chip 
                    label={getStatusText(syncStatus.teams)}
                    color={getStatusColor(syncStatus.teams)}
                    size="small"
                  />
                </Box>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  Sync team information from FTC API
                </Typography>
                <Button
                  variant="contained"
                  fullWidth
                  onClick={() => triggerDataSync('teams')}
                  disabled={syncStatus.teams === 'syncing'}
                  startIcon={<Refresh />}
                >
                  {syncStatus.teams === 'syncing' ? 'Syncing...' : 'Sync Teams'}
                </Button>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={4}>
            <Card variant="outlined">
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                  <Typography variant="h6">Events</Typography>
                  <Chip 
                    label={getStatusText(syncStatus.events)}
                    color={getStatusColor(syncStatus.events)}
                    size="small"
                  />
                </Box>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  Sync event information from FTC API
                </Typography>
                <Button
                  variant="contained"
                  fullWidth
                  onClick={() => triggerDataSync('events')}
                  disabled={syncStatus.events === 'syncing'}
                  startIcon={<Refresh />}
                >
                  {syncStatus.events === 'syncing' ? 'Syncing...' : 'Sync Events'}
                </Button>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={4}>
            <Card variant="outlined">
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                  <Typography variant="h6">Matches</Typography>
                  <Chip 
                    label={getStatusText(syncStatus.matches)}
                    color={getStatusColor(syncStatus.matches)}
                    size="small"
                  />
                </Box>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  Sync match results from FTC API
                </Typography>
                <Button
                  variant="contained"
                  fullWidth
                  onClick={() => triggerDataSync('matches')}
                  disabled={syncStatus.matches === 'syncing'}
                  startIcon={<Refresh />}
                >
                  {syncStatus.matches === 'syncing' ? 'Syncing...' : 'Sync Matches'}
                </Button>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Paper>

      {/* System Information */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          System Information
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6}>
            <Typography variant="body2">
              <strong>API Endpoint:</strong> emgquhzu1f.execute-api.us-east-1.amazonaws.com/stage
            </Typography>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Typography variant="body2">
              <strong>Region:</strong> us-east-1
            </Typography>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Typography variant="body2">
              <strong>User Pool:</strong> FTC-Predictor-Admin-Pool
            </Typography>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Typography variant="body2">
              <strong>Last Login:</strong> {new Date().toLocaleString()}
            </Typography>
          </Grid>
        </Grid>
      </Paper>
    </Container>
  );
};

export default AdminDashboard;
