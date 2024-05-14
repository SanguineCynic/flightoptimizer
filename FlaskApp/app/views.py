# Generic python packages
import os, requests, psycopg2, json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# Flask imports
from app import app, db, login_manager
from flask import render_template, request, redirect, url_for, flash, jsonify, request
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.utils import secure_filename
from app.models import UserProfile, Icao, Airport
from app.forms import LoginForm, FuelPredictionForm, EmissionForm, EmissionRankingForm, FuelBurnForm
from werkzeug.security import check_password_hash, generate_password_hash

# Amadeus for live flight data
from amadeus import Client, ResponseError

# AI model for fuel emissions predictions
import pickle
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder
from functools import lru_cache

###
# Routing for your application.
###

@app.route('/')
@login_required
def home():
    if is_admin(current_user.username) or is_atc(current_user.username):
        """This is actually the ICAO selection page for the weather report"""
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
    else:
        flash('Must be an ATC to access this page', 'warning')
        return redirect('dashboard')

@app.route('/dashboard')
@login_required
def dashboard():
    # For RBAC dynamic dashboard
    username = current_user.username
    user_role = UserProfile.query.filter_by(username=username).first().role

    return render_template('dashboard.html', user_role=user_role)

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
    if is_admin(current_user.username) or is_atc(current_user.username):
        api_key = os.environ.get('CX_WEATHER_API_KEY') 
        url = f'https://api.checkwx.com/metar/{icao}/nearest/decoded'

        taf_data = fetch_taf_data(icao)
        sigmet_data = fetch_sigmet_data(icao)
        taf_impacts = analyze_taf_fuel_impact(taf_data)
        sigmet_impacts = analyze_sigmet_fuel_impact(sigmet_data)

        response = requests.request("GET", url, headers={'X-API-Key': api_key})
        try:
            data = response.json()["data"][0]
        except IndexError:
            flash('Incorrect ICAO code', 'warning')
            return redirect(url_for('home'))

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
    else:
        flash('Must be ATC to access this page','warning')
        return redirect('dashboard')
    
@app.route('/flights/')
@login_required
def flights():
    if not(is_admin(current_user.username)):
        flash('Must be system administrator to access this page','warning')
        return redirect('dashboard')
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

@app.route('/flights/<src>/<dest>/<date>', methods=['GET'])
@login_required
def flights_to_dest(src, dest, date):
    if not(is_admin(current_user.username)):
        flash('Must be system administrator to access this page','warning')
        return redirect('dashboard')
    rockMe = Client(
        client_id=os.environ.get("AMADEUS_CLIENT_ID"),
        client_secret=os.environ.get("AMADEUS_API_KEY")
    )
    
    try:
        # Format the date as 'YYYY-MM-DD'
        formatted_date = date

        response = rockMe.shopping.flight_offers_search.get(
                    originLocationCode=src, 
                    destinationLocationCode=dest, 
                    departureDate=formatted_date,
                    adults=1)
        
        flights_info=[]
        for itinerary in response.data:
            flights_info.append(itinerary)

        # Initialize lists to hold the extracted data
        segment_counts = []
        departure_iata_codes = []
        arrival_iata_codes = []
        carrier_aircraft_pairs = []

        # Iterate through each flight offer
        for flight_offer in flights_info:
            
            # Iterate through each itinerary
            for itinerary in flight_offer["itineraries"]:
                # Extract the number of segments
                segment_count = len(itinerary["segments"])
                segment_counts.append(segment_count)
                
                # Extract departure and arrival iata codes
                departure_iata_code = itinerary["segments"][0]["departure"]["iataCode"]
                arrival_iata_code = itinerary["segments"][0]["arrival"]["iataCode"]
                departure_iata_codes.append(departure_iata_code)
                arrival_iata_codes.append(arrival_iata_code)
                
                # Pair up carrier and aircraft codes
                carrier_code = itinerary["segments"][0]["carrierCode"]
                aircraft_code = itinerary["segments"][0]["aircraft"]["code"]
                carrier_aircraft_pairs.append((carrier_code, aircraft_code))

        # Convert lists to tuples for easier manipulation
        segment_counts = tuple(segment_counts)
        departure_iata_codes = tuple(departure_iata_codes)
        arrival_iata_codes = tuple(arrival_iata_codes)
        carrier_aircraft_pairs = tuple(carrier_aircraft_pairs)

        # Now you have the data organized as requested
        print("Segment Counts:", segment_counts, " ", len(segment_counts))
        print("Departure IATA Codes:", departure_iata_codes, " ", len(departure_iata_codes))
        print("Arrival IATA Codes:", arrival_iata_codes, " ", len(arrival_iata_codes))
        print("Carrier-Aircraft Pairs:", carrier_aircraft_pairs, " ", len(carrier_aircraft_pairs))
        
        # Render the template with the data
        return render_template('specify_flights.html', segment_counts=segment_counts, departure_iata_codes=departure_iata_codes, arrival_iata_codes=arrival_iata_codes, carrier_aircraft_pairs=carrier_aircraft_pairs, len=len(arrival_iata_codes))
    except ResponseError as error:
        return render_template('error.html', error=str(error)), 500
    

