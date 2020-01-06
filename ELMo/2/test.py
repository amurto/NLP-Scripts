# -*- coding: utf-8 -*-
"""test.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1hYlM8eUGKQoSpeSbH0qoJXIv0F159SOx
"""

from google.colab import drive
drive.mount('/content/drive')

# Download the StanfordCoreNLP package
# We will use this package to extract verb phrases from sentences
!wget http://nlp.stanford.edu/software/stanford-corenlp-full-2018-10-05.zip

import zipfile

fh = open('stanford-corenlp-full-2018-10-05.zip', 'rb')
z = zipfile.ZipFile(fh)
for name in z.namelist():
    outpath = "/content/drive/My Drive/Causal_Relation_Extraction/Production/stanfordcorenlp"
    z.extract(name, outpath)
fh.close()

pip install stanfordcorenlp

import pandas as pd
import numpy as np
from nltk.tokenize import word_tokenize
from nltk import pos_tag
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from sklearn.preprocessing import LabelEncoder
from collections import defaultdict
from nltk.corpus import wordnet as wn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn import model_selection, svm
from sklearn.metrics import accuracy_score
import pickle 
import re
import json

from stanfordcorenlp import StanfordCoreNLP
from nltk.tree import Tree
nlp = StanfordCoreNLP('/content/drive/My Drive/Causal_Relation_Extraction/Production/stanfordcorenlp/stanford-corenlp-full-2018-10-05')

import nltk
nltk.download('punkt')
nltk.download('wordnet')
nltk.download('averaged_perceptron_tagger')
nltk.download('stopwords')

import spacy
# import spaCy's language model
nx = spacy.load('en', disable=['parser', 'ner'])

# function to lemmatize text
def lemmatization(texts):
    output = []
    for i in texts:
        s = [token.lemma_ for token in nx(i)]
        output.append(' '.join(s))
    return output

# form a parse tree of the sentence
# Extract the phrases
def extract_phrase(tree_str, label):
    phrases = []
    trees = Tree.fromstring(tree_str)
    for tree in trees:
        for subtree in tree.subtrees():
            if subtree.label() == label:
                t = subtree
                t = ' '.join(t.leaves())
                phrases.append(t)

    return phrases

# Check if the sentence contains a noun phrase and a verb phrase
def is_npvp(sentence):
  tree_str = nlp.parse(sentence)
  nps = extract_phrase(tree_str, 'NP')
  vps = extract_phrase(tree_str, 'VP')
  if len(nps) == 0 or len(vps) == 0:
    return False
  else:
    vpl = vps[0].split(" ")
    if len(vpl) > 1:
      return True
    else: 
      return False

import tensorflow_hub as hub
import tensorflow as tf

elmo = hub.Module("https://tfhub.dev/google/elmo/2", trainable=True)

def elmo_vectors(x):
  embeddings = elmo(x.tolist(), signature="default", as_dict=True)["elmo"]

  with tf.Session() as sess:
    sess.run(tf.global_variables_initializer())
    sess.run(tf.tables_initializer())
    # return average of ELMo features
    return sess.run(tf.reduce_mean(embeddings,1))

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score

# load the model from disk
loaded_model = pickle.load(open('/content/drive/My Drive/Causal_Relation_Extraction/Production/finalized_model.sav', 'rb'))
#result = loaded_model.predict(xvalid)

list_query = [query[i:i+100] for i in range(0,query.shape[0],100)]

elmo_query = [elmo_vectors(x['clean_sent']) for x in list_query]
elmo_query_new = np.concatenate(elmo_query, axis = 0)

# make predictions on test set
preds_query = lreg.predict(elmo_query_new)
preds_conf = lreg.decision_function(elmo_query_new)

def test1():
  from sklearn.externals import joblib 

  # Load the model from the file 
  cfcd = joblib.load('/content/drive/My Drive/Causal_Relation_Extraction/Production/cr_model.pkl')
  text = input("Enter text: ") 

  if not text:
    print("No text entered")
  else:
    from nltk import tokenize

    sentences = tokenize.sent_tokenize(text)
    label = []
    for i in range(len(sentences)):
      label.append(0)

    rawSentences = pd.DataFrame(list(zip(sentences, label)), 
                columns =['sentences', 'label'])
    sent_tokens = get_sent_token(rawSentences)

    if sent_tokens.empty:
      print("No causes found")
      text_and_causes = get_json_from_pd(text, sent_tokens)
      print(text_and_causes)
    else:
      ind = sent_tokens['loc'].tolist()
      print(sent_tokens)
      rawSentences = rawSentences.loc[ ind , : ]
      rawSentences.reset_index(drop = True, inplace = True)
      
      # Testing phase
      tf_features = pickle.load(open("/content/drive/My Drive/Causal_Relation_Extraction/Production/cr_features.pkl", 'rb'))

      sent_Tfidf = tf_features.transform(sent_tokens['sentences_final'])
      
      print(rawSentences)
      label_predictions = cfcd.predict(sent_Tfidf)
      n = rawSentences.columns[1]
      # Drop that column
      rawSentences.drop(n, axis = 1, inplace = True)

      rawSentences[n] = label_predictions.tolist()
      print(rawSentences)

      #convert to json format
      text_and_causes = get_json_from_pd(text, rawSentences)
      print(text_and_causes)

