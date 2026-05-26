# app.py
import os
import re
import sqlite3
import unicodedata
from functools import wraps
from io import BytesIO
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.security import check_password_hash

# ReportLab imports for generating beautiful PDFs
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

app = Flask(__name__)
app.secret_key = 'ifpb_secure_evaluation_dashboard_secret_key'

# Middleware para gerenciar hospedagem sob subcaminho (Proxy Reverso / Traefik)
class PrefixMiddleware(object):
    def __init__(self, app_wsgi, prefix=''):
        self.app_wsgi = app_wsgi
        self.prefix = prefix

    def __call__(self, environ, start_response):
        forwarded_prefix = environ.get('HTTP_X_FORWARDED_PREFIX', '')
        prefix = forwarded_prefix or self.prefix
        if prefix:
            environ['SCRIPT_NAME'] = prefix
            path_info = environ.get('PATH_INFO', '')
            if path_info.startswith(prefix):
                environ['PATH_INFO'] = path_info[len(prefix):]
        return self.app_wsgi(environ, start_response)

app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix=os.environ.get('APPLICATION_ROOT', ''))

# Locate database.db reliably (supports env database path)
DB_PATH = os.environ.get('DATABASE_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db'))

# Inicializa o banco de dados de forma resiliente se ele não existir
if not os.path.exists(DB_PATH):
    print(f"Banco de dados nao localizado em {DB_PATH}. Inicializando...")
    try:
        db_dir = os.path.dirname(DB_PATH)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            
        import subprocess
        # Roda o script de seed passando a variavel de ambiente correspondente
        env = os.environ.copy()
        env['DATABASE_PATH'] = DB_PATH
        subprocess.run(["python", "init_db.py"], env=env, check=True)
        print("Banco de dados criado e semeado com sucesso!")
    except Exception as e:
        print(f"Erro ao inicializar banco de dados: {e}")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

# Helper to determine which academic period is selected for statistics
def get_selected_period_id(conn, req_periodo_id=None):
    if req_periodo_id:
        period = conn.execute('SELECT * FROM Periodo WHERE id = ?', (req_periodo_id,)).fetchone()
        if period:
            return period['id'], period
            
    # Fallback to active period
    active_period = conn.execute('SELECT * FROM Periodo WHERE ativo = 1 LIMIT 1').fetchone()
    if active_period:
        return active_period['id'], active_period
        
    # Fallback to latest created period
    latest_period = conn.execute('SELECT * FROM Periodo ORDER BY ano DESC, bimestre DESC LIMIT 1').fetchone()
    if latest_period:
        return latest_period['id'], latest_period
        
    return None, None

# Decorator to secure routes
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, faça login para acessar esta página.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Context Processor to inject academic periods into all layouts (especially Navbar)
@app.context_processor
def inject_periods():
    conn = get_db_connection()
    # List of all periods for the dropdown selector
    todos_periodos = conn.execute('SELECT * FROM Periodo ORDER BY ano DESC, bimestre DESC').fetchall()
    
    # Current active period
    periodo_ativo = conn.execute('SELECT * FROM Periodo WHERE ativo = 1 LIMIT 1').fetchone()
    
    # Read the period_id from the active GET query params if present
    req_periodo_id = request.args.get('periodo_id', type=int)
    
    _, selected_period = get_selected_period_id(conn, req_periodo_id)
    
    conn.close()
    
    return dict(
        todos_periodos=todos_periodos,
        periodo_ativo=periodo_ativo,
        periodo_selecionado=selected_period
    )

