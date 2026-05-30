import React from 'react';

/**
 * Compare Component
 * Four-column comparison: This District → Republican → Democratic → National
 */
export default function Compare({ benchmarks, metric = "value", prefix = "$", suffix = "" }) {
  const buckets = [
    { key: 'thisDistrict', color: '#D85A30' },
    { key: 'republicanAvg', color: '#BA7517' },
    { key: 'democraticAvg', color: '#185FA5' },
    { key: 'nationalAvg', color: '#1D9E75' }
  ];
  
  return (
    <div style={{ 
      display: 'grid', 
      gridTemplateColumns: 'repeat(4, 1fr)', 
      gap: 10,
      marginTop: 16 
    }}>
      {buckets.map(bucket => {
        const data = benchmarks[bucket.key];
        const value = typeof data === 'object' ? data[metric] : data;
        const label = typeof data === 'object' ? data.label : bucket.key;
        
        return (
          <div 
            key={bucket.key}
            style={{ 
              background: '#f5f5f2', 
              borderRadius: 8, 
              padding: 12,
              borderTop: `3px solid ${bucket.color}`
            }}
          >
            <div style={{ 
              fontSize: 18, 
              fontWeight: 500, 
              color: bucket.color,
              marginBottom: 4
            }}>
              {prefix}{value}{suffix}
            </div>
            <div style={{ 
              fontSize: 10, 
              color: '#888',
              textTransform: 'uppercase',
              letterSpacing: '0.05em'
            }}>
              {label}
            </div>
          </div>
        );
      })}
    </div>
  );
}
