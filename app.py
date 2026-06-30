from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import PyPDF2
import json
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import plotly.graph_objs as go
import plotly
from datetime import datetime
import re
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///careerscope.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

RESUME_TEMPLATES = {
    'modern': {'name': 'Modern Professional', 'color': '#3b82f6', 'desc': 'Clean & ATS friendly'},
    'classic': {'name': 'Classic Formal', 'color': '#1e293b', 'desc': 'Traditional business'},
    'creative': {'name': 'Creative Bold', 'color': '#8b5cf6', 'desc': 'Stand out design'},
    'minimal': {'name': 'Minimal Simple', 'color': '#10b981', 'desc': 'Simple & effective'},
    'executive': {'name': 'Executive Elite', 'color': '#f59e0b', 'desc': 'Premium executive'},
}

COVER_LETTER_TEMPLATES = {
    'modern': {'name': 'Modern Professional', 'color': '#3b82f6', 'desc': 'Clean & ATS friendly'},
    'classic': {'name': 'Classic Formal', 'color': '#1e293b', 'desc': 'Traditional business'},
    'creative': {'name': 'Creative Bold', 'color': '#8b5cf6', 'desc': 'Stand out design'},
    'minimal': {'name': 'Minimal Simple', 'color': '#10b981', 'desc': 'Simple & effective'},
}

SKILL_ROADMAPS = {
    'Python': {
        'title': 'Python Developer Roadmap',
        'stages': [
            {'name': 'Basics', 'topics': ['Syntax', 'Variables', 'Data Types', 'Operators', 'Control Flow']},
            {'name': 'Intermediate', 'topics': ['Functions', 'OOP', 'File Handling', 'Error Handling', 'Modules']},
            {'name': 'Advanced', 'topics': ['Decorators', 'Generators', 'Context Managers', 'Async/Await', 'Metaclasses']},
            {'name': 'Frameworks', 'topics': ['Django', 'Flask', 'FastAPI', 'Pyramid']},
            {'name': 'Tools', 'topics': ['Git', 'Docker', 'Testing', 'CI/CD', 'Package Management']}
        ],
        'youtube': 'https://www.youtube.com/results?search_query=Python+tutorial+roadmap'
    },
    'REST API': {
        'title': 'REST API Developer Roadmap',
        'stages': [
            {'name': 'Basics', 'topics': ['HTTP Methods', 'Status Codes', 'JSON', 'Headers', 'URL Structure']},
            {'name': 'Design', 'topics': ['REST Principles', 'Resource Naming', 'CRUD Operations', 'Versioning']},
            {'name': 'Security', 'topics': ['Authentication', 'OAuth2', 'JWT', 'API Keys', 'CORS']},
            {'name': 'Advanced', 'topics': ['Pagination', 'Filtering', 'Rate Limiting', 'Caching', 'Webhooks']},
            {'name': 'Tools', 'topics': ['Postman', 'Swagger', 'Insomnia', 'API Testing', 'Documentation']}
        ],
        'youtube': 'https://www.youtube.com/results?search_query=REST+API+tutorial+roadmap'
    },
    'JavaScript': {
        'title': 'JavaScript Developer Roadmap',
        'stages': [
            {'name': 'Basics', 'topics': ['Syntax', 'Variables', 'Data Types', 'Functions', 'Arrays', 'Objects']},
            {'name': 'DOM', 'topics': ['Selectors', 'Events', 'Manipulation', 'AJAX', 'Fetch API']},
            {'name': 'ES6+', 'topics': ['Arrow Functions', 'Destructuring', 'Promises', 'Async/Await', 'Modules']},
            {'name': 'Frameworks', 'topics': ['React', 'Vue', 'Angular', 'Node.js', 'Express']},
            {'name': 'Tools', 'topics': ['npm', 'Webpack', 'Babel', 'Testing', 'TypeScript']}
        ],
        'youtube': 'https://www.youtube.com/results?search_query=JavaScript+tutorial+roadmap'
    },
    'React': {
        'title': 'React Developer Roadmap',
        'stages': [
            {'name': 'Basics', 'topics': ['JSX', 'Components', 'Props', 'State', 'Events']},
            {'name': 'Hooks', 'topics': ['useState', 'useEffect', 'useContext', 'useReducer', 'Custom Hooks']},
            {'name': 'Routing', 'topics': ['React Router', 'Navigation', 'Protected Routes', 'Dynamic Routes']},
            {'name': 'State Management', 'topics': ['Context API', 'Redux', 'Zustand', 'Recoil']},
            {'name': 'Advanced', 'topics': ['Performance', 'Testing', 'Next.js', 'TypeScript']}
        ],
        'youtube': 'https://www.youtube.com/results?search_query=React+tutorial+roadmap'
    },
    'Docker': {
        'title': 'Docker DevOps Roadmap',
        'stages': [
            {'name': 'Basics', 'topics': ['Containers', 'Images', 'Dockerfile', 'Docker Hub']},
            {'name': 'Commands', 'topics': ['docker run', 'docker build', 'docker ps', 'docker exec']},
            {'name': 'Compose', 'topics': ['docker-compose.yml', 'Multi-container', 'Networks', 'Volumes']},
            {'name': 'Advanced', 'topics': ['Docker Swarm', 'Kubernetes', 'CI/CD', 'Security']},
            {'name': 'Production', 'topics': ['Best Practices', 'Monitoring', 'Logging', 'Scaling']}
        ],
        'youtube': 'https://www.youtube.com/results?search_query=Docker+tutorial+roadmap'
    },
    'AWS': {
        'title': 'AWS Cloud Roadmap',
        'stages': [
            {'name': 'Basics', 'topics': ['IAM', 'EC2', 'S3', 'VPC', 'CloudWatch']},
            {'name': 'Compute', 'topics': ['Lambda', 'ECS', 'EKS', 'Auto Scaling']},
            {'name': 'Database', 'topics': ['RDS', 'DynamoDB', 'ElastiCache', 'Redshift']},
            {'name': 'Networking', 'topics': ['Route 53', 'CloudFront', 'API Gateway', 'Load Balancer']},
            {'name': 'DevOps', 'topics': ['CodePipeline', 'CodeBuild', 'CloudFormation', 'Terraform']}
        ],
        'youtube': 'https://www.youtube.com/results?search_query=AWS+tutorial+roadmap'
    }
}

