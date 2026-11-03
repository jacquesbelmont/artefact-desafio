"""Testes offline das funções auxiliares de test_atendimento.py (sem chamadas reais de API)."""
import pytest

from test_atendimento import (
    CENARIOS,
    analisar_argumentos,
    resposta_nega_catalogo_confirmado,
)


def test_consistencia_rejeita_negacao_quando_ferramenta_confirmou_produtos():
    texto = "Infelizmente não há violões disponíveis nessa faixa de preço."
    assert resposta_nega_catalogo_confirmado(texto, ["buscar_produtos"])


def test_consistencia_aceita_texto_que_nao_nega_catalogo():
    texto = "Temos o Yamaha C40 disponível por R$ 900."
    assert not resposta_nega_catalogo_confirmado(texto, ["buscar_produtos"])


def test_consistencia_ignora_quando_ferramenta_nao_foi_usada():
    texto = "Infelizmente não há violões disponíveis nessa faixa de preço."
    assert not resposta_nega_catalogo_confirmado(texto, [])


def test_analisar_argumentos_aceita_only_e_delay():
    args = analisar_argumentos(["--only", "Catálogo", "--delay", "2"])
    assert args.only == "Catálogo"
    assert args.delay == 2.0


def test_analisar_argumentos_delay_padrao_zero():
    args = analisar_argumentos([])
    assert args.only is None
    assert args.delay == 0.0


def test_analisar_argumentos_rejeita_delay_negativo():
    with pytest.raises(SystemExit):
        analisar_argumentos(["--delay", "-1"])


def test_cenarios_nomes_sao_unicos():
    nomes = [n for n, _, _ in CENARIOS]
    assert len(nomes) == len(set(nomes))
