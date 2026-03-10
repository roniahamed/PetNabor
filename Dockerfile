FROM python:3.14-slim 


ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1


WORKDIR /app

COPY ./requirements /app/requirements 



RUN pip install --upgrade pip 

RUN pip install -r requirements/local.txt


COPY . /app/

