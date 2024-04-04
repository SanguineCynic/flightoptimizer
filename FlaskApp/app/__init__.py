from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from .config import Config
from flask_migrate import Migrate
<<<<<<< HEAD
import os, psycopg2
# from app.models import Icao
=======
import os
import psycopg2
>>>>>>> 8b9d1e52343fc0843edd1cadf69f2ddd0d9f2af5

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
    database="FlightOptimizer",
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

conn.commit()

<<<<<<< HEAD
cur.close() 
=======
cur.close()
>>>>>>> 8b9d1e52343fc0843edd1cadf69f2ddd0d9f2af5
conn.close()
