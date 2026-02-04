#!/usr/bin/env python3
"""
Build Driva Knowledge Base
==========================

Script robusto para consolidar todas as fontes de dados em uma base de conhecimento
estruturada usando OpenAI GPT-4o.

Autor: Jarvis (OpenClaw)
Data: 2025-02-04
Task: CU-86af2wuwr

Uso:
    python build_knowledge_base.py
    python build_knowledge_base.py --api-key <key>
    OPENAI_API_KEY=<key> python build_knowledge_base.py
    python build_knowledge_base.py --resume  # Retoma de checkpoint
    python build_knowledge_base.py --force   # Força regeneração completa
"""

import os
import sys
import json
import time
import argparse
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import re

# Rate limiting and retry
import random

try:
    from openai import OpenAI
except ImportError:
    print("❌ OpenAI library not found. Install with: pip install openai")
    sys.exit(1)


# ============================================================================
# CONFIGURATION
# ============================================================================

REPO_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = REPO_ROOT / "knowledge-base"
CHECKPOINT_FILE = REPO_ROOT / "scripts" / ".kb_checkpoint.json"
LOG_FILE = REPO_ROOT / "scripts" / "build_kb.log"

# Source directories
SOURCES = {
    "datapacks": REPO_ROOT / "produtos" / "datapacks",
    "comercial": REPO_ROOT / "produtos" / "apresentacoes" / "comercial",
    "treinamentos": REPO_ROOT / "produtos" / "apresentacoes" / "treinamentos",
    "resumos": REPO_ROOT / "produtos" / "resumos-treinamentos",
}

# OpenAI settings
MODEL = "gpt-4o"
MAX_TOKENS = 4096
TEMPERATURE = 0.3

# Rate limiting
REQUESTS_PER_MINUTE = 20
MIN_DELAY_BETWEEN_REQUESTS = 3.0  # seconds
MAX_RETRIES = 5
BASE_BACKOFF = 2.0

