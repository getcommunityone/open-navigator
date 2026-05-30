import React from 'react';
import { Heart, Mail, Phone, Globe, Users, DollarSign } from 'lucide-react';

/**
 * NonprofitCard Component
 * Displays individual nonprofit or church organization
 */
export default function NonprofitCard({ nonprofit, isChurch = false }) {
  const {
    name,
    ein,
    ntee_code,
    ntee_description,
    mission,
    services = [],
    annual_budget,
    students_served,
    families_served,
    youth_served,
    contact,
    volunteer_opportunities,
    accepting_board_members
  } = nonprofit;
  
  return (
    <div style={{
      background: 'white',
      border: '1px solid',
      borderColor: isChurch ? '#A855F7' : '#10b981',
      borderLeft: `4px solid ${isChurch ? '#A855F7' : '#10b981'}`,
      borderRadius: 12,
      padding: 20,
      marginBottom: 16,
      boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
    }}>
      {/* Header */}
      <div style={{ marginBottom: 16 }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: 8
        }}>
          <h3 style={{
            fontSize: 18,
            fontWeight: 600,
            color: '#111',
            lineHeight: 1.4
          }}>
            {name}
          </h3>
          {isChurch && (
            <span style={{
              padding: '4px 10px',
              borderRadius: 12,
              background: '#F3E8FF',
              color: '#A855F7',
              fontSize: 11,
              fontWeight: 500
            }}>
              ⛪ Faith-Based
            </span>
          )}
        </div>
        
        <div style={{
          fontSize: 12,
          color: '#666',
          marginBottom: 8
        }}>
          NTEE {ntee_code}: {ntee_description}
          {ein && <span style={{ marginLeft: 8, color: '#999' }}>• EIN: {ein}</span>}
        </div>
        
        <div style={{
          fontSize: 15,
          color: '#444',
          lineHeight: 1.6,
          marginBottom: 16
        }}>
          {mission}
        </div>
      </div>
      
      {/* Services */}
      {services.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{
            fontSize: 13,
            fontWeight: 500,
            color: isChurch ? '#A855F7' : '#059669',
            marginBottom: 8
          }}>
            Services Provided:
          </div>
          <ul style={{
            margin: 0,
            paddingLeft: 20,
            fontSize: 14,
            color: '#555',
            lineHeight: 1.8
          }}>
            {services.map((service, i) => (
              <li key={i}>{service}</li>
            ))}
          </ul>
        </div>
      )}
      
      {/* Impact Metrics */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
        gap: 12,
        marginBottom: 16,
        padding: 16,
        background: isChurch ? '#FAF5FF' : '#f0fdf4',
        borderRadius: 8
      }}>
        {students_served > 0 && (
          <div>
            <div style={{ fontSize: 11, color: '#666', marginBottom: 4 }}>Students Served</div>
            <div style={{
              fontSize: 18,
              fontWeight: 600,
              color: isChurch ? '#A855F7' : '#059669',
              display: 'flex',
              alignItems: 'center',
              gap: 6
            }}>
              <Users size={16} />
              {students_served.toLocaleString()}
            </div>
          </div>
        )}
        {families_served > 0 && (
          <div>
            <div style={{ fontSize: 11, color: '#666', marginBottom: 4 }}>Families Served</div>
            <div style={{
              fontSize: 18,
              fontWeight: 600,
              color: isChurch ? '#A855F7' : '#059669',
              display: 'flex',
              alignItems: 'center',
              gap: 6
            }}>
              <Heart size={16} />
              {families_served.toLocaleString()}
            </div>
          </div>
        )}
        {youth_served > 0 && (
          <div>
            <div style={{ fontSize: 11, color: '#666', marginBottom: 4 }}>Youth Served</div>
            <div style={{
              fontSize: 18,
              fontWeight: 600,
              color: isChurch ? '#A855F7' : '#059669',
              display: 'flex',
              alignItems: 'center',
              gap: 6
            }}>
              <Users size={16} />
              {youth_served.toLocaleString()}
            </div>
          </div>
        )}
        <div>
          <div style={{ fontSize: 11, color: '#666', marginBottom: 4 }}>Annual Budget</div>
          <div style={{
            fontSize: 18,
            fontWeight: 600,
            color: isChurch ? '#A855F7' : '#059669',
            display: 'flex',
            alignItems: 'center',
            gap: 6
          }}>
            <DollarSign size={16} />
            {(annual_budget / 1000).toFixed(0)}K
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
        {contact?.website && (
          <a
            href={contact.website}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              fontSize: 13,
              padding: '8px 16px',
              background: isChurch ? '#A855F7' : '#059669',
              color: 'white',
              borderRadius: 6,
              textDecoration: 'none',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontWeight: 500
            }}
          >
            <Globe size={14} />
            Website
          </a>
        )}
        {contact?.email && (
          <a
            href={`mailto:${contact.email}`}
            style={{
              fontSize: 13,
              padding: '8px 16px',
              background: 'white',
              color: isChurch ? '#A855F7' : '#059669',
              border: `1px solid ${isChurch ? '#A855F7' : '#059669'}`,
              borderRadius: 6,
              textDecoration: 'none',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontWeight: 500
            }}
          >
            <Mail size={14} />
            Email
          </a>
        )}
        {contact?.phone && (
          <a
            href={`tel:${contact.phone}`}
            style={{
              fontSize: 13,
              padding: '8px 16px',
              background: 'white',
              color: isChurch ? '#A855F7' : '#059669',
              border: `1px solid ${isChurch ? '#A855F7' : '#059669'}`,
              borderRadius: 6,
              textDecoration: 'none',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontWeight: 500
            }}
          >
            <Phone size={14} />
            Call
          </a>
        )}
      </div>
      
      {/* Opportunities */}
      <div style={{
        display: 'flex',
        gap: 8,
        flexWrap: 'wrap'
      }}>
        {volunteer_opportunities && (
          <span style={{
            fontSize: 12,
            padding: '6px 12px',
            background: isChurch ? '#FAF5FF' : '#dcfce7',
            color: isChurch ? '#A855F7' : '#059669',
            borderRadius: 6,
            fontWeight: 500
          }}>
            ✓ Accepting Volunteers
          </span>
        )}
        {accepting_board_members && (
          <span style={{
            fontSize: 12,
            padding: '6px 12px',
            background: '#fef3c7',
            color: '#d97706',
            borderRadius: 6,
            fontWeight: 500
          }}>
            ⭐ Board Seats Available
          </span>
        )}
      </div>
    </div>
  );
}
