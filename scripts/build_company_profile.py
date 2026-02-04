#!/usr/bin/env python3
"""
Build Driva Company Profile
===========================

Coleta dados do site da Driva e gera documento estruturado sobre a empresa.

Uso:
    python build_company_profile.py
    python build_company_profile.py --api-key <key>
    OPENAI_API_KEY=<key> python build_company_profile.py
"""

import os
import sys
import argparse
import requests
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("❌ OpenAI library not found. Install with: pip install openai")
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("❌ BeautifulSoup not found. Install with: pip install beautifulsoup4")
    sys.exit(1)


REPO_ROOT = Path(__file__).parent.parent
OUTPUT_FILE = REPO_ROOT / "empresa" / "sobre.md"

URLS_TO_SCRAPE = [
    "https://www.driva.io/",
    "https://www.driva.io/inteligencia-de-mercado",
    "https://www.driva.io/geracao-de-leads",
    "https://www.driva.io/engajamento",
    "https://www.driva.io/driva-copilot",
    "https://www.driva.io/blog",
]


def scrape_url(url: str) -> str:
    """Scrape text content from a URL"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer"]):
            script.decompose()
        
        text = soup.get_text(separator='\n', strip=True)
        # Limit size
        return text[:8000]
    except Exception as e:
        return f"Erro ao acessar {url}: {e}"


def collect_site_data() -> str:
    """Collect data from all URLs"""
    print("📡 Coletando dados do site...")
    
    all_data = []
    for url in URLS_TO_SCRAPE:
        print(f"   → {url}")
        content = scrape_url(url)
        all_data.append(f"=== {url} ===\n{content}\n")
    
    return "\n".join(all_data)


def generate_profile(client: OpenAI, site_data: str) -> str:
    """Generate company profile using LLM"""
    print("🤖 Gerando perfil com GPT-4o...")
    
    prompt = f"""Com base nos dados coletados do site da Driva, crie um documento markdown completo e profissional sobre a empresa.

O documento deve incluir:

1. **Visão Geral** - O que é a Driva, proposta de valor
2. **Missão e Posicionamento** - Baseado no que a empresa comunica
3. **Produtos e Soluções** (Copilot, Inteligência de Mercado, Geração de Leads, Engajamento)
4. **Bases de Dados Exclusivas** - As bases proprietárias mencionadas
5. **Números e Métricas** - Os números divulgados
6. **Diferenciais Competitivos**
7. **Processo de Trabalho** - Como funciona o onboarding
8. **Casos de Sucesso** - Depoimentos de clientes
9. **Conteúdo e Thought Leadership** - Blog e temas

IMPORTANTE:
- Use português brasileiro
- Seja factual, use apenas informações do site
- Formate bem com headers, bullets, tabelas e citações
- O documento será usado para treinar IA sobre a empresa

DADOS DO SITE:
{site_data}
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Você é um especialista em criar documentação empresarial estruturada."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=4000
    )
    
    return response.choices[0].message.content


def main():
    parser = argparse.ArgumentParser(description="Build Driva company profile")
    parser.add_argument("--api-key", help="OpenAI API key")
    args = parser.parse_args()
    
    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("❌ API key required. Use --api-key or set OPENAI_API_KEY")
        sys.exit(1)
    
    client = OpenAI(api_key=api_key)
    
    # Collect data
    site_data = collect_site_data()
    
    # Generate profile
    content = generate_profile(client, site_data)
    
    # Build final document
    urls_list = "\n".join([f"- {url}" for url in URLS_TO_SCRAPE])
    
    full_content = f"""# Driva - Perfil da Empresa

> Documento gerado automaticamente a partir de dados coletados do site oficial (driva.io)
> Última atualização: Gerado por script

---

{content}

---

## Fontes

{urls_list}
"""
    
    # Save
    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    OUTPUT_FILE.write_text(full_content, encoding='utf-8')
    
    print(f"✅ Salvo em: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
