# Conversas de demonstração

O desafio pede de **3 a 5 conversas variadas**, incluindo cenário não trivial.

**Não considere este arquivo uma conversa real.** Os exemplos devem vir da execução do agente com uma API configurada.

Execute na raiz do projeto:

```bash
python test_atendimento.py | tee exemplos/conversas_reais.md
```

Depois abra `exemplos/conversas_reais.md` e confirme que as respostas realmente consultaram ferramentas. Corrija qualquer falha antes da entrega.

Sugestões extras no CLI:
- Pedido sem e-mail: `Qual o status do pedido 2?` (deve solicitar verificação)
- Produto esgotado: peça um item indisponível, confirmando que não seja oferecido como disponível
- Promoção: pergunte pela validade (não há datas de vigência no CSV)

Evite registrar no Git dados pessoais reais ou credenciais.
