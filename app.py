from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import pandas as pd
from flask import render_template
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from io import BytesIO
import json

app = Flask(__name__)
# Permitir acesso apenas do domínio do frontend ou de todos (*)

CORS(app, supports_credentials=True, resources={
    r"/api/*": {"origins": ["https://contrutora1-2.onrender.com"]}
})
GOOGLE_CREDENTIALS_FILE = "credenciais_drive.json"
GOOGLE_DRIVE_FOLDER_ID = "1k1kAtBU1Q8t85pfpRmN-338H2u3N64Zf"  # Copie da URL da pasta

def upload_para_google_drive(df, filename):
    # Autentica com conta de serviço
    credentials = service_account.Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_FILE,
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    service = build("drive", "v3", credentials=credentials)

    # Salva o Excel em memória
    file_stream = BytesIO()
    df.to_excel(file_stream, index=False)
    file_stream.seek(0)

    # Prepara upload
    media = MediaIoBaseUpload(file_stream, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    file_metadata = {
        "name": filename,
        "parents": [GOOGLE_DRIVE_FOLDER_ID]
    }

    # Faz o upload
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id"
    ).execute()

    return file.get("id")
# Rota para servir o index.html (homepage)
@app.route('/')
def home():
    return render_template('index.html')

# Rota para servir o dashboard.html

@app.route('/dashboard.html')
def dashboard_html():
    return render_template('dashboard.html')  # ✅ CORRETO



def login():
    url = "https://api.rededeobras.com.br/api/authorization/api/Authorization/Login"
    payload = {
        "login": "integracao_jacuzzi",
        "password": "<_-54bg5-"  # Em produção, use variável de ambiente
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
    import os
    port = int(os.environ.get("PORT", 10000))  # padrão do Render
    app.run(host="0.0.0.0", port=port)