def extract_pdf_text(file):
    try:
        pdf_reader = PyPDF2.PdfReader(file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        return ""

def extract_skills_from_text(text):
    skill_keywords = [
        'Python', 'Java', 'JavaScript', 'React', 'Node.js', 'Django', 'Flask',
        'HTML', 'CSS', 'SQL', 'MongoDB', 'PostgreSQL', 'Git', 'Docker', 'AWS',
        'Machine Learning', 'Data Science', 'AI', 'TensorFlow', 'PyTorch',
        'REST API', 'GraphQL', 'TypeScript', 'Vue', 'Angular', 'Express',
        'Kubernetes', 'CI/CD', 'Linux', 'Agile', 'Scrum', 'DevOps'
    ]
    found_skills = []
    text_lower = text.lower()
    for skill in skill_keywords:
        if skill.lower() in text_lower:
            found_skills.append(skill)
    return list(set(found_skills))

def analyze_job_description(jd_text):
    skills = extract_skills_from_text(jd_text)
    lines = jd_text.split('\n')
    job_title = "Software Developer"
    for line in lines[:5]:
        if any(word in line.lower() for word in ['developer', 'engineer', 'analyst', 'manager', 'api']):
            job_title = line.strip()
            break
    return job_title, skills

def calculate_ats_score(resume_text, target_skills):
    resume_skills = extract_skills_from_text(resume_text)
    matched = len(set(resume_skills) & set(target_skills))
    total = len(target_skills) if target_skills else 1
    score = int((matched / total) * 100)
    return max(min(score, 100), 30)

def generate_resume_content(resume_text, target_job, target_skills, template='modern'):
    lines = resume_text.split('\n')
    name = "Your Name"
    email = "email@example.com"
    phone = "+91 XXXXX XXXXX"
    linkedin = ""
    github = ""
    location = "Yanam, Andhra Pradesh, India"

    for line in lines[:15]:
        line = line.strip()
        if '@' in line and '.' in line:
            email = line
        elif any(char.isdigit() for char in line) and len(line) > 8:
            phone = line
        elif 'linkedin.com' in line.lower():
            linkedin = line
        elif 'github.com' in line.lower():
            github = line
        elif len(line.split()) <= 4 and line and not any(char.isdigit() for char in line) and '@' not in line:
            name = line

    skills = extract_skills_from_text(resume_text)
    summary = f"Results-driven {target_job} with expertise in {', '.join(skills[:3])}. Passionate about building scalable solutions and delivering high-quality code."

    experience = [{
        'title': target_job,
        'company': 'Tech Solutions Inc.',
        'duration': 'Jan 2022 - Present',
        'points': [
            'Developed and maintained scalable web applications using modern frameworks',
            'Collaborated with cross-functional teams to deliver features on time',
            'Improved application performance by 40% through code optimization'
        ]
    }]

    education = [{
        'degree': 'B.Tech in Computer Science',
        'university': 'ABC University',
        'year': '2018 - 2022',
        'cgpa': '8.5'
    }]

    projects = [{
        'name': 'E-Commerce Platform',
        'tech': 'React, Node.js, MongoDB',
        'link': '',
        'points': [
            'Built full-stack e-commerce application with payment integration',
            'Implemented user authentication and product management system'
        ]
    }]

    return {
        'template': template, 'name': name, 'email': email, 'phone': phone,
        'linkedin': linkedin, 'github': github, 'location': location, 'summary': summary,
        'skills': skills, 'experience': experience, 'education': education, 'projects': projects,
        'certifications': [], 'languages': [{'name': 'English', 'level': 'Fluent'}, {'name': 'Telugu', 'level': 'Native'}],
        'hobbies': 'Reading, Cricket, Coding'
    }

def generate_cover_letter(resume_text, target_job, company_name, template):
    lines = resume_text.split('\n')
    name = "Your Name"
    email = "email@example.com"
    phone = "+91 XXXXX XXXXX"

    for line in lines[:10]:
        if '@' in line and '.' in line:
            email = line.strip()
        elif any(char.isdigit() for char in line) and len(line) > 8:
            phone = line.strip()
        elif len(line.split()) <= 4 and line.strip() and not any(char.isdigit() for char in line):
            name = line.strip()

    body = f"""
    <p><strong>{name}</strong><br>
    {email} | {phone}</p>

    <p>{datetime.now().strftime('%B %d, %Y')}</p>

    <p>Hiring Manager<br>
    {company_name}</p>

    <p>Dear Hiring Manager,</p>

    <p>I am writing to express my strong interest in the <strong>{target_job}</strong> position at {company_name}. With my background in software development and proven track record of delivering high-quality solutions, I am confident that I would be a valuable addition to your team.</p>

    <p>Throughout my career, I have developed expertise in modern technologies and demonstrated the ability to solve complex problems efficiently. My experience aligns well with the requirements of this role, and I am excited about the opportunity to contribute to {company_name}'s continued success.</p>

    <p>Key highlights of my qualifications include:</p>
    <ul>
        <li>Strong technical foundation with hands-on experience in relevant technologies</li>
        <li>Proven ability to collaborate effectively with cross-functional teams</li>
        <li>Commitment to writing clean, maintainable code and following best practices</li>
        <li>Passion for continuous learning and staying updated with industry trends</li>
    </ul>

    <p>I am particularly drawn to {company_name} because of its reputation for innovation and excellence. I would welcome the opportunity to discuss how my skills and enthusiasm can contribute to your team's goals.</p>

    <p>Thank you for considering my application. I look forward to the possibility of discussing this opportunity with you.</p>

    <p>Sincerely,<br>
    {name}</p>
    """

    return {'name': name, 'email': email, 'phone': phone, 'company_name': company_name, 'body': body, 'template': template}

def generate_resume_pdf(content):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch, leftMargin=0.5*inch, rightMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor('#1e293b'), spaceAfter=6)
    heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#3b82f6'), spaceAfter=6, spaceBefore=12)

    story.append(Paragraph(content['name'], title_style))
    contact_info = f"{content['email']} | {content['phone']}"
    if content['linkedin']:
        contact_info += f" | {content['linkedin']}"
    story.append(Paragraph(contact_info, styles['Normal']))
    story.append(Spacer(1, 0.2*inch))

    story.append(Paragraph('PROFESSIONAL SUMMARY', heading_style))
    story.append(Paragraph(content['summary'], styles['Normal']))
    story.append(Spacer(1, 0.15*inch))

    story.append(Paragraph('TECHNICAL SKILLS', heading_style))
    story.append(Paragraph(' • '.join(content['skills']), styles['Normal']))
    story.append(Spacer(1, 0.15*inch))

    story.append(Paragraph('PROFESSIONAL EXPERIENCE', heading_style))
    for exp in content['experience']:
        story.append(Paragraph(f"<b>{exp['title']}</b> - {exp['company']}", styles['Normal']))
        story.append(Paragraph(f"<i>{exp['duration']}</i>", styles['Normal']))
        for point in exp['points']:
            story.append(Paragraph(f"• {point}", styles['Normal']))
        story.append(Spacer(1, 0.1*inch))

    story.append(Paragraph('EDUCATION', heading_style))
    for edu in content['education']:
        story.append(Paragraph(f"<b>{edu['degree']}</b>", styles['Normal']))
        story.append(Paragraph(f"{edu['university']} | {edu['year']} | CGPA: {edu['cgpa']}", styles['Normal']))
        story.append(Spacer(1, 0.1*inch))

    if content['projects']:
        story.append(Paragraph('KEY PROJECTS', heading_style))
        for proj in content['projects']:
            story.append(Paragraph(f"<b>{proj['name']}</b>", styles['Normal']))
            story.append(Paragraph(f"<i>{proj['tech']}</i>", styles['Normal']))
            for point in proj['points']:
                story.append(Paragraph(f"• {point}", styles['Normal']))
            story.append(Spacer(1, 0.1*inch))

    doc.build(story)
    buffer.seek(0)
    return buffer

