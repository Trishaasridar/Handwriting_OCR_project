# Handwriting OCR Project — Progress, Changes & Problems

*Last updated: March 14, 2026*

---

## Progress

### Version Timeline

| Version | Status | Description |
|---------|--------|-------------|
| **v1** | Original | Single-image upload, MySQL, basic OCR |
| **v2** | Completed | App factory, MySQL, improved OCR, validation |
| **v3** | Completed | SQLite3, book-style UI, no external DB |
| **v4** | Completed | Multi-image batch upload (25–50 images), background jobs, live progress |

### v4 Milestones

- **Multi-image upload** — Accept up to 50 images per request
- **Background processing** — Job-based processing; UI returns immediately with `job_id`
- **Live progress** — Poll `/api/job/<job_id>` for per-image progress and ETA
- **Higher limits** — 500 MB total, 20 MB per file, 15 min timeout
- **Batch tracking** — `batch_id` and `filename` per record in SQLite

---

## Changes

### v1 → v2

- Flask app factory pattern
- Environment-based config (`.env`)
- Input validation and security
- Improved OCR preprocessing (CLAHE, spell check)
- MySQL with parameterized queries
- New API: `/api/process`, `/api/search`

### v2 → v3

- **Database**: MySQL → SQLite3 (no external DB server)
- **Schema**: Added `record_time` (renamed from `time`), SQLite-compatible types
- **UI**: Restored original book-style layout from v1
- **Config**: `DB_PATH` instead of MySQL host/user/password

### v3 → v4

- **Upload**: Single file → multiple files (up to 50)
- **Processing**: Synchronous → background thread + job polling
- **Schema**: Added `batch_id`, `filename` columns
- **API**: New `/api/job/<job_id>` for progress
- **Limits**: 500 MB total, 20 MB per file, 50 files max
- **UI**: Live progress bar, per-image cards, “Download All”

---

## Problems & Fixes

### 1. OneDNN / MKL-DNN Error

**Error:**
```
(Unimplemented) ConvertPirAttribute2RuntimeAttribute not support 
[pir::ArrayAttribute<pir::DoubleAttribute>]
(at ..\paddle\fluid\framework\new_executor\instruction\onednn\onednn_instruction.cc:118)
```

**Fix:** Disable OneDNN in PaddleOCR:
```python
ocr = PaddleOCR(..., enable_mkldnn=False)
```

---

### 2. MySQL Connection Refused

**Error:**
```
2003: Can't connect to MySQL server on 'localhost:3306' 
(10061 No connection could be made because the target machine actively refused it)
```

**Fix:** MySQL server not running. Project migrated to SQLite3 in v3 to remove external DB dependency.

---

### 3. SECRET_KEY Required in Production

**Error:**
```
ValueError: SECRET_KEY environment variable is required in production
```

**Fix:** 
- Added `.env` with `FLASK_ENV=development` and `SECRET_KEY`
- Moved SECRET_KEY validation into `ProductionConfig.init_app()` so it runs only when production config is used

---

### 4. Logs Directory Missing

**Error:**
```
FileNotFoundError: [Errno 2] No such file or directory: '...\\logs\\app.log'
```

**Fix:** `setup_logging` now creates the `logs` directory if it does not exist.

---

### 5. PaddleOCR Deprecated Arguments

**Error:**
```
OCR initialisation failed: Unknown argument: show_log
```

**Fix:** Removed deprecated arguments (`show_log`, `device`, `det_db_thresh`, etc.) from `PaddleOCR()` for PaddleOCR 3.x.

---

### 6. Bounding Box Type Error

**Error:**
```
unsupported operand type(s) for -: 'list' and 'list'
```

**Fix:** PaddleOCR 3.x returns bboxes as `[x1, y1, x2, y2]`. Kept this flat list format instead of converting to polygon; updated `_group_into_lines` to use numeric values.

---

### 7. SQLite Column Name Conflict

**Error:** `time` column conflicted with SQLite built-in `TIME` function.

**Fix:** Renamed column to `record_time` in schema and model.

---

### 8. Request Entity Too Large (413)

**Error:**
```
413 Request Entity Too Large: The data value transmitted exceeds the capacity limit.
```

**Fix:**
- Raised `MAX_CONTENT_LENGTH` from 16 MB to 500 MB
- Added explicit `RequestEntityTooLarge` handling in routes
- Re-raise `HTTPException` so Flask’s 413 handler is used

---

### 9. Flask `_get_current_object` AttributeError

**Error:**
```
'Flask' object has no attribute '_get_current_object'
```

**Fix:** `_get_current_object()` is for `LocalProxy` (e.g. `current_app`), not the Flask app. Pass `app` directly to the background thread.

---

### 10. Database Transaction / Schema Creation

**Problem:** `conn.executescript()` conflicted with the context manager’s transaction handling.

**Fix:** Replaced with individual `conn.execute()` calls inside `init_db`.

---

## File Structure (v4)

```
v4/
├── app.py              # Entry point
├── .env                # Local config (not in git)
├── .gitignore
├── requirements.txt
├── app/
│   ├── __init__.py     # App factory
│   ├── config.py       # Config classes
│   ├── models.py       # SQLite, OCRResult, batch_id
│   ├── routes.py       # /api/process, /api/job/<id>, /api/search
│   ├── ocr_service.py  # PaddleOCR processing
│   └── utils.py        # Validation, file handling
├── templates/
│   └── index.html      # Book UI, multi-file, live progress
├── uploads/             # Temp files (not in git)
├── logs/               # App logs (not in git)
└── ocr.db              # SQLite DB (not in git)
```

---

## Run v4

```bash
cd v4
pip install -r requirements.txt
# Create .env with FLASK_ENV=development, SECRET_KEY, DB_PATH=ocr.db
python app.py
# Open http://127.0.0.1:5000
```