@app.route('/prediction/', methods=['GET', 'POST'])
def fuelPrediction():
    if is_admin(current_user.username):
        # Load your model and scaler
        fuel_Pred_Model = pickle.load(open("fuel_Pred_Model.pkl", "rb"))
        scaler = pickle.load(open("scaler.pkl", "rb")) 
        # Load the LabelEncoder for categorical columns
        label_encoder = LabelEncoder()
        prediction = None  # Initialize prediction and average emissions per flight
        formatted_prediction = None
        average_emissions_per_flight = None
        calcform = FuelBurnForm()
        conn, cur = get_db_connection()
        if calcform.validate_on_submit():
            icao_code = calcform.icao_code.data.upper()
            distance = calcform.distance.data

            cur.execute(f"SELECT avg_fuel_burn_kg_km FROM aircraft_data WHERE icao_code = \'{icao_code}\'")

            aircraft = cur.fetchone()
            print(aircraft)
            if aircraft:
                avg_fuel_burn_kg_km = aircraft[0]
                estimated_fuel = float(distance * avg_fuel_burn_kg_km)*1.07
                flash(f'Estimated fuel burn for {distance} km: {estimated_fuel:.2f} kg', 'success')
            else:
                flash('Aircraft ICAO code not found in the database.', 'danger')

            return redirect(url_for('fuelPrediction'))
        predform = FuelPredictionForm()
        if predform.validate_on_submit():
            # Collect features from the form
            airline_iata = predform.airline_iata.data.upper()
            acft_icao = predform.acft_icao.data.upper()
            seats = float(predform.seats.data)
            n_flights = float(predform.n_flights.data)
            n = float(predform.n_flights.data)
            # iata_departure = form.iata_departure.data.upper()
            # iata_arrival = form.iata_arrival.data.upper()

            icao_departure = predform.icao_departure.data.upper()
            icao_arrival = predform.icao_arrival.data.upper() 

            fuel_burn_seymour = float(predform.fuel_burn_seymour.data)

            # Get the distance between the departure and arrival airports
            if len(icao_arrival) != len(icao_departure):
                flash('Please use either a pair of IATA or a pair of ICAO codes')
                return redirect('fuelPrediction')
            if len(icao_arrival) == 4:
                # ICAO code
                distance_km = get_distance(icao_departure, icao_arrival)
            else:
                # IATA code
                cur.execute(f"SELECT icao from iata_to_icao where iata=\'{icao_arrival}\'")
                icao_arrival = cur.fetchone()[0]
                cur.execute(f"SELECT icao from iata_to_icao where iata=\'{icao_departure}\'")
                icao_departure = cur.fetchone()[0]
                distance_km = get_distance(icao_departure, icao_arrival)

            if distance_km is None:
                flash('Failed to calculate distance. Check the IATA/ICAO codes.', 'error')
                return render_template('fuelPrediction.html', predform=predform, calcform=calcform)
            
            print('calculated distance ', distance_km)
            # Calculate RPK using the seats, distance, and IATA average load factor
            rpk = seats * distance_km * 0.824
            print('calculated rpk ', rpk)

            # Calculate total fuel burn using the number of flights and fuel burn per flight
            fuel_burn = fuel_burn_seymour * n_flights
            print('calculated fuel_burn ', fuel_burn)

            # Prepare data for model
            data = np.array([airline_iata, acft_icao])  # Categorical data
            # data = np.array([airline_iata, acft_icao, iata_departure, iata_arrival])  # Categorical data
            numerical_data = np.array([seats, n_flights, distance_km, rpk,fuel_burn_seymour, fuel_burn])  # Numerical data

            # Encode categorical data
            data_encoded = np.array([label_encoder.fit_transform([feature])[0] for feature in data])

            # Combine and reshape data for scaling
            features = np.concatenate((data_encoded, numerical_data)).reshape(1, -1)
            features_scaled = scaler.transform(features)
            # Make prediction
            prediction = fuel_Pred_Model.predict(features_scaled)
            print('prediction', prediction)
            print('n', n)
            average_emissions_per_flight = prediction[0] / n if n > 0 else 0

            formatted_prediction = "{:,.2f}".format(prediction[0])  # Format the prediction to two decimal places and comma-separated
            average_emissions_per_flight = "{:,.2f}".format(average_emissions_per_flight)
        
        return render_template('fuelPrediction.html', predform=predform, calcform=calcform, prediction=formatted_prediction, average_emissions_per_flight=average_emissions_per_flight)
    else:
        flash('Must be a sytem administrator to access this page','warning')
        return redirect('dashboard')
    