def get_skill_roadmap(skill_name):
    if skill_name in SKILL_ROADMAPS:
        return SKILL_ROADMAPS[skill_name]
    return {
        'title': f'{skill_name} Learning Roadmap',
        'stages': [
            {'name': 'Beginner', 'topics': ['Introduction', 'Basic Concepts', 'Setup', 'First Project']},
            {'name': 'Intermediate', 'topics': ['Core Features', 'Best Practices', 'Common Patterns']},
            {'name': 'Advanced', 'topics': ['Advanced Topics', 'Optimization', 'Real-world Projects']},
            {'name': 'Expert', 'topics': ['Architecture', 'Scaling', 'Production', 'Contributing']}
        ],
        'youtube': f'https://www.youtube.com/results?search_query={skill_name}+tutorial+roadmap'
    }

@app.errorhandler(413)
def request_entity_too_large(error):
    flash('File too large! Please upload PDF under 16MB', 'danger')
    return redirect(url_for('skill_analysis')), 413

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email_or_username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter((User.username == email_or_username) | (User.email == email_or_username)).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
        elif User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
        else:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/skill_analysis', methods=['GET', 'POST'])
@login_required
def skill_analysis():
    if request.method == 'POST':
        resume_file = request.files.get('resume_file')
        jd_file = request.files.get('jd_file')
        jd_text = request.form.get('job_description', '')
        if not resume_file:
            flash('Please upload a resume', 'danger')
            return redirect(url_for('skill_analysis'))
        resume_text = extract_pdf_text(resume_file)
        if not resume_text:
            flash('Could not extract text from resume', 'danger')
            return redirect(url_for('skill_analysis'))
        if jd_file:
            jd_text = extract_pdf_text(jd_file)
        if not jd_text:
            flash('Please provide a job description', 'danger')
            return redirect(url_for('skill_analysis'))
        job_title, target_skills = analyze_job_description(jd_text)
        skills_found = extract_skills_from_text(resume_text)
        matched_skills = list(set(skills_found) & set(target_skills))
        missing_skills = list(set(target_skills) - set(skills_found))
        bonus_skills = list(set(skills_found) - set(target_skills))
        match_percent = int((len(matched_skills) / len(target_skills) * 100)) if target_skills else 0
        ats_score = calculate_ats_score(resume_text, target_skills)
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=match_percent,
            title={'text': "Match Score"},
            gauge={'axis': {'range': [None, 100]},
                   'bar': {'color': "#22d3ee"},
                   'steps': [{'range': [0, 50], 'color': "#ef4444"},
                            {'range': [50, 80], 'color': "#f59e0b"},
                            {'range': [80, 100], 'color': "#10b981"}]}
        ))
        fig.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20))
        charts = {'gauge': json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)}
        session['resume_text'] = resume_text
        session['target_job'] = job_title
        session['target_skills'] = target_skills
        session['analysis_results'] = {
            'job_title': job_title,
            'skills_found': skills_found,
            'matched_skills': matched_skills,
            'missing_skills': missing_skills,
            'bonus_skills': bonus_skills,
            'match_percent': match_percent,
            'ats_resume_score': ats_score,
            'charts': charts,
            'top_match_job': {'title': job_title, 'match_score': match_percent, 'salary': '$80k - $120k'}
        }
        return render_template('skill_analysis.html',
                             show_results=True,
                             job_title=job_title,
                             skills_found=skills_found,
                             matched_skills=matched_skills,
                             missing_skills=missing_skills,
                             bonus_skills=bonus_skills,
                             match_percent=match_percent,
                             ats_resume_score=ats_score,
                             charts=charts,
                             show_resume_builder=ats_score < 80,
                             top_match_job={'title': job_title, 'match_score': match_percent, 'salary': '$80k - $120k'})
    if 'analysis_results' in session:
        results = session['analysis_results']
        return render_template('skill_analysis.html',
                             show_results=True,
                             job_title=results['job_title'],
                             skills_found=results['skills_found'],
                             matched_skills=results['matched_skills'],
                             missing_skills=results['missing_skills'],
                             bonus_skills=results['bonus_skills'],
                             match_percent=results['match_percent'],
                             ats_resume_score=results['ats_resume_score'],
                             charts=results['charts'],
                             show_resume_builder=results['ats_resume_score'] < 80,
                             top_match_job=results['top_match_job'])
    return render_template('skill_analysis.html', show_results=False)

