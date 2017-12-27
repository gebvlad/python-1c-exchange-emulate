FROM python:2.7-alpine3.7

MAINTAINER Maks Ze <max.webdew@gmail.com>

RUN pip install requests
RUN pip install termcolor

COPY ./exchange.py /opt/exchange-emulate/exchange.py

WORKDIR /opt/exchange-files

ENTRYPOINT ["python", "/opt/exchange-emulate/exchange.py"]
