# Conversas reais de demonstração (API)

## Catálogo

**Cliente:** Quais violões disponíveis custam até R$ 1.000?

**Atendente:** Oi! No nosso catálogo de demonstração não temos nenhum violão com preço até R$ 1.000. Se quiser, posso buscar opções em outra faixa de preço ou outro tipo de instrumento. É só me dizer!

*Provedor: groq; tools: ['buscar_produtos']; validacao: OK*

## Política

**Cliente:** Comprei online e me arrependi. Posso devolver?

**Atendente:** Oi! Sim, você pode devolver a compra feita online.

**Como funciona o direito de arrependimento:**

- Você tem até **7 dias corridos** após receber o produto para solicitar a devolução, sem precisar justificar.
- O item deve estar **na embalagem original**, sem sinais de uso e com todos os acessórios e manuais que vieram.
- O **frete de devolução** é por conta da loja.
- O **reembolso** será feito na mesma forma de pagamento que você usou, em até **10 dias úteis**.

Para dar início ao processo, preciso do **número do pedido** e do **e‑mail cadastrado**. Assim que eu receber esses dados, encaminho a sua solicitação para a equipe responsável.

Qualquer dúvida, é só falar! 🎸✨

*Provedor: groq; tools: ['consultar_politicas']; validacao: OK*

## Endereço

**Cliente:** Qual é o endereço da loja e o horário de sábado?

**Erro:** Todas as APIs configuradas estão indisponíveis ou chegaram ao limite.

## Fora de escopo

**Cliente:** Qual a melhor receita de bolo de cenoura?

**Atendente:** Desculpe, mas aqui na Empório da Música ajudamos apenas com assuntos relacionados a instrumentos musicais, acessórios e políticas da loja. Para receitas de bolo de cenoura, recomendo buscar em sites de culinária ou em blogs especializados. Se precisar de alguma informação sobre nossos produtos ou serviços, estou à disposição!

*Provedor: groq; tools: []; validacao: OK*

**Resultado dos cenários:** 3/4 sem falhas identificadas.
