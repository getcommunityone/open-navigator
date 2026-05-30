import React from 'react';
import MetricCard from './shared/MetricCard';
import Compare from './shared/Compare';
import InsightBox from './shared/InsightBox';
import { logicChainData as d } from '../data/dashboardData';

/**
 * Dashboard 2: Delayed 6 months and counting
 * (Logic Chain / Sequential Deferral)
 */
export default function EndlessStudyLoop() {
  return (
    <div>
      <p style={{ 
        fontSize: 14, 
        color: '#555', 
        borderLeft: '2px solid #D85A30', 
        paddingLeft: 12, 
        marginBottom: 20 
      }}>
        {d.conclusion}
      </p>

      {/* Topic */}
      <div style={{
        background: '#f5f5f2',
        padding: 12,
        borderRadius: 8,
        marginBottom: 16
      }}>
        <div style={{ fontSize: 11, color: '#999', textTransform: 'uppercase', marginBottom: 4 }}>
          Policy Decision
        </div>
        <div style={{ fontSize: 14, fontWeight: 500, color: '#222' }}>
          {d.topic}
        </div>
      </div>

      {/* Key Metrics */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: '1fr 1fr', 
        gap: 12, 
        marginBottom: 20 
      }}>
        <MetricCard 
          value={`${d.totalDeferrals}×`} 
          label={`Times deferred in ${d.monthsInLimbo} months`}
          tone="negative" 
        />
        <MetricCard 
          value={new Set(d.justifications.map(j => j.reason)).size} 
          label="Distinct justifications used" 
        />
      </div>

      {/* The "Study" Loop Timeline */}
      <div style={{ marginBottom: 20 }}>
        <h4 style={{ 
          fontSize: 12, 
          textTransform: 'uppercase', 
          letterSpacing: '0.05em', 
          color: '#999',
          marginBottom: 12
        }}>
          Shifting Justifications
        </h4>
        
        <div style={{ position: 'relative', paddingLeft: 24 }}>
          {/* Vertical timeline line */}
          <div style={{ 
            position: 'absolute', 
            left: 7, 
            top: 8, 
            bottom: 8, 
            width: 1, 
            background: '#ddd' 
          }} />
          
          {d.justifications.map((item, i) => (
            <div key={i} style={{ position: 'relative', marginBottom: 18 }}>
              {/* Timeline dot */}
              <div style={{ 
                position: 'absolute', 
                left: -20, 
                top: 4, 
                width: 8, 
                height: 8, 
                borderRadius: '50%', 
                background: item.status === 'deferred' ? '#D85A30' : '#BA7517',
                border: '1.5px solid',
                borderColor: item.status === 'deferred' ? '#D85A30' : '#BA7517'
              }} />
              
              {/* Timeline content */}
              <div style={{ fontSize: 11, color: '#999', marginBottom: 2 }}>
                {item.month} — <strong>{item.status}</strong>
              </div>
              <div style={{ fontSize: 13, color: '#555' }}>
                "{item.reason}"
              </div>
              {item.speaker && item.speaker !== 'N/A' && (
                <div style={{ fontSize: 11, color: '#888', fontStyle: 'italic', marginTop: 2 }}>
                  — {item.speaker}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Benchmark Comparison */}
      <div style={{ marginTop: 20 }}>
        <h4 style={{ 
          fontSize: 12, 
          textTransform: 'uppercase', 
          letterSpacing: '0.05em', 
          color: '#999',
          marginBottom: 10
        }}>
          School-Linked Dental Programs by State Type
        </h4>
        <Compare 
          benchmarks={d.benchmarks} 
          metric="activePrograms"
          prefix=""
          suffix=" states"
        />
        <p style={{ 
          fontSize: 11, 
          color: '#888',
          marginTop: 8,
          textAlign: 'center'
        }}>
          Source: ASTDD State Oral Health Program Database, 2025
        </p>
      </div>

      {/* The Logic */}
      <InsightBox type="critical">
        <strong>{d.patternType}:</strong> {d.inference}
      </InsightBox>

      {/* Question for the Room */}
      <div style={{
        marginTop: 16,
        padding: 14,
        background: '#fff',
        border: '2px solid #D85A30',
        borderRadius: 8
      }}>
        <strong style={{ fontSize: 13, color: '#D85A30' }}>Ask them:</strong>
        <p style={{ fontSize: 13, color: '#222', marginTop: 6 }}>
          "This proposal has been 'under review' for {d.monthsInLimbo} months with {d.totalDeferrals} deferrals. 
          Each time, you give a different reason. {d.benchmarks.republicanAvg.activePrograms} Republican-led states 
          and {d.benchmarks.democraticAvg.activePrograms} Democratic-led states already have active programs. 
          What analysis are you waiting for that 35 states haven't already completed?"
        </p>
      </div>
    </div>
  );
}
