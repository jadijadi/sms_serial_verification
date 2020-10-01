from app import app
from app.views import create_sms_table

if __name__ == "__main__":
    create_sms_table()
    app.run("0.0.0.0", debug=False)
