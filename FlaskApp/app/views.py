import os, requests
from app import app, db, login_manager
from flask import render_template, request, redirect, url_for, flash, jsonify, request
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.utils import secure_filename
from app.models import UserProfile
from app.forms import LoginForm
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime



###
# Routing for your application.
###

@app.route('/')
@login_required
def home():
    """Render website's home page."""
    return render_template('home.html')


@app.route('/about/')
def about():
    """Render the website's about page."""
    return render_template('about.html', name="Mary Jane")

@app.route('/weather/', methods=['GET'])
def weather():
    api_key = 'a741a79a6d7246f8a3e0364dc8' # Replace with your actual API key
    url = 'https://api.checkwx.com/metar/MKJP/decoded'
    headers = {'X-API-Key': api_key}

    response = requests.request("GET", url, headers={'X-API-Key': api_key})
    data = response.json()["data"][0]
    temperature_data = data["temperature"]
    degsC = temperature_data["celsius"]
    degsF = temperature_data["fahrenheit"]
    # if response.status_code == 200:
    #     data = response.json()
    #     print(data["temperature"])
        # temperature = data['temperature'] # Assuming the temperature is directly accessible
    return render_template('weather.html', degsC=degsC, degsF=degsF)

@app.route('/login', methods=['POST', 'GET'])
def login():
    form = LoginForm()

    # change this to actually validate the entire form submission
    # and not just one field
    if form.validate_on_submit():
        # Get the username and password values from the form.
        res = request.form
        formUsername = res['username']
        formPassword = res['password']


        # Using your model, query database for a user based on the username
        # and password submitted. Remember you need to compare the password hash.
        # You will need to import the appropriate function to do so.
        # Then store the result of that query to a `user` variable so it can be
        # passed to the login_user() method below.
        #user =  db.session.execute(db.select(UserProfile).filter_by(username = formUsername)).scalars()
        user =  UserProfile.query.filter_by(username = formUsername)
        # user = userQuery[0]
        if check_password_hash(user[0].password, formPassword):
            # Gets user id, load into session
            login_user(user[0])
            # Remember to flash a message to the user
            flash("Successful login")
            return redirect(url_for("home"))  # The user should be redirected to the home instead

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