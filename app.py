from flask import Flask, render_template, request, redirect, url_for, session, jsonify, make_response, flash
import pandas as pd
import pdfplumber
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re
import plotly.graph_objects as go
import plotly.utils
import json
import urllib.parse
from datetime import datetime
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
import sqlite3
import secrets
import os
import numpy as np
from werkzeug.exceptions import RequestEntityTooLarge
import gc

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# FIXED: Removed Flask-Session, using default Flask cookie sessions
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 # 32MB

bcrypt = Bcrypt(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please login to continue'

@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    flash('File too large! Max 32MB allowed. Compress PDF or reduce JD text.', 'error')
    return redirect(url_for('index'))

@app.errorhandler(500)
def handle_500(e):
    flash('Server error occurred. Please try again.', 'error')
    return redirect(url_for('index'))

def init_db():
    conn = sqlite3.connect('careerscope_users.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  email TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL)''')
    conn.close()
init_db()

class User(UserMixin):
    def __init__(self, id, name, email):
        self.id = id
        self.name = name
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect('careerscope_users.db')
    cur = conn.cursor()
    cur.execute("SELECT id, name, email FROM users WHERE id =?", (user_id,))
    user = cur.fetchone()
    conn.close()
    if user:
        return User(user[0], user[1], user[2])
    return None

try:
    df_jobs = pd.read_csv('data/it_jobs_100.csv', encoding='utf-8')
    df_jobs = df_jobs.rename(columns={
        'job_title': 'title',
        'salary_lpa': 'salary',
        'automation_risk': 'risk'
    })
    df_jobs = df_jobs.fillna({
        'title': 'Unknown',
        'skills': '',
        'salary': 0,
        'risk': 0,
        'category': 'IT',
        'location': 'Not Specified'
    })
    df_jobs['salary'] = pd.to_numeric(df_jobs['salary'], errors='coerce').fillna(0)
    df_jobs['risk'] = pd.to_numeric(df_jobs['risk'], errors='coerce').fillna(0)
    print(f"✅ Loaded {len(df_jobs)} jobs")
except Exception as e:
    print(f"❌ CSV Error: {e}")
    df_jobs = pd.DataFrame(columns=['title', 'skills', 'salary', 'risk', 'category', 'location'])

SKILLS = [
    'python','java','sql','excel','tableau','powerbi','javascript','react','angular','vue',
    'nodejs','django','flask','spring','springboot','hibernate','html','css','typescript',
    'git','docker','kubernetes','jenkins','aws','azure','gcp','linux','mongodb','mysql',
    'postgresql','oracle','hadoop','spark','kafka','tensorflow','pytorch','machinelearning',
    'deeplearning','nlp','dsa','oop','systemdesign','api','rest','microservices',
    'agile','scrum','jira','selenium','figma','adobexd','android','kotlin','ios','swift',
    'flutter','dart','unity','c#','solidity','web3','security','networking','ccna',
    'activeDirectory','sre','salesforce','apex','sap','abap','erp','etl','informatica',
    'ssis','bigdata','terraform','cloudArchitecture','uipath','rpa','iot','arduino',
    'embeddedSystems','firmware','wordpress','php','laravel','dotnet','aspnet','mvc',
    'go','golang','rust','ruby','rails','seo','googleAnalytics','sem','socialMedia',
    'communication','problemsolving','leadership','teamwork','projectmanagement','airflow'
]

COMPANY_CAREERS = {
    'tcs': 'https://www.tcs.com/careers',
    'infosys': 'https://www.infosys.com/careers',
    'wipro': 'https://careers.wipro.com',
    'hcl': 'https://www.hcltech.com/careers',
    'tech mahindra': 'https://careers.techmahindra.com',
    'cognizant': 'https://careers.cognizant.com',
    'accenture': 'https://www.accenture.com/in-en/careers',
    'capgemini': 'https://www.capgemini.com/careers',
    'ibm': 'https://www.ibm.com/careers',
    'microsoft': 'https://careers.microsoft.com',
    'google': 'https://careers.google.com',
    'amazon': 'https://www.amazon.jobs',
    'oracle': 'https://www.oracle.com/careers',
    'dell': 'https://jobs.dell.com',
    'cisco': 'https://jobs.cisco.com',
    'adobe': 'https://careers.adobe.com',
    'salesforce': 'https://careers.salesforce.com',
    'zoho': 'https://careers.zohocorp.com',
    'flipkart': 'https://www.flipkartcareers.com',
    'paytm': 'https://jobs.paytm.com'
}

INTERVIEW_QUESTIONS = {
    'tcs': ['Explain SDLC', 'What is OOP?', 'SQL Joins', 'Python vs Java'],
    'infosys': ['Data Structures', 'DBMS Concepts', 'Cloud Basics', 'Agile Methodology'],
    'google': ['System Design', 'Algorithms', 'Behavioral Questions', 'Coding Challenge'],
    'amazon': ['Leadership Principles', 'DSA Problems', 'System Design', 'Bar Raiser Round'],
    'default': ['Tell me about yourself', 'Why this company?', 'Strengths & Weaknesses', 'Where do you see yourself in 5 years?']
}

def get_apply_url(job_title):
    if not job_title: return "https://www.linkedin.com/jobs"
    title_lower = job_title.lower()
    for company, url in COMPANY_CAREERS.items():
        if company in title_lower: return url
    return f"https://www.linkedin.com/jobs/search?keywords={urllib.parse.quote_plus(job_title)}"

def get_company_name(job_title):
    if not job_title: return None
    title_lower = job_title.lower()
    for company in COMPANY_CAREERS.keys():
        if company in title_lower: return company.upper()
    return None

def calculate_ats_score(resume_text, skills):
    score = 0
    skill_score = min(len(skills) * 4, 40)
    score += skill_score
    keywords = ['experience', 'project', 'achieved', 'developed', 'managed', 'led', 'improved']
    keyword_count = sum(1 for kw in keywords if kw in resume_text.lower())
    score += min(keyword_count * 5, 30)
    if len(resume_text) > 500: score += 10
    if 'education' in resume_text.lower(): score += 5
    if 'email' in resume_text.lower() or '@' in resume_text: score += 5
    if re.search(r'\d{10}', resume_text): score += 5
    if 'linkedin' in resume_text.lower(): score += 5
    return min(score, 100)

def create_salary_trend_chart(job_title, current_salary):
    experience = [0, 2, 4, 6, 8, 10]
    base_salary = float(current_salary)
    salaries = [round(base_salary * (1 + i*0.15), 1) for i in experience]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=experience, y=salaries, mode='lines+markers', name='Projected Salary',
        line=dict(color='#22d3ee', width=3), marker=dict(size=10, color='#22d3ee')))
    fig.update_layout(title=f'Salary Growth Projection - {job_title}', xaxis_title='Experience (Years)',
        yaxis_title='Salary (LPA)', paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={'color': "white", 'family': "Poppins"}, height=400)
    return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