@app.route('/emissions-report/', methods=['GET', 'POST'])
def generateReport():
    if not (is_admin(current_user.username) or is_regulator(current_user.username)):
        flash('Must be a system administrator or regulatory authority to access this page','warning')
        return redirect('dashboard')
    
    form = EmissionForm()
    if form.validate_on_submit():
        country_name = get_country_name_by_code(form.country.data)
        raw_data = get_emissions(
            country=form.country.data,
            timeframe=form.timeframe.data,
            start_year=form.start_year.data,
            month=form.start_month.data if form.start_month.data else None,
            quarter=form.start_quarter.data if form.start_quarter.data else None,
            end_year=form.end_year.data,
            end_month=form.end_month.data if form.end_month.data else None,
            end_quarter=form.end_quarter.data if form.end_quarter.data else None
        )

        if raw_data in ["NoRecordsFound", "ErrorParsingXML", "Failed to retrieve data"]:
            flash('No data available for the selected parameters.' if raw_data == "NoRecordsFound" else 'There was an error processing your request. Please try again later.', 'warning')
            return redirect(url_for('generateReport'))
        # print('raw_data', raw_data)
        sorted_data = sorted(raw_data, key=lambda x: x['time_period'])
        data_summary = {}
        total_emissions = 0
        all_emissions = []

        for item in sorted_data:
            time_key = item['time_period']
            emissions = float(item['emissions'])  # Ensure conversion to float
            total_emissions += emissions

            # Aggregate emissions by time period
            if time_key in data_summary:
                data_summary[time_key] += emissions
            else:
                data_summary[time_key] = emissions

        print('data summary', data_summary)

        highest_emissions = {'time_period': max(data_summary, key=data_summary.get), 'emissions': data_summary[max(data_summary, key=data_summary.get)], 'unit': 'T'} if data_summary else None
        lowest_emissions = {'time_period': min(data_summary, key=data_summary.get), 'emissions': data_summary[min(data_summary, key=data_summary.get)], 'unit': 'T'} if data_summary else None

        print('highest_emissions', highest_emissions)
        print('lowest_emissions', lowest_emissions)
        average_emissions = total_emissions / len(data_summary) if data_summary else 0

        # Format the numbers for display in the template
        formatted_total_emissions = "{:,.2f}".format(total_emissions)
        highest_emissions['emissions'] = "{:,.2f}".format(highest_emissions['emissions'])
        lowest_emissions['emissions'] = "{:,.2f}".format(lowest_emissions['emissions'])
        formatted_average_emissions = "{:,.2f}".format(average_emissions)

        return render_template('report.html', data_summary=data_summary, 
                               total_emissions=formatted_total_emissions,
                               highest_emissions=highest_emissions, 
                               lowest_emissions=lowest_emissions,
                               average_emissions=formatted_average_emissions, 
                               country=country_name, timeframe=form.timeframe.data,
                               start_year=form.start_year.data, end_year=form.end_year.data)
    else:
        for fieldName, errorMessages in form.errors.items():
            for err in errorMessages:
                flash(f'Error in {fieldName}: {err}', 'danger')
    return render_template('reportform.html', form=form)