# Segmentos conhecidos
SEGMENTOS = [
    "industria",
    "servicos", 
    "saas",
    "tecnologia",
    "agro",
    "varejo",
    "financeiro",
    "saude",
]


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging():
    """Configure logging to file and console."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class SourceFile:
    """Represents a source file."""
    path: Path
    category: str
    name: str
    content: str
    
    def get_hash(self) -> str:
        return hashlib.md5(self.content.encode()).hexdigest()


@dataclass
class Product:
    """Represents a Driva product/datapack."""
    name: str
    slug: str
    datapack_content: str
    mentions: Dict[str, List[str]]  # category -> list of excerpts
    
    def get_context_hash(self) -> str:
        """Generate hash of all content for caching."""
        content = self.datapack_content
        for excerpts in self.mentions.values():
            content += "".join(excerpts)
        return hashlib.md5(content.encode()).hexdigest()


@dataclass  
class Checkpoint:
    """Checkpoint state for resuming."""
    completed_products: List[str]
    completed_segments: List[str]
    product_hashes: Dict[str, str]  # slug -> content hash
    last_update: str
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Checkpoint':
        return cls(**data)
    
    @classmethod
    def empty(cls) -> 'Checkpoint':
        return cls(
            completed_products=[],
            completed_segments=[],
            product_hashes={},
            last_update=datetime.now().isoformat()
        )


# ============================================================================
# FILE OPERATIONS
# ============================================================================

def load_sources() -> Dict[str, List[SourceFile]]:
    """Load all source files organized by category."""
    sources: Dict[str, List[SourceFile]] = {}
    
    for category, source_dir in SOURCES.items():
        sources[category] = []
        if not source_dir.exists():
            logger.warning(f"⚠️  Source directory not found: {source_dir}")
            continue
            
        for file_path in source_dir.glob("*.md"):
            if file_path.name == "README.md":
                continue
            try:
                content = file_path.read_text(encoding='utf-8')
                sources[category].append(SourceFile(
                    path=file_path,
                    category=category,
                    name=file_path.stem,
                    content=content
                ))
                logger.debug(f"  Loaded: {file_path.name}")
            except Exception as e:
                logger.error(f"❌ Error loading {file_path}: {e}")
    
    return sources


def extract_products(sources: Dict[str, List[SourceFile]]) -> List[Product]:
    """Extract product list from datapacks."""
    products = []
    
    datapack_files = sources.get("datapacks", [])
    logger.info(f"📦 Found {len(datapack_files)} datapacks")
    
    for df in datapack_files:
        # Extract product name from filename or content
        name = df.name.replace("-", " ").title()
        
        # Try to extract from markdown header
        match = re.search(r'^#\s*(.+)$', df.content, re.MULTILINE)
        if match:
            name = match.group(1).strip()
        
        products.append(Product(
            name=name,
            slug=df.name.lower(),
            datapack_content=df.content,
            mentions={}
        ))
    
    return products


def find_mentions(product: Product, sources: Dict[str, List[SourceFile]]) -> None:
    """Find mentions of a product in all other sources."""
    # Keywords to search for
    keywords = [
        product.slug,
        product.slug.replace("-", " "),
        product.name.lower(),
    ]
    
    # Add specific keywords for known products
    keyword_map = {
        "cnpj": ["cnpj", "dados cadastrais", "empresa"],
        "fiscal": ["fiscal", "per/dcomp", "perdcomp", "tributário", "tributario", "folha salarial", "massa salarial"],
        "energia": ["energia", "consumo", "unidade consumidora", "mercado livre", "baixa tensão", "alta tensão"],
        "frotas": ["frotas", "veículos", "veiculos", "frota pesada", "carroceria"],
        "ecommerce": ["e-commerce", "ecommerce", "loja virtual", "shopify", "vtex"],
        "foodservice": ["food service", "foodservice", "restaurante", "cardápio", "varejo alimentar"],
        "processos-judiciais": ["processos judiciais", "jurídico", "juridico", "judicial", "advogado", "escritório de advocacia", "jurimetria"],
        "beneficios": ["benefícios", "beneficios", "pat", "vale alimentação", "vale refeição"],
        "agro": ["agro", "agronegócio", "fazenda", "propriedade rural", "cultivo"],
        "contadores": ["contadores", "contabilidade", "contador-cliente", "escritório contábil"],
        "saude": ["saúde", "saude", "médicos", "medicos", "hospital", "clínica", "leitos"],
        "geolocalizacao": ["geolocalização", "geolocalizacao", "localização", "estabelecimento", "avaliações"],
        "licitacoes": ["licitações", "licitacoes", "governo", "licitação"],
        "educacao": ["educação", "educacao", "escola", "ensino", "instituição de ensino"],
        "social": ["social", "linkedin", "redes sociais"],
        "erp": ["erp", "sistema de gestão", "sap", "totvs"],
        "obras": ["obras", "construção", "arquitetos", "reforma"],
        "residuos": ["resíduos", "residuos", "cadri", "destinação"],
        "marcas": ["marcas", "marca registrada", "inpi"],
        "saude-animal": ["saúde animal", "veterinário", "veterinario", "pet", "bovino"],
        "contatos-empresas": ["contatos", "telefone", "e-mail", "whatsapp"],
        "contatos-pessoas": ["contatos pessoas", "tomador de decisão", "linkedin pessoa"],
    }
    
    if product.slug in keyword_map:
        keywords.extend(keyword_map[product.slug])
    
    # Make keywords unique and lowercase
    keywords = list(set(k.lower() for k in keywords))
    
    # Search in each category
    for category, files in sources.items():
        if category == "datapacks":
            continue  # Skip datapacks themselves
            
        mentions = []
        for source_file in files:
            content_lower = source_file.content.lower()
            
            # Check if any keyword appears
            found_keywords = [k for k in keywords if k in content_lower]
            if found_keywords:
                # Extract relevant paragraphs
                paragraphs = source_file.content.split("\n\n")
                relevant = []
                
                for para in paragraphs:
                    para_lower = para.lower()
                    if any(k in para_lower for k in found_keywords):
                        relevant.append(para.strip())
                
                if relevant:
                    excerpt = f"### Fonte: {source_file.name}\n\n" + "\n\n".join(relevant[:5])  # Max 5 paragraphs
                    mentions.append(excerpt)
        
        if mentions:
            product.mentions[category] = mentions


def load_checkpoint() -> Checkpoint:
    """Load checkpoint from file."""
    if CHECKPOINT_FILE.exists():
        try:
            data = json.loads(CHECKPOINT_FILE.read_text())
            return Checkpoint.from_dict(data)
        except Exception as e:
            logger.warning(f"⚠️  Could not load checkpoint: {e}")
    return Checkpoint.empty()


def save_checkpoint(checkpoint: Checkpoint) -> None:
    """Save checkpoint to file."""
    checkpoint.last_update = datetime.now().isoformat()
    CHECKPOINT_FILE.write_text(json.dumps(checkpoint.to_dict(), indent=2))


def should_regenerate(product: Product, checkpoint: Checkpoint) -> bool:
    """Check if a product needs regeneration based on content hash."""
    current_hash = product.get_context_hash()
    stored_hash = checkpoint.product_hashes.get(product.slug)
    return stored_hash != current_hash


# ============================================================================
# OPENAI INTEGRATION
# ============================================================================

class OpenAIClient:
    """Wrapper for OpenAI API with rate limiting and retry logic."""
    
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        self.last_request_time = 0
        self.request_count = 0
        
    def _wait_for_rate_limit(self):
        """Ensure we don't exceed rate limits."""
        elapsed = time.time() - self.last_request_time
        if elapsed < MIN_DELAY_BETWEEN_REQUESTS:
            time.sleep(MIN_DELAY_BETWEEN_REQUESTS - elapsed)
        self.last_request_time = time.time()
    
    def _exponential_backoff(self, attempt: int) -> float:
        """Calculate backoff time with jitter."""
        return BASE_BACKOFF ** attempt + random.uniform(0, 1)
    
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate completion with retry logic."""
        self._wait_for_rate_limit()
        
        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=MAX_TOKENS,
                    temperature=TEMPERATURE
                )
                return response.choices[0].message.content
                
            except Exception as e:
                error_str = str(e)
                
                if "rate_limit" in error_str.lower():
                    wait_time = self._exponential_backoff(attempt)
                    logger.warning(f"⏳ Rate limit hit, waiting {wait_time:.1f}s (attempt {attempt + 1}/{MAX_RETRIES})")
                    time.sleep(wait_time)
                    
                elif attempt < MAX_RETRIES - 1:
                    wait_time = self._exponential_backoff(attempt)
                    logger.warning(f"⚠️  API error: {e}. Retrying in {wait_time:.1f}s (attempt {attempt + 1}/{MAX_RETRIES})")
                    time.sleep(wait_time)
                    
                else:
                    logger.error(f"❌ Failed after {MAX_RETRIES} attempts: {e}")
                    raise
        
        raise Exception("Max retries exceeded")


# ============================================================================
# CONTENT GENERATION
# ============================================================================

PRODUCT_SYSTEM_PROMPT = """Você é um especialista em dados e inteligência de mercado da Driva. 
Sua tarefa é criar documentação completa e rica sobre um produto/datapack específico.

