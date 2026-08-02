from app import app, db, Usuario, bcrypt

with app.app_context():
    u = Usuario.query.filter_by(email="eduardo@mind.com.br").first()
    if u:
        u.hash_senha = bcrypt.generate_password_hash("123456").decode("utf-8")
        db.session.commit()
        print("Password reset successfully to: 123456")
    else:
        print("User not found.")
