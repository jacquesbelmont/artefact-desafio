from decimal import Decimal
from tools import buscar_produtos, status_pedido, tabela, moeda, executar_ferramenta


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