@app.route('/clear_analysis')
@login_required
def clear_analysis():
    session.pop('analysis_results', None)
    session.pop('resume_text', None)
    session.pop('target_job', None)
    session.pop('target_skills', None)
    flash('Analysis cleared! Upload new files.', 'info')
    return redirect(url_for('skill_analysis'))

@app.route('/resume_builder', methods=['GET', 'POST'])
@login_required
def resume_builder():
    resume_text = session.get('resume_text', '')
    target_job = session.get('target_job', 'Software Developer')
    target_skills = session.get('target_skills', [])
    if not resume_text:
        flash('Please analyze your resume first', 'warning')
        return redirect(url_for('skill_analysis'))
    if request.method == 'POST':
        content = {
            'template': request.form.get('template', 'modern'),
            'name': request.form.get('name'),
            'email': request.form.get('email'),
            'phone': request.form.get('phone'),
            'linkedin': request.form.get('linkedin'),
            'github': request.form.get('github', ''),
            'portfolio': request.form.get('portfolio', ''),
            'location': request.form.get('location', ''),
            'summary': request.form.get('summary'),
            'skills': request.form.getlist('skills'),
            'experience': json.loads(request.form.get('experience_json', '[]')),
            'education': json.loads(request.form.get('education_json', '[]')),
            'projects': json.loads(request.form.get('projects_json', '[]')),
            'certifications': json.loads(request.form.get('certifications_json', '[]')),
            'languages': json.loads(request.form.get('languages_json', '[]')),
            'hobbies': request.form.get('hobbies', '')
        }
        pdf_buffer = generate_resume_pdf(content)
        return send_file(pdf_buffer, as_attachment=True, download_name=f'Resume_{target_job.replace(" ", "_")}.pdf', mimetype='application/pdf')
    mode = request.args.get('mode', 'preview')
    selected_template = request.args.get('template', 'modern')
    resume_content = generate_resume_content(resume_text, target_job, target_skills, selected_template)
    return render_template('resume_builder.html',
                         content=resume_content,
                         templates=RESUME_TEMPLATES,
                         target_job=target_job,
                         mode=mode,
                         selected_template=selected_template)

