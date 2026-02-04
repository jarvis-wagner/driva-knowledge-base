#!/usr/bin/env python3
"""
Processa o Catálogo de Dados da Driva e gera arquivos .md

Uso:
    python scripts/process_catalogo.py

Requer:
    - pandas
    - openpyxl
"""
import pandas as pd
import os
from pathlib import Path

# Caminhos
BASE_DIR = Path(__file__).parent.parent
SOURCE_FILE = BASE_DIR / "source_files" / "catalogo_dados.xlsx"
OUTPUT_DIR = BASE_DIR / "produtos" / "datapacks"

# Mapeamento de abas para arquivos
ABA_PARA_ARQUIVO = {
    '1. Dados Cadastrais - CNPJ': 'cnpj.md',
    '1. Dados Cadastrais - Social': 'social.md',
    '2. Nicho - Processos Judiciais': 'processos-judiciais.md',
    '2. Nicho - Fiscal': 'fiscal.md',
    '2. Nicho - Energia': 'energia.md',
    '2. Nicho - Contadores': 'contadores.md',
    '2. Nicho - Frotas': 'frotas.md',
    '2. Nicho - E-commerce': 'ecommerce.md',
    '2. Nicho - Beneficios': 'beneficios.md',
    '2. Nicho - ERP': 'erp.md',
    '2. Nicho - Food Service': 'foodservice.md',
    '2. Nicho - Geolocalizacao': 'geolocalizacao.md',
    '2. Nicho - Saúde Animal': 'saude-animal.md',
    '2. Nicho - Agro': 'agro.md',
    '2. Nicho - Resíduos': 'residuos.md',
    '2. Nicho - Marcas Registradas': 'marcas.md',
    '3. Contatos - Empresas': 'contatos-empresas.md',
    '3. Contatos - Pessoas': 'contatos-pessoas.md',
    'Licitacoes': 'licitacoes.md',
    'Dicionario_Educacao': 'educacao.md',
    'Dicionario_Obras': 'obras.md',
    'Dicionario_Saude': 'saude.md',
}


def gerar_md(aba_nome: str, df: pd.DataFrame) -> str | None:
    """Gera conteúdo markdown a partir dos dados da aba"""
    
    # Limpar nome para título
    titulo = aba_nome.replace('1. ', '').replace('2. ', '').replace('3. ', '')
    titulo = titulo.replace('Nicho - ', '').replace('Dicionario_', '')
    
    # Identificar colunas
    col_campo = col_descricao = col_plano = None
    
    for col in df.columns:
        col_lower = str(col).lower()
        if 'campo' in col_lower:
            col_campo = col
        elif 'descri' in col_lower:
            col_descricao = col
        elif 'disponível' in col_lower or 'plano' in col_lower:
            col_plano = col
    
    if not col_campo or not col_descricao:
        return None
    
    # Gerar conteúdo
    md = f"# {titulo}\n\n"
    md += f"> Datapack de dados da Driva\n\n"
    md += f"## Visão Geral\n\n"
    md += f"- **Total de campos:** {len(df)}\n"
    
    if col_plano:
        planos = df[col_plano].dropna().unique()
        if len(planos) > 0:
            md += f"- **Disponível em:** {', '.join(str(p) for p in planos)}\n"
    
    md += f"\n## Campos Disponíveis\n\n"
    md += f"| Campo | Descrição |\n"
    md += f"|-------|----------|\n"
    
    for _, row in df.iterrows():
        campo = str(row.get(col_campo, '')).strip()
        descricao = str(row.get(col_descricao, '')).strip()
        
        if campo and campo != 'nan':
            campo = campo.replace('|', '\\|')
            descricao = descricao.replace('|', '\\|') if descricao != 'nan' else ''
            md += f"| {campo} | {descricao} |\n"
    
    md += f"\n---\n\n*Gerado automaticamente a partir do Catálogo de Dados Driva*\n"
    
    return md


def main():
    print(f"📂 Lendo: {SOURCE_FILE}")
    
    if not SOURCE_FILE.exists():
        print(f"❌ Arquivo não encontrado: {SOURCE_FILE}")
        return
    
    xlsx = pd.ExcelFile(SOURCE_FILE)
    print(f"📋 Abas encontradas: {len(xlsx.sheet_names)}")
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    gerados = 0
    for aba, arquivo in ABA_PARA_ARQUIVO.items():
        if aba in xlsx.sheet_names:
            df = pd.read_excel(xlsx, sheet_name=aba)
            if len(df) > 0:
                md_content = gerar_md(aba, df)
                if md_content:
                    filepath = OUTPUT_DIR / arquivo
                    filepath.write_text(md_content, encoding='utf-8')
                    print(f"✅ {arquivo} ({len(df)} campos)")
                    gerados += 1
    
    print(f"\n📊 Total: {gerados} arquivos gerados em {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
