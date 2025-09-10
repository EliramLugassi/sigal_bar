"""Google Drive helper utilities."""
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import os
from dotenv import load_dotenv


load_dotenv()

# Authenticate only once, store token
def authenticate_drive():
    """Authenticate and return a GoogleDrive instance."""
    gauth = GoogleAuth()
    secret_file = os.getenv("GOOGLE_CLIENT_SECRET_FILE", "client_secrets.json")
    gauth.LoadClientConfigFile(secret_file)
    gauth.LocalWebserverAuth()
    return GoogleDrive(gauth)

def upload_receipt(file_path, file_name, building_id, drive, expense_id=None):
    """Upload a receipt/document and return its shareable link and id."""
    parent_folder = get_or_create_folder(drive, "Receipts")
    building_folder = get_or_create_folder(drive, str(building_id), parent_folder)

    target_folder = building_folder
    if expense_id is not None:
        target_folder = get_or_create_folder(drive, str(expense_id), building_folder)

    file = drive.CreateFile({
        "title": file_name,
        "parents": [{"id": target_folder}],
    })
    file.SetContentFile(file_path)
    file.Upload()

    file.InsertPermission({"type": "anyone", "value": "anyone", "role": "reader"})
    return file["alternateLink"], file["id"]


def delete_file(file_id, drive):
    """Delete a file from Google Drive by its ID."""
    file = drive.CreateFile({"id": file_id})
    file.Delete()

def get_or_create_folder(drive, folder_name, parent_id=None):
    """Fetch or create a folder and return its id."""
    query = f"title='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    file_list = drive.ListFile({'q': query}).GetList()
    if file_list:
        return file_list[0]['id']

    metadata = {'title': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
    if parent_id:
        metadata['parents'] = [{'id': parent_id}]
    folder = drive.CreateFile(metadata)
    folder.Upload()
    return folder['id']
