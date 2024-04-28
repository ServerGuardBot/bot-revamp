FROM python:3.11.8

# Copy the files
WORKDIR /app
ADD src .
ADD database .
ADD .surrealdb .

# Dependencies
RUN apt update && \
    apt install --no-install-recommends -y \
        git

RUN curl https://sh.rustup.rs -sSf | sh -s -- -y

ENV PATH="/root/.cargo/bin:${PATH}"

RUN rustup default stable && \
    export RUSTFLAGS='--cfg surrealdb_unstable' && \
    cargo install surrealdb-migrations && \
    pip install -r requirements.txt && \
    python -m spacy download en_core_web_sm

VOLUME /tmp

# Run
EXPOSE 7777
CMD ["python", "src/base.py"]