# Guia de instalação no MacBook — VS Code

Este guia pressupõe que você esteja no terminal mostrando `agent %`, como na imagem enviada. A pasta `agent/` é a raiz do Git, e o primeiro commit já existe.

## Passo 1 — Colocar os arquivos

Baixe o ZIP disponibilizado no ChatGPT. Com o terminal do VS Code aberto **dentro da pasta `agent/`**:

```bash
pwd
git status
unzip -o ~/Downloads/artefact_desafio_entrega.zip -d .
ls -la
ls data
```

Caso o arquivo seja baixado em outro lugar, substitua `~/Downloads/artefact_desafio_entrega.zip` pelo caminho real.

O ZIP contém um novo `test_atendimento.py`; seu primeiro commit anterior **continua preservado no histórico Git**.

## Passo 2 — Ambiente Python

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp -n .env.example .env
nano .env
```

No `nano`, preencha `GROQ_API_KEY` com sua chave e deixe `OPENROUTER_API_KEY` vazia se ainda não possuir uma segunda chave. Pressione `Ctrl + O`, Enter e `Ctrl + X` para salvar/sair. **Não compartilhe a chave no chat**.

## Passo 3 — Testar sem gastar tokens

```bash
python -m pytest -q
```

O pacote foi validado antes de ser entregue com **19 testes offline aprovados**. Se o seu Mac apresentar erro, copie apenas a mensagem de erro (não a chave) para investigarmos.

## Passo 4 — Testar o atendimento real

```bash
python main.py
```

Teste estas perguntas, uma por vez:

- `Quais violões vocês têm até R$ 1.000?`
- `Qual o horário de sábado?`
- `Posso devolver uma compra online?`
- `Qual o status do pedido 2?`
- `Me ensine uma receita de bolo.`

Digite `/sair` para encerrar.

## Passo 5 — Gerar as 4 conversas demonstrativas

```bash
python test_atendimento.py | tee exemplos/conversas_reais.md
```

Abra o arquivo gerado no VS Code e verifique se as respostas são corretas e se as ferramentas esperadas foram usadas. Se algo falhar, não entregue o transcript como se estivesse aprovado.

## Passo 6 — Commits reais e push

A Artefact pede commits progressivos. Os comandos abaixo criam três etapas **apenas se cada uma corresponder ao que você revisou e testou**.

```bash
git status
git check-ignore .env

git add data/ tools.py policies.py tests/test_tools.py tests/test_policies.py
git commit -m "feat: add grounded catalog and store policy tools"

git add providers.py history.py agent.py main.py tests/test_agent.py tests/test_fallback.py tests/test_http_adapter.py
git commit -m "feat: implement conversation agent and API failover"

git add README.md .gitignore .env.example requirements.txt test_atendimento.py exemplos/ GUIA_TERMINAL_MAC.md
git commit -m "docs: document design decisions and add demo scenarios"

git push origin main
```

Caso uma pasta tenha alterações ainda não revisadas, **não execute commits automaticamente**; confira os arquivos primeiro. Confira que `.env`, `.venv/` e `.local/` não estão sendo versionados. **Não faça commits após o prazo do processo seletivo.**

## O que comentar na entrevista

- Um único agente é suficiente para o escopo e evita complexidade desnecessária.
- *Function calling* separa geração de texto de acesso factual aos dados.
- Histórico independente do provedor permite fallback mantendo o contexto explícito.
- A escolha de PDF por página foi deliberada: oito páginas não justificam embeddings.
- Testes offline comprovam comportamento determinístico; testes com a API avaliam a integração real.
- E-mail + número do pedido é só proteção ilustrativa, não autenticação de produção.
