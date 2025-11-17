import React from 'react';
import {
  Container,
  Grid,
  Paper,
  Typography,
  Box,
  Card,
  CardContent,
} from '@mui/material';

function Home() {
  return (
    <Container maxWidth="xl">
      <Grid container spacing={4}>
        {/* Hero Section */}
        <Grid item xs={12}>
          <Paper 
            elevation={3} 
            sx={{ 
              p: 4, 
              display: 'flex', 
              alignItems: 'center',
              gap: 4,
              background: 'linear-gradient(45deg,rgb(25, 84, 210) 30%,rgb(177, 207, 251) 90%)',
              color: 'white'
            }}
          >
            <Box sx={{ flex: 1 }}>
              <Typography variant="h3" gutterBottom>
                Welcome to WinK
              </Typography>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Your FTC Scouting and Prediction Platform
              </Typography>
              <Typography variant="body1">
                Discover insights, track team performance, and predict match outcomes with advanced analytics.
              </Typography>
            </Box>
            <Box sx={{ width: 200, height: 200 }}>
              <img 
                src="https://yt3.googleusercontent.com/ytc/AIdro_lOe3ngANG3A7hvhkv15LZbsPYTTQB8XwgxucftEmE29ZU=s900-c-k-c0x00ffffff-no-rj"
                alt="FTC Logo"
                style={{ 
                  width: '100%', 
                  height: '100%', 
                  objectFit: 'contain',
                  borderRadius: '50%',
                }}
              />
            </Box>
          </Paper>
        </Grid>

        {/* Platform Features Section */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h5" gutterBottom>
                Why Choose WinK?
              </Typography>
              <Typography variant="body1" paragraph>
                Our platform provides comprehensive tools for FTC teams and enthusiasts:
              </Typography>
              <ul>
                <li>
                  <Typography variant="body1">
                    <strong>Advanced Scouting:</strong> Track team performance, analyze match data, and identify patterns
                  </Typography>
                </li>
                <li>
                  <Typography variant="body1">
                    <strong>Score Prediction:</strong> Use historical data and machine learning to predict match outcomes
                  </Typography>
                </li>
                <li>
                  <Typography variant="body1">
                    <strong>Team Analytics:</strong> Get detailed insights into team performance and rankings
                  </Typography>
                </li>
                <li>
                  <Typography variant="body1">
                    <strong>Event Tracking:</strong> Stay updated with upcoming events and match schedules
                  </Typography>
                </li>
              </ul>
            </CardContent>
          </Card>
        </Grid>

        {/* Stats Cards */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                Total Teams
              </Typography>
              <Typography variant="h4">2,500+</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                Active Events
              </Typography>
              <Typography variant="h4">150+</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                Matches Played
              </Typography>
              <Typography variant="h4">12,000+</Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Container>
  );
}

export default Home; 