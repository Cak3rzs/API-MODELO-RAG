from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from dotenv import load_dotenv
from flasgger import Swagger
import os
import uuid
from utils import processar_arquivo, gerar_resposta

# Configurações
load_dotenv()
app = Flask(__name__)
swagger = Swagger(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Conexão MongoDB
uri = os.getenv("MONGO_URI")
client = MongoClient(uri)
db = client["chatpdf"]
collection = db["contextos"]

# Página principal
@app.route('/')
def index():
    return render_template("index.html")

# Upload de arquivos (PDF, CSV, DOCX)
@app.route("/upload_context", methods=["POST"])
def upload_context():
    """
    Endpoint para upload de arquivos PDF, CSV ou DOCX.
    O arquivo é processado e indexado no banco de dados.
    ---
    consumes:
      - multipart/form-data
    parameters:
      - name: file
        in: formData
        type: file
        required: true
        description: O arquivo a ser enviado (PDF, CSV, DOCX)
    responses:
      200:
        description: Arquivo processado com sucesso
      400:
        description: Erro ao enviar o arquivo ou formato não suportado
    """
    if "file" not in request.files:
        return jsonify({"erro": "Nenhum arquivo enviado"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"erro": "Arquivo vazio"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    allowed_ext = {".pdf", ".csv", ".docx"}
    if ext not in allowed_ext:
        return jsonify({"erro": "Formato de arquivo não suportado"}), 400

    filename = secure_filename(file.filename)
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(path)

    # Processar e indexar
    contexto_id = str(uuid.uuid4())
    try:
        processar_arquivo(path, contexto_id)
        os.remove(path)
    except Exception as e:
        return jsonify({"erro": f"Erro ao processar arquivo: {str(e)}"}), 500

    return jsonify({"mensagem": "Arquivo processado com sucesso", "contexto_id": contexto_id}), 200

# Pergunta ao modelo com base no contexto carregado
@app.route("/ask", methods=["POST"])
def perguntar():
    """
    Endpoint para perguntar ao modelo com base no contexto carregado.
    ---
    parameters:
      - name: pergunta
        in: body
        type: string
        required: true
        description: A pergunta a ser respondida
      - name: contexto_id
        in: body
        type: string
        required: true
        description: O ID do contexto para buscar a resposta
    responses:
      200:
        description: Resposta gerada com sucesso
      400:
        description: Pergunta ou contexto_id não fornecidos
    """
    data = request.json
    pergunta = data.get("pergunta")
    contexto_id = data.get("contexto_id")

    if not pergunta or not contexto_id:
        return jsonify({"erro": "Pergunta e contexto_id são obrigatórios"}), 400

    resposta = gerar_resposta(pergunta, contexto_id)
    collection.insert_one({"contexto_id": contexto_id, "pergunta": pergunta, "resposta": resposta})
    return jsonify({"resposta": resposta})

# Lista todas as perguntas e respostas
@app.route("/answers", methods=["GET"])
def listar_respostas():
    """
    Endpoint para listar todas as perguntas e respostas já feitas.
    ---
    responses:
      200:
        description: Lista de perguntas e respostas
    """
    docs = list(collection.find({}, {"_id": 0, "pergunta": 1, "resposta": 1}))
    return jsonify(docs)

if __name__ == "__main__":
    app.run(debug=True)
