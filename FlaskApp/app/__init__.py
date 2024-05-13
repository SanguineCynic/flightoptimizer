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

conn.commit()

cur.close() 
conn.close()
