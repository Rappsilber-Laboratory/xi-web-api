FROM python:3.10-slim as base

# Setup env
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONFAULTHANDLER 1
ENV FLASK_ENV development

# Install pipenv and compilation dependencies
RUN python3 -m pip install wheel pip --upgrade && pip install pipenv
RUN apt-get update && apt-get install

COPY Pipfile .
COPY Pipfile.lock .
RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --system

# Create and switch to a new user to ensure security
RUN useradd --create-home appuser
WORKDIR /home/appuser
USER appuser

# Install application into container
COPY static ./static
COPY templates ./templates
COPY tests ./tests
COPY xi2_xiview_loader ./xi2_xiview_loader
COPY .env .
COPY default.database.ini .
COPY .kubernetes.yml .

#FROM base AS production
# Run the application
#CMD ["python" ,"-m" ,"flask", "run","--host=0.0.0.0"]
CMD ["waitress-serve", "--port", "8080", "--call", "xi2_xiview_loader.xi2_loader:create_app"]
