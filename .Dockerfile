FROM python:3.10-slim as build-stage

# Setup env
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONFAULTHANDLER 1
ENV FLASK_ENV production

COPY *.whl .

# Install pipenv and compilation dependencies
RUN apt-get update && apt-get install -y gcc
RUN python3 -m pip install wheel pip --upgrade && pip install pipenv
RUN apt-get update && apt-get install

COPY Pipfile .
COPY Pipfile.lock .
RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --system

echo 'from xisearch2.cython import *; ' | python

# Create and switch to a new user to ensure security
RUN useradd --create-home appuser
WORKDIR /home/appuser
USER appuser

# Install application into container
COPY static ./static
COPY templates ./templates
COPY tests ./tests
COPY xi_web_api ./xi_web_api
COPY .env .
COPY default.database.ini .
COPY .kubernetes.yml .

#FROM base AS production
# Run the application
#CMD ["python" ,"-m" ,"flask", "run","--host=0.0.0.0"]
ENTRYPOINT waitress-serve --port ${PORT} --url-prefix ${URL_PREFIX} --call ${APP_ENTRY}
