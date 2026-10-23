FROM nvcr.io/nvidia/tao/tao-toolkit:6.26.3-pyt

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV ULTRALYTICS_DATA_ROOT=/shared-storage \
    ULTRALYTICS_MODEL_ROOT=/shared-storage/models \
    ULTRALYTICS_JOB_ROOT=/shared-storage/ultralytics-jobs \
    ULTRALYTICS_DEVICE=0

EXPOSE 9200
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9200"]
