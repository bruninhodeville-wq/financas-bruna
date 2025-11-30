import os
import json
import re # Biblioteca para validação de senha (Regex)
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd

app = Flask(__name__)
app.secret_key = 'chave_secreta_bruna_2025'

# --- CONFIGURAÇÃO DO BANCO ---
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///orcamento.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- LOGIN ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- CONFIGURAÇÃO DE LOGIN ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ADICIONE ESTAS DUAS LINHAS:
login_manager.login_message = "Por favor, faça login para acessar esta página."
login_manager.login_message_category = "warning"

# --- VALIDAÇÃO DE SENHA FORTE ---
def validar_senha_forte(senha):
    # Minimo 6 caracteres
    if len(senha) < 6:
        return False, "A senha deve ter no mínimo 6 caracteres."
    # Letra Maiúscula
    if not re.search(r"[A-Z]", senha):
        return False, "A senha deve conter pelo menos uma letra maiúscula."
    # Números
    if not re.search(r"\d", senha):
        return False, "A senha deve conter pelo menos um número."
    # Caractere Especial
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", senha):
        return False, "A senha deve conter pelo menos um caractere especial (!@#$%)."
    return True, ""

# --- GUARDA DE SEGURANÇA ---
@app.before_request
def check_password_change():
    if current_user.is_authenticated and current_user.must_change_password:
        if request.endpoint not in ['trocar_senha', 'logout', 'static']:
            flash('Por segurança, redefina sua senha seguindo os novos critérios.', 'warning')
            return redirect(url_for('trocar_senha'))

# --- MODELOS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    nome_completo = db.Column(db.String(150), nullable=False) # Novo
    email = db.Column(db.String(150), unique=True, nullable=False) # Novo
    password = db.Column(db.String(255), nullable=False)
    
    # Segurança
    pergunta_seguranca = db.Column(db.String(200), nullable=False) # Novo
    resposta_seguranca = db.Column(db.String(255), nullable=False) # Novo (Será hash)
    must_change_password = db.Column(db.Boolean, default=False) 

class Movimentacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    subcategoria = db.Column(db.String(50), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    tipo = db.Column(db.String(10), nullable=False)
    data = db.Column(db.Date, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) 

with app.app_context():
    db.create_all()

# --- CATEGORIAS ---
CATEGORIAS = {
    "Renda Familiar": ["Salários", "Horas extras", "13º Salário", "Férias", "Outros"],
    "Habitação": ["Aluguel", "IPTU", "Água", "Luz", "Telefones", "TV por Assinatura", "Reformas/Consertos", "Outros", "Prestação"],
    "Saúde": ["Plano de Saúde", "Médico", "Dentista", "Medicamentos", "Seguro de Vida", "Outros"],
    "Transporte": ["Ônibus", "Táxi", "Outros"],
    "Automóvel": ["Prestação", "IPVA", "Combustível", "Lavagens", "Seguro", "Manutenção", "Multas", "Outros"],
    "Despesas Pessoais": ["Alimentação", "Higiene Pessoal", "Cosméticos", "Cabeleireiro", "Vestuário", "Lavanderia", "Academia", "Cursos", "Outros"],
    "Lazer": ["Restaurantes", "Cafés/Bares/Boates", "Locadora de Vídeo", "CDs/Acessórios", "Cinema", "Passagens", "Hotéis", "Livros/Revistas", "Outros"],
    "Cartões de Crédito": ["MasterCard", "Visa", "Outros"],
    "Dependentes": ["Escola/Faculdade", "Cursos Extras", "Material escolar", "Esportes/Uniformes", "Mesada", "Passeios/Férias", "Vestuário", "Saúde/Medicamentos", "Outros"]
}

# --- LISTA DE PERGUNTAS DE SEGURANÇA ---
PERGUNTAS_SEGURANCA = [
    "Qual o nome do seu primeiro animal de estimação?",
    "Qual a cidade onde seus pais se conheceram?",
    "Qual o nome da sua escola primária?",
    "Qual o seu filme favorito?",
    "Qual o nome de solteira da sua mãe?"
]

# --- ROTA DE MIGRAÇÃO (ATUALIZADA) ---
@app.route('/migrar_bruna')
def migrar_bruna():
    bruna = User.query.filter_by(username='bruna.emanuele').first()
    
    # Senha temporária simples (será forçada a troca)
    hashed_pw = generate_password_hash('Mudar@123', method='scrypt')
    # Resposta de segurança padrão para migração
    hashed_resposta = generate_password_hash('migracao', method='scrypt')
    
    if not bruna:
        bruna = User(
            username='bruna.emanuele', 
            nome_completo='Bruna Emanuele',
            email='bruna@email.com', # Email fictício, ela pode mudar no banco se quiser
            password=hashed_pw, 
            pergunta_seguranca='Qual o nome do seu primeiro animal de estimação?',
            resposta_seguranca=hashed_resposta,
            must_change_password=True
        )
        db.session.add(bruna)
    else:
        # Se já existir, atualiza para forçar troca
        bruna.must_change_password = True
        
    lancamentos_orfãos = Movimentacao.query.filter_by(user_id=None).all()
    for l in lancamentos_orfãos:
        l.user_id = bruna.id
    
    db.session.commit()
    return "Sucesso! Usuária migrada. Login: bruna.emanuele / Senha Temp: Mudar@123 (Resposta seg: migracao)"

# --- ROTAS DE AUTENTICAÇÃO ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Login ou senha incorretos.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Captura os campos
        nome = request.form['nome']
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']
        confirm = request.form['confirm_password']
        pergunta = request.form['pergunta']
        resposta = request.form['resposta']

        # 1. Validações Básicas
        if password != confirm:
            flash('As senhas não coincidem!', 'danger')
            return redirect(url_for('register'))
        
        # 2. Validação de Senha Forte
        valida, msg = validar_senha_forte(password)
        if not valida:
            flash(msg, 'warning')
            return redirect(url_for('register'))

        # 3. Verifica duplicidade
        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash('Usuário ou E-mail já cadastrados!', 'warning')
            return redirect(url_for('register'))
            
        # 4. Salva no Banco (Criptografando Senha e Resposta)
        hashed_pw = generate_password_hash(password, method='scrypt')
        hashed_resp = generate_password_hash(resposta.lower().strip(), method='scrypt') # Salva resposta em minúsculo pra facilitar
        
        new_user = User(
            nome_completo=nome,
            email=email,
            username=username, 
            password=hashed_pw,
            pergunta_seguranca=pergunta,
            resposta_seguranca=hashed_resp,
            must_change_password=False
        )
        db.session.add(new_user)
        db.session.commit()
        
        login_user(new_user)
        flash('Conta criada com sucesso!', 'success')
        return redirect(url_for('dashboard'))
        
    return render_template('register.html', perguntas=PERGUNTAS_SEGURANCA)

@app.route('/recuperar', methods=['GET', 'POST'])
def recuperar():
    if request.method == 'POST':
        username = request.form['username']
        pergunta_selecionada = request.form['pergunta']
        resposta_usuario = request.form['resposta']
        new_password = request.form['new_password']
        
        user = User.query.filter_by(username=username).first()
        
        # Verifica Usuário + Pergunta Correta + Resposta Correta
        if user and user.pergunta_seguranca == pergunta_selecionada:
            if check_password_hash(user.resposta_seguranca, resposta_usuario.lower().strip()):
                
                # Valida a nova senha
                valida, msg = validar_senha_forte(new_password)
                if not valida:
                    flash(msg, 'warning')
                    return render_template('recuperar.html', perguntas=PERGUNTAS_SEGURANCA)

                user.password = generate_password_hash(new_password, method='scrypt')
                user.must_change_password = False
                db.session.commit()
                flash('Senha alterada com sucesso! Faça login.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Resposta de segurança incorreta.', 'danger')
        else:
            flash('Usuário não encontrado ou pergunta incorreta.', 'danger')
            
    return render_template('recuperar.html', perguntas=PERGUNTAS_SEGURANCA)

@app.route('/trocar_senha', methods=['GET', 'POST'])
@login_required
def trocar_senha():
    if request.method == 'POST':
        nova_senha = request.form['password']
        confirmacao = request.form['confirm_password']
        
        if nova_senha != confirmacao:
            flash('As senhas não coincidem!', 'danger')
        else:
            # Valida Força
            valida, msg = validar_senha_forte(nova_senha)
            if not valida:
                flash(msg, 'warning')
            else:
                current_user.password = generate_password_hash(nova_senha, method='scrypt')
                current_user.must_change_password = False
                db.session.commit()
                flash('Senha atualizada! Acesso liberado.', 'success')
                return redirect(url_for('dashboard'))
            
    return render_template('trocar_senha.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- ROTAS DO SISTEMA (IGUAIS) ---
@app.route('/')
@login_required
def dashboard():
    movimentacoes = Movimentacao.query.filter_by(user_id=current_user.id).all()
    # ... Lógica resumida para caber aqui (Use a do código anterior) ...
    if not movimentacoes:
         return render_template('dashboard.html', receita_mes=0, despesa_mes=0, saldo_mes=0, saldo_geral=0, categorias_json="{}", meses_labels="[]", receitas_mes="[]", despesas_mes="[]", user=current_user)

    df = pd.DataFrame([m.to_dict() for m in movimentacoes])
    df['data'] = pd.to_datetime(df['data'])
    df['mes_ano'] = df['data'].dt.strftime('%Y-%m')

    total_receita_geral = df[df['tipo'] == 'receita']['valor'].sum()
    total_despesa_geral = df[df['tipo'] == 'despesa']['valor'].sum()
    saldo_geral = total_receita_geral - total_despesa_geral

    mes_atual_str = datetime.now().strftime('%Y-%m')
    df_mes = df[df['mes_ano'] == mes_atual_str]
    receita_mes = df_mes[df_mes['tipo'] == 'receita']['valor'].sum() if not df_mes.empty else 0
    despesa_mes = df_mes[df_mes['tipo'] == 'despesa']['valor'].sum() if not df_mes.empty else 0
    saldo_mes = receita_mes - despesa_mes

    despesas = df[df['tipo'] == 'despesa']
    por_categoria = despesas.groupby('categoria')['valor'].sum().to_dict() if not despesas.empty else {}
    por_mes = df.groupby(['mes_ano', 'tipo'])['valor'].sum().unstack(fill_value=0)
    if 'receita' not in por_mes.columns: por_mes['receita'] = 0
    if 'despesa' not in por_mes.columns: por_mes['despesa'] = 0
    por_mes = por_mes.sort_index()

    return render_template('dashboard.html', 
                           receita_mes=receita_mes, despesa_mes=despesa_mes, saldo_mes=saldo_mes, saldo_geral=saldo_geral,
                           categorias_json=json.dumps(por_categoria), meses_labels=json.dumps(por_mes.index.tolist()),
                           receitas_mes=json.dumps(por_mes['receita'].tolist()), despesas_mes=json.dumps(por_mes['despesa'].tolist()),
                           user=current_user)

@app.route('/novo', methods=['GET', 'POST'])
@login_required
def novo_lancamento():
    if request.method == 'POST':
        nova_mov = Movimentacao(
            descricao=request.form['descricao'],
            categoria=request.form['categoria'],
            subcategoria=request.form['subcategoria'],
            valor=float(request.form['valor']),
            data=datetime.strptime(request.form['data'], '%Y-%m-%d'),
            tipo=request.form['tipo'],
            user_id=current_user.id
        )
        db.session.add(nova_mov)
        db.session.commit()
        return redirect(url_for('dashboard'))
    return render_template('lancamento.html', categorias=CATEGORIAS, hoje=datetime.now().strftime('%Y-%m-%d'))

@app.route('/extrato')
@login_required
def extrato():
    movimentacoes = Movimentacao.query.filter_by(user_id=current_user.id).order_by(Movimentacao.data.desc()).all()
    return render_template('extrato.html', movimentacoes=movimentacoes)

@app.route('/excluir/<int:id>')
@login_required
def excluir(id):
    item = Movimentacao.query.get_or_404(id)
    if item.user_id == current_user.id:
        db.session.delete(item)
        db.session.commit()
    return redirect(url_for('extrato'))

if __name__ == '__main__':
    app.run(debug=True)