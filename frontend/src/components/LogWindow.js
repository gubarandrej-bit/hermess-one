import React from 'react';
export const LogWindow = ({ logs }) => (
  <div style={{ backgroundColor: '#000', color: '#0f0', padding: '20px', fontFamily: 'monospace', height: '400px', overflowY: 'auto' }}>
    {logs.map((l, i) => <div key={i}>{l}</div>)}
  </div>
);
