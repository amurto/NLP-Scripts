# -*- coding: utf-8 -*-
"""Untitled4.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1gi8oL04nB5D5yPKHNHwZuI9vSgImoex8
"""

########## make sure to exract all the zips ##########

from google.colab import drive
drive.mount('/content/drive')

!pip install pytorch-pretrained-bert

import os, sys, shutil
import time
import gc
from contextlib import contextmanager
from pathlib import Path
import random
import numpy as np, pandas as pd
from tqdm import tqdm, tqdm_notebook
import json

# Commented out IPython magic to ensure Python compatibility.
from sklearn.metrics import f1_score, classification_report
from sklearn.preprocessing import LabelBinarizer
import torch
import torch.nn as nn
import torch.utils.data

from matplotlib import pyplot as plt
# %config InlineBackend.figure_formats = ['retina']
from pytorch_pretrained_bert import convert_tf_checkpoint_to_pytorch
from pytorch_pretrained_bert import BertTokenizer, BertForSequenceClassification, BertAdam, BertConfig

MAX_SEQUENCE_LENGTH = 512    # maximal possible sequence length is 512. Generally, the higher, the better, but more GPU memory consumed
BATCH_SIZE = 1              # refer to the table here https://github.com/google-research/bert to adjust batch size to seq length

SEED = 1234
EPOCHS = 2                                   
PATH_TO_DATA=Path("/content/drive/My Drive/cb1bert") # path to model
WORK_DIR=Path("/content/drive/My Drive/cb1bert") # path to model

LRATE = 2e-5             # hard to tune with BERT, but this shall be fine (improvements: LR schedules, fast.ai wrapper for LR adjustment)
ACCUM_STEPS = 2          # wait for several backward steps, then one optimization step, this allows to use larger batch size
                         # well explained here https://medium.com/huggingface/training-larger-batches-practical-tips-on-1-gpu-multi-gpu-distributed-setups-ec88c3e51255
WARMUP = 5e-2            # warmup helps to tackle instability in the initial phase of training with large learning rates. 
                         # During warmup, learning rate is gradually increased from 0 to LRATE.
                         # WARMUP is a proportion of total weight updates for which warmup is done. By default, it's linear warmup

#reporting the running times
@contextmanager
def timer(name):
    t0 = time.time()
    yield
    print(f'[{name}] done in {time.time() - t0:.0f} s')

# Converting the lines to BERT format
def convert_lines(example, max_seq_length, tokenizer):
    max_seq_length -= 2
    all_tokens = []
    longer = 0
    for text in tqdm_notebook(example):
        tokens_a = tokenizer.tokenize(text)
        if len(tokens_a) > max_seq_length:
            tokens_a = tokens_a[:max_seq_length]
            longer += 1
        one_token = tokenizer.convert_tokens_to_ids(["[CLS]"] + tokens_a + ["[SEP]"]) + [0] * (max_seq_length - len(tokens_a))
        all_tokens.append(one_token)
    print(f"There are {longer} lines longer than {max_seq_length}")
    return np.array(all_tokens)

device = torch.device('cpu')
BERT_MODEL_PATH = Path('/content/drive/My Drive/cb1bert/uncased_L-12_H-768_A-12/')
model = BertForSequenceClassification.from_pretrained(WORK_DIR,
                                                          cache_dir=None,
                                                          num_labels=3)
model.load_state_dict(torch.load('/content/drive/My Drive/cb1bert/bert_pytorch.bin', map_location='cpu'))

def test():
  tokenizer = BertTokenizer.from_pretrained(BERT_MODEL_PATH, cache_dir=None,
                                                do_lower_case=True)
  print("Enter title")
  title = input()
  print("Enter text")
  text = input()

  # intialise data of lists. 
  input_data = {'title':[title], 'text':[text]} 
    
  # Create DataFrame 
  input_df = pd.DataFrame(input_data) 
    
  input_df['text'] = input_df['title'].astype(str).fillna("DUMMY_VALUE") + '_' + input_df['text'].astype(str).fillna("DUMMY_VALUE")
  X_test = convert_lines(input_df["text"], MAX_SEQUENCE_LENGTH, tokenizer)

  test_dataset = torch.utils.data.TensorDataset(torch.tensor(X_test, dtype=torch.long))
  label_binarizer = LabelBinarizer()
  label_encoder = label_binarizer.fit_transform(['clickbait', 'news', 'other'])
  with timer('Test predictions'):
      for param in model.parameters():
          param.requires_grad = False
      model.eval();
      
      test_pred_probs = np.zeros((len(X_test), 3))
      test_loader = torch.utils.data.DataLoader(test_dataset, batch_size=BATCH_SIZE, shuffle=False)
          
      for i,(x_batch,) in enumerate(tqdm_notebook(test_loader)):
          pred = model(x_batch.to(device), attention_mask=(x_batch>0).to(device), labels=None)
          test_pred_probs[i*BATCH_SIZE:(i+1)*BATCH_SIZE] = pred.detach().cpu().squeeze().numpy()
      test_preds = label_binarizer.inverse_transform(test_pred_probs)
      thisdict = {
                "Label": test_preds[0],
                "Confidence_Scores" : {
                    'clickbait' : (float(test_pred_probs[0][0]) + 10)/20,
                    'news' : (float(test_pred_probs[0][1]) + 10)/20,
                    'other' : (float(test_pred_probs[0][2]) + 10)/20            
              }
            }
      print(thisdict)
      with open('result.json', 'a') as fp:
        json.dump(thisdict, fp, indent=4)

test()