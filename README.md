# 🏙️ Smart City Complaint Analysis & Prioritization System

AI-powered web app that automatically classifies, prioritizes, and alerts on citizen complaints using ML + NLP.

---

## 📁 Project Structure

```
smart_city/
├── app.py                  # Flask backend (all routes + DB logic)
├── nlp_utils.py            # NLP: cleaning, classification, priority, duplicate detection
├── train_model.py          # Train the ML classifier (run ONCE)
├── requirements.txt        # Python dependencies
├── complaints.db           # SQLite database (auto-created)
├── data/
│   └── training_data.csv   # 70 labeled complaint samples
├── models/
│   ├── complaint_classifier.pkl  # Trained model (auto-generated)
│   └── tfidf_duplicate.pkl       # TF-IDF for duplicate detection
├── static/
│   ├── css/style.css       # All custom CSS
│   ├── js/main.js          # GPS capture + emergency alerts
│   └── uploads/            # Uploaded images
└── templates/
    ├── base.html           # Base layout (navbar, footer)
    ├── home.html           # Landing page with stats
    ├── complaint_form.html # Citizen submission form
    ├── admin_login.html    # Admin login
    ├── dashboard.html      # Admin complaint management + map
    └── analytics.html      # Charts and insights
```

---

## ⚡ Setup & Run (Windows / VS Code)

### Step 1: Install Python 3.10+
Download from https://python.org and check "Add to PATH"

### Step 2: Open terminal in VS Code
`Ctrl + ~` or Terminal → New Terminal

### Step 3: Create virtual environment
```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux
```

### Step 4: Install dependencies
```bash
pip install -r requirements.txt
```

### step 5:Download NLTK data
python -m nltk.downloader stopwords

### Step 6: Train the ML model (ONCE only)
```bash
python train_model.py
```
You'll see accuracy scores printed. Models saved in `models/` folder.

### Step 7: Run the app
```bash
python app.py
```

### Step 8: Open in browser
- **Home:** http://127.0.0.1:5000
- **Submit Complaint:** http://127.0.0.1:5000/submit
- **Admin Login:** http://127.0.0.1:5000/admin/login
  - Username: `admin`
  - Password: `admin123`

---

## 🤖 How the AI Works

1. **Text Cleaning:** Lowercase → remove punctuation → remove stopwords
2. **TF-IDF Vectorization:** Converts text to numerical feature vectors
3. **Logistic Regression Classifier:** Predicts category (7 classes)
4. **Duplicate Detection:** Cosine similarity > 0.75 = duplicate
5. **Priority Scoring:** Combines severity keywords + sentiment + duplicate status + emergency flags
6. **Emergency Detection:** Keyword matching for fire, gas leak, electric shock, etc.

---

## 🔑 Admin Credentials
- **Username:** admin  
- **Password:** admin123

---

## Database
The SQLite database (complaints.db) will be automatically created
when the application runs for the first time.
No manual setup is required.

---

## 📊 Technologies Used
| Layer | Technology |
|-------|-----------|
| Backend | Python + Flask |
| Database | SQLite |
| ML Model | TF-IDF + Logistic Regression (scikit-learn) |
| NLP | NLTK (stopwords, tokenization) |
| Frontend | Bootstrap 5 + Chart.js + Leaflet.js |
| Maps | OpenStreetMap (free, no API key) |
| GPS | Browser Geolocation API |
| Alerts | Web Audio API |