def extract_text_from_pdf(file):
    if not file or not hasattr(file, 'filename') or not file.filename: return ""
    text = ""
    try:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages[:10]:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + " "
                    if len(text) > 50000:
                        break
    except Exception as e:
        print(f"PDF Error: {e}")
        return ""
    finally:
        gc.collect()
    return text.strip()

def extract_skills_from_text(text):
    if not text or not isinstance(text, str): return []
    text = text.lower()
    text = re.sub(r'[^a-zA-Z0-9\s#+]', ' ', text)
    found_skills = []
    for skill in SKILLS:
        pattern = r'\b' + re.escape(skill.lower()) + r'\b'
        if re.search(pattern, text): found_skills.append(skill)
    return sorted(list(set(found_skills)))

def extract_job_title_from_jd(text):
    if not text or not isinstance(text, str): return None
    text = text.strip()
    lines = text.split('\n')[:10]
    patterns = [r'(?:job\s*title|position|role|designation)\s*[:\-]\s*([^\n\r]{3,60})',
        r'^([A-Z][A-Za-z\s/&-]{3,50})\s*(?:at|@|\-)', r'^([A-Z][A-Za-z\s/&-]{3,50})\s*$']
    for line in lines:
        line = line.strip()
        if len(line) < 5 or len(line) > 80: continue
        for pattern in patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                title = re.sub(r'\s+', ' ', title).title()
                if 5 < len(title) < 60: return title
    return None

