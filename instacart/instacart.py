# -*- coding: utf-8 -*-

import os
import traceback

from sqlite3 import dbapi2 as sqlite3
from flask import Flask, request, session, g, jsonify, redirect, url_for, \
    render_template, flash


# create our little application :)
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


def init_db():
    """Initializes the database."""
    db = get_db()
    with app.open_resource('schema.sql', mode='r') as f:
        db.cursor().executescript(f.read())
    db.commit()


@app.cli.command('initdb')
def initdb_command():
    """Creates the database tables."""
    init_db()
    print('Initialized the database.')


def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db


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
    
    app_id = session.get('application_id')
    if app_id:
        db = get_db()

        try:
            cur = db.execute(
                "SELECT * FROM applications WHERE id=? LIMIT 1",
                (app_id,)
            )
        except:
            del session['application_id']
            
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
                    data["firstname"], data["firstname"], data["email"],
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
                    data["firstname"], data["firstname"], data["email"],
                    data["cell"], data["city"]
                ),
            )

            app_id = insert_cursor.lastrowid
            
        db.commit()
        
    except:
        traceback.print_exc()
        
        # Couldn't save.  Give a generic error.
        return jsonify({
            'err': 'An unexpected error occurred.  Please try again'
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
