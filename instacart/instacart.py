# -*- coding: utf-8 -*-

import copy
import os
import random
import re
import string
import time
import traceback

from collections import OrderedDict
from datetime import datetime, timedelta
from sqlite3 import dbapi2 as sqlite3
from flask import Flask, request, session, g, jsonify, redirect, url_for, \
    render_template, flash


# The number of fake applications to make.  initdb() will create this
# many applications, with permutations on the status of the application.
FAKE_APPLICATIONS = 1000000

app = Flask(__name__)

# Load default config and override config from an environment variable
app.config.update(dict(
    DATABASE=os.path.join(app.root_path, 'development.sqlite3'),
    DEBUG=True,
    SECRET_KEY='development key',
    USERNAME='admin',
    PASSWORD='default'
))
app.config.from_envvar('INSTACART_SETTINGS', silent=True)


def connect_db():
    """Connects to the specific database."""
    rv = sqlite3.connect(app.config['DATABASE'])
    rv.row_factory = sqlite3.Row
    return rv


def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db


def init_db():
    """Initializes the database."""
    db = get_db()

    # Create the tables.
    with app.open_resource('schema.sql', mode='r') as f:
        db.cursor().executescript(f.read())

    # Handy function for generating random strings.
    def string_gen(size=6, chars=string.ascii_uppercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))

    # Handy function for generating dates in the range
    def application_date_gen():
        earliest = 1325376001  # Sun, 01 Jan 2012 00:00:01 GMT
        latest = 1419984001  # Wed, 31 Dec 2014 00:00:01 GMT
        time_val = random.randint(earliest, latest)
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time_val))

    # Create a whole bunch of records.
    for _ in range(0, FAKE_APPLICATIONS):
        applicant_status = random.choice(['p', 'h', 'r'])
        quiz_completed = application_date_gen()
        onboarding_completed = application_date_gen()

        # If the applicant isn't hired, there's a chance they haven't completed
        # quiz and onboarding.  Give it a 50% chance
        if applicant_status != 'h':
            quiz_completed = random.choice([None, quiz_completed])
            onboarding_completed = random.choice([None, onboarding_completed])

        # Create the applicant.
        application_cursor = db.execute(
            (
                "INSERT INTO `applications` "
                "(firstname, lastname, email, cell_number, city, created, "
                "status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)"
            ),
            (
                string_gen(), string_gen(), string_gen(), string_gen(),
                string_gen(), application_date_gen(), applicant_status
            ),
        )
        
        application_id = application_cursor.lastrowid

        # Create the quiz
        if onboarding_completed or random.choice([True, False]):
            db.execute(
                (
                    "INSERT INTO `quiz` "
                    "(application_id, completed) "
                    "VALUES (?, ?)"
                ),
                (
                    application_id, quiz_completed,
                ),
            )

        # Create the onboarding
        if quiz_completed or random.choice([True, False]):
            db.execute(
                (
                    "INSERT INTO `onboarding` "
                    "(application_id, completed) "
                    "VALUES (?, ?)"
                ),
                (
                    application_id, onboarding_completed,
                ),
            )
        
    db.commit()


@app.cli.command('initdb')
def initdb_command():
    """Creates the database tables."""
    init_db()
    print('Initialized the database.')


@app.teardown_appcontext
def close_db(error):
    """Closes the database again at the end of the request."""
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()


@app.route('/')
def route_home():
    return render_template('home.html')


@app.route('/apply', methods=['GET'])
def route_apply():
    app_data = {}

    # Do we have an application?
    app_id = session.get('application_id')
    if app_id:
        # Yep, get the existing data.
        db = get_db()
        try:
            cur = db.execute(
                "SELECT * FROM applications WHERE id=? LIMIT 1",
                (app_id,)
            )
        except:
            del session['application_id']
        else:
            app_data = cur.fetchone()
        
    return render_template('apply.html', app_data=app_data)