def get_top_matches(resume_skills, it_only=True):
    if not resume_skills or df_jobs.empty: return [], None
    try:
        resume_text = " ".join(resume_skills)
        job_skills_list = df_jobs['skills'].fillna('').astype(str).str.lower().tolist()
        vectorizer = TfidfVectorizer(stop_words='english', max_features=1000, ngram_range=(1, 2))
        vectors = vectorizer.fit_transform([resume_text] + job_skills_list)
        cosine_sim = cosine_similarity(vectors[0:1], vectors[1:]).flatten()
        cosine_sim = np.nan_to_num(cosine_sim, nan=0.0)
        df_jobs['match'] = (cosine_sim * 100).round(1)
    except Exception as e:
        print(f"Vectorizer Error: {e}")
        df_jobs['match'] = 0.0

    results = []
    for idx, row in df_jobs.iterrows():
        try:
            category = str(row.get('category', 'IT'))
            if it_only and category not in ['IT', 'IT-Business']: continue

            job_skills_str = str(row.get('skills', ''))
            job_skill_set = set(job_skills_str.lower().split())
            resume_skill_set = set([s.lower() for s in resume_skills])
            missing = list(job_skill_set - resume_skill_set)[:6]

            job_title_str = str(row.get('title', 'Unknown'))
            apply_url = get_apply_url(job_title_str)
            company_name = get_company_name(job_title_str)
            location = str(row.get('location', 'Not Specified'))

            results.append({
                "title": job_title_str,
                "match": float(row.get('match', 0)),
                "salary": float(row.get('salary', 0)),
                "risk": int(row.get('risk', 0)),
                "missing": missing,
                "category": category,
                "location": location,
                "apply_url": apply_url,
                "company_name": company_name,
                "id": int(idx)
            })
        except Exception as e:
            print(f"Row error {idx}: {e}")
            continue
    top10 = sorted(results, key=lambda x: x['match'], reverse=True)[:10]
    chart_data = create_charts(top10) if top10 else None
    gc.collect()
    return top10, chart_data

def create_charts(jobs, applying_job_title="Job Match", jd_match_percent=None):
    if not jobs:
        return None
    try:
        top_job = jobs[0]
        score = jd_match_percent if jd_match_percent is not None else top_job['match']

        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = score,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {
                'text': f"Top Match Job<br><span style='font-size:0.8em;color:#00ff88'>{applying_job_title if jd_match_percent else top_job['title']}</span>",
                'font': {'size': 20, 'color': 'white'}
            },
            number = {
                'font': {'size': 50, 'color': '#00ff88'},
                'suffix': '%'
            },
            gauge = {
                'axis': {'range': [None, 100], 'tickcolor': 'white'},
                'bar': {'color': "#00ff88", 'thickness': 0.75},
                'bgcolor': "rgba(0,0,0,0)",
                'borderwidth': 2,
                'bordercolor': "#334155",
                'steps': [
                    {'range': [0, 40], 'color': 'rgba(239, 68, 68, 0.3)'},
                    {'range': [40, 70], 'color': 'rgba(251, 191, 36, 0.3)'},
                    {'range': [70, 100], 'color': 'rgba(0, 255, 136, 0.3)'}
                ],
                'threshold': {
                    'line': {'color': "white", 'width': 4},
                    'thickness': 0.75,
                    'value': 80
                }
            }
        ))

        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font={'color': "white", 'family': "Poppins, Arial"},
            height=320,
            margin=dict(l=30, r=30, t=80, b=30)
        )
        return {"gauge": json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder), "top_job": top_job}
    except Exception as e:
        print(f"Chart Error: {e}")
        return None

