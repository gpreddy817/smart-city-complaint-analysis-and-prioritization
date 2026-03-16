"""
nlp_utils.py - All NLP processing: cleaning, categorization, sentiment, priority, duplicates
"""

import re
import pickle
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# Try to use NLTK; fall back to basic stopwords if unavailable
try:
    import nltk
    from nltk.corpus import stopwords
    from nltk.tokenize import word_tokenize
    nltk.download('stopwords', quiet=True)
    nltk.download('punkt', quiet=True)
    nltk.download('punkt_tab', quiet=True)
    STOP_WORDS = set(stopwords.words('english'))
    NLTK_AVAILABLE = True
except Exception:
    NLTK_AVAILABLE = False
    STOP_WORDS = set([
        'i','me','my','myself','we','our','ours','ourselves','you','your','yours','yourself',
        'he','him','his','himself','she','her','hers','they','them','their','it','its',
        'what','which','who','whom','this','that','these','those','am','is','are','was',
        'were','be','been','being','have','has','had','do','does','did','will','would',
        'could','should','may','might','shall','can','need','dare','ought','used',
        'a','an','the','and','but','if','or','because','as','until','while','of','at',
        'by','for','with','about','against','between','into','through','to','from',
        'up','down','in','out','on','off','then','so','no','nor','not','only','same',
        'very','just','too','also','than','other','each','more','most','such','both'
    ])

def _tokenize(text):
    """Simple whitespace tokenizer as NLTK fallback"""
    if NLTK_AVAILABLE:
        return word_tokenize(text)
    return re.findall(r'\b[a-z]+\b', text)

# ─── Keyword Lists ────────────────────────────────────────────────────────────

EMERGENCY_KEYWORDS = [
    'fire', 'electric shock', 'live wire', 'collapsed road', 'flooding',
    'accident', 'gas leak', 'electrocution', 'explosion', 'collapse',
    'flood', 'burning', 'blaze', 'unconscious', 'injured', 'dead body',
    'open manhole', 'wire fallen'
]

SEVERITY_KEYWORDS = [
    'danger', 'dangerous', 'accident', 'broken wire', 'flooding', 'gas leak',
    'open manhole', 'electric shock', 'fire', 'urgent', 'emergency',
    'hazard', 'collapsed', 'blocked', 'severe', 'critical', 'serious'
]

NEGATIVE_WORDS = [
    'terrible', 'horrible', 'worst', 'bad', 'awful', 'pathetic',
    'disgusting', 'unacceptable', 'dangerous', 'urgent', 'broken',
    'damaged', 'no', 'not', 'never', 'failed', 'failure', 'problem',
    'issue', 'complaint', 'poor', 'waste', 'dirty', 'filthy', 'illegal'
]

# ─── Text Cleaning ────────────────────────────────────────────────────────────

def clean_text(text):
    """Lowercase, remove punctuation, remove stopwords"""
    text = text.lower()
    text = re.sub(r'[^a-z\s]', '', text)
    tokens = _tokenize(text)
    tokens = [t for t in tokens if t not in STOP_WORDS and len(t) > 2]
    return ' '.join(tokens)

def extract_keywords(text):
    """Extract meaningful keywords from complaint text"""
    cleaned = clean_text(text)
    return cleaned.split()[:10]  # top 10 keywords

# ─── Sentiment Analysis ───────────────────────────────────────────────────────

def analyze_sentiment(text):
    """Simple lexicon-based sentiment: returns 'Negative' or 'Positive'"""
    text_lower = text.lower()
    neg_count = sum(1 for w in NEGATIVE_WORDS if w in text_lower)
    # Most complaints are inherently negative; threshold at 1
    return 'Negative' if neg_count >= 1 else 'Positive'

# ─── Category Prediction ──────────────────────────────────────────────────────

def load_classifier():
    try:
        with open('models/complaint_classifier.pkl', 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        return None

def predict_category(text, classifier=None):
    """Predict complaint category using trained model"""
    if classifier is None:
        classifier = load_classifier()
    if classifier is None:
        return 'Other'
    cleaned = clean_text(text)
    return classifier.predict([cleaned])[0]

# ─── Emergency Detection ──────────────────────────────────────────────────────

def is_emergency(text):
    """Check if complaint contains emergency keywords"""
    text_lower = text.lower()
    for kw in EMERGENCY_KEYWORDS:
        if kw in text_lower:
            return True
    return False

# ─── Priority Scoring ─────────────────────────────────────────────────────────

def calculate_priority(text, is_dup=False, dup_count=0, is_emerg=False, complaint_age_hours=0):
    """
    Priority score 0-100:
    - Emergency keywords: +40
    - Severity keywords: +5 each (max 20)
    - Negative sentiment: +10
    - Duplicate (already reported): +15
    - Age (older unresolved): up to +15
    Returns: score (int), label (HIGH/MEDIUM/LOW)
    """
    score = 0
    text_lower = text.lower()

    if is_emerg:
        score += 40

    sev_hits = sum(1 for kw in SEVERITY_KEYWORDS if kw in text_lower)
    score += min(sev_hits * 5, 20)

    sentiment = analyze_sentiment(text)
    if sentiment == 'Negative':
        score += 10

    if is_dup:
        score += 15

    # Age bonus: +1 per 6 hours unresolved, max 15
    age_bonus = min(int(complaint_age_hours / 6), 15)
    score += age_bonus

    score = min(score, 100)

    if score >= 50 or is_emerg:
        label = 'HIGH'
    elif score >= 15:
        label = 'MEDIUM'
    else:
        label = 'LOW'

    return score, label

# ─── Duplicate Detection ──────────────────────────────────────────────────────

def load_tfidf_dup():
    try:
        with open('models/tfidf_duplicate.pkl', 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        return None

def check_duplicate(new_text, existing_complaints, tfidf=None, threshold=0.75):
    """
    Compare new complaint with all existing ones using cosine similarity.
    Returns: (is_duplicate: bool, original_id: int or None, similarity: float)
    """
    if not existing_complaints:
        return False, None, 0.0

    if tfidf is None:
        tfidf = load_tfidf_dup()
    if tfidf is None:
        return False, None, 0.0

    new_clean = clean_text(new_text)
    existing_texts = [clean_text(c['complaint_text']) for c in existing_complaints]

    try:
        all_texts = existing_texts + [new_clean]
        tfidf_matrix = tfidf.transform(all_texts)
        new_vec = tfidf_matrix[-1]
        existing_matrix = tfidf_matrix[:-1]
        similarities = cosine_similarity(new_vec, existing_matrix)[0]

        max_idx = int(np.argmax(similarities))
        max_sim = float(similarities[max_idx])

        if max_sim >= threshold:
            return True, existing_complaints[max_idx]['id'], max_sim
    except Exception:
        pass

    return False, None, 0.0
