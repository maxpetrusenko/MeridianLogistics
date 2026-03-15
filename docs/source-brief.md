# Meridian Logistics: Source Brief

## Executive Summary
Meridian Logistics is a $380M freight brokerage with 4,200 carriers, 310 employees (50% brokers), and 22% YoY growth. They operate FreightView, a 6-year-old in-house Python/FastAPI + React platform with PostgreSQL (40M+ rows) handling 34 REST endpoints across five regional offices. Brokers spend 35% of their day on manual data lookup, and the analytics team has a 170-request backlog.

## 90 Day PoC Scope
- **Scope**: Memphis office only, read queries + single-step bookings
- **Phase 2 Goal**: Extend to multi-office, multi-step workflows
- **Team**: 4 engineers, VP of Engineering leads
- **Current Limitation**: LLM generates valid SQL only 62% of the time (hallucinated columns, incorrect joins, unbounded queries)

## Core Constraints
- **Security**: Row-level filtering by office_id and role (broker → office_manager → VP)
- **Performance**: Brokers manage 40-60 shipments each, need real-time responses
- **Compliance**: 14 sensitive columns (carrier_rate, shipper_rate, credit_limit) protected
- **Technical**: Existing API gateway with JWT auth, no admin API exposed
- **Data**: 15 tables, 40M+ rows tracking_events, strict 6-state shipment lifecycle

## Representative User Workflows
1. **Read - Aggregation**: "Average transit time for LTL Dallas to Chicago (90 days)"
2. **Read - Ranking**: "Top 5 carriers by on-time rate for FTL >20,000 lbs in Southeast"
3. **Read - Multi-Table**: "Shipments in transit with expiring insurance (30 days)"
4. **Write - Booking**: "Book Dallas-Chicago lane with carrier #4412 for Tuesday pickup"
5. **Write - Status Update**: "Mark shipment #88219 delayed, new ETA Thursday"
6. **Boundary Test**: "Compare Dallas vs Atlanta on-time rates" (VP succeeds, broker fails)

## Major Risks
- **Data Security**: Cross-office data leakage via prompt injection
- **Query Accuracy**: Hallucinated columns, incorrect joins, unbounded result sets
- **Workflow State**: Quote expiration during multi-step operations
- **Permission Bypass**: Unauthorized action escalation attacks
- **Performance**: Slow responses during peak broker operations

## Open Questions
- How to handle quote expiration mid-conversation for booking workflows?
- What's the pattern for human confirmation before financial operations?
- How to structure agent responses for rich components (tables, timelines, action buttons)?
- What's the evaluation metric for query accuracy beyond the initial 62%?
- How to scale from Memphis PoC to five offices with different regional nuances?

## Success Signals
- 90%+ valid SQL generation rate
- <500ms response time for standard queries
- 0 cross-office data breaches
- 95%+ broker satisfaction with chat interface
- Support for all 6 example query patterns
- Complete audit trail for all actions