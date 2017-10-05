#!/usr/bin/env python3

import os
import hashlib
import json
import time
import calendar
from datetime import datetime

from flask import Flask, abort, jsonify, request, session
from flask_sqlalchemy import SQLAlchemy

with open(os.environ.get('WORKLOG_ENV') or '.env') as f:
    env = json.load(f)

app = Flask(__name__)
app.config.update(env)

db = SQLAlchemy(app)

# TZ

# Helpers
def to_ts(dt):
    return calendar.timegm(dt.timetuple())

# Models

class Record(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    tags = db.Column(db.String(127), default='')
    created_at = db.Column(db.DateTime(),
            nullable=False, default=datetime.utcnow)

    def serialize(self):
        return {'id': self.id, 'content': self.content,
                'tags': self.tags.split('|'), 'created_at': to_ts(self.created_at)}



# Views

def _gen_token():
    return hashlib.md5(env['account.password'].encode('utf8')).hexdigest()

def _valid_auth():
    return request.headers.get('Authorization', '') == 'Bearer ' + _gen_token()

def _validate_login(username, password):
    return env['account.username'] == username and \
            env['account.password'] == password

def _search_records(keywords, tags, limit, offset):
    query = Record.query.filter(Record.content.like('%%%s%%' % keywords),
            Record.tags.like('%%%s%%' % tags))
    return query.count(), query.limit(limit).offset(offset).all()

def _get_records(tags, offset, limit):
    query = Record.query
    if tags:
        query = query.filter(Record.tags.like('%%%s%%' % tags))
    return query.count(), query.limit(limit).offset(offset).all()

def _add_record(content, tags, **kwargs):
    record = Record(content=content, tags='|'.join(tags))
    db.session.add(record)
    db.session.commit()
    return record

def _update_record(id, **kwargs):
    record = Record.query.get(id)
    for k, v in kwargs.items():
        setattr(record, k, v)
    db.session.add(record)
    db.session.commit()
    return record

def _delete_record(id):
    record = Record.query.get(id)
    if record:
        db.session.delete(record)
        db.session.commit()

@app.before_request
def require_login():
    if not _valid_auth():
        abort(401)

@app.route('/')
def index():
    return 'Hello world'

@app.route('/api/1/records')
def get_records():
    keyword, tags = request.args.get('keyword'), request.args.get('tags')
    offset = request.args.get('offset', type=int, default=0)
    limit = request.args.get('limit', type=int, default=20)
    if keyword:
        n, records = _search_records(keyword, tags, offset, limit)
    else:
        n, records = _get_records(tags, offset, limit)
    return jsonify(msg="OK", data={
        'records': [r.serialize() for r in records],
        'count': n})

@app.route('/api/1/records', methods=['POST'])
def add_record():
    record = _add_record(**request.get_json())
    return jsonify(msg="OK", data={'record': record.serialize()})

@app.route('/api/1/records/<int:id>', methods=['PUT'])
def update_record(id):
    record = _update_record(id, **request.get_json())
    return jsonify(msg="OK", data={'record': record.serialize()})

@app.route('/api/1/records/<int:id>', methods=['DELETE'])
def delete_record(id):
    _delete_record(id)
    return jsonify(msg="OK")



# RUN

db.create_all()
