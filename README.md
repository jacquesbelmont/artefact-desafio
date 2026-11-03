# Empório da Música — agente de atendimento com IA

> **Desafio técnico AI Engineer — Artefact.** Protótipo educacional em Python. A loja, os pedidos e os clientes pertencem ao cenário fictício do desafio; este sistema **não é um atendimento real de produção**.

## 1. O que o projeto entrega

Um agente de mensagens de texto que responde em português do Brasil, no tom informal e profissional da Empório da Música. O agente diferencia quando precisa **consultar dados estruturados** (produtos, preços, estoque, pedidos e promoções), quando precisa **consultar políticas** (horários, pagamento, entregas, trocas e garantia) e quando precisa **recusar assuntos fora do escopo**.

As respostas são geradas por um LLM com *function calling*. Os fatos são obtidos por funções Python somente de leitura; o LLM não recebe acesso direto ao filesystem, ao terminal, às credenciais ou a operações financeiras.

### Arquitetura

```text
Cliente (CLI)
    |
    v
main.py -> agent.py -> history.py (SQLite local)
               |
               +--> providers.py --> Groq (principal)
               |                 \--> OpenRouter (reserva opcional)
               |
               +--> tools.py --> CSVs: produtos/pedidos/clientes/promoções
               |            \--> policies.py --> PDF de políticas (páginas)
               |
               +--> resposta em português + ferramentas utilizadas
```

**Não há API web ou WhatsApp neste protótipo**, pois o enunciado permite CLI. Este recorte torna a solução fácil de executar e avaliar.

## 2. Pré-requisitos

- macOS, Linux ou Windows com Python **3.11 ou superior**.
- Acesso à internet para chamadas ao modelo de linguagem.
- Chave da **Groq** para demonstração principal ou chave do **OpenRouter** para executar somente com a reserva.
- A API reserva é **opcional**; não há obrigação de cadastrar cartão ou gastar créditos para os testes automatizados.

## 3. Como instalar e rodar

Execute no terminal, **na raiz do repositório** (`agent/` no ambiente original):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

Edite o arquivo `.env` e preencha **apenas** a chave que vai usar:

```dotenv
GROQ_API_KEY=sua_chave_aqui
GROQ_MODEL=openai/gpt-oss-120b

# Opcional: fallback para erro 429, timeout ou falha transitória
OPENROUTER_API_KEY=
OPENROUTER_MODEL=openai/gpt-4o-mini
LLM_TIMEOUT_SECONDS=25
```

Nunca publique `.env`, nem coloque a chave no README ou no código. O arquivo está no `.gitignore`.

Inicie o atendimento:

```bash
python main.py
```

Exemplo de perguntas:

```text
Quais violões vocês têm até R$ 1.000?
Quanto custa o Yamaha C40?
Quais são as formas de pagamento?
Comprei online. Posso devolver?
Qual o status do pedido 2?
Qual a melhor receita de bolo?
```

Uma nova sessão recebe um identificador mostrado no terminal. Para retomar o histórico:

```bash
python main.py --sessao demo-12345678
```

Digite `/sair` para encerrar. A base local fica em `.local/conversas.sqlite3` e **não é versionada**.

## 4. Testes

### Testes automatizados (sem API, sem custo)

```bash
python -m pytest -q
```

A suíte verifica leitura dos CSVs, preço e estoque, proteção básica de pedidos, busca de políticas, histórico em SQLite, uso de ferramentas e troca da Groq pela reserva quando uma falha HTTP `429` é simulada. Também verifica que erro HTTP `400` não é mascarado por fallback.

### Demonstração com API real (pode consumir cota/créditos)

```bash
python test_atendimento.py
```

Para registrar de 3 a 5 conversas exigidas pela Artefact:

```bash
python test_atendimento.py | tee exemplos/conversas_reais.md
```

**Importante:** esse arquivo só é uma evidência real depois que o comando tiver sido executado e as respostas verificadas manualmente. O projeto não inclui resultados de API inventados. Testes automatizados com modelos falsos não demonstram qualidade da resposta final.

Se a Groq limitar as requisições e uma reserva estiver configurada, o agente tenta a segunda API. Se nenhuma API responder, informa o problema e conserva a mensagem no histórico.

## 5. Justificativas das escolhas técnicas

