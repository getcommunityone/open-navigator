import React from 'react';
import Compare from './shared/Compare';
import InsightBox from './shared/InsightBox';
import { displacementData as d } from '../data/dashboardData';

/**
 * Dashboard 3: What got funded instead
 * (Displacement Matrix)
 */
export default function WhereMoneyWent() {
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
          Budget Cycle
        </div>
        <div style={{ fontSize: 14, fontWeight: 500, color: '#222' }}>
          {d.topic}
        </div>
      </div>

      {/* The Matrix Table */}
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, marginBottom: 20 }}>
        <thead>
          <tr>
            {['Funded (winner)', 'Stagnant (loser)', 'Trade-off factor'].map(h => (
              <th key={h} style={{ 
                fontSize: 11, 
                textTransform: 'uppercase', 
                letterSpacing: '0.07em', 
                color: '#999', 
                padding: '8px 10px', 
                borderBottom: '1px solid #eee', 
                textAlign: 'left' 
              }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {d.displacements.map((row, i) => (
            <tr key={i}>
              <td style={{ 
                padding: '10px 10px', 
                borderBottom: '1px solid #f0f0ee', 
                color: '#1D9E75', 
                fontWeight: 500 
              }}>
                {row.winner}
                {row.winnerAmount && ` — $${(row.winnerAmount / 1000).toFixed(0)}k`}
              </td>
              <td style={{ 
                padding: '10px 10px', 
                borderBottom: '1px solid #f0f0ee', 
                color: '#D85A30', 
                fontWeight: 500 
              }}>
                {row.loser}
                {row.loserAmount > 0 && ` — $${(row.loserAmount / 1000).toFixed(0)}k`}
              </td>
              <td style={{ padding: '10px 10px', borderBottom: '1px solid #f0f0ee' }}>
                <span style={{ 
                  fontSize: 11, 
                  padding: '2px 8px', 
                  borderRadius: 99, 
                  background: '#f0f0ee', 
                  color: '#666' 
                }}>
                  {row.tradeoffFactor}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Per-Student Spending Breakdown */}
      <div style={{ marginBottom: 20 }}>
        <h4 style={{ 
          fontSize: 12, 
          textTransform: 'uppercase', 
          letterSpacing: '0.05em', 
          color: '#999',
          marginBottom: 10
        }}>
          Health Capital Spending (Per Student)
        </h4>
        <Compare 
          benchmarks={d.benchmarks} 
          metric="healthCapital"
          prefix="$"
          suffix="/student"
        />
      </div>

      <div style={{ marginBottom: 20 }}>
        <h4 style={{ 
          fontSize: 12, 
          textTransform: 'uppercase', 
          letterSpacing: '0.05em', 
          color: '#999',
          marginBottom: 10
        }}>
          Athletic Capital Spending (Per Student)
        </h4>
        <Compare 
          benchmarks={d.benchmarks} 
          metric="athleticCapital"
          prefix="$"
          suffix="/student"
        />
        <p style={{ 
          fontSize: 11, 
          color: '#888',
          marginTop: 8,
          textAlign: 'center'
        }}>
          Source: NCES F-33 Survey, Capital Outlay by Function, FY2025
        </p>
      </div>

      {/* The Logic */}
      <InsightBox type="critical">
        <strong>{d.priorityPattern}:</strong> {d.inference}
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
          "This budget year, you spent $
          {(d.displacements[0].winnerAmount / 1000).toFixed(0)}k on {d.displacements[0].winner.toLowerCase()} 
          and $0 on {d.displacements[0].loser.toLowerCase()}. Can you explain why turf is worth more than 
          the dental health of 5,000 students?"
        </p>
      </div>
    </div>
  );
}
