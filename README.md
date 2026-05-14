# scrapper-server

FastAPI service that accepts URLs, scrapes page metadata asynchronously, stores results in MongoDB, and serves metadata through a Redis read-through cache.

## Stack

- FastAPI + Uvicorn
- MongoDB with Motor
- Redis async client
- httpx + BeautifulSoup4
- Docker Compose for local services

## Run With Docker

```bash
docker compose up --build
```

The API will be available at `http://localhost:8000`.

## Run Locally

Start MongoDB and Redis locally, then:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.cmd.main
```

For local non-Docker usage, `.env.example` already points MongoDB and Redis to `localhost`.

## API

### Health

```bash
curl http://localhost:8000/health
```

### Start Scraping

```bash
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}'
```

New URLs return `202 Accepted` and are processed in the background. Existing URLs return `200 OK` with the stored status.

### Fetch Metadata

```bash
curl "http://localhost:8000/metadata?url=https://example.com"
```

The endpoint checks Redis first, then MongoDB. If the URL is not known, it creates a pending MongoDB document, starts background scraping, and returns `202 Accepted`.

## Configuration

Docker Compose sets all runtime values for the API container:

- `MONGODB_URI`
- `MONGODB_DATABASE`
- `MONGODB_COLLECTION`
- `REDIS_URL`
- `CACHE_TTL_SECONDS`
- `MAX_CONCURRENT_WORKERS`
- `REQUEST_TIMEOUT_SECONDS`
- `MAX_RETRIES`
- `USER_AGENT`
- `MAX_PAGE_SOURCE_CHARS`

The same values can be set in `.env` for local execution.

## Testing

### Run Tests with Docker

The easiest way to run tests is using Docker:

```bash
# Linux/Mac
./run_tests.sh

# Windows
run_tests.bat

# Or manually
docker build -f Dockerfile.test -t scrapper-server-tests .
docker run --rm scrapper-server-tests
```

### Run Tests Locally

With virtual environment activated:

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=app --cov-report=term-missing

# Run specific test file
pytest tests/test_api.py -v
```

### Tests During Build

The main Dockerfile includes a test stage. When you build with `docker compose up --build`, tests are automatically executed. If tests fail, the build will stop.

## Project Layout

```text
app/
  api.py              FastAPI app and endpoints
  cache.py            Redis cache wrapper
  config.py           Environment-driven settings
  database.py         MongoDB persistence wrapper
  cmd/main.py         Uvicorn entry point
  fetcher/
    webscraper.py     HTTP fetch and metadata extraction
    worker.py         Retry and persistence workflow
  models/
    api_models.py     Request and response models
    db_models.py      DB document helpers

tests/
  test_api.py         API endpoint tests
  test_cache.py       Cache layer tests
  test_database.py    Database layer tests
  test_worker.py      Worker and retry logic tests
  test_webscraper.py  Metadata extraction tests
  test_models.py      Pydantic model tests
  test_config.py      Configuration tests
```

