from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from .config import Config
from flask_migrate import Migrate
import os, psycopg2
# from app.models import Icao

app = Flask(__name__)
app.config.from_object(Config)
app.config['SECRET_KEY'] = 'your_secret_key_here'

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Flask-Login login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

from app import views

conn = psycopg2.connect(
    host="localhost",
    database="flightoptimizer",
    user=os.environ.get('DATABASE_USERNAME', 'postgres'),
    password= os.environ.get('DATABASE_PASSWORD')
)

cur = conn.cursor()

cur.execute("""
    CREATE TABLE IF NOT EXISTS flights (
        flightid SERIAL PRIMARY KEY,
        planemodel VARCHAR(255) NOT NULL
        );
""")

cur.execute("""
    CREATE TABLE IF NOT EXISTS icao_codes(
        region_name VARCHAR(255),
        icao VARCHAR(5),
        airport VARCHAR(255)
    );
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS airports (
    city VARCHAR(255),
    country VARCHAR(255),
    iata_code VARCHAR(4) PRIMARY KEY,
    continent VARCHAR(255)
);""")


# cur.execute("""
# -- Reports tabLe
# CREATE TABLE IF NOT EXISTS Reports (
#     ReportID INT AUTO_INCREMENT PRIMARY KEY,
#     AdminID INT NOT NULL,
#     CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#     FOREIGN KEY (AdminID) REFERENCES AdminAccounts(AdminID)
# );

# -- Fuel emissions report table
# CREATE TABLE IF NOT EXISTS FuelEmissions (
#     EmissionID INT AUTO_INCREMENT PRIMARY KEY,
#     ReportID INT NOT NULL,
#     AirportID INT NOT NULL,
#     EmissionDate DATE NOT NULL,
#     FuelType VARCHAR(50) NOT NULL,
#     EmissionAmount DECIMAL(10,2) NOT NULL, -- Assuming emissions are recorded in some unit of measurement
#     Status VARCHAR(50) NOT NULL,
#     FOREIGN KEY (ReportID) REFERENCES Reports(ReportID),
#     FOREIGN KEY (AirportID) REFERENCES Airports(AirportID)
# );

# -- Emission anomalies table
# CREATE TABLE IF NOT EXISTS EmissionAnomalies (
#     AnomalyID INT AUTO_INCREMENT PRIMARY KEY,
#     EmissionID INT NOT NULL,
#     AnomalyType VARCHAR(255) NOT NULL,
#     AnomalyStatus VARCHAR(50) NOT NULL,
#     FOREIGN KEY (EmissionID) REFERENCES FuelEmissions(EmissionID)
# );
# """)

conn.commit()

cur.close() 
conn.close()
