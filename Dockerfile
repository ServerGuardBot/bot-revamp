FROM python:3.11.8

# Copy the files
WORKDIR /app
ADD . .

# Dependencies
RUN apt update && \
    apt install --no-install-recommends -y \
        rustup \
        git \
    rustup default stable && \
    export RUSTFLAGS='--cfg surrealdb_unstable' && \
    cargo install surrealdb-migrations && \
    pip install -r requirements.txt && \
    python -m spacy download en_core_web_sm

VOLUME /tmp

# Run
EXPOSE 7777
CMD ["python", "base.py"]