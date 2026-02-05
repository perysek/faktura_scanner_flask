"""
FakturaScanner - Flask Web Application
Main Flask application with Jinja templates, TailwindCSS, and JavaScript
"""
import logging
import os
from datetime import datetime

from flask import Flask, render_template
from flask_login import LoginManager

# Configure logging for debugging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console output
    ]
)
# Set specific loggers to appropriate levels
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

# Import services
from services.ocr_service import OCRService
from services.validation_service import ValidationService
from services.duplicate_detection_service import DuplicateDetectionService
from services.email_service import EmailService
from services.export_service import ExportService
from services.seller_service import SellerService


def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)

    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production-flask-login-session-key-2026')
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
        from repositories.users.user_repository import UserRepository
        user_repo = UserRepository()
        user_row = user_repo.get_by_id(int(user_id))
        if user_row:
            return user_repo.row_to_user(user_row)
        return None

    # Ensure upload folders exist
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    PDF_FOLDER.mkdir(parents=True, exist_ok=True)

    # Initialize database
    initialize_database()

    # Initialize repositories
    from config.database import get_database_path
    app.invoice_repo = InvoiceRepository()
    app.audit_repo = AuditRepository()
    app.staging_repo = UploadStagingRepository(db_path=get_database_path())
    app.seller_repo = SellerRepository()

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

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(upload_bp, url_prefix='/api/upload')
    app.register_blueprint(auth_bp)  # Auth blueprint already has /auth prefix

    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template('errors/500.html'), 500

    # Context processors
    @app.context_processor
    def inject_globals():
        return {
            'app_name': APP_NAME,
            'version': VERSION,
            'now': datetime.now
        }

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=8083)
