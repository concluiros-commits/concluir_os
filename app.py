import os
import re
import io
import zipfile
from datetime import datetime, timezone, timedelta  # Modificado aqui
from functools import wraps
from flask import Flask, render_template, request, send_file, flash, redirect, url_for, session
import fitz  # PyMuPDF

app = Flask(__name__)
app.secret_key = "chave_secreta_para_flash_messages"

# Dicionário de tokens simples por coordenação
TOKENS_COORDENACAO = {
    "BHS7K2": "BHS",
    "ELM5R1": "ELM",
    "CIV4P9": "CIV",
    "ELT8M3": "ELT"
}

# --- MAPEAMENTO COMPLETO DE MODELOS E FUNCIONÁRIOS ---
MODELOS_FUNCIONARIOS = {
    "M-015": "Márcio Felix ",
    "M-016": "Felipe de Andrade",
    "B-001": "Edimilson do Nascimento",
    "B-002": "Glauber Lindemberg",
    "B-003": "Ilkias Alves",
    "B-004": "Jonas Cardoso",
    "B-005": "Carlos Henrique",
    "B-006": "Andressa da Cruz",
    "C-001": "Anderson Abrahão",
    "C-002": "Clayton Ferreira",
    "C-003": "Daniel Balbino",
    "C-004": "Graziele Silva",
    "C-005": "Luiz Eduardo",
    "C-006": "Marcelo de Paula",
    "C-007": "Mariana Paes",
    "C-008": "Mozar Neves",
    "C-009": "Jeorge Veloso",
    "C-010": "Marcos Antonio",
    "C-011": "Ramon Rodrigo",
    "C-012": "Margarete Rocha",
    "C-013": "Thais de amorim",
    "C-014": "Daniel Alves Salomão",
    "C-015": "Henrique Yamaguchi",
    "C-016": "Manoel Nylo",
    "C-017": "Rubens Nobre",
    "C-018": "Ciro Serighelli",
    "C-019": "Gabriel Borba",
    "C-020": "Gabriel Meyer",
    "C-021": "Antonio Marcos",
    "C-022": "Glauber José",
    "C-023": "Letícia Custódio",
    "C-024": "Deanne Cristina",
    "C-025": "Raysson Ferreira",
    "E-001": "Kleber Mendes",
    "E-002": "Bruno José",
    "E-003": "Christiano Braz",
    "E-004": "Leandro Lhucas",
    "E-005": "Magdalo Neves",
    "E-006": "Rafael Resende",
    "E-007": "Rogério Vieira",
    "E-008": "Ariclene Duarte",
    "E-009": "Anderson Torres",
    "E-010": "Deusivan Alves",
    "E-011": "Kennedy Emanuel",
    "E-012": "José Francisco",
    "E-013": "Maurício Alves",
    "E-014": "André Correia",
    "E-015": "Célio Cesar",
    "E-016": "Hebert Rego",
    "E-017": "Reginaldo Gomes",
    "E-018": "Leonardo Gomes",
    "E-019": "Ricardo Correa",
    "E-020": "Erivelton Sudre",
    "E-021": "José Cleve",
    "E-022": "Josué Henrique",
    "E-023": "Vandinaldo Moreira",
    "E-024": "Marcelo de Souza",
    "E-025": "Marcius Ricardo",
    "E-026": "Vansigleis Correia",
    "E-027": "Alessandro da Silva",
    "E-028": "Carlos Ceza Ribeiro",
    "E-029": "Herinaldo Pequeno",
    "E-030": "Gilvando Neves",
    "E-031": "Heber Goldberg",
    "E-032": "Diego Souza Pereira",
    "E-033": "Ricardo Silva",
    "E-034": "Ronaldo Pacheco",
    "E-035": "Wanderson Da Silva",
    "E-036": "Rafael Pereira",
    "E-037": "Alexandre Vidal",
    "E-038": "Ricardo Ferreira",
    "E-039": "Daniel Oliveira",
    "E-040": "Igor Silva",
    "E-041": "José Pereira",
    "E-042": "Márcio Vinícius",
    "G-001": "Kleber Faria",
    "G-002": "Echo Mike",
    "M-001": "Marcos Valério",
    "M-002": "Ezequiel Corrêa",
    "M-003": "Fernando Mendes",
    "M-004": "José Erivaldo",
    "M-005": "Marcelo Andrade",
    "M-006": "Márcio Moraes",
    "M-007": "Thalys de Souza",
    "M-008": "Luis Bianciotto",
    "M-009": "Israel Morais",
    "M-010": "Ricardo Cortes",
    "M-011": "Eduardo Amaral",
    "M-012": "Saulo Castro",
    "M-013": "Lindomar Ribeiro",
    "M-014": "Rogério Santos"
}

