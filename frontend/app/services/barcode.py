import re
from datetime import date, datetime


BASE_DATE = date(1997, 10, 7)


def modulo10(numero: str) -> int:
    soma = 0
    peso = 2
    for i in range(len(numero) - 1, -1, -1):
        produto = int(numero[i]) * peso
        if produto > 9:
            produto = sum(int(d) for d in str(produto))
        soma += produto
        peso = 3 - peso
    resto = soma % 10
    return (10 - resto) % 10


def modulo11(numero: str, base: int = 9) -> int:
    soma = 0
    peso = 2
    for i in range(len(numero) - 1, -1, -1):
        soma += int(numero[i]) * peso
        peso += 1
        if peso > base:
            peso = 2
    resto = soma % 11
    if resto in (0, 1):
        return 0
    return 11 - resto


def _calcular_fator(vencimento: date) -> str:
    delta = (vencimento - BASE_DATE).days
    if delta > 9000:
        delta -= 9000
    return str(delta).zfill(4)[:4]


def _formatar_valor(valor: float) -> str:
    valor_int = int(round(valor * 100))
    return str(valor_int).zfill(10)[:10]


def _extrair_banco(nome_carteira: str) -> str:
    m = re.search(r'BAN(\d{3})', nome_carteira.upper())
    return m.group(1) if m else ""


def _campo_livre_748(nosso_numero: str,
                     agencia: str = "", posto: str = "",
                     codigo_cedente: str = "") -> str:
    if not nosso_numero or not codigo_cedente:
        return ""
    base = (
        "11"
        + nosso_numero.zfill(9)[-9:]
        + agencia.zfill(4)[-4:]
        + posto.zfill(2)[-2:]
        + codigo_cedente.zfill(5)[-5:]
        + "10"
    )
    if len(base) != 24:
        return ""
    dv = modulo11(base)
    return base + str(dv)


def _campo_livre_001(nosso_numero: str,
                     cod_carteira: str = "17",
                     variacao: str = "") -> str:
    if not nosso_numero:
        return ""
    nn = nosso_numero.zfill(17)[-17:]
    cart = cod_carteira.zfill(2)[-2:]
    if cart in ("00", "0", ""):
        cart = "17"
    campo = "000000" + nn + cart
    if len(campo) != 25:
        return ""
    return campo


def _campo_livre_756(nosso_numero: str,
                     cod_carteira: str = "01",
                     cooperativa: str = "",
                     cliente_cedente: str = "",
                     parcela: str = "001") -> str:
    if not cooperativa or not cliente_cedente or not nosso_numero:
        return ""
    campo = (
        cooperativa.zfill(4)[-4:]
        + "1"
        + cliente_cedente.zfill(5)[-5:]
        + nosso_numero.zfill(8)[-8:]
        + parcela.replace("/", "").zfill(3)[-3:]
        + "001"
    )
    dv = modulo11(campo)
    return campo + str(dv)


def calcular_codigo_barras(
    nome_carteira: str = "",
    nosso_numero: str = "",
    valor: float = 0.0,
    vencimento: date = None,
    cod_carteira: str = "",
    agencia: str = "",
    conta: str = "",
    digito_conta: str = "",
    parcela: str = "001",
    posto: str = "",
    beneficiario: str = "",
    codigo_cedente: str = "",
    convenio: str = "",
    variacao: str = "",
    cooperativa: str = "",
    cliente_cedente: str = "",
) -> str:
    if not nome_carteira or not nosso_numero or vencimento is None:
        return ""

    banco = _extrair_banco(nome_carteira)
    if not banco:
        return ""

    try:
        if banco == "748":
            campo_livre = _campo_livre_748(
                nosso_numero, agencia, posto, codigo_cedente or beneficiario
            )
        elif banco == "001":
            campo_livre = _campo_livre_001(
                nosso_numero, cod_carteira, variacao
            )
        elif banco == "756":
            campo_livre = _campo_livre_756(
                nosso_numero, cod_carteira, cooperativa, cliente_cedente, parcela
            )
        else:
            return ""

        if not campo_livre or len(campo_livre) != 25:
            return ""
    except Exception:
        return ""

    fator = _calcular_fator(vencimento)
    valor_fmt = _formatar_valor(valor)
    barcode_43 = banco + "9" + fator + valor_fmt + campo_livre
    dac = modulo11(barcode_43)
    return banco + "9" + str(dac) + fator + valor_fmt + campo_livre


def calcular_linha_digitavel(barcode: str) -> str:
    if len(barcode) != 44:
        return ""
    c1 = barcode[:4] + barcode[19:24]
    dv1 = modulo10(c1)
    c2 = barcode[24:34]
    dv2 = modulo10(c2)
    c3 = barcode[34:44]
    dv3 = modulo10(c3)
    c4 = barcode[4]
    c5 = barcode[5:19]
    return (
        f"{c1[:5]}.{c1[5:]}{dv1} "
        f"{c2[:5]}.{c2[5:]}{dv2} "
        f"{c3[:5]}.{c3[5:]}{dv3} "
        f"{c4} {c5}"
    )


BANCOS_SUPORTADOS = {
    "001": "Banco do Brasil",
    "748": "Sicredi",
    "756": "Sicoob",
}
