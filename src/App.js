import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Teams from './pages/teams';
import Events from './pages/Events';
import EventDetails from './pages/EventDetails';
import Home from './pages/Home';
import Navbar from './components/Navbar';
import TeamDetails from './pages/teamDetails';  // Fixed to match actual filename
import AdminLogin from './pages/AdminLogin';
import AdminDashboard from './pages/AdminDashboard';
import ProtectedRoute from './components/ProtectedRoute';
import { ThemeProvider } from '@mui/material';
import { theme } from './theme/theme';
import CssBaseline from '@mui/material/CssBaseline';
import './aws-config'; // Initialize AWS Amplify configuration

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <div className="App">
          <Navbar />
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/teams" element={<Teams />} />
            <Route path="/events" element={<Events />} />
            <Route path="/events/:season/:eventCode" element={<EventDetails />} />
            <Route path="/team/:teamNumber" element={<TeamDetails />} />
            <Route path="/admin" element={<AdminLogin />} />
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