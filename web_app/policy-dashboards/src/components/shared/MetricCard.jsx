import React from 'react';

/**
 * MetricCard Component
 * Display key metrics with optional positive/negative/neutral tone
 */
export default function MetricCard({ value, label, tone = "neutral" }) {
  const colors = { 
    positive: "#1D9E75", 
    negative: "#D85A30", 
    neutral: "#222" 
  };
  
  return (
    <div style={{ 
      background: "#f5f5f2", 
      borderRadius: 8, 
      padding: 14 
    }}>
      <div style={{ 
        fontSize: 22, 
        fontWeight: 500, 
        color: colors[tone] 
      }}>
        {value}
      </div>
      <div style={{ 
        fontSize: 12, 
        color: "#888", 
        marginTop: 3 
      }}>
        {label}
      </div>
    </div>
  );
}
