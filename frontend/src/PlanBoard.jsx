import React from 'react';
import { List, ListItem, Checkbox, ListItemText } from '@mui/material';

const PlanBoard = ({ plan }) => {
  return (
    <List>
      {plan.map((item) => (
        <ListItem key={item.id} dense button>
          <Checkbox checked={item.status === 'done'} disabled />
          <ListItemText 
            primary={item.description} 
            style={{ textDecoration: item.status === 'done' ? 'line-through' : 'none' }}
          />
        </ListItem>
      ))}
    </List>
  );
};

export default PlanBoard;