# Modificado para incluir a nova quebra de linha após "Concluir O.S."
TEXTO_BASE = "Concluir Ordem de Serviço.\nGerada para requisição de material/serviço.\nSolicitado por: {nome_funcionario}.\nAssinado Digitalmente em {data} às {hora}."
PASTA_RAIZ = os.path.dirname(os.path.abspath(__file__))

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'coordenacao' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        token = request.form.get('token', '').strip()
        if token in TOKENS_COORDENACAO:
            session['coordenacao'] = TOKENS_COORDENACAO[token]
            return redirect(url_for('index'))
        else:
            flash('Token inválido. Tente novamente.', 'erro')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('coordenacao', None)
    return redirect(url_for('login'))

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        if 'arquivos' not in request.files:
            flash('Nenhum arquivo enviado.', 'erro')
            return redirect(request.url)
            
        arquivos = request.files.getlist('arquivos')
        arquivos_pdf = [f for f in arquivos if f.filename.lower().endswith('.pdf') and f.filename != '']
        
        if not arquivos_pdf:
            flash('Por favor, selecione ao menos um arquivo PDF válido.', 'erro')
            return redirect(request.url)

        zip_buffer = io.BytesIO()

        # Cria explicitamente o fuso horário de Brasília (UTC -3 horas)
        fuso_brasilia = timezone(timedelta(hours=-3))
        agora = datetime.now(fuso_brasilia)

        data_atual = agora.strftime("%d/%m/%Y")
        hora_atual = agora.strftime("%H:%M:%S")
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for arquivo in arquivos_pdf:
                pdf_bytes = arquivo.read()
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                
                nome_final = ""  
                modelo_detectado = "Não identificado"
                arquivo_carimbo = None
                largura_img = 80 
                altura_img = 40
                
                for pagina in doc:
                    texto_completo = pagina.get_text().upper().replace(" ", "")
                    palavras_da_pagina = [palavra[4].upper().strip() for palavra in pagina.get_text("words")]
                    
                    achou = False
                    for cod_modelo, nome_func in MODELOS_FUNCIONARIOS.items():
                        cod_sem_traco = cod_modelo.replace("-", "")
                        
                        if (cod_modelo in texto_completo or 
                            cod_sem_traco in texto_completo or 
                            cod_modelo in palavras_da_pagina):
                            
                            nome_final = nome_func
                            modelo_detectado = cod_modelo
                            arquivo_carimbo = f"carimbo {cod_modelo.lower()}.png"
                            
                            if cod_modelo == "M-016":
                                largura_img = 95
                                altura_img = 55
                            elif cod_modelo == "M-015":
                                largura_img = 85
                                altura_img = 65
                            else:
                                largura_img = 80
                                altura_img = 40
                                
                            achou = True
                            break
                    if achou:
                        break
                
                texto_carimbo = TEXTO_BASE.format(
                    nome_funcionario=nome_final, 
                    data=data_atual, 
                    hora=hora_atual
                ).upper()
                
                primeira_pagina = doc[0]
                largura = primeira_pagina.rect.width
                altura = primeira_pagina.rect.height
                
                # --- POSICIONAMENTO DA IMAGEM DO CARIMBO (MANTIDO NO RODAPÉ) ---
                if arquivo_carimbo:
                    caminho_imagem = os.path.join(PASTA_RAIZ, arquivo_carimbo)
                    if os.path.exists(caminho_imagem):
                        x1 = largura - 1 - largura_img
                        x2 = x1 + largura_img
                        
                        if modelo_detectado == "M-016":
                            y2 = float(altura) - 10  
                        else:
                            y2 = float(altura) - 20  
                            
                        y1 = y2 - altura_img
                        rect_img = fitz.Rect(x1, y1, x2, y2)
                        primeira_pagina.insert_image(rect_img, filename=caminho_imagem)
                
                # --- NOVA POSIÇÃO DO RETÂNGULO DE TEXTO EM VERMELHO (TOPO DIREITO) ---
                # Recuado 30px da margem direita (largura - 30) e começando do topo (Y inicial: 15 até 55)
                # O tamanho de fonte ajustado para 8.0 garante que o texto longo caiba sem quebras indevidas
                rect_texto = fitz.Rect(largura - 260, 20, largura - 10, 90)
                
                primeira_pagina.insert_textbox(
                    rect_texto, 
                    texto_carimbo, 
                    fontsize=9.0,
                    fontname="helv",
                    color=(0, 0, 0),             
                    align=fitz.TEXT_ALIGN_LEFT  
                )
                
                pdf_saida_bytes = doc.tobytes()
                doc.close()
                
                padrao_numero = re.match(r"^(\d+)", arquivo.filename)
                if padrao_numero:
                    novo_nome_arquivo = f"{padrao_numero.group(1)}.pdf"
                else:
                    novo_nome_arquivo = f"concluida_{arquivo.filename}"
                
                zip_file.writestr(novo_nome_arquivo, pdf_saida_bytes)
                
        zip_buffer.seek(0)
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name='OrdensRequisicao_Concluidas.zip'
        )
        
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)