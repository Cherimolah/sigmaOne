import os

from dotenv import load_dotenv


load_dotenv()


PG_USER = os.getenv('PG_USER')
PG_PASSWORD = os.getenv('PG_PASSWORD')
DB_NAME = os.getenv('DB_NAME')
