from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import pandas as pd
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
import io
from google.auth.transport.requests import Request
import pickle

app = Flask(__name__)
CORS(app, supports_credentials=True, resources={
    r"/api/*": {"origins": ["https://contrutora1-2.onrender.com"]}
})

GOOGLE_SHEETS_ID = "1KimIySvsM_jPbouL8GzeZut-jXEioACe"
SHEET_NAME = "Sheet1"  # ou o nome da aba que você quer usar

def ler_dados_do_google_sheets():
    """Lê dados existentes do Google Sheets"""
    try:
        # Carrega credenciais do token
        with open("/etc/secrets/token_drive.json", "r") as token_file:
            token_info = json.load(token_file)
        creds = Credentials.from_authorized_user_info(token_info)

        # Inicializa o serviço do Sheets
        service = build("sheets", "v4", credentials=creds)

        # Lê dados da planilha
        range_name = f"{SHEET_NAME}!A:Z"  # Lê todas as colunas
        result = service.spreadsheets().values().get(
            spreadsheetId=GOOGLE_SHEETS_ID,
            range=range_name
        ).execute()
        
        values = result.get('values', [])
        
        if not values:
            print("📄 Nenhum dado encontrado no Google Sheets")
            return []
        
        # Converte para lista de dicionários usando a primeira linha como cabeçalho
        headers = values[0]
        dados = []
        
        for row in values[1:]:
            # Garante que a linha tenha o mesmo número de colunas que o cabeçalho
            while len(row) < len(headers):
                row.append('')
            
            row_dict = {}
            for i, header in enumerate(headers):
                row_dict[header] = row[i] if i < len(row) else ''
            dados.append(row_dict)
        
        print(f"✅ {len(dados)} registros carregados do Google Sheets")
        return dados

    except Exception as e:
        print(f"❌ Erro ao ler dados do Google Sheets: {e}")
        return []

def salvar_dados_no_google_sheets(df):
    try:
        # Carrega credenciais do token
        with open("/etc/secrets/token_drive.json", "r") as token_file:
            token_info = json.load(token_file)
        creds = Credentials.from_authorized_user_info(token_info)

        # Inicializa o serviço do Sheets
        service = build("sheets", "v4", credentials=creds)

        # Converte DataFrame para lista de listas
        values = [df.columns.tolist()] + df.values.tolist()

        # Limpa a planilha primeiro
        clear_request = service.spreadsheets().values().clear(
            spreadsheetId=GOOGLE_SHEETS_ID,
            range=f"{SHEET_NAME}!A:Z"
        )
        clear_request.execute()

        # Escreve os novos dados
        body = {
            'values': values
        }
        
        result = service.spreadsheets().values().update(
            spreadsheetId=GOOGLE_SHEETS_ID,
            range=f"{SHEET_NAME}!A1",
            valueInputOption='RAW',
            body=body
        ).execute()

        print(f"✅ Planilha atualizada com sucesso! {result.get('updatedCells')} células atualizadas")
        return GOOGLE_SHEETS_ID

    except Exception as e:
        print(f"❌ Erro ao salvar no Google Sheets: {e}")
        raise e
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/dashboard.html')
def dashboard_html():
    return render_template('dashboard.html')

def login():
    url = "https://api.rededeobras.com.br/api/authorization/api/Authorization/Login"
    payload = {
        "login": "integracao_jacuzzi",
        "password": "<_-54bg5-"
    }
    headers = {
        "accept": "*/*",
        "Content-Type": "application/json"
    }
    resp = requests.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    return resp.json()["data"]["token"]

def get_real_estate_report(token, type_export=1, limit_days=30):
    url = "https://api.rededeobras.com.br/export/StandardWorksReport/RealEstate"
    headers = {
        "Authorization": f"Bearer {token}",
        "accept": "application/json"
    }
    params = {
        "TypeExport": type_export,
        "LimitDays": limit_days
    }
    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    return resp.json()

