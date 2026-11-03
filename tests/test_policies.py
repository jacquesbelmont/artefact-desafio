from policies import consultar_politicas, paginas_pdf


def test_pdf_tem_oito_paginas():
    assert len(paginas_pdf()) == 8


def test_trocas_usa_paginas_corretas():
    resultado = consultar_politicas("quero devolver minha compra")
    assert 4 in [p["pagina"] for p in resultado["paginas"]]
    texto = " ".join(p["texto"] for p in resultado["paginas"])
    assert "Arrependimento" in texto


def test_horario_usa_pagina_dois():
    resultado = consultar_politicas("horário de sábado")
    assert 2 in [p["pagina"] for p in resultado["paginas"]]


def test_assunto_desconhecido_nao_inventa():
    assert "erro" in consultar_politicas("astronomia interestelar")