@app.route('/emissions-ranking', methods=['GET', 'POST'])
def country_ranking():
    current_year = datetime.now().year
    form = EmissionRankingForm()
    if request.method == 'GET':
        form.start_year.data = current_year - 1
        form.start_month.data = '1'
        form.end_month.data = '12'
    
    if form.validate_on_submit() or request.method == 'GET':
        start_year = int(form.start_year.data)
        start_month = int(form.start_month.data)
        end_year = start_year  # Assume same year for simplicity
        end_month = int(form.end_month.data)

        print("timeframe ", start_month, start_year," to ",  end_month, end_year)

        base_url = "https://sdmx.oecd.org/public/rest/data"
        dataflow = "OECD.SDD.NAD.SEEA,DSD_AIR_TRANSPORT@DF_AIR_TRANSPORT,1.0"
        time_suffix = f".M....._T.."  # Updated to include '_T' for all flights
        start_period = f"{start_year}-{start_month:02}"
        end_period = f"{end_year}-{end_month:02}"
        url = f"{base_url}/{dataflow}/{time_suffix}?startPeriod={start_period}&endPeriod={end_period}&dimensionAtObservation=AllDimensions"
        print('start_period', start_period)
        print('end_period ', end_period)
        print(url)

        root, error_message = fetch_country_data(url)
        if error_message:
            flash(error_message, 'danger')  # Flash an error messag
            return redirect(url_for('country_ranking')) 

        country_data = {}
        total_emissions = 0

        if root:
            for obs in root.findall('.//generic:Obs', namespaces={'generic': 'http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/generic'}):
                country_code = obs.find('.//generic:Value[@id="REF_AREA"]', namespaces={'generic': 'http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/generic'}).attrib['value']
                emissions = float(obs.find('.//generic:ObsValue', namespaces={'generic': 'http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/generic'}).attrib['value'])
                country_data[country_code] = country_data.get(country_code, 0) + emissions
                total_emissions += emissions

            print('country_data', country_data)
            print('total_emissions', total_emissions)
            emissions_values = list(country_data.values())
            low_threshold, high_threshold = np.percentile(emissions_values, [33, 66])
            
            formatted_countries = []
            for code, emissions in country_data.items():
                percentage = (emissions / total_emissions) * 100
                if emissions < low_threshold:
                    color_class = 'low-emissions'
                elif emissions < high_threshold:
                    color_class = 'medium-emissions'
                else:
                    color_class = 'high-emissions'
                
                formatted_countries.append((get_country_name_by_code(code), format(emissions, ',.2f'), format(percentage, '.2f'), color_class))

            sorted_countries = sorted(formatted_countries, key=lambda item: float(item[1].replace(',', '')), reverse=(form.order.data == 'descending'))

            average_emissions = total_emissions / len(country_data) if country_data else 0

            return render_template('ranking.html', form=form, countries=sorted_countries,
                                   total_emissions=format(total_emissions, ',.2f'), 
                                   average_emissions=format(average_emissions, ',.2f'),
                                   start_year=start_year, start_month=start_month, 
                                   end_year=end_year, end_month=end_month)

    return render_template('ranking.html', form=form)


@login_required
@app.route('/chat/')
def load_chatbot():
    if not(is_admin(current_user.username) or is_regulator(current_user.username)):
        flash('Must be regulatory authority or airline operator to access this page','warning')
        return redirect('dashboard')
    return render_template('chatbot.html')

