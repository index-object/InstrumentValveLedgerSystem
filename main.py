from app import create_app, db, init_seed_data

app = create_app()

with app.app_context():
    db.create_all()
    init_seed_data()

    from app.models import MaintenancePlan, User, PlanRecipient
    has_recipient = db.session.query(PlanRecipient).first() is not None
    if not has_recipient:
        from sqlalchemy import not_
        no_recipient_plans = MaintenancePlan.query.filter(
            MaintenancePlan.status == "published",
            not_(MaintenancePlan.recipients.any())
        ).all()
        if no_recipient_plans:
            active_emps = User.query.filter(
                User.role == "employee", User.status == "active"
            ).all()
            for plan in no_recipient_plans:
                plan.recipients.extend(active_emps)
            db.session.commit()

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True, port=5000)
