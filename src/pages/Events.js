import React, { useState, useEffect } from 'react';
import {
  Container,
  Grid,
  Typography,
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
  Card,
  CardContent,
  CardActionArea,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import FTCApi from '../services/ftcapi';
import PageTransition from '../components/PageTransition';

function Events() {
  const navigate = useNavigate();
  const [events, setEvents] = useState([]);
  const ftcApi = new FTCApi();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchText, setSearchText] = useState('');
  const [filter, setFilter] = useState('upcoming');

  const fetchEvents = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const season = 2024;
      
      // Try the AWS FTC API service first
      console.log('Trying to fetch events from AWS...');
      
      try {
        const response = await ftcApi.getEvents(season);
        console.log('FTC API response:', response);
        console.log('Response type:', typeof response);
        console.log('Response.events:', response.events);
        console.log('Response.events type:', typeof response.events);
        console.log('Response.events length:', response.events?.length);
        
        // Extract events from response
        let events = [];
        if (response.events && Array.isArray(response.events)) {
          events = response.events;
        } else if (Array.isArray(response)) {
          events = response;
        } else if (response && typeof response === 'object') {
          // Try to find events in the response object
          events = response.events || response.data || [];
        }
        
        console.log('Final events array:', events);
        console.log('Final events array length:', events.length);
        
        setEvents(events);
        
        if (events.length === 0) {
          setError('No events found for season 2024');
        } else {
          console.log('Successfully loaded', events.length, 'events');
        }
      } catch (ftcError) {
        console.warn('AWS API failed:', ftcError);
        
        // Temporary mock data while AWS infrastructure is being fixed
        console.log('Using temporary mock data...');
        const mockEvents = [
          {
            code: 'MOCKEV1',
            name: 'Mock Event 1 - FTC Championship',
            dateStart: '2024-03-15',
            venue: 'Mock High School',
            city: 'Seattle',
            stateProv: 'WA',
            country: 'USA'
          },
          {
            code: 'MOCKEV2', 
            name: 'Mock Event 2 - Regional Qualifier',
            dateStart: '2024-03-20',
            venue: 'Another Mock School',
            city: 'Portland',
            stateProv: 'OR',
            country: 'USA'
          }
        ];
        
        setEvents(mockEvents);
        setError('Using mock data - AWS API Gateway methods need to be configured');
      }
    } catch (err) {
      console.error('Error fetching events:', err);
      setError('Failed to fetch events. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let mounted = true;

    const loadEvents = async () => {
      try {
        setLoading(true);
        setError(null);
        
        const season = 2024;
        const response = await ftcApi.getEvents(season);
        
        if (mounted) {
          console.log('Received events data:', response);
          setEvents(response.events || []);
        }
      } catch (err) {
        if (mounted) {
          console.error('Error fetching events:', err);
          setError('Failed to fetch events. Please try again later.');
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    loadEvents();

    return () => {
      mounted = false;
    };
  }, []);

  const handleSearch = (event) => {
    setSearchText(event.target.value);
  };

  const handleFilterChange = (event) => {
    setFilter(event.target.value);
  };

  const getStatusColor = (dateStart, dateEnd) => {
    const now = new Date();
    const start = new Date(dateStart);
    const end = new Date(dateEnd);

    if (now < start) return 'primary'; // Upcoming
    if (now > end) return 'default'; // Past
    return 'success'; // In Progress
  };

  const getStatusLabel = (dateStart, dateEnd) => {
    const now = new Date();
    const start = new Date(dateStart);
    const end = new Date(dateEnd);

    if (now < start) return 'Upcoming';
    if (now > end) return 'Past';
    return 'In Progress';
  };

  const filteredEvents = events.filter(event => {
    // Exclude Workshop and Scrimmage events
    if (event.eventType === 'Workshop' || event.eventType === 'Scrimmage') {
      return false;
    }

    const matchesSearch = 
      (event.eventName?.toLowerCase() || '').includes(searchText.toLowerCase()) ||
      (event.city?.toLowerCase() || '').includes(searchText.toLowerCase()) ||
      (event.state?.toLowerCase() || '').includes(searchText.toLowerCase());
    
    const status = getStatusLabel(event.dateStart, event.dateEnd).toLowerCase();
    const matchesFilter = filter === 'all' || status === filter.toLowerCase();

    return matchesSearch && matchesFilter;
  }).sort((a, b) => {
    // Sort by dateStart (ascending order - earliest events first)
    return new Date(a.dateStart) - new Date(b.dateStart);
  });

  return (
    <PageTransition>
      <Container maxWidth="xl">
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Typography variant="h4" gutterBottom>
              Events
            </Typography>
          </Grid>

          {/* Filters */}
          <Grid item xs={12} md={6}>
            <FormControl fullWidth>
              <InputLabel>Filter by Status</InputLabel>
              <Select
                value={filter}
                onChange={handleFilterChange}
                label="Filter by Status"
              >
                <MenuItem value="upcoming">Upcoming Events</MenuItem>
                <MenuItem value="all">All Events</MenuItem>
                <MenuItem value="past">Past Events</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          {/* Search Bar */}
          <Grid item xs={12} md={6}>
            <Box sx={{ mb: 3 }}>
              <TextField
                fullWidth
                variant="outlined"
                placeholder="Search events..."
                size="small"
                value={searchText}
                onChange={handleSearch}
              />
            </Box>
          </Grid>

          {/* Error Message */}
          {error && (
            <Grid item xs={12}>
              <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>
              <Button 
                variant="contained" 
                color="primary" 
                onClick={fetchEvents}
                sx={{ mb: 2 }}
              >
                Retry
              </Button>
            </Grid>
          )}

          {/* Loading Spinner */}
          {loading ? (
            <Grid item xs={12} sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
              <CircularProgress />
            </Grid>
          ) : (
            /* Events Grid */
            <Grid item xs={12}>
              <Grid container spacing={3}>
                {filteredEvents.length === 0 ? (
                  <Grid item xs={12}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      No events found
                    </Paper>
                  </Grid>
                ) : (
                  filteredEvents.map((event) => (
                    <Grid item xs={12} sm={6} md={4} key={`2024-${event.eventCode}`}>
                      <Card sx={{ height: '100%' }}>
                        <CardActionArea onClick={() => navigate(`/events/2024/${event.eventCode}`)}>
                          <CardContent>
                            <Typography variant="h6" gutterBottom>
                              {event.eventName}
                            </Typography>
                            <Typography color="textSecondary" gutterBottom>
                              {new Date(event.dateStart).toLocaleDateString()} - {new Date(event.dateEnd).toLocaleDateString()}
                            </Typography>
                            <Typography gutterBottom>
                              {event.city}, {event.state}
                            </Typography>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 2 }}>
                              <Chip
                                label={getStatusLabel(event.dateStart, event.dateEnd)}
                                color={getStatusColor(event.dateStart, event.dateEnd)}
                                size="small"
                              />
                              <Typography variant="body2" color="textSecondary">
                                {event.eventType}
                              </Typography>
                            </Box>
                          </CardContent>
                        </CardActionArea>
                      </Card>
                    </Grid>
                ))
              )}
            </Grid>
          </Grid>
        )}
      </Grid>
    </Container>
    </PageTransition>
  );
}

export default Events;