@app.route('/api/chat/', methods=['POST'])
def chat():
    conn, cur = get_db_connection()
    try:
        data = request.json
        icao_code = data.get('icao_code', '').strip()
        # flight_distance_str = data.get('flight_distance', '0').strip()
        flight_distance_str = str(data.get('flight_distance'))

        if not icao_code:
            return jsonify({'error': 'Missing ICAO code'}), 400
        try:
            cur.execute("SELECT icao from icao_codes")
            icao_codes = cur.fetchall()
            # Format as iterable list
            icao_codes = [code[0] for code in icao_codes]
            print(icao_code)
            if not (icao_code in icao_codes):
                return jsonify({'message': 'Invalid ICAO code'}), 404
            flight_distance = float(flight_distance_str)
        except ValueError:
            return jsonify({'error': 'Invalid flight distance format'}), 400

        # Fetch weather data
        weather_data = get_weather(os.getenv('CX_WEATHER_API_KEY'), icao_code)
        wind_speed = extract_wind_speed(weather_data)
        temperature = extract_temperature(weather_data)
        is_rainfall, is_thunderstorms = check_weather_conditions(weather_data)

        # Calculate emissions
        emissions = calculate_emissions(flight_distance, wind_speed)
        recommendations = generate_recommendations(emissions)

        # Compose response message
        weather_info = []
        if temperature is not None:
            weather_info.append(f"Temperature: {temperature} °C <br> ")
        if wind_speed is not None:
            weather_info.append(f"Wind Speed: {wind_speed} kt <br> ")
        weather_info.append(f"Rainfall: {'Yes' if is_rainfall else 'None'} <br> ")
        weather_info.append(f"Thunderstorms: {'Yes' if is_thunderstorms else 'None'} <br> ")

        message = f"Current Weather Conditions:\n" + '\n'.join(weather_info) + \
                  f"\n\nEmissions: {emissions-(0.05*emissions):.2f} kg - {emissions+(0.05*emissions):.2f} kg CO2 ({emissions:.2f} ± 5%) <br> {recommendations}"

        return jsonify({'message': message})
    except Exception as e:
        return jsonify({'error': f"Error processing request: {str(e)}"}), 500

# @app.route('/fuel-calculator', methods=['GET', 'POST'])
def fuel_burn_calculator():
    form = FuelBurnForm()
    conn, cur = get_db_connection()
    if form.validate_on_submit():
        icao_code = form.icao_code.data.upper()
        distance = form.distance.data

        cur.execute(f"SELECT avg_fuel_burn_kg_km FROM aircraft_data WHERE icao_code = \'{icao_code}\'")

        aircraft = cur.fetchone()
        print(aircraft)
        if aircraft:
            avg_fuel_burn_kg_km = aircraft[0]
            estimated_fuel = float(distance * avg_fuel_burn_kg_km)*1.07
            flash(f'Estimated fuel burn for {distance} km: {estimated_fuel:.2f} kg', 'success')
        else:
            flash('Aircraft ICAO code not found in the database.', 'danger')

        return redirect(url_for('fuel_burn_calculator'))

    return render_template('fuel_burn_calculator.html', form=form)

