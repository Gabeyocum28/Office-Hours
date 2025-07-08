from app import create_app, db

def add_email_verification_columns():
    app = create_app()
    with app.app_context():
        try:
            db.engine.execute('ALTER TABLE user ADD COLUMN verification_token VARCHAR(100);')
            print("Added verification_token column.")
        except Exception as e:
            print("verification_token column probably already exists:", e)
        
        try:
            db.engine.execute('ALTER TABLE user ADD COLUMN token_expiry DATETIME;')
            print("Added token_expiry column.")
        except Exception as e:
            print("token_expiry column probably already exists:", e)

        try:
            db.engine.execute('ALTER TABLE user ADD COLUMN is_verified BOOLEAN DEFAULT FALSE;')
            print("Added is_verified column.")
        except Exception as e:
            print("is_verified column probably already exists:", e)

if __name__ == "__main__":
    add_email_verification_columns()
    print("Done.")
