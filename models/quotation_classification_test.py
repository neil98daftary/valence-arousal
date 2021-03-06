import numpy as np
import random as rn
import os
os.environ['PYTHONHASHSEED'] = '0'
np.random.seed(42)
rn.seed(12345)

import tensorflow as tf
session_conf = tf.ConfigProto(intra_op_parallelism_threads=1, inter_op_parallelism_threads=1)
from keras import backend as K
tf.set_random_seed(1234)
sess = tf.Session(graph=tf.get_default_graph(), config=session_conf)
K.set_session(sess)

import argparse

import pandas as pd
from scipy.stats import pearsonr
import scipy

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error
from sklearn.model_selection import KFold

import keras
from keras.models import Sequential, Model
from keras.layers import Dense, Activation, Embedding, LSTM, Flatten, Dropout, TimeDistributed, Bidirectional, InputLayer, Input, GRU, concatenate, GlobalMaxPooling1D
from keras.utils import plot_model
from keras.preprocessing import sequence
from keras import optimizers
from keras import backend as K
from keras.callbacks import EarlyStopping

import gc
import math

#from gensim.models import FastText

import nltk
from nltk.tokenize import word_tokenize


try: 
	import matplotlib.pyplot as plt
except:
	print("Failed to import matplotlib")
	
from custom_layers.GlobalMaxPooling1DMasked import *
from custom_layers.Attention import *


def load_embeddings(args):	
	if(args.fasttext):
		embeddings_dict = FastText.load_fasttext_format(args.fasttext) 
	elif(args.emb):
		embeddings_dict = np.load(args.emb).item()
	else:
		print("Error - No embeddings specified")

	return embeddings_dict, len(embeddings_dict['the'])

def get_statistics(arousals, valences):
	mean_v = np.mean(valences)
	std_v = np.std(valences)
	median_v = np.median(valences)
	#mode_v = scipy.stats.mode(valences)
	min_v = np.min(valences)
	max_v = np.max(valences)
	len_v = len(valences)

	mean_a = np.mean(arousals)
	std_a = np.std(arousals)
	median_a = np.median(arousals)
	#mode_a = scipy.stats.mode(arousals)
	min_a = np.min(arousals)
	max_a = np.max(arousals)
	len_a = len(arousals)

	print("M_V: {}\t | STD_V: {}\t | MED_V: {}\t | MIN: {}\t | MAX: {}\t | LEN: {}".format(mean_v, std_v, median_v, min_v, max_v, len_v))
	print("M_A: {}\t | STD_A: {}\t | MED_A: {}\t | MIN: {}\t | MAX: {}\t | LEN: {}".format(mean_a, std_a, median_a, min_a, max_a, len_a))

