import random
import string
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user, logout_user
from website.forms import GroupForm, OylamaForm
from .models import Group, Member, Poll, User, Vote
from . import db
import json
from .models import get_user_votes, get_user_groups
from .decorators import admin_required
from datetime import datetime, timedelta

views = Blueprint('views', __name__)

@views.route('/')
@login_required
def home():
    return render_template("home.html", user=current_user)

def create_vote_code():
    """Rastgele bir oy verme kodu oluşturur."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=7))

@views.route('/create_group', methods=['GET', 'POST'])
@login_required
@admin_required
def create_group():
    form = GroupForm()
    if form.validate_on_submit():
        group_name = form.name.data
        emails = request.form.getlist('emails')  # Dinamik olarak eklenen e-postaları alın
        
        new_group = Group(name=group_name)
        db.session.add(new_group)
        db.session.commit()
        
        for email in emails:
            user = User.query.filter_by(email=email).first()
            if user:
                new_member = Member(user_id=user.id, group_id=new_group.id)
                db.session.add(new_member)
            else:
                flash(f'{email} adresine sahip bir kullanıcı bulunamadı.', category='error')
        db.session.commit()
        
        # Grup oluşturulduktan sonra kullanıcıyı gruba ekleyin
        new_member = Member(user_id=current_user.id, group_id=new_group.id)
        db.session.add(new_member)
        db.session.commit()
        
        flash('Grup başarıyla oluşturuldu ve kullanıcılar gruba eklendi!', category='success')
        return redirect(url_for('views.home'))
    
    return render_template('create_group.html', user=current_user, form=form)

@views.route('/create_poll', methods=['GET', 'POST'])
@login_required
@admin_required
def create_poll():
    form = OylamaForm()
    user_groups = Group.query.join(Member).filter(Member.user_id == current_user.id).all()
    form.group_id.choices = [(group.id, group.name) for group in user_groups]

    if form.validate_on_submit():
        question = form.question.data
        options = [option.strip() for option in request.form.getlist('options') if option.strip()]
        group_id = form.group_id.data
        days = int(request.form.get('days', 0))
        hours = int(request.form.get('hours', 0))
        minutes = int(request.form.get('minutes', 0))

        duration = timedelta(days=days, hours=hours, minutes=minutes)
        end_time = datetime.utcnow() + duration

        vote_code = create_vote_code()

        new_poll = Poll(question=question, options=json.dumps(options), group_id=group_id, created_by=current_user.id, vote_code=vote_code, end_time=end_time)
        db.session.add(new_poll)
        db.session.commit()

        flash(f"Oylama başarıyla oluşturuldu! Oylama Katılım Kodu: {vote_code}", category='success')
        return redirect(url_for('views.list_polls'))

    return render_template('create_poll.html', user=current_user, form=form)

@views.route('/vote/<int:poll_id>', methods=['GET', 'POST'])
@login_required
def vote(poll_id):
    poll = Poll.query.get(poll_id)
    if not poll:
        flash('Oylama bulunamadı.', category='error')
        return redirect(url_for('views.home'))

    existing_vote = Vote.query.filter_by(user_id=current_user.id, poll_id=poll_id).first()
    if existing_vote:
        flash('Bu oylamaya zaten katıldınız.', category='error')
        return redirect(url_for('views.home'))

    if poll.end_time and poll.end_time < datetime.utcnow():
        flash('Oylama süresi dolmuştur, oy kullanamazsınız.', category='error')
        return redirect(url_for('views.home'))

    if request.method == 'POST':
        vote_code = request.form.get('vote_code')
        if vote_code != poll.vote_code:
            flash('Geçersiz oy verme kodu.', category='error')
            return redirect(url_for('views.vote', poll_id=poll_id))

        choice = request.form.get('choice')
        new_vote = Vote(user_id=current_user.id, poll_id=poll_id, choice=choice)
        db.session.add(new_vote)
        db.session.commit()

        flash('Oy başarıyla gönderildi!', category='success')
        return redirect(url_for('views.home'))

    options = poll.get_options()
    return render_template("vote.html", user=current_user, poll=poll, options=options)

@views.route('/poll/<int:poll_id>/results')
@login_required
def view_results(poll_id):
    poll = Poll.query.get(poll_id)
    if not poll:
        flash('Oylama bulunamadı.', category='error')
        return redirect(url_for('views.home'))

    # Bitiş zamanını kontrol et
    if poll.end_time and poll.end_time > datetime.utcnow():
        flash('Oylama sonuçları henüz erişilebilir değil.', category='error')
        return redirect(url_for('views.home'))

    votes = Vote.query.filter_by(poll_id=poll_id).all()

    # Oyların sayısını hesaplayalım
    total_votes = len(votes)

    # Tüm seçenekleri alalım
    options = poll.get_options()

    # Seçeneklerin oy sayılarını hesaplayalım
    option_vote_counts = {}
    
    for option in options:
        option_vote_counts[option] = 0

    for vote in votes:
        if vote.choice in option_vote_counts:
            option_vote_counts[vote.choice] += 1

    return render_template("poll_results.html", user=current_user, poll=poll, option_vote_counts=option_vote_counts, total_votes=total_votes)

@views.route('/polls')
@login_required
def list_polls():
    user_group_ids = [member.group_id for member in current_user.groups]
    available_polls = Poll.query.filter(Poll.group_id.in_(user_group_ids)).all()
    
    return render_template("polls.html", user=current_user, polls=available_polls)

@views.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