# PDF Generation Helper
def gerar_pdf_report(disciplina, periodo, metrics, comentarios):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=45,
        leftMargin=45,
        topMargin=45,
        bottomMargin=45
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0f172a'),
        alignment=1, # Center
        spaceAfter=12
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=11,
        textColor=colors.HexColor('#4b5563'),
        alignment=1, # Center
        spaceAfter=25
    )
    
    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=colors.HexColor('#059669'), # Emerald green
        spaceBefore=20,
        spaceAfter=10,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#1e293b')
    )
    
    comment_style = ParagraphStyle(
        'CommentText',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#334155')
    )

    story = []
    
    # Header
    story.append(Paragraph("INSTITUTO FEDERAL DA PARAÍBA — CAMPUS SOUSA", subtitle_style))
    story.append(Paragraph("RELATÓRIO CONSOLIDADO DE AVALIAÇÃO DOCENTE", title_style))
    story.append(Spacer(1, 10))
    
    # Metadata Table
    metadata_data = [
        [Paragraph("<b>Docente:</b>", body_style), Paragraph(disciplina['nome_professor'], body_style),
         Paragraph("<b>Período Letivo:</b>", body_style), Paragraph(f"{periodo['ano']}.{periodo['bimestre']}º Bimestre", body_style)],
        [Paragraph("<b>Disciplina:</b>", body_style), Paragraph(disciplina['nome_disciplina'], body_style),
         Paragraph("<b>Turma:</b>", body_style), Paragraph(disciplina['turma'], body_style)],
        [Paragraph("<b>Amostra de Respostas:</b>", body_style), Paragraph(f"{metrics['count']} avaliações submetidas", body_style),
         "", ""]
    ]
    
    metadata_table = Table(metadata_data, colWidths=[110, 160, 110, 140])
    metadata_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor('#f1f5f9')),
    ]))
    
    story.append(metadata_table)
    story.append(Spacer(1, 15))
    
    # Table Header Style
    header_style = ParagraphStyle(
        'TableHeaderText',
        parent=body_style,
        fontName='Helvetica-Bold',
        textColor=colors.white
    )

    # Scores Section
    story.append(Paragraph("DESEMPENHO QUANTITATIVO", section_heading))
    
    scores_data = [
        [Paragraph("Critério de Avaliação", header_style), Paragraph("Média Ponderada (1 a 5)", header_style), Paragraph("Classificação", header_style)]
    ]
    
    criterios = [
        ("Domínio do Conteúdo Programático", metrics['avg_conteudo']),
        ("Metodologia e Didática de Ensino", metrics['avg_didatica']),
        ("Cumprimento de Horário e Presença", metrics['avg_presenca']),
        ("Relacionamento e Diálogo com Estudantes", metrics['avg_relacionamento'])
    ]
    
    for name, score in criterios:
        if score >= 4.5:
            classification = "Excelente"
        elif score >= 3.5:
            classification = "Bom"
        elif score >= 2.5:
            classification = "Regular"
        else:
            classification = "Insuficiente"
            
        scores_data.append([
            Paragraph(name, body_style),
            Paragraph(f"<b>{score:.2f} / 5.00</b>", body_style),
            Paragraph(classification, body_style)
        ])
        
    scores_table = Table(scores_data, colWidths=[240, 140, 140])
    scores_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#059669')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('ALIGN', (1,0), (1,-1), 'CENTER'),
        ('ALIGN', (2,0), (2,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ]))
    
    story.append(scores_table)
    story.append(Spacer(1, 15))
    
    # Section: Positive Comments
    story.append(Paragraph("OPINIÕES DOS ESTUDANTES: ELOGIOS E PONTOS POSITIVOS", section_heading))
    positives = [c for c in comentarios if c['pontos_positivos']]
    
    if positives:
        pos_data = []
        for c in positives:
            pos_data.append([Paragraph(f"\" {c['pontos_positivos']} \"", comment_style)])
        pos_table = Table(pos_data, colWidths=[520])
        pos_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f0fdf4')),
            ('LINELEFT', (0,0), (-1,-1), 3, colors.HexColor('#10b981')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('BOTTOMMARGIN', (0,0), (-1,-1), 4),
        ]))
        story.append(pos_table)
    else:
        story.append(Paragraph("Nenhum feedback positivo textual registrado para este período.", body_style))
        
    story.append(Spacer(1, 15))
    
    # Section: Improvement Comments
    story.append(Paragraph("OPINIÕES DOS ESTUDANTES: SUGESTÕES DE APERFEIÇOAMENTO", ParagraphStyle('RedHeading', parent=section_heading, textColor=colors.HexColor('#dc2626'))))
    improvements = [c for c in comentarios if c['pontos_melhoria']]
    
    if improvements:
        imp_data = []
        for c in improvements:
            imp_data.append([Paragraph(f"\" {c['pontos_melhoria']} \"", comment_style)])
        imp_table = Table(imp_data, colWidths=[520])
        imp_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#fef2f2')),
            ('LINELEFT', (0,0), (-1,-1), 3, colors.HexColor('#ef4444')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('BOTTOMMARGIN', (0,0), (-1,-1), 4),
        ]))
        story.append(imp_table)
    else:
        story.append(Paragraph("Nenhuma sugestão de melhoria textual registrada para este período.", body_style))
        
    # Build Document
    doc.build(story)
    buffer.seek(0)
    return buffer

# ROTA: Login (GET/POST)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard_geral'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM Usuario WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash(f'Bem-vindo de volta, {username.capitalize()}!', 'success')
            return redirect(url_for('dashboard_geral'))
        else:
            flash('Usuário ou senha incorretos.', 'error')
            
    return render_template('login.html')

# ROTA: Logout
@app.route('/logout')
def logout():
    session.clear()
    flash('Você saiu do sistema com sucesso.', 'success')
    return redirect(url_for('login'))

