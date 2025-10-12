# 504:DeadlineExceeded

## Frontend:

## Backend:

### Environment setup

1. Create `server/.env` (see `server/.env` for required keys) and populate:
   - Canvas credentials (`CANVAS_BASE_URL`, `CANVAS_TOKEN`, etc.).
   - Firebase Admin credentials via either `GOOGLE_APPLICATION_CREDENTIALS` (file path) or `GOOGLE_APPLICATION_CREDENTIALS_JSON` (inline JSON).
   - Gemini API configuration: set `GEMINI_API_KEY` (required) and optionally override `GEMINI_MODEL_NAME`.
2. Install Python deps with `pip install -r server/requirements.txt`.
3. Start the API with `python server/app.py`.

