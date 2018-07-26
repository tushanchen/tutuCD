# -*- encoding=UTF-8 -*-

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import pymysql
from flask_admin import Admin,BaseView,expose
from flask_login import current_user
from flask_babelex import Babel

app = Flask(__name__)
admin = Admin(app,name='后台管理')
babel = Babel(app)
app.config['BABEL_DEFAULT_LOCALE'] = 'zh_CN'
app.jinja_env.add_extension('jinja2.ext.loopcontrols')
app.config.from_pyfile('app.conf')
app.secret_key = 'nowcoder'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = '/regloginpage/'
pymysql.install_as_MySQLdb()

class MyView(BaseView):
    def is_accessible(self):
        return current_user.is_authenticated
    @expose('/')
    def index1(self):
        return self.render('index1.html')


admin.add_view(MyView(name='Hello 1', endpoint='test1', category='Test'))
admin.add_view(MyView(name='Hello 2', endpoint='test2', category='Test1'))
admin.add_view(MyView(name='Hello 3', endpoint='test3', category='Test'))

from nowstagram import views, models