@app.route('/api/obras', methods=['GET'])
def obter_obras():
    try:
        print("🔐 Autenticando na API...")
        token = login()

        print("📦 Buscando relatório de obras...")
        response = get_real_estate_report(token)

        obras = response.get("data", [])
        print(f"✅ Total de obras processadas: {len(obras)}")
        return jsonify(obras)

    except requests.HTTPError as e:
        return jsonify({"error": "HTTP Error", "status_code": e.response.status_code, "message": e.response.text}), e.response.status_code
    except Exception as e:
        return jsonify({"error": "Erro inesperado", "message": repr(e)}), 500

@app.route('/api/enviar-email', methods=['POST'])
def enviar_email():
    data = request.get_json()
    destinatario = data.get('email')
    nome_obra = data.get('obraNome')
    nome_empresa = data.get('empresaNomeFantasia')

    if not destinatario:
        return jsonify({"error": "Nenhum e-mail de destinatário fornecido."}), 400

    MAIL_USERNAME = "matheus.cabrerisso@jacuzzi.com.br"
    MAIL_PASSWORD = "Grageffe@40197386"
    MAIL_SERVER = "smtp.office365.com"
    MAIL_PORT = 587

    assunto = f"Oportunidade de Parceria para a obra: {nome_obra}"
    corpo_html = f"""
    <p>Prezada equipe da {nome_empresa},</p>
    <p>Gostaríamos de apresentar nossos produtos e soluções que podem agregar grande valor à sua obra <strong>{nome_obra}</strong>.</p>
    <p>A Jacuzzi é líder de mercado e sinônimo de qualidade e inovação. Seria um prazer agendar uma breve conversa para explorar as possibilidades de parceria.</p>
    <p>Atenciosamente,</p>
    <p>Matheus Cabrerisso<br>
    Jacuzzi</p>
    """

    try:
        msg = MIMEMultipart()
        msg['From'] = MAIL_USERNAME
        msg['To'] = destinatario
        msg['Subject'] = assunto
        msg.attach(MIMEText(corpo_html, 'html'))

        server = smtplib.SMTP(MAIL_SERVER, MAIL_PORT)
        server.starttls()
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(MAIL_USERNAME, destinatario, text)
        server.quit()

        print(f"E-mail enviado com sucesso para {destinatario}")
        return jsonify({"success": True, "message": "E-mail enviado com sucesso!"})

    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        return jsonify({"error": "Falha ao enviar e-mail", "message": str(e)}), 500

@app.route('/api/salvar-dashboard', methods=['POST'])
def salvar_dashboard():
    dados_recebidos = request.get_json()

    try:
        df = pd.DataFrame(dados_recebidos)
        df['id'] = df['id'].astype(str)

        sheets_id = salvar_dados_no_google_sheets(df)

        return jsonify({"success": True, "message": f"Dashboard atualizado no Google Sheets com ID {sheets_id}"})

    except Exception as e:
        print(f"Erro ao salvar no Sheets: {e}")
        return jsonify({"error": "Falha ao salvar no Google Sheets", "message": str(e)}), 500

@app.route('/api/carregar-dashboard', methods=['GET'])
def carregar_dashboard():
    """Carrega dados existentes do dashboard do Google Sheets"""
    try:
        dados = ler_dados_do_google_sheets()
        return jsonify({
            "success": True,
            "data": dados,
            "message": f"{len(dados)} registros carregados com sucesso"
        })
    except Exception as e:
        print(f"Erro ao carregar dashboard: {e}")
        return jsonify({
            "error": "Falha ao carregar dados do dashboard",
            "message": str(e)
        }), 500

@app.route('/api/salvar-contato-comprador', methods=['POST'])
def salvar_contato_comprador():
    dados_contato = request.get_json()
    
    try:
        # Aqui você pode salvar os dados do comprador no banco de dados
        # Por enquanto, apenas retornamos sucesso
        print(f"Contato do comprador salvo: {dados_contato}")
        
        return jsonify({
            "success": True, 
            "message": "Contato do comprador salvo com sucesso!",
            "data": dados_contato
        })
        
    except Exception as e:
        print(f"Erro ao salvar contato do comprador: {e}")
        return jsonify({
            "error": "Falha ao salvar contato do comprador", 
            "message": str(e)
        }), 500

@app.route('/health')
def health():
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
