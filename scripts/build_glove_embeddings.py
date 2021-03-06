import jellyfish as jf
import numpy as np
import io
import argparse
import pandas as pd
import nltk
import os
import numpy as np

def calculate_oov_token(embeddings, token):
	words = list(embeddings.keys())
	near = [words[0], words[1]]
	for w in words:
		if(jf.jaro_winkler(token, w) > jf.jaro_winkler(token, near[0])):
			near[0] = w
		else:
			if(jf.jaro_winkler(token, w) > jf.jaro_winkler(token, near[1])):
				near[1] = w

	word_vector = (embeddings[near[0]] + embeddings[near[1]]) / 2
	#print("Closest words to <{}> : {}, {} | Dist: {}".format(token, near[0], near[1], word_vector))
	return word_vector

def calculate_vectors(embeddings, words, name):
	data = {}
	for index, word in enumerate(words, start=1):
		try:
			data[word] = embeddings[word]
		except:
			#print("Adding to file: <{0}>".format(word))
			try:
				data[word] = calculate_oov_token(embeddings, word)
			except:
				print("Unknown Error on line: {}".format(word))

	print(len(words), len(data.keys()))
	np.save("glove_embeddings{}.npy".format(name), data)

def read_embeddings_file(args):
	print ("Reading Embeddings File")
	embeddings = dict()
	f = open(args.glove, encoding="utf8")
	for line in f:
		#print (line)
		values = line.split(' ')
		word = values[0]
		coefs = np.asarray(values[1:], dtype='float32')
		embeddings[word] = coefs
	f.close()
	return embeddings

def load_data(args):
	print("Loading Data")

	if("facebook" in args.data):	
		dataset = pd.read_csv(args.data)
		sentences = np.array(dataset["Anonymized Message"])
		data_type = 0
		name = "facebook.embs"
	elif("emo" in args.data):
		dataset = pd.read_csv(args.data, sep='\t')
		sentences = np.array(dataset["sentence"])
		data_type = 0
		name = "combination.embs"
	elif("ANET" in args.data):
		dataset = pd.read_csv(args.data, sep='\t')
		sentences = np.array(dataset["Sentence"])
		data_type = 0
		name = "anet.embs"
	elif("Warriner" in args.data):
		dataset = pd.read_csv(args.data)
		words = np.array(dataset["Word"])
		data_type = 1
		name = "warriner.embs"
	elif("nrc" in args.data):
		dataset = pd.read_csv(args.data, sep='\t')
		words = np.array(dataset['word1'])
		data_type = 1
		name = "nrc.embs"
	elif("word_combination" in args.data):
		dataset = pd.read_csv(args.data, sep='\t')
		words = np.array(dataset['Description'])
		data_type = 1
		name = "word_combination.embs"
	elif("ALL_SENTENCES" in args.data):
		dataset1 = pd.read_csv(args.face)
		dataset2 = pd.read_csv(args.emo, sep='\t')
		dataset3 = pd.read_csv(args.anet, sep='\t')
		sentences = np.array(dataset1["Anonymized Message"])
		sentences = np.append(sentences, np.array(dataset2["sentence"]))
		sentences = np.append(sentences, np.array(dataset3["Sentence"]))
		data_type = 0
		name="all_sentences.emb"


	if(data_type == 0):
		words = set()	
		for sentence in sentences:
			for word in nltk.word_tokenize(sentence):
				words.add(word)
		
	return words, name


def receive_arguments():
	parser = argparse.ArgumentParser()
	parser.add_argument("--glove", help="glove vector file", type=str, required=True)
	parser.add_argument("--data", help="data path", type=str, required=True)
	parser.add_argument("--face", help="data path1", type=str, required=False)
	parser.add_argument("--emo", help="data path2", type=str, required=False)
	parser.add_argument("--anet", help="data path3", type=str, required=False)
	args = parser.parse_args()
	return args

def main():
	args = receive_arguments()
	words, name = load_data(args)
	embeddings = read_embeddings_file(args)
	calculate_vectors(embeddings, words, name)

main()