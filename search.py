import streamlit as st
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd
from deep_translator import GoogleTranslator
import pathlib
from bs4 import BeautifulSoup
import logging
import shutil
from google.cloud import firestore
import datetime
import time
import re
import pickle
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import PorterStemmer
from collections import defaultdict
import numpy as np 
nltk.download('punkt')
nltk.download('stopwords')


key = {
  "type": st.secrets["type"],
  "project_id": st.secrets["project_id"],
  "private_key_id": st.secrets["private_key_id"],
  "private_key": st.secrets["private_key"],
  "client_email": st.secrets["client_email"],
  "client_id": st.secrets["client_id"],
  "auth_uri": st.secrets["auth_uri"],
  "token_uri": st.secrets["token_uri"],
  "auth_provider_x509_cert_url": st.secrets["auth_provider_x509_cert_url"],
  "client_x509_cert_url": st.secrets["client_x509_cert_url"],
}
GID = st.secrets["GID"]

db = firestore.Client.from_service_account_info(key)

def inject_ga():
    GA_ID = "google_analytics"
    GA_JS = """
    <!-- Google tag (gtag.js) -->
        <script async src="https://www.googletagmanager.com/gtag/js?id=""" + GID + """"></script>
        
        <script>
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());
            gtag('config', '""" + GID + """');
        </script>
    """

    # Insert the script in the head tag of the static template inside your virtual
    index_path = pathlib.Path(st.__file__).parent / "static" / "index.html"
    logging.info(f'editing {index_path}')
    soup = BeautifulSoup(index_path.read_text(), features="html.parser")
    if not soup.find(id=GA_ID): 
        bck_index = index_path.with_suffix('.bck')
        if bck_index.exists():
            shutil.copy(bck_index, index_path)  
        else:
            shutil.copy(index_path, bck_index)  
        html = str(soup)
        new_html = html.replace('<head>', '<head>\n' + GA_JS)
        index_path.write_text(new_html)

inject_ga()

def load_model(model_path):
    with open(model_path, 'rb') as f:
        return pickle.load(f)


class SearchEngine:
    def __init__(self, documents):
        df = pd.read_csv('data/main_df.csv')
        arabic = []
        self.documents=[]
        translation_col = list(df.columns)
        self.translation_col = [x for x in translation_col if "Translation" in x]

        tafaseer_col = list(df.columns)
        self.tafaseer_col = [x for x in tafaseer_col if "Tafaseer" in x]

        for index, row in df.iterrows():
            arabic.append(row['Arabic'])
            t = ""
            t += row['Name'] + " | " + str(row['Arabic'])+" | "+ str(row['Surah'])+" | "+str(row['Ayat'])+" | "
            t += row['EnglishTitle'] + " | " + str(row['ArabicTitle'])+" | "+ str(row['RomanTitle'])+" | "
            t += row['PlaceOfRevelation'] + " | "
            for j in self.translation_col:
                t += row[j] + " + "
            t += " | "
            for j in self.tafaseer_col:
                t+= row[j] + " + "
            t = t[:-3]
            self.documents.append(t)
        
        self.documents = documents
        self.total_documents = len(self.documents)
        self.stop_words = set(stopwords.words('english'))
        self.index = defaultdict(list)
        self.document_lengths = []
        self.idf = {}

        # Preprocess the documents and build the search index
        self.build_index()

    def preprocess(self, document):
        """
        Tokenize, remove stop words, and stem the words in the document.
        """
        words = word_tokenize(document.lower())
        words = [word for word in words if word.isalpha() and word not in self.stop_words]
        ps = PorterStemmer()
        words = [ps.stem(word) for word in words]
        return words

    def build_index(self):
        """
        Build an inverted index of the preprocessed documents.
        """
        for i, document in enumerate(self.documents):
            words = self.preprocess(document)
            self.document_lengths.append(len(words))
            for word in words:
                self.index[word].append(i)

        # Compute IDF for each term
        for term in self.index:
            self.idf[term] = 1 + np.log(self.total_documents / len(self.index[term]))

    def search(self, query, top_k=10):
        """
        Search the documents for the given query and return the top_k most relevant documents.
        """
        query_words = self.preprocess(query)

        # Compute the TF-IDF score for each document
        scores = defaultdict(float)
        for word in query_words:
            if word in self.index:
                for doc_id in self.index[word]:
                    tf = self.documents[doc_id].count(word) / self.document_lengths[doc_id]
                    scores[doc_id] += tf * self.idf[word]

        # Sort the documents by their scores
        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        # Return the top_k most relevant documents
        top_docs = [self.documents[doc_id] for doc_id, score in sorted_docs[:top_k]]

        return top_docs
    
    def save_model(self, model_path):
        with open(model_path, 'wb') as f:
            pickle.dump(self, f)


search = load_model('./search_model/search_engine_model.pkl')


def translate(language, query):
    # return query
    return GoogleTranslator(target=language).translate(query)


