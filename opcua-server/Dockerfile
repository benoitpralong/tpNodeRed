FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --trusted-host pypi.org \
                --trusted-host files.pythonhosted.org \
                --no-cache-dir -r requirements.txt

COPY server.py .

EXPOSE 4840

CMD ["python", "server.py"]