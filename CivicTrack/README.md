# CivicTrack

**Report problems. Track progress. Build better cities.**

CivicTrack is a full-stack academic demonstration of a civic issue reporting and accountability workflow. It includes a Next.js/React/TypeScript dashboard and a FastAPI/SQLAlchemy API. The default local database is SQLite so an examiner can launch the demo without configuring a database server.

All preloaded records, department scores, and locations are **synthetic demonstration data**. They do not represent an operating municipality. Prototype deadline targets are configurable examples, not government regulations. The Accountability Index is experimental and is not an official ranking.

## Start the application

Use Node.js 20+ and Python 3.11+.

### 1. Install and start the API

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
uvicorn backend.main:app --reload --port 8000
```

The API docs are at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). On first start, the demo database and sample accounts are created at `backend/civictrack.db`.

### 2. Install and start the web app

In a second terminal from the project directory:

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The Next.js rewrite proxies `/api/*` and private image requests to the FastAPI service. Set `BACKEND_URL` before starting or building Next.js if the API is hosted somewhere else.

### Optional Docker Compose demo

```bash
docker compose up --build
```

Open [http://localhost:3000](http://localhost:3000). Compose starts a PostGIS-enabled PostgreSQL service, FastAPI, and Next.js. The application stores coordinates as latitude/longitude and runs clustering in the API; the PostGIS image is provided as a deployment option, but geometry operators and spatial indexes are not yet used. Change the default Compose passwords before sharing the stack beyond a local demo.

### Demo accounts

All sample accounts use the password `civictrack123`.

| Role | Email |
| --- | --- |
| Municipal administrator | `admin@civictrack.demo` |
| Citizen | `citizen@civictrack.demo` |
| Road department officer | `officer1@civictrack.demo` |
| Sanitation officer | `officer2@civictrack.demo` |
| Water works officer | `officer3@civictrack.demo` |

The sign-in screen has quick links for the administrator, citizen, and officer views. Use **Reset sample data** from the account menu to restore the seeded dataset.

## Main workflows

- The public home page introduces the reporting lifecycle and platform capabilities, with examiner demo data clearly identified as synthetic. Visitors can sign in to the role-based workspace or create a citizen account.
- Citizens can register, submit a report with a location and optional image, review their report history, and confirm a resolution or reopen it.
- Administrators can review AI suggestions, update category and priority, assign an officer and department, set category response targets and escalation grace periods, monitor service metrics, export CSV or a print-ready PDF report, manage departments, and inspect audit events.
- Officers see assigned reports, log progress, and submit a completion note plus optional photo for citizen verification.
- The civic map uses OpenStreetMap tiles, with category, status, priority, and date filters. Public map previews omit resident names and contact details and round coordinates to neighborhood precision.
- Officers can resume work on citizen-reopened reports. Each report keeps status and escalation history; escalation checks create a first alert at the configured target and a second alert after its grace period.
- Department service scores publish their weights in the UI. Metrics come from database records. The DBSCAN/Haversine hotspot layer is marked experimental when the dataset is small.

## AI and analytics notes

- Text classification uses a local scikit-learn TF-IDF/logistic-regression model trained from a small included phrase set. The model is an academic demonstration, not a production-trained civic classifier. A keyword fallback is used if scikit-learn cannot load.
- Priority uses a readable rule score (safety terms, severity terms, reported impact, duration, and photo presence). Staff can review and adjust it; AI alone does not close, reject, or discard reports.
- Duplicate candidates combine text token overlap, category, approximate distance, time window, and a simple average image hash where Pillow is available. Suggestions are advisory and are never automatically merged.
- Summaries use a concise local excerpt of the report description. Image categories/embeddings, translation, and Hindi speech recognition are not implemented. The optional browser voice input is experimental and English-only.

## Database and migrations

SQLAlchemy models define users, departments, category-level service policies, complaints, status history, notifications, evidence, feedback, duplicate candidates, escalation events, and audit logs. SQLite is the default. PostgreSQL URLs are supported through SQLAlchemy; set `DATABASE_URL` and install the included psycopg driver. The hotspot calculation currently uses application-side coordinates rather than PostGIS geometry/index operators. Service targets are saved in the database; changing a target affects new reports, while existing report deadlines remain as recorded.

Apply the initial Alembic baseline with:

```bash
source .venv/bin/activate
alembic upgrade head
```

The API also creates missing tables at startup to keep the examiner demo easy to launch. Revision `0002_service_policies` adds saved response and escalation targets for databases that already applied the initial baseline.

## Tests and production build

```bash
npm run lint
npm run build
source .venv/bin/activate
python -m pytest backend/test_api.py -q
```

The API tests cover role protection, the report-to-verification lifecycle, reopened officer work, AI review, service target persistence, staged escalations, report export access, and invalid image rejection.

## Configuration

Copy `.env.example` to `.env` and set:

- `DATABASE_URL` — defaults to a local SQLite file.
- `JWT_SECRET` — replace the demo value with a long, random secret for any non-demo environment.
- `DEMO_MODE` — `true` seeds synthetic demo accounts and enables reset; set `false` to disable seeding and reset.
- `BACKEND_URL` — used by Next.js server rewrites; defaults to `http://127.0.0.1:8000`.
- `CIVICTRACK_INDEX_WEIGHTS` — optional JSON object for the six index weights; values must total 100 (example: `{"resolution_rate":30,"resolution_time":20,"overdue_rate":20,"citizen_verification":15,"reopened_rate":5,"citizen_satisfaction":10}`).

Do not use the included demo password or sample JWT secret outside a local classroom demonstration.

## Current prototype limits

This project is functional for a local academic demonstration. It does not claim to be production-hardened. Escalation checks run when an administrator opens analytics; there is no always-on scheduler. The PDF report opens a print-ready browser page and uses the browser's **Save as PDF** option. Email delivery, WebSockets/push notifications, SMS, department service-area GIS layers, Hindi translation, and image-based issue classification are not connected. Voice input is browser-provided, experimental, and English-only. Notifications are in-app. A production deployment should add managed secrets, HTTPS, a shared rate-limit store, verified email, object storage, formal data-retention rules, observability, and a migration policy. Accessibility has keyboard focus styles and responsive layouts, but has not received an independent WCAG 2.2 AA audit.
