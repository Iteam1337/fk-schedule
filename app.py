import json
import enum
import datetime
import os

from flask import Flask
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event, types

import pika

rabbit_host = os.environ.get('RABBITMQ__HOST', 'ampq://localhost')
postgresql_host = os.environ.get('POSTGRES__HOST', 'postgresql://pguser:pgpass@localhost:5432/pgdb')


channel = None

def get_channel():
    global channel
    if channel is not None:
        return channel
    connection = pika.BlockingConnection(pika.URLParameters(rabbit_host))
    channel = connection.channel()
    channel.exchange_declare(
        exchange='dispatch',
        type='x-delayed-message',
        durable=True,
        arguments={ 'x-delayed-type': 'direct' }
    )
    channel.exchange_declare(
        exchange='logs',
        type='fanout',
        durable=True
    )
    return channel


app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = postgresql_host
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'blahblahblah'
db = SQLAlchemy(app)


class Departures(enum.Enum):
    CENTRALSTATION = 1
    LARGE_AIRPORT = 2
    SMALL_AIRPORT = 3


class Speaker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=False)
    topic = db.Column(db.String(80))

    def __repr__(obj):
        return 'Speaker <{}>'.format(obj.name)


class Pickup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    speaker_id = db.Column(db.Integer, db.ForeignKey('speaker.id'))
    speaker = db.relationship('Speaker')
    time = db.Column(db.DateTime)
    location = db.Column(types.Enum(Departures))


@event.listens_for(Pickup, 'after_insert')
def send_message(mapper, connection, pickup):
    message = dict(
        source='schedule',
        action='pickup',
        time=pickup.time.isoformat(),
        data=dict(
            name=pickup.speaker.name,
            location=pickup.location,
        )
    )
    delay = max(0, (pickup.time - datetime.timedelta(hours=2, minutes=30) - datetime.datetime.utcnow()).seconds)
    headers = {
       'x-delay': delay * 1000
    }
    get_channel().basic_publish(
        exchange='dispatch',
        routing_key='',
        body=json.dumps(message),
        properties=pika.spec.BasicProperties(headers=headers)
    )

@event.listens_for(Speaker, 'after_insert')
def send_message(mapper, connection, speaker):
    message = {
        'source': 'schedule',
        'timestamp': datetime.datetime.now().isoformat(),
        'level': 'info',
        'message': 'speaker {} has been added'.format(speaker.name)
    }
    get_channel().basic_publish(
        exchange='logs',
        routing_key='',
        body=json.dumps(message),
    )

admin = Admin(app, name='schedule', template_mode='bootstrap3')
admin.add_view(ModelView(Pickup, db.session))
admin.add_view(ModelView(Speaker, db.session))