# xiview-server

Instructions for setting up a local installation of xiVIEW are below.

## 1. Follow the instructions at https://github.com/Rappsilber-Laboratory/xi-mzidentml-converter. 
They will show you how to create the xiVIEW database, parse an mzIdentML 1.2.0 file into it, and start an API that will serve the data to the visualisation javascript in the browser.

## 2. Install the xiVIEW server
Clone the git repository :
```
git clone https://github.com/Rappsilber-Laboratory/xiview-server.git
```

cd into the repository:
```
cd xiview-server
```

Set up the python environment:
```
pipenv install --python 3.10
```

### 3. Start the server
```
python -m flask run --port 5000
```

flask is not suitable for production use, so you should use a production server such as gunicorn or uwsgi. See https://flask.palletsprojects.com/en/2.0.x/deploying/ for more information.
(Others are using 'waitress' as the production server, flask is OK just to test.)

You should now see a list of parsed datasets at http://127.0.0.1:5000/

At the moment, if you need to change the path to the API serving te data, edit lines 168 & 169 of network.html and line 40 of app.py.







