# Cortex Engine

Cortex Engine is a standalone FastAPI backend for storing and processing Nyabag memory metadata in Neon PostgreSQL.

This foundation includes the API, database connection, health check, memory intake endpoint, and synchronous Gemini Vision screenshot processing. Embeddings, workers, queues, and semantic search are intentionally out of scope for now.

## Requirements

- Python 3.10 or newer
- Neon PostgreSQL database with the existing Cortex tables
- VS Code or another editor

## Setup

Create a virtual environment:

```powershell
python -m venv .venv
```

If `python` opens the Microsoft Store or is not found, install Python from python.org and reopen VS Code, or disable the Windows app execution aliases for `python.exe` and `python3.exe`.

Activate it on Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Copy the example environment file:

```powershell
Copy-Item .env.example .env
```

Open `.env` and paste your Neon pooled connection string into `DATABASE_URL`:

```env
DATABASE_URL="postgresql://..."
GEMINI_API_KEY="your_gemini_api_key_here"
```

Get a Gemini API key from Google AI Studio and add it to `.env` as `GEMINI_API_KEY`.

Run the development server:

```powershell
uvicorn app.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

## Endpoints

### Root

```http
GET /
```

Expected response:

```json
{
  "name": "Cortex Engine",
  "status": "awake"
}
```

### Health Check

```http
GET /health
```

Expected response when the database is reachable:

```json
{
  "status": "ok",
  "database": "connected",
  "result": 1
}
```

Test with curl:

```powershell
curl.exe http://127.0.0.1:8000/health
```

### Remember

```http
POST /remember
```

Sample JSON body:

```json
{
  "nyabagBookmarkId": "11111111-1111-1111-1111-111111111111",
  "userId": "22222222-2222-2222-2222-222222222222",
  "url": "https://stripe.com",
  "title": "Stripe Landing Page",
  "summary": "Modern SaaS landing page reference",
  "screenshotUrl": "https://picsum.photos/1200/800"
}
```

Test with curl:

```powershell
curl.exe -X POST http://127.0.0.1:8000/remember `
  -H "Content-Type: application/json" `
  -d '{
    "nyabagBookmarkId": "11111111-1111-1111-1111-111111111111",
    "userId": "22222222-2222-2222-2222-222222222222",
    "url": "https://stripe.com",
    "title": "Stripe Landing Page",
    "summary": "Modern SaaS landing page reference",
    "screenshotUrl": "https://picsum.photos/1200/800"
  }'
```

Expected response:

```json
{
  "status": "queued",
  "memoryId": "generated-memory-id",
  "processingStatus": "pending"
}
```

You can also test `POST /remember` in Thunder Client by creating a new POST request to `http://127.0.0.1:8000/remember`, setting the body type to JSON, and pasting the sample body above.

### Processing a Memory

```http
POST /process/{memory_id}
```

This downloads the memory screenshot, sends it to Gemini Vision, stores structured UI/design analysis back into `cortex_memories`, and marks the memory as `completed`.

For now, processing runs synchronously inside the API request. Later, this should move into a background worker or queue. Embeddings and semantic search will be added after vision analysis works.

First create a memory with `POST /remember`, then copy the returned `memoryId` and call:

```powershell
curl.exe -X POST http://127.0.0.1:8000/process/generated-memory-id
```

Expected response:

```json
{
  "status": "processed",
  "memoryId": "generated-memory-id",
  "processingStatus": "completed",
  "visualDescription": "A polished SaaS landing page with a clear hero section and strong visual hierarchy.",
  "extractedText": "Visible page text extracted by Gemini.",
  "detectedComponents": [
    {
      "type": "navbar",
      "label": "Top navigation",
      "confidence": 0.72
    },
    {
      "type": "hero_section",
      "label": "Primary hero area",
      "confidence": 0.81
    }
  ],
  "detectedColors": [
    {
      "hex": "#111827",
      "role": "background",
      "confidence": 0.78
    },
    {
      "hex": "#6366F1",
      "role": "accent",
      "confidence": 0.66
    }
  ],
  "autoTags": [
    "landing-page",
    "saas",
    "hero-section"
  ]
}
```

If `GEMINI_API_KEY` is missing, the API returns:

```json
{
  "detail": "Processing failed"
}
```

The memory row is marked as `failed`, and `processing_error` stores a clean message explaining that `GEMINI_API_KEY` is missing.

You can also test the full flow in Swagger:

```text
http://127.0.0.1:8000/docs
```

Use `POST /remember` first, copy `memoryId` from the response, then run `POST /process/{memory_id}`.

### Embedding a Processed Memory

```http
POST /embed/{memory_id}
```

Run this only after `POST /process/{memory_id}` has completed successfully. Cortex builds a searchable text document from the processed memory, generates a Gemini embedding with `gemini-embedding-001`, and stores it in `cortex_embeddings`.

If an existing `memory_analysis` embedding already exists for the same memory, it is replaced when you re-embed. Search will be added next.

Testing flow:

1. Create a memory:

```http
POST /remember
```

2. Copy `memoryId`.

3. Process the memory:

```http
POST /process/{memoryId}
```

4. Embed the processed memory:

