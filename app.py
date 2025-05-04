import os
from flask import Flask
from src.routes.survey import survey_bp
from src.routes.internal_qc.single_station import single_station_bp
from src.routes.internal_qc.multi_station import multi_station_bp
from src.routes.comparison_qc.comparison import comparison_qc_bp
from src.routes.internal_qc.measurement import measurement_bp
from src.routes.toolcode import toolcode_bp
from src.routes.recommendations import recommendations_bp
from src.routes.synthetic_data import synthetic_data_bp, parse_bp
from src.routes.corrections.corrections import corrections_bp


def create_app(config_name=None):
    app = Flask(__name__)
    
    # Configure the app using environment variables
    app.config['DEBUG'] = os.environ.get('DEBUG', 'False').lower() == 'true'
    app.config['TESTING'] = os.environ.get('TESTING', 'False').lower() == 'true'
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'hard-to-guess-key'
    
    # Add any additional configuration parameters as needed
    
    # Register basic blueprints
    app.register_blueprint(survey_bp, url_prefix='/api/v1/survey')
    app.register_blueprint(single_station_bp, url_prefix='/api/v1/qc/single-station')
    app.register_blueprint(multi_station_bp, url_prefix='/api/v1/qc/multi-station')
    app.register_blueprint(toolcode_bp, url_prefix='/api/v1/toolcode')
    app.register_blueprint(measurement_bp, url_prefix='/api/v1/qc/measurement')  # Add this line
    
    # Register comparison QC blueprint
    app.register_blueprint(comparison_qc_bp, url_prefix='/api/v1/qc/comparison')
    
    # Register recommendations blueprint
    app.register_blueprint(recommendations_bp, url_prefix='/api/v1/recommendations')
    
    # Register synthetic data blueprint
    app.register_blueprint(synthetic_data_bp, url_prefix='/api/v1/synthetic-data')
    
    # Register parse blueprint
    app.register_blueprint(parse_bp, url_prefix='/api/v1/parse')

    # Register corrections blueprint
    app.register_blueprint(corrections_bp, url_prefix='/api/v1/corrections')  

    
    @app.route('/healthz', methods=['GET'])
    def health_check():
        return {'status': 'healthy'}, 200
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))