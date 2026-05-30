import React from 'react';

/**
 * BarMeter Component
 * Reusable horizontal bar chart for showing metrics
 */
export default function BarMeter({ label, value, max = 100, color = "#D85A30", suffix = "%" }) {
  const pct = Math.min((value / max) * 100, 100);
  
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
        <span style={{ fontSize: 13, color: "#555" }}>{label}</span>
        <span style={{ fontSize: 13, fontWeight: 500 }}>
          {value}{suffix}
        </span>
      </div>
      <div style={{ 
        height: 8, 
        background: "#f0f0ee", 
        borderRadius: 99, 
        overflow: "hidden" 
      }}>
        <div style={{ 
          height: "100%", 
          width: `${pct}%`, 
          background: color, 
          borderRadius: 99, 
          transition: "width 0.6s ease" 
        }} />
      </div>
    </div>
  );
}
