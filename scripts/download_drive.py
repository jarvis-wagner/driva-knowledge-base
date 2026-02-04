#!/usr/bin/env python3
"""
Baixa arquivos do Google Drive compartilhados com jarvis.driva@gmail.com

Uso:
    python scripts/download_drive.py

Requer:
    - google-api-python-client
    - google-auth-oauthlib
    
Configuração:
    - .google_token.json (OAuth tokens)
"""
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import json
import io
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
TOKEN_FILE = BASE_DIR.parent / ".google_token.json"
OUTPUT_DIR = BASE_DIR / "source_files"


def get_credentials():
    """Carrega credenciais OAuth"""
    with open(TOKEN_FILE, 'r') as f:
        token_data = json.load(f)
    
    return Credentials(
        token=token_data['token'],
        refresh_token=token_data['refresh_token'],
        token_uri=token_data['token_uri'],
        client_id=token_data['client_id'],
        client_secret=token_data['client_secret'],
        scopes=token_data['scopes']
    )


def list_shared_files(service):
    """Lista arquivos compartilhados"""
    results = service.files().list(
        q="sharedWithMe=true",
        fields="files(id, name, mimeType, size)",
        pageSize=100
    ).execute()
    return results.get('files', [])


def download_file(service, file_id, filename, output_dir):
    """Baixa um arquivo do Drive"""
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    
    done = False
    while not done:
        status, done = downloader.next_chunk()
    
    fh.seek(0)
    output_path = output_dir / filename
    output_path.write_bytes(fh.read())
    return output_path


def main():
    print("🔐 Carregando credenciais...")
    creds = get_credentials()
    
    print("📡 Conectando ao Google Drive...")
    service = build('drive', 'v3', credentials=creds)
    
    print("🔍 Listando arquivos compartilhados...\n")
    files = list_shared_files(service)
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    for f in files:
        print(f"📄 {f['name']}")
        print(f"   Tipo: {f['mimeType']}")
        
        # Baixar se for arquivo (não pasta)
        if 'folder' not in f['mimeType']:
            try:
                path = download_file(service, f['id'], f['name'], OUTPUT_DIR)
                print(f"   ✅ Baixado: {path}")
            except Exception as e:
                print(f"   ❌ Erro: {e}")
        print()
    
    print(f"📁 Arquivos salvos em: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
