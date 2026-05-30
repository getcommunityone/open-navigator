import React from 'react';
import BarMeter from './shared/BarMeter';
import MetricCard from './shared/MetricCard';
import Compare from './shared/Compare';
import InsightBox from './shared/InsightBox';
import { rhetoricGapData as d } from '../data/dashboardData';

/**
 * Dashboard 1: They cut health spending while praising wellness
 * (Rhetoric Gap Monitor)
 */
export default function WordsVsDollars() {
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

      {/* Key Metrics */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: '1fr 1fr', 
        gap: 12, 
        marginBottom: 20 
      }}>
        <MetricCard 
          value={`${d.sentimentScore}%`} 
          label='Positive sentiment re: "wellness"' 
          tone="positive" 
        />
        <MetricCard 
          value={`-$${(Math.abs(d.budgetDelta) / 1000).toFixed(0)}k`} 
          label="Budget delta: contracted dental/vision" 
          tone="negative" 
        />
      </div>

      {/* What They SAY */}
      <div style={{ marginBottom: 16 }}>
        <h4 style={{ 
          fontSize: 12, 
          textTransform: 'uppercase', 
          letterSpacing: '0.05em', 
          color: '#999',
          marginBottom: 10
        }}>
          What They SAY
        </h4>
        <BarMeter 
          label="Wellness language in meeting minutes" 
          value={d.sentimentScore} 
          color="#1D9E75" 
        />
        <div style={{ 
          fontSize: 12, 
          color: '#888', 
          fontStyle: 'italic',
          marginTop: 8,
          paddingLeft: 12,
          borderLeft: '2px solid #f0f0ee'
        }}>
          <p style={{ marginBottom: 6 }}>Sample quotes ({d.totalMentions} total mentions):</p>
          {d.sampleQuotes.slice(0, 2).map((quote, i) => (
            <p key={i} style={{ marginBottom: 4 }}>"{quote}"</p>
          ))}
        </div>
      </div>

      {/* What They FUND */}
      <div style={{ marginBottom: 16 }}>
        <h4 style={{ 
          fontSize: 12, 
          textTransform: 'uppercase', 
          letterSpacing: '0.05em', 
          color: '#999',
          marginBottom: 10
        }}>
          What They FUND
        </h4>
        <BarMeter 
          label={`${d.budgetCategory} vs. prior year`} 
          value={100 + d.budgetDeltaPercent} 
          max={100}
          color="#D85A30" 
          suffix="% of last year" 
        />
        <BarMeter 
          label="Admin cost growth (same period)" 
          value={d.adminCostGrowth} 
          max={100}
          color="#BA7517" 
          suffix="% increase" 
        />
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
          Per-Student Health Spending Comparison
        </h4>
        <Compare 
          benchmarks={d.benchmarks} 
          metric="perStudent"
          prefix="$"
          suffix="/student"
        />
        <p style={{ 
          fontSize: 11, 
          color: '#888',
          marginTop: 8,
          textAlign: 'center'
        }}>
          Source: NCES Common Core of Data (CCD), FY2025
        </p>
      </div>

      {/* The Logic */}
      <InsightBox type="critical">
        {d.inference}
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
          "You've praised student wellness {d.totalMentions} times this year with {d.sentimentScore}% 
          positive sentiment. But you cut the health budget by ${Math.abs(d.budgetDelta).toLocaleString()}. 
          Which statement is true: your words or your wallet?"
        </p>
      </div>
    </div>
  );
}
