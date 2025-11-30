import os
import json
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

# --- CONFIGURAÇÃO DE LOGIN ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- "O GUARDA" (Bloqueia quem precisa trocar a senha) ---
@app.before_request
def check_password_change():
    if current_user.is_authenticated and current_user.must_change_password:
        # Se o usuário tentar acessar qualquer coisa que NÃO seja trocar a senha ou sair
        if request.endpoint not in ['trocar_senha', 'logout', 'static']:
            flash('Por segurança, você precisa redefinir sua senha antes de continuar.', 'warning')
            return redirect(url_for('trocar_senha'))

# --- MODELOS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    recovery_key = db.Column(db.String(100), nullable=True)
    # NOVA COLUNA: Define se é obrigado a trocar a senha
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

# Cria tabelas
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

# --- ROTA DE MIGRAÇÃO ATUALIZADA ---
@app.route('/migrar_bruna')
def migrar_bruna():
    bruna = User.query.filter_by(username='bruna.emanuele').first()
    
    # Se a Bruna não existir, cria. Se existir, FORÇA a troca de senha.
    if not bruna:
        hashed_pw = generate_password_hash('123456', method='scrypt')
        bruna = User(username='bruna.emanuele', password=hashed_pw, recovery_key='segredo', must_change_password=True)
        db.session.add(bruna)
    else:
        bruna.must_change_password = True # Força a troca na próxima vez
        
    # Migra os lançamentos
    lancamentos_orfãos = Movimentacao.query.filter_by(user_id=None).all()
    for l in lancamentos_orfãos:
        l.user_id = bruna.id
    
    db.session.commit()
    return "Sucesso! Usuária 'bruna.emanuele' configurada. A troca de senha será exigida no login."

# --- ROTAS DE AUTENTICAÇÃO ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            # O @app.before_request vai cuidar de redirecionar se precisar trocar senha
            return redirect(url_for('dashboard'))
        else:
            flash('Login ou senha incorretos.', 'danger')
    return render_template('login.html')

@app.route('/trocar_senha', methods=['GET', 'POST'])
@login_required
def trocar_senha():
    if request.method == 'POST':
        nova_senha = request.form['password']
        confirmacao = request.form['confirm_password']
        
        if nova_senha != confirmacao:
            flash('As senhas não coincidem!', 'danger')
        elif len(nova_senha) < 4:
            flash('A senha deve ter pelo menos 4 caracteres.', 'warning')
        else:
            # Salva a nova senha
            current_user.password = generate_password_hash(nova_senha, method='scrypt')
            current_user.must_change_password = False # Libera o usuário
            db.session.commit()
            flash('Senha atualizada com sucesso! Bem-vinda.', 'success')
            return redirect(url_for('dashboard'))
            
    return render_template('trocar_senha.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        recovery = request.form['recovery']
        
        if User.query.filter_by(username=username).first():
            flash('Usuário já existe!', 'warning')
            return redirect(url_for('register'))
            
        hashed_pw = generate_password_hash(password, method='scrypt')
        # Novos usuários não precisam trocar senha logo de cara
        new_user = User(username=username, password=hashed_pw, recovery_key=recovery, must_change_password=False)
        db.session.add(new_user)
        db.session.commit()
        
        login_user(new_user)
        return redirect(url_for('dashboard'))
        
    return render_template('register.html')

@app.route('/recuperar', methods=['GET', 'POST'])
def recuperar():
    if request.method == 'POST':
        username = request.form['username']
        recovery_try = request.form['recovery']
        new_password = request.form['new_password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.recovery_key == recovery_try:
            user.password = generate_password_hash(new_password, method='scrypt')
            # Se recuperou, pode exigir troca ou não. Aqui vamos liberar direto.
            user.must_change_password = False 
            db.session.commit()
            flash('Senha alterada com sucesso! Faça login.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Usuário ou Palavra-chave incorretos.', 'danger')
            
    return render_template('recuperar.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- ROTAS DO SISTEMA (PROTEGIDAS) ---

@app.route('/')
@login_required
def dashboard():
    movimentacoes = Movimentacao.query.filter_by(user_id=current_user.id).all()
    # ... LÓGICA RESUMIDA (MANTENHA A SUA LOGICA PANDAS AQUI) ...
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