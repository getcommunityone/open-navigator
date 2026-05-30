import React from 'react';
import { TrendingUp, AlertCircle, Users, Scale, Droplet, Building2, Heart, Church, Grid } from 'lucide-react';

/**
 * HomePage Component - Policy Accountability Platform
 * Sector-based landing page for citizens
 */
export default function HomePage({ onPersonaSelect, onTopicSelect, onSectorSelect }) {
  return (
    <div>
      {/* Top Section: Explore by Sector */}
      <div style={{
        background: 'linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%)',
        color: 'white',
        borderRadius: 12,
        padding: '2rem',
        marginBottom: 24
      }}>
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 13, color: '#aaa', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8 }}>
            Policy Accountability Platform
          </div>
          <h1 style={{ fontSize: 28, fontWeight: 500, marginBottom: 12, lineHeight: 1.3 }}>
            Track Government Decisions & Community Solutions
          </h1>
          <p style={{ fontSize: 16, color: '#ccc', lineHeight: 1.6 }}>
            Explore policy decisions, track accountability, and discover community resources
          </p>
        </div>

        {/* Sector Navigation Cards */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 12,
          marginTop: 24
        }}>
          <SectorCard
            icon={<Grid size={24} />}
            title="All Sectors"
            description="View everything together"
            color="#059669"
            onClick={() => onSectorSelect('all')}
          />
          <SectorCard
            icon={<Building2 size={24} />}
            title="Public Sector"
            description="Government decisions"
            color="#185FA5"
            onClick={() => onSectorSelect('public')}
          />
          <SectorCard
            icon={<Heart size={24} />}
            title="Nonprofits"
            description="Community organizations"
            color="#059669"
            onClick={() => onSectorSelect('nonprofits')}
          />
          <SectorCard
            icon={<Church size={24} />}
            title="Churches"
            description="Faith-based ministries"
            color="#A855F7"
            onClick={() => onSectorSelect('churches')}
          />
        </div>
      </div>

      {/* Middle Section: Find Your Impact (Persona Filters) */}
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 22, fontWeight: 500, marginBottom: 8 }}>
          Find Your Impact
        </h2>
        <p style={{ fontSize: 16, color: '#666', marginBottom: 16 }}>
          How are these decisions affecting you?
        </p>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: 16
        }}>
          <PersonaCard
            icon="🏠"
            persona="Parent"
            concern="Student Dental Health"
            action="The Learning Barrier Map"
            onClick={() => onPersonaSelect('parent', 'dental-health')}
          />
          <PersonaCard
            icon="📢"
            persona="Advocate"
            concern="Transparency & Vetoes"
            action="The Influence Radar"
            onClick={() => onPersonaSelect('advocate', 'transparency')}
          />
          <PersonaCard
            icon="🚰"
            persona="Resident"
            concern="Water & Infrastructure"
            action="The Lifetime Health Tax"
            onClick={() => onPersonaSelect('resident', 'water-infrastructure')}
          />
        </div>
      </div>

      {/* Bottom Section: Topic Navigation */}
      <div>
        <h2 style={{ fontSize: 18, fontWeight: 500, marginBottom: 16 }}>
          Browse by Topic
        </h2>
        
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
          gap: 12
        }}>
          <TopicCard
            icon={<Scale size={24} />}
            title="Public Health"
            subtitle="Dental, Water, Mental Health"
            count={24}
            color="#1D9E75"
            onClick={() => onTopicSelect('public-health')}
          />
          <TopicCard
            icon={<Users size={24} />}
            title="Education & Youth"
            subtitle="School Board, Pre-K"
            count={18}
            color="#185FA5"
            onClick={() => onTopicSelect('education')}
          />
          <TopicCard
            icon={<TrendingUp size={24} />}
            title="Infrastructure"
            subtitle="Roads, Utilities, Construction"
            count={32}
            color="#BA7517"
            onClick={() => onTopicSelect('infrastructure')}
          />
          <TopicCard
            icon={<Droplet size={24} />}
            title="Public Safety"
            subtitle="Police, Fire, EMS"
            count={15}
            color="#E24B4A"
            onClick={() => onTopicSelect('public-safety')}
          />
        </div>
      </div>
    </div>
  );
}

function SectorCard({ icon, title, description, color, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        background: 'rgba(255, 255, 255, 0.1)',
        border: '1px solid rgba(255, 255, 255, 0.2)',
        borderRadius: 8,
        padding: 20,
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        textAlign: 'center'
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = 'rgba(255, 255, 255, 0.15)';
        e.currentTarget.style.borderColor = color;
        e.currentTarget.style.transform = 'translateY(-4px)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'rgba(255, 255, 255, 0.1)';
        e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.2)';
        e.currentTarget.style.transform = 'translateY(0)';
      }}
    >
      <div style={{ color: color, marginBottom: 12 }}>
        {icon}
      </div>
      <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4, color: 'white' }}>
        {title}
      </div>
      <div style={{ fontSize: 13, color: '#aaa' }}>
        {description}
      </div>
    </div>
  );
}

function PersonaCard({ icon, persona, concern, action, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        background: 'white',
        border: '2px solid #eee',
        borderRadius: 12,
        padding: 20,
        cursor: 'pointer',
        transition: 'all 0.2s ease'
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = '#D85A30';
        e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = '#eee';
        e.currentTarget.style.boxShadow = 'none';
      }}
    >
      <div style={{ fontSize: 32, marginBottom: 12 }}>{icon}</div>
      <div style={{ marginBottom: 8 }}>
        <div style={{ fontSize: 12, color: '#999', marginBottom: 4 }}>
          I am a...
        </div>
        <div style={{ fontSize: 16, fontWeight: 500, color: '#222' }}>
          {persona}
        </div>
      </div>
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 12, color: '#999', marginBottom: 4 }}>
          I care about...
        </div>
        <div style={{ fontSize: 14, color: '#555' }}>
          {concern}
        </div>
      </div>
      <div style={{
        fontSize: 13,
        color: '#D85A30',
        fontWeight: 500,
        display: 'flex',
        alignItems: 'center',
        gap: 6
      }}>
        Show me → {action}
      </div>
    </div>
  );
}

function TopicCard({ icon, title, subtitle, count, color, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        background: 'white',
        border: '1px solid #eee',
        borderRadius: 8,
        padding: 16,
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        display: 'flex',
        alignItems: 'center',
        gap: 12
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = color;
        e.currentTarget.style.transform = 'translateY(-2px)';
        e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = '#eee';
        e.currentTarget.style.transform = 'translateY(0)';
        e.currentTarget.style.boxShadow = 'none';
      }}
    >
      <div style={{ color }}>{icon}</div>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 14, fontWeight: 500, color: '#222', marginBottom: 2 }}>
          {title}
        </div>
        <div style={{ fontSize: 11, color: '#888' }}>
          {subtitle}
        </div>
      </div>
      <div style={{
        fontSize: 18,
        fontWeight: 500,
        color,
        minWidth: 32,
        textAlign: 'right'
      }}>
        {count}
      </div>
    </div>
  );
}