Diretrizes:
- Escreva em português brasileiro
- Use linguagem clara e profissional, mas acessível
- Foque em valor prático para vendedores e usuários
- Inclua exemplos concretos sempre que possível
- Mantenha o tom da Driva: inovador, orientado a dados, focado em resultados

Formato de saída: Markdown bem estruturado com as seções solicitadas."""

PRODUCT_USER_PROMPT_TEMPLATE = """Com base nas informações abaixo, crie uma documentação completa para o produto "{product_name}" da Driva.

## DADOS TÉCNICOS DO DATAPACK (fonte primária)
{datapack_content}

## MENÇÕES EM MATERIAIS COMERCIAIS
{comercial_mentions}

## MENÇÕES EM TREINAMENTOS
{training_mentions}

## MENÇÕES EM RESUMOS DE TREINAMENTOS  
{summary_mentions}

---

Gere a documentação com TODAS as seguintes seções:

# {product_name}

## O que é
[Descrição clara e completa do produto, o que ele oferece e sua proposta de valor única]

## Dados Disponíveis
[Lista organizada dos principais campos e informações que o produto oferece. Use bullet points.]

## Para quem serve
[Segmentos de mercado, tipos de empresa e perfis de cliente que mais se beneficiam]

## Casos de Uso Reais
[Exemplos práticos e concretos de como clientes usam o produto. Mencione cases citados nos materiais se houver.]

