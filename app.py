# app.py completo e modificado apenas com a rota de autenticação
import os
import zipfile
import io
import re
import pandas as pd
from datetime import datetime
from flask import Flask, request, send_file, render_template_string, jsonify
from flask_cors import CORS

# Bibliotecas de PDF/Excel originais preservadas
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

app = Flask(__name__)
CORS(app)

# =========================================================================
# REGRAS DE NEGÓCIO ORIGINAIS (100% PRESERVADAS)
# =========================================================================

COORDENACOES = {
    "CIV": ["Gabriel Meyer", "Raysson Ferreira", "Kilian Alves", "Graziele Francisco", "Glauber José", "Ramon Rodrigo", "Deanne Cristina"],
    "ELT": ["Kleber Beirao", "Josué Henrique", "José Pereira", "Magdalo Neves", "Anderson Torres", "Rubervânia Maria"],
    "ELM": ["Rogério Santos", "Felipe de Andrade", "Márcio Felix", "Victor Martins", "Camila Pereira"],
    "BHS": ["Christiano Braz", "Andressa da Cruz", "Glauber Lindemberg", "Jonas Cardoso", "Ilkias Alves", "Carlos Henrique", "Guilherme Gomes"]
}

# MAPA DE TOKENS PARA COMPATIBILIDADE CORPORATIVA
# (Substitua os tokens de exemplo 'TOKEN_XYZ' pelos tokens reais da sua empresa)
TOKENS_ACESSO = {
    "A7#k": {"funcionario": "Gabriel Meyer", "coordenacao": "CIV"},
    "9@Bx": {"funcionario": "Raysson Ferreira", "coordenacao": "CIV"},
    "m4!Q": {"funcionario": "Kilian Alves", "coordenacao": "CIV"},
    "Z&2r": {"funcionario": "Graziele Francisco", "coordenacao": "CIV"},
    "p$8N": {"funcionario": "Glauber José", "coordenacao": "CIV"},
    "3*Kj": {"funcionario": "Ramon Rodrigo", "coordenacao": "CIV"},
    "h7%T": {"funcionario": "Deanne Cristina", "coordenacao": "CIV"},
    
    "Y!5c": {"funcionario": "Kleber Beirao", "coordenacao": "ELT"},
    "2@Lm": {"funcionario": "Josué Henrique", "coordenacao": "ELT"},
    "R#9v": {"funcionario": "José Pereira", "coordenacao": "ELT"},
    "g&4P": {"funcionario": "Magdalo Neves", "coordenacao": "ELT"},
    "X$1n": {"funcionario": "Anderson Torres", "coordenacao": "ELT"},
    "8!Wd": {"funcionario": "Rubervânia Maria", "coordenacao": "ELT"},
    
    "q@6K": {"funcionario": "Rogério Santos", "coordenacao": "ELM"},
    "M$3s": {"funcionario": "Felipe de Andrade", "coordenacao": "ELM"},
    "t#7J": {"funcionario": "Márcio Felix", "coordenacao": "ELM"},
    "C&5x": {"funcionario": "Victor Martins", "coordenacao": "ELM"},
    "4$Hp": {"funcionario": "Camila Pereira", "coordenacao": "ELM"},
    
    "u!8R": {"funcionario": "Christiano Braz", "coordenacao": "BHS"},
    "N@2f": {"funcionario": "Andressa da Cruz", "coordenacao": "BHS"},
    "k%9V": {"funcionario": "Glauber Lindemberg", "coordenacao": "BHS"},
    "D#1m": {"funcionario": "Jonas Cardoso", "coordenacao": "BHS"},
    "7&Qz": {"funcionario": "Ilkias Alves", "coordenacao": "BHS"},
    "b$4T": {"funcionario": "Carlos Henrique", "coordenacao": "BHS"},
    "P!6y": {"funcionario": "Guilherme Gomes", "coordenacao": "BHS"},
}

def extrair_nome_arquivo_puro(nome_completo):
    nome_puro, _ = os.path.splitext(nome_completo)
    numeros_encontrados = "".join(re.findall(r'\d+', nome_puro))
    if numeros_encontrados:
        return numeros_encontrados[:8]
    return nome_puro.strip()

def criar_overlay_carimbo(solicitante, motivo, horario_assinatura, largura=612, altura=792):
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(largura, altura))
    solicitante_upper = str(solicitante).upper()
    motivo_upper = str(motivo).upper()[:33] 
    
    can.setFillColorRGB(0, 0, 0)
    inicio_bloco_x = largura - 230
    topo_y1 = altura - 30
    topo_y2 = altura - 45
    topo_y3 = altura - 60
    topo_y4 = altura - 75
    
    can.setFont("Helvetica-Bold", 10)
    can.drawString(inicio_bloco_x, topo_y1, "CANCELAR O.S")
    can.setFont("Helvetica", 9)
    can.drawString(inicio_bloco_x, topo_y2, f"SOLICITANTE: {solicitante_upper}")
    can.drawString(inicio_bloco_x, topo_y3, f"MOTIVO: {motivo_upper}")
    texto_assinatura = f"ASSINADO DIGITALMENTE EM {horario_assinatura}"
    can.setFont("Helvetica-Bold", 8)
    can.drawString(inicio_bloco_x, topo_y4, texto_assinatura)
    
    can.save()
    packet.seek(0)
    return PdfReader(packet)

