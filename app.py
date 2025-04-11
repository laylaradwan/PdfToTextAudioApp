# pdf_to_text_audio_app.py

import streamlit as st
import os
import dropbox
import fitz  # PyMuPDF
from docx import Document
from google.cloud import texttospeech
import sqlite3
import uuid

# ------------------------
# CONFIGURATION
# ------------------------
DROPBOX_ACCESS_TOKEN = "YOUR_DROPBOX_ACCESS_TOKEN"
GOOGLE_CLOUD_CREDENTIALS = "YOUR_GOOGLE_CREDENTIALS.json"
DROPBOX_FOLDER_PATH = "/Livres"
DB_PATH = "livres.db"

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_CLOUD_CREDENTIALS

db = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

# ------------------------
# DATABASE SETUP
# ------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS livres (
                 id TEXT PRIMARY KEY,
                 titre TEXT,
                 texte_path TEXT,
                 audio_path TEXT
                 )''')
    conn.commit()
    conn.close()

# ------------------------
# PDF PROCESSING
# ------------------------
def download_pdf_files():
    entries = db.files_list_folder(DROPBOX_FOLDER_PATH).entries
    files = [f for f in entries if isinstance(f, dropbox.files.FileMetadata)]
    local_paths = []
    for file in files:
        local_path = os.path.join("temp", file.name)
        with open(local_path, "wb") as f:
            metadata, res = db.files_download(file.path_lower)
            f.write(res.content)
        local_paths.append(local_path)
    return local_paths

def split_pdf(path):
    doc = fitz.open(path)
    chunks = []
    for i in range(0, len(doc), 100):
        chunk = doc[i:i+100]
        temp_path = f"temp/{uuid.uuid4().hex}.pdf"
        chunk.save(temp_path)
        chunks.append(temp_path)
    return chunks

# ------------------------
# DUMMY GEMINI & TEXT CLEANING
# ------------------------
def gemini_ocr(pdf_path):
    # Dummy extraction
    return f"Texte brut extrait de {pdf_path}"

def clean_text(raw_text):
    # Dummy clean
    return raw_text.replace("\n", " ").strip()

# ------------------------
# WORD + AUDIO GENERATION
# ------------------------
def save_as_word(titre, full_text):
    doc = Document()
    doc.add_paragraph(full_text)
    path = f"output/{titre}.docx"
    doc.save(path)
    return path

def text_to_speech(titre, text):
    client = texttospeech.TextToSpeechClient()
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(language_code="fr-FR", ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL)
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
    response = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
    audio_path = f"output/{titre}.mp3"
    with open(audio_path, "wb") as out:
        out.write(response.audio_content)
    return audio_path

# ------------------------
# PROCESS ALL PDF FILES
# ------------------------
def process_all():
    pdfs = download_pdf_files()
    for pdf in pdfs:
        titre = os.path.splitext(os.path.basename(pdf))[0]
        chunks = split_pdf(pdf)
        all_cleaned = []
        for chunk in chunks:
            raw_text = gemini_ocr(chunk)
            clean = clean_text(raw_text)
            all_cleaned.append(clean)
        full_text = "\n".join(all_cleaned)
        word_path = save_as_word(titre, full_text)
        audio_path = text_to_speech(titre, full_text)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO livres VALUES (?, ?, ?, ?)",
                  (uuid.uuid4().hex, titre, word_path, audio_path))
        conn.commit()
        conn.close()

# ------------------------
# STREAMLIT UI
# ------------------------
init_db()

st.title("📚 Bibliothèque Intelligente")

if st.button("🛠️ Traiter les nouveaux fichiers PDF"):
    with st.spinner("Traitement en cours..."):
        process_all()
    st.success("Tous les fichiers ont été traités avec succès!")

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("SELECT titre, texte_path, audio_path FROM livres")
data = c.fetchall()
conn.close()

livres = {titre: (texte, audio) for titre, texte, audio in data}
titres = list(livres.keys())

if titres:
    choix = st.selectbox("📖 Choisissez un livre", titres)
    mode = st.radio("🧏‍♂️ Mode de lecture", ["Texte", "Audio"])

    if mode == "Texte":
        with open(livres[choix][0], "r") as f:
            st.text(f.read())
    else:
        audio_path = livres[choix][1]
        st.audio(audio_path)
else:
    st.info("Aucun livre disponible. Veuillez en ajouter depuis Dropbox et relancer le traitement.")