# ROTA: Dashboard Geral (Protegida)
@app.route('/')
@login_required
def dashboard_geral():
    req_periodo_id = request.args.get('periodo_id', type=int)
    
    conn = get_db_connection()
    selected_id, selected_period = get_selected_period_id(conn, req_periodo_id)
    
    if not selected_id:
        stats = {
            'total_avaliacoes': 0, 'avg_conteudo': 0.0, 'avg_didatica': 0.0, 
            'avg_presenca': 0.0, 'avg_relacionamento': 0.0
        }
        return render_template('dashboard_geral.html', stats=stats, top_professors=[])
    
    total_reviews = conn.execute(
        'SELECT COUNT(*) FROM Avaliacao WHERE periodo_id = ?', 
        (selected_id,)
    ).fetchone()[0]
    
    avg_ratings = conn.execute('''
        SELECT 
            AVG(nota_conteudo) as avg_cont,
            AVG(nota_didatica) as avg_did,
            AVG(nota_presenca) as avg_pres,
            AVG(nota_relacionamento) as avg_rel
        FROM Avaliacao
        WHERE periodo_id = ?
    ''', (selected_id,)).fetchone()
    
    stats = {
        'total_avaliacoes': total_reviews,
        'avg_conteudo': avg_ratings['avg_cont'] if avg_ratings['avg_cont'] is not None else 0.0,
        'avg_didatica': avg_ratings['avg_did'] if avg_ratings['avg_did'] is not None else 0.0,
        'avg_presenca': avg_ratings['avg_pres'] if avg_ratings['avg_pres'] is not None else 0.0,
        'avg_relacionamento': avg_ratings['avg_rel'] if avg_ratings['avg_rel'] is not None else 0.0
    }
    
    top_professors = conn.execute('''
        SELECT 
            D.nome_professor,
            AVG((A.nota_conteudo + A.nota_didatica + A.nota_presenca + A.nota_relacionamento) / 4.0) as media_geral,
            COUNT(A.id) as total
        FROM Disciplina D
        JOIN Avaliacao A ON D.id = A.disciplina_id
        WHERE A.periodo_id = ?
        GROUP BY D.nome_professor
        HAVING total >= 3
        ORDER BY media_geral DESC
        LIMIT 5
    ''', (selected_id,)).fetchall()
    
    conn.close()
    
    return render_template('dashboard_geral.html', stats=stats, top_professors=top_professors)

