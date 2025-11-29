import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import pandas as pd

app = Flask(__name__)

# --- CONFIGURAÇÃO INTELIGENTE DO BANCO DE DADOS ---
# Tenta pegar o endereço do banco da nuvem (Render)
database_url = os.environ.get('DATABASE_URL')

if database_url:
    # Ajuste necessário: O Render às vezes fornece 'postgres://' mas o SQLAlchemy exige 'postgresql://'
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    # Se não tiver banco na nuvem, usa o arquivo local (Seu PC)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///orcamento.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- MODELO (Igual ao anterior) ---
class Movimentacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    subcategoria = db.Column(db.String(50), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    tipo = db.Column(db.String(10), nullable=False)
    data = db.Column(db.Date, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'descricao': self.descricao,
            'categoria': self.categoria,
            'subcategoria': self.subcategoria,
            'valor': self.valor,
            'tipo': self.tipo,
            'data': self.data
        }

# Cria as tabelas automaticamente (tanto no SQLite quanto no Postgres)
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

# --- ROTAS ---
@app.route('/')
def dashboard():
    movimentacoes = Movimentacao.query.all()
    if not movimentacoes:
        return render_template('dashboard.html', receita_mes=0, despesa_mes=0, saldo_mes=0, saldo_geral=0, categorias_json="{}", meses_labels="[]", receitas_mes="[]", despesas_mes="[]")

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
                           receitas_mes=json.dumps(por_mes['receita'].tolist()), despesas_mes=json.dumps(por_mes['despesa'].tolist()))

@app.route('/novo', methods=['GET', 'POST'])
def novo_lancamento():
    if request.method == 'POST':
        nova_mov = Movimentacao(
            descricao=request.form['descricao'],
            categoria=request.form['categoria'],
            subcategoria=request.form['subcategoria'],
            valor=float(request.form['valor']),
            data=datetime.strptime(request.form['data'], '%Y-%m-%d'),
            tipo=request.form['tipo']
        )
        db.session.add(nova_mov)
        db.session.commit()
        return redirect(url_for('dashboard'))
    return render_template('lancamento.html', categorias=CATEGORIAS, hoje=datetime.now().strftime('%Y-%m-%d'))

@app.route('/extrato')
def extrato():
    movimentacoes = Movimentacao.query.order_by(Movimentacao.data.desc()).all()
    return render_template('extrato.html', movimentacoes=movimentacoes)

@app.route('/excluir/<int:id>')
def excluir(id):
    item = Movimentacao.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for('extrato'))

if __name__ == '__main__':
    app.run(debug=True)