import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Alert,
  Container,
  IconButton,
  InputAdornment,
} from '@mui/material';
import {
  Visibility,
  VisibilityOff,
  AdminPanelSettings,
} from '@mui/icons-material';
import { signIn, getCurrentUser, signOut } from 'aws-amplify/auth';
import { useNavigate } from 'react-router-dom';

const AdminLogin = () => {
  const [credentials, setCredentials] = useState({
    username: '',
    password: ''
  });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const navigate = useNavigate();

  // Check if user is already authenticated
  useEffect(() => {
    checkAuthState();
  }, []);

  const checkAuthState = async () => {
    try {
      const currentUser = await getCurrentUser();
      setUser(currentUser);
      setIsAuthenticated(true);
    } catch (error) {
      setIsAuthenticated(false);
      setUser(null);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setCredentials(prev => ({
      ...prev,
      [name]: value
    }));
    // Clear error when user starts typing
    if (error) setError('');
  };

  const handleSignIn = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const { isSignedIn } = await signIn({
        username: credentials.username,
        password: credentials.password,
      });

      if (isSignedIn) {
        await checkAuthState();
        // Redirect to admin dashboard
        navigate('/admin/dashboard');
      }
    } catch (error) {
      console.error('Sign in error:', error);
      
      // Handle different error types
      switch (error.name) {
        case 'NotAuthorizedException':
          setError('Invalid username or password');
          break;
        case 'UserNotConfirmedException':
          setError('User account is not confirmed');
          break;
        case 'PasswordResetRequiredException':
          setError('Password reset is required');
          break;
        case 'UserNotFoundException':
          setError('User does not exist');
          break;
        case 'TooManyRequestsException':
          setError('Too many failed attempts. Please try again later');
          break;
        default:
          setError(error.message || 'An error occurred during sign in');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSignOut = async () => {
    try {
      await signOut();
      setIsAuthenticated(false);
      setUser(null);
      setCredentials({ username: '', password: '' });
    } catch (error) {
      console.error('Sign out error:', error);
    }
  };

  const togglePasswordVisibility = () => {
    setShowPassword(!showPassword);
  };

  if (isAuthenticated && user) {
    return (
      <Container maxWidth="sm" sx={{ mt: 8 }}>
        <Paper elevation={3} sx={{ p: 4, textAlign: 'center' }}>
          <AdminPanelSettings sx={{ fontSize: 60, color: 'primary.main', mb: 2 }} />
          <Typography variant="h4" gutterBottom color="primary">
            Admin Panel
          </Typography>
          <Typography variant="h6" gutterBottom>
            Welcome, {user.username}!
          </Typography>
          <Typography variant="body1" sx={{ mb: 3 }}>
            You are successfully authenticated as an administrator.
          </Typography>
          
          <Box sx={{ mt: 3, display: 'flex', gap: 2, justifyContent: 'center' }}>
            <Button
              variant="contained"
              onClick={() => navigate('/admin/dashboard')}
              size="large"
            >
              Go to Dashboard
            </Button>
            <Button
              variant="outlined"
              onClick={() => navigate('/')}
              size="large"
            >
              Main App
            </Button>
            <Button
              variant="outlined"
              onClick={handleSignOut}
              size="large"
            >
              Sign Out
            </Button>
          </Box>
        </Paper>
      </Container>
    );
  }

  return (
    <Container maxWidth="sm" sx={{ mt: 8 }}>
      <Paper elevation={3} sx={{ p: 4 }}>
        <Box sx={{ textAlign: 'center', mb: 3 }}>
          <AdminPanelSettings sx={{ fontSize: 60, color: 'primary.main', mb: 2 }} />
          <Typography variant="h4" gutterBottom color="primary">
            Admin Login
          </Typography>
          <Typography variant="body2" color="text.secondary">
            This area is restricted to administrators only
          </Typography>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {error}
          </Alert>
        )}

        <Box component="form" onSubmit={handleSignIn}>
          <TextField
            fullWidth
            name="username"
            label="Username or Email"
            value={credentials.username}
            onChange={handleInputChange}
            margin="normal"
            required
            autoComplete="username"
            autoFocus
            disabled={loading}
            variant="outlined"
          />

          <TextField
            fullWidth
            name="password"
            label="Password"
            type={showPassword ? 'text' : 'password'}
            value={credentials.password}
            onChange={handleInputChange}
            margin="normal"
            required
            autoComplete="current-password"
            disabled={loading}
            variant="outlined"
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    aria-label="toggle password visibility"
                    onClick={togglePasswordVisibility}
                    edge="end"
                    disabled={loading}
                  >
                    {showPassword ? <VisibilityOff /> : <Visibility />}
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />

          <Button
            type="submit"
            fullWidth
            variant="contained"
            size="large"
            disabled={loading}
            sx={{ mt: 3, mb: 2 }}
          >
            {loading ? 'Signing In...' : 'Sign In'}
          </Button>
        </Box>

        <Box sx={{ textAlign: 'center', mt: 2 }}>
          <Typography variant="body2" color="text.secondary">
            Contact Big Dawg Ishaan if you need access
          </Typography>
        </Box>
      </Paper>
    </Container>
  );
};

export default AdminLogin;