# ROTA: Dashboard Turma Específica (Protegida)
@app.route('/turma/<nome_turma>')
@login_required
def dashboard_turma(nome_turma):
    allowed_turmas = ['1A', '2A', '3A', '1C', '2C', '3C', '1D', '2D', '3D', '1I', '2I', '3I']
    if nome_turma not in allowed_turmas:
        flash('Turma inválida ou inexistente.', 'error')
        return redirect(url_for('dashboard_geral'))
        
    disciplina_id = request.args.get('disciplina_id', type=int)
    req_periodo_id = request.args.get('periodo_id', type=int)
    
    conn = get_db_connection()
    selected_id, selected_period = get_selected_period_id(conn, req_periodo_id)
    
    disciplinas_opcoes = conn.execute('''
        SELECT id, nome_disciplina, nome_professor 
        FROM Disciplina 
        WHERE turma = ? 
        ORDER BY nome_professor, nome_disciplina
    ''', (nome_turma,)).fetchall()
    
    if not selected_id:
        metrics = {
            'avg_conteudo': 0.0, 'avg_didatica': 0.0, 'avg_presenca': 0.0, 
            'avg_relacionamento': 0.0, 'count': 0
        }
        return render_template(
            'dashboard_turma.html', turma=nome_turma, disciplinas_opcoes=disciplinas_opcoes,
            selected_disciplina_id=None, selected_disciplina=None, metrics=metrics, comentarios=[]
        )
    
    selected_disciplina = None
    professores_stats = []
    
    if disciplina_id:
        selected_disciplina = conn.execute('''
            SELECT id, nome_disciplina, nome_professor 
            FROM Disciplina 
            WHERE id = ? AND turma = ?
        ''', (disciplina_id, nome_turma)).fetchone()
        
        if selected_disciplina:
            ratings = conn.execute('''
                SELECT 
                    AVG(nota_conteudo) as avg_cont,
                    AVG(nota_didatica) as avg_did,
                    AVG(nota_presenca) as avg_pres,
                    AVG(nota_relacionamento) as avg_rel,
                    COUNT(*) as count
                FROM Avaliacao
                WHERE disciplina_id = ? AND periodo_id = ?
            ''', (disciplina_id, selected_id)).fetchone()
            
            comentarios = conn.execute('''
                SELECT 
                    A.pontos_positivos, 
                    A.pontos_melhoria, 
                    D.nome_disciplina, 
                    D.nome_professor
                FROM Avaliacao A
                JOIN Disciplina D ON A.disciplina_id = D.id
                WHERE A.disciplina_id = ? AND A.periodo_id = ?
                ORDER BY A.id DESC
            ''', (disciplina_id, selected_id)).fetchall()
        else:
            flash('Filtro de disciplina inválido para esta turma.', 'error')
            return redirect(url_for('dashboard_turma', nome_turma=nome_turma, periodo_id=selected_id))
    else:
        ratings = conn.execute('''
            SELECT 
                AVG(A.nota_conteudo) as avg_cont,
                AVG(A.nota_didatica) as avg_did,
                AVG(A.nota_presenca) as avg_pres,
                AVG(A.nota_relacionamento) as avg_rel,
                COUNT(A.id) as count
            FROM Avaliacao A
            JOIN Disciplina D ON A.disciplina_id = D.id
            WHERE D.turma = ? AND A.periodo_id = ?
        ''', (nome_turma, selected_id)).fetchone()
        
        comentarios = conn.execute('''
            SELECT 
                A.pontos_positivos, 
                A.pontos_melhoria, 
                D.nome_disciplina, 
                D.nome_professor
            FROM Avaliacao A
            JOIN Disciplina D ON A.disciplina_id = D.id
            WHERE D.turma = ? AND A.periodo_id = ?
            ORDER BY A.id DESC
        ''', (nome_turma, selected_id)).fetchall()

        # Estatísticas comparativas de todos os professores da turma no período
        professores_stats = conn.execute('''
            SELECT 
                D.nome_professor,
                D.nome_disciplina,
                AVG(A.nota_conteudo) as avg_cont,
                AVG(A.nota_didatica) as avg_did,
                AVG(A.nota_presenca) as avg_pres,
                AVG(A.nota_relacionamento) as avg_rel,
                COUNT(A.id) as total_respostas
            FROM Disciplina D
            LEFT JOIN Avaliacao A ON D.id = A.disciplina_id AND A.periodo_id = ?
            WHERE D.turma = ?
            GROUP BY D.id
            ORDER BY D.nome_professor
        ''', (selected_id, nome_turma)).fetchall()
        
    metrics = {
        'avg_conteudo': ratings['avg_cont'] if ratings['avg_cont'] is not None else 0.0,
        'avg_didatica': ratings['avg_did'] if ratings['avg_did'] is not None else 0.0,
        'avg_presenca': ratings['avg_pres'] if ratings['avg_pres'] is not None else 0.0,
        'avg_relacionamento': ratings['avg_rel'] if ratings['avg_rel'] is not None else 0.0,
        'count': ratings['count'] if ratings['count'] is not None else 0
    }
    
    frase_confirmacao = None
    frase_confirmacao_turma = None
    
    if selected_period:
        def normalizar(texto):
            nfkd = unicodedata.normalize('NFKD', texto)
            sem_acentos = "".join([c for c in nfkd if not unicodedata.combining(c)])
            return re.sub(r'[^a-zA-Z0-9\s\-\.]', '', sem_acentos).upper().strip()
            
        if selected_disciplina:
            nome_prof_norm = normalizar(selected_disciplina['nome_professor'])
            frase_confirmacao = f"EXCLUIR AVALIACOES {nome_prof_norm} EM {selected_period['ano']}.{selected_period['bimestre']}"
        else:
            frase_confirmacao_turma = f"EXCLUIR TODAS AVALIACOES DA TURMA {nome_turma} EM {selected_period['ano']}.{selected_period['bimestre']}"
            
    conn.close()
    
    return render_template(
        'dashboard_turma.html',
        turma=nome_turma,
        disciplinas_opcoes=disciplinas_opcoes,
        selected_disciplina_id=disciplina_id,
        selected_disciplina=selected_disciplina,
        metrics=metrics,
        comentarios=comentarios,
        frase_confirmacao=frase_confirmacao,
        frase_confirmacao_turma=frase_confirmacao_turma,
        professores_stats=professores_stats
    )

