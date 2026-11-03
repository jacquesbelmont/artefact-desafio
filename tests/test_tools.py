from decimal import Decimal
from tools import buscar_produtos, status_pedido, tabela, moeda, executar_ferramenta, normalizar


def test_seis_tabelas_carregam():
    assert len(tabela("products")) == 65
    assert len(tabela("orders")) == 20
    assert len(tabela("categories")) == 9


def test_violao_ate_mil_so_disponiveis():
    resposta = buscar_produtos(categoria="Violões", preco_max=1000)
    assert resposta["produtos"]
    assert all(p["estoque"] > 0 for p in resposta["produtos"])
    assert all(Decimal(p["preco_atual"].removeprefix("R$ ").replace(".", "").replace(",", ".")) <= 1000 for p in resposta["produtos"])


def test_nao_oferece_descontinuados_ou_estoque_zero():
    validos = {p["product_id"] for p in tabela("products") if p["status"] == "active" and int(p["stock_quantity"]) > 0}
    listados = {p["produto_id"] for p in buscar_produtos()["produtos"]}
    assert listados.issubset({int(x) for x in validos})


def test_moeda():
    assert moeda(Decimal("1234.5")) == "R$ 1.234,50"


def test_pedido_exige_email_correspondente():
    assert "erro" in status_pedido(2, "nao-existe@example.com")
    pedido = tabela("orders")[1]
    cliente = next(c for c in tabela("customers") if c["customer_id"] == pedido["customer_id"])
    resultado = status_pedido(2, cliente["email"])
    assert resultado["status"] == pedido["status"]
    assert resultado["valor_registrado"] == moeda(Decimal(pedido["total_brl"]))
    assert "email" not in resultado


def test_ferramenta_desconhecida_rejeitada():
    assert "não autorizada" in executar_ferramenta("executar_shell", "{}").lower()


def test_json_de_parametros_invalidos():
    assert "Parâmetros inválidos" in executar_ferramenta("buscar_produtos", "{quebrado")


def test_estoque_zero_e_descontinuado_nao_sao_oferecidos():
    assert not buscar_produtos(nome="Giannini GF-3D")["produtos"]
    assert not buscar_produtos(nome="Ibanez Bass 2X")["produtos"]
    assert not buscar_produtos(nome="Kala KA-ABP-CTG")["produtos"]


def test_preco_de_promocao_ativa_e_informado():
    produto = buscar_produtos(nome="Crafter HT-100")["produtos"]
    assert produto
    assert produto[0]["promocao"]["desconto_percentual"] == "18"
    assert produto[0]["preco_tabela"] != produto[0]["preco_atual"]


def test_nome_com_categoria_violoes_resolve_para_categoria():
    por_nome = buscar_produtos(nome="violões")
    por_categoria = buscar_produtos(categoria="Violões")
    assert por_nome["produtos"]
    assert {p["produto_id"] for p in por_nome["produtos"]} == {p["produto_id"] for p in por_categoria["produtos"]}


def test_nome_com_variantes_sem_acento_resolve_categoria():
    for variante in ("violao", "violoes", "VIOLÃO"):
        resultado = buscar_produtos(nome=variante)
        assert resultado["produtos"]
        assert all(p["categoria"] == "Violões" for p in resultado["produtos"])


def test_nome_categoria_guitarra_resolve_para_guitarras():
    resultado = buscar_produtos(nome="guitarra")
    assert resultado["produtos"]
    assert all(p["categoria"] == "Guitarras" for p in resultado["produtos"])


def test_categoria_explicita_tambem_passa_pelo_alias():
    resultado = buscar_produtos(categoria="violao")
    assert resultado["produtos"]
    assert all(p["categoria"] == "Violões" for p in resultado["produtos"])


def test_alias_de_categoria_respeita_estoque_e_status():
    # Produtos sem estoque ou descontinuados na categoria não devem aparecer
    # mesmo quando a busca é feita pelo alias passado em "nome".
    validos = {
        p["product_id"] for p in tabela("products")
        if p["status"] == "active" and int(p["stock_quantity"]) > 0
    }
    listados = {p["produto_id"] for p in buscar_produtos(nome="violões")["produtos"]}
    assert listados.issubset({int(x) for x in validos})


def test_categoria_ja_informada_nao_e_sobrescrita_pelo_nome():
    # Se "categoria" já foi informada, "nome" continua filtrando por nome do produto,
    # mesmo que coincida com outro alias de categoria.
    resultado = buscar_produtos(nome="violao", categoria="Guitarras")
    assert resultado["produtos"] == []


def test_nome_exato_violino_nao_retorna_outros_instrumentos():
    # "violino" não é mais alias de categoria inteira (Cordas Orquestrais);
    # deve casar apenas por substring no nome do produto, nunca trazendo
    # flautas, saxofones, violas ou violoncelos como efeito colateral.
    resultado = buscar_produtos(nome="violino")
    assert all("violino" in normalizar(p["nome"]) for p in resultado["produtos"])
    assert all(
        p["categoria"] not in ("Instrumentos de Sopro (Madeiras)", "Instrumentos de Sopro (Metais)")
        for p in resultado["produtos"]
    )