```powershell
curl.exe -X POST http://127.0.0.1:8000/embed/generated-memory-id
```

Expected response:

```json
{
  "status": "embedded",
  "memoryId": "generated-memory-id",
  "embeddingId": "generated-embedding-id",
  "embeddingType": "memory_analysis",
  "modelName": "gemini-embedding-001",
  "dimensions": 768,
  "contentPreview": "Title:\nStripe Landing Page\n\nURL:\nhttps://stripe.com"
}
```

You can verify the stored embedding in Neon with:

```sql
SELECT
  e.id,
  e.memory_id,
  e.embedding_type,
  e.model_name,
  length(e.content) AS content_length,
  e.created_at
FROM cortex_embeddings e
WHERE e.memory_id = 'PASTE_MEMORY_ID_HERE';
```

If your current Neon table predates the `model_name` column, omit `e.model_name` from that verification query. The API still returns `gemini-embedding-001` as `modelName`.

### Semantic Search

```http
GET /search?q=AI%20SaaS%20landing%20page%20with%20pricing%20and%20testimonials&limit=10
```

Make sure a memory has been processed and embedded first. Search generates a query embedding with `gemini-embedding-001`, compares it against `cortex_embeddings` with pgvector cosine distance, and returns ranked completed memories.

Testing flow:

1. Create a memory:

```http
POST /remember
```

2. Process the memory:

```http
POST /process/{memoryId}
```

3. Embed the memory:

```http
POST /embed/{memoryId}
```

4. Search:

```powershell
curl.exe "http://127.0.0.1:8000/search?q=AI%20SaaS%20landing%20page%20with%20pricing%20and%20testimonials&limit=10"
```

Example queries:

- AI SaaS landing page with pricing
- productivity app with integrations
- long marketing page with testimonials
- dark and light mixed landing page
- workflow automation product

Expected response shape:

```json
{
  "query": "AI SaaS landing page with pricing and testimonials",
  "count": 1,
  "results": [
    {
      "memoryId": "generated-memory-id",
      "nyabagBookmarkId": "bookmark-id",
      "userId": "user-id",
      "title": "Stripe Landing Page",
      "url": "https://stripe.com",
      "summary": "Modern SaaS landing page reference",
      "screenshotUrl": "https://picsum.photos/1200/800",
      "similarity": 0.7,
      "autoTags": ["landing-page", "saas", "pricing-page"],
      "visualPreview": "A polished SaaS landing page...",
      "contentPreview": "Title:\nStripe Landing Page...",
      "embeddingId": "generated-embedding-id",
      "embeddingType": "memory_analysis",
      "modelName": "gemini-embedding-001"
    }
  ]
}
```

The exact similarity score can vary. If no embedded completed memories match, the API returns an empty result set:

```json
{
  "query": "your query",
  "count": 0,
  "results": []
}
```

Optional Neon SQL verification:

```sql
SELECT
  m.title,
  e.embedding_type,
  e.model_name,
  1 - (e.embedding <=> '[PASTE_QUERY_VECTOR_HERE]'::vector) AS similarity
FROM cortex_embeddings e
JOIN cortex_memories m ON m.id = e.memory_id
LIMIT 5;
```

This SQL check is optional. The API handles query embedding automatically.
If your current Neon table predates the `model_name` column, omit `e.model_name` from the optional SQL query.

### Full Ingestion Endpoint

```http
POST /ingest
```

This synchronous endpoint runs `remember` + `process` + `embed` in one request. It creates the memory, analyzes the screenshot with Gemini Vision, generates a `gemini-embedding-001` embedding, and stores the embedding in `cortex_embeddings`.

This can take several seconds because it calls Gemini Vision and Gemini Embeddings during the API request. Later, this should move into a background worker or queue.

Run the server:

```powershell
uvicorn app.main:app --reload
```

Open Swagger:

```text
http://127.0.0.1:8000/docs
```

Call `POST /ingest` with:

```json
{
  "nyabagBookmarkId": "33333333-3333-3333-3333-333333333333",
  "userId": "44444444-4444-4444-4444-444444444444",
  "url": "https://example.com",
  "title": "Runner Landing Page",
  "summary": "AI productivity landing page with pricing, testimonials, workflow automation, and integrations",
  "screenshotUrl": "https://vydawrbigmlhijpdnbgf.supabase.co/storage/v1/object/public/bookmark-screenshots/e6884fe1-9cd7-44ac-9064-712383f650ca/c08696a9-ae27-44f9-b095-f2c09928a592/long-screenshot-1783325766822.webp"
}
```

Expected response shape:

```json
{
  "status": "ingested",
  "memoryId": "generated-memory-id",
  "processingStatus": "completed",
  "embeddingStatus": "embedded",
  "embeddingId": "generated-embedding-id",
  "modelName": "gemini-embedding-001",
  "dimensions": 768,
  "title": "Runner Landing Page",
  "url": "https://example.com/",
  "autoTags": ["landing-page", "saas", "pricing-page"],
  "visualPreview": "A long-scrolling product landing page..."
}
```

Then test search:

```powershell
curl.exe "http://127.0.0.1:8000/search?q=AI%20productivity%20landing%20page%20with%20pricing&limit=10"
```
#   c o r t e x  
 