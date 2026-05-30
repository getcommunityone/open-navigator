import React from 'react';

/**
 * InsightBox Component
 * Bottom summary box with "The logic" explanation
 */
export default function InsightBox({ title = "The logic", children, type = "default" }) {
  const styles = {
    default: {
      background: '#f5f5f2',
      borderLeft: 'none'
    },
    warning: {
      background: '#fff4e6',
      borderLeft: '3px solid #BA7517'
    },
    critical: {
      background: '#ffe6e6',
      borderLeft: '3px solid #D85A30'
    }
  };
  
  const style = styles[type] || styles.default;
  
  return (
    <div style={{ 
      ...style,
      borderRadius: 8, 
      padding: 14, 
      fontSize: 13, 
      color: '#555',
      marginTop: 16 
    }}>
      <strong style={{ color: '#222' }}>{title}:</strong> {children}
    </div>
  );
}
