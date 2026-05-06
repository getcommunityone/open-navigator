---
sidebar_position: 15
---

# Council Data Project (CDP) Compatibility

Open Navigator's data model is designed to be compatible with the [Council Data Project (CDP)](https://councildataproject.org/) backend schema, enabling interoperability with CDP instances deployed across cities nationwide.

## 🏛️ About Council Data Project

Council Data Project (CDP) is an open-source project that makes local government more accessible by providing infrastructure to index, archive, and make searchable city council meetings. CDP instances are deployed in cities across the United States.

**Website:** https://councildataproject.org/  
**Documentation:** https://councildataproject.org/cdp-backend/  
**GitHub:** https://github.com/CouncilDataProject/cdp-backend

## 🔗 Data Model Mapping

Our data model maps to CDP's core models while maintaining flexibility for additional data sources (YouTube, LocalView, Legistar, etc.):

### Event Model Mapping

| CDP Field | Open Navigator Field | Notes |
|-----------|---------------------|-------|
| `event_datetime` | `event_datetime` | Combined date+time timestamp |
| `body_ref` | `body_name` | Meeting body (e.g., "City Council") |
| `agenda_uri` | `agenda_url` | Link to meeting agenda PDF |
| `minutes_uri` | `minutes_url` | Link to meeting minutes PDF |
| `external_source_id` | `external_source_id` | Cross-system tracking ID |
| N/A | `video_url` | Extended field for YouTube/streaming |

### Session Model Mapping

| CDP Field | Open Navigator Field | Notes |
|-----------|---------------------|-------|
| `video_uri` | `video_url` | Video URL for the meeting |
| `session_content_hash` | `session_content_hash` | Hash for deduplication |
| `session_datetime` | `event_datetime` | When the session occurred |
| `event_ref` | `id` | Reference to parent event |

### Body Model Mapping

| CDP Field | Open Navigator Field | Notes |
|-----------|---------------------|-------|
| `name` | `body_name` | "City Council", "Planning Commission" |
| `description` | `body_description` | Full description of the body |
| `external_source_id` | `external_source_id` | Source system identifier |

### Transcript Model Mapping

| CDP Field | Open Navigator Field | Notes |
|-----------|---------------------|-------|
| `session_ref` | `event_id` (in events_text_ai) | Links to session/event |
| `file_ref` | `video_id` | Reference to video file |
| `confidence` | `transcript_quality` | Transcript quality score |
| `generator` | `ai_model` | AI model used (Gemini, Whisper, etc.) |

## 🗄️ Database Schema

### Bronze Layer (open_navigator_bronze)

Our bronze tables include all CDP fields plus additional fields for YouTube and other sources:

```sql
CREATE TABLE bronze_events_search (
    -- CDP-compatible core fields
    event_datetime TIMESTAMP,
    body_name VARCHAR(200),
    body_description TEXT,
    agenda_url TEXT,              -- CDP: agenda_uri
    minutes_url TEXT,             -- CDP: minutes_uri
    external_source_id VARCHAR(255),
    
    -- Extended fields for multi-source ingestion
    video_url TEXT,               -- YouTube, Granicus, etc.
    channel_id VARCHAR(50),       -- YouTube channel tracking
    source VARCHAR(50),           -- 'youtube', 'localview', 'legistar'
    jurisdiction_name VARCHAR(200),
    state_code VARCHAR(2),
    -- ... additional fields
);
```

### Production Layer (events_search)

The production `events_search` table (built via dbt) maintains CDP compatibility while providing a unified view across all data sources.

## 🔄 Data Flow

```
CDP Instance (e.g., Seattle) ──┐
YouTube (Municipal Channels) ──┼──► Bronze Layer ──► dbt Staging ──► dbt Marts ──► events_search (CDP-compatible)
LocalView Dataset ─────────────┤
Legistar API ──────────────────┘
```

## 🎯 Benefits of CDP Compatibility

1. **Interoperability**: Data can be shared with CDP instances in other cities
2. **Standardization**: Follows civic tech best practices for meeting data
3. **Community**: Leverage tools built by the CDP ecosystem
4. **Federation**: Potential to federate queries across CDP instances nationwide

## 📚 CDP Models Reference

### Event
An event can be a normally scheduled meeting, a special event such as a press conference or election debate, and can be upcoming or historical.

**Key Fields:**
- `event_datetime`: When the event occurs
- `body_ref`: Reference to the meeting body
- `agenda_uri`: Link to the agenda
- `minutes_uri`: Link to the minutes

### Body
A meeting body. This can be full council, a subcommittee, or "off-council" matters such as election debates.

**Key Fields:**
- `name`: Name of the body (e.g., "City Council")
- `description`: Full description
- `is_active`: Whether the body is currently active

### Session
A session is a working period for an event. For example, an event could have a morning and afternoon session.

**Key Fields:**
- `video_uri`: Link to the video
- `session_content_hash`: Hash for deduplication
- `session_datetime`: When the session occurred

### Transcript
A transcript is a document per-session.

**Key Fields:**
- `session_ref`: Reference to the session
- `confidence`: Transcript confidence score
- `generator`: What generated the transcript (e.g., "whisper-large-v3")

### Matter
A matter is a specific legislative document (bill, resolution, initiative, etc.).

**Key Fields:**
- `name`: Matter identifier (e.g., "CB 120001")
- `title`: Full title
- `matter_type`: Type (bill, resolution, etc.)

### Vote
A reference tying a specific person and an event minutes item together.

**Key Fields:**
- `person_ref`: Reference to the person voting
- `event_minutes_item_ref`: What they voted on
- `decision`: approve/reject/abstain

## 🔍 Querying CDP-Compatible Data

### Get all City Council meetings in 2024

```sql
SELECT 
    event_datetime,
    body_name,
    title,
    agenda_url,
    minutes_url,
    video_url
FROM events_search
WHERE body_name = 'City Council'
  AND event_datetime BETWEEN '2024-01-01' AND '2024-12-31'
ORDER BY event_datetime DESC;
```

### Find meetings with transcripts

```sql
SELECT 
    e.event_datetime,
    e.body_name,
    e.title,
    t.transcript_quality,
    t.ai_model
FROM events_search e
JOIN events_text_search t ON e.id = t.event_id
WHERE t.has_transcript = true
ORDER BY e.event_datetime DESC;
```

## 🤝 Contributing to CDP Ecosystem

Open Navigator extends CDP's vision by:

1. **Multi-source ingestion**: YouTube, LocalView, Legistar, Granicus
2. **AI-powered transcription**: Gemini, Whisper for automatic transcripts
3. **Nationwide coverage**: 90,000+ jurisdictions tracked
4. **Policy analysis**: AI models for policy opportunity detection

## 📖 Further Reading

- [CDP Documentation](https://councildataproject.org/cdp-backend/)
- [CDP GitHub Repository](https://github.com/CouncilDataProject/cdp-backend)
- [CDP Database Models](https://councildataproject.org/cdp-backend/database_models.html)
- [Open Navigator Data Sources](./citations)
- [Events Bronze Migration Guide](../deployment/events-bronze-migration)

## 📜 Citation

When citing Council Data Project compatibility in Open Navigator:

```bibtex
@software{council_data_project,
  title = {Council Data Project: Indexing City Council Meetings},
  author = {{Council Data Project Team}},
  year = {2020},
  url = {https://councildataproject.org/},
  note = {Open-source infrastructure for making local government more accessible}
}
```
