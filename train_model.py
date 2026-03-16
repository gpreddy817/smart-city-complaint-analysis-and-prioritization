"""
train_model.py - Train the complaint category classifier
Run this ONCE before starting the Flask app: python train_model.py
"""

import os
import pickle
import pandas as pd
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

try:
    import nltk
    from nltk.corpus import stopwords
    from nltk.tokenize import word_tokenize
    nltk.download('stopwords', quiet=True)
    nltk.download('punkt', quiet=True)
    nltk.download('punkt_tab', quiet=True)
    STOP_WORDS = set(stopwords.words('english'))
    def _tokenize(t): return word_tokenize(t)
except Exception:
    STOP_WORDS = set(['i','me','my','we','our','you','your','he','his','she','her',
                      'they','it','the','a','an','and','but','or','in','on','at','to',
                      'for','of','is','are','was','be','been','have','do','not','no'])
    def _tokenize(t): return re.findall(r'\b[a-z]+\b', t)

def clean_text(text):
    """Clean and preprocess complaint text"""
    text = text.lower()
    text = re.sub(r'[^a-z\s]', '', text)  # remove punctuation/numbers
    tokens = _tokenize(text)
    tokens = [t for t in tokens if t not in STOP_WORDS and len(t) > 2]
    return ' '.join(tokens)

def train():
    print("Loading training data...")
    df = pd.read_csv('data/training_data.csv')
    df['clean_text'] = df['text'].apply(clean_text)

    X_train, X_test, y_train, y_test = train_test_split(
        df['clean_text'], df['category'], test_size=0.2, random_state=42
    )

    # Pipeline: TF-IDF + Logistic Regression
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(ngram_range=(1, 2), max_features=5000)),
        ('clf', LogisticRegression(max_iter=1000, C=1.0))
    ])

    print("Training model...")
    pipeline.fit(X_train, y_train)

    print("\nEvaluation on test set:")
    preds = pipeline.predict(X_test)
    print(classification_report(y_test, preds))

    os.makedirs('models', exist_ok=True)
    with open('models/complaint_classifier.pkl', 'wb') as f:
        pickle.dump(pipeline, f)

    # Also save a standalone TF-IDF for duplicate detection
    tfidf_dup = TfidfVectorizer(ngram_range=(1, 2), max_features=5000)
    tfidf_dup.fit(df['clean_text'])
    with open('models/tfidf_duplicate.pkl', 'wb') as f:
        pickle.dump(tfidf_dup, f)

    print("\nModel saved to models/complaint_classifier.pkl")
    print("Duplicate TF-IDF saved to models/tfidf_duplicate.pkl")

if __name__ == '__main__':
    train()