def processar_pdf_final(pdf_bytes, solicitante, motivo, horario_assinatura):
    reader_original = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    
    primeira_pagina = reader_original.pages[0]
    largura = float(primeira_pagina.mediabox.width)
    altura = float(primeira_pagina.mediabox.height)
    
    carimbo_reader = criar_overlay_carimbo(solicitante, motivo, horario_assinatura, largura, altura)
    carimbo_page = carimbo_reader.pages[0]
    primeira_pagina.merge_page(carimbo_page)
    
    for page in reader_original.pages:
        writer.add_page(page)
        
    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return output

def gerar_pdf_auditoria_protegido(df_base, coordenacao, horario_acao):
    packet = io.BytesIO()
    doc = SimpleDocTemplate(packet, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=5, bottomMargin=40)
    styles = getSampleStyleSheet()
    
    style_titulo = ParagraphStyle('TituloAudit', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=13, leading=16, textColor=colors.black, alignment=1, spaceAfter=10)
    style_label = ParagraphStyle('LabelAudit', fontName='Helvetica-Bold', fontSize=10, leading=13)
    style_value = ParagraphStyle('ValueAudit', fontName='Helvetica', fontSize=10, leading=13)
    style_item_title = ParagraphStyle('ItemTitleAudit', fontName='Helvetica-Bold', fontSize=10, leading=14, spaceBefore=10)
    style_item_detail = ParagraphStyle('ItemDetailAudit', fontName='Helvetica', fontSize=9, leading=13, leftIndent=15)
    
    elementos = []
    base_dir = os.path.dirname(os.path.abspath(__file__))
    caminho_logo = os.path.join(base_dir, "logo.png")
    if os.path.exists(caminho_logo):
        from PIL import Image as PILImage
        img_original = PILImage.open(caminho_logo)
        largura_original, altura_original = img_original.size
        largura_desejada = 105
        proporcao = altura_original / largura_original
        altura_proporcional = largura_desejada * proporcao
        
        logo = Image(caminho_logo, width=largura_desejada, height=altura_proporcional)
        tabela_logo = Table([[logo]], colWidths=[532])
        tabela_logo.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), -18), ('BOTTOMPADDING', (0,0), (-1,-1), -15),
        ]))
        elementos.append(tabela_logo)
        elementos.append(Spacer(1, 5))
    
    elementos.append(Paragraph("HISTÓRICO DE CANCELAMENTO DE ORDENS DE SERVIÇO", style_titulo))
    
    linha_divisoria = Table([[""]], colWidths=[532], rowHeights=[1])
    linha_divisoria.setStyle(TableStyle([('LINEABOVE', (0,0), (-1,-1), 1, colors.HexColor("#888888")), ('BOTTOMPADDING', (0,0), (-1,-1), 0), ('TOPPADDING', (0,0), (-1,-1), 0)]))
    elementos.append(linha_divisoria)
    elementos.append(Spacer(1, 12))
    
    dados_metadados = [
        [Paragraph("DATA/HORA DA OPERAÇÃO:", style_label), Paragraph(horario_acao, style_value)],
        [Paragraph("COORDENAÇÃO RESPONSÁVEL:", style_label), Paragraph(str(coordenacao).upper(), style_value)],
        [Paragraph("TOTAL DE PROCESSAMENTOS:", style_label), Paragraph(f"{len(df_base)} registros", style_value)]
    ]
    
    tabela_metadados = Table(dados_metadados, colWidths=[170, 362])
    tabela_metadados.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('BOTTOMPADDING', (0,0), (-1,-1), 4), ('TOPPADDING', (0,0), (-1,-1), 4), ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0)]))
    elementos.append(tabela_metadados)
    elementos.append(Spacer(1, 10))
    elementos.append(linha_divisoria)
    elementos.append(Spacer(1, 12))
    
    elementos.append(Paragraph("RELATÓRIO DETALHADO:", style_label))
    
    for idx, linha in df_base.iterrows():
        elementos.append(Paragraph(f"OS Nº {linha['Ordem']}", style_item_title))
        elementos.append(Paragraph(f"• SOLICITANTE: {str(linha['Solicitante']).upper()}", style_item_detail))
        elementos.append(Paragraph(f"• MOTIVO: {str(linha['Motivo']).upper()}", style_item_detail))
        elementos.append(Paragraph(f"• ARQUIVO ORIGINAL: {linha['Nome do Arquivo']}", style_item_detail))
        
        linha_os = Table([[""]], colWidths=[532], rowHeights=[1])
        linha_os.setStyle(TableStyle([('LINEABOVE', (0,0), (-1,-1), 0.5, colors.HexColor("#CCCCCC")), ('BOTTOMPADDING', (0,0), (-1,-1), 0), ('TOPPADDING', (0,0), (-1,-1), 4)]))
        elementos.append(linha_os)
        
    doc.build(elementos)
    packet.seek(0)
    
    reader_pdf = PdfReader(packet)
    writer_protegido = PdfWriter()
    for pagina in reader_pdf.pages:
        writer_protegido.add_page(pagina)
        
    chave_seguranca_invisivel = f"LOCK_{datetime.now().timestamp()}"
    writer_protegido.encrypt(user_password="", owner_password=chave_seguranca_invisivel, permissions_flag=int("111111000100", 2))
    
    output_final = io.BytesIO()
    writer_protegido.write(output_final)
    output_final.seek(0)
    return output_final

