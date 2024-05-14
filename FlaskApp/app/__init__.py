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
cur.execute("""
    CREATE TABLE IF NOT EXISTS countries (
        code CHAR(3) PRIMARY KEY,
        name TEXT NOT NULL
    );
""")
cur.execute("""
    CREATE TABLE IF NOT EXISTS aircraft_data (
    model TEXT,
    icao_code TEXT PRIMARY KEY,
    iata_code TEXT,
    avg_seats NUMERIC,
    avg_sector_km NUMERIC,
    avg_fuel_burn_kg_km NUMERIC,
    avg_fuel_per_seat_l_100km NUMERIC
);
""")
cur.execute("""
    CREATE TABLE IF NOT EXISTS iata_to_icao (
        country_code VARCHAR(4),
        region_name VARCHAR(60),
        iata VARCHAR(4),
        icao VARCHAR(5),
        airport VARCHAR(60),
        latitude NUMERIC,
        longitude NUMERIC
    )
""")

conn.commit()

cur.close() 
conn.close()
