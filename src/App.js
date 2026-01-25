import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, useLocation } from 'react-router-dom';
import Teams from './pages/teams';
import Events from './pages/Events';
import EventDetails from './pages/EventDetails';
import Home from './pages/Home';
import Navbar from './components/Navbar';
import TeamDetails from './pages/teamDetails';  // Fixed to match actual filename
import AdminLogin from './pages/AdminLogin';
import AdminDashboard from './pages/AdminDashboard';
import TestAwsApi from './pages/TestAwsApi';
import ProtectedRoute from './components/ProtectedRoute';
import { ThemeProvider } from '@mui/material';
import { theme } from './theme/theme';
import CssBaseline from '@mui/material/CssBaseline';
import './aws-config'; // Initialize AWS Amplify configuration

function RouteChangeTracker() {
  const location = useLocation();

  useEffect(() => {
    if (typeof window !== 'undefined' && typeof window.gtag === 'function') {
      const pagePath = `${location.pathname}${location.search}${location.hash}`;
      window.gtag('config', 'G-WWZH9P80V8', { page_path: pagePath });
    }
  }, [location.pathname, location.search, location.hash]);

  return null;
}

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <div className="App">
          <RouteChangeTracker />
          <Navbar />
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/teams" element={<Teams />} />
            <Route path="/events" element={<Events />} />
            <Route path="/events/:season/:eventCode" element={<EventDetails />} />
            <Route path="/team/:teamNumber" element={<TeamDetails />} />
            <Route path="/admin" element={<AdminLogin />} />
            <Route path="/test-aws-api" element={<TestAwsApi />} />
            <Route 
              path="/admin/dashboard" 
              element={
                <ProtectedRoute requireAuth>
                  <AdminDashboard />
                </ProtectedRoute>
              } 
            />
          </Routes>
        </div>
      </Router>
    </ThemeProvider>
  );
}

export default App;