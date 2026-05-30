import React from 'react';
import { summaryData as d } from '../data/dashboardData';
import { DashboardGrid } from './shared/DashboardTile';

/**
 * Summary Dashboard
 * Overview of all four findings with tile-based navigation
 */
export default function Summary({ onNavigate }) {
  return (
    <div>
      {/* Headline */}
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 18, fontWeight: 500, color: '#222', marginBottom: 8 }}>
          {d.headline}
        </h2>
        <p style={{ fontSize: 14, color: '#666' }}>
          {d.subheadline}
        </p>
      </div>

      {/* Dashboard Tiles */}
      <DashboardGrid 
        dashboards={d.findings} 
        onNavigate={onNavigate}
      />

      {/* Legacy Finding Cards - Keep for compact view */}
      <details style={{ marginBottom: 24 }}>
        <summary style={{ 
          cursor: 'pointer', 
          fontSize: 13, 
          color: '#888',
          marginBottom: 12
        }}>
          Show compact list view
        </summary>
        <div style={{ 
          display: 'grid', 
          gap: 12
        }}>
          {d.findings.map((finding, i) => (
            <div 
              key={finding.id}
              onClick={() => onNavigate && onNavigate(finding.id)}
              style={{ 
                background: '#fff',
                border: '1px solid #eee',
                borderLeft: `4px solid ${finding.discomfort >= 9 ? '#D85A30' : '#BA7517'}`,
                borderRadius: 8,
                padding: 16,
                cursor: onNavigate ? 'pointer' : 'default',
                transition: 'all 0.2s ease'
              }}
              onMouseEnter={(e) => {
                if (onNavigate) {
                  e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)';
                  e.currentTarget.style.borderLeftWidth = '6px';
                }
              }}
              onMouseLeave={(e) => {
                if (onNavigate) {
                  e.currentTarget.style.boxShadow = 'none';
                  e.currentTarget.style.borderLeftWidth = '4px';
                }
              }}
            >
            <div style={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'flex-start',
              marginBottom: 8
            }}>
              <div>
                <div style={{ 
                  fontSize: 11, 
                  color: '#999', 
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  marginBottom: 4
                }}>
                  Dashboard {finding.id}
                </div>
                <div style={{ fontSize: 15, fontWeight: 500, color: '#222' }}>
                  {finding.title}
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ 
                  fontSize: 18, 
                  fontWeight: 500, 
                  color: finding.discomfort >= 9 ? '#D85A30' : '#BA7517' 
                }}>
                  {finding.metric}
                </div>
                <div style={{ fontSize: 11, color: '#888' }}>
                  {finding.context}
                </div>
              </div>
            </div>
            <p style={{ fontSize: 13, color: '#666', lineHeight: 1.5 }}>
              {finding.summary}
            </p>
            {finding.discomfort >= 9 && (
              <div style={{ 
                marginTop: 8,
                fontSize: 11,
                color: '#D85A30',
                fontWeight: 500
              }}>
                ⚠️ High accountability impact
              </div>
            )}
          </div>
        ))}
        </div>
      </details>

      {/* How to Use Section */}
      <div style={{
        background: '#f5f5f2',
        borderRadius: 8,
        padding: 18,
        marginBottom: 20
      }}>
        <h3 style={{ 
          fontSize: 14, 
          fontWeight: 500, 
          color: '#222',
          marginBottom: 12
        }}>
          {d.howToUse.title}
        </h3>
        
        <div style={{ display: 'grid', gap: 12 }}>
          {d.howToUse.strategies.map((strategy, i) => (
            <div key={i} style={{ 
              display: 'grid', 
              gridTemplateColumns: '1fr 1fr',
              gap: 12
            }}>
              <div>
                <div style={{ 
                  fontSize: 11, 
                  color: '#E24B4A',
                  fontWeight: 500,
                  marginBottom: 4
                }}>
                  ❌ DON'T: {strategy.dont}
                </div>
              </div>
              <div>
                <div style={{ 
                  fontSize: 11, 
                  color: '#1D9E75',
                  fontWeight: 500,
                  marginBottom: 4
                }}>
                  ✅ DO: {strategy.do}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Bottom Navigation Hint */}
      {onNavigate && (
        <div style={{ 
          textAlign: 'center',
          fontSize: 12,
          color: '#888',
          padding: 12,
          background: '#fff',
          border: '1px dashed #ddd',
          borderRadius: 8
        }}>
          💡 Click any finding above to see the detailed dashboard
        </div>
      )}
    </div>
  );
}
