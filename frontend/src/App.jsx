import React, { useEffect, useState } from 'react';
import { Container, Grid, Paper, Typography, AppBar, Toolbar } from '@mui/material';
import Timeline from './Timeline';
import PlanBoard from './PlanBoard';
import ChatOverlay from './ChatOverlay';
import axios from 'axios';

function App() {
  const [scratchpad, setScratchpad] = useState(null);

  useEffect(() => {
    // WebSocket connection
    const ws = new WebSocket('ws://localhost:8000/ws');
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setScratchpad(data);
    };

    return () => ws.close();
  }, []);

  const handleUserResponse = async (text) => {
    await axios.post('http://localhost:8000/input', { response: text });
  };

  const handleAudioUpload = async (blob) => {
    const formData = new FormData();
    formData.append('file', blob);
    await axios.post('http://localhost:8000/audio', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
  };

  if (!scratchpad) return <div>Loading Aethel-os...</div>;

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <AppBar position="static" color="primary">
        <Toolbar>
          <Typography variant="h6">Aethel-os</Typography>
        </Toolbar>
      </AppBar>

      <Container maxWidth="xl" sx={{ mt: 2, flexGrow: 1 }}>
        <Grid container spacing={2} sx={{ height: '80vh' }}>
          {/* Left: Timeline */}
          <Grid item xs={3}>
            <Paper sx={{ height: '100%', p: 2, overflow: 'auto' }}>
              <Typography variant="h6" gutterBottom>Execution Log</Typography>
              <Timeline steps={scratchpad.steps} />
            </Paper>
          </Grid>

          {/* Center: Plan */}
          <Grid item xs={6}>
            <Paper sx={{ height: '100%', p: 2, overflow: 'auto' }}>
              <Typography variant="h6" gutterBottom>Current Plan</Typography>
              <PlanBoard plan={scratchpad.plan} />
            </Paper>
          </Grid>

          {/* Right: Chat Overlay (Floating) */}
          <ChatOverlay 
            uiAction={scratchpad.ui_action}
            onSend={handleUserResponse}
            onAudio={handleAudioUpload}
          />
        </Grid>
      </Container>
    </div>
  );
}

export default App;