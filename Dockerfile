FROM python:3.12-alpine

WORKDIR /app

COPY . .

RUN pip install -r requirements.txt --no-cache-dir && \
    apk update && \
    apk add --no-cache bash && \
    chmod +x wait-for-it.sh

EXPOSE 8200

CMD ["bash", "-c", "./wait-for-it.sh $HP_DATABASE_HOST:$HP_DATABASE_PORT --timeout=60 --strict -- python -m main"]
