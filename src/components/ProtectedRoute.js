import React, { useState, useEffect } from 'react';
import { getCurrentUser } from 'aws-amplify/auth';
import { Navigate } from 'react-router-dom';
import { Box, CircularProgress, Typography } from '@mui/material';

const ProtectedRoute = ({ children, requireAuth = false, adminOnly = false }) => {
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);

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
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Box
        display="flex"
        flexDirection="column"
        alignItems="center"
        justifyContent="center"
        minHeight="50vh"
        gap={2}
      >
        <CircularProgress />
        <Typography>Checking authentication...</Typography>
      </Box>
    );
  }

  // If authentication is required but user is not authenticated
  if (requireAuth && !isAuthenticated) {
    return <Navigate to="/admin" replace />;
  }

  // If admin access is required but user is not admin (you can add admin role checking here)
  if (adminOnly && !isAuthenticated) {
    return <Navigate to="/admin" replace />;
  }

  // Render the protected content
  return children;
};

export default ProtectedRoute;
