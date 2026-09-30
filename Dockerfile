FROM python:3.10-slim

WORKDIR /app

COPY backend/requirements.txt .

# Install CPU-only PyTorch
RUN pip install --no-cache-dir \
    torch==2.7.1+cpu \
    --extra-index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]