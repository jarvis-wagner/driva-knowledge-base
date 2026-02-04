#!/usr/bin/env python3
"""
Script para enriquecimento da Driva Knowledge Base usando Claude API
Processa materiais brutos e gera documentos estruturados para consumo por IA
"""

import os
import json
import time
import logging
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

import anthropic
from anthropic import Anthropic

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('enrich_progress.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class SourceFile:
    """Representa um arquivo fonte para processamento"""
    path: Path
    type: str  # 'datapack', 'commercial', 'training', 'summary'
    product_name: str
    content: str

@dataclass
class ProcessingCache:
    """Cache para retomar processamento"""
    processed_files: List[str]
    failed_files: List[str]
    last_update: str

class DatapackEnricher:
    """Classe principal para enriquecimento dos datapacks"""
    
    def __init__(self, base_path: str, output_path: str):
        self.base_path = Path(base_path)
        self.output_path = Path(output_path)
        self.client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        self.cache_file = Path('processing_cache.json')
        self.cache = self._load_cache()
        
        # Rate limiting (Claude API limits)
        self.request_delay = 1.0  # 1 segundo entre requests
        self.last_request_time = 0
        
    def _load_cache(self) -> ProcessingCache:
        """Carrega cache de processamento"""
        if self.cache_file.exists():
            with open(self.cache_file, 'r') as f:
                data = json.load(f)
                return ProcessingCache(**data)
        return ProcessingCache([], [], datetime.now().isoformat())
    
    def _save_cache(self):
        """Salva cache de processamento"""
        with open(self.cache_file, 'w') as f:
            json.dump({
                'processed_files': self.cache.processed_files,
                'failed_files': self.cache.failed_files,
                'last_update': datetime.now().isoformat()
            }, f, indent=2)
    
    def _rate_limit(self):
        """Implementa rate limiting para API"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self.last_request_time = time.time()
    
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
        
        # Apresentações comerciais
        comercial_dir = self.base_path / 'produtos' / 'apresentacoes' / 'comercial'
        if comercial_dir.exists():
            for file_path in comercial_dir.glob('*.md'):
                # Extrai segmento do nome do arquivo (Tech, Indústria, etc.)
                filename = file_path.stem
                if 'Tech-' in filename:
                    segment = 'tech'
                elif 'Indústria-' in filename:
                    segment = 'industria'
                elif 'Serviços-' in filename:
                    segment = 'servicos'
                elif 'SaaS-' in filename:
                    segment = 'saas'
                elif 'Geral-' in filename:
                    segment = 'geral'
                else:
                    continue
                    
                content = file_path.read_text(encoding='utf-8')
                
                if segment not in files_by_product:
                    files_by_product[segment] = []
                
                files_by_product[segment].append(
                    SourceFile(file_path, 'commercial', segment, content)
                )
        
        # Treinamentos
        training_dir = self.base_path / 'produtos' / 'apresentacoes' / 'treinamentos'
        if training_dir.exists():
            for file_path in training_dir.glob('*.md'):
                content = file_path.read_text(encoding='utf-8')
                # Usa 'training' como chave genérica
                if 'training' not in files_by_product:
                    files_by_product['training'] = []
                
                files_by_product['training'].append(
                    SourceFile(file_path, 'training', 'training', content)
                )
        
        # Resumos de treinamentos
        resumos_dir = self.base_path / 'produtos' / 'resumos-treinamentos'
        if resumos_dir.exists():
            for file_path in resumos_dir.glob('*.md'):
                content = file_path.read_text(encoding='utf-8')
                if 'training' not in files_by_product:
                    files_by_product['training'] = []
                
                files_by_product['training'].append(
                    SourceFile(file_path, 'summary', 'training', content)
                )
        
        return files_by_product
    
    def _create_enrichment_prompt(self, sources: List[SourceFile], product_name: str) -> str:
        """Cria prompt para enriquecimento usando Claude API"""
        
        # Agrupa conteúdo por tipo
        datapack_content = []
        commercial_content = []
        training_content = []
        summary_content = []
        
        for source in sources:
            if source.type == 'datapack':
                datapack_content.append(source.content)
            elif source.type == 'commercial':
                commercial_content.append(source.content)
            elif source.type == 'training':
                training_content.append(source.content)
            elif source.type == 'summary':
                summary_content.append(source.content)
        
        prompt = f"""Você é um especialista em produtos de dados e inteligência de mercado. 

Sua tarefa é processar e estruturar informações brutas sobre o produto/segmento "{product_name}" da Driva para criar documentação estruturada e útil para consumo por IA.

## MATERIAIS FONTE DISPONÍVEIS:

"""
        
        if datapack_content:
            prompt += f"""
### DADOS TÉCNICOS DOS DATAPACKS:
{chr(10).join(datapack_content)}
"""
        
        if commercial_content:
            prompt += f"""
### APRESENTAÇÕES COMERCIAIS:
{chr(10).join(commercial_content)}
"""
        
        if training_content:
            prompt += f"""
### MATERIAIS DE TREINAMENTO:
{chr(10).join(training_content)}
"""
        
        if summary_content:
            prompt += f"""
### RESUMOS DE TREINAMENTOS:
{chr(10).join(summary_content)}
"""
        
        prompt += f"""
## INSTRUÇÕES:

Analise todo o conteúdo fornecido e crie um documento estruturado em markdown seguindo EXATAMENTE este formato:

# {product_name.title()}

## Descrição Geral
[Descrição clara e concisa do produto/datapack, consolidando informações de todas as fontes]

## Dados e Campos Disponíveis
[Lista estruturada dos campos/dados disponíveis, organizados logicamente]

## Casos de Uso Práticos
[Exemplos específicos de como o produto pode ser utilizado]

## Público-Alvo
[Segmentação por indústria/perfil de cliente - indústria, serviços, tech, SaaS, etc.]

## Integração com Outros Produtos
[Como este produto se complementa com outros datapacks da Driva]

## Exemplos de Aplicação
[Cenários práticos detalhados de uso]

## Informações Técnicas
[Especificações técnicas, volumes de dados, frequência de atualização, etc.]

## Diferenciais Competitivos
[O que torna este produto único no mercado]

DIRETRIZES IMPORTANTES:
1. Consolide informações redundantes - não repita o mesmo ponto várias vezes
2. Remova ruído e informações irrelevantes (como "Slide X", numeração, etc.)
3. Mantenha linguagem clara e profissional
4. Estruture o conteúdo de forma lógica e hierárquica
5. Foque em informações úteis para tomada de decisão comercial e técnica
6. Se alguma seção não tiver informações suficientes, escreva "[Informação não disponível nos materiais fonte]"

Por favor, gere APENAS o documento estruturado, sem comentários ou explicações adicionais.
"""
        
        return prompt
    
    async def _enrich_product(self, product_name: str, sources: List[SourceFile]) -> str:
        """Enriquece um produto específico usando Claude API"""
        self._rate_limit()
        
        prompt = self._create_enrichment_prompt(sources, product_name)
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                temperature=0.3,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            return response.content[0].text
            
        except Exception as e:
            logger.error(f"Erro ao processar {product_name}: {str(e)}")
            raise
    
    def _save_enriched_content(self, product_name: str, content: str):
        """Salva conteúdo enriquecido"""
        output_file = self.output_path / f"{product_name}.md"
        output_file.write_text(content, encoding='utf-8')
        logger.info(f"Salvo: {output_file}")
    
    def _generate_index(self, processed_products: List[str]):
        """Gera índice/README com visão geral"""
        index_content = f"""# Driva Knowledge Base - Produtos Enriquecidos

*Documentação estruturada gerada automaticamente em {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*

## Produtos Processados

Total de produtos: {len(processed_products)}

"""
        
        for product in sorted(processed_products):
            index_content += f"- [{product.title()}]({product}.md)\n"
        
        index_content += f"""
## Sobre Este Repositório

Esta documentação foi gerada automaticamente a partir dos materiais brutos da Driva Knowledge Base, incluindo:

- Especificações técnicas dos datapacks
- Apresentações comerciais por segmento
- Materiais de treinamento
- Resumos de sessões de capacitação

O processamento utilizou Claude API para consolidar, estruturar e enriquecer as informações, removendo redundâncias e organizando o conteúdo de forma útil para consumo por IA e equipes comerciais/técnicas.

## Última Atualização

{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC
"""
        
        index_file = self.output_path / "README.md"
        index_file.write_text(index_content, encoding='utf-8')
        logger.info(f"Índice gerado: {index_file}")
    
    async def process_all(self):
        """Processa todos os produtos"""
        logger.info("Iniciando processamento de enriquecimento")
        
        # Descobrir arquivos
        files_by_product = self._discover_files()
        logger.info(f"Encontrados {len(files_by_product)} produtos/segmentos para processar")
        
        processed_products = []
        
        for product_name, sources in files_by_product.items():
            cache_key = f"{product_name}_{len(sources)}"
            
            # Verificar se já foi processado
            if cache_key in self.cache.processed_files:
                logger.info(f"Pulando {product_name} (já processado)")
                processed_products.append(product_name)
                continue
            
            # Verificar se falhou anteriormente
            if cache_key in self.cache.failed_files:
                logger.warning(f"Reprocessando {product_name} (falha anterior)")
            
            try:
                logger.info(f"Processando {product_name} ({len(sources)} arquivos fonte)")
                
                # Enriquecer conteúdo
                enriched_content = await self._enrich_product(product_name, sources)
                
                # Salvar resultado
                self._save_enriched_content(product_name, enriched_content)
                
                # Atualizar cache
                self.cache.processed_files.append(cache_key)
                if cache_key in self.cache.failed_files:
                    self.cache.failed_files.remove(cache_key)
                
                processed_products.append(product_name)
                self._save_cache()
                
                logger.info(f"✅ {product_name} processado com sucesso")
                
            except Exception as e:
                logger.error(f"❌ Falha ao processar {product_name}: {str(e)}")
                if cache_key not in self.cache.failed_files:
                    self.cache.failed_files.append(cache_key)
                self._save_cache()
                continue
        
        # Gerar índice
        if processed_products:
            self._generate_index(processed_products)
        
        logger.info(f"Processamento concluído. {len(processed_products)} produtos processados.")

async def main():
    """Função principal"""
    base_path = "/root/.openclaw/workspace/driva-knowledge-base"
    output_path = "/root/.openclaw/workspace/driva-knowledge-base/produtos/enriched"
    
    # Verificar se ANTHROPIC_API_KEY está configurada
    if not os.getenv('ANTHROPIC_API_KEY'):
        logger.error("ANTHROPIC_API_KEY não está configurada")
        return
    
    # Criar diretório de output se não existir
    Path(output_path).mkdir(parents=True, exist_ok=True)
    
    # Inicializar e executar enriquecedor
    enricher = DatapackEnricher(base_path, output_path)
    await enricher.process_all()

if __name__ == "__main__":
    asyncio.run(main())