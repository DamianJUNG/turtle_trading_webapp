# modules/google_sheet_writer.py

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from config import GOOGLE_SHEET_NAME

# 구글 서비스 계정 JSON 파일 경로 (앱 루트에 위치)
SERVICE_ACCOUNT_FILE = "service_account.json"
SCOPES = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def connect_sheet_by_url(sheet_url: str):
    """
    서비스 계정으로 구글시트 연결, 워크시트 객체 반환
    """
    creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_url(sheet_url)
    worksheet = spreadsheet.worksheet(GOOGLE_SHEET_NAME)
    return worksheet

def append_position(worksheet, record: dict):
    """
    record 예시:
    {
        "date": "2025-06-07",
        "code": "005930",
        "name": "삼성전자",
        "entry_price": 79200,
        "quantity": 100,
        "atr": 1200,
        "stop_loss": 76800,
        "next_add_on": 79800
    }
    """
    row = [
        record["date"],
        record["code"],
        record["name"],
        record["entry_price"],
        record["quantity"],
        record["atr"],
        record["stop_loss"],
        record["next_add_on"]
    ]
    worksheet.append_row(row)
