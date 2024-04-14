from . import db
from werkzeug.security import generate_password_hash

class UserProfile(db.Model):
    # You can use this to change the table name. The default convention is to use
    # the class name. In this case a class name of UserProfile would create a
    # user_profile (singular) table, but if we specify __tablename__ we can change it
    # to `user_profiles` (plural) or some other name.
    __tablename__ = 'user_profiles'

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80))
    last_name = db.Column(db.String(80))
    username = db.Column(db.String(80), unique=True)
    password = db.Column(db.String(128))

    def __init__(self, first_name, last_name, username, password):
        self.first_name = first_name
        self.last_name = last_name
        self.username = username
        self.password = generate_password_hash(password, method='pbkdf2:sha256')

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        try:
            return unicode(self.id)  # python 2 support
        except NameError:
            return str(self.id)  # python 3 support

    def __repr__(self):
        return '<User %r>' % (self.username)
    
class Icao(db.Model):
    __tablename__ = "icao_codes"

    region_name = db.Column(db.String(255))
    icao = db.Column(db.String(5), primary_key=True)
    airport = db.Column(db.String(255))

    def __init__(self,region_name,icao,airport):
        self.region_name = region_name
        self.icao=icao
        self.airport=airport 

class Airport(db.Model):
    __tablename__ = "airports"

    city = db.Column(db.String(255))
    country = db.Column(db.String(255))
    iata_code = db.Column(db.String(4), primary_key=True)
    continent = db.Column(db.String(255))

    def __init__(self,city, country, iata_code, continent):
        self.city = city
        self.country = country
        self.iata_code=iata_code
        self.continent=continent 
