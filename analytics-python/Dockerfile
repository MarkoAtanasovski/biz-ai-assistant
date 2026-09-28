FROM python:3.12-slim
WORKDIR /app
# Same caching idea as the Java build: requirements.txt rarely changes,
# so this layer is reused unless you actually add/remove a package.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
