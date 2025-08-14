from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import pandas as pd
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = Flask(__name__)
CORS(app, supports_credentials=True, resources={
    r"/api/*": {"origins": ["https://contrutora1-2.onrender.com"]}
})

GOOGLE_DRIVE_FOLDER_ID = "1k1kAtBU1Q8t85pfpRmN-338H2u3N64Zf"
DASHBOARD_FILE_NAME = "dashboard_obras.xlsx"

# -----------------------------------------------
# Google Drive Helpers
# -----------------------------------------------
def buscar_arquivo_existente(service, nome_arquivo):
    try:
        query = f"name='{nome_arquivo}' and parents in '{GOOGLE_DRIVE_FOLDER_ID}' and trashed=false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])
        return files[0]['id'] if files else None
    except Exception as e:
        print(f"Erro ao buscar arquivo existente: {e}")
        return None

def upload_para_google_drive(df, nome_arquivo):
    try:
        caminho_excel = f"/tmp/{nome_arquivo}"
        df.to_excel(caminho_excel, index=False)

        with open("/etc/secrets/token_drive.json", "r") as token_file:
            token_info = json.load(token_file)
        creds = Credentials.from_authorized_user_info(token_info)
        service = build("drive", "v3", credentials=creds)

        arquivo_existente_id = buscar_arquivo_existente(service, nome_arquivo)
        media = MediaFileUpload(
            caminho_excel,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        if arquivo_existente_id:
            file = service.files().update(
                fileId=arquivo_existente_id,
                media_body=media,
                fields="id"
            ).execute()
            print(f"✅ Arquivo atualizado com sucesso! ID: {file.get('id')}")
        else:
            file_metadata = {"name": nome_arquivo, "parents": [GOOGLE_DRIVE_FOLDER_ID]}
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id"
            ).execute()
            print(f"✅ Novo arquivo criado com sucesso! ID: {file.get('id')}")

        return file.get('id')
    except Exception as e:
        print(f"❌ Erro ao fazer upload no Google Drive: {e}")
        raise e

# -----------------------------------------------
# Rotas de Frontend
# -----------------------------------------------
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/dashboard.html')
def dashboard_html():
    return render_template('dashboard.html')

# -----------------------------------------------
# API Rededeobras
# -----------------------------------------------
def login():
    url = "https://api.rededeobras.com.br/api/authorization/api/Authorization/Login"
    payload = {"login": "integracao_jacuzzi", "password": "<_-54bg5-"}
    headers = {"accept": "*/*", "Content-Type": "application/json"}
    resp = requests.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    return resp.json()["data"]["token"]

def get_real_estate_report_paginated(token, limit_obras=5000, chunk_size=500):
    """Busca obras da API em blocos para economizar memória"""
    url = "https://api.rededeobras.com.br/export/StandardWorksReport/RealEstate"
    headers = {"Authorization": f"Bearer {token}", "accept": "application/json"}
    todas_obras = []
    offset = 0

    while len(todas_obras) < limit_obras:
        params = {
            "TypeExport": 1,
            "LimitDays": 30,
            "Offset": offset,  # Supondo que a API aceite offset (se não, precisamos outro parâmetro)
            "Limit": min(chunk_size, limit_obras - len(todas_obras))
        }
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        if not data:
            break
        todas_obras.extend(data)
        offset += len(data)
    return todas_obras
    
@app.route('/api/obras', methods=['GET'])
def obter_obras():
    try:
        print("🔐 Autenticando na API...")
        token = login()

        print("📦 Buscando relatório de obras...")
        obras = get_real_estate_report(token, limit_obras=5000)

        print(f"✅ Total de obras processadas: {len(obras)}")
        return jsonify(obras)
    except requests.HTTPError as e:
        return jsonify({"error": "HTTP Error", "status_code": e.response.status_code, "message": e.response.text}), e.response.status_code
    except Exception as e:
        return jsonify({"error": "Erro inesperado", "message": repr(e)}), 500

# -----------------------------------------------
# Envio de E-mails
# -----------------------------------------------
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
    <p>Matheus Cabrerisso<br>Jacuzzi</p>
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
        server.sendmail(MAIL_USERNAME, destinatario, msg.as_string())
        server.quit()

        print(f"E-mail enviado com sucesso para {destinatario}")
        return jsonify({"success": True, "message": "E-mail enviado com sucesso!"})
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        return jsonify({"error": "Falha ao enviar e-mail", "message": str(e)}), 500

# -----------------------------------------------
# Salvar Dashboard
# -----------------------------------------------
@app.route('/api/salvar-dashboard', methods=['POST'])
def salvar_dashboard():
    dados_recebidos = request.get_json()
    try:
        df = pd.DataFrame(dados_recebidos)
        df['id'] = df['id'].astype(str)
        file_id = upload_para_google_drive(df, DASHBOARD_FILE_NAME)
        return jsonify({"success": True, "message": f"Dashboard atualizado no Google Drive com ID {file_id}"})
    except Exception as e:
        print(f"Erro ao salvar no Drive: {e}")
        return jsonify({"error": "Falha ao salvar no Google Drive", "message": str(e)}), 500

# -----------------------------------------------
# Salvar Contato do Comprador
# -----------------------------------------------
@app.route('/api/salvar-contato-comprador', methods=['POST'])
def salvar_contato_comprador():
    dados_contato = request.get_json()
    try:
        print(f"Contato do comprador salvo: {dados_contato}")
        return jsonify({"success": True, "message": "Contato do comprador salvo com sucesso!", "data": dados_contato})
    except Exception as e:
        print(f"Erro ao salvar contato do comprador: {e}")
        return jsonify({"error": "Falha ao salvar contato do comprador", "message": str(e)}), 500

# -----------------------------------------------
# Healthcheck
# -----------------------------------------------
@app.route('/health')
def health():
    return "OK", 200

# -----------------------------------------------
# Inicialização do App
# -----------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
