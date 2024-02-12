FROM python:latest

# Copy the files
WORKDIR /app
ADD . .

# Dependencies
RUN pip install -r requirements.txt

# Run
EXPOSE 7777
CMD ["python", "base.py"]