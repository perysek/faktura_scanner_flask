# FakturaScanner - Flask Web Application

## Migration Overview

The application has been successfully migrated from **Flet** (Python GUI framework) to a modern **Flask web application** with:

- **Flask** for backend routing and API endpoints
- **Jinja2** templates for HTML rendering
- **TailwindCSS** for responsive, modern styling
- **Vanilla JavaScript** with AJAX/Fetch API for dynamic interactions
- **Material Icons** for consistent iconography

## Features

All original features have been preserved:

1. **Invoice Management**
   - View all invoices in a sortable, searchable table
   - Create, read, update, delete (CRUD) operations
   - Real-time statistics dashboard
   - Export to Excel/CSV

2. **PDF Processing**
   - Upload PDF files via drag-and-drop or file picker
   - OCR extraction using Tesseract
   - Automatic data validation
   - Duplicate detection

3. **Email Integration**
   - IMAP email import
   - Automatic PDF extraction from email attachments
   - Configurable date range filtering

4. **Audit Trail**
   - Complete history of all changes
   - Filter by invoice
   - Detailed change tracking

5. **Modern UI/UX**
   - Responsive design (works on mobile, tablet, desktop)
   - Toast notifications
   - Modal dialogs
   - Progress indicators
   - Dark hover states and smooth transitions

## Project Structure

```
faktura_scanner_flask/
├── app.py                      # Main Flask application
├── routes/
│   ├── main_routes.py          # Page routes (HTML views)
│   └── api_routes.py           # API endpoints (JSON)
├── templates/
│   ├── base.html               # Base layout with navigation
│   ├── invoices/
│   │   ├── list.html           # Invoice list view
│   │   ├── upload.html         # Upload & processing view
│   │   └── edit.html           # Edit invoice form
│   ├── history/
│   │   └── list.html           # Audit trail view
│   ├── settings/
│   │   └── email.html          # Email configuration
│   └── errors/
│       ├── 404.html
│       └── 500.html
├── static/
│   ├── css/
│   │   ├── input.css           # TailwindCSS source
│   │   └── output.css          # TailwindCSS compiled (generated)
│   └── js/
│       ├── utils.js            # Utility functions
│       ├── api.js              # API wrapper
│       ├── notifications.js    # Toast system
│       ├── modals.js           # Modal dialogs
│       └── invoices/
│           ├── list.js         # Invoice list page JS
│           └── upload.js       # Upload page JS
├── services/                   # Business logic (unchanged)
├── repositories/               # Database access (unchanged)
├── database/                   # Models & DB setup (unchanged)
├── config/                     # Configuration (unchanged)
└── utils/                      # Utilities (unchanged)
```

## Setup Instructions

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Node.js Dependencies (for TailwindCSS)

```bash
npm install
```

### 3. Build TailwindCSS

```bash
# One-time build
npm run build:css

# Or watch mode for development (auto-rebuild on changes)
npm run watch:css
```

### 4. Initialize Database

The database will be automatically initialized on first run. The SQLite database file will be created at the path specified in `config/database.py`.

### 5. Run the Application

```bash
python app.py
```

The application will be available at: **http://localhost:5000**

## Development

### TailwindCSS Development

When developing and modifying styles:

```bash
# Start TailwindCSS watch mode in a separate terminal
npm run watch:css
```

This will automatically rebuild the CSS whenever you modify:
- HTML templates in `templates/`
- JavaScript files in `static/js/`
- The source CSS in `static/css/input.css`

### Adding New Pages

1. **Create route** in `routes/main_routes.py`:
```python
@main_bp.route('/your-page')
def your_page():
    return render_template('your_page.html')
```

2. **Create template** in `templates/`:
```html
{% extends "base.html" %}
{% block content %}
  <!-- Your content -->
{% endblock %}
```

3. **Add JavaScript** if needed in `static/js/`

4. **Add to navigation** in `templates/base.html`

### Adding API Endpoints

Add new endpoints in `routes/api_routes.py`:

```python
@api_bp.route('/your-endpoint', methods=['GET', 'POST'])
def your_endpoint():
    # Your logic here
    return jsonify({'success': True, 'data': data})
```

## API Endpoints

### Invoices
- `GET /api/invoices` - Get all invoices (with optional search)
- `GET /api/invoices/<id>` - Get single invoice
- `PUT /api/invoices/<id>` - Update invoice
- `DELETE /api/invoices/<id>` - Delete invoice
- `GET /api/invoices/statistics` - Get statistics

