FROM python:3.10-slim as build-stage

# Setup env
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONFAULTHANDLER 1
ENV FLASK_DEBUG production

COPY *.whl .

# Install pipenv and compilation dependencies
RUN apt-get update && apt-get install -y gcc g++
RUN python3 -m pip install wheel pip --upgrade && pip install pipenv
RUN apt-get update && apt-get install

COPY Pipfile .
COPY Pipfile.lock .
RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --system

RUN echo 'from xisearch2.cython import *; ' | python

# Create and switch to a new user to ensure security
RUN useradd --create-home appuser
WORKDIR /home/appuser
USER appuser
RUN mkdir -p /home/appuser/logs

# Install application into container
COPY static ./static
COPY templates ./templates
COPY tests ./tests
COPY xiview_server ./xiview_server
COPY .env .
COPY default.database.ini .
COPY logging.ini .
COPY .kubernetes.yml .

#FROM base AS production
# Run the application
#CMD ["python" ,"-m" ,"flask", "run","--host=0.0.0.0"]
ENTRYPOINT waitress-serve --port ${PORT} --url-prefix ${URL_PREFIX} --call ${APP_ENTRY}