languages = {
 'English': 'en',
 'Urdu': 'ur',
 'Pashto': 'ps',
 'Sindhi': 'sd',
 'Arabic': 'ar', 
 'Azerbaijani': 'az',
 'Albanian': 'sq',
 'Bengali': 'bn',
 'Bhojpuri': 'bho',
 'Bosnian': 'bs',
 'Chinese (simplified)': 'zh-CN',
 'Chinese (traditional)': 'zh-TW',
 'Danish': 'da',
 'Dutch': 'nl',
 'French': 'fr',
 'German': 'de',
 'Gujarati': 'gu',
 'Hindi': 'hi',
 'Hebrew': 'iw',
 'Italian': 'it',
 'Japanese': 'ja',
 'Kannada': 'kn',
 'Korean': 'ko',
 'Kurdish (kurmanji)': 'ku',
 'Kurdish (sorani)': 'ckb',
 'Kyrgyz': 'ky',
 'Kazakh': 'kk',
 'Malay': 'ms',
 'Malayalam': 'ml',
 'Marathi': 'mr',
 'Persian': 'fa',
 'Russian': 'ru',
 'Spanish': 'es',
 'Turkish': 'tr',
 'Turkmen': 'tk',
 'Tamil': 'ta',
 'Tajik': 'tg',
 'Uzbek': 'uz',
 'Ukrainian': 'uk',
 }

# Streamlit Starting

st.set_page_config(page_title="Islam & AI", page_icon = "images/islam_ai.png", initial_sidebar_state = 'auto')

hide_footer_style = """
    <style>
    .reportview-container .main footer {visibility: hidden;}    
    #MainMenu {
            visibility: hidden;
        }

    footer {
             visibility: hidden;
        }
    </style>
    
    """
st.markdown(hide_footer_style, unsafe_allow_html=True)

streamlit_style = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@100&display=swap');

    html, body, [class*="css"]  {
    font-family: 'Roboto', work-sans;
    }
    </style>
    """
st.markdown(streamlit_style, unsafe_allow_html=True)

option = st.selectbox('Select Language', languages.keys())

title = "Welcome to Islam & AI"
subtitle = "Your Personal AI Assistant that uses Quranic Ayats to search for your queries! Our model is based on Natural Language Processing techniques and is designed to help you find relevant information from the Quran quickly and easily."
subtitle2 = "This is the initial model for a very big project; please give feedback, share & let us know about any questions you might have"
subtitle3 = "If you have any queries or would like to collaborate, please do contact at this email address"

st.title(translate(languages[option], title))
st.write(translate(languages[option], subtitle))
st.write(translate(languages[option], subtitle2))
st.write(translate(languages[option], subtitle3))
st.write("alizahidrajaa@gmail.com")

st.write(translate(languages[option], "Enter your email address to get updates!"))
email = st.text_input("email", translate(languages[option], "user@domain.com"))

if not email == "user@domain.com" :
    if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        # create a dictionary to store the data
        timestamp = datetime.datetime.now()
        data = {"email": email, "timestamp": timestamp}
        doc_ref = db.collection("emails").add(data)
        alert = st.warning(translate(languages[option], "Email saved successfully!")) # Display the success
        time.sleep(2) # Wait for 2 seconds
        alert.empty()
    else:
        alert = st.warning(translate(languages[option], "Invalid email!")) # Display the success
        time.sleep(2) # Wait for 2 seconds
        alert.empty()

st.subheader(translate(languages[option], "Enter your query:"))
query = st.text_input("query", translate(languages[option], "Importance of Prayer"))

st.subheader(translate(languages[option], "Select the number of queries:"))
num = st.slider("num", 2, 25, 3)

if not query == "Importance of Prayer":
    timestamp = datetime.datetime.now()
    data = {"query": query, "number": num, "timestamp": timestamp, "language": option}
    doc_ref = db.collection("queries").add(data)


query = GoogleTranslator(target='en').translate(query)
results = search.search(query, int(num))

st.title(f"**{translate(languages[option], 'Results:')}**")

if len(results) == 0:
    st.subheader(f"{translate(languages[option], 'Nothing found')}")

for r in results:
    text = r.split(" | ")
    st.subheader(f"{text[1]}")
    
    st.write(f"**{translate(languages[option], 'Surah Name')}**")
    st.write(f"**-- {text[5]} | {text[4]} | {text[6]} | {text[0]}**")

    st.write(f"**- {translate(languages[option], f'Surah No. {text[2]} | Ayat No. {text[3]}')}**")

    st.write(f"**- {translate(languages[option], f'Surah Revealed in {text[7]}')}**")

    st.subheader(f"{translate(languages[option], 'Translations:')}")
    translations = text[-2].split(" + ")
    for i in range(len(translations)):
        if len(translations[i])>2:
            st.write(f"{i+1}: {translate(languages[option], search.translation_col[i])}")
            st.write(f"{translate(languages[option], translations[i])}")
            

    st.subheader(f"{translate(languages[option], 'Tafaseer:')}")
    tafaseer = text[-1].split(" + ")
    for i in range(len(tafaseer)):
        if len(tafaseer[i])>2:
            st.write(f"{i+1}: {translate(languages[option], search.tafaseer_col[i])}")
            st.write(f"{translate(languages[option], tafaseer[i])}")
        
    st.subheader("-"*70)

footer="""<style>
a:link , a:visited{
color: green;
background-color: transparent;
text-decoration: underline;
}

a:hover,  a:active {
color: green;
background-color: transparent;
text-decoration: underline;
}

.footer {
left: 0;
bottom: 0;
width: 100%;
color: green;
text-align: center;
}
</style>
<div class="footer">
<p>Copyright @ 2023 - Islam & AI <a style='display: block; text-align: center;' href="https://www.alizahidraja.com/" target="_blank">Contact</a></p>
</div>
"""
st.markdown(footer,unsafe_allow_html=True)