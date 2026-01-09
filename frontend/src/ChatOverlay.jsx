import React, { useState, useRef } from 'react';
import { Box, TextField, Button, Modal, Typography, Fab } from '@mui/material';
import MicIcon from '@mui/icons-material/Mic';

const ChatOverlay = ({ uiAction, onSend, onAudio }) => {
  const [input, setInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorder = useRef(null);
  const audioChunks = useRef([]);

  const handleSend = () => {
    onSend(input);
    setInput('');
  };

  // Audio Recording Logic
  const startRecording = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder.current = new MediaRecorder(stream);
    mediaRecorder.current.ondataavailable = (e) => audioChunks.current.push(e.data);
    mediaRecorder.current.onstop = () => {
      const blob = new Blob(audioChunks.current, { type: 'audio/webm' });
      onAudio(blob);
      audioChunks.current = [];
    };
    mediaRecorder.current.start();
    setIsRecording(true);
  };

  const stopRecording = () => {
    mediaRecorder.current.stop();
    setIsRecording(false);
  };

  return (
    <>
      {/* UI Action Modal */}
      <Modal open={!!uiAction.type} onClose={() => {}}>
        <Box sx={{
          position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
          width: 400, bgcolor: 'background.paper', p: 4, boxShadow: 24, borderRadius: 2
        }}>
          <Typography variant="h6" gutterBottom>{uiAction.title}</Typography>
          <Typography variant="body1" gutterBottom>{uiAction.message}</Typography>
          {uiAction.options && uiAction.options.map(opt => (
            <Button key={opt} variant="contained" sx={{ m: 1 }} onClick={() => onSend(opt)}>
              {opt}
            </Button>
          ))}
        </Box>
      </Modal>

      {/* Floating Chat Input */}
      <Box sx={{
        position: 'fixed', bottom: 20, right: 20, width: 300,
        display: 'flex', gap: 1, bgcolor: 'white', p: 1, borderRadius: 2, boxShadow: 3
      }}>
        <TextField
          fullWidth
          size="small"
          placeholder="Command Aethel..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <Fab size="small" color={isRecording ? "secondary" : "primary"} onClick={isRecording ? stopRecording : startRecording}>
          <MicIcon />
        </Fab>
        <Button variant="contained" onClick={handleSend}>Send</Button>
      </Box>
    </>
  );
};

export default ChatOverlay;