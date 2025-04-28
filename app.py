from flask import Flask
from blueprints.survey import survey_bp
from blueprints.qc.single_station import single_station_bp
from blueprints.qc.multi_station import multi_station_bp
from blueprints.qc.other import other_qc_bp
from blueprints.toolcode import toolcode_bp
import config

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config.config[config_name])
    
    # Register blueprints
    app.register_blueprint(survey_bp, url_prefix='/api/v1/survey')
    app.register_blueprint(single_station_bp, url_prefix='/api/v1/qc/single-station')
    app.register_blueprint(multi_station_bp, url_prefix='/api/v1/qc/multi-station')
    app.register_blueprint(other_qc_bp, url_prefix='/api/v1/qc/other')
    app.register_blueprint(toolcode_bp, url_prefix='/api/v1/toolcode')
    
    @app.route('/health', methods=['GET'])
    def health_check():
        return {'status': 'healthy'}, 200
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)