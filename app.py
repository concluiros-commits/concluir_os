import os
import fitz  # PyMuPDF
import io
import zipfile
import re
from datetime import datetime
import pytz
from flask import Flask, request, send_file, render_template_string, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# =========================================================================
# BANCO DE DADOS DE FUNCIONÁRIOS
# =========================================================================
FUNCIONARIOS = {
    "M-015": "Márcio Felix", "M-016": "Felipe de Andrade",
    "B-001": "Edimilson do Nascimento", "B-002": "Glauber Lindemberg",
    "B-003": "Ilkias Alves", "B-004": "Jonas Cardoso",
    "B-005": "Carlos Henrique", "B-006": "Andressa da Cruz",
    "C-001": "Anderson Abrahão", "C-002": "Clayton Ferreira",
    "C-003": "Daniel Balbino", "C-004": "Graziele Silva",
    "C-005": "Luiz Eduardo", "C-006": "Marcelo de Paula",
    "C-007": "Mariana Paes", "C-008": "Mozar Neves",
    "C-009": "Jeorge Veloso", "C-010": "Marcos Antonio",
    "C-011": "Ramon Rodrigo", "C-012": "Margarete Rocha",
    "C-013": "Thais de amorim", "C-014": "Daniel Alves Salomão",
    "C-015": "Henrique Yamaguchi", "C-016": "Manoel Nylo",
    "C-017": "Rubens Nobre", "C-018": "Ciro Serighelli",
    "C-019": "Gabriel Borba", "C-020": "Gabriel Meyer",
    "C-021": "Antonio Marcos", "C-022": "Glauber José",
    "C-023": "Letícia Custódio", "C-024": "Deanne Cristina",
    "C-025": "Raysson Ferreira", "E-001": "Kleber Mendes",
    "E-002": "Bruno José", "E-003": "Christiano Braz",
    "E-004": "Leandro Lhucas", "E-005": "Magdalo Neves",
    "E-006": "Rafael Resende", "E-007": "Rogério Vieira",
    "E-008": "Ariclene Duarte", "E-009": "Anderson Torres",
    "E-010": "Deusivan Alves", "E-011": "Kennedy Emanuel",
    "E-012": "José Francisco", "E-013": "Maurício Alves",
    "E-014": "André Correia", "E-015": "Célio Cesar",
    "E-016": "Hebert Rego", "E-017": "Reginaldo Gomes",
    "E-018": "Leonardo Gomes", "E-019": "Ricardo Correa",
    "E-020": "Erivelton Sudre", "E-021": "José Cleve",
    "E-022": "Josué Henrique", "E-023": "Vandinaldo Moreira",
    "E-024": "Marcelo de Souza", "E-025": "Marcius Ricardo",
    "E-026": "Vansigleis Correia", "E-027": "Alessandro da Silva",
    "E-028": "Carlos Ceza Ribeiro", "E-029": "Herinaldo Pequeno",
    "E-030": "Gilvando Neves", "E-031": "Heber Goldberg",
    "E-032": "Diego Souza Pereira", "E-033": "Ricardo Silva",
    "E-034": "Ronaldo Pacheco", "E-035": "Wanderson Da Silva",
    "E-036": "Rafael Pereira", "E-037": "Alexandre Vidal",
    "E-038": "Ricardo Ferreira", "E-039": "Daniel Oliveira",
    "E-040": "Igor Silva", "E-041": "José Pereira",
    "E-042": "Márcio Vinícius", "G-001": "Kleber Faria",
    "G-002": "Echo Mike", "M-001": "Marcos Valério",
    "M-002": "Ezequiel Corrêa", "M-003": "Fernando Mendes",
    "M-004": "José Erivaldo", "M-005": "Marcelo Andrade",
    "M-006": "Márcio Moraes", "M-007": "Thalys de Souza",
    "M-008": "Luis Bianciotto", "M-009": "Israel Morais",
    "M-010": "Ricardo Cortes", "M-011": "Eduardo Amaral",
    "M-012": "Saulo Castro", "M-013": "Lindomar Ribeiro",
    "M-014": "Rogério Santos"
}

TOKENS_ACESSO = {
    "A7#k": {"coordenacao": "CIVIL"},
    "Y!5c": {"coordenacao": "ELÉTRICA"},
    "q@6K": {"coordenacao": "ELETROMECÂNICA"},
    "u!8R": {"coordenacao": "BHS"},
}

# =========================================================================
# FUNÇÕES DE APOIO
# =========================================================================

def extrair_numero_os_8_digitos(nome_arquivo):
    """Filtra o nome do arquivo e retorna apenas os primeiros 8 dígitos."""
    nome_puro = os.path.splitext(nome_arquivo)[0]
    todos_numeros = "".join(re.findall(r'\d+', nome_puro))
    return todos_numeros[:8] if todos_numeros else nome_puro

def processar_conclusao_pdf(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    nome_funcionario = "Não Identificado"

    # Percorre todas as páginas para achar a Chave Modelo do funcionário
    for pagina in doc:
        texto = pagina.get_text()
        # Busca códigos B, C, E, G ou M seguidos de hífen e 3 dígitos
        matches = re.findall(r'\b([BCEGM]-\d{3})\b', texto)
        validos = [m for m in matches if m in FUNCIONARIOS]
        if validos:
            nome_funcionario = FUNCIONARIOS[validos[-1]]
            break

    # Carimbo sempre na primeira página
    primeira_pagina = doc[0]
    largura = primeira_pagina.rect.width
    fuso = pytz.timezone('America/Sao_Paulo')
    agora = datetime.now(fuso)
    
    texto_carimbo = (
        f"CONCLUIR ORDEM DE SERVIÇO.\n"
        f"GERADA PARA REQUISIÇÃO DE MATERIAL/SERVIÇO.\n"
        f"SOLICITADO POR: {nome_funcionario.upper()}.\n"
        f"ASSINADO DIGITALMENTE EM {agora.strftime('%d/%m/%Y')} ÀS {agora.strftime('%H:%M:%S')}."
    )

    rect_texto = fitz.Rect(largura - 260, 20, largura - 10, 90)
    primeira_pagina.insert_textbox(rect_texto, texto_carimbo, fontsize=9.0, fontname="helv", align=fitz.TEXT_ALIGN_LEFT)
    
    return doc.tobytes()

# =========================================================================
# ROTAS
# =========================================================================

@app.route('/')
def index():
    with open('index.html', 'r', encoding='utf-8') as f:
        return render_template_string(f.read())

@app.route('/login', methods=['POST'])
def login():
    token = request.get_json().get("token", "")
    if token in TOKENS_ACESSO:
        return jsonify({"sucesso": True, "coordenacao": TOKENS_ACESSO[token]["coordenacao"]})
    return jsonify({"sucesso": False}), 401

@app.route('/concluir-ordens', methods=['POST'])
def concluir_ordens():
    arquivos = request.files.getlist('arquivos')
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for arq in arquivos:
            if arq.filename.lower().endswith('.pdf'):
                os_8_digitos = extrair_numero_os_8_digitos(arq.filename)
                pdf_saida = processar_conclusao_pdf(arq.read())
                zip_file.writestr(f"{os_8_digitos}.pdf", pdf_saida)
    zip_buffer.seek(0)
    return send_file(zip_buffer, mimetype="application/zip", as_attachment=True, download_name="Ordens_Concluidas.zip")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)