def load_data(args):
	print("[LOADING DATA]")

	#load facebook dataset	
	if("facebook" in args.data):	
		dataset = pd.read_csv(args.data)
		sentences = np.array(dataset["Anonymized Message"])
		arousals = np.array(dataset["Arousal_mean"]).reshape(-1, 1)
		valences = np.array(dataset["Valence_mean"]).reshape(-1, 1)
		get_statistics(arousals, valences)

		dataset2 = pd.read_csv(args.secondary, sep='\t')
		sentences2 = np.array(dataset2["sentence"])
		arousals2 = np.array(dataset2["Arousal"]).reshape(-1, 1)
		valences2 = np.array(dataset2["Valence"]).reshape(-1, 1)
		get_statistics(arousals2, valences2)
	else:
		dataset = pd.read_csv(args.data, sep='\t')
		sentences = np.array(dataset["sentence"])
		arousals = np.array(dataset["Arousal"]).reshape(-1, 1)
		valences = np.array(dataset["Valence"]).reshape(-1, 1)

		dataset2 = pd.read_csv(args.secondary)
		sentences2 = np.array(dataset2["Anonymized Message"])
		arousals2 = np.array(dataset2["Arousal_mean"]).reshape(-1, 1)
		valences2 = np.array(dataset2["Valence_mean"]).reshape(-1, 1)

	# ANET
	dataset3 = pd.read_csv(args.anet, sep='\t')
	sentences3 = np.array(dataset3["Sentence"])
	arousals3 = np.array(dataset3["AroMN"]).reshape(-1,1)
	valences3 = np.array(dataset3["PlMN"]).reshape(-1,1)

	get_statistics(arousals3, valences3)
	
	# Normalize To Same Range
	min_v = np.min(valences)
	max_v = np.max(valences)
	min_a = np.min(arousals)
	max_a = np.max(arousals)
	
	scalerVM = MinMaxScaler(feature_range=(min_v, max_v))
	scalerAM = MinMaxScaler(feature_range=(min_a, max_a))

	valences = scalerVM.fit_transform(valences)
	arousals = scalerAM.fit_transform(arousals)

	valences2 = scalerVM.fit_transform(valences2)
	arousals2 = scalerAM.fit_transform(arousals2)

	valences3 = scalerVM.fit_transform(valences3)
	arousals3 = scalerAM.fit_transform(arousals3)

	words = set()
	# Main
	for sentence in sentences:
		for word in nltk.word_tokenize(sentence):
			words.add(word)
	
	# Secondary
	for sentence in sentences2:
		for word in nltk.word_tokenize(sentence):
			words.add(word)

	# ANET
	for sentence in sentences3:
		for word in nltk.word_tokenize(sentence):
			words.add(word)

	# Normalization
	scalerV = MinMaxScaler(feature_range=(0, 1))
	scalerA = MinMaxScaler(feature_range=(0, 1))
	
	valences = scalerV.fit_transform(valences)
	arousals = scalerA.fit_transform(arousals)

	valences2 = scalerV.transform(valences2)
	arousals2 = scalerA.transform(arousals2)

	valences3 = scalerV.transform(valences3)
	arousals3 = scalerA.transform(arousals3)


	words_dict = {w: i for i, w in enumerate(words, start=1)}

	# Main
	tokenized_sentences = [[words_dict[word] for word in nltk.word_tokenize(sentence)] for sentence in sentences]
	vocab_size = len(words)	
	encoded_docs = sequence.pad_sequences(tokenized_sentences)

	# Secondary
	tokenized_sentences2 = [[words_dict[word] for word in nltk.word_tokenize(sentence)] for sentence in sentences2]	
	encoded_docs2 = sequence.pad_sequences(tokenized_sentences2, maxlen=len(encoded_docs[0]))

	# ANET
	tokenized_sentences3 = [[words_dict[word] for word in nltk.word_tokenize(sentence)] for sentence in sentences3]	
	encoded_docs3 = sequence.pad_sequences(tokenized_sentences3, maxlen=len(encoded_docs[0]))

	return encoded_docs, np.concatenate((valences, arousals),axis=1), vocab_size, encoded_docs.shape[1], words, scalerV, scalerA, encoded_docs2, np.concatenate((valences2, arousals2),axis=1),encoded_docs3, np.concatenate((valences3, arousals3),axis=1)

def get_word_classification(path):
	word_model = keras.models.load_model(path)
	initial_layer = word_model.get_layer("initial_layer")
	return initial_layer


def build_model(args, embeddings, emb_dim, vocab_size, max_len, words):

	if(args.wordratings):
		dense_layer = get_word_classification(args.wordratings)
	else:
		dense_layer = Dense(120, activation="relu")

	# Embedding layer
	#embeddings_matrix = np.zeros((vocab_size+1, emb_dim))
	embeddings_matrix = np.random.rand(vocab_size + 1, emb_dim)
	embeddings_matrix[0] *= 0

	for index, word in enumerate(words, start=1):
		try:
			embedding_vector = embeddings[word]
			embeddings_matrix[index] = embedding_vector
		except:
			print("Not found embedding for: <{0}>".format(word))

	input_layer = Input(shape=(max_len,))

	embedding_layer = Embedding(embeddings_matrix.shape[0], 
								embeddings_matrix.shape[1], 
								weights = [embeddings_matrix],
								mask_zero=True,
								trainable=False)(input_layer)

	layer1 = TimeDistributed(dense_layer)(embedding_layer)

	# Recurrent layer. Either LSTM or GRU
	if(args.rnn == "LSTM"):
		rnn_layer = LSTM(units=64, return_sequences=(args.attention or args.maxpooling))
	else:
		rnn_layer = GRU(units=64, return_sequences=(args.attention or args.maxpooling))

	rnn = Bidirectional(rnn_layer)(layer1)

	# Max Pooling and attention
	if(args.maxpooling and args.attention):
		max_pooling = GlobalMaxPooling1DMasked()(rnn)
		con = TimeDistributed(Dense(100))(rnn)
		attention = Attention()(con)
		connection = concatenate([max_pooling, attention])
	elif(args.maxpooling):
		max_pooling = GlobalMaxPooling1DMasked()
		connection = max_pooling(rnn)
	elif(args.attention):
		con = TimeDistributed(Dense(100))(rnn)
		attention = Attention()
		connection = attention(con)
	else:
		connection = rnn

	connection = Dropout(0.2)(connection)

	valence_output = Dense(1, activation="sigmoid", name="valence_output")(connection)
	arousal_output = Dense(1, activation="sigmoid", name="arousal_output")(connection)

	# Build Model
	model = Model(inputs=[input_layer], outputs=[valence_output, arousal_output])
	return model


