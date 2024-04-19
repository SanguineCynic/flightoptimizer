import os, requests, psycopg2
from amadeus import Client, ResponseError

from app import app, db, login_manager
from flask import render_template, request, redirect, url_for, flash, jsonify, request
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.utils import secure_filename
from app.models import UserProfile, Icao, Airport
from app.forms import LoginForm
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
# from amadeus import Client, ResponseError


###
# Routing for your application.
###

@app.route('/')
@login_required
def home():
    """Render website's home page."""
    conn, cur = get_db_connection()

    # Queries the Icao model from models.py to check for table population. If empty, populate.
    if Icao.query.first() is None:
        with open(os.getcwd()+"\\app\\static\\sql\\icao_query.sql", "r", encoding="utf-8") as file:
            cur.execute(file.read())
            conn.commit()
    
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
@login_required
def airport_weather(icao):
    api_key = os.environ.get('CX_WEATHER_API_KEY') 
    url = f'https://api.checkwx.com/metar/{icao}/nearest/decoded'
    headers = {'X-API-Key': api_key}

    taf_data = fetch_taf_data(icao)
    sigmet_data = fetch_sigmet_data(icao)
    taf_impacts = analyze_taf_fuel_impact(taf_data)
    sigmet_impacts = analyze_sigmet_fuel_impact(sigmet_data)

    response = requests.request("GET", url, headers={'X-API-Key': api_key})
    data = response.json()["data"][0]

    temperature_data = data["temperature"]
    degsC = temperature_data["celsius"]
    degsF = temperature_data["fahrenheit"]

    try:
        wind_data=data["wind"]
        speedKPH = wind_data["speed_kph"]
        speedMPH = wind_data["speed_mph"]
    except KeyError:
        speedKPH = "Not Reported "
        speedMPH = "Not Reported "

    conditions = data["clouds"][0]
    forecast_desc = conditions["text"]
    
    humidity = data["humidity"]["percent"]

    return render_template('weather.html', degsC=degsC, degsF=degsF, speedKPH=speedKPH, speedMPH=speedMPH, icao=icao, humidity=humidity,
                           forecast_desc=forecast_desc, taf_impacts=taf_impacts, sigmet_impacts=sigmet_impacts)

@app.route('/flights/')
@login_required
def flights():
    conn, cur = get_db_connection()

    # Queries the Airport model from models.py to check for table population. If empty, populate.
    if Airport.query.first() is None:
        print("Populating table...")
        with open(os.getcwd()+"\\app\\static\\sql\\load_airports.sql", "r", encoding="utf-8") as file:
            print("SQL file found.")
            cur.execute(file.read())
            conn.commit()
            print("Table populated.")
    
    cur.execute("SELECT * FROM airports")
    rows = cur.fetchall()

    cities = [row[0] for row in rows]
    countries = [row[1] for row in rows]
    iata = [row[2] for row in rows]
    continent = [row[3] for row in rows]
    print(len(cities))

    return render_template('flights.html', cities=cities, countries=countries,iata=iata,continent=continent)

@app.route('/flights/<dest>', methods=['GET'])
@login_required
def flights_to_dest(dest):
    rockMe = Client(
    client_id=os.environ.get('AMADEUS_CLIENT_ID'),
    client_secret=os.environ.get('AMADEUS_CLIENT_SECRET')
)
    
    try:
        # Use the destination as the origin for the flight search
        response = rockMe.shopping.flight_destinations.get(
            origin=dest,
            departureDate='2024-04-14'
        )
        return jsonify(response.data)
    except ResponseError as error:
        return jsonify({"error": str(error)})
    
# @app.route("/flights/", methods=['GET'])
# def flights():
#     con, cursor = get_db_connection()
#     cursor.execute("SELECT planemodel, source, destination, source_icao, destination_icao FROM flights")
#     flights = cursor.fetchall()
#     print(flights)
#     return render_template("flights.html", flights=flights)


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

