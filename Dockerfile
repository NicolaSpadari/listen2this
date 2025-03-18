FROM python:3.10

WORKDIR /app

# Copia i requisiti e installa le dipendenze Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia lo script dell'applicazione
COPY main.py .

# Comando di avvio
CMD ["python", "main.py"]
