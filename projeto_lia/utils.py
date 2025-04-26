import os
from langchain_community.document_loaders import PyPDFLoader, CSVLoader, Docx2txtLoader
from langchain_community.vectorstores import MongoDBAtlasVectorSearch
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.chains import RetrievalQA
from langchain_groq import ChatGroq
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# MongoDB
client = MongoClient(os.getenv("MONGO_URI"))
db = client["chatpdf"]
collection = db["contextos"]

# Embeddings e LLM
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
llm = ChatGroq(model="llama3-70b-8192", api_key=os.getenv("GROQ_API_KEY"))

# Variáveis globais (único contexto por vez)
retriever = None
qa_chain = None
contexto_carregado = None

def processar_arquivo(caminho_arquivo, contexto_id):
    global retriever, qa_chain, contexto_carregado

    ext = os.path.splitext(caminho_arquivo)[1].lower()
    if ext == ".pdf":
        loader = PyPDFLoader(caminho_arquivo)
    elif ext == ".csv":
        loader = CSVLoader(caminho_arquivo)
    elif ext == ".docx":
        loader = Docx2txtLoader(caminho_arquivo)
    else:
        raise ValueError("Formato de arquivo não suportado.")

    documentos = loader.load()

    # Indexa no MongoDB Atlas Vector Search
    vectorstore = MongoDBAtlasVectorSearch.from_documents(
        documents=documentos,
        embedding=embeddings,
        collection=collection,
        index_name=f"contexto_{contexto_id}"
    )

    retriever = vectorstore.as_retriever()
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        return_source_documents=True
    )
    contexto_carregado = contexto_id

def gerar_resposta(pergunta, contexto_id):
    if not qa_chain or contexto_id != contexto_carregado:
        return "Nenhum contexto válido carregado. Faça upload de um arquivo primeiro."

    resposta = qa_chain({"query": pergunta})
    return resposta["result"]
