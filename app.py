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

GOOGLE_DRIVE_FOLDER_ID = "1k1kAtBU1Q8t85pfpRmN-338H2u3N64Zf"

def upload_para_google_drive(df, nome_arquivo):
    try:
        # Salva o DataFrame como arquivo Excel temporário
        caminho_excel = f"/tmp/{nome_arquivo}"
        df.to_excel(caminho_excel, index=False)

        # Carrega credenciais do token
        with open("/etc/secrets/token_drive.json", "r") as token_file:
            token_info = json.load(token_file)
        creds = Credentials.from_authorized_user_info(token_info)

        # Inicializa o serviço do Drive
        service = build("drive", "v3", credentials=creds)

        # Define metadados do arquivo
        file_metadata = {
            "name": nome_arquivo,
            "parents": [GOOGLE_DRIVE_FOLDER_ID]  # <-- Para salvar na pasta correta
        }
        media = MediaFileUpload(
            caminho_excel,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id"
        ).execute()

        print(f"✅ Arquivo enviado com sucesso! ID: {file.get('id')}")
        return file.get('id')  # <-- Muito importante retornar o ID

    except Exception as e:
        print(f"❌ Erro ao fazer upload no Google Drive: {e}")
        raise e  # relevanta para o Flask capturar e retornar erro
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

        file_id = upload_para_google_drive(df, "dashboard.xlsx")

        return jsonify({"success": True, "message": f"Salvo no Google Drive com ID {file_id}"})

    except Exception as e:
        print(f"Erro ao salvar no Drive: {e}")
        return jsonify({"error": "Falha ao salvar no Google Drive", "message": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
