import flask
from flask import request
from flask_cors import CORS
from flask import jsonify
import psycopg2
import os
from config import config

app = flask.Flask(__name__)
cors = CORS(app)
app.config["DEBUG"] = True


@app.route('/get_intact', methods=['GET'])
def get_intact():
    uuid = request.args.get('uuid')
    data_obj = get_data_object(uuid)
    response = jsonify(data_obj)
    # print (response)
    return response


def get_data_object(uuid):
    """ Connect to the PostgreSQL database server """
    conn = None
    data = {}
    try:
        # read connection parameters
        params = config()

        # connect to the PostgreSQL server
        print('Connecting to the PostgreSQL database...')
        conn = psycopg2.connect(**params)

        # create a cursor
        cur = conn.cursor()

        sql = """select * from filename_json;
                   """
        cur.execute(sql, [uuid])
        data = cur.fetchall()

        # close the communication with the PostgreSQL
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()
            print('Database connection closed.')
        return data


if __name__ == '__main__':
    app.run(host=os.getenv("app_host"), port="5000")
