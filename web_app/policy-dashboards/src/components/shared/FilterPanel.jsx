import React, { useState } from 'react';
import { Search, Filter, X } from 'lucide-react';

/**
 * FilterPanel Component
 * Allows filtering by policy domains/keywords and search
 */
export default function FilterPanel({ 
  selectedDomains = [], 
  onDomainToggle,
  searchQuery = "",
  onSearchChange,
  onClear 
}) {
  const [showFilters, setShowFilters] = useState(false);
  
  const policyDomains = [
    { id: 'health', label: 'Health & Wellness', color: '#1D9E75' },
    { id: 'education', label: 'Education & Curriculum', color: '#185FA5' },
    { id: 'facilities', label: 'Facilities & Infrastructure', color: '#BA7517' },
    { id: 'budget', label: 'Budget & Finance', color: '#D85A30' },
    { id: 'personnel', label: 'Personnel & Staffing', color: '#6B4C9A' },
    { id: 'safety', label: 'Safety & Security', color: '#E24B4A' },
    { id: 'community', label: 'Community & Partnerships', color: '#2C7A7B' },
    { id: 'policy', label: 'Policy & Governance', color: '#744210' }
  ];
  
  const keywords = [
    'dental', 'health', 'screening', 'wellness', 'nurse',
    'budget', 'funding', 'capital', 'expenditure',
    'facility', 'building', 'construction', 'renovation',
    'teacher', 'salary', 'contract', 'hiring',
    'curriculum', 'textbook', 'program', 'academic',
    'safety', 'security', 'police', 'emergency',
    'community', 'partnership', 'grant', 'donation'
  ];
  
  const hasActiveFilters = selectedDomains.length > 0 || searchQuery.length > 0;
  
  return (
    <div style={{ marginBottom: 20 }}>
      {/* Search Bar */}
      <div style={{ 
        display: 'flex', 
        gap: 8, 
        marginBottom: 12 
      }}>
        <div style={{ 
          position: 'relative', 
          flex: 1 
        }}>
          <Search 
            size={16} 
            style={{ 
              position: 'absolute', 
              left: 12, 
              top: '50%', 
              transform: 'translateY(-50%)',
              color: '#999'
            }} 
          />
          <input
            type="text"
            placeholder="Search decisions, speakers, rationales..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            style={{
              width: '100%',
              padding: '8px 12px 8px 36px',
              border: '1px solid #ddd',
              borderRadius: 8,
              fontSize: 13,
              fontFamily: 'inherit'
            }}
          />
          {searchQuery && (
            <button
              onClick={() => onSearchChange('')}
              style={{
                position: 'absolute',
                right: 8,
                top: '50%',
                transform: 'translateY(-50%)',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: '#999',
                padding: 4
              }}
            >
              <X size={14} />
            </button>
          )}
        </div>
        
        <button
          onClick={() => setShowFilters(!showFilters)}
          style={{
            padding: '8px 16px',
            border: '1px solid',
            borderColor: showFilters ? '#888' : '#ddd',
            borderRadius: 8,
            background: showFilters ? '#f5f5f2' : 'white',
            cursor: 'pointer',
            fontSize: 13,
            fontWeight: 500,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            color: showFilters ? '#222' : '#666'
          }}
        >
          <Filter size={14} />
          Filters
          {selectedDomains.length > 0 && (
            <span style={{
              background: '#D85A30',
              color: 'white',
              borderRadius: '50%',
              width: 18,
              height: 18,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 10,
              fontWeight: 600
            }}>
              {selectedDomains.length}
            </span>
          )}
        </button>
        
        {hasActiveFilters && (
          <button
            onClick={onClear}
            style={{
              padding: '8px 16px',
              border: '1px solid #ddd',
              borderRadius: 8,
              background: 'white',
              cursor: 'pointer',
              fontSize: 13,
              color: '#D85A30'
            }}
          >
            Clear All
          </button>
        )}
      </div>
      
      {/* Filter Panel */}
      {showFilters && (
        <div style={{
          background: '#f5f5f2',
          borderRadius: 8,
          padding: 16,
          marginTop: 8
        }}>
          <div style={{ marginBottom: 12 }}>
            <div style={{
              fontSize: 12,
              fontWeight: 500,
              color: '#666',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              marginBottom: 10
            }}>
              Policy Domains
            </div>
            <div style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 8
            }}>
              {policyDomains.map(domain => {
                const isSelected = selectedDomains.includes(domain.id);
                return (
                  <button
                    key={domain.id}
                    onClick={() => onDomainToggle(domain.id)}
                    style={{
                      padding: '6px 12px',
                      borderRadius: 16,
                      border: '1px solid',
                      borderColor: isSelected ? domain.color : '#ddd',
                      background: isSelected ? domain.color : 'white',
                      color: isSelected ? 'white' : '#666',
                      fontSize: 12,
                      cursor: 'pointer',
                      fontWeight: isSelected ? 500 : 400,
                      transition: 'all 0.2s ease'
                    }}
                  >
                    {domain.label}
                  </button>
                );
              })}
            </div>
          </div>
          
          <div>
            <div style={{
              fontSize: 12,
              fontWeight: 500,
              color: '#666',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              marginBottom: 10
            }}>
              Common Keywords
            </div>
            <div style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 6
            }}>
              {keywords.map(keyword => (
                <button
                  key={keyword}
                  onClick={() => onSearchChange(keyword)}
                  style={{
                    padding: '4px 10px',
                    borderRadius: 12,
                    border: '1px solid #ddd',
                    background: searchQuery === keyword ? '#f0f0ee' : 'white',
                    color: '#666',
                    fontSize: 11,
                    cursor: 'pointer'
                  }}
                >
                  {keyword}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
