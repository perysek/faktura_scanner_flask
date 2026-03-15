"""
FakturaScanner - Flask Web Application
Main Flask application with Jinja templates, TailwindCSS, and JavaScript
"""
import base64
import logging
import os
from datetime import datetime, date, time
from decimal import Decimal
from flask.json.provider import DefaultJSONProvider

from dotenv import load_dotenv
load_dotenv()  # Loads .env file from project root (Vultr/local deployment)

from flask import Flask, render_template
from flask_login import LoginManager

# Configure logging — DEBUG only in development, INFO in production
_log_level = logging.DEBUG if os.environ.get('FLASK_ENV') == 'development' else logging.INFO
logging.basicConfig(
    level=_log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console output
    ]
)
# Verbose debug for core services only in development
if _log_level == logging.DEBUG:
    logging.getLogger('utils.pdf_processor').setLevel(logging.DEBUG)
    logging.getLogger('services.ocr_service').setLevel(logging.DEBUG)

# Import configuration
from config.settings import APP_NAME, VERSION, UPLOAD_FOLDER, PDF_FOLDER
from config.database import initialize_database

# Import repositories
from repositories.invoice_repository import InvoiceRepository
from repositories.audit_repository import AuditRepository
from repositories.upload_staging_repository import UploadStagingRepository
from repositories.seller_repository import SellerRepository
from repositories.clients.client_repository import ClientRepository
from repositories.services.service_repository import ServiceRepository
from repositories.employees.employee_repository import EmployeeRepository
from repositories.employees.forma_zatrudnienia_repository import FormaZatrudnieniaRepository

# Import services
from services.ocr_service import OCRService
from services.validation_service import ValidationService
from services.duplicate_detection_service import DuplicateDetectionService
from services.email_service import EmailService
from services.export_service import ExportService
from services.seller_service import SellerService


class PostgreSQLJSONProvider(DefaultJSONProvider):
    """Custom JSON provider that handles PostgreSQL native types."""

    def default(self, obj):
        if isinstance(obj, (datetime, date, time)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)
    app.json_provider_class = PostgreSQLJSONProvider
    app.json = PostgreSQLJSONProvider(app)

    # Configuration
    # SECRET_KEY: required in production, fallback only for development
    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key and os.environ.get('FLASK_ENV') != 'development':
        raise ValueError('SECRET_KEY environment variable must be set in production')
    app.config['SECRET_KEY'] = secret_key or 'dev-only-insecure-key'
    app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
    app.config['PDF_FOLDER'] = str(PDF_FOLDER)

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

    # Initialize database
    initialize_database()

    # Initialize repositories
    app.invoice_repo = InvoiceRepository()
    app.audit_repo = AuditRepository()
    app.staging_repo = UploadStagingRepository()
    app.seller_repo = SellerRepository()
    app.client_repo = ClientRepository()
    app.service_repo = ServiceRepository()
    app.employee_repo = EmployeeRepository()
    app.forma_zatrudnienia_repo = FormaZatrudnieniaRepository()

    # Initialize services
    app.ocr_service = OCRService()
    app.validation_service = ValidationService()
    app.duplicate_detection = DuplicateDetectionService(app.invoice_repo)
    app.email_service = EmailService()
    app.export_service = ExportService()
    app.seller_service = SellerService(app.seller_repo, app.invoice_repo)

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

    # Error handlers
    from exceptions import AppError
    from flask import jsonify, request

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
        from config.auth_config import get_user_module_permissions

        user_permissions = {}
        if current_user.is_authenticated:
            try:
                user_permissions = get_user_module_permissions(current_user.role)
            except Exception:
                pass

        return {
            'app_name': APP_NAME,
            'version': VERSION,
            'now': datetime.now,
            'logo_data_uri': logo_data_uri,
            'user_permissions': user_permissions,
        }

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=8083)
