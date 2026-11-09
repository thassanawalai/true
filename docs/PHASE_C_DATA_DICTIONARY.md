# Data Dictionary — actual SQLAlchemy metadata

Generated from current models without migrations or DB writes. Nullable, primary keys and foreign keys below are model declarations; no undocumented field is inferred.

## chat_rooms

| Field | Type | Nullable | PK | FK |
|---|---|---|---|---|
| id | UUID | False | True |  |
| owner_id | UUID | False | False | users.id |
| company_id | UUID | False | False | companies.id |
| ticket_id | UUID | False | False | tickets.id |
| created_at | DATETIME | False | False |  |

Unique constraints: ticket_id

## companies

| Field | Type | Nullable | PK | FK |
|---|---|---|---|---|
| id | UUID | False | True |  |
| name | VARCHAR | False | False |  |
| created_at | DATETIME | True | False |  |

Unique constraints: name

## customer_assets

| Field | Type | Nullable | PK | FK |
|---|---|---|---|---|
| id | UUID | False | True |  |
| company_id | UUID | False | False | companies.id |
| ip_address | VARCHAR(45) | False | False |  |
| hostname | VARCHAR(255) | False | False |  |
| asset_type | VARCHAR(64) | False | False |  |

Unique constraints: company_id, ip_address

## customer_logs

| Field | Type | Nullable | PK | FK |
|---|---|---|---|---|
| id | UUID | False | True |  |
| company_id | UUID | False | False | companies.id |
| asset_id | UUID | False | False | customer_assets.id |
| collector_id | UUID | False | False | log_collectors.id |
| event_type | VARCHAR(100) | False | False |  |
| message | TEXT | False | False |  |
| occurred_at | DATETIME | False | False |  |

Unique constraints: none

## log_collectors

| Field | Type | Nullable | PK | FK |
|---|---|---|---|---|
| id | UUID | False | True |  |
| company_id | UUID | False | False | companies.id |
| name | VARCHAR(100) | False | False |  |
| site | VARCHAR(255) | False | False |  |

Unique constraints: company_id, name

## room_messages

| Field | Type | Nullable | PK | FK |
|---|---|---|---|---|
| id | UUID | False | True |  |
| room_id | UUID | False | False | chat_rooms.id |
| sequence | INTEGER | False | False |  |
| role | VARCHAR | False | False |  |
| sender_id | UUID | True | False | users.id |
| sender_name | VARCHAR | False | False |  |
| content | TEXT | False | False |  |
| created_at | DATETIME | False | False |  |

Unique constraints: none

## sla_policies

| Field | Type | Nullable | PK | FK |
|---|---|---|---|---|
| id | UUID | False | True |  |
| name | VARCHAR | False | False |  |
| priority | VARCHAR(2) | False | False |  |
| time_to_own_minutes | INTEGER | False | False |  |
| time_to_resolve_minutes | INTEGER | False | False |  |

Unique constraints: priority

## ticket_audit_logs

| Field | Type | Nullable | PK | FK |
|---|---|---|---|---|
| id | UUID | False | True |  |
| ticket_id | UUID | False | False | tickets.id |
| user_id | UUID | False | False | users.id |
| action | VARCHAR | False | False |  |
| old_value | VARCHAR | True | False |  |
| new_value | VARCHAR | True | False |  |
| created_at | DATETIME | True | False |  |

Unique constraints: none

## ticket_categories

| Field | Type | Nullable | PK | FK |
|---|---|---|---|---|
| id | UUID | False | True |  |
| name | VARCHAR | False | False |  |

Unique constraints: none

## ticket_comments

| Field | Type | Nullable | PK | FK |
|---|---|---|---|---|
| id | UUID | False | True |  |
| ticket_id | UUID | False | False | tickets.id |
| sender_id | UUID | False | False | users.id |
| message | TEXT | False | False |  |
| is_internal | BOOLEAN | True | False |  |
| created_at | DATETIME | True | False |  |

Unique constraints: none

## ticket_slas

| Field | Type | Nullable | PK | FK |
|---|---|---|---|---|
| id | UUID | False | True |  |
| ticket_id | UUID | False | False | tickets.id |
| sla_policy_id | UUID | False | False | sla_policies.id |
| ownership_due_at | DATETIME | False | False |  |
| resolution_due_at | DATETIME | False | False |  |
| owned_at | DATETIME | True | False |  |
| resolved_at | DATETIME | True | False |  |

Unique constraints: ticket_id

## tickets

| Field | Type | Nullable | PK | FK |
|---|---|---|---|---|
| id | UUID | False | True |  |
| ticket_number | VARCHAR | False | False |  |
| company_id | UUID | False | False | companies.id |
| requester_id | UUID | False | False | users.id |
| assignee_id | UUID | True | False | users.id |
| category_id | UUID | False | False | ticket_categories.id |
| sla_policy_id | UUID | False | False | sla_policies.id |
| subject | VARCHAR | False | False |  |
| description | TEXT | False | False |  |
| impact | VARCHAR(11) | False | False |  |
| urgency | VARCHAR(8) | False | False |  |
| priority | VARCHAR(2) | False | False |  |
| status | VARCHAR | False | False |  |
| created_at | DATETIME | True | False |  |
| updated_at | DATETIME | True | False |  |

Unique constraints: none

## users

| Field | Type | Nullable | PK | FK |
|---|---|---|---|---|
| id | UUID | False | True |  |
| email | VARCHAR | False | False |  |
| full_name | VARCHAR | False | False |  |
| role | VARCHAR(8) | False | False |  |
| company_id | UUID | False | False | companies.id |
| created_at | DATETIME | True | False |  |

Unique constraints: email

## JSON KB and transient state

KB fields: id, title, content, tags, scope (public/company), company_id, source.title/source.url, review.date/review.method. Ten public articles are shipped; private fixtures exist only in offline tests.

Temporary rooms: id, owner_id, company_id, created_at, monotonic deadline, messages; RAM only, 30-minute idle TTL, 1000 rooms maximum, 200 messages per room. Only ticket-linked chat is durable.

ticket_slas, ticket_comments and ticket_audit_logs are legacy supporting models. Their presence does not establish implemented SLA timers or audit-writing workflows.
