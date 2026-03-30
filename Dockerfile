FROM python:3.14-slim 


ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1


WORKDIR /app

COPY ./requirements /app/requirements 



RUN apt-get update && apt-get install -y binutils libproj-dev gdal-bin

RUN pip install --upgrade pip 

RUN pip install -r requirements/local.txt


COPY . /app/

# Ensure temp upload directory exists in the built image.
RUN mkdir -p /app/tmp_uploads

COPY ./entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
