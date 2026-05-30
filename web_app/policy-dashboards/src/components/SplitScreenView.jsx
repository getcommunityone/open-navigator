import React from 'react';
import { ExternalLink, Users, DollarSign, Heart, Mail, Phone, Globe } from 'lucide-react';

/**
 * SplitScreenView Component
 * Shows government decisions on the left, community nonprofits on the right
 * Demonstrates the accountability gap and community response
 */
export default function SplitScreenView({ decision, nonprofits = [] }) {
  // Find nonprofits matching this decision's NTEE code
  const matchingNonprofits = nonprofits.filter(np => 
    np.ntee_code === decision.ntee_code ||
    (decision.ntee_code && np.ntee_code?.startsWith(decision.ntee_code[0])) // Match category
  );
  
  const hasGap = decision.community_gap?.nonprofit_filling_gap;
  
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      gap: 24,
      marginTop: 20
    }}>
      {/* LEFT RAIL: The Public Sector (Government Decision) */}
      <div style={{
        background: 'white',
        border: '1px solid #eee',
        borderRadius: 12,
        padding: 24
      }}>
        <div style={{
          fontSize: 12,
          fontWeight: 600,
          color: '#666',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          marginBottom: 16
        }}>
          🏛️ Public Sector Decision
        </div>
        
        <h3 style={{
          fontSize: 18,
          fontWeight: 600,
          color: '#111',
          marginBottom: 12,
          lineHeight: 1.4
        }}>
          {decision.decision_summary}
        </h3>
        
        <div style={{
          background: '#f9f9f7',
          borderRadius: 8,
          padding: 16,
          marginBottom: 16
        }}>
          <div style={{
            fontSize: 13,
            fontWeight: 500,
            color: '#BA7517',
            marginBottom: 8
          }}>
            Official Rationale:
          </div>
          <div style={{
            fontSize: 15,
            color: '#444',
            lineHeight: 1.5
          }}>
            "{decision.primary_rationale}"
          </div>
        </div>
        
        {hasGap && (
          <div style={{
            background: '#FFF5F0',
            border: '1px solid #D85A30',
            borderRadius: 8,
            padding: 16,
            marginBottom: 16
          }}>
            <div style={{
              fontSize: 14,
              fontWeight: 500,
              color: '#D85A30',
              marginBottom: 6,
              display: 'flex',
              alignItems: 'center',
              gap: 6
            }}>
              ⚠️ The Accountability Gap
            </div>
            <div style={{
              fontSize: 14,
              color: '#666',
              lineHeight: 1.5
            }}>
              {decision.community_gap.description}
            </div>
          </div>
        )}
        
        <div style={{
          fontSize: 13,
          color: '#888',
          paddingTop: 12,
          borderTop: '1px solid #eee'
        }}>
          <div>Outcome: <strong>{decision.outcome}</strong></div>
          <div>Vote: {decision.vote_result}</div>
          <div>Date: {new Date(decision.meeting_date).toLocaleDateString()}</div>
        </div>
      </div>
      
      {/* RIGHT RAIL: The Community Sector (Nonprofits) */}
      <div style={{
        background: 'linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)',
        border: '1px solid #10b981',
        borderRadius: 12,
        padding: 24
      }}>
        <div style={{
          fontSize: 12,
          fontWeight: 600,
          color: '#059669',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          marginBottom: 16
        }}>
          🤝 Community Sector Response
        </div>
        
        {matchingNonprofits.length === 0 ? (
          <div style={{
            textAlign: 'center',
            padding: '2rem',
            color: '#666'
          }}>
            <p style={{ fontSize: 15, marginBottom: 12 }}>
              No nonprofits found filling this gap yet.
            </p>
            <p style={{ fontSize: 13, color: '#888' }}>
              NTEE Code: {decision.ntee_code || 'Not classified'}
            </p>
          </div>
        ) : (
          <>
            <div style={{
              fontSize: 15,
              fontWeight: 500,
              color: '#059669',
              marginBottom: 16
            }}>
              {matchingNonprofits.length} organization{matchingNonprofits.length !== 1 ? 's' : ''} filling this gap:
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {matchingNonprofits.map((nonprofit, i) => (
                <NonprofitCard key={i} nonprofit={nonprofit} />
              ))}
            </div>
            
            <div style={{
              marginTop: 20,
              padding: 16,
              background: 'white',
              borderRadius: 8,
              fontSize: 13,
              color: '#666'
            }}>
              <div style={{ fontWeight: 500, color: '#059669', marginBottom: 8 }}>
                💡 Bridge the Gap
              </div>
              <ul style={{ margin: 0, paddingLeft: 20, lineHeight: 1.6 }}>
                <li>Support these organizations with donations or volunteering</li>
                <li>Join their boards to influence systemic change</li>
                <li>Cite their work in public meetings to show solutions exist</li>
              </ul>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function NonprofitCard({ nonprofit }) {
  return (
    <div style={{
      background: 'white',
      borderRadius: 8,
      padding: 16,
      border: '1px solid #10b981'
    }}>
      <div style={{ marginBottom: 12 }}>
        <h4 style={{
          fontSize: 16,
          fontWeight: 600,
          color: '#111',
          marginBottom: 4
        }}>
          {nonprofit.name}
        </h4>
        <div style={{
          fontSize: 12,
          color: '#666',
          marginBottom: 8
        }}>
          NTEE {nonprofit.ntee_code}: {nonprofit.ntee_description}
        </div>
        <div style={{
          fontSize: 14,
          color: '#444',
          lineHeight: 1.5,
          marginBottom: 12
        }}>
          {nonprofit.mission}
        </div>
      </div>
      
      {/* Services */}
      <div style={{ marginBottom: 12 }}>
        <div style={{
          fontSize: 12,
          fontWeight: 500,
          color: '#059669',
          marginBottom: 6
        }}>
          Services Provided:
        </div>
        <ul style={{
          margin: 0,
          paddingLeft: 20,
          fontSize: 13,
          color: '#666',
          lineHeight: 1.6
        }}>
          {nonprofit.services.slice(0, 3).map((service, i) => (
            <li key={i}>{service}</li>
          ))}
        </ul>
      </div>
      
      {/* Impact */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 12,
        marginBottom: 12,
        padding: 12,
        background: '#f0fdf4',
        borderRadius: 6
      }}>
        {nonprofit.students_served && (
          <div>
            <div style={{ fontSize: 11, color: '#666' }}>Impact</div>
            <div style={{ fontSize: 15, fontWeight: 600, color: '#059669' }}>
              <Users size={14} style={{ display: 'inline', marginRight: 4 }} />
              {nonprofit.students_served.toLocaleString()} students
            </div>
          </div>
        )}
        {nonprofit.families_served && (
          <div>
            <div style={{ fontSize: 11, color: '#666' }}>Impact</div>
            <div style={{ fontSize: 15, fontWeight: 600, color: '#059669' }}>
              <Heart size={14} style={{ display: 'inline', marginRight: 4 }} />
              {nonprofit.families_served.toLocaleString()} families
            </div>
          </div>
        )}
        {nonprofit.youth_served && (
          <div>
            <div style={{ fontSize: 11, color: '#666' }}>Impact</div>
            <div style={{ fontSize: 15, fontWeight: 600, color: '#059669' }}>
              <Users size={14} style={{ display: 'inline', marginRight: 4 }} />
              {nonprofit.youth_served.toLocaleString()} youth
            </div>
          </div>
        )}
        <div>
          <div style={{ fontSize: 11, color: '#666' }}>Annual Budget</div>
          <div style={{ fontSize: 15, fontWeight: 600, color: '#059669' }}>
            <DollarSign size={14} style={{ display: 'inline', marginRight: 2 }} />
            {(nonprofit.annual_budget / 1000).toFixed(0)}K
          </div>
        </div>
      </div>
      
      {/* Contact & Actions */}
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: 8,
        marginBottom: 12
      }}>
        {nonprofit.contact.website && (
          <a
            href={nonprofit.contact.website}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              fontSize: 12,
              padding: '6px 12px',
              background: '#059669',
              color: 'white',
              borderRadius: 6,
              textDecoration: 'none',
              display: 'flex',
              alignItems: 'center',
              gap: 4
            }}
          >
            <Globe size={12} />
            Website
          </a>
        )}
        {nonprofit.contact.email && (
          <a
            href={`mailto:${nonprofit.contact.email}`}
            style={{
              fontSize: 12,
              padding: '6px 12px',
              background: 'white',
              color: '#059669',
              border: '1px solid #059669',
              borderRadius: 6,
              textDecoration: 'none',
              display: 'flex',
              alignItems: 'center',
              gap: 4
            }}
          >
            <Mail size={12} />
            Email
          </a>
        )}
      </div>
      
      {/* Opportunities */}
      <div style={{
        display: 'flex',
        gap: 8,
        flexWrap: 'wrap'
      }}>
        {nonprofit.volunteer_opportunities && (
          <span style={{
            fontSize: 11,
            padding: '4px 8px',
            background: '#dcfce7',
            color: '#059669',
            borderRadius: 4,
            fontWeight: 500
          }}>
            ✓ Accepting Volunteers
          </span>
        )}
        {nonprofit.accepting_board_members && (
          <span style={{
            fontSize: 11,
            padding: '4px 8px',
            background: '#fef3c7',
            color: '#d97706',
            borderRadius: 4,
            fontWeight: 500
          }}>
            ⭐ Board Seats Available
          </span>
        )}
      </div>
    </div>
  );
}
