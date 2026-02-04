# Driva Knowledge Base

Base de conhecimento estruturada dos produtos e serviços da Driva, otimizada para consumo por IA.

## 📁 Estrutura

```
driva-knowledge-base/
├── knowledge-base/          # 📚 Output principal (documentos prontos para IA)
│   ├── produtos/            # 22 produtos documentados
│   ├── segmentos/           # Visão por segmento de mercado
│   ├── visao-geral/         # Catálogo completo
│   └── index.md             # Índice navegável
├── produtos/                # 🗂️ Fontes brutas
│   ├── datapacks/           # Dados técnicos dos produtos
│   ├── apresentacoes/       # Materiais comerciais extraídos
│   └── resumos-treinamentos/# Resumos de treinamentos
├── scripts/                 # 🔧 Scripts de processamento
│   └── build_knowledge_base.py
└── source_files/            # 📎 Arquivos originais (Excel, etc)
```

## 🚀 Como Funciona

### Processo de Geração

```
┌─────────────────┐
│   FONTES        │
├─────────────────┤
│ • Datapacks     │──┐
│ • Slides        │  │
│ • Treinamentos  │  │
│ • Resumos       │  │
└─────────────────┘  │
                     ▼
        ┌────────────────────────┐
        │  1. COLETA & PARSING   │
        │  Lê todos os arquivos  │
        │  .md das fontes        │
        └───────────┬────────────┘
                    ▼
        ┌────────────────────────┐
        │ 2. BUSCA DE MENÇÕES    │
        │ Para cada produto,     │
        │ encontra referências   │
        │ em todas as fontes     │
        └───────────┬────────────┘
                    ▼
        ┌────────────────────────┐
        │ 3. CONSOLIDAÇÃO LLM    │
        │ GPT-4o processa e      │
        │ gera documento rico    │
        │ e estruturado          │
        └───────────┬────────────┘
                    ▼
        ┌────────────────────────┐
        │ 4. OUTPUT              │
        │ • 22 produtos          │
        │ • 8 segmentos          │
        │ • Índice + Catálogo    │
        └────────────────────────┘
```

### O que cada documento contém

Cada produto na `knowledge-base/produtos/` inclui:

- **O que é** — Descrição clara do produto
- **Dados disponíveis** — Campos e informações oferecidas
- **Para quem serve** — Segmentos e tipos de empresa
- **Casos de uso reais** — Exemplos práticos de aplicação
- **Como vender** — Argumentos comerciais, proposta de valor
- **Objeções comuns** — E como responder
- **Combos recomendados** — Produtos que combinam bem

## 🔧 Como Executar

### Pré-requisitos

```bash
pip install openai
```

### Executar o build

```bash
# Com API key como argumento
python scripts/build_knowledge_base.py --api-key "sk-..."

# Ou via variável de ambiente
export OPENAI_API_KEY="sk-..."
python scripts/build_knowledge_base.py
```

### Opções

| Flag | Descrição |
|------|-----------|
| `--api-key` | Chave da OpenAI API |
| `--resume` | Retoma do último checkpoint |
| `--force` | Força regeneração completa |

### Tempo de execução

~13 minutos para processar 22 produtos + 8 segmentos + catálogo.

## 📊 Produtos Disponíveis

| Produto | Descrição |
|---------|-----------|
| CNPJ | Dados cadastrais empresariais |
| Contatos Empresas | Telefones, emails, decisores |
| Contatos Pessoas | Dados de pessoas físicas |
| Fiscal | Notas fiscais e transações |
| Processos Judiciais | Histórico jurídico |
| Social | Redes sociais e presença digital |
| Energia | Consumo energético |
| Frotas | Veículos e frotas |
| E-commerce | Lojas online e marketplaces |
| ERP | Sistemas de gestão |
| Benefícios | Vale-transporte, alimentação |
| Licitações | Contratos públicos |
| Food Service | Restaurantes e alimentação |
| Saúde | Estabelecimentos de saúde |
| Saúde Animal | Veterinárias e pet shops |
| Agro | Produtores rurais |
| Educação | Instituições de ensino |
| Obras | Construção civil |
| Contadores | Escritórios contábeis |
| Resíduos | Gestão de resíduos |
| Marcas | Marcas registradas |
| Geolocalização | Dados de localização |

## 🏢 Segmentos

- **Indústria** — Foco em manufatura e produção
- **Serviços** — Empresas de serviços B2B
- **Tecnologia** — Empresas de software e tech
- **Varejo** — Comércio e distribuição
- **Financeiro** — Bancos, fintechs, seguradoras
- **Saúde** — Healthcare e life sciences
- **Agronegócio** — Setor agrícola
- **Governo** — Setor público e licitações

## 🔄 Atualizações

Para atualizar a knowledge base quando houver novos materiais:

1. Adicione os novos arquivos em `produtos/`
2. Execute o script com `--force` para regenerar tudo
3. Commit e push das alterações

---

**Mantido por:** Jarvis (AI Assistant)  
**Última atualização:** Fevereiro 2026
