<<<<<<< HEAD
import os, requests, psycopg2
=======
import os, requests
>>>>>>> 8b9d1e52343fc0843edd1cadf69f2ddd0d9f2af5
from app import app, db, login_manager
from flask import render_template, request, redirect, url_for, flash, jsonify, request
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.utils import secure_filename
<<<<<<< HEAD
from app.models import UserProfile, Icao
from app.forms import LoginForm
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
=======
from app.models import UserProfile
from app.forms import LoginForm
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

>>>>>>> 8b9d1e52343fc0843edd1cadf69f2ddd0d9f2af5


###
# Routing for your application.
###

@app.route('/')
@login_required
def home():
    """Render website's home page."""
    conn = psycopg2.connect(
        host="localhost",
        database="FlightOptimizer",
        user=os.environ.get('DATABASE_USERNAME', 'postgres'),
        password= os.environ.get('DATABASE_PASSWORD')
    )    
    cur = conn.cursor()

    # Queries the Icao model from models.py to check for table population. If empty, populate.
    if Icao.query.first() is None:
        with open("C:/Users/jastw/Desktop/Labs/Capstone/flightoptimizer/FlaskApp/app/icao_query.sql", "r", encoding="utf-8") as file:
            cur.execute(file.read())
            db.session.commit()
    
    # Query to get all ICAO codes
    cur.execute("SELECT * FROM icao_codes")
    rows = cur.fetchall()

    region_names = [row[0] for row in rows]
    icao_codes = [row[1] for row in rows]
    airports = [row[2] for row in rows]

    return render_template('home.html', icao_codes=icao_codes, region_names=region_names, airports=airports)


@app.route('/about/')
def about():
    """Render the website's about page."""
    return render_template('about.html', name="Mary Jane")

# This needs to be here. Without it, the endpoint /weather/<icao> cannot exist
@app.route('/weather/')
def weather():
    return redirect(url_for('home'))

@app.route('/weather/<icao>', methods=['GET'])
def airport_weather(icao):
    api_key = 'a741a79a6d7246f8a3e0364dc8' # Replace with your actual API key
    url = f'https://api.checkwx.com/metar/{icao}/nearest/decoded'
    headers = {'X-API-Key': api_key}

    response = requests.request("GET", url, headers={'X-API-Key': api_key})
    data = response.json()["data"][0]

    temperature_data = data["temperature"]
    degsC = temperature_data["celsius"]
    degsF = temperature_data["fahrenheit"]

    wind_data=data["wind"]
    speedKPH = wind_data["speed_kph"]
    speedMPH = wind_data["speed_mph"]

    conditions = data["clouds"][0]
    forecast_desc = conditions["text"]
    
    icao = data["icao"]
    humidity = data["humidity"]["percent"]

    return render_template('weather.html', degsC=degsC, degsF=degsF, speedKPH=speedKPH, speedMPH=speedMPH, icao=icao, humidity=humidity,
                           forecast_desc=forecast_desc)

@app.route('/login', methods=['POST', 'GET'])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        # Get the username and password values from the form.
        res = request.form
        formUsername = res['username']
        formPassword = res['password']

        user =  UserProfile.query.filter_by(username = formUsername)

        #Try catch in the event of incorrect username
        try:
            if check_password_hash(user[0].password, formPassword):
                # Gets user id, load into session
                login_user(user[0])
                # Remember to flash a message to the user
                return redirect(url_for("home"))  
            else:
                flash("Incorrect password","error")
        except IndexError:
            flash("User not found", "error")
            return redirect(url_for('login'))

    return render_template("login.html", form=form)

# user_loader callback. This callback is used to reload the user object from
# the user ID stored in the session
@login_manager.user_loader
def load_user(id):
    return db.session.execute(db.select(UserProfile).filter_by(id=id)).scalar()

###
# The functions below should be applicable to all Flask apps.
###

# Flash errors from the form if validation fails
def flash_errors(form):
    for field, errors in form.errors.items():
        for error in errors:
            flash(u"Error in the %s field - %s" % (
                getattr(form, field).label.text,
                error
), 'danger')

@app.route('/<file_name>.txt')
def send_text_file(file_name):
    """Send your static text file."""
    file_dot_text = file_name + '.txt'
    return app.send_static_file(file_dot_text)


@app.after_request
def add_header(response):
    """
    Add headers to both force latest IE rendering engine or Chrome Frame,
    and also to cache the rendered page for 10 minutes.
    """
    response.headers['X-UA-Compatible'] = 'IE=Edge,chrome=1'
    response.headers['Cache-Control'] = 'public, max-age=0'
    return response


@app.errorhandler(404)
def page_not_found(error):
    """Custom 404 page."""
    return render_template('404.html'), 404

@app.route('/logout')
def logout():
    logout_user()
    flash("You are now logged out")
    return redirect(url_for('home'))