# Database connection setup
def get_db_connection():
    conn = psycopg2.connect(
        host="localhost",
        database="FlightOptimizer",
        user=os.environ.get('DATABASE_USERNAME', 'postgres'),
        password= os.environ.get('DATABASE_PASSWORD')
    )    
    cur = conn.cursor()    
    return conn, cur

# Helper functions for SIGMET and TAF weather advisories
def fetch_data(url, headers):
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch data: {response.status_code} {response.text}")
        return None

def fetch_taf_data(icao):
    taf_base_url = 'https://api.checkwx.com/taf/'
    url = f"{taf_base_url}{icao}/decoded"
    api_key = os.environ.get('CX_WEATHER_API_KEY') 
    headers = {'X-API-Key': api_key}
    return fetch_data(url, headers)

def fetch_sigmet_data(icao):
    sigmet_base_url = 'https://api.checkwx.com/sigmet/'
    url = f"{sigmet_base_url}{icao}/decoded"
    api_key = os.environ.get('CX_WEATHER_API_KEY')
    headers = {'X-API-Key': api_key}
    return fetch_data(url, headers)

def analyze_taf_fuel_impact(taf_data):
    impacts = []
    if taf_data and 'data' in taf_data:
        for report in taf_data['data']:
            icao = report.get('icao', 'Unknown')
            for forecast in report.get('forecast', []):
                period = f"From {forecast['timestamp']['from']} to {forecast['timestamp']['to']}"
                conditions_described = ', '.join(c['text'] for c in forecast.get('conditions', []))
                wind_speed = forecast.get('wind', {}).get('speed_kts', 0)
                impact_desc = f"{conditions_described}. High winds might increase fuel if wind speed > 20 kts ({wind_speed} kts)."

                # Include visibility and significant weather conditions like snow, ice, or fog
                if 'visibility' in forecast and forecast['visibility']['miles_float'] < 1:
                    impact_desc += " Low visibility could lead to delays and increased fuel usage."
                if any('snow' in c['text'].lower() or 'ice' in c['text'].lower() or 'fog' in c['text'].lower() for c in forecast.get('conditions', [])):
                    impact_desc += " Conditions like snow, ice, or fog may require de-icing and can cause delays, increasing fuel usage."

                # Check for rain and its operational implications
                if any('rain' in c['text'].lower() for c in forecast.get('conditions', [])):
                    impact_desc += " Rain may lead to increased braking distances and reduced runway friction, potentially affecting fuel usage due to longer taxi and rollout times."

                # Check for thunderstorms and turbulence for additional flight considerations
                if any('thunderstorm' in c['text'].lower() for c in forecast.get('conditions', [])):
                    impact_desc += " Thunderstorms may necessitate significant rerouting."
                if any('turbulence' in c['text'].lower() for c in forecast.get('conditions', [])):
                    impact_desc += " Turbulence could lead to operational adjustments and potential fuel inefficiencies."

                # Append the formatted string to impacts list
                impacts.append({
                    'icao': icao,
                    'period': period,
                    'description': impact_desc
                })
    return impacts

def analyze_sigmet_fuel_impact(sigmet_data):
    impacts = []
    if sigmet_data and 'data' in sigmet_data:
        for entry in sigmet_data['data']:
            icao = entry.get('icao', 'Unknown')
            hazard_type = entry.get('hazard', {}).get('type', {}).get('text', 'Unknown')
            description = f"Hazard type: {hazard_type}. "
            if 'Thunderstorm' in hazard_type:
                description += "Potential rerouting increases fuel."
            elif 'Volcanic ash' in hazard_type:
                description += "Avoidance increases fuel usage."
            # ... more conditions if necessary

            impacts.append({
                'icao': icao,
                'description': description
            })
        if not impacts:
            impacts.append({
            'icao': 'N/A',
            'period': 'N/A',
            'description': 'No significant SIGMET advisories affecting fuel emissions.'
        })
    return impacts