FROM python:latest

# Copy the files
WORKDIR /app
ADD . .

# Dependencies
RUN pip install -r requirements.txt
RUN python -m spacy download en_core_web_sm

# Run
EXPOSE 7777
CMD ["python", "base.py"]