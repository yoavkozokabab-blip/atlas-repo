# Phase 191 — Admin Intake Dashboard

**Date:** 2026-06-07

## Before fix — what admin could see

- Read-only **Beta applicants** table in `admin.html` via `GET /api/accounts/admin/users`.
- Required admin signed into Atlas app; no pending-only view.
- No approve/reject actions in UI.
- No operator notification on new applications.
- Profile fields partially visible (missing languages, goals, submission timestamp column).

## After fix — what admin can see

### Pending Applications view
Dedicated table (`GET /admin/applications/pending`) with:

| Field | Source |
|-------|--------|
| Email | `users.email` |
| Submission timestamp | `users.created_at` |
| Role | `beta_profiles.primary_role` |
| Developer experience | `beta_profiles.developer_experience` |
| Works at company? | derived from `currently_developer` + `project_use` + `company_name` |
| Company name | `beta_profiles.company_name` |
| Company size | `beta_profiles.company_size` |
| Project type | `beta_profiles.project_use` |
| Repo size | `beta_profiles.repo_size` |
| Languages | `beta_profiles.languages_frameworks` |
| AI tools used | `beta_profiles.coding_tools` |
| Goals | `beta_profiles.atlas_help` |
| Notes | `beta_profiles.notes` / `users.admin_notes` |

### Actions
- **Approve** → `POST /admin/users/{id}/approve-application` (beta access + audit log)
- **Reject** → `POST /admin/users/{id}/reject-application` (status `expired` + audit log)
- **Notes** → prompt (full PATCH notes via admin API in future)

Desktop proxy:
- `GET /api/accounts/admin/applications/pending`
- `GET /api/accounts/admin/notifications`
- `POST /api/accounts/admin/applications/approve`
- `POST /api/accounts/admin/applications/reject`

### Operator notification (Task D)
On successful registration with beta profile:
- Row inserted into `admin_notifications` with email + summary (role, company, experience, etc.).
- Admin page banner: **New beta application received** with email, role, company, timestamp.
- Dashboard metrics include `pending_applications` and `unread_notifications`.

## UX rationale

- Operators need one queue for **pending** applicants, not a mixed user list.
- Notifications surface new intake without polling the full user table.
- Approve/reject in the admin UI closes the loop for beta cohort management.

## Screenshots

- Admin intake: `reports/phase191_admin_intake.png` (after deploy — capture from `admin.html` while signed in as admin)