# Works and retruns  a dictionary
def get_emissions(country, timeframe, start_year, month, quarter, end_year, end_month, end_quarter):
    base_url = "https://sdmx.oecd.org/public/rest/data"
    dataflow = "OECD.SDD.NAD.SEEA,DSD_AIR_TRANSPORT@DF_AIR_TRANSPORT,1.0"
    
    # Determine time suffix and period based on the timeframe
    if timeframe == 'annual':
        start_period = f"{start_year}"
        end_period = f"{end_year}"
        time_suffix = f".A....._T.."  # Updated to include '_T' for all flights
    elif timeframe == 'monthly':
        start_period = f"{start_year}-{month.zfill(2)}"
        end_period = f"{end_year}-{end_month.zfill(2)}"
        time_suffix = f".M....._T.."  # Updated to include '_T' for all flights
    elif timeframe == 'quarterly':
        start_period = f"{start_year}-Q{quarter}"
        end_period = f"{end_year}-Q{end_quarter}"
        time_suffix = f".Q....._T.."  # Updated to include '_T' for all flights
    
    url = f"{base_url}/{dataflow}/{country}{time_suffix}?startPeriod={start_period}&endPeriod={end_period}&dimensionAtObservation=AllDimensions"
    print("Requesting URL:", url)  # For debugging purposes
    response = requests.get(url)
    print("response: ", response)
    
    if response.status_code == 404:
        return "NoRecordsFound"
    elif response.status_code == 200:
        try:
            root = ET.fromstring(response.content)
            emissions_data = []
            for obs in root.findall('.//generic:Obs', namespaces={'generic': 'http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/generic'}):
                data_point = {
                    'time_period': obs.find('.//generic:Value[@id="TIME_PERIOD"]', namespaces={'generic': 'http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/generic'}).attrib['value'],
                    'emissions': float(obs.find('.//generic:ObsValue', namespaces={'generic': 'http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/generic'}).attrib['value']),
                    'unit': obs.find('.//generic:Value[@id="UNIT_MEASURE"]', namespaces={'generic': 'http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/generic'}).attrib['value']
                }
                emissions_data.append(data_point)
            return emissions_data
        except ET.ParseError:
            return "ErrorParsingXML"
    return "Failed to retrieve data"  # Handles other unexpected status codes



@app.route('/login', methods=['POST', 'GET'])
def login():
    
    if UserProfile.query.count() == 0:
        # If the table is empty, add a new user profile
        user = UserProfile(first_name="Crypto",
                           last_name="Ciphers Unltd.",
                            username="admin",
                            password="admin")
        db.session.add(user)
        db.session.commit()
        print("Admin user created")

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
                return redirect(url_for("dashboard"))  
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
        database="flightoptimizer",
        user=os.environ.get('DATABASE_USERNAME', 'postgres'),
        password= os.environ.get('DATABASE_PASSWORD')
    )    
    cur = conn.cursor()    
    return conn, cur