## Como Vender
[Argumentos comerciais fortes, proposta de valor, diferenciais competitivos, gatilhos de interesse]

## Objeções Comuns e Respostas
[Liste as principais objeções que clientes podem ter e como responder a cada uma]

## Combos Recomendados
[Outros produtos Driva que combinam bem e por quê]

## Números-Chave
[Volume de dados, cobertura, frequência de atualização - o que impressiona]

---

Seja rico em detalhes mas organizado. O objetivo é que um vendedor consiga entender completamente o produto e vender bem após ler este documento."""


SEGMENT_SYSTEM_PROMPT = """Você é um especialista em vendas B2B e inteligência de mercado da Driva.
Sua tarefa é criar um guia estratégico para vendas em um segmento específico de mercado.

Diretrizes:
- Escreva em português brasileiro
- Foque em estratégia de vendas e cases de sucesso
- Seja prático e orientado a ação
- Considere as dores específicas do segmento

Formato: Markdown bem estruturado."""

SEGMENT_USER_PROMPT_TEMPLATE = """Crie um guia completo de vendas para o segmento de {segment_name} usando os dados da Driva.

## MATERIAIS COMERCIAIS DO SEGMENTO
{segment_materials}

## PRODUTOS DRIVA MAIS RELEVANTES PARA ESTE SEGMENTO
{relevant_products}

---

Gere o guia com as seguintes seções:

# Vendendo para {segment_name_title}

## Visão do Segmento
[Características, tamanho de mercado, tendências]

## Dores Comuns
[Principais desafios que empresas deste segmento enfrentam que a Driva resolve]

## Produtos Mais Indicados
[Quais datapacks e soluções são mais relevantes e por quê]

## Abordagem de Vendas
[Como abordar, o que destacar, em que focar]

## Objeções Típicas do Segmento
[Objeções específicas e como contornar]

## Cases de Sucesso
[Exemplos de clientes e resultados alcançados]

## Argumentos Matadores
[Frases e argumentos que fecham vendas neste segmento]"""


CATALOG_SYSTEM_PROMPT = """Você é um especialista em documentação técnica e marketing da Driva.
Crie um catálogo completo e navegável de todos os produtos.

Diretrizes:
- Organização clara e lógica
- Links internos para navegação
- Resumos concisos mas informativos
- Visual limpo e profissional"""

INDEX_TEMPLATE = """# Base de Conhecimento Driva

> Última atualização: {date}

## 📊 Visão Geral

A Driva oferece **inteligência de mercado** através de dados estruturados e enriquecidos. 
Esta base de conhecimento consolida todas as informações sobre nossos produtos, segmentos e estratégias de vendas.

## 🗂️ Navegação

### Produtos (Datapacks)
{product_list}

### Segmentos de Mercado
{segment_list}

### Visão Geral
- [Catálogo Completo](visao-geral/catalogo-completo.md)

