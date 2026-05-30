import React, { useState } from 'react';
import HomePage from './components/HomePage';
import ImpactDashboard from './components/ImpactDashboard';
import TopicNavigation from './components/TopicNavigation';
import DecisionCard from './components/shared/DecisionCard';
import SplitScreenView from './components/SplitScreenView';
import NonprofitCard from './components/NonprofitCard';
import { metadata } from './data/dashboardData';
import { Home, Grid, Building2, Heart, Church, Search, X, Calendar, Filter, MapPin, Edit2, Lightbulb } from 'lucide-react';

export default function App() {
  const [viewMode, setViewMode] = useState('home'); // 'home', 'impact', 'browse', 'split-screen'
  const [exploreMode, setExploreMode] = useState('decisions'); // 'decisions', 'organizations', or 'causes'
  const [sectorView, setSectorView] = useState('all'); // 'all', 'public', 'nonprofits', 'churches'
  const [selectedPersona, setSelectedPersona] = useState(null);
  const [selectedTopic, setSelectedTopic] = useState(null);
  const [selectedDecision, setSelectedDecision] = useState(null);
  const [selectedTopics, setSelectedTopics] = useState([]);
  const [selectedPatterns, setSelectedPatterns] = useState([]);
  const [selectedResources, setSelectedResources] = useState([]);
  const [startDate, setStartDate] = useState(null);
  const [endDate, setEndDate] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [quickDateFilter, setQuickDateFilter] = useState('all'); // 'all', '7days', '30days', '90days'
  const [quickTopicFilter, setQuickTopicFilter] = useState('all'); // 'all', 'health', 'education', 'infrastructure'
  const [jurisdictionType, setJurisdictionType] = useState('city'); // 'nation', 'state', 'county', 'city', 'school-district'
  const [jurisdictionName, setJurisdictionName] = useState('Tuscaloosa');
  const [jurisdictionState, setJurisdictionState] = useState('AL');
  const [showLocationModal, setShowLocationModal] = useState(false);
  const [tempJurisdictionType, setTempJurisdictionType] = useState('city');
  const [tempJurisdictionName, setTempJurisdictionName] = useState('');
  const [tempJurisdictionState, setTempJurisdictionState] = useState('');
  
  const handlePersonaSelect = (persona, topic) => {
    setSelectedPersona(persona);
    setSelectedTopic(topic);
    setViewMode('impact');
  };
  
  const handleTopicSelect = (topicId) => {
    setSelectedTopics([topicId]);
    setViewMode('browse');
  };
  
  const handleTopicToggle = (topicId) => {
    setSelectedTopics(prev =>
      prev.includes(topicId)
        ? prev.filter(t => t !== topicId)
        : [...prev, topicId]
    );
  };
  
  const handlePatternToggle = (patternId) => {
    setSelectedPatterns(prev =>
      prev.includes(patternId)
        ? prev.filter(p => p !== patternId)
        : [...prev, patternId]
    );
  };
  
  const handleResourceToggle = (resourceId) => {
    setSelectedResources(prev =>
      prev.includes(resourceId)
        ? prev.filter(r => r !== resourceId)
        : [...prev, resourceId]
    );
  };
  
  const handleClearFilters = () => {
    setSelectedTopics([]);
    setSelectedPatterns([]);
    setSelectedResources([]);
    setStartDate(null);
    setEndDate(null);
    setSearchQuery('');
    setQuickDateFilter('all');
    setQuickTopicFilter('all');
  };
  
  const handleQuickDateFilter = (filter) => {
    setQuickDateFilter(filter);
    const today = new Date();
    
    switch(filter) {
      case '7days':
        const sevenDaysAgo = new Date(today);
        sevenDaysAgo.setDate(today.getDate() - 7);
        setStartDate(sevenDaysAgo.toISOString().split('T')[0]);
        setEndDate(today.toISOString().split('T')[0]);
        break;
      case '30days':
        const thirtyDaysAgo = new Date(today);
        thirtyDaysAgo.setDate(today.getDate() - 30);
        setStartDate(thirtyDaysAgo.toISOString().split('T')[0]);
        setEndDate(today.toISOString().split('T')[0]);
        break;
      case '90days':
        const ninetyDaysAgo = new Date(today);
        ninetyDaysAgo.setDate(today.getDate() - 90);
        setStartDate(ninetyDaysAgo.toISOString().split('T')[0]);
        setEndDate(today.toISOString().split('T')[0]);
        break;
      case 'all':
      default:
        setStartDate(null);
        setEndDate(null);
        break;
    }
  };
  
  const handleQuickTopicFilter = (filter) => {
    setQuickTopicFilter(filter);
    
    if (filter === 'all') {
      setSelectedTopics([]);
    } else {
      setSelectedTopics([filter]);
    }
  };
  
  const handleBackToHome = () => {
    setViewMode('home');
    setSelectedPersona(null);
    setSelectedTopic(null);
    setSelectedDecision(null);
  };
  
  const handleDecisionClick = (decision) => {
    setSelectedDecision(decision);
    setViewMode('split-screen');
  };
  
  const handleSectorSelect = (sector) => {
    setViewMode('browse');
    
    // Set explore mode and sector based on selection
    if (sector === 'public') {
      setExploreMode('decisions');
      setSectorView('public');
    } else if (sector === 'nonprofits' || sector === 'churches') {
      setExploreMode('organizations');
      setSectorView(sector);
    } else if (sector === 'all') {
      setExploreMode('organizations');
      setSectorView('all');
    }
  };
  
  // Example decision data - would come from Python export
  const exampleDecisions = [
    {
      decision_summary: "Approval of $850,000 athletic turf replacement project",
      outcome: "Approved",
      primary_rationale: "Athletic facilities are essential for student engagement and community pride. The current turf is beyond its useful life and poses safety concerns.",
      supporters: [
        { name: "Board Member Johnson", role: "Board Member" },
        { name: "Athletic Director Smith", role: "Staff" }
      ],
      opponents: [
        { name: "Parent Coalition for Health", role: "Public" }
      ],
      vote_result: "6-1",
      meeting_date: "2026-03-15",
      tradeoffs_discussed: ["Athletic facilities vs. health screening programs"],
      evidence_cited: [{ source: "Athletic Department Report" }],
      policy_domain: "facilities",
      ntee_code: "N20" // Recreation, Sports, and Athletics
    },
    {
      decision_summary: "Tabled decision on dental screening partnership with West Alabama Dental Clinic",
      outcome: "Tabled for further study",
      primary_rationale: "Risk management concerns require additional legal review and liability analysis before proceeding with external health partnerships.",
      supporters: [
        { name: "Patricia Johnson, Risk Manager", role: "Staff" }
      ],
      opponents: [
        { name: "Dr. Sarah Martinez", role: "Public" },
        { name: "Parent Teacher Association", role: "Public" },
        { name: "Board Member Williams", role: "Board Member" }
      ],
      vote_result: "5-2 to table",
      meeting_date: "2026-01-18",
      tradeoffs_discussed: ["Preventive care vs. perceived liability risk"],
      evidence_cited: [{ source: "Risk Management Memo" }],
      policy_domain: "health",
      ntee_code: "E32", // School-Based Health Care
      community_gap: {
        description: "100% of surveyed parents want dental screenings for students",
        nonprofit_filling_gap: true
      }
    },
    {
      decision_summary: "Reduction of nursing staff from 5 FTE to 3 FTE",
      outcome: "Approved",
      primary_rationale: "Budget constraints necessitate cost reductions. Nursing positions will be restructured to focus on emergency response rather than preventive services.",
      supporters: [
        { name: "Superintendent Brown", role: "Staff" },
        { name: "Board Chair Thompson", role: "Board Member" }
      ],
      opponents: [
        { name: "School Nurses Association", role: "Public" },
        { name: "Board Member Lee", role: "Board Member" }
      ],
      vote_result: "4-3",
      meeting_date: "2026-02-20",
      tradeoffs_discussed: ["Cost savings vs. preventive health services"],
      evidence_cited: [{ source: "FY2026 Budget Proposal" }],
      policy_domain: "budget",
      ntee_code: "E40", // Health - General and Rehabilitative
      community_gap: {
        description: "Students lost access to preventive health services",
        nonprofit_filling_gap: true
      }
    }
  ];
  
  // Example nonprofit data - would come from IRS/GuideStar API
  const exampleNonprofits = [
    {
      name: "West Alabama Dental Initiative",
      ein: "63-1234567",
      ntee_code: "E32",
      ntee_description: "School-Based Health Care",
      mission: "Providing free dental screenings and preventive care to underserved students in West Alabama",
      services: [
        "Mobile dental unit visits to schools",
        "Free toothbrush and fluoride kits",
        "Dental education workshops for parents"
      ],
      annual_budget: 125000,
      students_served: 2400,
      contact: {
        website: "https://wadaldentalinitiative.org",
        email: "info@wadaldentalinitiative.org",
        phone: "(205) 555-0123"
      },
      volunteer_opportunities: true,
      accepting_board_members: true
    },
    {
      name: "Tuscaloosa Family Health Network",
      ein: "63-7654321",
      ntee_code: "E40",
      ntee_description: "Health - General and Rehabilitative",
      mission: "Connecting low-income families with preventive health services and wellness programs",
      services: [
        "Health screenings at community centers",
        "Nutrition education programs",
        "Mental health counseling referrals"
      ],
      annual_budget: 280000,
      families_served: 850,
      contact: {
        website: "https://tuscfamilyhealth.org",
        email: "contact@tuscfamilyhealth.org",
        phone: "(205) 555-0456"
      },
      volunteer_opportunities: true,
      accepting_board_members: false
    },
    {
      name: "After School Champions",
      ein: "63-9876543",
      ntee_code: "O50",
      ntee_description: "Youth Development Programs",
      mission: "Providing safe, enriching after-school programs that support academic success and healthy development",
      services: [
        "Homework help and tutoring",
        "Healthy snacks and meals",
        "Physical activity and sports",
        "Health and wellness workshops"
      ],
      annual_budget: 340000,
      youth_served: 450,
      contact: {
        website: "https://afterschoolchamps.org",
        email: "info@afterschoolchamps.org",
        phone: "(205) 555-0789"
      },
      volunteer_opportunities: true,
      accepting_board_members: true
    },
    {
      name: "First Baptist Church Tuscaloosa - Health Ministry",
      ein: "63-2345678",
      ntee_code: "X20",
      ntee_description: "Christian",
      mission: "Faith-based health outreach serving Tuscaloosa families through free dental kits, health screenings, and nutrition education",
      services: [
        "Free dental hygiene kits distribution",
        "Health screenings after Sunday service",
        "Nutrition education classes",
        "Mobile health unit partnership"
      ],
      annual_budget: 45000,
      families_served: 450,
      contact: {
        website: "https://fbctuscaloosa.org/health",
        email: "health@fbctuscaloosa.org",
        phone: "(205) 555-0200"
      },
      volunteer_opportunities: true,
      accepting_board_members: false
    },
    {
      name: "Tuscaloosa County Interfaith Dental Initiative",
      ein: "63-3456789",
      ntee_code: "X20",
      ntee_description: "Christian",
      mission: "Multi-faith collaboration providing free dental care to low-income students across Tuscaloosa County schools",
      services: [
        "Mobile dental unit serving Title I schools",
        "Free toothbrush and fluoride programs",
        "Parent education workshops",
        "Dental emergency fund for families"
      ],
      annual_budget: 180000,
      students_served: 1600,
      contact: {
        website: "https://tuscaloosainterfaithdental.org",
        email: "contact@tuscaloosainterfaithdental.org",
        phone: "(205) 555-0300"
      },
      volunteer_opportunities: true,
      accepting_board_members: true
    },
    {
      name: "Catholic Social Services - Dental Outreach",
      ein: "63-4567890",
      ntee_code: "X20",
      ntee_description: "Christian",
      mission: "Diocese of Birmingham outreach providing dental care and health services to underserved communities",
      services: [
        "Quarterly dental clinics at parish hall",
        "School dental screening partnerships",
        "Dental supply distribution",
        "Financial assistance for dental emergencies"
      ],
      annual_budget: 95000,
      families_served: 320,
      contact: {
        website: "https://cssalabama.org/dental",
        email: "dental@cssalabama.org",
        phone: "(205) 555-0400"
      },
      volunteer_opportunities: true,
      accepting_board_members: false
    }
  ];
  
  // Filter decisions based on search, topics, patterns, resources, and date range
  const filteredDecisions = exampleDecisions.filter(decision => {
    const matchesSearch = searchQuery === '' || 
      decision.decision_summary.toLowerCase().includes(searchQuery.toLowerCase()) ||
      decision.primary_rationale.toLowerCase().includes(searchQuery.toLowerCase());
    
    // Map policy_domain to topic IDs
    const topicMap = {
      'health': 'public-health',
      'facilities': 'infrastructure',
      'budget': 'education' // Example mapping
    };
    const decisionTopic = topicMap[decision.policy_domain] || decision.policy_domain;
    const matchesTopic = selectedTopics.length === 0 || selectedTopics.includes(decisionTopic);
    
    // Date filtering
    const decisionDate = new Date(decision.meeting_date);
    const matchesStartDate = !startDate || decisionDate >= new Date(startDate);
    const matchesEndDate = !endDate || decisionDate <= new Date(endDate);
    
    // TODO: Add pattern matching based on decision.patterns field
    // TODO: Add resource matching based on decision.available_resources field
    
    return matchesSearch && matchesTopic && matchesStartDate && matchesEndDate;
  });
  
  // Filter nonprofits and churches based on search and topic
  const filteredNonprofits = exampleNonprofits.filter(org => {
    const matchesSearch = searchQuery === '' ||
      org.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      org.mission.toLowerCase().includes(searchQuery.toLowerCase()) ||
      org.services.some(service => service.toLowerCase().includes(searchQuery.toLowerCase())) ||
      org.ntee_description.toLowerCase().includes(searchQuery.toLowerCase());
    
    // Map NTEE codes to topic IDs
    const nteeTopicMap = {
      'E': 'public-health',    // Health
      'F': 'public-health',    // Mental Health
      'K': 'public-health',    // Food/Nutrition
      'O': 'education',        // Youth Development
      'P': 'education',        // Human Services
      'X': 'public-health'     // Religious (often health ministries)
    };
    const orgTopic = nteeTopicMap[org.ntee_code?.[0]] || 'public-health';
    const matchesTopic = selectedTopics.length === 0 || selectedTopics.includes(orgTopic);
    
    return matchesSearch && matchesTopic;
  });

  return (
    <div>
      {/* Sticky Header */}
      <div style={{
        position: 'sticky',
        top: 0,
        zIndex: 1000,
        background: 'white',
        borderBottom: '1px solid #eee',
        boxShadow: '0 2px 8px rgba(0,0,0,0.05)'
      }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', padding: '16px 24px' }}>
          {/* Logo and Title Row */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 12 }}>
            {/* CommunityOne Logo */}
            <img 
              src="/communityone_logo.svg" 
              alt="CommunityOne"
              onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
              style={{
                height: 100,
                cursor: 'pointer',
                objectFit: 'contain'
              }}
            />
            
            {/* User Location Display */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '8px 16px',
              background: '#f5f5f5',
              borderRadius: 8,
              border: '1px solid #e0e0e0'
            }}>
              <MapPin size={18} style={{ color: '#059669' }} />
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#111' }}>
                  {jurisdictionType === 'nation' ? 'United States' : 
                   jurisdictionType === 'state' ? jurisdictionState :
                   jurisdictionType === 'county' ? `${jurisdictionName} County, ${jurisdictionState}` :
                   jurisdictionType === 'school-district' ? `${jurisdictionName} (${jurisdictionState})` :
                   `${jurisdictionName}, ${jurisdictionState}`}
                </div>
                <div style={{ fontSize: 12, color: '#666', textTransform: 'capitalize' }}>
                  {jurisdictionType === 'school-district' ? 'School District' : jurisdictionType}
                </div>
              </div>
              <button
                onClick={() => {
                  setTempJurisdictionType(jurisdictionType);
                  setTempJurisdictionName(jurisdictionName);
                  setTempJurisdictionState(jurisdictionState);
                  setShowLocationModal(true);
                }}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: 4,
                  display: 'flex',
                  alignItems: 'center',
                  color: '#059669'
                }}
                title="Change location"
              >
                <Edit2 size={16} />
              </button>
            </div>
            
            <div style={{ flex: 1 }}>
              <h1 style={{ fontSize: 20, fontWeight: 600, marginBottom: 4, color: '#111' }}>
                {metadata.title}
              </h1>
              <p style={{ color: '#666', fontSize: 14, lineHeight: 1.4, margin: 0 }}>
                {metadata.description}
              </p>
            </div>
          </div>
          
          {/* Global Search Bar */}
          <div style={{
            background: 'white',
            border: '1px solid #eee',
            borderRadius: 8,
            padding: 12,
            marginBottom: 12
          }}>
            <div style={{
              position: 'relative',
              display: 'flex',
              alignItems: 'center'
            }}>
              <Search
                size={16}
                style={{
                  position: 'absolute',
                  left: 12,
                  color: '#999'
                }}
              />
              <input
                type="text"
                placeholder="Search decisions, nonprofits, churches, or topics..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px 40px 10px 40px',
                  fontSize: 14,
                  border: '1px solid #ddd',
                  borderRadius: 6,
                  outline: 'none',
                  transition: 'border-color 0.2s'
                }}
                onFocus={(e) => e.target.style.borderColor = '#059669'}
                onBlur={(e) => e.target.style.borderColor = '#ddd'}
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  style={{
                    position: 'absolute',
                    right: 12,
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: '#999',
                    display: 'flex',
                    alignItems: 'center',
                    padding: 4
                  }}
                >
                  <X size={16} />
                </button>
              )}
            </div>
          </div>

          {/* View Mode Toggle */}
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between',
            alignItems: 'center'
          }}>
            <div style={{ display: 'flex', gap: 6 }}>
              <button
                onClick={() => setViewMode('home')}
            style={{
              padding: '10px 20px',
              borderRadius: 8,
              fontSize: 15,
              cursor: 'pointer',
              border: '1px solid',
              borderColor: viewMode === 'home' ? '#888' : '#ddd',
              background: viewMode === 'home' ? '#f5f5f2' : 'white',
              fontWeight: viewMode === 'home' ? 500 : 400,
              color: viewMode === 'home' ? '#111' : '#666',
              display: 'flex',
              alignItems: 'center',
              gap: 6
            }}
          >
            <Home size={14} />
            Home
          </button>
          <button
            onClick={() => {
              setViewMode('browse');
              setExploreMode('causes');
              setSectorView('all');
            }}
            style={{
              padding: '10px 20px',
              borderRadius: 8,
              fontSize: 15,
              cursor: 'pointer',
              border: '1px solid',
              borderColor: (viewMode === 'browse' && exploreMode === 'causes') ? '#888' : '#ddd',
              background: (viewMode === 'browse' && exploreMode === 'causes') ? '#f5f5f2' : 'white',
              fontWeight: (viewMode === 'browse' && exploreMode === 'causes') ? 500 : 400,
              color: (viewMode === 'browse' && exploreMode === 'causes') ? '#111' : '#666',
              display: 'flex',
              alignItems: 'center',
              gap: 6
            }}
          >
            <Lightbulb size={14} />
            Explore Causes
          </button>
          <button
            onClick={() => {
              setViewMode('browse');
              setExploreMode('decisions');
              setSectorView('public');
            }}
            style={{
              padding: '10px 20px',
              borderRadius: 8,
              fontSize: 15,
              cursor: 'pointer',
              border: '1px solid',
              borderColor: (viewMode === 'browse' && exploreMode === 'decisions') ? '#888' : '#ddd',
              background: (viewMode === 'browse' && exploreMode === 'decisions') ? '#f5f5f2' : 'white',
              fontWeight: (viewMode === 'browse' && exploreMode === 'decisions') ? 500 : 400,
              color: (viewMode === 'browse' && exploreMode === 'decisions') ? '#111' : '#666',
              display: 'flex',
              alignItems: 'center',
              gap: 6
            }}
          >
            <Building2 size={14} />
            Explore Decisions
          </button>
          <button
            onClick={() => {
              setViewMode('browse');
              setExploreMode('organizations');
              setSectorView('all');
            }}
            style={{
              padding: '10px 20px',
              borderRadius: 8,
              fontSize: 15,
              cursor: 'pointer',
              border: '1px solid',
              borderColor: (viewMode === 'browse' && exploreMode === 'organizations') ? '#888' : '#ddd',
              background: (viewMode === 'browse' && exploreMode === 'organizations') ? '#f5f5f2' : 'white',
              fontWeight: (viewMode === 'browse' && exploreMode === 'organizations') ? 500 : 400,
              color: (viewMode === 'browse' && exploreMode === 'organizations') ? '#111' : '#666',
              display: 'flex',
              alignItems: 'center',
              gap: 6
            }}
          >
            <Heart size={14} />
            Explore Organizations
          </button>
        </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: 24 }}>

      {/* Search Bar & Quick Filters (show in browse view) */}
      {viewMode === 'browse' && (
        <div style={{
          background: 'white',
          border: '1px solid #eee',
          borderRadius: 12,
          padding: 16,
          marginBottom: 16,
          boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
        }}>
          {/* Quick Filters */}
          <div style={{
            display: 'flex',
            gap: 16,
            flexWrap: 'wrap',
            alignItems: 'center'
          }}>
            {/* Date Range Quick Filter */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Calendar size={14} style={{ color: '#666' }} />
              <span style={{ fontSize: 13, color: '#666', fontWeight: 500 }}>Date:</span>
              <div style={{ display: 'flex', gap: 4 }}>
                {['all', '7days', '30days', '90days'].map(filter => (
                  <button
                    key={filter}
                    onClick={() => handleQuickDateFilter(filter)}
                    style={{
                      padding: '6px 12px',
                      fontSize: 12,
                      fontWeight: 500,
                      border: '1px solid',
                      borderColor: quickDateFilter === filter ? '#059669' : '#ddd',
                      background: quickDateFilter === filter ? '#dcfce7' : 'white',
                      color: quickDateFilter === filter ? '#059669' : '#666',
                      borderRadius: 6,
                      cursor: 'pointer',
                      transition: 'all 0.2s'
                    }}
                  >
                    {filter === 'all' ? 'All Time' :
                     filter === '7days' ? 'Last 7 Days' :
                     filter === '30days' ? 'Last 30 Days' : 'Last 90 Days'}
                  </button>
                ))}
              </div>
            </div>
            
            {/* Topic Quick Filter */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Filter size={14} style={{ color: '#666' }} />
              <span style={{ fontSize: 13, color: '#666', fontWeight: 500 }}>Topic:</span>
              <div style={{ display: 'flex', gap: 4 }}>
                {[
                  { id: 'all', label: 'All' },
                  { id: 'public-health', label: 'Health' },
                  { id: 'education', label: 'Education' },
                  { id: 'infrastructure', label: 'Infrastructure' },
                  { id: 'safety', label: 'Safety' }
                ].map(topic => (
                  <button
                    key={topic.id}
                    onClick={() => handleQuickTopicFilter(topic.id)}
                    style={{
                      padding: '6px 12px',
                      fontSize: 12,
                      fontWeight: 500,
                      border: '1px solid',
                      borderColor: quickTopicFilter === topic.id ? '#059669' : '#ddd',
                      background: quickTopicFilter === topic.id ? '#dcfce7' : 'white',
                      color: quickTopicFilter === topic.id ? '#059669' : '#666',
                      borderRadius: 6,
                      cursor: 'pointer',
                      transition: 'all 0.2s'
                    }}
                  >
                    {topic.label}
                  </button>
                ))}
              </div>
            </div>
            
            {/* Clear All Filters */}
            {(searchQuery || quickDateFilter !== 'all' || quickTopicFilter !== 'all' || 
              selectedPatterns.length > 0 || selectedResources.length > 0) && (
              <button
                onClick={handleClearFilters}
                style={{
                  padding: '6px 12px',
                  fontSize: 12,
                  fontWeight: 500,
                  border: '1px solid #D85A30',
                  background: 'white',
                  color: '#D85A30',
                  borderRadius: 6,
                  cursor: 'pointer',
                  marginLeft: 'auto'
                }}
              >
                Clear All
              </button>
            )}
          </div>
        </div>
      )}

      {/* Filters (show in browse view for decisions only) */}
      {viewMode === 'browse' && exploreMode === 'decisions' && (
        <TopicNavigation
          selectedTopics={selectedTopics}
          selectedPatterns={selectedPatterns}
          selectedResources={selectedResources}
          startDate={startDate}
          endDate={endDate}
          onTopicToggle={handleTopicToggle}
          onPatternToggle={handlePatternToggle}
          onResourceToggle={handleResourceToggle}
          onStartDateChange={setStartDate}
          onEndDateChange={setEndDate}
          onClearAll={handleClearFilters}
        />
      )}

      {/* Content */}
      {viewMode === 'home' ? (
        <HomePage 
          onPersonaSelect={handlePersonaSelect}
          onTopicSelect={handleTopicSelect}
          onSectorSelect={handleSectorSelect}
          decisionsCount={exampleDecisions.length}
          nonprofitsCount={exampleNonprofits.filter(org => !org.ntee_code.startsWith('X')).length}
          churchesCount={exampleNonprofits.filter(org => org.ntee_code.startsWith('X')).length}
        />
      ) : viewMode === 'impact' ? (
        <div style={{ 
          background: 'white', 
          border: '1px solid #eee', 
          borderRadius: 12, 
          padding: '1.5rem',
          boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
        }}>
          <button
            onClick={handleBackToHome}
            style={{
              fontSize: 13,
              color: '#666',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              marginBottom: 16,
              display: 'flex',
              alignItems: 'center',
              gap: 4
            }}
          >
            ← Back to Home
          </button>
          <ImpactDashboard persona={selectedPersona} topic={selectedTopic} />
        </div>
      ) : viewMode === 'split-screen' ? (
        <div style={{ 
          background: 'white', 
          border: '1px solid #eee', 
          borderRadius: 12, 
          padding: '1.5rem',
          boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
        }}>
          <button
            onClick={() => setViewMode('browse')}
            style={{
              fontSize: 13,
              color: '#666',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              marginBottom: 16,
              display: 'flex',
              alignItems: 'center',
              gap: 4
            }}
          >
            ← Back to Decisions
          </button>
          <div style={{
            fontSize: 12,
            fontWeight: 600,
            color: '#059669',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            marginBottom: 8
          }}>
            Split-Screen Analysis
          </div>
          <h2 style={{
            fontSize: 22,
            fontWeight: 600,
            color: '#111',
            marginBottom: 16
          }}>
            Government Decision ↔ Community Response
          </h2>
          <SplitScreenView 
            decision={selectedDecision} 
            nonprofits={exampleNonprofits}
          />
        </div>
      ) : (
        <div style={{
          background: 'white',
          border: '1px solid #eee',
          borderRadius: 12,
          padding: '1.5rem',
          boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
        }}>
          <h2 style={{
            fontSize: 20,
            fontWeight: 500,
            marginBottom: 16
          }}>
            {exploreMode === 'decisions' ? 'Explore Decisions' : exploreMode === 'organizations' ? 'Explore Organizations' : 'Explore Causes'}
            {sectorView !== 'all' && sectorView !== 'public' && exploreMode !== 'causes' && (
              <span style={{ color: '#999', fontWeight: 400 }}>
                {' '}› {sectorView === 'nonprofits' ? 'Nonprofits' : 'Churches'}
              </span>
            )}
          </h2>
          
          {/* Sector Filter Buttons */}
          {exploreMode === 'decisions' && (
            <div style={{
              display: 'flex',
              gap: 8,
              marginBottom: 20,
              padding: 16,
              background: '#f9fafb',
              borderRadius: 8,
              flexWrap: 'wrap'
            }}>
              <button
                onClick={() => setSectorView('public')}
                style={{
                  padding: '10px 16px',
                  borderRadius: 6,
                  fontSize: 14,
                  fontWeight: 500,
                  cursor: 'pointer',
                  border: '1px solid',
                  borderColor: sectorView === 'public' ? '#185FA5' : '#ddd',
                  background: sectorView === 'public' ? '#EFF6FF' : 'white',
                  color: sectorView === 'public' ? '#185FA5' : '#666',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6
                }}
              >
                <Building2 size={14} />
                Public Sector ({filteredDecisions.length})
              </button>
            </div>
          )}
          
          {exploreMode === 'organizations' && (
          <div style={{
            display: 'flex',
            gap: 8,
            marginBottom: 20,
            padding: 16,
            background: '#f9fafb',
            borderRadius: 8,
            flexWrap: 'wrap'
          }}>
            <button
              onClick={() => setSectorView('all')}
              style={{
                padding: '10px 16px',
                borderRadius: 6,
                fontSize: 14,
                fontWeight: 500,
                cursor: 'pointer',
                border: '1px solid',
                borderColor: sectorView === 'all' ? '#059669' : '#ddd',
                background: sectorView === 'all' ? '#dcfce7' : 'white',
                color: sectorView === 'all' ? '#059669' : '#666',
                display: 'flex',
                alignItems: 'center',
                gap: 6
              }}
            >
              <Grid size={14} />
              All Organizations
            </button>
            <button
              onClick={() => setSectorView('nonprofits')}
              style={{
                padding: '10px 16px',
                borderRadius: 6,
                fontSize: 14,
                fontWeight: 500,
                cursor: 'pointer',
                border: '1px solid',
                borderColor: sectorView === 'nonprofits' ? '#059669' : '#ddd',
                background: sectorView === 'nonprofits' ? '#dcfce7' : 'white',
                color: sectorView === 'nonprofits' ? '#059669' : '#666',
                display: 'flex',
                alignItems: 'center',
                gap: 6
              }}
            >
              <Heart size={14} />
              Nonprofits ({filteredNonprofits.filter(org => !org.ntee_code.startsWith('X')).length})
            </button>
            <button
              onClick={() => setSectorView('churches')}
              style={{
                padding: '10px 16px',
                borderRadius: 6,
                fontSize: 14,
                fontWeight: 500,
                cursor: 'pointer',
                border: '1px solid',
                borderColor: sectorView === 'churches' ? '#A855F7' : '#ddd',
                background: sectorView === 'churches' ? '#FAF5FF' : 'white',
                color: sectorView === 'churches' ? '#A855F7' : '#666',
                display: 'flex',
                alignItems: 'center',
                gap: 6
              }}
            >
              <Church size={14} />
              Churches ({filteredNonprofits.filter(org => org.ntee_code.startsWith('X')).length})
            </button>
          </div>
          )}
          
          {/* Public Sector Decisions */}
          {exploreMode === 'decisions' && (
            <div>
              {filteredDecisions.length === 0 ? (
                <div style={{
                  textAlign: 'center',
                  padding: '2rem',
                  color: '#999',
                  background: '#f9fafb',
                  borderRadius: 8
                }}>
                  <p style={{ fontSize: 15, marginBottom: 8 }}>
                    No government decisions match your filters
                  </p>
                  <button
                    onClick={handleClearFilters}
                    style={{
                      fontSize: 14,
                      color: '#D85A30',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      textDecoration: 'underline'
                    }}
                  >
                    Clear all filters
                  </button>
                </div>
              ) : (
                <>
                  <div style={{ fontSize: 14, color: '#888', marginBottom: 12 }}>
                    Showing {filteredDecisions.length} decision{filteredDecisions.length !== 1 ? 's' : ''}
                  </div>
                  {filteredDecisions.map((decision, i) => (
                    <DecisionCard
                      key={i}
                      decision={decision}
                      onClick={() => handleDecisionClick(decision)}
                    />
                  ))}
                </>
              )}
            </div>
          )}
          
          {/* Nonprofits Section */}
          {exploreMode === 'organizations' && (sectorView === 'all' || sectorView === 'nonprofits') && (
            <div style={{ marginBottom: sectorView === 'all' ? 32 : 0 }}>
              {sectorView === 'all' && (
                <h3 style={{
                  fontSize: 18,
                  fontWeight: 600,
                  color: '#059669',
                  marginBottom: 16,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8
                }}>
                  <Heart size={20} />
                  Nonprofit Organizations
                </h3>
              )}
              {filteredNonprofits.filter(org => !org.ntee_code.startsWith('X')).length === 0 ? (
                <div style={{
                  textAlign: 'center',
                  padding: '2rem',
                  color: '#999',
                  background: '#f9fafb',
                  borderRadius: 8
                }}>
                  <p style={{ fontSize: 15 }}>
                    No nonprofits match your search
                  </p>
                </div>
              ) : (
                filteredNonprofits
                  .filter(org => !org.ntee_code.startsWith('X'))
                  .map((nonprofit, i) => (
                    <NonprofitCard key={i} nonprofit={nonprofit} isChurch={false} />
                  ))
              )}
            </div>
          )}
          
          {/* Churches Section */}
          {exploreMode === 'organizations' && (sectorView === 'all' || sectorView === 'churches') && (
            <div>
              {sectorView === 'all' && (
                <h3 style={{
                  fontSize: 18,
                  fontWeight: 600,
                  color: '#A855F7',
                  marginBottom: 16,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8
                }}>
                  <Church size={20} />
                  Faith-Based Organizations
                </h3>
              )}
              {filteredNonprofits.filter(org => org.ntee_code.startsWith('X')).length === 0 ? (
                <div style={{
                  textAlign: 'center',
                  padding: '2rem',
                  color: '#999',
                  background: '#f9fafb',
                  borderRadius: 8
                }}>
                  <p style={{ fontSize: 15 }}>
                    No churches match your search
                  </p>
                </div>
              ) : (
                filteredNonprofits
                  .filter(org => org.ntee_code.startsWith('X'))
                  .map((church, i) => (
                    <NonprofitCard key={i} nonprofit={church} isChurch={true} />
                  ))
              )}
            </div>
          )}
          
          {/* Causes Section */}
          {exploreMode === 'causes' && (
            <div>
              <div style={{
                textAlign: 'center',
                padding: '3rem 2rem',
                color: '#666',
                background: '#f9fafb',
                borderRadius: 12,
                border: '2px dashed #ddd'
              }}>
                <Lightbulb size={48} style={{ color: '#D85A30', marginBottom: 16 }} />
                <h3 style={{
                  fontSize: 20,
                  fontWeight: 600,
                  color: '#111',
                  marginBottom: 12
                }}>
                  Explore Root Causes
                </h3>
                <p style={{ fontSize: 15, lineHeight: 1.6, maxWidth: 600, margin: '0 auto', marginBottom: 16 }}>
                  Discover the underlying factors driving policy decisions in your community. 
                  Understand the connections between social determinants, community needs, and government actions.
                </p>
                <p style={{ fontSize: 14, color: '#999', fontStyle: 'italic' }}>
                  Coming soon: Interactive cause analysis and trend mapping
                </p>
              </div>
            </div>
          )}
        </div>
      )}
      </div>
      </div>

      {/* Location Selection Modal */}
      {showLocationModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 2000
        }}>
          <div style={{
            background: 'white',
            borderRadius: 12,
            padding: 32,
            maxWidth: 500,
            width: '90%',
            boxShadow: '0 10px 40px rgba(0,0,0,0.2)'
          }}>
            <h2 style={{
              fontSize: 22,
              fontWeight: 600,
              marginBottom: 8,
              color: '#111'
            }}>
              Select Your Jurisdiction
            </h2>
            <p style={{
              color: '#666',
              fontSize: 14,
              marginBottom: 24
            }}>
              Choose the level and location to see relevant decisions and organizations.
            </p>

            <div style={{ marginBottom: 16 }}>
              <label style={{
                display: 'block',
                fontSize: 14,
                fontWeight: 500,
                marginBottom: 8,
                color: '#111'
              }}>
                Jurisdiction Level
              </label>
              <select
                value={tempJurisdictionType}
                onChange={(e) => setTempJurisdictionType(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  fontSize: 15,
                  border: '1px solid #ddd',
                  borderRadius: 6,
                  outline: 'none',
                  cursor: 'pointer'
                }}
                onFocus={(e) => e.target.style.borderColor = '#059669'}
                onBlur={(e) => e.target.style.borderColor = '#ddd'}
              >
                <option value="nation">Nation</option>
                <option value="state">State</option>
                <option value="county">County</option>
                <option value="city">City</option>
                <option value="school-district">School District</option>
              </select>
            </div>

            {tempJurisdictionType !== 'nation' && (
              <div style={{ marginBottom: 16 }}>
                <label style={{
                  display: 'block',
                  fontSize: 14,
                  fontWeight: 500,
                  marginBottom: 8,
                  color: '#111'
                }}>
                  {tempJurisdictionType === 'state' ? 'State' :
                   tempJurisdictionType === 'county' ? 'County Name' :
                   tempJurisdictionType === 'school-district' ? 'School District Name' :
                   'City Name'}
                </label>
                <input
                  type="text"
                  value={tempJurisdictionName}
                  onChange={(e) => setTempJurisdictionName(e.target.value)}
                  placeholder={
                    tempJurisdictionType === 'state' ? 'e.g., Alabama' :
                    tempJurisdictionType === 'county' ? 'e.g., Tuscaloosa' :
                    tempJurisdictionType === 'school-district' ? 'e.g., Tuscaloosa City Schools' :
                    'e.g., Tuscaloosa'
                  }
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    fontSize: 15,
                    border: '1px solid #ddd',
                    borderRadius: 6,
                    outline: 'none'
                  }}
                  onFocus={(e) => e.target.style.borderColor = '#059669'}
                  onBlur={(e) => e.target.style.borderColor = '#ddd'}
                />
              </div>
            )}

            {tempJurisdictionType !== 'nation' && tempJurisdictionType !== 'state' && (
              <div style={{ marginBottom: 24 }}>
                <label style={{
                  display: 'block',
                  fontSize: 14,
                  fontWeight: 500,
                  marginBottom: 8,
                  color: '#111'
                }}>
                  State
                </label>
                <input
                  type="text"
                  value={tempJurisdictionState}
                  onChange={(e) => setTempJurisdictionState(e.target.value)}
                  placeholder="e.g., AL"
                  maxLength="2"
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    fontSize: 15,
                    border: '1px solid #ddd',
                    borderRadius: 6,
                    outline: 'none',
                    textTransform: 'uppercase'
                  }}
                  onFocus={(e) => e.target.style.borderColor = '#059669'}
                  onBlur={(e) => e.target.style.borderColor = '#ddd'}
                />
              </div>
            )}

            {tempJurisdictionType === 'state' && (
              <div style={{ marginBottom: 24 }}>
                <label style={{
                  display: 'block',
                  fontSize: 14,
                  fontWeight: 500,
                  marginBottom: 8,
                  color: '#111'
                }}>
                  State Code
                </label>
                <input
                  type="text"
                  value={tempJurisdictionState}
                  onChange={(e) => setTempJurisdictionState(e.target.value)}
                  placeholder="e.g., AL"
                  maxLength="2"
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    fontSize: 15,
                    border: '1px solid #ddd',
                    borderRadius: 6,
                    outline: 'none',
                    textTransform: 'uppercase'
                  }}
                  onFocus={(e) => e.target.style.borderColor = '#059669'}
                  onBlur={(e) => e.target.style.borderColor = '#ddd'}
                />
              </div>
            )}

            <div style={{
              display: 'flex',
              gap: 12,
              justifyContent: 'flex-end'
            }}>
              <button
                onClick={() => setShowLocationModal(false)}
                style={{
                  padding: '10px 20px',
                  fontSize: 15,
                  border: '1px solid #ddd',
                  background: 'white',
                  borderRadius: 6,
                  cursor: 'pointer',
                  color: '#666'
                }}
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setJurisdictionType(tempJurisdictionType);
                  setJurisdictionName(tempJurisdictionName);
                  setJurisdictionState(tempJurisdictionState);
                  setShowLocationModal(false);
                }}
                style={{
                  padding: '10px 20px',
                  fontSize: 15,
                  border: 'none',
                  background: '#059669',
                  color: 'white',
                  borderRadius: 6,
                  cursor: 'pointer',
                  fontWeight: 500
                }}
              >
                Save Location
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