# 
def fetch_country_data(url):
    response = requests.get(url)
    if response.status_code == 200:
        return ET.fromstring(response.content), None
    else:
        error_message = f"Failed to fetch data: {response.status_code} - {response.reason}"
        return None, error_message
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
                impact_desc = ''
                if wind_speed > 20:
                    impact_desc += f"High winds might increase fuel consumption, current wind speed is {wind_speed}Kts. "
                else:
                    impact_desc += f"Low winds with a speed of {wind_speed} Kts. "
                if conditions_described:
                    impact_desc += f"{conditions_described}. "

                # Include visibility and significant weather conditions like snow, ice, or fog
                if 'visibility' in forecast and forecast['visibility']['miles_float'] < 1:
                    impact_desc += " \nLow visibility could lead to delays and increased fuel usage."
                if any('snow' in c['text'].lower() or 'ice' in c['text'].lower() or 'fog' in c['text'].lower() for c in forecast.get('conditions', [])):
                    impact_desc += " \nConditions like snow, ice, or fog may require de-icing and can cause delays, increasing fuel usage."

                # Check for rain and its operational implications
                if any('rain' in c['text'].lower() for c in forecast.get('conditions', [])):
                    impact_desc += " \nRain may lead to increased braking distances and reduced runway friction, potentially affecting fuel usage due to longer taxi and rollout times."

                # Check for thunderstorms and turbulence for additional flight considerations
                if any('thunderstorm' in c['text'].lower() for c in forecast.get('conditions', [])):
                    impact_desc += " \nThunderstorms may necessitate significant rerouting."
                if any('turbulence' in c['text'].lower() for c in forecast.get('conditions', [])):
                    impact_desc += " \nTurbulence could lead to operational adjustments and potential fuel inefficiencies."

                # Append the formatted string to impacts list
                impacts.append({
                    'icao': icao,
                    'period': period,
                    'description': impact_desc
                })

    if not impacts:
                    impacts.append({
                    'icao': 'N/A',
                    'period': 'N/A',
                    'description': 'No significant TAF advisories affecting fuel emissions.'
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

@lru_cache(maxsize=1)
def fetch_country_codes():
    conn, cur = get_db_connection()
    cur.execute("SELECT * FROM countries;")
    response = cur.fetchall()
    return {r[0]:r[1] for r in response}
    
def get_country_name_by_code(country_code):
    countries = fetch_country_codes()
    return countries.get(country_code, "Unknown country code")

def extract_wind_speed(weather_data):
    try:
        return weather_data['data'][0]['wind']['speed_kts']
    except (IndexError, KeyError):
        return None

def extract_temperature(weather_data):
    try:
        return weather_data['data'][0]['temperature']['value']
    except (IndexError, KeyError):
        return None

def check_weather_conditions(weather_data):
    try:
        weather_conditions = weather_data['data'][0]['weather']
        is_rainfall = any(condition['value'] in ['RA', 'TSRA'] for condition in weather_conditions)
        is_thunderstorms = any(condition['value'] == 'TS' for condition in weather_conditions)
        return is_rainfall, is_thunderstorms
    except (IndexError, KeyError):
        return False, False

def calculate_emissions(flight_distance, wind_speed):
    baseline_emissions = flight_distance * 0.1
    if wind_speed is not None and wind_speed > 10:
        adjusted_emissions = baseline_emissions * 0.9
    else:
        adjusted_emissions = baseline_emissions
    return adjusted_emissions

def generate_recommendations(emissions):
    if emissions < 100:
        return "Your flight emissions are relatively low. Consider offsetting them with a carbon offset program."
    elif emissions >= 100 and emissions < 200:
        return "Your flight emissions are moderate. You may want to choose a more fuel-efficient airline for future flights."
    else:
        return "Your flight emissions are high. Consider alternative transportation options or carbon offset programs."
    
# Function to fetch weather data from CheckWX API
def get_weather(api_key, icao_code):
    url = f'https://api.checkwx.com/metar/{icao_code}/decoded'
    headers = {'X-API-Key': api_key}
    response = requests.get(url, headers=headers)
    return response.json()

# Function to calculate distance between 2 airports via ICAO codes w/ CheckWX API
def get_distance(src, dest):
    api_key = os.environ.get('CX_WEATHER_API_KEY')
    urlsrc = f'https://api.checkwx.com/metar/{src}/decoded'
    urldest = f'https://api.checkwx.com/metar/{dest}/decoded'

    responsesrc = requests.get(urlsrc, headers={'X-API-Key': api_key})
    responsedest = requests.get(urldest, headers={'X-API-Key': api_key})

    try:
        srcdata = responsesrc.json()["data"][0]['station']['geometry']['coordinates']
        srclat = srcdata[1]
        srclong = srcdata[0]

        destdata = responsedest.json()["data"][0]['station']['geometry']['coordinates']
        destlat= destdata[1]
        destlong = destdata[0]

        def calc_distance(lat1, lon1, lat2, lon2):
            import math
            # Convert degrees to radians
            lat1_rad = math.radians(lat1)
            lon1_rad = math.radians(lon1)
            lat2_rad = math.radians(lat2)
            lon2_rad = math.radians(lon2)

            # Calculate the difference in longitude
            delta_lon = lon2_rad - lon1_rad

            # Apply the formula
            distance = math.acos(math.sin(lat1_rad) * math.sin(lat2_rad) +
                                math.cos(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon)) * 6371

            return distance

        return calc_distance(srclat, srclong, destlat, destlong)

    except (IndexError, KeyError):
        return None  # Return None or a suitable default if an error occurs

from flask import jsonify, request

@app.route('/ajax/getDistance', methods=['POST'])
def ajax_get_distance():
    try:
        # Parse the incoming JSON data
        data = request.get_json()
        
        # Extract src and dest from the parsed data
        src = data['src']
        dest = data['dest']
        d= get_distance(src,dest)
        return jsonify({"distance": d}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def is_admin(username):
    user = UserProfile.query.filter_by(username=username).first()
    return user.role == 'admin'

def is_regulator(username):
    user = UserProfile.query.filter_by(username=username).first()
    return user.role == 'regulator'

def is_atc(username):
    user = UserProfile.query.filter_by(username=username).first()
    return user.role == 'atc'