@app.route('/apply', methods=['POST'])
def route_apply_submit():
    # Grab all the data
    data = {
        'firstname': request.values.get('firstname'),
        'lastname': request.values.get('lastname'),
        'email': request.values.get('email'),
        'cell': request.values.get('cell_number'),
        'city': request.values.get('city'),
    }
    
    # Simple error checking -- just check for empty
    err_fields = []
    for k, v in data.items():
        if not v:
            err_fields.append(k)

    # Did we find any data errors?
    if err_fields:
        return jsonify({
            'err_fields': err_fields,
        })

    db = get_db()
    app_id = session.get('application_id')

    try:
        if app_id:
            # Save to the database.
            db.execute(
                (
                    "UPDATE `applications` SET "
                    "firstname=?, lastname=?, email=?, cell_number=?, city=?"
                    "WHERE id=?"
                ),
                (
                    data["firstname"], data["lastname"], data["email"],
                    data["cell"], data["city"], app_id
                ),
            )
        else:
            # Save to the database.
            insert_cursor = db.execute(
                (
                    "INSERT INTO `applications` "
                    "(firstname, lastname, email, cell_number, city) "
                    "VALUES (?, ?, ?, ?, ?)"
                ),
                (
                    data["firstname"], data["lastname"], data["email"],
                    data["cell"], data["city"]
                ),
            )

            app_id = insert_cursor.lastrowid
            
        db.commit()
        
    except:
        traceback.print_exc()
        
        # Couldn't save.  Give a generic error.
        return jsonify({
            'err': 'An unexpected error occurred.  Please try again.'
        })

    # Set the application ID for future reference.
    session['application_id'] = app_id
    
    # All is good!
    return jsonify({
        'succ': True,
    })


@app.route('/apply_confirm', methods=['GET'])
def route_apply_confirm():
    return render_template('apply_confirm.html')
    

@app.route('/logout')
def logout():
    session.clear()
    flash('You were logged out')
    return redirect(url_for('route_home'))


@app.route('/funnels.json')
def route_funnels():
    start = request.values.get('start_date', '')
    end = request.values.get('end_date', '')

    # Sanity check start_date
    if not re.match(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', start):
        return jsonify({
            'err': 'Bad start date',
        })

    # Sanity check end_date
    if not re.match(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', end):
        return jsonify({
            'err': 'Bad end date',
        })    

    db = get_db()

    # Get all sums by days.
    # NOTE: I'd love to group here by %Y.%W, to get max 52 records per
    # year instead of the 365 we get per year by grouping on date.
    # Sadly SQLite starts weeks on Sunday, and the project requirements say
    # the week needs to start on Monday.
    cursor = db.execute(
        (
            """
            SELECT
            status,
            count(*) as num_applicants,
            count(t_q.id) as num_quiz,
            count(t_q.completed) as num_quiz_complete,
            count(t_o.id) as num_onboard,
            count(t_o.completed) as num_onboard_complete,
            date(t_a.created) as created_date
            FROM applications as t_a
            LEFT JOIN quiz as t_q ON t_a.id=t_q.application_id
            LEFT JOIN onboarding as t_o ON t_a.id=t_o.application_id
            WHERE date(t_a.created) >= ? and date(t_a.created) < ?
            GROUP BY date(t_a.created), status
            ORDER BY t_a.created
            """
        ),
        (
            start, end
        )
    )

    # The default we'll start with for each week
    default = OrderedDict({
        'applied': 0,
        'quiz_started': 0,
        'quiz_completed': 0,
        'onboarding_requested': 0,
        'onboarding_completed': 0,
        'hired': 0,
        'rejected': 0
    })
    
    data = OrderedDict()
    
    for row in cursor.fetchall():
        row = dict(zip(row.keys(), row))

        # Get the week-bounded date keyB
        dt = datetime.strptime(row['created_date'], '%Y-%m-%d')
        start = dt - timedelta(days=dt.weekday())
        end = start + timedelta(days=6)
        date_key = "{}-{}".format(
            datetime.strftime(start, "%Y-%m-%d"),
            datetime.strftime(end, "%Y-%m-%d")
        )

        # Make sure the data is there for this week.
        if date_key not in data:
            data[date_key] = copy.copy(default)

        # Update the data.
        curr = data[date_key]
        curr["applied"] += row['num_applicants']
        curr["quiz_started"] += row['num_quiz']
        curr["quiz_completed"] += row['num_quiz_complete']
        curr["onboarding_requested"] += row['num_onboard']
        curr["onboarding_completed"] += row['num_onboard_complete']

        # Add status
        if row['status'] == 'h':
            curr["hired"] += row['num_applicants']
        elif row['status'] == 'r':
            curr["rejected"] += row['num_applicants']

    return jsonify(data)
