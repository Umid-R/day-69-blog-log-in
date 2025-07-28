from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text,ForeignKey
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
# Import your forms from the forms.py
from forms import CreatePostForm
from forms import RegisterForm
from forms import LoginForm
from forms import CommentForm
import os
from dotenv import load_dotenv
from flask import request
import smtplib
import random

load_dotenv()

date=date.today().year

app = Flask(__name__)
app.config['SECRET_KEY'] =os.getenv('FLASK_KEY')
ckeditor = CKEditor(app)
Bootstrap5(app)

#Profile avatar for the commentator
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

# TODO: Configure Flask-Login
login_manager=LoginManager()
login_manager.init_app(app=app)
#this is only for the Flask-login i dont use it
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User,user_id)



# CREATE DATABASE
class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DB_URI','sqlite:///posts.db')
db = SQLAlchemy(model_class=Base)
db.init_app(app)


# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    author = relationship('User',back_populates='posts')
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    all_comments=relationship('Comment',back_populates='blog_comment')


# TODO: Create a User table for all your registered users.
class User(db.Model,UserMixin):
    __tablename__='users'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    email:Mapped[str]=mapped_column(String(50),nullable=False,unique=True)
    password:Mapped[str]=mapped_column(String(50),nullable=False)
    name:Mapped[str]=mapped_column(String(50),nullable=False)
    posts=relationship('BlogPost',back_populates="author")
    comments=relationship('Comment',back_populates='author')

#Comments table  
class Comment(db.Model):
    __tablename__='comments'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    text:Mapped[str]=mapped_column(String(500),nullable=False)
    author_id:Mapped[int]=mapped_column(ForeignKey('users.id'))
    author=relationship('User',back_populates='comments')
    blog_id:Mapped[int]=mapped_column(ForeignKey('blog_posts.id'))
    blog_comment=relationship('BlogPost',back_populates='all_comments')

with app.app_context():
    db.create_all()



@app.route('/register',methods=['GET','POST'])
def register():
    form=RegisterForm()
    if form.validate_on_submit():
        password=form.password.data
        password=generate_password_hash(password,method='pbkdf2:sha256',salt_length=16)
        if not db.session.execute(db.select(User).where(User.email==form.email.data)).scalar():
            new_user=User(email=form.email.data,password=password,name=form.name.data)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('get_all_posts',date=date))
        else:
            flash('You have already signed up with that email, log in instead!')
            return redirect(url_for('login',date=date))
    return render_template("register.html",form=form,date=date)


# TODO: Retrieve a user from the database based on their email. 
@app.route('/login',methods=['GET','POST'])
def login():
    form=LoginForm()
    if form.validate_on_submit():
        email=form.email.data
        password=form.password.data
        user=db.session.execute(db.select(User).where(User.email==email)).scalar()
        if user:
            if check_password_hash(user.password,password):
                login_user(user)
                print('logged in')
                return redirect(url_for('get_all_posts',date=date))
            else:
                flash('Wrong password')
                return redirect(url_for('login',date=date))
            
        else:
            flash('Not user found with that email')
            return redirect(url_for('login',date=date))
            
        

    return render_template("login.html",form=form,date=date)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts,date=date)



@app.route("/post/<int:post_id>",methods=['GET','POST'])
def show_post(post_id):
    form=CommentForm()
    current_post=db.get_or_404(BlogPost,post_id)
    if form.validate_on_submit():
            if current_user.is_authenticated:
                text=form.body.data
                new_comment=Comment(text=text,blog_id=current_post.id,author_id=current_user.id)
                db.session.add(new_comment)
                
                db.session.commit()
                return redirect(url_for('show_post',post_id=post_id,date=date))
                
            else:
                flash("PLease log in or register to comment!")

                return redirect(url_for('login',date=date))
    
    comments=current_post.all_comments
    requested_post = db.get_or_404(BlogPost, post_id)
    return render_template("post.html", post=requested_post,form=form,comments=comments,date=date)


# TODO: Use a decorator so only an admin user can create a new post
def admin_only(func):
    @wraps(func)
    def wrapper(*args,**kwargs):
        if current_user.is_authenticated  and current_user.id==1:
            return func(*args,**kwargs)
        else:
            return abort(403)
    return wrapper

@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts",date=date))
    return render_template("make-post.html", form=form,date=date)


# TODO: Use a decorator so only an admin user can edit a post

@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id,date=date))
    return render_template("make-post.html", form=edit_form, is_edit=True,date=date)


# TODO: Use a decorator so only an admin user can delete a post

@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts',date=date))


@app.route("/about")
def about():
    return render_template("about.html",date=date)


@app.route("/contact",methods=['GET','POST'])
def contact():
    if request.method=='POST':
        name=request.form.get('name')
        email=request.form.get('email')
        phone=request.form.get('phone')
        message=request.form.get('message')
        EMAIL=os.getenv('EMAIL')
        EMAIL_PASSWORD=os.getenv('EMAIL_PASSWORD')
        with smtplib.SMTP('smtp.gmail.com') as connection:
            connection.starttls()
            connection.login(user=EMAIL,password=EMAIL_PASSWORD)
            connection.sendmail(from_addr=EMAIL,to_addrs='umidraxmatullayev96@gmail.com',msg=f'Subject:New Message From A User\n\n{name}\n{email}\n{phone}\n{message}')
        return redirect(url_for('contact',date=date))       

    return render_template("contact.html",date=date)


if __name__ == "__main__":
    app.run(debug=False, port=5002)