# ROTA PÚBLICA: Responder Questionário de Avaliação Passo a Passo por Turma (Apenas Período Ativo)
@app.route('/turma/<nome_turma>/avaliar', methods=['GET', 'POST'])
def avaliar_turma(nome_turma):
    allowed_turmas = ['1A', '2A', '3A', '1C', '2C', '3C', '1D', '2D', '3D', '1I', '2I', '3I']
    if nome_turma not in allowed_turmas:
        flash('Turma inválida ou inexistente.', 'error')
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    periodo_ativo = conn.execute('SELECT * FROM Periodo WHERE ativo = 1 LIMIT 1').fetchone()
    
    # Busca todas as disciplinas da turma ordenadas por ID de forma estável
    disciplinas = conn.execute('''
        SELECT id, nome_disciplina, nome_professor 
        FROM Disciplina 
        WHERE turma = ? 
        ORDER BY id
    ''', (nome_turma,)).fetchall()
    
    total_disciplines = len(disciplinas)
    
    if total_disciplines == 0:
        flash('Não há disciplinas cadastradas para esta turma.', 'error')
        conn.close()
        return redirect(url_for('login'))
        
    # Obtém o passo atual do aluno
    step = request.args.get('step', type=int)
    if step is None:
        # Se for o POST primário ou o início sem step, inicializa
        if request.method == 'GET':
            step = 0
            session['respostas_avaliacoes'] = {}
        else:
            step = request.form.get('step', 0, type=int)
            
    # Se o passo for 0 no GET, reinicializa o dicionário temporário da sessão
    if request.method == 'GET' and step == 0:
        session['respostas_avaliacoes'] = {}
        
    # Garante a existência do contêiner de respostas na sessão
    if 'respostas_avaliacoes' not in session:
        session['respostas_avaliacoes'] = {}
        
    if step < 0 or step >= total_disciplines:
        conn.close()
        return redirect(url_for('avaliar_turma', nome_turma=nome_turma, step=0))
        
    disciplina_atual = disciplinas[step]
    
    if request.method == 'POST':
        if not periodo_ativo:
            flash('Erro: Não há nenhum período letivo de avaliações ativo no momento. Submissão bloqueada.', 'error')
            conn.close()
            return redirect(url_for('login'))
            
        disciplina_id = request.form.get('disciplina_id', type=int)
        nota_conteudo = request.form.get('nota_conteudo', type=float)
        nota_didatica = request.form.get('nota_didatica', type=float)
        nota_presenca = request.form.get('nota_presenca', type=float)
        nota_relacionamento = request.form.get('nota_relacionamento', type=float)
        pontos_positivos = request.form.get('pontos_positivos', '').strip()
        pontos_melhoria = request.form.get('pontos_melhoria', '').strip()
        
        if not (disciplina_id and nota_conteudo and nota_didatica and nota_presenca and nota_relacionamento):
            flash('Por favor, responda a todas as avaliações de notas para prosseguir.', 'error')
            conn.close()
            return redirect(url_for('avaliar_turma', nome_turma=nome_turma, step=step))
            
        # Salva a avaliação intermediária na sessão
        respostas = session.get('respostas_avaliacoes', {})
        respostas[str(disciplina_id)] = {
            'nota_conteudo': nota_conteudo,
            'nota_didatica': nota_didatica,
            'nota_presenca': nota_presenca,
            'nota_relacionamento': nota_relacionamento,
            'pontos_positivos': pontos_positivos,
            'pontos_melhoria': pontos_melhoria
        }
        session['respostas_avaliacoes'] = respostas
        
        # Se houver mais disciplinas, avança para o próximo passo
        if step < total_disciplines - 1:
            conn.close()
            return redirect(url_for('avaliar_turma', nome_turma=nome_turma, step=step + 1))
        else:
            # Se for o último passo, grava TODAS as respostas no banco em uma única transação
            try:
                for disc_id, eval_data in session['respostas_avaliacoes'].items():
                    conn.execute('''
                        INSERT INTO Avaliacao (
                            disciplina_id, periodo_id, nota_conteudo, nota_didatica, nota_presenca, nota_relacionamento, 
                            pontos_positivos, pontos_melhoria
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (int(disc_id), periodo_ativo['id'], 
                          eval_data['nota_conteudo'], eval_data['nota_didatica'], 
                          eval_data['nota_presenca'], eval_data['nota_relacionamento'], 
                          eval_data['pontos_positivos'] if eval_data['pontos_positivos'] else None, 
                          eval_data['pontos_melhoria'] if eval_data['pontos_melhoria'] else None))
                conn.commit()
                flash(f'Parabéns! Você avaliou com sucesso todos os {total_disciplines} professores da sua turma!', 'success')
            except Exception as e:
                conn.rollback()
                flash('Erro ao registrar as avaliações no banco de dados. Por favor, tente novamente.', 'error')
                conn.close()
                return redirect(url_for('avaliar_turma', nome_turma=nome_turma, step=0))
            finally:
                conn.close()
                
            # Limpa as respostas temporárias da sessão
            session.pop('respostas_avaliacoes', None)
            return redirect(url_for('avaliar_sucesso', nome_turma=nome_turma))
            
    # GET: renderiza o passo atual
    progress_percent = int((step / total_disciplines) * 100)
    conn.close()
    
    return render_template(
        'avaliar_turma.html', 
        turma=nome_turma, 
        step=step, 
        total_disciplines=total_disciplines, 
        disciplina_atual=disciplina_atual, 
        progress_percent=progress_percent, 
        periodo_ativo=periodo_ativo
    )

# ROTA PÚBLICA: Tela de Agradecimento após Conclusão do Wizard
@app.route('/turma/<nome_turma>/avaliar/sucesso')
def avaliar_sucesso(nome_turma):
    return render_template('avaliar_sucesso.html', turma=nome_turma)

# ROTA: Gerenciar Períodos Letivos (Protegida)
@app.route('/admin/periodos', methods=['GET', 'POST'])
@login_required
def admin_periodos():
    conn = get_db_connection()
    
    if request.method == 'POST':
        ano = request.form.get('ano', type=int)
        bimestre = request.form.get('bimestre', type=int)
        
        if not (ano and bimestre):
            flash('Por favor, preencha todos os campos para cadastrar o período.', 'error')
        else:
            try:
                conn.execute('INSERT INTO Periodo (ano, bimestre, ativo) VALUES (?, ?, 0)', (ano, bimestre))
                conn.commit()
                flash(f'Período Letivo {ano}.{bimestre} cadastrado com sucesso!', 'success')
            except sqlite3.IntegrityError:
                flash(f'Erro: O Período Letivo {ano}.{bimestre} já está cadastrado.', 'error')
                
    periodos = conn.execute('SELECT * FROM Periodo ORDER BY ano DESC, bimestre DESC').fetchall()
    conn.close()
    
    return render_template('admin_periodos.html', periodos=periodos)

# ROTA: Ativar Período Letivo (Protegida - Apenas POST)
@app.route('/admin/periodo/<int:id>/ativar', methods=['POST'])
@login_required
def ativar_periodo(id):
    conn = get_db_connection()
    period = conn.execute('SELECT * FROM Periodo WHERE id = ?', (id,)).fetchone()
    
    if not period:
        flash('Erro: Período letivo não localizado.', 'error')
        conn.close()
        return redirect(url_for('admin_periodos'))
        
    try:
        conn.execute('UPDATE Periodo SET ativo = 0')
        conn.execute('UPDATE Periodo SET ativo = 1 WHERE id = ?', (id,))
        conn.commit()
        flash(f'Período Letivo {period["ano"]}.{period["bimestre"]} ativado com sucesso!', 'success')
    except Exception as e:
        flash('Erro ao tentar ativar o período letivo.', 'error')
        
    conn.close()
    return redirect(url_for('admin_periodos'))

# ROTA: Gerar Relatório PDF por Professor/Disciplina e Período (Protegida)
@app.route('/disciplina/<int:disciplina_id>/pdf')
@login_required
def gerar_pdf_disciplina(disciplina_id):
    req_periodo_id = request.args.get('periodo_id', type=int)
    
    conn = get_db_connection()
    disciplina = conn.execute('SELECT * FROM Disciplina WHERE id = ?', (disciplina_id,)).fetchone()
    
    if not disciplina:
        flash('Erro: Disciplina/Professor não localizado.', 'error')
        conn.close()
        return redirect(url_for('dashboard_geral'))
        
    selected_id, selected_period = get_selected_period_id(conn, req_periodo_id)
    
    if not selected_id:
        flash('Erro: Período letivo não localizado.', 'error')
        conn.close()
        return redirect(url_for('dashboard_geral'))
        
    # Fetch metrics
    ratings = conn.execute('''
        SELECT 
            AVG(nota_conteudo) as avg_cont,
            AVG(nota_didatica) as avg_did,
            AVG(nota_presenca) as avg_pres,
            AVG(nota_relacionamento) as avg_rel,
            COUNT(*) as count
        FROM Avaliacao
        WHERE disciplina_id = ? AND periodo_id = ?
    ''', (disciplina_id, selected_id)).fetchone()
    
    metrics = {
        'avg_conteudo': ratings['avg_cont'] if ratings['avg_cont'] is not None else 0.0,
        'avg_didatica': ratings['avg_did'] if ratings['avg_did'] is not None else 0.0,
        'avg_presenca': ratings['avg_pres'] if ratings['avg_pres'] is not None else 0.0,
        'avg_relacionamento': ratings['avg_rel'] if ratings['avg_rel'] is not None else 0.0,
        'count': ratings['count'] if ratings['count'] is not None else 0
    }
    
    # Fetch comments
    comentarios = conn.execute('''
        SELECT pontos_positivos, pontos_melhoria
        FROM Avaliacao
        WHERE disciplina_id = ? AND periodo_id = ?
        ORDER BY id DESC
    ''', (disciplina_id, selected_id)).fetchall()
    
    conn.close()
    
    # Generate the beautiful PDF buffer
    pdf_buffer = gerar_pdf_report(disciplina, selected_period, metrics, comentarios)
    
    # Normalize filename: professor-disciplina-ano-bimestre.pdf
    def sanitize_filename(name):
        nfkd = unicodedata.normalize('NFKD', name)
        name_without_accents = "".join([c for c in nfkd if not unicodedata.combining(c)])
        # Remove special chars and spaces
        cleaned = re.sub(r'[^a-zA-Z0-9_\-]', '_', name_without_accents)
        return re.sub(r'_+', '_', cleaned).strip('_')
        
    prof_clean = sanitize_filename(disciplina['nome_professor'])
    disc_clean = sanitize_filename(disciplina['nome_disciplina'])
    
    filename = f"{prof_clean}-{disc_clean}-{selected_period['ano']}-{selected_period['bimestre']}.pdf"
    
    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )

# ROTA: Excluir com segurança todas as avaliações de um período para uma determinada disciplina (Protegida - Apenas POST)
@app.route('/disciplina/<int:disciplina_id>/periodo/<int:periodo_id>/excluir', methods=['POST'])
@login_required
def excluir_avaliacoes_disciplina(disciplina_id, periodo_id):
    conn = get_db_connection()
    disciplina = conn.execute('SELECT * FROM Disciplina WHERE id = ?', (disciplina_id,)).fetchone()
    periodo = conn.execute('SELECT * FROM Periodo WHERE id = ?', (periodo_id,)).fetchone()
    
    if not disciplina or not periodo:
        flash('Erro: Disciplina ou Período letivo não localizado.', 'error')
        conn.close()
        return redirect(url_for('dashboard_geral'))
        
    confirmacao_usuario = request.form.get('frase_confirmacao', '').strip()
    
    def normalizar(texto):
        nfkd = unicodedata.normalize('NFKD', texto)
        sem_acentos = "".join([c for c in nfkd if not unicodedata.combining(c)])
        return re.sub(r'[^a-zA-Z0-9\s\-\.]', '', sem_acentos).upper().strip()
        
    nome_prof_norm = normalizar(disciplina['nome_professor'])
    frase_esperada = f"EXCLUIR AVALIACOES {nome_prof_norm} EM {periodo['ano']}.{periodo['bimestre']}"
    
    if normalizar(confirmacao_usuario) != normalizar(frase_esperada):
        flash('Erro: A frase de confirmação não confere. Nenhuma avaliação foi excluída.', 'error')
        conn.close()
        return redirect(url_for('dashboard_turma', nome_turma=disciplina['turma'], disciplina_id=disciplina_id, periodo_id=periodo_id))
        
    try:
        cur = conn.execute('DELETE FROM Avaliacao WHERE disciplina_id = ? AND periodo_id = ?', (disciplina_id, periodo_id))
        count_excluidas = cur.rowcount
        conn.commit()
        flash(f'Sucesso! Todas as {count_excluidas} avaliações do professor {disciplina["nome_professor"]} para o período {periodo["ano"]}.{periodo["bimestre"]} foram excluídas definitivamente.', 'success')
    except Exception as e:
        conn.rollback()
        flash('Erro ao tentar excluir as avaliações do banco de dados.', 'error')
    finally:
        conn.close()
        
    return redirect(url_for('dashboard_turma', nome_turma=disciplina['turma'], periodo_id=periodo_id))

# ROTA: Excluir com segurança todas as avaliações de um período para uma determinada turma inteira (Protegida - Apenas POST)
@app.route('/turma/<nome_turma>/periodo/<int:periodo_id>/excluir', methods=['POST'])
@login_required
def excluir_avaliacoes_turma(nome_turma, periodo_id):
    allowed_turmas = ['1A', '2A', '3A', '1C', '2C', '3C', '1D', '2D', '3D', '1I', '2I', '3I']
    if nome_turma not in allowed_turmas:
        flash('Erro: Turma inválida.', 'error')
        return redirect(url_for('dashboard_geral'))
        
    conn = get_db_connection()
    periodo = conn.execute('SELECT * FROM Periodo WHERE id = ?', (periodo_id,)).fetchone()
    
    if not periodo:
        flash('Erro: Período letivo não localizado.', 'error')
        conn.close()
        return redirect(url_for('dashboard_geral'))
        
    confirmacao_usuario = request.form.get('frase_confirmacao_turma', '').strip()
    
    def normalizar(texto):
        nfkd = unicodedata.normalize('NFKD', texto)
        sem_acentos = "".join([c for c in nfkd if not unicodedata.combining(c)])
        return re.sub(r'[^a-zA-Z0-9\s\-\.]', '', sem_acentos).upper().strip()
        
    frase_esperada = f"EXCLUIR TODAS AVALIACOES DA TURMA {nome_turma} EM {periodo['ano']}.{periodo['bimestre']}"
    
    if normalizar(confirmacao_usuario) != normalizar(frase_esperada):
        flash('Erro: A frase de confirmação não confere. Nenhuma avaliação foi excluída.', 'error')
        conn.close()
        return redirect(url_for('dashboard_turma', nome_turma=nome_turma, periodo_id=periodo_id))
        
    try:
        cur = conn.execute('''
            DELETE FROM Avaliacao 
            WHERE periodo_id = ? 
              AND disciplina_id IN (SELECT id FROM Disciplina WHERE turma = ?)
        ''', (periodo_id, nome_turma))
        count_excluidas = cur.rowcount
        conn.commit()
        flash(f'Sucesso! Todas as {count_excluidas} avaliações da turma {nome_turma} para o período {periodo["ano"]}.{periodo["bimestre"]} foram excluídas definitivamente.', 'success')
    except Exception as e:
        conn.rollback()
        flash('Erro ao tentar excluir as avaliações da turma.', 'error')
    finally:
        conn.close()
        
    return redirect(url_for('dashboard_turma', nome_turma=nome_turma, periodo_id=periodo_id))

# ROTA: Excluir com segurança todas as avaliações de um período letivo de todas as turmas (Protegida - Apenas POST)
@app.route('/admin/periodo/<int:periodo_id>/limpar', methods=['POST'])
@login_required
def limpar_periodo(periodo_id):
    conn = get_db_connection()
    periodo = conn.execute('SELECT * FROM Periodo WHERE id = ?', (periodo_id,)).fetchone()
    
    if not periodo:
        flash('Erro: Período letivo não localizado.', 'error')
        conn.close()
        return redirect(url_for('admin_periodos'))
        
    confirmacao_usuario = request.form.get('frase_confirmacao_periodo', '').strip()
    
    def normalizar(texto):
        nfkd = unicodedata.normalize('NFKD', texto)
        sem_acentos = "".join([c for c in nfkd if not unicodedata.combining(c)])
        return re.sub(r'[^a-zA-Z0-9\s\-\.]', '', sem_acentos).upper().strip()
        
    frase_esperada = f"LIMPAR TODAS AVALIACOES DO PERIODO {periodo['ano']}.{periodo['bimestre']}"
    
    if normalizar(confirmacao_usuario) != normalizar(frase_esperada):
        flash('Erro: A frase de confirmação não confere. Nenhuma avaliação foi excluída.', 'error')
        conn.close()
        return redirect(url_for('admin_periodos'))
        
    try:
        cur = conn.execute('DELETE FROM Avaliacao WHERE periodo_id = ?', (periodo_id,))
        count_excluidas = cur.rowcount
        conn.commit()
        flash(f'Sucesso! Todas as {count_excluidas} avaliações do período {periodo["ano"]}.{periodo["bimestre"]} foram excluídas definitivamente.', 'success')
    except Exception as e:
        conn.rollback()
        flash('Erro ao tentar excluir as avaliações do período.', 'error')
    finally:
        conn.close()
        
    return redirect(url_for('admin_periodos'))

# ROTA: Baixar arquivo do banco de dados SQLite (Protegida)
@app.route('/admin/backup/download')
@login_required
def download_backup():
    try:
        if not os.path.exists(DB_PATH):
            flash('Erro: Banco de dados não localizado.', 'error')
            return redirect(url_for('admin_periodos'))
            
        return send_file(
            DB_PATH,
            mimetype='application/x-sqlite3',
            as_attachment=True,
            download_name='database_backup.db'
        )
    except Exception as e:
        flash(f'Erro ao tentar exportar o banco de dados: {e}', 'error')
        return redirect(url_for('admin_periodos'))

# ROTA: Fazer upload e substituir a base de dados SQLite (Protegida)
@app.route('/admin/backup/upload', methods=['POST'])
@login_required
def upload_backup():
    if 'backup_file' not in request.files:
        flash('Nenhum arquivo enviado.', 'error')
        return redirect(url_for('admin_periodos'))
        
    file = request.files['backup_file']
    
    if file.filename == '':
        flash('Nenhum arquivo selecionado.', 'error')
        return redirect(url_for('admin_periodos'))
        
    if file:
        temp_path = DB_PATH + '.temp'
        try:
            # Salva o arquivo temporário
            file.save(temp_path)
            
            # Valida se é um banco de dados SQLite válido abrindo uma conexão de teste
            test_conn = sqlite3.connect(temp_path)
            test_conn.execute("SELECT count(*) FROM Usuario")
            test_conn.execute("SELECT count(*) FROM Disciplina")
            test_conn.execute("SELECT count(*) FROM Periodo")
            test_conn.execute("SELECT count(*) FROM Avaliacao")
            test_conn.close()
            
            # Substitui o banco atual com segurança
            if os.path.exists(DB_PATH):
                emergency_backup = DB_PATH + '.bak'
                if os.path.exists(emergency_backup):
                    os.remove(emergency_backup)
                os.rename(DB_PATH, emergency_backup)
                
            os.rename(temp_path, DB_PATH)
            
            # Se havia backup de emergência, remove agora que deu tudo certo
            emergency_backup = DB_PATH + '.bak'
            if os.path.exists(emergency_backup):
                os.remove(emergency_backup)
                
            flash('Sucesso! O banco de dados foi restaurado e substituído com êxito.', 'success')
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            emergency_backup = DB_PATH + '.bak'
            if os.path.exists(emergency_backup) and not os.path.exists(DB_PATH):
                os.rename(emergency_backup, DB_PATH)
            elif os.path.exists(emergency_backup):
                os.remove(emergency_backup)
                
            flash(f'Erro: O arquivo enviado não é um banco de dados de avaliação válido. ({e})', 'error')
            
    return redirect(url_for('admin_periodos'))

if __name__ == '__main__':
    # Run the application locally or read from env for Docker
    host = os.environ.get('FLASK_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    app.run(debug=debug, host=host, port=port)