def train_predict_model(model, x_train, x_test, y_valence_train, y_valence_test, y_arousal_train, y_arousal_test, scalerV, scalerA):

	earlyStopping = EarlyStopping(patience=1)

	adamOpt = keras.optimizers.Adam(lr=0.001, amsgrad=True)

	# Compilation
	model.compile(loss={"valence_output" : "mean_squared_error", "arousal_output" : "mean_squared_error"}, optimizer=adamOpt)

	print("{},{},{},{},{}".format(x_train.shape, y_valence_train.shape, y_arousal_train.shape, x_test.shape, y_valence_test.shape, y_arousal_test.shape))

	# Training
	history = model.fit( x_train, 
						{"valence_output": y_valence_train, "arousal_output": y_arousal_train}, 
						#validation_data=(x_test, {"valence_output": y_valence_test, "arousal_output": y_arousal_test}), 
						batch_size=20, 
						epochs=10,
						#callbacks = [earlyStopping]
						)
	
	# Predictions
	test_predict = model.predict(x_test)

	test_valence_predict = test_predict[0].reshape(-1,1)
	test_arousal_predict = test_predict[1].reshape(-1,1)
	y_valence_test = y_valence_test.reshape(-1, 1)
	y_arousal_test = y_arousal_test.reshape(-1, 1)

	# Remove normalization
	test_valence_predict = scalerV.inverse_transform(test_valence_predict)
	test_arousal_predict = scalerA.inverse_transform(test_arousal_predict)
	y_valence_test = scalerV.inverse_transform(y_valence_test)
	y_arousal_test = scalerA.inverse_transform(y_arousal_test)

	# Compute metrics
	valence_pearson = pearsonr(test_valence_predict, y_valence_test)[0]
	arousal_pearson = pearsonr(test_arousal_predict, y_arousal_test)[0]
	valence_mae = mean_absolute_error(test_valence_predict, y_valence_test)
	arousal_mae = mean_absolute_error(test_arousal_predict, y_arousal_test)
	valence_mse = mean_squared_error(test_valence_predict, y_valence_test)
	arousal_mse = mean_squared_error(test_arousal_predict, y_arousal_test)
	
	return valence_pearson, arousal_pearson, valence_mse, arousal_mse, valence_mae, arousal_mae

def receive_arguments():
	parser = argparse.ArgumentParser()
	parser.add_argument("--data", help="path to dataset file", type=str, required=True)
	parser.add_argument("--fasttext", help="use fasttext embeddings?", type=str, required=False)
	parser.add_argument("--emb", help="pre trained vector embedding file", type=str, required=False)
	parser.add_argument("--wordratings", help="path to word ratings model", type=str, required=False)
	parser.add_argument("--k", help="number of foldings", type=int, required=True)
	parser.add_argument("--attention", help="use attention layer", action="store_true")
	parser.add_argument("--maxpooling", help="use MaxPooling layer", action="store_true")
	parser.add_argument("--rnn", help="type of recurrent layer <LSTM>|<GRU>", type=str, required=True)
	parser.add_argument("--anet", help="path to anet file", type=str, required=True)
	parser.add_argument("--secondary", help="path to secondary dataset (facebook or combination)", type=str, required=True)

	args = parser.parse_args()
	return args

def main():
	args = receive_arguments()
	X_train, Y_train, vocab_size, max_len, words, scalerV, scalerA, X_test1, Y_test1, X_test2, Y_test2 = load_data(args)
	embeddings, emb_dim = load_embeddings(args)
	
	model = build_model(args, embeddings, emb_dim, vocab_size, max_len, words)
	
	print(train_predict_model(model, X_train, X_test1, Y_train[:,0], Y_test1[:,0], Y_train[:,1], Y_test1[:,1], scalerV, scalerA))
	print(train_predict_model(model, X_train, X_test2, Y_train[:,0], Y_test2[:,0], Y_train[:,1], Y_test2[:,1], scalerV, scalerA))

main()