# =========================================================================
# ROTAS DA API WEB INTERNA
# =========================================================================

@app.route('/')
def index():
    with open('index.html', 'r', encoding='utf-8') as f:
        return render_template_string(f.read())

# NOVA ROTA: Validação de login por Token
@app.route('/login', methods=['POST'])
def login():
    dados = request.get_json() or {}
    token = dados.get("token", "").strip()
    
    if token in TOKENS_ACESSO:
        return jsonify({
            "sucesso": True,
            "funcionario": TOKENS_ACESSO[token]["funcionario"],
            "coordenacao": TOKENS_ACESSO[token]["coordenacao"]
        })
    return jsonify({"sucesso": False, "mensagem": "Token inválido ou inexistente."}), 401

@app.route('/coordenacoes', methods=['GET'])
def get_coordenacoes():
    return jsonify(COORDENACOES)

@app.route('/Analisar-arquivos', methods=['POST'])
def analisar_arquivos():
    if 'arquivos' not in request.files:
        return jsonify([])
    
    arquivos = request.files.getlist('arquivos')
    solicitante_padrao = request.form.get('solicitante_padrao', '')
    
    lista_dados = []
    for index, arq in enumerate(arquivos):
        num_os = extrair_nome_arquivo_puro(arq.filename)
        lista_dados.append({
            "id_interno": index,
            "nome_arquivo": arq.filename,
            "ordem": num_os,
            "solicitante": solicitante_padrao,
            "motivo": ""
        })
    
    df = pd.DataFrame(lista_dados)
    if not df.empty:
        if df["ordem"].str.isdigit().all():
            df["ordem_num"] = df["ordem"].astype(int)
            df = df.sort_values(by="ordem_num").drop(columns=["ordem_num"])
        else:
            df = df.sort_values(by="ordem")
        lista_dados = df.to_dict(orient='records')

    return jsonify(lista_dados)

@app.route('/processar', methods=['POST'])
def processar():
    arquivos = request.files.getlist('arquivos')
    import json
    import pytz
    
    dados_linhas = json.loads(request.form.get('dados'))
    coordenacao = request.form.get('coordenacao', 'NÃO INFORMADA')
    
    fuso_br = pytz.timezone('America/Sao_Paulo')
    horario_inicio_auditoria = datetime.now(fuso_br).strftime("%d/%m/%Y ÀS %H:%M:%S")
    
    mapa_arquivos = {i: arq for i, arq in enumerate(arquivos)}
    zip_buffer = io.BytesIO()
    registros_auditoria = []
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for dynamic_index, linha in enumerate(dados_linhas):
            id_orig = int(linha['id_interno'])
            arq_original = mapa_arquivos[id_orig]
            
            pdf_bytes = arq_original.read()
            arq_original.seek(0)
            
            horario_carimbo_atual = datetime.now(fuso_br).strftime("%d/%m/%Y ÀS %H:%M:%S")
            
            pdf_modificado = processar_pdf_final(pdf_bytes, linha['solicitante'], linha['motivo'], horario_carimbo_atual)
            zip_file.writestr(f"{str(linha['ordem']).strip()}.pdf", pdf_modificado.getvalue())
            
            registros_auditoria.append({
                "Ordem": linha['ordem'],
                "Solicitante": linha['solicitante'],
                "Motivo": linha['motivo'],
                "Nome do Arquivo": linha['nome_arquivo']
            })
            
        df_base = pd.DataFrame(registros_auditoria)
        
        df_excel = pd.DataFrame()
        df_excel[0] = df_base["Ordem"]
        df_excel[1] = "SOLICITANTE: " + df_base["Solicitante"].astype(str).str.upper()
        df_excel[2] = "MOTIVO:" + df_base["Motivo"].astype(str).str.upper()
        
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df_excel.to_excel(writer, index=False, header=False, sheet_name="Resumo Ordens")
        zip_file.writestr("Cancelar Ordens.xlsx", excel_buffer.getvalue())
        
        pdf_auditoria = gerar_pdf_auditoria_protegido(df_base, coordenacao, horario_inicio_auditoria)
        zip_file.writestr("Registro de Cancelamento.pdf", pdf_auditoria.getvalue())
        
    zip_buffer.seek(0)
    return send_file(zip_buffer, mimetype="application/zip", as_attachment=True, download_name="OS_Processadas_Completas.zip")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)