| Decisão | Alternativa considerada | Motivo |
|---|---|---|
| **Python + CLI** | FastAPI, Streamlit, WhatsApp | CLI é suficiente e concentra a avaliação no comportamento do agente. |
| **Um agente com ferramentas** | Sistema multiagente / ReAct sem limites | O problema possui três consultas bem definidas; menos partes reduzem erros. |
| **Function calling** | Prompt com todos os CSVs | O modelo solicita funções Python e recebe resultados verificáveis. |
| **HTTPX e contrato OpenAI Chat Completions** | SDK exclusivo da Groq ou de cada fornecedor | Groq e OpenRouter aceitam um formato HTTP comum; fica fácil incluir outros provedores. |
| **Groq principal** | Modelo local | O primeiro experimento do projeto já usava Groq e o objetivo é entregar em 1–2 dias. |
| **OpenRouter opcional** | Retry ilimitado no mesmo provedor | Permite provar um fallback 429 sem depender de um só fornecedor. |
| **CSV via biblioteca padrão `csv`** | pandas, PostgreSQL, agente SQL | São seis tabelas pequenas; `csv` dispensa infraestrutura e dependências adicionais. |
| **Busca de políticas por tópico + páginas PDF** | RAG vetorial com embeddings | O manual possui oito páginas. Selecionar páginas relevantes é simples, auditável e suficiente para o MVP. |
| **SQLite de conversas** | Redis/PostgreSQL | Já vem com Python, guarda contexto entre reinícios e não depende de serviços externos. |
| **`pytest` e mocks** | Testar tudo somente contra APIs reais | Verifica lógica, erros e fallback de maneira reproduzível e sem consumo de tokens. |

### Como funciona o retrieval

- **Dados operacionais:** `tools.py` relê os arquivos CSV no instante em que uma ferramenta é chamada. São dados de um **snapshot fictício**, não consultas ao estoque de produção.
- **Políticas:** `policies.py` extrai texto do PDF com `pypdf` e seleciona páginas conforme o assunto. Cada resultado inclui a página de origem.
- **Prompt:** `agent.py` orienta o modelo a pedir dados às ferramentas, não inventar informações, responder de forma cordial e pedir intervenção humana em dúvidas de regras.

Isso é **retrieval por regras de seleção de fonte**, não RAG semântico com embeddings. Foi uma escolha consciente de simplicidade.

### Contrato das ferramentas

1. `buscar_produtos(nome?, categoria?, preco_max?)`: só oferece produtos `active` **e** `stock_quantity > 0`, com preço final após eventual promoção `is_active=1`. Resultados limitados a oito por consulta.
2. `status_pedido(order_id, email)`: associa o pedido ao e-mail cadastrado antes de informar status e rastreamento; nunca retorna nome, telefone, endereço nem dados de outros pedidos.
3. `consultar_politicas(assunto)`: seleciona páginas do manual de oito páginas sobre a dúvida apresentada.

**Segurança:** e-mail + número de pedido é apenas barreira demonstrativa, **não autenticação adequada para produção**. Um sistema real deve autenticar o cliente por canal confiável/OTP e controlar acesso no servidor. O LLM não decide quem está autenticado.

### Como funciona o fallback sem perder a conversa

1. `history.py` salva as mensagens do cliente em SQLite **antes** da chamada ao modelo.
2. `providers.py` tenta a Groq (quando configurada).
3. Em HTTP `429`, `408`, `5xx`, falha de conexão ou timeout, tenta o OpenRouter (quando configurado), enviando **as mesmas mensagens**, com histórico e resultados das ferramentas já executadas.
4. A API que responder continua a conversa. Novas respostas entram no mesmo histórico SQLite.
5. Não fazemos fallback automático em HTTP `400`, `401` e `403`: esses erros sugerem configuração, autorização ou pedido inválido, não sobrecarga passageira.
6. Se ambos falharem, o sistema avisa e a pergunta permanece registrada para retomada.

**Limites:** não transferimos estados internos ocultos de um modelo para outro; apenas o contexto explícito. Não há garantia de continuidade quando ambas as APIs falham. Não implementamos fila distribuída, idempotência global ou circuito de saúde entre processos porque o desafio é um CLI local.

O fallback lida apenas com **ferramentas de leitura**. Em ferramentas que fazem pagamentos, alteram pedidos ou enviam mensagens reais, é obrigatório implementar idempotência de efeitos antes de repetir chamadas.

## 6. Regras do manual e ambiguidades encontradas

Manual de Políticas e Procedimentos, v2.1, junho de 2025:

