from functools import wraps
from flask import abort
from flask_login import current_user

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:  # Kullanıcının yönetici olup olmadığını kontrol edin
            abort(403)  # 403 Hata Kodu: Yasak
        return f(*args, **kwargs)
    return decorated_function