### Upload
- `POST /api/upload` - Upload and process PDF files

### Export
- `GET /api/export/excel` - Export to Excel
- `GET /api/export/csv` - Export to CSV

### Email
- `POST /api/email/import` - Import PDFs from email
- `POST /api/email/test` - Test email connection
- `GET /api/email/settings` - Get email settings
- `POST /api/email/settings` - Save email settings

### History
- `GET /api/history` - Get audit trail (optional invoice_id filter)

### PDF
- `GET /api/pdf/<invoice_id>` - View PDF file

## UI Components

### Notifications

```javascript
Notifications.success('Operation successful!');
Notifications.error('An error occurred');
Notifications.warning('Please check this');
Notifications.info('Information message');
```

### Modals

```javascript
// Confirm dialog
Modals.confirm({
    title: 'Delete Invoice',
    message: 'Are you sure?',
    onConfirm: () => { /* delete logic */ }
});

// Alert dialog
Modals.alert({
    title: 'Success',
    message: 'Operation completed',
    type: 'success'
});

// Loading modal
const loading = Modals.loading('Processing...');
// ... do work ...
Modals.close(loading);
```

### API Calls

```javascript
// Get invoices
const data = await API.invoices.getAll(searchQuery);

// Update invoice
const result = await API.invoices.update(id, updateData);

// Upload files with progress
await API.upload.files(files, (percent) => {
    console.log(`Progress: ${percent}%`);
});
```

## Styling with TailwindCSS

The application uses custom TailwindCSS classes defined in `static/css/input.css`:

- `.card` - White background card with shadow
- `.btn-primary` - Primary blue button
- `.btn-secondary` - Secondary gray button
- `.btn-success`, `.btn-danger`, `.btn-warning` - Colored buttons
- `.input` - Styled form input
- `.badge-success`, `.badge-error`, `.badge-warning` - Status badges
- `.nav-link` - Navigation link styling
- `.modal-*` - Modal components
- `.toast-*` - Toast notification styles

## Configuration

### Environment Variables

Set these environment variables (or modify in code):

- `SECRET_KEY` - Flask secret key for sessions
- `UPLOAD_FOLDER` - Path for uploaded files
- `PDF_FOLDER` - Path for PDF storage

### Email Settings

Configure IMAP settings in the Email Settings page:
- Server (e.g., imap.gmail.com)
- Port (usually 993 for SSL)
- Email address
- Password (use app password for Gmail)

## Production Deployment

For production deployment:

1. **Set proper SECRET_KEY**:
```bash
export SECRET_KEY="your-secure-random-key"
```

2. **Use production WSGI server** (e.g., Gunicorn):
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

3. **Build TailwindCSS with minification**:
```bash
npm run build:css
```

4. **Set Flask environment**:
```bash
export FLASK_ENV=production
```

5. **Use proper database** (PostgreSQL recommended for production)

6. **Set up reverse proxy** (nginx recommended)

## Migration Notes

### What Was Changed

1. **Removed Flet** - No longer using Python GUI framework
2. **Added Flask** - Standard web framework
3. **Created HTML templates** - Jinja2 templates for all views
4. **Added TailwindCSS** - Modern CSS framework
5. **JavaScript for interactivity** - AJAX/Fetch for dynamic updates

### What Stayed the Same

1. **All business logic** - Services, repositories, utilities unchanged
2. **Database models** - No changes to data structure
3. **Configuration** - Settings and config files preserved
4. **OCR processing** - PDF processing pipeline intact
5. **Email integration** - IMAP email service preserved

### Old Files (Can be removed if migration is successful)

- `main.py` - Old Flet desktop entry point
- `main_webview.py` - Old Flet webview entry point
- `gui/` directory - All old Flet GUI components
- `config/webview_settings.py` - Webview-specific settings

## Troubleshooting

### TailwindCSS not working
Run `npm run build:css` to generate the output CSS file.

### Static files not loading
Ensure Flask is serving static files correctly. Check the `static/` folder exists.

### Database errors
Delete the database file and restart the app to reinitialize.

### Upload not working
Check that `UPLOAD_FOLDER` directory exists and has write permissions.

### Email import failing
Verify IMAP settings in Email Settings page. For Gmail, use app password.

## Browser Compatibility

The application is tested and works on:
- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)

## License

Same as original project.
