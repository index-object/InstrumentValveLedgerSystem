from app import create_app, db, init_seed_data

app = create_app()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        init_seed_data()
    app.run(host='0.0.0.0', debug=True, port=5000)
