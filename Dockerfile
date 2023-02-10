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

# Install python dependencies in /.venv
COPY Pipfile .
COPY Pipfile.lock .
RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --system


##
#FROM base AS runtime
##
### Copy virtual env from python-deps stage
#COPY --from=python-deps /.venv /.venv
#ENV PATH="/.venv/bin:$PATH"

# Create and switch to a new user to ensure security
#RUN useradd --create-home appuser
#WORKDIR /home/appuser
#USER appuser

# Install application into container
COPY .. .

#FROM base AS production
# Run the application
CMD ["python" ,"-m" ,"flask", "run","--host=0.0.0.0"]