---

## 📈 Números Driva

- **26.3M** empresas ativas mapeadas
- **80M** telefones de empresas
- **47M** e-mails de empresas
- **150+** fontes de dados integradas
- **22.000+** empresas clientes

---

*Documentação gerada automaticamente. Para atualizações, execute `scripts/build_knowledge_base.py`*
"""


def generate_product_doc(client: OpenAIClient, product: Product) -> str:
    """Generate documentation for a single product."""
    # Prepare mentions
    comercial = "\n\n".join(product.mentions.get("comercial", ["Nenhuma menção encontrada."]))
    training = "\n\n".join(product.mentions.get("treinamentos", ["Nenhuma menção encontrada."]))
    summaries = "\n\n".join(product.mentions.get("resumos", ["Nenhuma menção encontrada."]))
    
    # Truncate if too long (OpenAI context limits)
    max_section = 8000
    comercial = comercial[:max_section]
    training = training[:max_section]
    summaries = summaries[:max_section]
    
    user_prompt = PRODUCT_USER_PROMPT_TEMPLATE.format(
        product_name=product.name,
        datapack_content=product.datapack_content,
        comercial_mentions=comercial,
        training_mentions=training,
        summary_mentions=summaries
    )
    
    return client.generate(PRODUCT_SYSTEM_PROMPT, user_prompt)


def generate_segment_doc(client: OpenAIClient, segment: str, sources: Dict[str, List[SourceFile]], products: List[Product]) -> str:
    """Generate documentation for a market segment."""
    # Find segment-specific materials
    segment_materials = []
    segment_keywords = {
        "industria": ["indústria", "industria", "industrial"],
        "servicos": ["serviços", "servicos", "service"],
        "saas": ["saas", "software"],
        "tecnologia": ["tech", "tecnologia", "technology"],
        "agro": ["agro", "agronegócio", "rural"],
        "varejo": ["varejo", "retail", "loja"],
        "financeiro": ["financeiro", "banco", "fintech", "crédito"],
        "saude": ["saúde", "saude", "health", "hospital"],
    }
    
    keywords = segment_keywords.get(segment, [segment])
    
    for category, files in sources.items():
        for sf in files:
            name_lower = sf.name.lower()
            content_lower = sf.content.lower()
            if any(k in name_lower or k in content_lower for k in keywords):
                segment_materials.append(f"### {sf.name}\n\n{sf.content[:3000]}")
    
    if not segment_materials:
        segment_materials = ["Material específico não encontrado para este segmento."]
    
    # Find relevant products
    relevant = []
    product_segment_map = {
        "industria": ["frotas", "fiscal", "energia", "cnpj", "beneficios"],
        "servicos": ["processos-judiciais", "contadores", "cnpj", "fiscal"],
        "saas": ["ecommerce", "erp", "social", "cnpj"],
        "tecnologia": ["ecommerce", "erp", "social", "cnpj"],
        "agro": ["agro", "energia", "cnpj", "fiscal"],
        "varejo": ["foodservice", "geolocalizacao", "ecommerce", "cnpj"],
        "financeiro": ["fiscal", "processos-judiciais", "cnpj", "beneficios"],
        "saude": ["saude", "saude-animal", "cnpj", "fiscal"],
    }
    
    relevant_slugs = product_segment_map.get(segment, [])
    for p in products:
        if p.slug in relevant_slugs:
            relevant.append(f"- **{p.name}**: {p.datapack_content[:500]}...")
    
    if not relevant:
        relevant = ["Consulte o catálogo completo para produtos aplicáveis."]
    
    segment_title = segment.replace("-", " ").title()
    user_prompt = SEGMENT_USER_PROMPT_TEMPLATE.format(
        segment_name=segment,
        segment_name_title=segment_title,
        segment_materials="\n\n".join(segment_materials[:5]),
        relevant_products="\n".join(relevant)
    )
    
    return client.generate(SEGMENT_SYSTEM_PROMPT, user_prompt)


def generate_catalog(client: OpenAIClient, products: List[Product]) -> str:
    """Generate complete product catalog."""
    product_summaries = []
    for p in products:
        summary = p.datapack_content[:500].replace("\n", " ")
        product_summaries.append(f"## {p.name}\n\n{summary}...\n\n[Ver documentação completa](../produtos/{p.slug}.md)")
    
    catalog_prompt = f"""Crie um catálogo organizado dos produtos Driva com base nos seguintes dados:

