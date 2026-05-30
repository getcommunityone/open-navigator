import React from 'react';
import BarMeter from './shared/BarMeter';
import MetricCard from './shared/MetricCard';
import Compare from './shared/Compare';
import InsightBox from './shared/InsightBox';
import { influenceData as d } from '../data/dashboardData';

const colors = { blocker: '#E24B4A', public: '#185FA5' };

/**
 * Dashboard 4: One memo beat 240 residents
 * (Influence Radar)
 */
export default function WhoIsInCharge() {
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

      {/* Influence Bars */}
      <div style={{ marginBottom: 20 }}>
        <h4 style={{ 
          fontSize: 12, 
          textTransform: 'uppercase', 
          letterSpacing: '0.05em', 
          color: '#999',
          marginBottom: 12
        }}>
          Influence on Final Decision
        </h4>
        
        {d.actors.map((item, i) => (
          <div key={i} style={{ marginBottom: 12 }}>
            <BarMeter 
              label={item.actor} 
              value={item.influence} 
              color={colors[item.type]} 
            />
            <div style={{ 
              fontSize: 11, 
              color: '#888', 
              marginLeft: 12, 
              marginTop: -8,
              marginBottom: 8
            }}>
              {item.contactName && `Contact: ${item.contactName}`}
            </div>
          </div>
        ))}
      </div>

      {/* Key Metrics */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: '1fr 1fr', 
        gap: 12, 
        marginBottom: 20 
      }}>
        <MetricCard 
          value={`${d.publicComments}+`} 
          label="Public comments in support" 
        />
        <MetricCard 
          value="1" 
          label="Memo that blocked the policy" 
          tone="negative" 
        />
      </div>

      {/* Veto Holder Callout */}
      <div style={{
        background: '#ffe6e6',
        border: '2px solid #E24B4A',
        borderRadius: 8,
        padding: 14,
        marginBottom: 20
      }}>
        <div style={{ fontSize: 11, color: '#999', textTransform: 'uppercase', marginBottom: 4 }}>
          Effective Veto Holder
        </div>
        <div style={{ fontSize: 16, fontWeight: 500, color: '#E24B4A' }}>
          {d.vetoHolder}
        </div>
        <div style={{ fontSize: 12, color: '#666', marginTop: 6 }}>
          One liability memo had {d.actors.find(a => a.type === 'blocker').influence}% influence 
          despite {d.publicComments}+ citizen testimonies
        </div>
      </div>

      {/* Liability Benchmark */}
      <div style={{ marginTop: 20 }}>
        <h4 style={{ 
          fontSize: 12, 
          textTransform: 'uppercase', 
          letterSpacing: '0.05em', 
          color: '#999',
          marginBottom: 10
        }}>
          Successful Liability Suits in States with Screening Programs
        </h4>
        <Compare 
          benchmarks={d.benchmarks} 
          metric="liabilitySuits"
          prefix=""
          suffix=""
        />
        <p style={{ 
          fontSize: 11, 
          color: '#888',
          marginTop: 8,
          textAlign: 'center'
        }}>
          Source: National Association of School Nurses, ADA Health Policy Institute
        </p>
      </div>

      {/* The Logic */}
      <InsightBox type="critical">
        <strong>{d.powerStructure}:</strong> {d.inference}
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
          "{d.vetoHolder}, can you please stand and explain to these {d.publicComments} citizens 
          why your one memo expressing 'liability concerns' outweighed their collective voice? 
          And can you cite a single successful lawsuit in any of the 35 states with active 
          school dental screening programs?"
        </p>
      </div>
    </div>
  );
}
