
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import pandas as pd
import json
import uuid

# --------------------------------------------------
# FOLDERS
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

METADATA_FILE = DATA_DIR / "datasets.json"


# --------------------------------------------------
# FASTAPI APP
# --------------------------------------------------

app = FastAPI(
    title="DABI AI",
    description="AI Data Analyst Backend",
    version="1.0.0"
)


# --------------------------------------------------
# CORS
# Allows your Google AI Studio frontend to connect
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# METADATA FUNCTIONS
# --------------------------------------------------

def load_metadata():
    if not METADATA_FILE.exists():
        return {
            "datasets": [],
            "active_dataset_id": None
        }

    with open(METADATA_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def save_metadata(metadata):
    with open(METADATA_FILE, "w", encoding="utf-8") as file:
        json.dump(metadata, file, indent=4)


# --------------------------------------------------
# HOME
# --------------------------------------------------

@app.get("/")
def home():
    return {
        "message": "DABI AI Backend is running!",
        "status": "success"
    }


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


# --------------------------------------------------
# UPLOAD DATASET
# --------------------------------------------------

@app.post("/datasets/upload")
async def upload_dataset(file: UploadFile = File(...)):

    allowed_extensions = [".csv", ".xlsx", ".xls"]

    original_name = file.filename or "dataset"
    extension = Path(original_name).suffix.lower()

    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Only CSV, XLSX and XLS files are allowed."
        )

    dataset_id = "ds_" + uuid.uuid4().hex[:8]

    stored_name = dataset_id + extension
    file_path = DATA_DIR / stored_name

    contents = await file.read()

    with open(file_path, "wb") as output:
        output.write(contents)

    try:
        if extension == ".csv":
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)

    except Exception as error:
        file_path.unlink(missing_ok=True)

        raise HTTPException(
            status_code=400,
            detail=f"Could not read dataset: {str(error)}"
        )

    metadata = load_metadata()

    dataset_info = {
        "dataset_id": dataset_id,
        "original_name": original_name,
        "stored_name": stored_name,
        "rows": int(df.shape[0]),
        "columns": int(df.shape[1]),
        "column_names": df.columns.tolist()
    }

    metadata["datasets"].append(dataset_info)

    # Automatically make new upload active
    metadata["active_dataset_id"] = dataset_id

    save_metadata(metadata)

    return {
        "message": "Dataset uploaded successfully.",
        "dataset": dataset_info,
        "active": True
    }


# --------------------------------------------------
# LIST ALL DATASETS
# --------------------------------------------------

@app.get("/datasets")
def get_datasets():

    metadata = load_metadata()

    return {
        "active_dataset_id": metadata["active_dataset_id"],
        "datasets": metadata["datasets"]
    }


# --------------------------------------------------
# SWITCH ACTIVE DATASET
# --------------------------------------------------

@app.put("/datasets/{dataset_id}/activate")
def activate_dataset(dataset_id: str):

    metadata = load_metadata()

    dataset = next(
        (
            item
            for item in metadata["datasets"]
            if item["dataset_id"] == dataset_id
        ),
        None
    )

    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found."
        )

    metadata["active_dataset_id"] = dataset_id
    save_metadata(metadata)

    return {
        "message": f"Dataset switched to {dataset['original_name']}.",
        "active_dataset_id": dataset_id,
        "dataset": dataset
    }


# --------------------------------------------------
# GET ACTIVE DATASET DATA
# --------------------------------------------------

@app.get("/datasets/active/data")
def get_active_dataset_data():

    metadata = load_metadata()

    active_id = metadata["active_dataset_id"]

    if active_id is None:
        raise HTTPException(
            status_code=404,
            detail="No active dataset."
        )

    dataset = next(
        (
            item
            for item in metadata["datasets"]
            if item["dataset_id"] == active_id
        ),
        None
    )

    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail="Active dataset not found."
        )

    file_path = DATA_DIR / dataset["stored_name"]

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Dataset file not found."
        )

    try:
        extension = file_path.suffix.lower()

        if extension == ".csv":
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)

    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=f"Could not read dataset: {str(error)}"
        )

    # Convert data to JSON-compatible format
    df = df.where(pd.notnull(df), None)

    return {
        "dataset_id": active_id,
        "name": dataset["original_name"],
        "rows": int(df.shape[0]),
        "columns": int(df.shape[1]),
        "column_names": df.columns.tolist(),
        "data": df.to_dict(orient="records")
    }



# --------------------------------------------------
# DELETE DATASET
# --------------------------------------------------

@app.delete("/datasets/{dataset_id}")
def delete_dataset(dataset_id: str):

    metadata = load_metadata()

    dataset = next(
        (
            item
            for item in metadata["datasets"]
            if item["dataset_id"] == dataset_id
        ),
        None
    )

    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found."
        )

    # Prevent deleting active dataset
    if metadata["active_dataset_id"] == dataset_id:
        raise HTTPException(
            status_code=400,
            detail="Active dataset cannot be deleted. Switch to another dataset first."
        )

    file_path = DATA_DIR / dataset["stored_name"]

    if file_path.exists():
        file_path.unlink()

    metadata["datasets"] = [
        item
        for item in metadata["datasets"]
        if item["dataset_id"] != dataset_id
    ]

    save_metadata(metadata)

    return {
        "message": f"Dataset '{dataset['original_name']}' deleted successfully."
    }
