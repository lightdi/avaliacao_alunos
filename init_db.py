# init_db.py
import sqlite3
import random
from werkzeug.security import generate_password_hash

# CSV data provided in the request
CSV_DATA = """Turma,Disciplina,Professor
1A,Língua Portuguesa,Elanny
1A,Sociologia,SAULO
1A,História,Gutiele
1A,Biologia,ELIANE
1A,Física,DAVID
1A,Informática Básica,RACKYNELLY
1A,Química,CARLOS
1A,Matemática,Paulo Cezar
1A,Inglês,JONATHAN
1A,Sist. Agrossilvipast,SELMA
1A,Int. Agroecologia,MARIO
1A,Filosofia,Ijaelson
1A,Artes,LADY JANE
1A,Ed. Física,GERTRUDES
1A,Solos Agríc.,EDNALDO
1A,Int. A Agropecuária,SERGIO
1A,Aquicultura,SERGIO
1A,Desenho/Topog.,GILTON
1A,Forragicultura,TATIANA
1A,Geografia,Anúzia
2A,Sociologia,SAULO
2A,I.M.C.,PATRICIA
2A,Mecanização Agric.,EDUARDO
2A,Avicultura,SERGIO
2A,Inglês,JONATHAN
2A,Olericultura,GILTON
2A,Suinocultura,DAVI
2A,Agricultura Familiar,HUGO
2A,Culturas Anuais,Paulo Wanderley
2A,Física,GEIMSON
2A,Matemática,Paulo Cezar
2A,História,Gutiele
2A,Cooperativismo,CAETANO
2A,Filosofia,Ijaelson
2A,Apicultura/Melip.,Paulo Wanderley
2A,Língua Portuguesa,Amanda
2A,Ed. Física,BARBARA
2A,Geografia,Anúzia
2A,Química,HIGO
2A,Biologia,ELIANE
3A,Irrigação/Drenagem,ELIEZER
3A,Fruticultura,MARIO
3A,Ed. Física,PAMELA
3A,Bovinocultura,TATIANA
3A,Proc. Cons. Alimento,BRUNO
3A,Extensão Rural,Chiquinho
3A,Sociologia,SAULO
3A,Gestão Agronegócio,SERGIO
3A,Língua Portuguesa,RISONELHA
3A,Projeto Agrop.,HUGO
3A,Inglês,JONATHAN
3A,História,Gutiele
3A,Geografia,Anúzia
3A,Matemática,Paulo Cezar
3A,Química,CARLOS
3A,Ovinocaprinocultura,TATIANA
3A,GEST. AMBIENTAL,Allan
3A,Filosofia,Ijaelson
3A,Biologia,ELIANE
3A,Física,GEIMSON
3A,Const. Rurais,OVIDIO
1C,Higiene e Legislação,Flávio
1C,Segurança no Trabalh,Flávio
1C,Artes,LADY JANE
1C,Matemática,Edgley
1C,Filosofia,Tibério
1C,R.H.T.,LADYJANE
1C,Informática Básica,ADSON
1C,Geografia,EDNALDO
1C,Biologia,GLAUCIA
1C,Química,JHUDSON
1C,Língua Portuguesa,Eianny
1C,História,Gutiele
1C,Introdução Ciencias,Aline
1C,Ed. Física,Adriano
1C,Controle de qualidad,DALANY
1C,Sociologia,PEDRO
1C,Inglês,JONATHAN
1C,Microbiologia e Cons,TICIANA
1C,Física,DAVID
2C,História,Gutiele
2C,Geografia,EDNALDO
2C,Análises de Alimento,BRUNO
2C,Matemática,Marcelo Bruno
2C,Filosofia,Tibério
2C,Física,GEIMSON
2C,Tecnologia de Cereai,CAROLINA
2C,Tec. de Vegetais,DALANY
2C,Química,JHUDSON
2C,Biologia,GLAUCIA
2C,Língua Portuguesa,VANALUCIA
2C,Sociologia,PEDRO
2C,I.M.C.,CLAUDIA
2C,Embalagens,KEROLAYNE
2C,Inglês,JONATHAN
2C,Ed. Física,BARBARA
3C,Língua Portuguesa,VANALUCIA
3C,Elaboração de Projet,KEROLAYNE
3C,Geografia,EDNALDO
3C,GEST. AMBIENTAL,Daniele
3C,Gerenciamento de res,Allan
3C,Química,HERMESSON
3C,Matemática,Marcelo Bruno
3C,Inglês,JONATHAN
3C,Gestão Agronegócio,Chiquinho
3C,Ed. Física,Joyce
3C,Física,GEIMSON
3C,Tecnologia de Carnes,JULIANA
3C,Tecnologia de Leites,SUELY
3C,Biologia,GLAUCIA
3C,Sociologia,PEDRO
3C,História,Gutiele
3C,Filosofia,Tibério
1D,Sociologia,SAULO
1D,Biologia,ELIANE
1D,Matemática,GABRIELA
1D,Língua Portuguesa,Eianny
1D,Inglês,JONATHAN
1D,Desenvolvimento rura,OVIDIO
1D,Tópicos especiais em,KARINE
1D,História,Gutiele
1D,Segurança no Trabalh,Allan
1D,Cartografia e geopro,RACKYNELLY
1D,R.H.T.,LADYJANE
1D,Física,DAVID
1D,Geografia,Anúzia
1D,Artes,LADYJANE
1D,Informática Básica,ADSON
1D,Química,JOAO
1D,Filosofia,Ijaelson
1D,Ed. Física,Joyce
2D,Recursos hídricos e,KARINE
2D,Sociologia,SAULO
2D,Língua Portuguesa,VANALUCIA
2D,História,Gutiele
2D,Filosofia,Ijaelson
2D,Educação ambiental,CLAUDIA
2D,Química,Thiago Neves
2D,Sistema de tratament,Daniele
2D,Matemática,GABRIELA
2D,Legislação e poluiçã,PATRICIA
2D,IMC,CLAUDIA
2D,Meio ambiente/socie,SAULO
2D,Biologia,ELIANE
2D,Ed. Física,BARBARA
2D,Física,DAVID
2D,Geografia,Anúzia
2D,Inglês,JONATHAN
3D,História,Gutiele
3D,Conservação de solos,CAETANO
3D,Língua Portuguesa,Amanda
3D,Biologia,ELIANE
3D,Sociologia,SAULO
3D,Física,GEIMSON
3D,Empreendedorismo,MARCELLE
3D,Química,Thiago Neves
3D,Filosofia,Ijaelson
3D,Ed. Física,GIULYANNE
3D,Matemática,GABRIELA
3D,Inglês,JONATHAN
3D,Geografia,Anúzia
3D,Gestão e perícia,Allan
3D,Planejamento e avali,KARINE
3D,Técnicas de amostrag,Allan
3D,Gerenciamento de res,Daniele
1I,Sociologia,PEDRO
1I,R.H.T.,Aline Diniz
1I,Ed. Física,ATILA
1I,Física,DAVID
1I,Geografia,EDNALDO
1I,Matemática,LAIRTON
1I,Meio Ambiente,CLAUDIA
1I,Algoritmos,Rene
1I,Química,Polyana
1I,Língua Portuguesa,LEUZIEDNA
1I,Fundamentos do Compu,GUSTAVO SABRY
1I,Biologia,GILCEAN
1I,Inglês,MIGUEL
1I,História,Paulo Nascimento
1I,Filosofia,Tibério
1I,Segurança no Trabalh,Allan
1I,Artes,LADY JANE
2I,Língua Portuguesa,RISONELHA
2I,Ed. Física,ATILA
2I,Redes de computador,GUSTAVO SABRY
2I,Biologia,GILCEAN
2I,Inglês,MIGUEL
2I,Sociologia,PEDRO
2I,I.M.C.,CLAUDIA
2I,Física,DAVID
2I,Geografia,EDNALDO
2I,História,Paulo Nascimento
2I,Filosofia,Tibério
2I,Matemática,LAIRTON
2I,Analise e projeto de,ADSON
2I,Fundamentos de Hardw,Gutierre
2I,Programação Orientad,Rene
2I,Banco de dados,EDYFRAN
2I,Química,GLAUCIENE
3I,Ed. Física,ATILA
3I,Língua Portuguesa,RISONELHA
3I,Sistemas operacionai,ADSON
3I,Tópicos Especiais,EDYFRAN
3I,Empreendedorismo,MARCELLE
3I,Química,EMMANUELA
3I,Filosofia,Tibério
3I,Biologia,GILCEAN
3I,Inglês,MIGUEL
3I,Geografia,EDNALDO
3I,Sociologia,PEDRO
3I,Desenvolviento Web,Rene
3I,Física,DAVID
3I,Matemática,LAIRTON
3I,História,Paulo Nascimento
3I,Segurança da Informa,Jefferson"""

