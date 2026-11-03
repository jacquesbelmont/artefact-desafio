"""Regressões offline sobre respostas falsas, sem modelos e sem custo de API."""
from avaliacao import avaliar_catalogo, avaliar_regras
from tools import buscar_produtos


def test_preco_errado_para_modelo_existente_e_detectado():
    produtos = buscar_produtos(nome="Takamine GD20")["produtos"]
    n, erros = avaliar_catalogo("O Takamine GD20 custa R$ 3.500,00.", produtos)
    assert n >= 1
    assert any("Preço inconsistente" in e for e in erros)


def test_preco_correto_com_estoque_correto_passa():
    produtos = buscar_produtos(nome="Takamine GD20")["produtos"]
    n, erros = avaliar_catalogo("Takamine GD20: R$ 2.199,00, 5 unidades em estoque.", produtos)
    assert n == 2
    assert erros == []


def test_estoque_falso_e_detectado():
    produtos = buscar_produtos(nome="Yamaha C40")["produtos"]
    _, erros = avaliar_catalogo("Yamaha C40: R$ 599,90, 99 unidades em estoque.", produtos)
    assert any("Estoque inconsistente" in e for e in erros)


def test_negacao_de_catalogo_existente_e_detectada():
    produtos = buscar_produtos(categoria="Violões", preco_max=1000)["produtos"]
    _, erros = avaliar_catalogo("Não temos violões disponíveis.", produtos)
    assert erros


def test_14_dias_contradiz_politica_pdf():
    assert avaliar_regras("Você tem até 14 dias corridos por arrependimento.", "arrependimento")


def test_7_dias_nao_gera_contradicao():
    assert not avaliar_regras("O prazo de arrependimento é de 7 dias corridos.", "arrependimento")


def test_nao_prometer_alteracao_sem_integracao():
    assert avaliar_regras("Pronto, já alterei o endereço do pedido!", "alteracao_endereco")


def test_proibicao_absoluta_inventada_e_detectada():
    assert avaliar_regras("Não é possível alterar o endereço após finalizar o pedido.", "alteracao_endereco")


def test_nao_confundir_orientacao_com_acao():
    assert not avaliar_regras("Peça à equipe humana para verificar se pode mudar o endereço.", "alteracao_endereco")
