from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import os
import json
import uuid
import pandas as pd
app = FastAPI(title="DABI AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
METADATA_FILE = os.path.join(BASE_DIR, "datasets.json")

os.makedirs(DATA_DIR, exist_ok=True)


def load_datasets():
    if not os.path.exists(METADATA_FILE):
        return []

    with open(METADATA_FILE, "r") as f:
        return json.load(f)


def save_datasets(datasets):
    with open(METADATA_FILE, "w") as f:
        json.dump(datasets, f, indent=4)


@app.get("/")
def home():
    return {
        "message": "DABI AI Backend is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.post("/datasets/upload")
async def upload_dataset(file: UploadFile = File(...)):
    allowed_extensions = [".csv", ".xlsx", ".xls"]

    filename = file.filename
    extension = os.path.splitext(filename)[1].lower()

    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Only CSV and Excel files are allowed."
        )

    dataset_id = "ds_" + uuid.uuid4().hex[:8]

    saved_filename = dataset_id + "_" + filename
    file_path = os.path.join(DATA_DIR, saved_filename)

    contents = await file.read()

    with open(file_path, "wb") as f:
        f.write(contents)

    try:
        if extension == ".csv":
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)

    except Exception as e:
        os.remove(file_path)
        raise HTTPException(
            status_code=400,
            detail=f"Could not read dataset: {str(e)}"
        )

    datasets = load_datasets()

    for dataset in datasets:
        dataset["active"] = False

    new_dataset = {
        "id": dataset_id,
        "filename": filename,
        "stored_filename": saved_filename,
        "rows": len(df),
        "columns": len(df.columns),
        "active": True
    }

    datasets.append(new_dataset)
    save_datasets(datasets)

    return new_dataset


@app.get("/datasets")
def get_datasets():
    return load_datasets()


@app.get("/datasets/active")
def get_active_dataset():
    datasets = load_datasets()

    for dataset in datasets:
        if dataset.get("active"):
            return dataset

    return {
        "message": "No active dataset"
    }


@app.put("/datasets/{dataset_id}/activate")
def activate_dataset(dataset_id: str):
    datasets = load_datasets()

    found = False

    for dataset in datasets:
        if dataset["id"] == dataset_id:
            dataset["active"] = True
            found = True
        else:
            dataset["active"] = False

    if not found:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found"
        )

    save_datasets(datasets)

    return {
        "message": "Dataset activated",
        "dataset_id": dataset_id
    }


@app.delete("/datasets/{dataset_id}")
def delete_dataset(dataset_id: str):
    datasets = load_datasets()

    dataset_to_delete = None

    for dataset in datasets:
        if dataset["id"] == dataset_id:
            dataset_to_delete = dataset
            break

    if dataset_to_delete is None:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found"
        )

    if dataset_to_delete.get("active"):
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the active dataset. Activate another dataset first."
        )

    file_path = os.path.join(
        DATA_DIR,
        dataset_to_delete["stored_filename"]
    )

    if os.path.exists(file_path):
        os.remove(file_path)

    datasets.remove(dataset_to_delete)
    save_datasets(datasets)

    return {
        "message": "Dataset deleted",
        "dataset_id": dataset_id
    }