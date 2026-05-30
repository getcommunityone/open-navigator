import React from 'react';
import { Users, MessageSquare, FileText, Calendar, CheckCircle, XCircle } from 'lucide-react';

/**
 * DecisionCard Component
 * Shows individual decision with speakers, rationale, and details
 */
export default function DecisionCard({ decision, onClick }) {
  const {
    decision_summary,
    outcome,
    primary_rationale,
    supporters = [],
    opponents = [],
    vote_result,
    meeting_date,
    tradeoffs_discussed = [],
    evidence_cited = [],
    policy_domain = 'general',
    community_gap,
    ntee_code
  } = decision;
  
  const domainColors = {
    health: '#1D9E75',
    education: '#185FA5',
    facilities: '#BA7517',
    budget: '#D85A30',
    personnel: '#6B4C9A',
    safety: '#E24B4A',
    community: '#2C7A7B',
    policy: '#744210',
    general: '#888'
  };
  
  const isApproved = outcome?.toLowerCase().includes('approved') || 
                     outcome?.toLowerCase().includes('passed');
  
  return (
    <div
      onClick={onClick}
      style={{
        background: 'white',
        border: '1px solid #eee',
        borderLeft: `4px solid ${domainColors[policy_domain] || '#888'}`,
        borderRadius: 8,
        padding: 20,
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        marginBottom: 12
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)';
        e.currentTarget.style.borderLeftWidth = '6px';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = 'none';
        e.currentTarget.style.borderLeftWidth = '4px';
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 16, fontWeight: 500, color: '#222', lineHeight: 1.5, marginBottom: 8 }}>
            {decision_summary}
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span style={{
              fontSize: 13,
              color: '#888',
              display: 'flex',
              alignItems: 'center',
              gap: 4
            }}>
              <Calendar size={14} />
              {meeting_date ? new Date(meeting_date).toLocaleDateString() : 'Date unknown'}
            </span>
            {vote_result && (
              <span style={{ fontSize: 13, color: '#888' }}>
                Vote: {vote_result}
              </span>
            )}
          </div>
        </div>
        
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '4px 10px',
          borderRadius: 12,
          background: isApproved ? '#e6f4f1' : '#fff4e6',
          color: isApproved ? '#1D9E75' : '#BA7517',
          fontSize: 11,
          fontWeight: 500
        }}>
          {isApproved ? <CheckCircle size={12} /> : <XCircle size={12} />}
          {outcome || 'Unknown'}
        </div>
      </div>
      
      {/* Rationale */}
      {primary_rationale && (
        <div style={{
          background: '#f5f5f2',
          borderRadius: 6,
          padding: 10,
          marginBottom: 10
        }}>
          <div style={{
            fontSize: 10,
            color: '#999',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            marginBottom: 4,
            display: 'flex',
            alignItems: 'center',
            gap: 4
          }}>
            <MessageSquare size={10} />
            Primary Rationale
          </div>
          <div style={{ fontSize: 12, color: '#555', lineHeight: 1.5 }}>
            "{primary_rationale}"
          </div>
        </div>
      )}
      
      {/* Speakers */}
      {(supporters.length > 0 || opponents.length > 0) && (
        <div style={{ display: 'flex', gap: 12, marginBottom: 10 }}>
          {supporters.length > 0 && (
            <div style={{ flex: 1 }}>
              <div style={{
                fontSize: 10,
                color: '#1D9E75',
                fontWeight: 500,
                marginBottom: 4,
                display: 'flex',
                alignItems: 'center',
                gap: 4
              }}>
                <Users size={10} />
                Supporters ({supporters.length})
              </div>
              {supporters.slice(0, 2).map((supporter, i) => (
                <div key={i} style={{ fontSize: 11, color: '#666', marginBottom: 2 }}>
                  • {typeof supporter === 'string' ? supporter : supporter.name || 'Unknown'}
                  {supporter.role && <span style={{ color: '#999' }}> ({supporter.role})</span>}
                </div>
              ))}
              {supporters.length > 2 && (
                <div style={{ fontSize: 10, color: '#999', fontStyle: 'italic' }}>
                  +{supporters.length - 2} more
                </div>
              )}
            </div>
          )}
          
          {opponents.length > 0 && (
            <div style={{ flex: 1 }}>
              <div style={{
                fontSize: 10,
                color: '#D85A30',
                fontWeight: 500,
                marginBottom: 4,
                display: 'flex',
                alignItems: 'center',
                gap: 4
              }}>
                <Users size={10} />
                Opponents ({opponents.length})
              </div>
              {opponents.slice(0, 2).map((opponent, i) => (
                <div key={i} style={{ fontSize: 11, color: '#666', marginBottom: 2 }}>
                  • {typeof opponent === 'string' ? opponent : opponent.name || 'Unknown'}
                  {opponent.role && <span style={{ color: '#999' }}> ({opponent.role})</span>}
                </div>
              ))}
              {opponents.length > 2 && (
                <div style={{ fontSize: 10, color: '#999', fontStyle: 'italic' }}>
                  +{opponents.length - 2} more
                </div>
              )}
            </div>
          )}
        </div>
      )}
      
      {/* Tradeoffs & Evidence */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {tradeoffs_discussed.length > 0 && (
          <span style={{
            fontSize: 10,
            padding: '2px 8px',
            borderRadius: 10,
            background: '#fff4e6',
            color: '#BA7517',
            display: 'flex',
            alignItems: 'center',
            gap: 4
          }}>
            {tradeoffs_discussed.length} tradeoff{tradeoffs_discussed.length > 1 ? 's' : ''}
          </span>
        )}
        {evidence_cited.length > 0 && (
          <span style={{
            fontSize: 10,
            padding: '2px 8px',
            borderRadius: 10,
            background: '#e6f4f1',
            color: '#1D9E75',
            display: 'flex',
            alignItems: 'center',
            gap: 4
          }}>
            <FileText size={10} />
            {evidence_cited.length} source{evidence_cited.length > 1 ? 's' : ''}
          </span>
        )}
        {community_gap?.nonprofit_filling_gap && (
          <span style={{
            fontSize: 10,
            padding: '2px 8px',
            borderRadius: 10,
            background: '#dcfce7',
            color: '#059669',
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            fontWeight: 500
          }}>
            🤝 Community filling gap
          </span>
        )}
        {ntee_code && (
          <span style={{
            fontSize: 10,
            padding: '2px 8px',
            borderRadius: 10,
            background: '#f3f4f6',
            color: '#6b7280',
            display: 'flex',
            alignItems: 'center',
            gap: 4
          }}>
            NTEE: {ntee_code}
          </span>
        )}
      </div>
    </div>
  );
}
