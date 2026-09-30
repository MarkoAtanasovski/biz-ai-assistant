FROM python:3.12-slim
WORKDIR /app
# requirements.txt rarely changes, so this layer is reused unless you
# actually add/remove a package.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py ./
# Don't run as root inside the container.
RUN useradd --create-home app
USER app
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
