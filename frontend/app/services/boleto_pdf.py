import os
import re
from datetime import date


LINHA_REGEX = re.compile(
    r"\d{5}\.\d{5}\s+\d{5}\.\d{6}\s+\d{5}\.\d{6}\s+\d\s+\d{14}"
)


def _build_pdf_path(
    diretorio_base: str,
    prefixo: str,
    num_boleto: str,
    nosso_numero: str,
    data: date,
) -> str:
    num_limpo = num_boleto.replace("/", "").replace("\\", "").strip()
    filename = f"{prefixo}{num_limpo}_{nosso_numero}.pdf"
    return os.path.join(
        diretorio_base,
        str(data.year),
        f"{data.month:02d}",
        filename,
    )


def _extrair_linha_do_texto(texto: str) -> str | None:
    for linha in texto.splitlines():
        linha = linha.strip()
        if LINHA_REGEX.match(linha):
            return linha
    return None


def _linha_para_barcode(linha: str) -> str:
    campos = linha.strip().split()
    if len(campos) != 5:
        return ""

    f1 = campos[0].replace(".", "")   # 10 chars
    f2 = campos[1].replace(".", "")   # 11 chars
    f3 = campos[2].replace(".", "")   # 11 chars
    f4 = campos[3]                    # 1 char  (DAC)
    f5 = campos[4]                    # 14 chars (fator + valor)

    if not (len(f1) == 10 and len(f2) == 11 and len(f3) == 11 and len(f4) == 1 and len(f5) == 14):
        return ""

    c1 = f1[:9]           # 9 chars: banco(3) + moeda(1) + campo[0:5]
    c2 = f2[:10]          # 10 chars: campo[5:15]
    c3 = f3[:10]          # 10 chars: campo[15:25]

    banco = c1[:3]
    moeda = c1[3]
    campo_livre = c1[4:] + c2 + c3

    return banco + moeda + f4 + f5 + campo_livre


def buscar_codigo_e_linha(
    diretorio_base: str,
    prefixo: str,
    num_boleto: str,
    nosso_numero: str,
    data: date,
) -> tuple[str, str] | None:
    pdf_path = _build_pdf_path(
        diretorio_base, prefixo, num_boleto, nosso_numero, data
    )

    if not os.path.isfile(pdf_path):
        return None

    try:
        import fitz
        doc = fitz.open(pdf_path)
        texto = doc[0].get_text()
        doc.close()
    except Exception:
        return None

    linha = _extrair_linha_do_texto(texto)
    if not linha:
        return None

    barcode = _linha_para_barcode(linha)
    return barcode, linha
