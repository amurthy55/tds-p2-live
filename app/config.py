import os
from pathlib import Path
from dotenv import load_dotenv


# Always load .env from project root
env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=env_path,override=True)

STUDENT_EMAIL = "25ds2000003@ds.study.iitm.ac.in"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AIPIPE_API_KEY = os.getenv("AIPIPE_API_KEY")
STUDENT_SECRET = os.getenv("STUDENT_SECRET")