@app.route('/cover_letter', methods=['GET', 'POST'])
@login_required
def cover_letter():
    resume_text = session.get('resume_text', '')
    target_job = session.get('target_job', 'Software Developer')
    if not resume_text:
        flash('Please analyze your resume first', 'warning')
        return redirect(url_for('skill_analysis'))
    mode = request.args.get('mode', 'preview')
    selected_template = request.args.get('template', 'modern')
    company_name = request.form.get('company_name', 'Your Company') if request.method == 'POST' else 'Your Company'
    cover_content = generate_cover_letter(resume_text, target_job, company_name, selected_template)
    if request.method == 'POST':
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75*inch, bottomMargin=0.75*inch, leftMargin=0.75*inch, rightMargin=0.75*inch)
        styles = getSampleStyleSheet()
        story = []
        body_text = request.form.get('body', cover_content['body'])
        import re
        clean_text = re.sub('<[^<]+?>', '', body_text)
        paragraphs = clean_text.split('\n\n')
        for para in paragraphs:
            if para.strip():
                story.append(Paragraph(para.strip(), styles['Normal']))
                story.append(Spacer(1, 0.2*inch))
        doc.build(story)
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f'Cover_Letter_{target_job.replace(" ", "_")}.pdf', mimetype='application/pdf')
    return render_template('cover_letter.html',
                         content=cover_content,
                         templates=COVER_LETTER_TEMPLATES,
                         target_job=target_job,
                         mode=mode,
                         selected_template=selected_template)