def get_sent_token(Sent):
  # Step - a : Remove blank rows if any.
  rawSent = Sent.copy()
  rawSent['sentences'].dropna(inplace=True)

  # remove URL's from train and test
  rawSent['clean_sentences'] = rawSent['sentences'].apply(lambda x: re.sub(r'http\S+', '', x)) 
  
  # Step - b : Change all the sentences to lower case. This is required as python interprets 'dog' and 'DOG' differently
  rawSent['clean_sentences'] = [entry.lower() for entry in rawSent['clean_sentences']]

  # Step - c : Remove all special symbols 
  # remove punctuation marks
  punctuation = '!"#$%&()*+-/:;<=>?@[\\]^_`{|}~'

  rawSent['clean_sentences'] = rawSent['clean_sentences'].apply(lambda x: ''.join(ch for ch in x if ch not in set(punctuation)))

  rel = [' consequently', 
         ' as a result ', 
         ' therefore', 
         ' as a consequence', 
         ' for this reason', 
         ' for all these reasons', 
         ' thus',
         ' because', 
         ' since ',
         ' cause of', 
         ' because of',
         ' after', 
         ' as '
         ]
  
  vsent = []  
  og_sents = []    
  for sent in rawSent['clean_sentences']:
    if any(x in sent for x in rel):
      if is_npvp(sent):
        vsent.append(sent)
        i = rawSent.clean_sentences[rawSent.clean_sentences == sent].index.tolist()
        og_sents.append(rawSent['sentences'].iloc[i[0]])
  if len(vsent) == 0:
    emp = pd.DataFrame()
    return emp
  else:
    polSent = pd.DataFrame(list(zip(vsent, og_sents)), 
                columns =['clean_sentences', 'sentences'])
    polSent['clean_sentences'] = lemmatization(polSent['clean_sentences'])
    return polSent

def test():
  from sklearn.externals import joblib 

  # Load the model from the file 
  cfcd = joblib.load('/content/drive/My Drive/Causal_Relation_Extraction/Production/cr_model.pkl')
  text = input("Enter text: ") 

  if not text:
    print("No text entered")
  else:
    from nltk import tokenize

    sentences = tokenize.sent_tokenize(text)
    label = []
    for i in range(len(sentences)):
      label.append(0)

    rawSentences = pd.DataFrame(list(zip(sentences, label)), 
                columns =['sentences', 'label'])
    sent_tokens = get_sent_token(rawSentences)
    if sent_tokens.empty:
      print("No causes found")
      text_and_causes = get_json_from_pd(sent_tokens)
      print(text_and_causes)
    else:
      list_query = [sent_tokens[i:i+100] for i in range(0,sent_tokens.shape[0],100)]
      elmo_query = [elmo_vectors(x['clean_sentences']) for x in list_query]
      elmo_query_new = np.concatenate(elmo_query, axis = 0)
      # make predictions on test set
      # load the model from disk
      loaded_model = pickle.load(open('/content/drive/My Drive/Causal_Relation_Extraction/Production/finalized_model.sav', 'rb'))
      preds_query = loaded_model.predict(elmo_query_new)
      preds_conf = loaded_model.decision_function(elmo_query_new)
      sent_tokens['labels'] = preds_query
      sent_tokens['score'] = preds_conf

      #convert to json format
      text_and_causes = get_json_from_pd(sent_tokens)
      print(text_and_causes)

def get_json_from_pd(rawSentences):
  if rawSentences.empty:
    thisdict = {
      "causes": []
    }
  else:
    rawSentences = rawSentences[rawSentences.score >= 2]
    rawSentences['score'] = [float((entry + 10)/20) for entry in rawSentences['score']]
    causes = rawSentences['sentences'].tolist()
    scores = rawSentences['score'].tolist()
    for i in range(0, len(scores)):
      if scores[i] > 1:
        scores[i] = 1
    thisdict = {
      "causes": causes,
      "scores": scores
    }
  text_and_causes = json.dumps(thisdict)
  return text_and_causes

test()
