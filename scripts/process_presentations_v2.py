#!/usr/bin/env python3
"""
Extrai texto de apresentações usando Google Slides API diretamente
(Sem precisar baixar o arquivo)
"""
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
TOKEN_FILE = BASE_DIR.parent / ".google_token.json"
OUTPUT_DIR = BASE_DIR / "produtos" / "apresentacoes"
FOLDER_ID = "14hZDQzNs5gq6b_u5kM0NH77wTZvKWBTY"


def get_credentials():
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


def list_presentations(drive_service, folder_id, path=""):
    """Lista apresentações recursivamente"""
    presentations = []
    
    results = drive_service.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        fields="files(id, name, mimeType)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        pageSize=100
    ).execute()
    
    for f in results.get('files', []):
        current_path = f"{path}/{f['name']}" if path else f['name']
        
        if f['mimeType'] == 'application/vnd.google-apps.folder':
            presentations.extend(list_presentations(drive_service, f['id'], current_path))
        elif f['mimeType'] == 'application/vnd.google-apps.presentation':
            presentations.append({
                'id': f['id'],
                'name': f['name'],
                'path': current_path
            })
    
    return presentations


def extract_text_from_slides(slides_service, presentation_id):
    """Extrai texto usando Google Slides API"""
    presentation = slides_service.presentations().get(
        presentationId=presentation_id
    ).execute()
    
    slides_content = []
    
    for i, slide in enumerate(presentation.get('slides', []), 1):
        slide_text = []
        
        for element in slide.get('pageElements', []):
            # Extrair texto de shapes
            if 'shape' in element:
                shape = element['shape']
                if 'text' in shape:
                    for text_elem in shape['text'].get('textElements', []):
                        if 'textRun' in text_elem:
                            content = text_elem['textRun'].get('content', '').strip()
                            if content:
                                slide_text.append(content)
            
            # Extrair texto de tabelas
            if 'table' in element:
                table = element['table']
                for row in table.get('tableRows', []):
                    for cell in row.get('tableCells', []):
                        if 'text' in cell:
                            for text_elem in cell['text'].get('textElements', []):
                                if 'textRun' in text_elem:
                                    content = text_elem['textRun'].get('content', '').strip()
                                    if content:
                                        slide_text.append(content)
        
        if slide_text:
            slides_content.append({
                'slide': i,
                'content': slide_text
            })
    
    return slides_content


def generate_markdown(name, path, slides):
    """Gera markdown"""
    md = f"# {name}\n\n"
    md += f"> Fonte: {path}\n\n"
    md += "---\n\n"
    
    for slide in slides:
        md += f"## Slide {slide['slide']}\n\n"
        for text in slide['content']:
            text = text.replace('\n', ' ').strip()
            if text:
                md += f"- {text}\n"
        md += "\n---\n\n"
    
    return md


def main():
    print("🔐 Carregando credenciais...")
    creds = get_credentials()
    
    drive_service = build('drive', 'v3', credentials=creds)
    slides_service = build('slides', 'v1', credentials=creds)
    
    print("🔍 Listando apresentações...")
    presentations = list_presentations(drive_service, FOLDER_ID)
    print(f"   Encontradas: {len(presentations)}\n")
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    processed = 0
    for pres in presentations:
        print(f"📄 {pres['name'][:50]}...")
        
        try:
            slides = extract_text_from_slides(slides_service, pres['id'])
            print(f"   📝 {len(slides)} slides com conteúdo")
            
            md_content = generate_markdown(pres['name'], pres['path'], slides)
            
            safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in pres['name'])
            md_path = OUTPUT_DIR / f"{safe_name}.md"
            md_path.write_text(md_content, encoding='utf-8')
            print(f"   💾 Salvo!")
            
            processed += 1
            
        except Exception as e:
            print(f"   ❌ Erro: {e}")
        
        print()
    
    print(f"✅ Processadas: {processed}/{len(presentations)}")


if __name__ == "__main__":
    main()