{chr(10).join(product_summaries)}

Organize por categoria:
1. Dados Cadastrais (CNPJ, Social)
2. Dados de Contato (Empresas, Pessoas)
3. Dados de Nicho (todos os outros)

Para cada produto, inclua:
- Nome
- Descrição curta (1 linha)
- Link para documentação

Use formato Markdown com uma tabela por categoria."""
    
    return client.generate(CATALOG_SYSTEM_PROMPT, catalog_prompt)


def generate_index(products: List[Product], segments: List[str]) -> str:
    """Generate the main index file."""
    product_list = "\n".join([
        f"- [{p.name}](produtos/{p.slug}.md)" for p in products
    ])
    
    segment_list = "\n".join([
        f"- [{s.replace('-', ' ').title()}](segmentos/{s}.md)" for s in segments
    ])
    
    return INDEX_TEMPLATE.format(
        date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        product_list=product_list,
        segment_list=segment_list
    )


# ============================================================================
# MAIN BUILD PROCESS
# ============================================================================

def build_knowledge_base(api_key: str, force: bool = False, resume: bool = True):
    """Main build process."""
    start_time = time.time()
    
    logger.info("=" * 60)
    logger.info("🚀 INICIANDO BUILD DA KNOWLEDGE BASE DRIVA")
    logger.info("=" * 60)
    
    # Initialize OpenAI client
    client = OpenAIClient(api_key)
    
    # Load checkpoint
    checkpoint = load_checkpoint() if resume and not force else Checkpoint.empty()
    
    if force:
        logger.info("🔄 Modo FORCE: regenerando tudo do zero")
    elif checkpoint.completed_products:
        logger.info(f"📋 Checkpoint encontrado: {len(checkpoint.completed_products)} produtos já processados")
    
    # Create output directories
    (OUTPUT_DIR / "produtos").mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "segmentos").mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "visao-geral").mkdir(parents=True, exist_ok=True)
    
    # Load sources
    logger.info("\n📂 Carregando fontes de dados...")
    sources = load_sources()
    for cat, files in sources.items():
        logger.info(f"   {cat}: {len(files)} arquivos")
    
    # Extract products
    products = extract_products(sources)
    logger.info(f"\n📦 {len(products)} produtos identificados")
    
    # Find mentions for each product
    logger.info("\n🔍 Buscando menções em todas as fontes...")
    for product in products:
        find_mentions(product, sources)
        mention_count = sum(len(m) for m in product.mentions.values())
        logger.info(f"   {product.name}: {mention_count} menções encontradas")
    
    # Generate product documentation
    logger.info("\n" + "=" * 60)
    logger.info("📝 GERANDO DOCUMENTAÇÃO DOS PRODUTOS")
    logger.info("=" * 60)
    
    products_to_process = []
    for p in products:
        if p.slug in checkpoint.completed_products and not force:
            if not should_regenerate(p, checkpoint):
                logger.info(f"⏭️  {p.name} - já processado, pulando")
                continue
            else:
                logger.info(f"🔄 {p.name} - conteúdo alterado, regenerando")
        products_to_process.append(p)
    
    total_products = len(products_to_process)
    for i, product in enumerate(products_to_process, 1):
        logger.info(f"\n[{i}/{total_products}] 📄 Gerando: {product.name}")
        
        try:
            doc = generate_product_doc(client, product)
            
            # Save document
            output_path = OUTPUT_DIR / "produtos" / f"{product.slug}.md"
            output_path.write_text(doc, encoding='utf-8')
            
            # Update checkpoint
            checkpoint.completed_products.append(product.slug)
            checkpoint.product_hashes[product.slug] = product.get_context_hash()
            save_checkpoint(checkpoint)
            
            logger.info(f"   ✅ Salvo: {output_path.name}")
            
        except Exception as e:
            logger.error(f"   ❌ Erro: {e}")
            continue
    
    # Generate segment documentation
    logger.info("\n" + "=" * 60)
    logger.info("📊 GERANDO DOCUMENTAÇÃO POR SEGMENTO")
    logger.info("=" * 60)
    
    segments_to_process = [s for s in SEGMENTOS if s not in checkpoint.completed_segments or force]
    
    for i, segment in enumerate(segments_to_process, 1):
        logger.info(f"\n[{i}/{len(segments_to_process)}] 🏢 Gerando: {segment.title()}")
        
        try:
            doc = generate_segment_doc(client, segment, sources, products)
            
            output_path = OUTPUT_DIR / "segmentos" / f"{segment}.md"
            output_path.write_text(doc, encoding='utf-8')
            
            checkpoint.completed_segments.append(segment)
            save_checkpoint(checkpoint)
            
            logger.info(f"   ✅ Salvo: {output_path.name}")
            
        except Exception as e:
            logger.error(f"   ❌ Erro: {e}")
            continue
    
    # Generate catalog
    logger.info("\n📚 Gerando catálogo completo...")
    try:
        catalog = generate_catalog(client, products)
        (OUTPUT_DIR / "visao-geral" / "catalogo-completo.md").write_text(catalog, encoding='utf-8')
        logger.info("   ✅ Catálogo salvo")
    except Exception as e:
        logger.error(f"   ❌ Erro no catálogo: {e}")
    
    # Generate index
    logger.info("\n📑 Gerando índice...")
    index = generate_index(products, SEGMENTOS)
    (OUTPUT_DIR / "index.md").write_text(index, encoding='utf-8')
    logger.info("   ✅ Índice salvo")
    
    # Summary
    elapsed = time.time() - start_time
    logger.info("\n" + "=" * 60)
    logger.info("✨ BUILD COMPLETO!")
    logger.info("=" * 60)
    logger.info(f"📁 Output: {OUTPUT_DIR}")
    logger.info(f"📄 Produtos: {len(products)}")
    logger.info(f"🏢 Segmentos: {len(SEGMENTOS)}")
    logger.info(f"⏱️  Tempo: {elapsed/60:.1f} minutos")
    
    # Clean up checkpoint on success
    if CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()
        logger.info("🧹 Checkpoint limpo")
    
    return True


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Build Driva Knowledge Base",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python build_knowledge_base.py
  python build_knowledge_base.py --api-key sk-xxx
  python build_knowledge_base.py --resume
  python build_knowledge_base.py --force
  
A API key pode ser passada via:
  1. Argumento --api-key
  2. Variável de ambiente OPENAI_API_KEY
        """
    )
    
    parser.add_argument(
        "--api-key",
        help="OpenAI API key (ou use OPENAI_API_KEY env var)"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint if available"
    )
    parser.add_argument(
        "--force",
        action="store_true", 
        help="Force regeneration of all content"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Get API key
    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
    
    if not api_key:
        logger.error("❌ OpenAI API key not provided!")
        logger.error("   Use --api-key or set OPENAI_API_KEY environment variable")
        sys.exit(1)
    
    try:
        success = build_knowledge_base(
            api_key=api_key,
            force=args.force,
            resume=args.resume
        )
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Interrompido pelo usuário. Progresso salvo em checkpoint.")
        sys.exit(130)
        
    except Exception as e:
        logger.error(f"\n❌ Erro fatal: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