@app.route('/skill_roadmap/<skill_name>')
@login_required
def skill_roadmap(skill_name):
    roadmap = get_skill_roadmap(skill_name)
    return render_template('skill_roadmap.html', skill=skill_name, roadmap=roadmap)

@app.route('/job_matches')
@login_required
def job_matches():
    analysis_data = session.get('analysis_results', {})

    if not analysis_data:
        target_job = 'Software Developer'
        target_skills = ['Python', 'JavaScript', 'React', 'SQL', 'Node.js']
        skills_found = ['Python', 'HTML', 'CSS']
        missing_skills = ['JavaScript', 'React', 'SQL', 'Node.js']
    else:
        target_job = analysis_data.get('job_title', 'Software Developer')
        target_skills = session.get('target_skills', ['Python', 'JavaScript'])
        skills_found = analysis_data.get('skills_found', ['Python'])
        missing_skills = analysis_data.get('missing_skills', [])

    location = "India"
    experience_level = "2"
    job_list = []

    # High match jobs - based on skills you have
    for idx, skill in enumerate(skills_found[:3], 1):
        keywords = f"{skill.replace(' ', '%20')}%20Developer"
        linkedin_url = f"https://www.linkedin.com/jobs/search/?keywords={keywords}&location={location}&f_E={experience_level}&f_TP=1&sortBy=R"
        skill_missing_for_job = list(set(target_skills) - set([skill, 'Git', 'Problem Solving']))
        job_list.append({
            'id': idx,
            'title': f'{skill} Developer',
            'company': 'Top MNCs & Startups',
            'location': f'{location} / Remote',
            'match_score': max(95 - (idx * 5), 70),
            'salary': '₹5L - ₹18L PA',
            'skills_required': [skill, 'Git', 'Problem Solving'],
            'missing_skills': skill_missing_for_job[:3],
            'posted': 'Past 24 hours',
            'linkedin_url': linkedin_url,
            'description': f'Hiring {skill} developers. Click to see all active openings on LinkedIn.'
        })

    # Low match jobs - based on skills you DON'T have
    for idx, skill in enumerate(missing_skills[:3], 4):
        keywords = f"{skill.replace(' ', '%20')}%20Developer"
        linkedin_url = f"https://www.linkedin.com/jobs/search/?keywords={keywords}&location={location}&f_E={experience_level}&f_TP=1&sortBy=R"
        job_list.append({
            'id': idx,
            'title': f'{skill} Developer',
            'company': 'Learning Opportunity',
            'location': f'{location} / Remote',
            'match_score': max(60 - (idx * 5), 40),
            'salary': '₹4L - ₹15L PA',
            'skills_required': [skill] + skills_found[:2],
            'missing_skills': [skill],
            'posted': 'Past 24 hours',
            'linkedin_url': linkedin_url,
            'description': f'Learn {skill} to qualify. Click skill to see roadmap.'
        })

    # General job
    general_keywords = target_job.replace(' ', '%20')
    general_url = f"https://www.linkedin.com/jobs/search/?keywords={general_keywords}&location={location}&f_TP=1&sortBy=R"
    job_list.append({
        'id': 99,
        'title': f'{target_job} - All Openings',
        'company': 'Multiple Companies',
        'location': f'{location} / Remote',
        'match_score': analysis_data.get('match_percent', 75),
        'salary': '₹6L - ₹25L PA',
        'skills_required': target_skills[:4],
        'missing_skills': missing_skills[:3],
        'posted': 'Recent',
        'linkedin_url': general_url,
        'description': f'All {target_job} positions matching your profile.'
    })

    return render_template('job_matches.html', jobs=job_list, target_job=target_job, has_analysis=bool(analysis_data))

# ==================== MAIN - ADDED THIS BLOCK ====================
@app.route('/saved_jobs')
@login_required
def saved_jobs():
    return render_template('saved_jobs.html', jobs=[])

@app.route('/export_pdf', methods=['POST'])
@login_required
def export_pdf():
    resume_text = session.get('resume_text', '')
    target_job = session.get('target_job', 'Software Developer')
    target_skills = session.get('target_skills', [])
    content = generate_resume_content(resume_text, target_job, target_skills, 'modern')
    pdf_buffer = generate_resume_pdf(content)
    return send_file(pdf_buffer, as_attachment=True, download_name=f'Resume_{target_job.replace(" ", "_")}.pdf', mimetype='application/pdf')
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='127.0.0.1', port=5000)