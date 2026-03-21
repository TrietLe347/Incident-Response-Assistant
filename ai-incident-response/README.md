# ARIA — AI Incident Response Assistant

A production-ready React frontend for a RAG-based incident response system.
Communicates with the **Answer Service** on Google Cloud Run, which retrieves
policy document chunks and generates answers via Gemini.

```
┌─────────────────────────────────────────────────┐
│              ARIA Frontend (this repo)          │
│         React · Tailwind · Vite                 │
└────────────────────┬────────────────────────────┘
                     │ POST /  { query }
                     ▼
┌─────────────────────────────────────────────────┐
│           Answer Service (Cloud Run)            │
│  RAG pipeline: retrieval → Gemini → response   │
└─────────────────────────────────────────────────┘
```

---

## Project Structure

```
ai-incident-response/
├── public/
│   └── favicon.svg
├── src/
│   ├── components/
│   │   ├── ChatWindow.jsx      # Scrollable message list + empty state
│   │   ├── MessageBubble.jsx   # User/assistant bubbles + source list
│   │   └── ChatInput.jsx       # Auto-resize textarea + send button
│   ├── services/
│   │   └── api.js              # Fetch wrapper for Answer Service
│   ├── App.jsx                 # Root component + state management
│   ├── main.jsx                # React entry point
│   └── index.css               # Tailwind + custom CSS
├── Dockerfile                  # Multi-stage build for Cloud Run
├── nginx.conf                  # SPA routing + compression
├── firebase.json               # Firebase Hosting config
├── vite.config.js
├── tailwind.config.js
├── postcss.config.js
└── package.json
```

---

## Prerequisites

- **Node.js** ≥ 18
- **npm** ≥ 9

---

## Run Locally

```bash
# 1. Install dependencies
npm install

# 2. Start dev server (hot reload on http://localhost:3000)
npm run dev

# 3. Build for production
npm run build

# 4. Preview production build locally
npm run preview
```

---

## Deploy to Firebase Hosting

Firebase Hosting is the easiest option — global CDN, free SSL, zero config.

```bash
# 1. Install Firebase CLI (once)
npm install -g firebase-tools

# 2. Login
firebase login

# 3. Initialize (first time only — select "Hosting", use existing project)
firebase init hosting
# When prompted:
#   Public directory: dist
#   Single-page app: yes
#   Overwrite index.html: no

# 4. Build & deploy
npm run build
firebase deploy --only hosting
```

After deploy you'll get a URL like:
`https://YOUR_PROJECT_ID.web.app`

---

## Deploy to Google Cloud Run

### Option A — Using Cloud Build (recommended for CI/CD)

```bash
# Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Build the container image and push to Artifact Registry
gcloud builds submit \
  --tag gcr.io/YOUR_PROJECT_ID/aria-frontend:latest \
  --project YOUR_PROJECT_ID

# Deploy to Cloud Run
gcloud run deploy aria-frontend \
  --image gcr.io/YOUR_PROJECT_ID/aria-frontend:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --memory 256Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 5
```

### Option B — Local Docker build

```bash
# Build the image
docker build -t aria-frontend .

# Test locally
docker run -p 8080:8080 aria-frontend
# Open http://localhost:8080

# Push and deploy (after tagging)
docker tag aria-frontend gcr.io/YOUR_PROJECT_ID/aria-frontend:latest
docker push gcr.io/YOUR_PROJECT_ID/aria-frontend:latest
gcloud run deploy aria-frontend \
  --image gcr.io/YOUR_PROJECT_ID/aria-frontend:latest \
  --region us-central1 \
  --allow-unauthenticated
```

---

## API Configuration

The Answer Service URL is defined in `src/services/api.js`:

```js
const ANSWER_SERVICE_URL =
  'https://answer-service-571628338947.us-central1.run.app';
```

To change the endpoint (e.g. for a different environment), update this constant
or add a `.env` file and use Vite's `import.meta.env`:

```bash
# .env.local
VITE_ANSWER_SERVICE_URL=https://your-service-url.run.app
```

```js
// src/services/api.js
const ANSWER_SERVICE_URL = import.meta.env.VITE_ANSWER_SERVICE_URL;
```

---

## CORS

If the Answer Service returns CORS errors, add these headers to the Cloud Run
service (in the Cloud Console or via `gcloud`):

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: POST, OPTIONS
Access-Control-Allow-Headers: Content-Type
```

Or restrict the origin to your Firebase/Cloud Run frontend URL for production.

---

## Features

| Feature | Status |
|---|---|
| Chat interface with history | ✅ |
| Enter to send, Shift+Enter for newline | ✅ |
| Loading spinner / typing animation | ✅ |
| Assistant answer bubbles | ✅ |
| Collapsible source document list | ✅ |
| Response latency display (ms) | ✅ |
| Friendly error messages | ✅ |
| Auto-scroll to latest message | ✅ |
| Auto-resize input textarea | ✅ |
| Clear chat button | ✅ |
| Suggestion chips (empty state) | ✅ |
| Keyboard accessible | ✅ |
| Dark mode design | ✅ |
| Responsive (mobile + desktop) | ✅ |

---

## Tech Stack

- **React 18** — functional components + hooks
- **Vite 5** — dev server + build tool
- **Tailwind CSS 3** — utility-first styling
- **DM Mono + DM Sans** — typography (Google Fonts)
- **Nginx (Alpine)** — production static file server
- **Docker** — multi-stage container build

---

## License

MIT
