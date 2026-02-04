# Plano de Processamento - Base de Conhecimento Driva

## Fontes de Dados

### 1. Catálogo de Dados - IM.xlsx ✅
- **Status:** Baixado
- **Conteúdo:** 26 abas, 493 campos de dados
- **Estrutura:** Datapack, Campo, Descrição, Plano

### 2. Pasta "Oferta de Inteligência 2026" ⏳
- **Status:** Aguardando acesso
- **Conteúdo:** A ser explorado

## Estrutura de Output

```
produtos/
├── datapacks/
│   ├── README.md           # Visão geral dos datapacks
│   ├── cnpj.md             # Dados Cadastrais CNPJ
│   ├── social.md           # Dados Social
│   ├── frotas.md           # Nicho Frotas
│   ├── ecommerce.md        # Nicho E-commerce
│   ├── agro.md             # Nicho Agro
│   ├── foodservice.md      # Nicho Food Service
│   ├── energia.md          # Nicho Energia
│   ├── saude-animal.md     # Nicho Saúde Animal
│   ├── residuos.md         # Nicho Resíduos
│   ├── beneficios.md       # Nicho Benefícios
│   ├── erp.md              # Nicho ERP
│   ├── geolocalizacao.md   # Nicho Geolocalização
│   ├── processos.md        # Processos Judiciais
│   ├── fiscal.md           # Dados Fiscais
│   ├── contadores.md       # Contadores
│   ├── contatos.md         # Contatos
│   ├── licitacoes.md       # Licitações
│   ├── educacao.md         # Educação
│   ├── obras.md            # Obras
│   └── saude.md            # Saúde
└── planos/
    ├── prospeccao.md       # Plano Prospecção
    └── inteligencia.md     # Plano Inteligência
```

## Processo

1. **Extração:** Ler cada aba da planilha
2. **Enriquecimento:** Usar LLM para criar descrições detalhadas
3. **Estruturação:** Gerar .md com formato padronizado
4. **Validação:** Revisão humana

## Formato dos .md

```markdown
# [Nome do Datapack]

> Descrição gerada por LLM

## Visão Geral
- Plano: [Prospecção/Inteligência]
- Total de campos: X

## Campos Disponíveis

| Campo | Descrição |
|-------|-----------|
| ... | ... |

## Casos de Uso
- ...

## Exemplos de Aplicação
- ...
```
