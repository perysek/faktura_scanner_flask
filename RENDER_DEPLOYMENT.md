# Render Deployment Guide

This project is now configured for deployment on **Render** (or any Docker-based platform).

## 🐳 Docker Configuration
We have added a `Dockerfile` that handles:
1.  **System Dependencies**: Installs `tesseract-ocr` (with Polish language pack), `poppler-utils`, and OpenCV libraries.
2.  **Node.js**: Installs Node.js to build TailwindCSS styles during the build process.
3.  **Python**: Installs all requirements and uses `gunicorn` as the production WSGI server.

## 🚀 How to Deploy on Render

1.  **Push your code** to GitHub/GitLab.
2.  Log in to [Render.com](https://render.com).
3.  Click **New +** -> **Web Service**.
4.  Connect your repository.
5.  Select **Docker** as the Runtime.
6.  **Environment Variables**:
    *   `SECRET_KEY`: (Generate a strong random string)
    *   `TESSERACT_CMD`: `/usr/bin/tesseract` (Default in Dockerfile, but good to be explicit)
    *   `POPPLER_PATH`: `/usr/bin` (Default in Dockerfile)

## ⚠️ Important Considerations

### 1. Database Persistence (SQLite)
*   **Current State**: The app uses `faktury.db` (SQLite).
*   **Issue**: On Render, the disk is ephemeral. **You will lose all data (invoices, sellers) every time you redeploy.**
*   **Solution**:
    *   **Recommended**: Create a **Render PostgreSQL** database.
    *   **Action Required**: You need to update the application code to support PostgreSQL (currently it relies heavily on raw SQLite queries). This is a significant refactor.
    *   **Alternative (Not Recommended)**: Use a "Disk" in Render. This allows you to mount a persistent storage volume (e.g., at `/data`) and store the SQLite DB there.
        *   *If you choose this*: Update `DB_PATH` in `config/settings.py` to point to `/data/faktury.db`.

### 2. File Storage (`uploads/`, `pdfs/`)
*   **Issue**: Similar to the database, uploaded PDF files will be lost on redeploy.
*   **Solution**: Use a Render **Disk** (Persistent Disk).
    *   Mount a disk at `/app/pdfs`.
    *   Or switch to AWS S3 / Google Cloud Storage.

## Summary
The application will **run** successfully with this Docker setup. However, for a production app where you need to keep your data, you **must** configure persistent storage (Render Disk) or switch to a persistent database (Postgres) and cloud storage (S3).
