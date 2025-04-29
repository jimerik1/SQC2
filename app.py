import os
from flask import Flask
from src.routes.survey import survey_bp
from src.routes.internal_qc.single_station import single_station_bp
from src.routes.internal_qc.multi_station import multi_station_bp
from src.routes.external_qc.comparison import external_qc_bp
from src.routes.internal_qc.measurement import measurement_bp
from src.routes.toolcode import toolcode_bp

def create_app(config_name=None):
    app = Flask(__name__)
    
    # Configure the app using environment variables
    app.config['DEBUG'] = os.environ.get('DEBUG', 'False').lower() == 'true'
    app.config['TESTING'] = os.environ.get('TESTING', 'False').lower() == 'true'
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'hard-to-guess-key'
    
    # Add any additional configuration parameters as needed
    
    # Register basic blueprints
    app.register_blueprint(survey_bp, url_prefix='/api/v1/survey')
    app.register_blueprint(single_station_bp, url_prefix='/api/v1/qc/internal/single-station')
    app.register_blueprint(multi_station_bp, url_prefix='/api/v1/qc/internal/multi-station')
    app.register_blueprint(toolcode_bp, url_prefix='/api/v1/toolcode')
    app.register_blueprint(measurement_bp, url_prefix='/api/v1/qc/measurement')  # Add this line
    
    # Register  external QC blueprint
    app.register_blueprint(external_qc_bp, url_prefix='/api/v1/qc/external')

    
    @app.route('/healthz', methods=['GET'])
    def health_check():
        return {'status': 'healthy'}, 200
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))