PONTOS_POSITIVOS = [
    "Professor extremamente atencioso e sempre pronto para esclarecer dúvidas.",
    "Aulas bastante dinâmicas, com exemplos reais de aplicação prática.",
    "Didática excelente, explica matérias complexas de maneira simples e acessível.",
    "Cumpre muito bem o plano de ensino e demonstra profundo domínio do conteúdo.",
    "Muito pontual e prestativo no atendimento individual extraclasse.",
    "Metodologia inovadora que estimula o raciocínio crítico da turma.",
    "Trata os estudantes com extremo respeito e empatia, criando um ambiente ótimo.",
    "O material de apoio disponibilizado é muito completo e de alta qualidade.",
    "A avaliação é coerente com o que é ministrado em sala de aula.",
    "Excelente capacidade de motivar a turma, tornando o aprendizado engajador."
]

PONTOS_MELHORIA = [
    "Poderia reduzir o uso de slides extensos e realizar mais explicações no quadro.",
    "O ritmo das aulas é muito acelerado em alguns momentos mais densos.",
    "A disponibilização dos materiais de estudo poderia ser feita com mais antecedência.",
    "Sugiro incluir mais dinâmicas em grupo ou estudos de caso em vez de avaliações puramente teóricas.",
    "O controle de presença e atrasos na entrada da sala poderia ser um pouco mais flexível.",
    "Poderia responder mais rapidamente aos e-mails e mensagens dos alunos.",
    "As vezes ultrapassa um pouco o horário final da aula para concluir os conteúdos.",
    "Seria proveitoso realizar revisões gerais antes das avaliações bimestrais.",
    "Alguns conceitos complexos poderiam ser explicados com vocabulário mais simplificado.",
    "Os critérios de correção das atividades poderiam ser mais detalhados e transparentes."
]

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # Drop existing tables to establish the new schema cleanly
    print("Limpando tabelas antigas se existirem...")
    cursor.execute("DROP TABLE IF EXISTS Avaliacao")
    cursor.execute("DROP TABLE IF EXISTS Disciplina")
    cursor.execute("DROP TABLE IF EXISTS Periodo")
    cursor.execute("DROP TABLE IF EXISTS Usuario")
    
    print("Criando tabelas...")
    # Tabela Usuario
    cursor.execute("""
    CREATE TABLE Usuario (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL
    );
    """)
    
    # Tabela Periodo
    cursor.execute("""
    CREATE TABLE Periodo (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ano INTEGER NOT NULL,
        bimestre INTEGER NOT NULL,
        ativo INTEGER DEFAULT 0,
        UNIQUE(ano, bimestre)
    );
    """)
    
    # Tabela Disciplina
    cursor.execute("""
    CREATE TABLE Disciplina (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        turma TEXT NOT NULL,
        nome_disciplina TEXT NOT NULL,
        nome_professor TEXT NOT NULL
    );
    """)
    
    # Tabela Avaliacao
    cursor.execute("""
    CREATE TABLE Avaliacao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        disciplina_id INTEGER NOT NULL,
        periodo_id INTEGER NOT NULL,
        nota_conteudo REAL NOT NULL,
        nota_didatica REAL NOT NULL,
        nota_presenca REAL NOT NULL,
        nota_relacionamento REAL NOT NULL,
        pontos_positivos TEXT,
        pontos_melhoria TEXT,
        FOREIGN KEY (disciplina_id) REFERENCES Disciplina(id) ON DELETE CASCADE,
        FOREIGN KEY (periodo_id) REFERENCES Periodo(id) ON DELETE CASCADE
    );
    """)
    
    # Insert default admin user
    print("Criando usuário administrador...")
    admin_pw_hash = generate_password_hash('admin123')
    cursor.execute("INSERT INTO Usuario (username, password_hash) VALUES (?, ?)", ('admin', admin_pw_hash))

    # Insert default Academic Periods
    print("Cadastrando Períodos Letivos...")
    # 2025.4 (Inativo)
    cursor.execute("INSERT INTO Periodo (ano, bimestre, ativo) VALUES (?, ?, ?)", (2025, 4, 0))
    period_inactive_id = cursor.lastrowid
    
    # 2026.1 (Ativo)
    cursor.execute("INSERT INTO Periodo (ano, bimestre, ativo) VALUES (?, ?, ?)", (2026, 1, 1))
    period_active_id = cursor.lastrowid

    # Parse and insert CSV Disciplines
    print("Importando dados do CSV de disciplinas...")
    lines = CSV_DATA.strip().split('\n')
    
    disciplines_count = 0
    evaluations_count = 0
    
    random.seed(42) # Replicable seed
    
    for line in lines[1:]:
        parts = line.strip().split(',')
        if len(parts) == 3:
            turma, disciplina, professor = parts
            cursor.execute("""
                INSERT INTO Disciplina (turma, nome_disciplina, nome_professor) 
                VALUES (?, ?, ?)
            """, (turma, disciplina, professor))
            disciplina_id = cursor.lastrowid
            disciplines_count += 1
            
            # Seed ratings for BOTH periods to demonstrate historical querying
            # Period 1 (Inactive 2025.4): 1 to 3 reviews
            num_evals_p1 = random.randint(1, 3)
            for _ in range(num_evals_p1):
                nota_conteudo = round(random.choices([1, 2, 3, 4, 5], weights=[4, 8, 18, 35, 35])[0] + random.uniform(0, 0.9), 1)
                nota_didatica = round(random.choices([1, 2, 3, 4, 5], weights=[5, 9, 20, 36, 30])[0] + random.uniform(0, 0.9), 1)
                nota_presenca = round(random.choices([1, 2, 3, 4, 5], weights=[2, 5, 15, 28, 50])[0] + random.uniform(0, 0.9), 1)
                nota_relacionamento = round(random.choices([1, 2, 3, 4, 5], weights=[4, 8, 16, 32, 40])[0] + random.uniform(0, 0.9), 1)
                
                nota_conteudo = max(1.0, min(5.0, nota_conteudo))
                nota_didatica = max(1.0, min(5.0, nota_didatica))
                nota_presenca = max(1.0, min(5.0, nota_presenca))
                nota_relacionamento = max(1.0, min(5.0, nota_relacionamento))
                
                pos = random.choice(PONTOS_POSITIVOS) if random.random() > 0.4 else None
                imp = random.choice(PONTOS_MELHORIA) if random.random() > 0.45 else None
                
                cursor.execute("""
                    INSERT INTO Avaliacao (
                        disciplina_id, periodo_id, nota_conteudo, nota_didatica, nota_presenca, nota_relacionamento, 
                        pontos_positivos, pontos_melhoria
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (disciplina_id, period_inactive_id, nota_conteudo, nota_didatica, nota_presenca, nota_relacionamento, pos, imp))
                evaluations_count += 1
                
            # Period 2 (Active 2026.1): 2 to 4 reviews
            num_evals_p2 = random.randint(2, 4)
            for _ in range(num_evals_p2):
                # Generates slightly different distribution to make query results visually interesting between periods
                nota_conteudo = round(random.choices([1, 2, 3, 4, 5], weights=[2, 5, 12, 30, 51])[0] + random.uniform(0, 0.9), 1)
                nota_didatica = round(random.choices([1, 2, 3, 4, 5], weights=[2, 6, 13, 34, 45])[0] + random.uniform(0, 0.9), 1)
                nota_presenca = round(random.choices([1, 2, 3, 4, 5], weights=[1, 3, 10, 24, 62])[0] + random.uniform(0, 0.9), 1)
                nota_relacionamento = round(random.choices([1, 2, 3, 4, 5], weights=[1, 5, 10, 28, 56])[0] + random.uniform(0, 0.9), 1)
                
                nota_conteudo = max(1.0, min(5.0, nota_conteudo))
                nota_didatica = max(1.0, min(5.0, nota_didatica))
                nota_presenca = max(1.0, min(5.0, nota_presenca))
                nota_relacionamento = max(1.0, min(5.0, nota_relacionamento))
                
                pos = random.choice(PONTOS_POSITIVOS) if random.random() > 0.35 else None
                imp = random.choice(PONTOS_MELHORIA) if random.random() > 0.4 else None
                
                cursor.execute("""
                    INSERT INTO Avaliacao (
                        disciplina_id, periodo_id, nota_conteudo, nota_didatica, nota_presenca, nota_relacionamento, 
                        pontos_positivos, pontos_melhoria
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (disciplina_id, period_active_id, nota_conteudo, nota_didatica, nota_presenca, nota_relacionamento, pos, imp))
                evaluations_count += 1

    conn.commit()
    conn.close()
    
    print(f"Banco de dados re-inicializado com sucesso!")
    print(f"Total de Disciplinas importadas: {disciplines_count}")
    print(f"Total de Avaliações dummy inseridas: {evaluations_count}")
    print("Períodos cadastrados: 2025.4 (Inativo) e 2026.1 (Ativo)")
    print("Administrador padrão criado: username 'admin', senha 'admin123'")

if __name__ == '__main__':
    init_db()