- **Horários:** segunda a sexta, 9h–18h; sábado, 9h–13h; domingo/feriados, fechado (p. 2).
- **PIX:** 5% sobre preço de tabela, não cumulativo com promoção (pp. 3 e 6).
- **Direito de arrependimento:** o manual prevê sete dias corridos após o recebimento em compras online (p. 4). O CSV de pedidos não contém a **data real do recebimento**; o agente não deve decidir sozinho se o prazo terminou.
- **Garantia e defeito:** o manual fala em troca em 30 dias (p. 4) e em garantia legal de 90 dias (p. 7). O agente deve consultar as duas regras e encaminhar dúvidas, sem negar direitos por uma leitura parcial.
- **Contato:** o manual apresenta um número na identificação da empresa (p. 2) e outro no atendimento via WhatsApp (p. 6). A solução evita assumir que os dois são idênticos.
- **Promoções:** os CSVs possuem `is_active`, mas **não há datas de início/fim**. Não afirmar validade de calendário nem acumular descontos.
- **Estoque:** há produto descontinuado com estoque positivo e produto `active` com estoque zero. Ambos são excluídos das sugestões disponíveis.
- **Histórico:** valores de pedidos são lidos de `orders.total_brl`, não recalculados com preços atuais de produtos.

Essas ambiguidades são documentadas, não escondidas. O enunciado da Artefact permite assumir uma interpretação razoável, desde que seja registrada no README.

## 7. Estrutura do repositório

```text
.
├── main.py                     # CLI
├── agent.py                    # loop de tool calling e prompt
├── providers.py                # provedores e fallback
├── tools.py                    # 2 consultas aos CSVs + política
├── policies.py                 # busca de páginas relevantes do PDF
├── history.py                  # SQLite (somente mensagens textuais)
├── test_atendimento.py         # demonstração usando API real
├── tests/                      # testes offline pytest
├── data/                       # 6 CSVs e manual do desafio
├── exemplos/                   # orientação e conversas capturadas
├── .env.example                # configuração sem credenciais
├── .gitignore
├── requirements.txt
└── README.md
```

## 8. Limitações conhecidas / próximos passos

- O modelo pode **não chamar a ferramenta** mesmo quando solicitado pelo prompt; os cenários reais devem comprovar as chamadas e podemos reforçar a orquestração caso falhe.
- Produtos, estoque, preços, pedidos e promoções são **dados estáticos do desafio**; não existe sincronização com loja real ou rastreamento dos Correios.
- A busca de políticas por palavras-chave não equivale a um mecanismo semântico robusto. Um RAG vetorial com citações faria sentido com centenas de documentos, não com oito páginas.
- A validação de pedidos por e-mail é fraca e não deve ser usada em produção. O SQLite local também guarda as mensagens em texto puro; dados sensíveis exigiriam controles adicionais em produção.
- SQLite salva mensagens finais; passos intermediários de ferramentas são reaplicados no contexto de cada turno, mas não persistidos como eventos independentes.
- A troca entre modelos não preserva estados internos ou raciocínio privado, somente histórico explícito.
- O fallback não oferece garantias de disponibilidade ou orçamento; o modelo de reserva pode ter tarifas e restrições diferentes.
- Ainda não há interface web, atendimento humano real, autenticação forte, observabilidade central ou integração com WhatsApp.
- O PDF pode incluir uma regra juridicamente questionável; este protótipo **não oferece aconselhamento jurídico**.

Com mais tempo: adicionar testes de avaliação semântica (resposta fiel à fonte), bloqueio determinístico de saídas não verificadas, autenticação real, casos de borda, métricas, versionamento dos dados e implantação em API web.

## 9. Uso de assistentes de programação (transparência)

O planejamento e a proposta inicial da implementação foram realizados com ajuda do **ChatGPT**, que apoiou a análise do enunciado, dos CSVs e do PDF, o desenho das ferramentas, o fallback, a estrutura de testes e este README. O projeto original `test_atendimento.py` foi iniciado com a API Groq e evoluiu para um agente modular.

**Antes da entrega, o autor deve atualizar esta seção com o workflow realmente executado:** quais ferramentas usou no VS Code (por exemplo, Claude Code), quais partes revisou manualmente, os testes que executou, falhas corrigidas e critérios das escolhas. Não afirmar revisão ou uso de ferramenta que não aconteceu.

A responsabilidade por compreender, testar e explicar a solução na entrevista é do candidato. O histórico Git deve refletir incrementos reais, sem commits artificiais retroativos.

## 10. Referências técnicas

- Enunciado do desafio Artefact — documento fornecido separadamente ao candidato, **não incluído neste repositório**.
- [Groq — OpenAI compatibility](https://console.groq.com/docs/openai)
- [Groq — Rate limits e 429](https://console.groq.com/docs/rate-limits)
- [OpenRouter — OpenAI-compatible API](https://openrouter.ai/developers)
- [HTTPX](https://www.python-httpx.org/)
- [pypdf](https://pypdf.readthedocs.io/)

> **Nota:** nunca faça commits após o prazo oficial da Artefact. O repositório é público; use somente dados do cenário fictício e nunca inclua dados reais de clientes, segredos ou `.env`.
