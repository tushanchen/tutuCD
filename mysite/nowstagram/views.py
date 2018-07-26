# -*- encoding=UTF-8 -*-
import datetime

from wtforms import TextAreaField
from wtforms.widgets import TextArea

from nowstagram import app, db
from nowstagram import models
from nowstagram.models import Image, User, Comment
from flask import render_template, redirect, request, flash, get_flashed_messages, send_from_directory, url_for
import random, hashlib, json, uuid, os
from flask_login import login_user, logout_user, current_user, login_required
from nowstagram.qiniusdk import qiniu_upload_file
from nowstagram import db,admin
from flask_admin import Admin, BaseView, expose
from flask_admin.contrib.sqla import ModelView

@app.route('/index/images/<int:page>/<int:per_page>/')
def index_images(page, per_page):
    paginate = Image.query.order_by(db.desc(Image.id)).paginate(page=page, per_page=per_page, error_out=False)
    map = {'has_next': paginate.has_next}
    images = []
    for image in paginate.items:
        comments = []
        for i in range(0, min(2, len(image.comments))):
            comment = image.comments[i]
            comments.append({'username':comment.user.username,
                             'user_id':comment.user_id,
                             'content':comment.content})
        imgvo = {'id': image.id,
                 'url': image.url,
                 'comment_count': len(image.comments),
                 'user_id': image.user_id,
                 'head_url':image.user.head_url,
                 'created_date':str(image.created_date),
                 'comments':comments}
        images.append(imgvo)

    map['images'] = images
    return json.dumps(map)

@app.route('/')
def index():
    images = Image.query.order_by(db.desc(Image.id)).limit(10).all()
    return render_template('index.html', images=images)


@app.route('/image/<int:image_id>/')
@login_required
def image(image_id):
    image = Image.query.get(image_id)
    if image == None:
        return redirect('/')
    comments = Comment.query.filter_by(image_id=image_id).order_by(db.desc(Comment.id)).limit(20).all()
    return render_template('pageDetail.html', image=image, comments=comments)


@app.route('/profile/<int:user_id>/')
@login_required
def profile(user_id):
    user = User.query.get(user_id)
    if user == None:
        return redirect('/')
    paginate = Image.query.filter_by(user_id=user_id).order_by(db.desc(Image.id)).paginate(page=1, per_page=3, error_out=False)
    return render_template('profile.html', user=user, images=paginate.items, has_next=paginate.has_next)


@app.route('/profile/images/<int:user_id>/<int:page>/<int:per_page>/')
def user_images(user_id, page, per_page):
    paginate = Image.query.filter_by(user_id=user_id).order_by(db.desc(Image.id)).paginate(page=page, per_page=per_page, error_out=False)
    map = {'has_next': paginate.has_next}
    images = []
    for image in paginate.items:
        imgvo = {'id': image.id, 'url': image.url, 'comment_count': len(image.comments)}
        images.append(imgvo)

    map['images'] = images
    return json.dumps(map)


@app.route('/regloginpage/')
def regloginpage():
    msg = ''
    for m in get_flashed_messages(with_categories=False, category_filter=['reglogin']):
        msg = msg + m
    return render_template('login.html', msg=msg, next=request.values.get('next'))


def redirect_with_msg(target, msg, category):
    if msg != None:
        flash(msg, category=category)
    return redirect(target)


@app.route('/login/', methods={'post', 'get'})
def login():
    username = request.values.get('username').strip()
    password = request.values.get('password').strip()

    if username == '' or password == '':
        return redirect_with_msg('/regloginpage/', u'用户名或密码不能为空', 'reglogin')

    user = User.query.filter_by(username=username).first()
    if user == None:
        return redirect_with_msg('/regloginpage/', u'用户名不存在', 'reglogin')

    m = hashlib.md5()
    m.update((password + user.salt).encode('utf8'))
    if (m.hexdigest() != user.password):
        return redirect_with_msg('/regloginpage/', u'密码错误', 'reglogin')

    login_user(user)

    next = request.values.get('next')
    if next != None and next.startswith('/'):
        return redirect(next)

    return redirect('/')


