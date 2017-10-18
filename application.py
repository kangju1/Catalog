from flask import (Flask, render_template, request,
                   redirect, jsonify, url_for, flash)
from sqlalchemy import create_engine, asc, desc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, User, Category, Item

from flask import session as login_session
import random
import string

from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

from handler import gconnect, gdisconnect

app = Flask(__name__)

engine = create_engine('sqlite:///catalog.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


@app.route('/')
@app.route('/catalog')
def index():
    categories = session.query(Category).all()
    items = session.query(Item).order_by(desc(Item.id)).limit(10)
    return render_template('index.html',
                           categories=categories, items=items)


@app.route('/catalog/<path:cat_name>/')
def showItems(cat_name):
    categories = session.query(Category).all()
    category = session.query(Category).filter_by(
        name=cat_name).one()
    items = session.query(Item).filter_by(cat_id=category.id).all()
    number = len(items)
    return render_template('showitems.html',
                           categories=categories,
                           category=category,
                           items=items,
                           number=number)


@app.route('/catalog/<path:cat_name>/<path:item_title>')
def showItem(cat_name, item_title):
    category = session.query(Category).filter_by(name=cat_name).one()
    item = session.query(Item).filter_by(title=item_title,
                                         cat_id=category.id).one()
    return render_template('showitem.html',
                           category=category, item=item)


@app.route('/catalog/item/<int:item_id>')
def passToItem(item_id):
    item = session.query(Item).filter_by(id=item_id).one()
    category = session.query(Category).filter_by(id=item.cat_id).one()
    return redirect('/catalog/' + category.name + '/' + item.title)


@app.route('/catalog/newitem', methods=['GET', 'POST'])
def newItem():
    if 'username' not in login_session:
        return redirect('/login')
    categories = session.query(Category).all()
    if request.method == 'POST':
        item = getItem(request.form['category'], request.form['title'])
        if item is not None:
            flash("Item already Exists")
            return render_template('newitem.html', categories=categories)
        elif request.form['title'] == "":
            flash("No title inserted")
            return render_template('newitem.html', categories=categories)
        else:
            newItem = Item(title=request.form['title'],
                           description=request.form['description'],
                           cat_id=request.form['category'],
                           user_id=login_session['user_id'])
            session.add(newItem)
            session.commit()
            flash("Item successfully added")
            category = session.query(
                        Category).filter_by(
                        id=request.form['category']).one()
            items = session.query(Item).filter_by(cat_id=category.id).all()
            number = len(items)
            return render_template('showitems.html',
                                   categories=categories,
                                   category=category,
                                   items=items,
                                   number=number)
    else:
        return render_template('newitem.html', categories=categories)


@app.route('/catalog/<path:item_title>/edit', methods=['GET', 'POST'])
def editItem(item_title):
    # Check if the user is logged in
    if 'username' not in login_session:
        return redirect('/login')
    editItem = session.query(Item).filter_by(title=item_title).one()
    # Check if the user is authrized for altering the item
    if editItem.user_id != login_session['user_id']:
        flash("Permission denied")
        return redirect('/')
    if request.method == 'POST':
        if request.form['title']:
            editItem.title = request.form['title']
        if request.form['description']:
            editItem.description = request.form['description']
        if request.form['category']:
            editItem.cat_id = request.form['category']
        session.add(editItem)
        session.commit()
        flash("Item successfully edited")
        category = session.query(
                    Category).filter_by(id=request.form['category']).one()
        item = session.query(Item).filter_by(
                cat_id=request.form['category'],
                title=request.form['title']).one()
        return render_template('showitem.html', category=category, item=item)
    else:
        categories = session.query(Category).all()
        item = session.query(Item).filter_by(title=item_title).one()
        return render_template(
                'edititem.html',
                categories=categories,
                item=item)


@app.route('/catalog/<path:cat_name>/<path:item_title>/delete', methods=['GET', 'POST'])
def deleteItem(cat_name, item_title):
    # Check if the user is logged in
    if 'username' not in login_session:
        return redirect('/login')
    category = session.query(Category).filter_by(name=cat_name).one()
    deleteItem = session.query(Item).filter_by(
                  cat_id=category.id,
                  title=item_title).one()
    # Check if the user is authrized for altering the item
    if deleteItem.user_id != login_session['user_id']:
        flash("Permission denied")
        return redirect('/')
    if request.method == 'POST':
        categories = session.query(Category).all()
        session.delete(deleteItem)
        flash("Item successfully Deleted")
        session.commit()
        items = session.query(Item).filter_by(cat_id=category.id).all()
        number = len(items)
        return render_template(
                'showitems.html',
                categories=categories,
                category=category,
                items=items,
                number=number)
    else:
        category = session.query(Category).filter_by(name=cat_name).one()
        item = session.query(Item).filter_by(
                cat_id=category.id,
                title=item_title).one()
        return render_template('deleteitem.html', category=category, item=item)


@app.route('/catalog/json/<int:category_id>/')
def showJson(category_id):
    return jsonify(Category=makeCatJson(category_id))


@app.route('/login')
def login():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state)


@app.route('/gconnect', methods=['POST'])
def googleLogin():
    result = gconnect()
    return result


@app.route('/disconnect')
def logout():
    result = gdisconnect()
    return result


def makeCatJson(category_id):
    """
    makeCatJson: Get arbitrary items of the category sorted by the id
    """
    category = session.query(Category).filter_by(id=category_id).one()
    cat_list = []
    items = session.query(Item).filter_by(cat_id=category.id).all()
    obj = {
        "name": category.name,
        "id": category.id,
        "items": [i.serialize for i in items]
    }
    cat_list.append(obj)
    return cat_list


def getItem(cat_id, title):
    try:
        item = session.query(Item).filter_by(cat_id=cat_id, title=title).one()
        return item
    except:
        return None


if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
