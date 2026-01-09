import React from 'react';
import { List, ListItem, ListItemText, ListItemIcon, Typography } from '@mui/material';

const getIcon = (action) => {
  switch(action) {
    case 'fs_move': return '📂';
    case 'kg_search': return '🔍';
    case 'ask_user': return '❓';
    default: return '⚙️';
  }
};

const Timeline = ({ steps }) => {
  return (
    <List>
      {steps.map((step) => (
        <ListItem key={step.step_id} divider>
          <ListItemIcon>{getIcon(step.action)}</ListItemIcon>
          <ListItemText
            primary={step.action || 'Thinking...'}
            secondary={
              <Typography variant="caption" component="div">
                {step.result}
              </Typography>
            }
          />
        </ListItem>
      ))}
    </List>
  );
};

export default Timeline;