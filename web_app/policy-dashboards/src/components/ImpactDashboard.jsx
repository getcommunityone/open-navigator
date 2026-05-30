import React from 'react';
import { XCircle, AlertTriangle, MapPin } from 'lucide-react';

/**
 * ImpactDashboard Component
 * Visual impact story for specific persona + topic combination
 */
export default function ImpactDashboard({ persona, topic }) {
  // Example: Parent + Dental Health
  if (persona === 'parent' && topic === 'dental-health') {
    return <DentalHealthImpact />;
  }
  
  // Example: Advocate + Transparency
  if (persona === 'advocate' && topic === 'transparency') {
    return <TransparencyImpact />;
  }
  
  // Default fallback
  return <GenericImpact persona={persona} topic={topic} />;
}

function DentalHealthImpact() {
  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 11, color: '#999', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>
          Impact Story: Parent → Student Dental Health
        </div>
        <h2 style={{ fontSize: 20, fontWeight: 500, color: '#222', marginBottom: 8 }}>
          The School Dental Screening Veto
        </h2>
        <p style={{ fontSize: 14, color: '#D85A30', fontWeight: 500 }}>
          A legal "Risk Rationale" is blocking healthcare for 5,000 students
        </p>
      </div>

      {/* The Visual Split */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: '1fr 1fr', 
        gap: 20,
        marginBottom: 24
      }}>
        {/* Left: The Human Cost */}
        <div style={{
          background: 'white',
          border: '2px solid #eee',
          borderRadius: 12,
          padding: 20
        }}>
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: 8,
            marginBottom: 16
          }}>
            <MapPin size={20} color="#D85A30" />
            <h3 style={{ fontSize: 16, fontWeight: 500, margin: 0 }}>
              The Human Cost
            </h3>
          </div>
          
          {/* School Map Placeholder */}
          <div style={{
            background: '#f5f5f2',
            borderRadius: 8,
            padding: 16,
            marginBottom: 16,
            minHeight: 200,
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
            color: '#888'
          }}>
            <MapPin size={32} color="#D85A30" style={{ marginBottom: 8 }} />
            <div style={{ fontSize: 13, textAlign: 'center' }}>
              Map of Tuscaloosa Schools
            </div>
            <div style={{ fontSize: 11, textAlign: 'center', marginTop: 4 }}>
              Red = High dental pain absence rates
            </div>
            <div style={{ fontSize: 11, textAlign: 'center', color: '#185FA5' }}>
              Blue dots = Mobile clinics (currently: 0)
            </div>
          </div>
          
          {/* Stats */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div style={{ background: '#ffe6e6', borderRadius: 6, padding: 12 }}>
              <div style={{ fontSize: 20, fontWeight: 500, color: '#D85A30' }}>
                48%
              </div>
              <div style={{ fontSize: 11, color: '#666' }}>
                Students with no dental visit last year
              </div>
            </div>
            <div style={{ background: '#fff4e6', borderRadius: 6, padding: 12 }}>
              <div style={{ fontSize: 20, fontWeight: 500, color: '#BA7517' }}>
                127
              </div>
              <div style={{ fontSize: 11, color: '#666' }}>
                Days missed due to dental pain (2025)
              </div>
            </div>
          </div>
        </div>

        {/* Right: The Veto */}
        <div style={{
          background: 'white',
          border: '2px solid #eee',
          borderRadius: 12,
          padding: 20
        }}>
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: 8,
            marginBottom: 16
          }}>
            <XCircle size={20} color="#E24B4A" />
            <h3 style={{ fontSize: 16, fontWeight: 500, margin: 0 }}>
              The Veto Chain
            </h3>
          </div>
          
          {/* Flowchart */}
          <div style={{ position: 'relative' }}>
            {/* Step 1: Public Demand */}
            <div style={{
              background: '#e6f4f1',
              border: '2px solid #1D9E75',
              borderRadius: 8,
              padding: 12,
              marginBottom: 16
            }}>
              <div style={{ fontSize: 12, fontWeight: 500, color: '#1D9E75', marginBottom: 4 }}>
                ✓ Public Demand
              </div>
              <div style={{ fontSize: 13, color: '#222' }}>
                1,200 Signed Petitions
              </div>
              <div style={{ fontSize: 11, color: '#666', marginTop: 4 }}>
                240+ Testimonies at board meetings
              </div>
            </div>
            
            {/* Arrow */}
            <div style={{ 
              textAlign: 'center', 
              margin: '-8px 0',
              fontSize: 20,
              color: '#D85A30',
              fontWeight: 'bold'
            }}>
              ↓ BLOCKED
            </div>
            
            {/* Step 2: The Blocker */}
            <div style={{
              background: '#ffe6e6',
              border: '2px solid #E24B4A',
              borderRadius: 8,
              padding: 12,
              marginBottom: 16,
              marginTop: 8
            }}>
              <div style={{ fontSize: 12, fontWeight: 500, color: '#E24B4A', marginBottom: 4 }}>
                ✗ The Blocker
              </div>
              <div style={{ fontSize: 13, color: '#222', fontWeight: 500 }}>
                Risk Management Memo
              </div>
              <div style={{ fontSize: 11, color: '#666', marginTop: 4 }}>
                From: Patricia Johnson, District Legal Office
              </div>
              <div style={{ fontSize: 11, color: '#666' }}>
                Concern: "Insurance Liability"
              </div>
            </div>
            
            {/* Arrow */}
            <div style={{ 
              textAlign: 'center', 
              margin: '-8px 0',
              fontSize: 20,
              color: '#888'
            }}>
              ↓
            </div>
            
            {/* Step 3: The Result */}
            <div style={{
              background: '#f5f5f2',
              border: '2px solid #888',
              borderRadius: 8,
              padding: 12,
              marginTop: 8
            }}>
              <div style={{ fontSize: 12, fontWeight: 500, color: '#888', marginBottom: 4 }}>
                The Result
              </div>
              <div style={{ fontSize: 13, color: '#222' }}>
                Board votes to "Table" initiative
              </div>
              <div style={{ fontSize: 11, color: '#D85A30', marginTop: 4 }}>
                Status: Deferred for 152 days
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom: Key Fact */}
      <div style={{
        background: '#fff4e6',
        border: '2px solid #BA7517',
        borderRadius: 12,
        padding: 16,
        display: 'flex',
        alignItems: 'flex-start',
        gap: 12
      }}>
        <AlertTriangle size={24} color="#BA7517" />
        <div>
          <div style={{ fontSize: 14, fontWeight: 500, color: '#222', marginBottom: 4 }}>
            Key Finding
          </div>
          <div style={{ fontSize: 13, color: '#555' }}>
            Zero successful liability lawsuits in any of the 35 states with active school dental screening programs. 
            The "risk" cited in the memo has no empirical basis.
          </div>
        </div>
      </div>
    </div>
  );
}

function TransparencyImpact() {
  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 11, color: '#999', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>
          Impact Story: Advocate → Transparency & Vetoes
        </div>
        <h2 style={{ fontSize: 20, fontWeight: 500, color: '#222', marginBottom: 8 }}>
          Who Really Decides?
        </h2>
        <p style={{ fontSize: 14, color: '#D85A30', fontWeight: 500 }}>
          Unelected staff have veto power that outweighs public input
        </p>
      </div>
      
      <div style={{ fontSize: 13, color: '#666', marginBottom: 16 }}>
        See the Influence Radar dashboard for detailed analysis →
      </div>
    </div>
  );
}

function GenericImpact({ persona, topic }) {
  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 11, color: '#999', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>
          Impact Story: {persona} → {topic}
        </div>
        <h2 style={{ fontSize: 20, fontWeight: 500, color: '#222', marginBottom: 8 }}>
          Coming Soon
        </h2>
        <p style={{ fontSize: 14, color: '#666' }}>
          This impact story is being developed. Check back soon or browse other topics.
        </p>
      </div>
    </div>
  );
}
