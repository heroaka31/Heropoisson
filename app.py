from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///poisson.db'
app.config['SECRET_KEY'] = 'poisson_secret_2024'
db = SQLAlchemy(app)

# ─── Modèle de données ───────────────────────────────────────────────
class Vente(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    date_vente  = db.Column(db.Date, nullable=False, default=date.today)
    type_poisson = db.Column(db.String(100), nullable=False)
    quantite_kg  = db.Column(db.Float, nullable=False)
    prix_kg      = db.Column(db.Float, nullable=False)
    vendeur      = db.Column(db.String(100), nullable=False)
    lieu         = db.Column(db.String(100), nullable=False)
    notes        = db.Column(db.Text, default='')
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def total(self):
        return round(self.quantite_kg * self.prix_kg, 2)


# ─── Routes ──────────────────────────────────────────────────────────
@app.route('/')
def index():
    ventes = Vente.query.order_by(Vente.date_vente.desc()).all()
    total_global = sum(v.total for v in ventes)
    total_kg     = sum(v.quantite_kg for v in ventes)
    nb_ventes    = len(ventes)
    return render_template('index.html',
                           ventes=ventes,
                           total_global=total_global,
                           total_kg=total_kg,
                           nb_ventes=nb_ventes)


@app.route('/ajouter', methods=['GET', 'POST'])
def ajouter():
    if request.method == 'POST':
        try:
            vente = Vente(
                date_vente   = datetime.strptime(request.form['date_vente'], '%Y-%m-%d').date(),
                type_poisson = request.form['type_poisson'].strip(),
                quantite_kg  = float(request.form['quantite_kg']),
                prix_kg      = float(request.form['prix_kg']),
                vendeur      = request.form['vendeur'].strip(),
                lieu         = request.form['lieu'].strip(),
                notes        = request.form.get('notes', '').strip()
            )
            db.session.add(vente)
            db.session.commit()
            flash('Vente enregistrée avec succès !', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            flash(f'Erreur : {e}', 'danger')

    return render_template('ajouter.html', today=date.today().isoformat())


@app.route('/modifier/<int:id>', methods=['GET', 'POST'])
def modifier(id):
    vente = Vente.query.get_or_404(id)
    if request.method == 'POST':
        try:
            vente.date_vente   = datetime.strptime(request.form['date_vente'], '%Y-%m-%d').date()
            vente.type_poisson = request.form['type_poisson'].strip()
            vente.quantite_kg  = float(request.form['quantite_kg'])
            vente.prix_kg      = float(request.form['prix_kg'])
            vente.vendeur      = request.form['vendeur'].strip()
            vente.lieu         = request.form['lieu'].strip()
            vente.notes        = request.form.get('notes', '').strip()
            db.session.commit()
            flash('Vente modifiée avec succès !', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            flash(f'Erreur : {e}', 'danger')

    return render_template('ajouter.html', vente=vente, today=date.today().isoformat())


@app.route('/supprimer/<int:id>')
def supprimer(id):
    vente = Vente.query.get_or_404(id)
    db.session.delete(vente)
    db.session.commit()
    flash('Vente supprimée.', 'warning')
    return redirect(url_for('index'))


@app.route('/rapport')
def rapport():
    ventes = Vente.query.order_by(Vente.date_vente.desc()).all()

    # Regrouper par type de poisson
    stats = {}
    for v in ventes:
        if v.type_poisson not in stats:
            stats[v.type_poisson] = {'quantite': 0, 'total': 0, 'nb': 0}
        stats[v.type_poisson]['quantite'] += v.quantite_kg
        stats[v.type_poisson]['total']    += v.total
        stats[v.type_poisson]['nb']       += 1

    return render_template('rapport.html', stats=stats, ventes=ventes)


# ─── Lancement ───────────────────────────────────────────────────────
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