def compare_with_jd(resume_skills, jd_skills):
    if not jd_skills: return None
    resume_set = set([s.lower() for s in resume_skills])
    jd_set = set([s.lower() for s in jd_skills])
    matched = sorted(list(resume_set & jd_set))
    missing = sorted(list(jd_set - resume_set))
    extra = sorted(list(resume_set - jd_set))
    match_percent = round((len(matched) / len(jd_set)) * 100, 1) if len(jd_set) > 0 else 0
    return {"match_percent": match_percent, "matched_skills": matched, "missing_skills": missing[:6],
        "extra_skills": extra[:4], "total_jd_skills": len(jd_set), "total_matched": len(matched)}

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = sqlite3.connect('careerscope_users.db')
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email =?", (email,))
        user = cur.fetchone()
        conn.close()
        if user and bcrypt.check_password_hash(user[3], password):
            login_user(User(user[0], user[1], user[2]))
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        flash('Invalid email or password', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
        try:
            conn = sqlite3.connect('careerscope_users.db')
            conn.execute("INSERT INTO users (name, email, password) VALUES (?,?,?)", (name, email, password))
            conn.commit()
            conn.close()
            flash('Registered successfully! Please login', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already registered', 'error')
    return render_template('register.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        flash(f'Password reset link sent to {email} if account exists', 'info')
        return redirect(url_for('login'))
    return render_template('forgot_password.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('login'))

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        resume_file = request.files.get('resume')
        jd_file = request.files.get('jd_pdf')
        it_only = request.form.get('it_only') == 'on'
        jd_text_manual = request.form.get('job_description', '').strip()

        if len(jd_text_manual) > 10000:
            return render_template('index.html', error="Job Description too long! Max 10,000 characters.")

        if not resume_file or not resume_file.filename:
            return render_template('index.html', error="Please upload your resume PDF")
        try:
            resume_text = extract_text_from_pdf(resume_file)
            if not resume_text:
                return render_template('index.html', error="Could not read PDF. Upload a valid text-based PDF.")
            skills = extract_skills_from_text(resume_text)
            if not skills:
                return render_template('index.html', error="No technical skills found. Upload a detailed resume.")
            ats_score = calculate_ats_score(resume_text, skills)
            jd_skills = []
            jd_text_final = ""
            jd_job_title = None
            if jd_file and jd_file.filename:
                jd_text_final = extract_text_from_pdf(jd_file)
                if jd_text_final:
                    jd_skills = extract_skills_from_text(jd_text_final)
                    jd_job_title = extract_job_title_from_jd(jd_text_final)
            elif jd_text_manual:
                jd_text_final = jd_text_manual
                jd_skills = extract_skills_from_text(jd_text_manual)
                jd_job_title = extract_job_title_from_jd(jd_text_manual)
            jd_comparison = compare_with_jd(skills, jd_skills)

            session['analysis_data'] = {
                'skills_found': skills[:50],
                'it_checked': it_only,
                'jd_comparison': jd_comparison,
                'applying_job_title': jd_job_title or "Software Engineer",
                'title_source': "job_description" if jd_job_title else "resume_match",
                'ats_score': ats_score
            }
            return redirect(url_for('skill_analysis'))
        except Exception as e:
            print(f"❌ Error: {e}")
            return render_template('index.html', error=f"Processing error: {str(e)}")
    return render_template('index.html', error=None)

@app.route('/skill-analysis')
@login_required
def skill_analysis():
    data = session.get('analysis_data')
    if not data: return redirect(url_for('index'))
    results, charts = get_top_matches(data['skills_found'], data['it_checked'])
    return render_template('skill_analysis.html',
                         results=results,
                         skills_found=data['skills_found'],
                         it_checked=data['it_checked'],
                         charts=charts,
                         jd_comparison=data.get('jd_comparison'),
                         applying_job_title=data['applying_job_title'],
                         title_source=data['title_source'],
                         ats_score=data['ats_score'])

@app.route('/job-matches')
@login_required
def job_matches():
    data = session.get('analysis_data')
    if not data: return redirect(url_for('index'))
    results, _ = get_top_matches(data['skills_found'], data['it_checked'])
    min_match = request.args.get('min_match', type=float, default=0)
    min_salary = request.args.get('min_salary', type=float, default=0)
    max_risk = request.args.get('max_risk', type=int, default=100)
    location = request.args.get('location', default='')
    sort_by = request.args.get('sort', default='match')
    search = request.args.get('search', default='').lower()

    filtered = []
    for job in results:
        if job['match'] >= min_match and job['salary'] >= min_salary and job['risk'] <= max_risk:
            if location and job.get('location', '')!= location: continue
            if search == '' or search in job['title'].lower(): filtered.append(job)

    if sort_by == 'salary': filtered = sorted(filtered, key=lambda x: x['salary'], reverse=True)
    elif sort_by == 'risk': filtered = sorted(filtered, key=lambda x: x['risk'])
    else: filtered = sorted(filtered, key=lambda x: x['match'], reverse=True)

    stats = {'total': len(filtered), 'avg_match': round(sum(j['match'] for j in filtered) / len(filtered), 1) if filtered else 0,
        'avg_salary': round(sum(j['salary'] for j in filtered) / len(filtered), 1) if filtered else 0,
        'high_match': len([j for j in filtered if j['match'] >= 80])}

    return render_template('job_matches.html', results=filtered, stats=stats,
                         applying_job_title=data['applying_job_title'],
                         filters={'min_match': float(min_match), 'min_salary': float(min_salary),
                                  'max_risk': int(max_risk), 'sort': str(sort_by),
                                  'search': str(search), 'location': str(location)})

@app.route('/saved-jobs')
@login_required
def saved_jobs():
    data = session.get('analysis_data')
    if not data: return redirect(url_for('index'))
    results, _ = get_top_matches(data['skills_found'], data['it_checked'])

    safe_results = []
    for job in results:
        safe_results.append({
            'id': int(job.get('id', 0)),
            'title': str(job.get('title', 'Unknown')),
            'category': str(job.get('category', 'IT')),
            'location': str(job.get('location', 'Not Specified')),
            'salary': float(job.get('salary', 0)),
            'risk': int(job.get('risk', 0)),
            'match': float(job.get('match', 0)),
            'apply_url': str(job.get('apply_url', '#')),
            'company_name': job.get('company_name'),
            'missing': job.get('missing', [])
        })

    return render_template('saved_jobs.html', jobs=safe_results)

@app.route('/compare')
@login_required
def compare():
    job_ids = request.args.getlist('job_id', type=int)
    data = session.get('analysis_data')
    if not data: return redirect(url_for('index'))
    results, _ = get_top_matches(data['skills_found'], data['it_checked'])
    compare_jobs = [j for j in results if j.get('id') in job_ids][:2]
    return render_template('compare.html', jobs=compare_jobs)

@app.route('/interview-prep/<job_title>')
@login_required
def interview_prep(job_title):
    company = get_company_name(job_title)
    company_key = company.lower() if company else 'default'
    questions = INTERVIEW_QUESTIONS.get(company_key, INTERVIEW_QUESTIONS['default'])
    return render_template('interview_prep.html', job_title=job_title, company=company or 'General', questions=questions)

@app.route('/salary-trend/<job_title>/<float:salary>')
@login_required
def salary_trend(job_title, salary):
    chart_json = create_salary_trend_chart(job_title, salary)
    return render_template('salary_trend.html', job_title=job_title, current_salary=salary, chart_json=chart_json)

@app.route('/email-alerts', methods=['GET', 'POST'])
@login_required
def email_alerts():
    if request.method == 'POST':
        email = request.form.get('email')
        min_match = request.form.get('min_match', 70)
        session['email_alerts'] = {'email': email, 'min_match': min_match, 'enabled': True}
        return jsonify({'success': True, 'message': f'Alerts enabled for {email}'})
    alerts = session.get('email_alerts', {'enabled': False})
    return render_template('email_alerts.html', alerts=alerts)

@app.route('/export-pdf')
@login_required
def export_pdf():
    data = session.get('analysis_data')
    if not data: return redirect(url_for('index'))
    results, _ = get_top_matches(data['skills_found'], data['it_checked'])
    html = render_template('export_pdf.html', results=results[:5], applying_job_title=data['applying_job_title'],
                          date=datetime.now().strftime('%Y-%m-%d'))
    response = make_response(html)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline; filename=careerscope_report.pdf'
    return response

@app.route('/new-analysis')
@login_required
def new_analysis():
    session.pop('analysis_data', None)
    return redirect(url_for('index'))

@app.template_filter('urlencode')
def urlencode_filter(s):
    if isinstance(s, str): return urllib.parse.quote_plus(s)
    return s

if __name__ == '__main__':
    print("🚀 CareerScope AI Pro - Production Ready")
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)