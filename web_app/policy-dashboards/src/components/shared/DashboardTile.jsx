import React from 'react';
import { ArrowRight, TrendingUp, Clock, DollarSign, Users } from 'lucide-react';

/**
 * DashboardTile Component
 * Tile-based navigation for dashboards
 */
export default function DashboardTile({ 
  id, 
  title, 
  metric, 
  context, 
  summary, 
  discomfort,
  icon: Icon,
  onClick 
}) {
  const getDiscomfortColor = (score) => {
    if (score >= 9) return '#D85A30';
    if (score >= 7) return '#BA7517';
    return '#888';
  };
  
  return (
    <div
      onClick={() => onClick(id)}
      style={{
        background: 'white',
        border: '1px solid #eee',
        borderRadius: 12,
        padding: 18,
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        position: 'relative',
        overflow: 'hidden'
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
        e.currentTarget.style.transform = 'translateY(-2px)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = 'none';
        e.currentTarget.style.transform = 'translateY(0)';
      }}
    >
      {/* Discomfort indicator */}
      <div style={{
        position: 'absolute',
        top: 0,
        right: 0,
        width: 60,
        height: 60,
        background: getDiscomfortColor(discomfort),
        borderBottomLeft: '60px solid transparent',
        opacity: 0.1
      }} />
      
      {/* Icon */}
      {Icon && (
        <div style={{
          width: 40,
          height: 40,
          borderRadius: 8,
          background: '#f5f5f2',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: 12,
          color: getDiscomfortColor(discomfort)
        }}>
          <Icon size={20} />
        </div>
      )}
      
      {/* Title */}
      <h3 style={{
        fontSize: 15,
        fontWeight: 500,
        color: '#222',
        marginBottom: 8,
        lineHeight: 1.3
      }}>
        {title}
      </h3>
      
      {/* Metrics */}
      <div style={{
        display: 'flex',
        gap: 12,
        marginBottom: 10
      }}>
        <div>
          <div style={{
            fontSize: 20,
            fontWeight: 500,
            color: getDiscomfortColor(discomfort)
          }}>
            {metric}
          </div>
          <div style={{
            fontSize: 11,
            color: '#888'
          }}>
            {context}
          </div>
        </div>
      </div>
      
      {/* Summary */}
      <p style={{
        fontSize: 12,
        color: '#666',
        lineHeight: 1.5,
        marginBottom: 12
      }}>
        {summary}
      </p>
      
      {/* Footer */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <div style={{
          fontSize: 11,
          color: getDiscomfortColor(discomfort),
          fontWeight: 500
        }}>
          {discomfort >= 9 ? '⚠️ High Impact' : discomfort >= 7 ? '⚡ Medium Impact' : '📊 Analysis'}
        </div>
        <div style={{
          fontSize: 12,
          color: '#666',
          display: 'flex',
          alignItems: 'center',
          gap: 4
        }}>
          View Details
          <ArrowRight size={14} />
        </div>
      </div>
    </div>
  );
}

/**
 * DashboardGrid Component
 * Grid layout for dashboard tiles
 */
export function DashboardGrid({ dashboards, onNavigate }) {
  const icons = [TrendingUp, Clock, DollarSign, Users];
  
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
      gap: 16,
      marginBottom: 24
    }}>
      {dashboards.map((dashboard, i) => (
        <DashboardTile
          key={dashboard.id}
          {...dashboard}
          icon={icons[i % icons.length]}
          onClick={onNavigate}
        />
      ))}
    </div>
  );
}
