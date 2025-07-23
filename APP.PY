from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import pandas as pd

app = Flask(__name__)
CORS(app)

def login():
    url = "https://api.rededeobras.com.br/api/authorization/api/Authorization/Login"
    payload = {
        "login": "integracao_jacuzzi",
        "password": "<_-54bg5-"  # Substitua por variável de ambiente em produção
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

    # Credenciais - ATENÇÃO: Usar variáveis de ambiente em produção
    MAIL_USERNAME = "matheus.cabrerisso@jacuzzi.com.br"
    MAIL_PASSWORD = "Grageffe@40197386"
    
    # Configuração do servidor SMTP da Microsoft (Outlook/Office 365)
    MAIL_SERVER = "smtp.office365.com"
    MAIL_PORT = 587

    # Corpo do E-mail
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
    caminho_excel = 'database.xlsx'

    try:
        # Tenta ler o arquivo existente. Se não existir, cria um DataFrame vazio.
        if os.path.exists(caminho_excel):
            df = pd.read_excel(caminho_excel)
        else:
            df = pd.DataFrame()

        # Converte os dados recebidos para um DataFrame do pandas
        df_novos = pd.DataFrame(dados_recebidos)

        # Garante que a coluna 'id' seja do mesmo tipo em ambos os DataFrames para a mesclagem
        if not df.empty:
            df['id'] = df['id'].astype(str)
        df_novos['id'] = df_novos['id'].astype(str)

        # Remove as linhas do DataFrame antigo que têm IDs presentes nos novos dados
        if not df.empty:
            df = df[~df['id'].isin(df_novos['id'])]

        # Concatena o DataFrame antigo (sem as linhas atualizadas) com os novos dados
        df_final = pd.concat([df, df_novos], ignore_index=True)
        
        # Salva o DataFrame final no arquivo Excel
        df_final.to_excel(caminho_excel, index=False)
        
        print(f"Dados salvos com sucesso em {caminho_excel}")
        return jsonify({"success": True, "message": "Dados salvos no Excel com sucesso!"})

    except Exception as e:
        print(f"Erro ao salvar no Excel: {e}")
        return jsonify({"error": "Falha ao salvar no Excel", "message": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
