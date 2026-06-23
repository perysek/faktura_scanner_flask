"""
FakturaScanner - Flask Web Application
Main Flask application with Jinja templates, TailwindCSS, and JavaScript
"""
import atexit
import base64
import logging
import os
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from flask.json.provider import DefaultJSONProvider

from dotenv import load_dotenv
load_dotenv()  # Loads .env file from project root (Vultr/local deployment)

from flask import Flask, render_template, url_for
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError

# Configure logging — DEBUG level only when DEBUG=true is explicitly set
_log_level = logging.DEBUG if os.environ.get('DEBUG', '').lower() == 'true' else logging.INFO
logging.basicConfig(
    level=_log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console output
    ]
)
# Verbose debug for OCR/PDF services only when debug mode is active
if _log_level == logging.DEBUG:
    logging.getLogger('utils.pdf_processor').setLevel(logging.DEBUG)
    logging.getLogger('services.ocr_service').setLevel(logging.DEBUG)

# Import configuration
from config.settings import APP_NAME, VERSION, UPLOAD_FOLDER, PDF_FOLDER
from config.database import initialize_pool, close_pool, assert_schema_current

# Import repositories
from repositories.base_repository import freeze_repository_singleton as _frozen
from repositories.invoice_repository import InvoiceRepository
from repositories.audit_repository import AuditRepository
from repositories.upload_staging_repository import UploadStagingRepository
from repositories.seller_repository import SellerRepository
from repositories.seller_password_repository import SellerPasswordRepository
from repositories.clients.client_repository import ClientRepository
from repositories.services.service_repository import ServiceRepository
from repositories.services.service_category_repository import ServiceCategoryRepository
from repositories.services.service_price_history_repository import ServicePriceHistoryRepository
from repositories.employees.employee_repository import EmployeeRepository
from repositories.employees.forma_zatrudnienia_repository import FormaZatrudnieniaRepository
from repositories.absences.absence_category_repository import AbsenceCategoryRepository
from repositories.absences.absence_repository import AbsenceRepository
from repositories.absences.employee_supervisor_repository import EmployeeSupervisorRepository
from repositories.absences.absence_limit_repository import AbsenceLimitRepository
from repositories.absences.absence_adjustment_repository import AbsenceAdjustmentRepository
from repositories.absences.absence_balance_repository import AbsenceBalanceRepository

# Import services
from services.ocr_service import OCRService
from services.validation_service import ValidationService
from services.duplicate_detection_service import DuplicateDetectionService
from services.email_service import EmailService
from services.export_service import ExportService
from services.seller_service import SellerService
from services.absence_service import AbsenceService


