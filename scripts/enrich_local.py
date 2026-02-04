#!/usr/bin/env python3
"""
Script para processamento básico da Driva Knowledge Base
Estrutura os materiais sem usar API externa
"""

import os
import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class SourceFile:
    """Representa um arquivo fonte para processamento"""
    path: Path
    type: str  # 'datapack', 'commercial', 'training', 'summary'
    product_name: str
    content: str

class DatapackProcessor:
    """Classe para processamento local dos datapacks"""
    
    def __init__(self, base_path: str, output_path: str):
        self.base_path = Path(base_path)
        self.output_path = Path(output_path)
        
    def _discover_files(self) -> Dict[str, List[SourceFile]]:
        """Descobre e categoriza todos os arquivos de origem"""
        files_by_product = {}
        
        # Datapacks
        datapacks_dir = self.base_path / 'produtos' / 'datapacks'
        if datapacks_dir.exists():
            for file_path in datapacks_dir.glob('*.md'):
                if file_path.name == 'README.md':
                    continue
                product_name = file_path.stem
                content = file_path.read_text(encoding='utf-8')
                
                if product_name not in files_by_product:
                    files_by_product[product_name] = []
                
                files_by_product[product_name].append(
                    SourceFile(file_path, 'datapack', product_name, content)
                )
        
        return files_by_product
    
    def _extract_datapack_info(self, content: str) -> Dict[str, any]:
        """Extrai informações estruturadas de um datapack"""
        info = {
            'description': '',
            'total_fields': '',
            'plans': [],
            'fields': [],
            'categories': []
        }
        
        lines = content.split('\n')
        current_section = None
        in_table = False
        
        for line in lines:
            line = line.strip()
            
            # Título principal
            if line.startswith('# '):
                info['title'] = line[2:].strip()
            
            # Total de campos
            if 'Total de campos:' in line:
                match = re.search(r'\*\*Total de campos:\*\* (\d+)', line)
                if match:
                    info['total_fields'] = match.group(1)
            
            # Disponibilidade nos planos
            if 'Disponível em:' in line:
                plans_text = line.split('Disponível em:')[-1].strip()
                info['plans'] = [p.strip() for p in plans_text.split(',')]
            
            # Tabela de campos
            if '| Campo | Descrição |' in line:
                in_table = True
                continue
            
            if in_table and line.startswith('|') and line.count('|') >= 3:
                parts = [p.strip() for p in line.split('|')[1:-1]]
                if len(parts) >= 2 and parts[0] != 'Campo':
                    info['fields'].append({
                        'name': parts[0],
                        'description': parts[1]
                    })
            elif in_table and not line.startswith('|'):
                in_table = False
        
        return info
    
    def _generate_enriched_content(self, product_name: str, sources: List[SourceFile]) -> str:
        """Gera conteúdo enriquecido baseado nos arquivos fonte"""
        
        # Para datapacks, extrair informações estruturadas
        datapack_info = None
        for source in sources:
            if source.type == 'datapack':
                datapack_info = self._extract_datapack_info(source.content)
                break
        
        if not datapack_info:
            return f"# {product_name.title()}\n\nNão foi possível processar este produto."
        
        content = f"""# {product_name.title().replace('-', ' ').title()}

## Descrição Geral
{datapack_info.get('title', product_name)} - Datapack da Driva com dados estruturados para inteligência de mercado.

## Dados e Campos Disponíveis
Total de campos: {datapack_info.get('total_fields', 'Não especificado')}

### Campos Principais
"""
        
        # Adicionar primeiros 10 campos como exemplo
        fields = datapack_info.get('fields', [])[:10]
        if fields:
            content += "\n| Campo | Descrição |\n|-------|----------|\n"
            for field in fields:
                content += f"| {field['name']} | {field['description']} |\n"
        
        if len(datapack_info.get('fields', [])) > 10:
            content += f"\n*E mais {len(datapack_info.get('fields', [])) - 10} campos adicionais...*\n"
        
        # Planos disponíveis
        plans = datapack_info.get('plans', [])
        if plans:
            content += f"\n## Planos Disponíveis\n"
            for plan in plans:
                content += f"- {plan.strip()}\n"
        
        content += f"""
## Casos de Uso Práticos
Este datapack pode ser utilizado para:
- Enriquecimento de bases de dados existentes
- Análise de mercado e inteligência comercial
- Segmentação e targeting de clientes
- Due diligence e análise de risco

## Público-Alvo
- Empresas de tecnologia
- Consultorias e agências
- Instituições financeiras
- Departamentos de vendas e marketing

## Integração com Outros Produtos
Este produto pode ser combinado com outros datapacks da Driva para análises mais abrangentes e insights mais profundos.

## Informações Técnicas
- Formato: API REST e exportação em formatos estruturados
- Atualização: Conforme especificação do produto
- Volume: {datapack_info.get('total_fields', 'Consultar documentação')} campos disponíveis

## Última Atualização
Processado em {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC
"""
        
        return content
    
    def _save_enriched_content(self, product_name: str, content: str):
        """Salva conteúdo processado"""
        output_file = self.output_path / f"{product_name}.md"
        output_file.write_text(content, encoding='utf-8')
        print(f"✅ Processado: {product_name}")
    
    def _generate_index(self, processed_products: List[str]):
        """Gera índice/README com visão geral"""
        index_content = f"""# Driva Knowledge Base - Produtos Processados

*Documentação estruturada gerada em {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*

## Produtos Disponíveis

Total de produtos: {len(processed_products)}

"""
        
        for product in sorted(processed_products):
            product_title = product.replace('-', ' ').title()
            index_content += f"- [{product_title}]({product}.md)\n"
        
        index_content += f"""
## Sobre Este Repositório

Esta documentação foi processada automaticamente a partir dos datapacks brutos da Driva Knowledge Base.

O processamento incluiu:
- Extração de metadados técnicos
- Estruturação de campos e descrições
- Organização em formato padronizado
- Geração de índice navegável

## Última Atualização

{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC
"""
        
        index_file = self.output_path / "README.md"
        index_file.write_text(index_content, encoding='utf-8')
        print(f"📋 Índice gerado: {index_file}")
    
    def process_all(self):
        """Processa todos os produtos"""
        print("🚀 Iniciando processamento local...")
        
        # Descobrir arquivos
        files_by_product = self._discover_files()
        print(f"📁 Encontrados {len(files_by_product)} produtos para processar")
        
        processed_products = []
        
        for product_name, sources in files_by_product.items():
            try:
                print(f"⏳ Processando {product_name}...")
                
                # Processar conteúdo
                enriched_content = self._generate_enriched_content(product_name, sources)
                
                # Salvar resultado
                self._save_enriched_content(product_name, enriched_content)
                processed_products.append(product_name)
                
            except Exception as e:
                print(f"❌ Erro ao processar {product_name}: {str(e)}")
                continue
        
        # Gerar índice
        if processed_products:
            self._generate_index(processed_products)
        
        print(f"✅ Processamento concluído! {len(processed_products)} produtos processados.")

def main():
    """Função principal"""
    base_path = "/root/.openclaw/workspace/driva-knowledge-base"
    output_path = "/root/.openclaw/workspace/driva-knowledge-base/produtos/enriched"
    
    # Criar diretório de output se não existir
    Path(output_path).mkdir(parents=True, exist_ok=True)
    
    # Inicializar e executar processador
    processor = DatapackProcessor(base_path, output_path)
    processor.process_all()

if __name__ == "__main__":
    main()