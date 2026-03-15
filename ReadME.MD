# IoT Health Care Project

Backend service for an IoT-based health monitoring system built with FastAPI.

This project sets up a lightweight API server that can receive and process data from IoT health devices (e.g., heart rate monitors, temperature sensors, etc.).

---

# Status

**Completed**
Core FastAPI server setup is completed. IoT data ingestion and processing added.

---

#  Tech Stack

* **FastAPI** — modern high-performance Python API framework
* **Uvicorn** — ASGI server for running FastAPI applications
* **Python 3.10+**

---

# Project Setup

## 1. Clone the Repository

```bash
git clone https://github.com/imashu001/IoT_health.git
cd IoT_health
```

---

## 2. Create Virtual Environment

```bash
py -m venv venv
```

This creates an isolated Python environment inside the project.

```
venv/
```

---

## 3. Activate Virtual Environment

### Windows

```bash
venv\Scripts\activate
```

After activation your terminal should look like:

```
(venv) C:\Users\your_user\IoT_health>
```

---

## 4. Install Dependencies

Install all required packages using:

```bash
pip install -r requirements.txt
```

---

# ENV variable replace:
add the connection string and the db name in the env file.

# Running the Server

Start the FastAPI server using:

```bash
uvicorn main:app --reload
```

Explanation:

| Component  | Meaning                            |
| ---------- | ---------------------------------- |
| `main`     | Python file (`main.py`)            |
| `app`      | FastAPI instance                   |
| `--reload` | Auto reload server on code changes |

---

# API Documentation

FastAPI automatically generates interactive documentation.

### Swagger UI

```http://127.0.0.1:8000/docs```

This allows you to test API endpoints directly from the browser.

---

# for auth login:
for auth login use this body as mentioned in the project document:
{
  "username": "admin",
  "password": "password"
}
this would give the auth token set it in swagger top right corner and you can use any api .
the timeout of token is set to 10 minutes for now can be changed in dbutils file


#  UNIT TESTS -->
-- to run the unit test
use ```pytest```
-- to check the coverage
use ```pytest --cov=main --cov-report=html```
and to open the html in browser use : ```start htmlcov/index.html```