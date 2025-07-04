FROM python:3.12-alpine
RUN apk update \
  && apk add \
    build-base \
    ffmpeg
RUN mkdir /app
WORKDIR /app
COPY ./requirements.txt .
RUN pip install -r requirements.txt
ENV PYTHONUNBUFFERED 1
COPY . .
RUN addgroup -g 1000 -S epworker && \
    adduser -u 1000 -S epworker -G epworker
USER epworker
CMD ["python", "main.py"]
