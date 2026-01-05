# Vercel Deployment Guide & Limitations

## Configuration Added
We have configured the project for Vercel deployment:
1.  **`package.json`**: Added `"build": "npm run build:css"` script. Vercel runs this automatically to generate Tailwind styles.
2.  **`vercel.json`**: Configured to route all traffic to `api/index.py`.
3.  **`api/index.py`**: A Vercel-compatible entry point that exposes the Flask `app`.

## ⚠️ CRITICAL LIMITATIONS
This application relies on components that are **NOT compatible with standard Vercel Serverless Functions**:

### 1. SQLite Database (`faktury.db`)
*   **Problem:** Vercel functions are ephemeral and read-only (except `/tmp`). You cannot persist a SQLite database file.
*   **Result:** Data will be lost on every deployment or function restart, or the app will crash trying to write to the DB.
*   **Solution:** You must use an external database (e.g., PostgreSQL via Neon, Supabase, or Railway) and update `config/database.py`.

### 2. Tesseract OCR & Poppler
*   **Problem:** The app requires `tesseract-ocr` and `poppler` binaries installed on the system (`apt-get install ...`). Vercel does not support installing system packages easily.
*   **Result:** Uploading and processing PDFs will **FAIL** with "Command not found" or similar errors.
*   **Solution:** 
    *   **Option A:** Deploy to a container-based host like **Railway**, **Fly.io**, or **Render** (using a `Dockerfile`).
    *   **Option B:** Refactor the OCR logic to use an external API (Google Cloud Vision, AWS Textract).

### 3. Local File Storage (`uploads/`, `pdfs/`)
*   **Problem:** Vercel does not support persistent file storage.
*   **Result:** Uploaded PDFs will disappear.
*   **Solution:** Use AWS S3, Google Cloud Storage, or Azure Blob Storage for files.

## Recommendation
For this specific application (OCR + Database + File Processing), **Vercel is not recommended**.
We suggest deploying using **Docker** on a platform like **Railway** or **Render**.
