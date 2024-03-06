from flask_frozen import Freezer
from app import app

app.config['FREEZER_RELATIVE_URLS'] = True
app.config['FREEZER_IGNORED_ROUTES'] = ['send_text_file']  # Exclude the send_text_file route

freezer = Freezer(app)

if __name__ == '__main__':
    freezer.freeze()