@app.route('/reg/', methods={'post', 'get'})
def reg():
    # request.args
    # request.form
    username = request.values.get('username').strip()
    password = request.values.get('password').strip()

    if username == '' or password == '':
        return redirect_with_msg('/regloginpage/', u'用户名或密码不能为空', 'reglogin')

    user = User.query.filter_by(username=username).first()
    if user != None:
        return redirect_with_msg('/regloginpage/', u'用户名已经存在', 'reglogin')

    # 更多判断

    salt = '.'.join(random.sample('01234567890abcdefghigABCDEFGHI', 10))
    m = hashlib.md5()
    m.update((password + salt).encode('utf8'))
    password = m.hexdigest()
    headurl = 'http://images.nowcoder.com/head/' + str(random.randint(0, 1000)) + 'm.png'
    user = User(username=username, password=password, salt=salt,headurl = headurl)
    db.session.add(user)
    db.session.commit()

    login_user(user)

    next = request.values.get('next')
    if next != None and next.startswith('/'):
        return redirect(next)

    return redirect('/')


@app.route('/logout/')
def logout():
    logout_user()
    return redirect('/')


@app.route('/image/<image_name>')
def view_image(image_name):
    return send_from_directory(app.config['UPLOAD_DIR'], image_name)


@app.route('/addcomment/', methods={'post'})
@login_required
def add_comment():
    image_id = int(request.values['image_id'])
    content = request.values['content']
    comment = Comment(content=content, image_id=image_id, user_id=current_user.id)
    db.session.add(comment)
    db.session.commit()
    return json.dumps({"code":0, "id":comment.id,
                       "content":comment.content,
                       "username":comment.user.username,
                       "user_id":comment.user_id})

def save_to_qiniu(file, file_name):
    return qiniu_upload_file(file, file_name)

def save_to_local(file, file_name):
    save_dir = app.config['UPLOAD_DIR']
    file.save(os.path.join(save_dir, file_name))
    return '/image/' + file_name

@app.route('/upload/', methods={"post"})
@login_required
def upload():
    file = request.files['file']
    # http://werkzeug.pocoo.org/docs/0.10/datastructures/
    # 需要对文件进行裁剪等操作
    file_ext = ''
    if file.filename.find('.') > 0:
        file_ext = file.filename.rsplit('.', 1)[1].strip().lower()
    if file_ext in app.config['ALLOWED_EXT']:
        file_name = str(uuid.uuid1()).replace('-', '') + '.' + file_ext
        url = qiniu_upload_file(file, file_name)
        #url = save_to_local(file, file_name)
        if url != None:
            db.session.add(Image(url=url, user_id = current_user.id,created_date=datetime.now()))
            db.session.commit()

    return redirect('/profile/%d' % current_user.id)

@app.route('/secret')
@login_required
def secret():
    return 'Only authenticated users are allowed!'

class MyUserModel(ModelView):
    column_display_pk = True
    column_formatters = dict( password = lambda v,c,m,p:'**'+m.password[-6:])
    column_searchable_list = (User.username,)
    column_labels = dict(username = '用户名',password = '密码', id = '编号')
    column_exclude_list = ['salt',]

    def is_accessible(self):
        if  current_user.is_active or  current_user.is_authenticated:
              return True
        # if current_user.has_role('superuser'):
        #     return True
        return False

    def _handle_view(self, name, **kwargs):
        """
        Override builtin _handle_view in order to redirect users when a view is not accessible.
        """
        if not self.is_accessible():
            if current_user.is_authenticated:
                # permission denied
                os.abort(403)
            else:
                # login
                return redirect(url_for('regloginpage', next=request.url))

class CKTextAreaWidget(TextArea):
    def __call__(self, field, **kwargs):
        if kwargs.get('class'):
            kwargs['class'] += ' ckeditor'
        else:
            kwargs.setdefault('class', 'ckeditor')
        return super(CKTextAreaWidget, self).__call__(field, **kwargs)

class CKTextAreaField(TextAreaField):
    widget = CKTextAreaWidget()

class MyCommentModel(ModelView):
    extra_js = ['//cdn.ckeditor.com/4.6.0/standard/ckeditor.js']

    form_overrides = {
        'content': CKTextAreaField
    }

admin.add_view(MyUserModel(User,db.session))
admin.add_view(MyCommentModel(Comment,db.session))
admin.add_view(ModelView(Image,db.session))