class PostgreSQLJSONProvider(DefaultJSONProvider):
    """Custom JSON provider that handles PostgreSQL native types."""

    def default(self, obj):
        if isinstance(obj, (datetime, date, time)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


# Per-route mobile header titles (P08) live in config/page_titles.py so the
# mapping is importable in tests without the app factory / DB init.
from config.page_titles import page_title_for  # noqa: E402


def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)
    app.json_provider_class = PostgreSQLJSONProvider
    app.json = PostgreSQLJSONProvider(app)

    # Configuration
    # SECRET_KEY: required, and must be a unique high-entropy value.
    # It signs session cookies AND CSRF tokens — a known/placeholder/short key
    # lets anyone forge a superuser session, so we reject those at boot.
    _SECRET_KEY_PLACEHOLDERS = {
        'change-this-to-a-long-random-string',
        'changeme', 'change-me', 'secret', 'dev', 'development', 'test',
    }
    _SECRET_KEY_GEN_HINT = (
        'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
    )
    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key:
        raise RuntimeError(
            'SECRET_KEY environment variable is not set. ' + _SECRET_KEY_GEN_HINT
        )
    if secret_key.strip().lower() in _SECRET_KEY_PLACEHOLDERS or len(secret_key) < 32:
        raise RuntimeError(
            'SECRET_KEY is a placeholder or too short (< 32 characters). '
            'It must be a unique, high-entropy value — a known key lets anyone '
            'forge a session cookie for any user. ' + _SECRET_KEY_GEN_HINT
        )
    app.config['SECRET_KEY'] = secret_key
    app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
    app.config['PDF_FOLDER'] = str(PDF_FOLDER)

    # Session cookie hardening (defense-in-depth against CSRF + cookie theft).
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # blocks cross-site POST cookie send
    # Secure = cookie only sent over HTTPS. Flip on by setting SESSION_COOKIE_SECURE=true
    # in .env once the site is reached over the TLS edge (Cloudflare) AND the app sees
    # the https scheme (ProxyFix + nginx X-Forwarded-Proto, below). A Secure cookie over
    # plain HTTP is silently dropped and login breaks, so this stays env-gated.
    app.config['SESSION_COOKIE_SECURE'] = (
        os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    )

    # Sessions persist 30 days (sliding window — each request resets the clock),
    # so users stay logged in across browser restarts without the "remember me"
    # box. `session.permanent = True` is set on login (routes/auth/routes.py).
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
    app.config['SESSION_REFRESH_EACH_REQUEST'] = True

    # Behind a TLS-terminating reverse proxy (Cloudflare -> nginx -> gunicorn).
    # Trust ONE proxy hop's X-Forwarded-* so Flask sees the real client IP
    # (audit logs), the original https scheme (secure-cookie + external URLs),
    # and the original host. Only safe because the origin is reached solely via
    # the proxy — keep the nginx Cloudflare IP allowlist in place.
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # CSRF protection — applies to every POST/PUT/PATCH/DELETE by default.
    # Public, token-authenticated blueprints are exempted after registration.
    csrf = CSRFProtect(app)

    # Flask-Login initialization
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Musisz być zalogowany, aby uzyskać dostęp do tej strony.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        """Load user by ID for Flask-Login"""
        if user_id is None:
            return None
        try:
            from repositories.users.user_repository import UserRepository
            user_repo = UserRepository()
            user_row = user_repo.get_by_id(int(user_id))
            if user_row:
                return user_repo.row_to_user(user_row)
        except (ValueError, TypeError):
            # Invalid user_id format
            return None
        except Exception as e:
            logging.error(f"Error loading user {user_id}: {e}")
            return None
        return None

    @app.teardown_appcontext
    def close_db_connection(error):
        """Close database connection at end of request"""
        from config.database import DatabaseConnection
        DatabaseConnection.close_connection()

    # Ensure upload folders exist
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    PDF_FOLDER.mkdir(parents=True, exist_ok=True)

    # Initialize the connection pool. Schema creation is NO LONGER a boot side
    # effect (improvement #1): the schema is owned solely by the Alembic chain
    # and applied by an explicit `alembic upgrade head` deploy step. The old
    # initialize_database() call — which re-ran database/schema.sql on every
    # boot as a second, parallel schema authority — is gone. schema.sql is now
    # the baseline migration's source (alembic/versions/000_baseline_*), not a
    # competing definition.
    initialize_pool()
    atexit.register(close_pool)
    # Schema guard: refuse to boot a migrated DB that is behind head, turning a
    # silent missing-column 500 into a clear boot-time error that names the fix.
    assert_schema_current()

    # Initialize repositories (improvement #2).
    # These are SHARED singletons served by all gthread worker threads, so each
    # is frozen via freeze_repository_singleton(): stateless today, and the
    # freeze makes it impossible for any future method to add per-instance state
    # that would leak across threads/requests. Repos remain obtainable two ways
    # — current_app.<x>_repo here, or XRepository() in thread/mixin/boot contexts
    # — and both are safe because repositories never hold mutable instance state.
    # Any NEW app.*_repo singleton MUST be wrapped in _frozen() too.
    app.invoice_repo = _frozen(InvoiceRepository())
    app.audit_repo = _frozen(AuditRepository())
    app.staging_repo = _frozen(UploadStagingRepository())
    app.seller_repo = _frozen(SellerRepository())
    app.seller_password_repo = _frozen(SellerPasswordRepository())
    app.client_repo = _frozen(ClientRepository())
    app.service_repo = _frozen(ServiceRepository())
    app.service_category_repo = _frozen(ServiceCategoryRepository())
    app.service_price_history_repo = _frozen(ServicePriceHistoryRepository())
    app.employee_repo = _frozen(EmployeeRepository())
    app.forma_zatrudnienia_repo = _frozen(FormaZatrudnieniaRepository())
    app.absence_category_repo = _frozen(AbsenceCategoryRepository())
    app.absence_repo = _frozen(AbsenceRepository())
    app.supervisor_repo = _frozen(EmployeeSupervisorRepository())
    app.absence_limit_repo = _frozen(AbsenceLimitRepository())
    app.absence_adjustment_repo = _frozen(AbsenceAdjustmentRepository())
    app.absence_balance_repo = _frozen(AbsenceBalanceRepository())

    # Initialize services
    app.ocr_service = OCRService()
    app.validation_service = ValidationService()
    app.duplicate_detection = DuplicateDetectionService(app.invoice_repo)
    app.email_service = EmailService()
    app.export_service = ExportService()
    app.seller_service = SellerService(app.seller_repo, app.invoice_repo)
    app.absence_service = AbsenceService()

    # Register blueprints
    from routes.main_routes import main_bp
    from routes.api_routes import api_bp
    from routes.upload_routes import upload_bp
    from routes.auth.routes import auth_bp
    from routes.appointment_routes import appointment_bp
    from routes.employee_service_routes import employee_service_bp
    from routes.service_addon_routes import service_addon_bp
    from routes.client_preference_routes import client_preference_bp
    from routes.income_routes import income_bp
    from routes.analytics_routes import analytics_bp
    from routes.users.routes import users_bp
    from routes.roles.routes import roles_bp
    from routes.booking_routes import booking_bp
    from routes.absence_routes import absence_bp
    from routes.absence_balance_routes import absence_balance_bp
    from routes.sms_routes import sms_bp
    from routes.public_routes import public_bp
    from routes.import_routes import import_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(upload_bp, url_prefix='/api/upload')
    app.register_blueprint(auth_bp)  # Auth blueprint already has /auth prefix
    app.register_blueprint(appointment_bp, url_prefix='/api')
    app.register_blueprint(employee_service_bp, url_prefix='/api')
    app.register_blueprint(service_addon_bp, url_prefix='/api')
    app.register_blueprint(client_preference_bp, url_prefix='/api')
    app.register_blueprint(income_bp, url_prefix='/api')
    app.register_blueprint(analytics_bp, url_prefix='/api')
    app.register_blueprint(users_bp)
    app.register_blueprint(roles_bp)
    app.register_blueprint(booking_bp)
    app.register_blueprint(absence_bp)
    app.register_blueprint(absence_balance_bp)
    app.register_blueprint(sms_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(import_bp, url_prefix='/api')

    # CSRF exemptions — anonymous, non-session endpoints whose security boundary
    # is NOT a session cookie:
    #   • public_bp  — confirm/cancel/rate/visit, authenticated by an unguessable
    #                  URL token; CSRF (which protects ambient session creds) is
    #                  meaningless here, and its 1h token expiry would break SMS
    #                  links opened hours later.
    #   • booking_bp — open public booking API; no privileged session to forge.
    csrf.exempt(public_bp)
    csrf.exempt(booking_bp)

    # Error handlers
    from exceptions import AppError
    from flask import jsonify, request, flash

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        """Return a clean message on CSRF failure (JSON for API, HTML otherwise)."""
        if request.path.startswith('/api/'):
            return jsonify({'success': False,
                            'error': 'Sesja wygasła lub token bezpieczeństwa jest '
                                     'nieprawidłowy. Odśwież stronę i spróbuj ponownie.'}), 400
        from config.ui_messages import msg
        flash(msg('auth.session.expired'), 'error')
        return render_template('errors/500.html'), 400

    @app.errorhandler(AppError)
    def handle_app_error(e):
        """Auto-convert AppError subclasses to JSON for API routes, HTML otherwise."""
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': str(e)}), e.status_code
        return render_template('errors/500.html'), e.status_code

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template('errors/500.html'), 500

    # Pre-encode sidebar logo as base64 data URI (eliminates flash on navigation)
    logo_path = app.static_folder + '/Logo.png'
    try:
        with open(logo_path, 'rb') as f:
            logo_data_uri = 'data:image/png;base64,' + base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        logo_data_uri = ''

    # Context processors
    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        from flask import request as _request
        from config.auth_config import (
            get_user_module_permissions, is_supervisor, get_linked_employee,
            can_edit_service_price_history, can_send_appointment_sms
        )

        user_permissions = {}
        _is_supervisor = False
        _has_linked_employee = False
        _can_edit_price_history = False
        _can_send_sms = False

        if current_user.is_authenticated:
            try:
                user_permissions = get_user_module_permissions(current_user.role)
            except Exception:
                pass
            try:
                _can_edit_price_history = can_edit_service_price_history(current_user.role)
            except Exception:
                pass
            try:
                _can_send_sms = can_send_appointment_sms(current_user.role)
            except Exception:
                pass
            try:
                emp = get_linked_employee(current_user)
                _has_linked_employee = emp is not None
                if emp:
                    from repositories.absences.employee_supervisor_repository import EmployeeSupervisorRepository
                    _is_supervisor = EmployeeSupervisorRepository().is_supervisor(emp['id'])
            except Exception:
                pass

        # Active-tone UI message map for the JS MSG() resolver. Only the active
        # tone crosses to the browser; '<' is escaped so a string can never
        # break out of the injecting <script> tag. (Catalog: config/ui_messages.py)
        import json
        from config.ui_messages import flat_map, ACTIVE_TONE, msg as _msg
        ui_messages_json = json.dumps(flat_map(), ensure_ascii=False).replace('<', '\\u003c')

        return {
            'app_name': APP_NAME,
            'version': VERSION,
            'now': datetime.now,
            'logo_data_uri': logo_data_uri,
            'user_permissions': user_permissions,
            'is_supervisor': _is_supervisor,
            'has_linked_employee': _has_linked_employee,
            'can_edit_price_history': _can_edit_price_history,
            'can_send_sms': _can_send_sms,
            'page_title': page_title_for(getattr(_request, 'endpoint', None)),
            'ui_messages_json': ui_messages_json,
            'ui_tone': ACTIVE_TONE,
            'msg': _msg,
        }

    # P4-3/P4-4: Clean up stale upload temp files on startup
    from routes.upload_routes import cleanup_stale_uploads
    cleanup_stale_uploads(app)

    # Flip any orphaned import_logs rows (status='running') left by a previous crash
    try:
        from repositories.data_import.import_log_repository import ImportLogRepository
        with app.app_context():
            _orphan_count = ImportLogRepository().cleanup_orphans()
        if _orphan_count:
            logging.info("Flipped %d orphaned import_logs rows to 'failed'", _orphan_count)
    except Exception as _imp_err:
        logging.warning("Could not run import_logs orphan cleanup at startup: %s", _imp_err)

    # SMS auto-send background scheduler
    app.config['BASE_URL'] = os.environ.get('BASE_URL', 'http://localhost:5000')
    try:
        from scheduler import start_scheduler, stop_scheduler
        import atexit as _atexit
        start_scheduler(app)
        _atexit.register(stop_scheduler)
    except Exception as _sched_err:
        logging.warning("SMS scheduler not started: %s", _sched_err)

    # Static-asset cache busting. nginx serves /static as immutable, max-age=1y,
    # so a stable URL pins returning browsers to a stale file after a deploy —
    # e.g. adding a method to an existing JS file makes the cached copy throw
    # "X is not a function" until a manual hard-refresh. asset_url() appends
    # ?v=<content-hash> per file, so each asset's URL changes exactly when that
    # file's bytes change. Use it for every <script>/<link> in templates instead
    # of url_for('static', ...). The hash is cached per (filename, mtime): one
    # stat per render, re-hash only when the file changes (picks up dev edits
    # with no restart). Invalidates naturally on each deploy.
    import hashlib as _hashlib
    _asset_hash_cache = {}

    @app.template_global()
    def asset_url(filename):
        try:
            path = os.path.join(app.static_folder, filename)
            mtime = os.path.getmtime(path)
            cached = _asset_hash_cache.get(filename)
            if cached is None or cached[0] != mtime:
                with open(path, 'rb') as _f:
                    digest = _hashlib.sha256(_f.read()).hexdigest()[:10]
                cached = (mtime, digest)
                _asset_hash_cache[filename] = cached
            return url_for('static', filename=filename, v=cached[1])
        except OSError:
            # File missing/unreadable — fall back to an un-versioned URL rather
            # than 500 the whole page over a cache-busting nicety.
            return url_for('static', filename=filename)

    @app.template_filter('format_phone')
    def format_phone(raw):
        """Display a stored Polish phone as '48 XXX XXX XXX' (display-only).

        Mirror of the JS formatPhone() in static/js/utils.js. Stored numbers are
        the bare 11-digit '48XXXXXXXXX' form (see normalize_phone). Unrecognized
        values are returned unchanged so legacy oddities still render.
        """
        if not raw:
            return raw
        digits = ''.join(ch for ch in str(raw) if ch.isdigit())
        if len(digits) == 11 and digits.startswith('48'):
            national = digits[2:]
        elif len(digits) == 9:
            national = digits
        else:
            return raw
        return f"48 {national[0:3]} {national[3:6]} {national[6:9]}"

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=8083)
